from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .p0a_support import _load_hate_schema, _validate_schema_value

SCHEMA_VERSION = "HATE/v1"

def _build_evidence_map(
    run_id: str,
    run_attempt: int,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    test_node_ids: dict[str, str],
    coverage_node_ids: dict[str, str],
    missing_executions: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    unsupported_claims: list[dict[str, Any]],
    unsafe_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build evidence-map.json internal representation."""
    requirements: list[dict[str, Any]] = []
    risks_list: list[dict[str, Any]] = []
    tests_list: list[dict[str, Any]] = []
    evidence_list: list[dict[str, Any]] = []
    findings_list: list[dict[str, Any]] = []
    contracts_list: list[dict[str, Any]] = []
    mutations_list: list[dict[str, Any]] = []
    evidence_strength_list: list[dict[str, Any]] = []
    escaped_defects_list: list[dict[str, Any]] = []

    for node in nodes:
        kind = node.get("kind", "")
        if kind == "risk":
            risks_list.append({
                "risk_id": node["id"],
                "label": node.get("label", ""),
                "severity": node.get("data", {}).get("severity", "medium"),
            })
        elif kind == "test":
            tests_list.append({
                "test_id": node["id"],
                "canonical_test_id": node.get("data", {}).get("canonical_test_id", ""),
                "status": node.get("data", {}).get("status", "unknown"),
            })
        elif kind in {"execution_evidence", "coverage", "evidence_artifact", "contract_evidence", "mutation_evidence", "evidence_strength"}:
            data = node.get("data", {})
            evidence_list.append({
                "evidence_id": node["id"],
                "kind": kind,
                "label": node.get("label", ""),
                "artifact_kind": data.get("kind", ""),
                "adapter": data.get("adapter", ""),
                "artifact_role": data.get("artifact_role", ""),
                "path": data.get("path", ""),
                "sourceRefs": node.get("sourceRefs", []),
            })
            if kind == "evidence_strength":
                evidence_strength_list.append({
                    "test_id": data.get("test_id", ""),
                    "flake_score": data.get("flake_score", "unknown"),
                    "mutation_score": data.get("mutation_score", "unknown"),
                    "sample_size": data.get("sample_size", 0),
                    "computed_at": data.get("computed_at", ""),
                    "inputs": data.get("inputs", []),
                    "sourceRefs": node.get("sourceRefs", []),
                })
            if kind == "contract_evidence":
                contracts_list.append({
                    "contract_id": data.get("contract_id", ""),
                    "provider": data.get("provider", ""),
                    "consumer": data.get("consumer", ""),
                    "interaction": data.get("interaction", ""),
                    "status": data.get("status", ""),
                    "required": data.get("required", False),
                    "sourceRefs": node.get("sourceRefs", []),
                })
            if kind == "mutation_evidence":
                mutations_list.append({
                    "mutation_id": data.get("mutation_id", ""),
                    "status": data.get("status", ""),
                    "mutator": data.get("mutator", ""),
                    "file": data.get("file", ""),
                    "start_line": data.get("start_line", 0),
                    "end_line": data.get("end_line", 0),
                    "covered_by": data.get("covered_by", []),
                    "killed_by": data.get("killed_by", []),
                    "sourceRefs": node.get("sourceRefs", []),
                })
        elif kind == "finding":
            data = node.get("data", {})
            findings_list.append({
                "finding_id": node["id"],
                "rule_id": data.get("rule_id", ""),
                "level": data.get("level", "warning"),
                "severity": data.get("severity", "warning"),
                "location": data.get("location", {}),
                "sourceRefs": node.get("sourceRefs", []),
            })
        elif kind == "escaped_defect":
            data = node.get("data", {})
            escaped_defects_list.append({
                "defect_id": data.get("defect_id", ""),
                "detected_at": data.get("detected_at", ""),
                "severity": data.get("severity", "unknown"),
                "affected_requirement_ids": data.get("affected_requirement_ids", []),
                "affected_risk_ids": data.get("affected_risk_ids", []),
                "release_ref": data.get("release_ref", ""),
                "sourceRefs": node.get("sourceRefs", []),
            })

    # Build link arrays
    requires_test_links: list[dict[str, Any]] = []
    evidenced_by_links: list[dict[str, Any]] = []
    supports_links: list[dict[str, Any]] = []
    touches_links: list[dict[str, Any]] = []
    contradicts_links: list[dict[str, Any]] = []
    escaped_after_links: list[dict[str, Any]] = []
    relates_to_requirement_links: list[dict[str, Any]] = []
    relates_to_risk_links: list[dict[str, Any]] = []
    has_strength_links: list[dict[str, Any]] = []

    for edge in edges:
        kind = edge.get("kind", "")
        link = {
            "from": edge.get("from", ""),
            "to": edge.get("to", ""),
            "confidence": edge.get("traceability", {}).get("confidence", "medium"),
        }
        traceability = edge.get("traceability", {})
        if traceability.get("adapter"):
            link["adapter"] = traceability.get("adapter")
        if traceability.get("artifact_role"):
            link["artifact_role"] = traceability.get("artifact_role")
        if kind == "requires_test":
            requires_test_links.append(link)
        elif kind == "evidenced_by":
            evidenced_by_links.append(link)
        elif kind == "supports":
            supports_links.append(link)
        elif kind == "touches":
            touches_links.append(link)
        elif kind == "contradicts":
            contradicts_links.append(link)
        elif kind == "escaped_after":
            escaped_after_links.append(link)
        elif kind == "relates_to_requirement":
            relates_to_requirement_links.append(link)
        elif kind == "relates_to_risk":
            relates_to_risk_links.append(link)
        elif kind == "has_strength":
            has_strength_links.append(link)

    # Build gaps
    for miss in missing_executions:
        unsupported_claims.append({
            "risk_id": miss.get("risk_id", ""),
            "expected_test": miss.get("expected_test_ref", ""),
            "reason": miss.get("reason", ""),
        })

    links = {
        "requires_test": requires_test_links,
        "evidenced_by": evidenced_by_links,
        "supports": supports_links,
        "touches": touches_links,
        "contradicts": contradicts_links,
    }
    if escaped_defects_list:
        links.update({
            "escaped_after": escaped_after_links,
            "relates_to_requirement": relates_to_requirement_links,
            "relates_to_risk": relates_to_risk_links,
        })
    if evidence_strength_list:
        links["has_strength"] = has_strength_links

    evidence_map = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "requirements": requirements,
        "risks": risks_list,
        "tests": tests_list,
        "evidence": evidence_list,
        "findings": findings_list,
        "contracts": contracts_list,
        "mutations": mutations_list,
        "links": links,
        "gaps": {
            "unsupported_claims": unsupported_claims,
            "missing_execution": missing_executions,
            "missing_coverage": [],
            "unsafe_artifacts": unsafe_artifacts,
        },
    }
    if evidence_strength_list:
        evidence_map["evidence_strength"] = evidence_strength_list
    if escaped_defects_list:
        evidence_map["escaped_defects"] = escaped_defects_list
    return evidence_map


def _calculate_completeness(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    missing_artifacts: list[str],
    missing_executions: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    parser_failures: list[dict[str, Any]],
    unsupported_claims: list[dict[str, Any]],
    unsafe_artifacts: list[dict[str, Any]],
    excluded_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculate P0b completeness score per contract."""
    base = 1.0

    # Penalty for missing required artifacts
    if missing_artifacts:
        base -= 0.20

    # Penalty for parser failures
    base -= 0.15 * len(parser_failures)

    # Penalty for unsupported high-risk claims (missing execution)
    high_risk_missing = [
        m for m in missing_executions
        if any(
            r.get("risk_id") == m.get("risk_id") and r.get("severity") == "high"
            for r in risks
        )
    ]
    base -= 0.10 * len(high_risk_missing)

    # Penalty when sourceRefs or artifact safety leave the export incomplete.
    if any(claim.get("reason") == "risk source_refs missing" for claim in unsupported_claims):
        base -= 0.10
    if any(claim.get("reason") in {"required contract failed", "required contract evidence missing"} for claim in unsupported_claims):
        base -= 0.10
    if any(claim.get("reason") in {"required mutation survived", "required mutation evidence missing"} for claim in unsupported_claims):
        base -= 0.10
    if any(str(claim.get("reason", "")).startswith("escaped defect") for claim in unsupported_claims):
        base -= 0.10
    if unsafe_artifacts:
        base -= 0.10

    # Floor at 0
    score = max(0.0, base)

    # partial=true means the bundle is exportable but not complete enough to
    # claim full QEG evidence coverage.
    partial = bool(missing_artifacts or parser_failures or unsupported_claims or missing_executions or unsafe_artifacts)

    return {
        "score": round(score, 2),
        "partial": partial,
        "parserFailures": parser_failures,
        "unsupportedClaims": unsupported_claims,
        "excludedArtifacts": excluded_artifacts,
    }


def _artifact_refs_from_test(payload: dict[str, Any]) -> list[str]:
    """Extract artifact ids from a test result payload."""
    refs: list[str] = []
    for item in payload.get("artifacts", []):
        if isinstance(item, str):
            refs.append(item)
        elif isinstance(item, dict) and item.get("artifact_id"):
            refs.append(str(item["artifact_id"]))
    return refs


def _artifact_is_unsafe(artifact: dict[str, Any]) -> bool:
    """Return true when an artifact must not be exported into QEG evidence."""
    if not artifact.get("safe_for_summary", False):
        return True
    if artifact.get("classification") in {"secret", "pii", "restricted"}:
        return True
    checks = artifact.get("security_checks", {})
    return any(value == "fail" for value in checks.values())


def _playwright_artifact_role(artifact: dict[str, Any]) -> str:
    """Return a stable Playwright artifact role when an artifact is a browser-test attachment."""
    explicit_adapter = str(artifact.get("adapter") or artifact.get("framework") or "").lower()
    explicit_role = str(artifact.get("artifact_role") or artifact.get("role") or "").lower()
    kind = str(artifact.get("kind") or "").lower()
    path = str(artifact.get("path") or "").lower()
    artifact_id = str(artifact.get("artifact_id") or "").lower()
    haystack = f"{path} {artifact_id}"

    role = explicit_role if explicit_role in {"trace", "screenshot", "video", "log"} else ""
    if not role:
        if kind in {"trace", "screenshot", "video"}:
            role = kind
        elif path.endswith(".log") or "log" in artifact_id or "/logs/" in path:
            role = "log"

    if not role:
        return ""
    if explicit_adapter in {"playwright", "pw"} or "playwright" in haystack or role in {"trace", "screenshot", "video"}:
        return role
    return ""


def _dedupe_gap_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Preserve order while removing duplicate gap entries."""
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = json.dumps(item, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _validate_qeg_bundle_schema(bundle: dict[str, Any]) -> dict[str, Any]:
    """Validate qeg-bundle.json against the local QEG compatibility schema."""
    schema = _load_hate_schema("qeg-bundle.schema.json")
    errors = _validate_schema_value(bundle, schema, "$")
    return {
        "schema": "schemas/HATE/v1/qeg-bundle.schema.json",
        "valid": not errors,
        "errors": errors,
    }


def _build_risk_debt_register(
    run_id: str,
    run_attempt: int,
    missing_executions: list[dict[str, Any]],
    risks: list[dict[str, Any]] | None = None,
    lifecycle: dict[str, Any] | None = None,
    created_at: str = "",
) -> dict[str, Any]:
    """Build risk-debt entries for high-risk obligations without execution."""
    risks = risks or []
    lifecycle = lifecycle or {}
    lifecycle_items = lifecycle.get("items", [])
    if not isinstance(lifecycle_items, list):
        lifecycle_items = []
    current_items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for miss in missing_executions:
        risk_id = str(miss.get("risk_id", ""))
        expected_test_ref = str(miss.get("expected_test_ref", ""))
        debt_id = f"risk-debt:{risk_id}:{_hash_test_id(expected_test_ref)}"
        risk = next((item for item in risks if item.get("risk_id") == risk_id), {})
        lifecycle_item = _find_lifecycle_item(lifecycle_items, debt_id, risk_id, "missing_execution")
        status = str(lifecycle_item.get("status") or "open")
        item = {
            "debt_id": debt_id,
            "risk_debt_id": debt_id,
            "risk_id": risk_id,
            "debt_type": "missing_execution",
            "severity": risk.get("severity", "high"),
            "expected_test_ref": expected_test_ref,
            "status": status,
            "owner": lifecycle_item.get("owner", "unassigned"),
            "created_at": lifecycle_item.get("created_at", created_at),
            "last_seen_at": created_at,
            "age_days": int(lifecycle_item.get("age_days", 0)),
            "sourceRefs": ["qeg-export-report.json"],
            "source_refs": ["qeg-export-report.json"],
            "evidence_refs": lifecycle_item.get("evidence_refs", []),
            "recommended_actions": lifecycle_item.get("recommended_actions", ["Add or restore execution evidence for the required high-risk test."]),
            "blocking_profile": lifecycle_item.get("blocking_profile", ["release"]),
            "qeg_refs": lifecycle_item.get("qeg_refs", []),
            "manual_bridge_refs": lifecycle_item.get("manual_bridge_refs", ["manual-bb-bridge-requests.jsonl"]),
        }
        current_items.append(item)
        seen_ids.add(debt_id)
    historical_items: list[dict[str, Any]] = []
    for lifecycle_item in lifecycle_items:
        if not isinstance(lifecycle_item, dict):
            continue
        debt_id = str(lifecycle_item.get("debt_id") or lifecycle_item.get("risk_debt_id") or "")
        if not debt_id or debt_id in seen_ids:
            continue
        historical_items.append({
            "debt_id": debt_id,
            "risk_debt_id": debt_id,
            "risk_id": lifecycle_item.get("risk_id", ""),
            "debt_type": lifecycle_item.get("debt_type", "missing_execution"),
            "severity": lifecycle_item.get("severity", "medium"),
            "expected_test_ref": lifecycle_item.get("expected_test_ref", ""),
            "status": lifecycle_item.get("status", "open"),
            "owner": lifecycle_item.get("owner", "unassigned"),
            "created_at": lifecycle_item.get("created_at", created_at),
            "last_seen_at": lifecycle_item.get("last_seen_at", created_at),
            "age_days": int(lifecycle_item.get("age_days", 0)),
            "sourceRefs": lifecycle_item.get("sourceRefs", lifecycle_item.get("source_refs", ["risk-debt-lifecycle.json"])),
            "source_refs": lifecycle_item.get("source_refs", lifecycle_item.get("sourceRefs", ["risk-debt-lifecycle.json"])),
            "evidence_refs": lifecycle_item.get("evidence_refs", []),
            "recommended_actions": lifecycle_item.get("recommended_actions", []),
            "blocking_profile": lifecycle_item.get("blocking_profile", []),
            "qeg_refs": lifecycle_item.get("qeg_refs", []),
            "manual_bridge_refs": lifecycle_item.get("manual_bridge_refs", []),
        })
    items = current_items + historical_items
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "profile_version": SCHEMA_VERSION,
        "summary": _risk_debt_summary(items),
        "items": items,
        "debts": items,
    }


def _find_lifecycle_item(items: list[Any], debt_id: str, risk_id: str, debt_type: str) -> dict[str, Any]:
    for item in items:
        if not isinstance(item, dict):
            continue
        item_debt_id = str(item.get("debt_id") or item.get("risk_debt_id") or "")
        if item_debt_id == debt_id:
            return item
        if item.get("risk_id") == risk_id and item.get("debt_type", debt_type) == debt_type:
            return item
    return {}


def _risk_debt_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    for item in items:
        status = str(item.get("status", "open"))
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "total_count": len(items),
        "open_count": by_status.get("open", 0),
        "acknowledged_count": by_status.get("acknowledged", 0),
        "mitigated_count": by_status.get("mitigated", 0),
        "stale_count": by_status.get("stale", 0),
        "by_status": by_status,
    }


def _build_manual_bridge_requests(
    run_id: str,
    run_attempt: int,
    missing_executions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build manual-bb bridge requests for missing high-risk execution."""
    requests: list[dict[str, Any]] = []
    for miss in missing_executions:
        risk_id = str(miss.get("risk_id", ""))
        expected_test_ref = str(miss.get("expected_test_ref", ""))
        request_id = f"manual-bb:{run_id}:{run_attempt}:{risk_id}:{_hash_test_id(expected_test_ref)}"
        changed_entities = _manual_changed_entities(miss)
        source_refs = _manual_source_refs(miss)
        oracle_refs = _manual_oracle_refs(miss)
        requests.append({
            "schema_version": SCHEMA_VERSION,
            "record_type": "manual_bb_bridge_request",
            "contract_type": "manual_supplement_request",
            "request_id": request_id,
            "run_id": run_id,
            "run_attempt": run_attempt,
            "source_run_id": run_id,
            "risk_id": risk_id,
            "risk_title": miss.get("risk_title", ""),
            "severity": miss.get("severity", "high"),
            "request_type": "missing_execution_review",
            "gap_type": "no_execution",
            "status": "open",
            "recommended_manual_layer": "manual-scripted",
            "changed_entity_id": changed_entities[0]["entity_id"] if changed_entities else "",
            "changed_entity_ids": [entity["entity_id"] for entity in changed_entities],
            "changed_entities": changed_entities,
            "obligation_id": miss.get("obligation_id", ""),
            "expected_test_ref": expected_test_ref,
            "required_test_layers": miss.get("required_test_layers", []),
            "required_evidence_kinds": miss.get("required_evidence_kinds", []),
            "required_oracle_refs": oracle_refs,
            "evidence_refs": ["qeg-export-report.json", "risk-debt-register.json"],
            "sourceRefs": ["risk-debt-register.json", "qeg-export-report.json", *[ref["id"] for ref in source_refs]],
            "source_refs": source_refs,
            "manual_case_seed": _manual_case_seed(request_id, miss, source_refs, oracle_refs),
            "assumptions": [
                {
                    "id": "ASM-MANUAL-BRIDGE-001",
                    "text": "Automated execution evidence is absent, so manual scripted review is required until execution evidence is restored.",
                    "severity": "high",
                    "impact_on_coverage": "Release evidence remains partial and must not be treated as a waiver.",
                }
            ],
            "confidence": "medium",
            "reason": miss.get("reason", ""),
            "handoff_policy": {
                "target_suite_id": "manual-bb-harness",
                "primary_view": "black",
                "does_not_override_qeg_verdict": True,
                "manual_execution_evidence_required_for_mitigation": True,
            },
        })
    return requests


def _manual_changed_entities(miss: dict[str, Any]) -> list[dict[str, Any]]:
    changed_entities = miss.get("changed_entities", [])
    if not isinstance(changed_entities, list):
        return []
    normalized: list[dict[str, Any]] = []
    for entity in changed_entities:
        if not isinstance(entity, dict):
            continue
        normalized.append({
            "entity_id": str(entity.get("entity_id", "")),
            "path": str(entity.get("path", "")).replace("\\", "/"),
            "ranges": entity.get("ranges", []),
        })
    return normalized


def _manual_source_refs(miss: dict[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = [
        {"id": "qeg-export-report.json", "kind": "auto_test", "excerpt": "missing_execution"},
        {"id": "risk-debt-register.json", "kind": "ops", "excerpt": "risk debt for unresolved execution gap"},
    ]
    for ref in miss.get("risk_source_refs", []):
        refs.append({"id": str(ref), "kind": "code_review", "excerpt": str(miss.get("risk_title", ""))})
    for entity in _manual_changed_entities(miss):
        if entity["path"]:
            refs.append({"id": entity["path"], "kind": "code_review", "excerpt": entity["entity_id"]})
    return _dedupe_source_refs(refs)


def _manual_oracle_refs(miss: dict[str, Any]) -> list[str]:
    refs = [str(ref) for ref in miss.get("risk_source_refs", []) if str(ref)]
    expected_test_ref = str(miss.get("expected_test_ref", ""))
    if expected_test_ref:
        refs.append(expected_test_ref)
    return sorted(set(refs))


def _manual_case_seed(
    request_id: str,
    miss: dict[str, Any],
    source_refs: list[dict[str, str]],
    oracle_refs: list[str],
) -> dict[str, Any]:
    risk_id = str(miss.get("risk_id", ""))
    risk_title = str(miss.get("risk_title", risk_id))
    expected_test_ref = str(miss.get("expected_test_ref", ""))
    priority = "P1" if str(miss.get("severity", "high")) in {"high", "critical"} else "P2"
    return {
        "tc_id": f"TC-{_hash_test_id(request_id)[:8]}",
        "title": f"Manual confirmation for {risk_title or risk_id}",
        "priority": priority,
        "primary_view": "black",
        "techniques": ["regression", "risk_based"],
        "preconditions": [
            f"Changed risk is in scope: {risk_id}",
            f"Automated execution is missing: {expected_test_ref}",
        ],
        "steps": [
            "Exercise the user-visible behavior covered by the missing automated test obligation.",
            "Capture expected and actual results with enough evidence for QEG ingestion.",
        ],
        "expected_results": [
            "Behavior satisfies the referenced risk source and acceptance evidence.",
            "No regression is observed on the changed high-risk path.",
        ],
        "oracle": {
            "type": "specified" if oracle_refs else "derived",
            "refs": oracle_refs,
        },
        "estimate_minutes": 10,
        "trace_to": [risk_id, request_id, expected_test_ref],
        "source_refs": source_refs,
    }


def _dedupe_source_refs(refs: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for ref in refs:
        key = (ref.get("id", ""), ref.get("kind", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def _hash_test_id(canonical_test_id: str) -> str:
    """Compute deterministic hash for test node ID."""
    digest = hashlib.sha256(canonical_test_id.encode("utf-8")).hexdigest()
    return digest[:16]


def _hash_path(file_path: str) -> str:
    """Compute deterministic hash for path-based node ID."""
    # Normalize path for cross-platform consistency
    normalized = file_path.replace("\\", "/")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return digest[:16]


def _read_json(path: Path) -> dict[str, Any]:
    """Read JSON file."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return data


def _read_ndjson(path: Path) -> list[dict[str, Any]]:
    """Read NDJSON file."""
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            records.append(record)
    return records


def _write_json(path: Path, value: dict[str, Any]) -> None:
    """Write JSON file with indentation."""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
