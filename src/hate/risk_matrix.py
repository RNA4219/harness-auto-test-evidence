from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .evidence_envelope import source_refs
from .risk_matrix_types import (
    SEVERITY_AGING_DAYS,
    SEVERITY_LEVELS,
    RiskCoverageEntry,
    RiskDebtItem,
    _compute_age_days,
    _required_evidence_for_severity,
)


def _check_expired_accepted_debt(debt_items: list[RiskDebtItem], current_time: str) -> tuple[list[dict[str, Any]], list[RiskDebtItem]]:
    """Check for expired accepted debt and invalid expiry formats.

    Returns findings and updated debt items with status changed to 'open' for expired.
    """
    findings = []
    updated_items = []

    for item in debt_items:
        # Only check accepted debt with expiry_date
        if item.status == "accepted" and item.expiry_date:
            # Try to parse expiry_date
            try:
                expiry_dt = datetime.fromisoformat(item.expiry_date.replace("Z", "+00:00"))
                now_dt = datetime.fromisoformat(current_time.replace("Z", "+00:00"))

                if expiry_dt < now_dt:
                    # Debt has expired - it's now a blocker
                    findings.append({
                        "code": "accepted_debt_expired",
                        "severity": "hard",
                        "message": f"accepted risk debt {item.risk_debt_id} has expired at {item.expiry_date}",
                        "sourceRefs": item.source_refs,
                    })
                    # Change status to open (expired acceptance becomes blocker)
                    updated_item = RiskDebtItem(
                        risk_debt_id=item.risk_debt_id,
                        debt_type=item.debt_type,
                        severity=item.severity,
                        status="open",  # Expired -> reopens as blocker
                        risk_id=item.risk_id,
                        owner=item.owner,
                        created_at=item.created_at,
                        last_seen_at=item.last_seen_at,
                        age_days=item.age_days,
                        source_refs=item.source_refs,
                        recommended_actions=item.recommended_actions + ["re-evaluate acceptance or resolve"],
                        blocking_profile=item.blocking_profile + ["default"],
                        expiry_date=item.expiry_date,
                        justification=item.justification,
                    )
                    updated_items.append(updated_item)
                else:
                    # Still valid, keep as-is
                    updated_items.append(item)
            except ValueError:
                # Invalid expiry_date format
                findings.append({
                    "code": "accepted_debt_invalid_expiry_format",
                    "severity": "medium",
                    "message": f"accepted risk debt {item.risk_debt_id} has invalid expiry_date format: {item.expiry_date}",
                    "sourceRefs": item.source_refs,
                })
                updated_items.append(item)
        else:
            # Not accepted or no expiry, keep as-is
            updated_items.append(item)

    return findings, updated_items


def build_risk_coverage_matrix(
    graph: dict[str, Any],
    *,
    profile: str = "default",
    fixture_id: str = "risk-matrix",
    now: str | None = None,
    historical_debt: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    edges = graph.get("edges", [])
    findings = list(graph.get("findings", []))

    risk_nodes = [node for node in nodes.values() if node.get("kind") == "risk"]
    entries: list[RiskCoverageEntry] = []
    debt_items: list[RiskDebtItem] = []

    current_time = now or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    # Process historical debt items first - compute age from created_at to now
    historical_by_risk: dict[str, RiskDebtItem] = {}
    if historical_debt:
        for item in historical_debt:
            created_at = item.get("created_at", current_time)
            age_days = _compute_age_days(created_at, current_time)
            debt = RiskDebtItem(
                risk_debt_id=item.get("risk_debt_id", ""),
                debt_type=item.get("debt_type", "missing_execution"),
                severity=item.get("severity", "medium"),
                status=item.get("status", "open"),
                risk_id=item.get("risk_id", ""),
                owner=item.get("owner"),
                created_at=created_at,
                last_seen_at=current_time,
                age_days=age_days,
                source_refs=item.get("source_refs", []),
                recommended_actions=item.get("recommended_actions", []),
                blocking_profile=item.get("blocking_profile", []),
                expiry_date=item.get("expiry_date"),
                justification=item.get("justification"),
            )
            historical_by_risk[debt.risk_id] = debt

    for risk in risk_nodes:
        risk_id = str(risk["id"]).removeprefix("risk:")
        severity = str(risk.get("data", {}).get("severity") or "medium")
        if severity not in SEVERITY_LEVELS:
            severity = "medium"

        # Extract requirement_refs from risk data
        requirement_refs = risk.get("data", {}).get("requirement_refs", [])
        if not isinstance(requirement_refs, list):
            requirement_refs = []

        # Determine required evidence classes based on severity and requirement
        required_evidence_classes = _required_evidence_for_severity(severity)

        evidence_info = _classify_evidence_for_risk(risk_id, nodes, edges, requirement_refs)
        oracle_strength = _compute_oracle_strength(evidence_info)
        gap_class = _determine_gap_class(evidence_info, oracle_strength, severity)
        readiness_effect = _determine_readiness_effect(severity, gap_class, profile, evidence_info)

        refs = risk.get("sourceRefs", [])
        entries.append(
            RiskCoverageEntry(
                risk_id=risk_id,
                severity=severity,
                evidence_class=evidence_info.get("primary_class"),
                oracle_strength=oracle_strength,
                gap_class=gap_class,
                readiness_effect=readiness_effect,
                sourceRefs=refs,
                requirement_refs=requirement_refs,
                required_evidence_classes=required_evidence_classes,
                observed_evidence_classes=evidence_info.get("all_classes", []),
                owner=risk.get("data", {}).get("owner"),
                due_date=risk.get("data", {}).get("due_date"),
            )
        )

        if gap_class and readiness_effect in {"blocked", "hold"}:
            # Use historical debt if available, otherwise create fresh
            if risk_id in historical_by_risk:
                debt_items.append(historical_by_risk[risk_id])
            else:
                debt_items.append(
                    _create_debt_item(
                        risk_id=risk_id,
                        gap_class=gap_class,
                        severity=severity,
                        refs=refs,
                        current_time=current_time,
                    )
                )

    # Add historical debt for risks no longer in graph (closed/resolved)
    for risk_id, debt in historical_by_risk.items():
        if risk_id not in {str(r["id"]).removeprefix("risk:") for r in risk_nodes}:
            debt_items.append(debt)

    unsupported_claims = _detect_unsupported_claims(nodes, edges)
    for claim in unsupported_claims:
        claim_id = claim.get("claim_id", "")
        findings.append(
            {
                "code": "unsupported_claim_no_evidence",
                "severity": "hard",
                "message": f"unsupported claim has no evidence path: {claim_id}",
                "sourceRefs": claim.get("sourceRefs", []),
            }
        )
        debt_items.append(
            _create_debt_item(
                risk_id=claim_id,
                gap_class="unsupported_claim",
                severity="high",
                refs=claim.get("sourceRefs", []),
                current_time=current_time,
                debt_type="traceability_gap",
            )
        )

    # Check for manual reviews without owner (hard DQ)
    manual_review_nodes = [node for node in nodes.values() if node.get("kind") == "manual_review"]
    for review in manual_review_nodes:
        owner = review.get("data", {}).get("owner") or review.get("owner")
        if owner is None:
            review_id = str(review.get("id", "")).removeprefix("manual_review:")
            findings.append(
                {
                    "code": "manual_review_no_owner",
                    "severity": "hard",
                    "message": f"manual review {review_id} has no owner assigned - hard disqualification",
                    "sourceRefs": review.get("sourceRefs", []),
                }
            )

    stale_threshold_items = _check_stale_debt(debt_items, current_time)
    for item in stale_threshold_items:
        findings.append(
            {
                "code": "risk_debt_stale",
                "severity": "medium",
                "message": f"risk debt {item.risk_debt_id} exceeds stale threshold for severity {item.severity}",
                "sourceRefs": item.source_refs,
            }
        )

    # Check for expired accepted debt and invalid expiry formats
    expiry_findings, debt_items = _check_expired_accepted_debt(debt_items, current_time)
    findings.extend(expiry_findings)

    overall_status = _compute_matrix_overall_status(entries, findings)
    matrix_projection = _build_dashboard_projection(entries, debt_items)

    return {
        "schema_version": "HATE/v1",
        "record_type": "risk_coverage_matrix",
        "fixture_id": fixture_id,
        "profile": profile,
        "summary": {
            "overall_status": overall_status,
            "risk_count": len(entries),
            "covered_count": sum(1 for e in entries if e.gap_class is None),
            "gap_count": sum(1 for e in entries if e.gap_class is not None),
            "hold_count": sum(1 for e in entries if e.readiness_effect == "hold"),
            "blocked_count": sum(1 for e in entries if e.readiness_effect == "blocked"),
            "debt_count": len(debt_items),
            "stale_count": len(stale_threshold_items),
        },
        "entries": [entry.as_dict() for entry in entries],
        "risk_debt": [item.as_dict() for item in debt_items],
        "matrix_projection": matrix_projection,
        "findings": findings,
        "sourceRefs": sorted({ref for entry in entries for ref in entry.sourceRefs}),
    }


def _classify_evidence_for_risk(
    risk_id: str,
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    requirement_refs: list[str],
) -> dict[str, Any]:
    risk_node_id = f"risk:{risk_id}"
    connected_evidence = []
    has_static_blocker = False

    # First check for edges from this risk
    for edge in edges:
        if edge.get("kind") == "blocked_by" and edge.get("from") == risk_node_id:
            to_id = edge.get("to", "")
            to_node = nodes.get(to_id)
            if to_node:
                kind = to_node.get("kind", "")
                # Static findings are blockers, not coverage evidence
                if kind == "finding":
                    has_static_blocker = True
                    # Don't add to connected_evidence - findings indicate problems
                elif kind in {"contract", "mutation", "manual_review", "execution"}:
                    # Contract, mutation, manual_review, and execution can provide coverage
                    connected_evidence.append(to_node)

    # If risk has requirement_refs, only consider evidence tied to those requirements
    if requirement_refs:
        valid_requirement_ids = {f"requirement:{req_id}" for req_id in requirement_refs}

        for edge in edges:
            if edge.get("kind") in {"supported_by", "reviewed_by"}:
                from_id = edge.get("from", "")
                # Only include evidence from requirements the risk is associated with
                if from_id in valid_requirement_ids:
                    to_id = edge.get("to", "")
                    to_node = nodes.get(to_id)
                    if to_node and to_node.get("kind") != "finding":
                        connected_evidence.append(to_node)

        # Also check requirement -> test -> execution chains
        for req_id in requirement_refs:
            req_node_id = f"requirement:{req_id}"
            req_edges = [e for e in edges if e.get("from") == req_node_id and e.get("kind") == "requires_test"]
            for req_edge in req_edges:
                test_id = req_edge.get("to", "")
                test_node = nodes.get(test_id)
                if test_node:
                    exec_edges = [e for e in edges if e.get("from") == test_id and e.get("kind") == "executed_by"]
                    for exec_edge in exec_edges:
                        exec_id = exec_edge.get("to", "")
                        exec_node = nodes.get(exec_id)
                        if exec_node:
                            connected_evidence.append(exec_node)
    else:
        # If no requirement_refs specified, use legacy logic for backward compatibility
        for edge in edges:
            if edge.get("kind") in {"supported_by", "reviewed_by"}:
                from_id = edge.get("from", "")
                if from_id.startswith("requirement:"):
                    req_edges = [e for e in edges if e.get("from") == from_id and e.get("kind") == "requires_test"]
                    for req_edge in req_edges:
                        test_id = req_edge.get("to", "")
                        test_node = nodes.get(test_id)
                        if test_node:
                            exec_edges = [e for e in edges if e.get("from") == test_id and e.get("kind") == "executed_by"]
                            for exec_edge in exec_edges:
                                exec_id = exec_edge.get("to", "")
                                exec_node = nodes.get(exec_id)
                                if exec_node:
                                    connected_evidence.append(exec_node)

    # Deduplicate evidence nodes
    seen_ids = set()
    unique_evidence = []
    for node in connected_evidence:
        node_id = node.get("id", "")
        if node_id not in seen_ids:
            seen_ids.add(node_id)
            unique_evidence.append(node)

    if not unique_evidence and not has_static_blocker:
        return {"primary_class": None, "evidence_nodes": [], "has_oracle": False, "all_classes": [], "has_static_blocker": False}

    evidence_classes_found: set[str] = set()
    has_oracle = False

    for node in unique_evidence:
        kind = node.get("kind", "")
        data = node.get("data", {})

        if kind == "execution":
            payload = data.get("payload", {})
            status = payload.get("status", "")
            has_assertions = payload.get("has_assertions", True)
            if status in {"passed", "failed"} and has_assertions:
                evidence_classes_found.add("executable_oracle")
                has_oracle = True
            else:
                evidence_classes_found.add("coverage_only")

        elif kind == "contract":
            status = data.get("payload", {}).get("status", "")
            if status == "passed":
                evidence_classes_found.add("contract_check")
                has_oracle = True
            else:
                evidence_classes_found.add("contract_check")

        elif kind == "mutation":
            status = data.get("payload", {}).get("status", "")
            if status == "killed":
                evidence_classes_found.add("mutation_score")
                has_oracle = True
            else:
                evidence_classes_found.add("mutation_score")

        elif kind == "coverage":
            contexts = data.get("payload", {}).get("contexts", [])
            has_contexts = bool(contexts)
            if has_contexts:
                evidence_classes_found.add("coverage_only")
            else:
                evidence_classes_found.add("coverage_only")

        elif kind == "manual_review":
            status = data.get("status", "") or data.get("data", {}).get("status", "")
            if status == "approved":
                evidence_classes_found.add("manual_review")
                has_oracle = True

    primary_class = _select_primary_evidence_class(evidence_classes_found)

    return {
        "primary_class": primary_class,
        "evidence_nodes": [node["id"] for node in unique_evidence],
        "has_oracle": has_oracle,
        "all_classes": sorted(evidence_classes_found),
        "has_static_blocker": has_static_blocker,
    }


def _select_primary_evidence_class(classes: set[str]) -> str | None:
    priority = ["executable_oracle", "contract_check", "mutation_score", "static_finding", "manual_review", "coverage_only"]
    for cls in priority:
        if cls in classes:
            return cls
    return None


def _compute_oracle_strength(evidence_info: dict[str, Any]) -> float:
    if evidence_info.get("has_oracle"):
        primary_class = evidence_info.get("primary_class")
        if primary_class == "executable_oracle":
            return 0.9
        if primary_class == "contract_check":
            return 0.85
        if primary_class == "mutation_score":
            return 0.75
        if primary_class == "static_finding":
            return 0.6
        if primary_class == "manual_review":
            return 0.5
    if evidence_info.get("primary_class") == "coverage_only":
        return 0.2
    if evidence_info.get("primary_class") is None:
        return 0.0
    return 0.1


def _determine_gap_class(evidence_info: dict[str, Any], oracle_strength: float, severity: str) -> str | None:
    """Determine gap classification based on evidence vs required classes."""
    # If static finding is blocking, it's a blocker not a gap
    if evidence_info.get("has_static_blocker"):
        return "blocked_by_static_finding"

    if evidence_info.get("primary_class") is None:
        # No evidence at all - use legacy classification
        return "missing_execution"

    if evidence_info.get("primary_class") == "coverage_only":
        return "coverage_gap"
    if oracle_strength < 0.5:
        return "oracle_weak"
    if not evidence_info.get("has_oracle"):
        return "no_oracle"
    return None


def _determine_readiness_effect(severity: str, gap_class: str | None, profile: str, evidence_info: dict[str, Any] | None = None) -> str:
    """Determine readiness effect based on gap, severity, and blockers."""
    # Static findings block regardless of other evidence
    if evidence_info and evidence_info.get("has_static_blocker"):
        return "blocked"

    if gap_class is None:
        return "pass"

    if gap_class == "unsupported_claim":
        return "blocked"

    if gap_class == "blocked_by_static_finding":
        return "blocked"

    if severity in {"critical", "high"}:
        if gap_class in {"missing_execution", "no_oracle", "missing_oracle"}:
            if profile in {"release", "product"}:
                return "blocked"
            return "hold"
        if gap_class in {"oracle_weak", "coverage_gap"}:
            if profile in {"release", "product"}:
                return "hold"
            return "soft_gap"

    if severity == "medium":
        if gap_class in {"missing_execution", "no_oracle", "missing_oracle"}:
            if profile in {"release", "product"}:
                return "hold"
            return "soft_gap"
        return "soft_gap"

    if severity == "low":
        return "soft_gap"

    return "soft_gap"


def _create_debt_item(
    risk_id: str,
    gap_class: str,
    severity: str,
    refs: list[str],
    current_time: str,
    debt_type: str | None = None,
) -> RiskDebtItem:
    actual_debt_type = debt_type or _gap_to_debt_type(gap_class)
    recommended_actions = _recommended_actions_for_debt_type(actual_debt_type)
    blocking_profile = _blocking_profile_for_severity(severity)

    return RiskDebtItem(
        risk_debt_id=f"riskdebt_{risk_id}_{actual_debt_type}",
        debt_type=actual_debt_type,
        severity=severity,
        status="open",
        risk_id=risk_id,
        owner=None,
        created_at=current_time,
        last_seen_at=current_time,
        age_days=0,
        source_refs=refs,
        recommended_actions=recommended_actions,
        blocking_profile=blocking_profile,
    )


def _gap_to_debt_type(gap_class: str) -> str:
    mapping = {
        "missing_execution": "missing_execution",
        "coverage_gap": "coverage_gap",
        "oracle_weak": "manual_required",
        "no_oracle": "manual_required",
        "unsupported_claim": "traceability_gap",
    }
    return mapping.get(gap_class, "missing_execution")


def _recommended_actions_for_debt_type(debt_type: str) -> list[str]:
    mapping = {
        "missing_execution": ["add unit test", "add integration test", "add e2e test"],
        "coverage_gap": ["add test covering changed lines/branches", "add coverage context"],
        "manual_required": ["request manual review", "add explicit oracle"],
        "contract_gap": ["add pact verification", "run can-i-deploy"],
        "mutation_gap": ["run mutation testing", "add Stryker evidence"],
        "static_unresolved": ["fix SARIF finding", "add suppression with justification"],
        "traceability_gap": ["add requirement_ref", "link test to requirement"],
    }
    return mapping.get(debt_type, ["investigate gap"])


def _blocking_profile_for_severity(severity: str) -> list[str]:
    if severity == "critical":
        return ["default", "strict", "release", "product"]
    if severity == "high":
        return ["strict", "release", "product"]
    if severity == "medium":
        return ["release", "product"]
    return []


def _detect_unsupported_claims(nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claim_nodes = [node for node in nodes.values() if node.get("kind") == "release_claim"]
    supported = _supported_claim_ids(edges)
    unsupported = []

    for claim in claim_nodes:
        claim_id = str(claim["id"]).removeprefix("release_claim:")
        if claim["id"] not in supported:
            unsupported.append(
                {
                    "claim_id": claim_id,
                    "sourceRefs": claim.get("sourceRefs", []),
                }
            )
    return unsupported


def _supported_claim_ids(edges: list[dict[str, Any]]) -> set[str]:
    requirement_to_claims: dict[str, set[str]] = {}
    supported_requirements: set[str] = set()

    for edge in edges:
        if edge.get("kind") == "derived_from" and str(edge.get("from", "")).startswith("release_claim:"):
            requirement_to_claims.setdefault(str(edge["to"]), set()).add(str(edge["from"]))
        if edge.get("kind") in {"supported_by", "reviewed_by"} and str(edge.get("from", "")).startswith("requirement:"):
            supported_requirements.add(str(edge["from"]))

    supported_claims: set[str] = set()
    for requirement_id in supported_requirements:
        supported_claims.update(requirement_to_claims.get(requirement_id, set()))
    return supported_claims


def _check_stale_debt(debt_items: list[RiskDebtItem], current_time: str) -> list[RiskDebtItem]:
    stale_items = []
    try:
        now_dt = datetime.fromisoformat(current_time.replace("Z", "+00:00"))
    except ValueError:
        return stale_items

    for item in debt_items:
        threshold_days = SEVERITY_AGING_DAYS.get(item.severity, 30)
        if item.age_days > threshold_days:
            stale_items.append(item)

    return stale_items


def _compute_matrix_overall_status(entries: list[RiskCoverageEntry], findings: list[dict[str, Any]]) -> str:
    if any(finding.get("severity") == "hard" for finding in findings):
        return "blocked"

    blocked_count = sum(1 for e in entries if e.readiness_effect == "blocked")
    if blocked_count > 0:
        return "blocked"

    hold_count = sum(1 for e in entries if e.readiness_effect == "hold")
    if hold_count > 0:
        return "hold"

    soft_gap_count = sum(1 for e in entries if e.readiness_effect == "soft_gap")
    if soft_gap_count > 0:
        return "soft_gap"

    return "pass"


def _build_dashboard_projection(entries: list[RiskCoverageEntry], debt_items: list[RiskDebtItem]) -> dict[str, Any]:
    by_severity: dict[str, dict[str, int]] = {}
    for severity in SEVERITY_LEVELS:
        by_severity[severity] = {
            "total": 0,
            "covered": 0,
            "gaps": 0,
        }

    for entry in entries:
        sev = entry.severity
        by_severity[sev]["total"] += 1
        if entry.gap_class is None:
            by_severity[sev]["covered"] += 1
        else:
            by_severity[sev]["gaps"] += 1

    by_gap_class: dict[str, int] = {}
    for entry in entries:
        if entry.gap_class:
            by_gap_class[entry.gap_class] = by_gap_class.get(entry.gap_class, 0) + 1

    by_evidence_class: dict[str, int] = {}
    for entry in entries:
        if entry.evidence_class:
            by_evidence_class[entry.evidence_class] = by_evidence_class.get(entry.evidence_class, 0) + 1

    debt_summary = {
        "total": len(debt_items),
        "open": sum(1 for item in debt_items if item.status == "open"),
        "by_severity": {sev: sum(1 for item in debt_items if item.severity == sev) for sev in SEVERITY_LEVELS},
    }

    return {
        "by_severity": by_severity,
        "by_gap_class": dict(sorted(by_gap_class.items())),
        "by_evidence_class": dict(sorted(by_evidence_class.items())),
        "debt_summary": debt_summary,
        "rows": [entry.as_dict() for entry in sorted(entries, key=lambda e: (e.severity, e.risk_id))],
    }
