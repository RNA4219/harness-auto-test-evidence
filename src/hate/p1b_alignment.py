"""RanD requirement alignment and trace-link assembly for P1b."""

from __future__ import annotations

from typing import Any


SCHEMA_VERSION = "HATE/v1"


def _build_requirement_alignment(
    run_id: str,
    run_attempt: int,
    bundle: dict[str, Any],
    report: dict[str, Any],
    aete: dict[str, Any],
    doctor: dict[str, Any],
    source_refs: list[str],
    version: str,
    rand_requirements: dict[str, Any] | None = None,
    rand_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    missing_execution = report.get("missing_execution", [])
    unsupported = report.get("unsupportedClaims", [])
    doctor_findings = doctor.get("summary", {}).get("finding_count", 0)
    gate_verdict = "conditional_go" if missing_execution or unsupported or doctor_findings else "go"
    requirements = _requirements_from_rand_packet(rand_requirements, missing_execution, source_refs)
    if not requirements:
        requirements = [{
            "requirement_id": "REQ-HATE-P1B-WORKFLOW-INTEGRATION",
            "statement": "Generate advisory RanD alignment, Shipyard evidence, and workflow-cookbook mapping artifacts without overriding upstream gates.",
            "gate_verdict": gate_verdict,
            "upstream_gate_verdict": gate_verdict,
            "testability": "high",
            "implementation_alignment": "implemented",
            "evidence_coverage": "partial" if missing_execution else "covered",
            "kpis": [],
            "acceptance_criteria": [],
            "risk_refs": [],
            "supported_evidence_refs": [
                "qeg-bundle.json",
                "qeg-export-report.json",
                "aete-score.json",
                "doctor-report.json",
            ],
            "unverified_acceptance": [
                {
                    "acceptance_id": "AC-HATE-P1B-HIGH-RISK-GAP",
                    "risk_id": gap.get("risk_id", ""),
                    "reason": gap.get("reason", "missing execution evidence"),
                    "required_action": "Keep RanD verdict unchanged and attach manual-bb bridge evidence until automated execution exists.",
                    "source_refs": ["qeg-export-report.json"],
                }
                for gap in missing_execution
            ],
            "source_refs": source_refs,
        }]
    trace_links = _build_requirement_trace_links(requirements, bundle)
    for requirement in requirements:
        requirement["trace_links"] = trace_links.get(requirement["requirement_id"], [])
        requirement["evidence_link_status"] = "linked" if requirement["trace_links"] else "unlinked"
        requirement["linked_risk_count"] = len({link["risk_id"] for link in requirement["trace_links"] if link.get("risk_id")})
    audit_verdict = _audit_overall_verdict(rand_audit)
    summary_gate_verdict = _aggregate_gate_verdicts(
        [_aggregate_requirement_verdict(requirements, gate_verdict), audit_verdict or ""],
        gate_verdict,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "requirement_alignment",
        "run_id": run_id,
        "run_attempt": run_attempt,
        "source_tool": "harness-auto-test-evidence",
        "source_version": version,
        "requirements": requirements,
        "manual_bb_bridge": _manual_bridge_items(missing_execution),
        "summary": {
            "requirement_count": len(requirements),
            "gate_verdict": summary_gate_verdict,
            "aete_weighted_score": aete.get("weighted_score"),
            "doctor_finding_count": doctor_findings,
            "unverified_acceptance_count": len(missing_execution),
            "rand_requirement_count": len(rand_requirements.get("requirements", [])) if isinstance(rand_requirements, dict) else 0,
            "rand_audit_overall_assessment": audit_verdict or "",
            "trace_link_count": sum(len(item.get("trace_links", [])) for item in requirements),
            "fully_linked_requirement_count": sum(1 for item in requirements if item.get("evidence_link_status") == "linked"),
        },
        "rand": {
            "requirements_packet_ingested": bool(rand_requirements),
            "packet_id": rand_requirements.get("packet_id", "") if isinstance(rand_requirements, dict) else "",
            "source_tool": rand_requirements.get("source_tool", "RanD") if isinstance(rand_requirements, dict) else "",
            "verdicts_preserved": True,
        },
        "rand_audit": _build_rand_audit_summary(rand_audit),
        "boundary": {
            "rand_verdict_override": False,
            "rand_audit_overwrite": False,
            "manual_bb_gate_override": False,
            "publish_gate_override": False,
            "release_gate_override": False,
        },
        "source_refs": source_refs,
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _requirements_from_rand_packet(
    rand_requirements: dict[str, Any] | None,
    missing_execution: list[dict[str, Any]],
    source_refs: list[str],
) -> list[dict[str, Any]]:
    if not isinstance(rand_requirements, dict):
        return []
    raw_requirements = rand_requirements.get("requirements", [])
    if not isinstance(raw_requirements, list):
        return []
    requirements: list[dict[str, Any]] = []
    for raw in raw_requirements:
        if not isinstance(raw, dict):
            continue
        requirement_id = str(raw.get("requirement_id") or raw.get("id") or "")
        if not requirement_id:
            continue
        gate_verdict = str(raw.get("gate_verdict") or raw.get("verdict") or "unknown")
        risk_refs = [str(item) for item in raw.get("risk_refs", raw.get("risks", [])) if str(item)]
        related_missing = [
            gap for gap in missing_execution
            if not risk_refs or str(gap.get("risk_id", "")) in risk_refs
        ]
        requirements.append({
            "requirement_id": requirement_id,
            "statement": str(raw.get("statement") or raw.get("title") or ""),
            "gate_verdict": gate_verdict,
            "upstream_gate_verdict": gate_verdict,
            "testability": raw.get("testability", "unknown"),
            "implementation_alignment": raw.get("implementation_alignment", "advisory"),
            "evidence_coverage": "partial" if related_missing else "covered",
            "kpis": raw.get("kpis", []),
            "acceptance_criteria": raw.get("acceptance_criteria", raw.get("acceptance_refs", [])),
            "risk_refs": risk_refs,
            "supported_evidence_refs": [
                "qeg-bundle.json",
                "qeg-export-report.json",
                "aete-score.json",
                "doctor-report.json",
            ],
            "unverified_acceptance": [
                {
                    "acceptance_id": f"AC-{requirement_id}-MISSING-EXECUTION",
                    "risk_id": gap.get("risk_id", ""),
                    "reason": gap.get("reason", "missing execution evidence"),
                    "required_action": "Keep RanD verdict unchanged and attach manual-bb bridge evidence until automated execution exists.",
                    "source_refs": ["qeg-export-report.json"],
                }
                for gap in related_missing
            ],
            "source_refs": [*source_refs, *[str(ref) for ref in raw.get("source_refs", [])]],
        })
    return requirements


def _build_requirement_trace_links(requirements: list[dict[str, Any]], bundle: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    nodes = {str(node.get("id", "")): node for node in bundle.get("nodes", []) if isinstance(node, dict)}
    edges = [edge for edge in bundle.get("edges", []) if isinstance(edge, dict)]
    trace_links: dict[str, list[dict[str, Any]]] = {}
    for requirement in requirements:
        requirement_id = str(requirement.get("requirement_id", ""))
        links: list[dict[str, Any]] = []
        for risk_ref in requirement.get("risk_refs", []):
            risk_id = str(risk_ref)
            risk_node_id = risk_id if risk_id.startswith("risk:") else f"risk:{risk_id}"
            risk_node = nodes.get(risk_node_id, {})
            changed_nodes = _edge_sources(edges, nodes, kind="touches", target_id=risk_node_id)
            test_nodes = _edge_targets(edges, nodes, kind="requires_test", source_id=risk_node_id)
            if not test_nodes:
                links.append(_trace_link(requirement_id, risk_id, risk_node, None, None, [], changed_nodes))
                continue
            for test_node in test_nodes:
                execution_nodes = _edge_targets(edges, nodes, kind="evidenced_by", source_id=str(test_node.get("id", "")))
                coverage_nodes = _edge_sources(edges, nodes, kind="supports", target_id=str(test_node.get("id", "")))
                links.append(_trace_link(requirement_id, risk_id, risk_node, test_node, execution_nodes[0] if execution_nodes else None, coverage_nodes, changed_nodes))
        trace_links[requirement_id] = links
    return trace_links


def _edge_targets(edges: list[dict[str, Any]], nodes: dict[str, dict[str, Any]], *, kind: str, source_id: str) -> list[dict[str, Any]]:
    return [
        nodes[edge["to"]]
        for edge in edges
        if edge.get("kind") == kind and edge.get("from") == source_id and edge.get("to") in nodes
    ]


def _edge_sources(edges: list[dict[str, Any]], nodes: dict[str, dict[str, Any]], *, kind: str, target_id: str) -> list[dict[str, Any]]:
    return [
        nodes[edge["from"]]
        for edge in edges
        if edge.get("kind") == kind and edge.get("to") == target_id and edge.get("from") in nodes
    ]


def _trace_link(
    requirement_id: str,
    risk_id: str,
    risk_node: dict[str, Any],
    test_node: dict[str, Any] | None,
    execution_node: dict[str, Any] | None,
    coverage_nodes: list[dict[str, Any]],
    changed_nodes: list[dict[str, Any]],
) -> dict[str, Any]:
    test_data = test_node.get("data", {}) if isinstance(test_node, dict) else {}
    execution_data = execution_node.get("data", {}) if isinstance(execution_node, dict) else {}
    return {
        "requirement_id": requirement_id,
        "risk_id": risk_id,
        "risk_node_id": str(risk_node.get("id", "")),
        "risk_severity": risk_node.get("data", {}).get("severity", ""),
        "changed_code_refs": [
            {
                "node_id": str(node.get("id", "")),
                "path": node.get("data", {}).get("path", ""),
                "start_line": node.get("data", {}).get("start_line"),
                "end_line": node.get("data", {}).get("end_line"),
            }
            for node in changed_nodes
        ],
        "test_node_id": str(test_node.get("id", "")) if isinstance(test_node, dict) else "",
        "canonical_test_id": str(test_data.get("canonical_test_id", "")),
        "test_status": str(test_data.get("status", "")),
        "execution_node_id": str(execution_node.get("id", "")) if isinstance(execution_node, dict) else "",
        "execution_status": str(execution_data.get("status", "")),
        "coverage_refs": [
            {
                "node_id": str(node.get("id", "")),
                "file": node.get("data", {}).get("file", ""),
                "contexts": node.get("data", {}).get("contexts", []),
            }
            for node in coverage_nodes
        ],
        "evidence_state": "covered" if test_node and execution_node else "missing_execution",
        "source_refs": ["qeg-bundle.json"],
    }


def _aggregate_requirement_verdict(requirements: list[dict[str, Any]], fallback: str) -> str:
    verdicts = [str(item.get("gate_verdict", "")) for item in requirements]
    return _aggregate_gate_verdicts(verdicts, fallback)


def _aggregate_gate_verdicts(verdicts: list[str], fallback: str) -> str:
    if "no_go" in verdicts:
        return "no_go"
    if "conditional_go" in verdicts:
        return "conditional_go"
    if "go" in verdicts:
        return "go"
    return fallback


def _audit_overall_verdict(rand_audit: dict[str, Any] | None) -> str:
    if not isinstance(rand_audit, dict):
        return ""
    gate_summary = rand_audit.get("gate_summary", {})
    if isinstance(gate_summary, dict):
        return str(gate_summary.get("overall_assessment") or "")
    return ""


def _build_rand_audit_summary(rand_audit: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(rand_audit, dict):
        return {
            "audit_packet_ingested": False,
            "packet_id": "",
            "overall_assessment": "",
            "overall_reason": "",
            "requirement_verdicts": [],
            "verdicts_preserved": True,
            "no_overwrite_enforced": True,
        }
    gate_summary = rand_audit.get("gate_summary", {})
    if not isinstance(gate_summary, dict):
        gate_summary = {}
    requirements = rand_audit.get("requirements", [])
    requirement_verdicts = [
        {
            "requirement_id": str(item.get("requirement_id", "")),
            "gate_verdict": str(item.get("gate_verdict", "")),
            "upstream_gate_verdict": str(item.get("gate_verdict", "")),
        }
        for item in requirements
        if isinstance(item, dict) and item.get("requirement_id")
    ] if isinstance(requirements, list) else []
    return {
        "audit_packet_ingested": True,
        "packet_id": str(rand_audit.get("packet_id") or rand_audit.get("document_id") or ""),
        "overall_assessment": str(gate_summary.get("overall_assessment") or ""),
        "overall_reason": str(gate_summary.get("overall_reason") or ""),
        "gate_summary": gate_summary,
        "requirement_verdicts": requirement_verdicts,
        "verdicts_preserved": True,
        "no_overwrite_enforced": True,
    }


def _manual_bridge_items(missing_execution: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "bridge_id": f"manual-bb:{gap.get('risk_id', 'unknown')}",
            "risk_id": gap.get("risk_id", ""),
            "expected_test_ref": gap.get("expected_test_ref", ""),
            "priority": "high",
            "status": "requested",
            "source_refs": ["qeg-export-report.json", "manual-bb-bridge-requests.jsonl"],
        }
        for gap in missing_execution
    ]
