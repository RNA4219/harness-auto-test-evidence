"""Core graph seed construction for P0b QEG export."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def append_gate_changed_and_risk_nodes(
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    unsupported_claims: list[dict[str, Any]],
    run_id: str,
    run_attempt: int,
    decision: str,
    precheck_decision: dict[str, Any],
    run_record: dict[str, Any],
    diff_risk_test: dict[str, Any],
    p0a_dir: Path,
    diff_risk_path: Path,
    source_ref: Callable[[Path], str],
) -> tuple[str, list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, list[str]], dict[str, dict[str, int]]]:
    precheck_node_id = f"hate_precheck:{run_id}:{run_attempt}"
    nodes.append({
        "id": precheck_node_id,
        "kind": "gate_verdict",
        "label": f"HATE P0a Precheck {run_id}",
        "data": {
            "decision": decision,
            "exit_code": precheck_decision.get("payload", {}).get("exit_code", 0),
            "qeg_export_allowed": precheck_decision.get("payload", {}).get("qeg_export_allowed", False),
            "qeg_export_phase": precheck_decision.get("payload", {}).get("qeg_export_phase", "P0b"),
        },
        "sourceRefs": [source_ref(p0a_dir / "precheck-decision.json")],
    })
    nodes.append({
        "id": f"run:{run_id}:{run_attempt}",
        "kind": "run",
        "label": f"CI Run {run_id}",
        "data": run_record.get("payload", {}),
        "sourceRefs": [source_ref(p0a_dir / "HATE-run.json")],
    })
    changed_entities = diff_risk_test.get("changed_entities", [])
    changed_entities_by_risk: dict[str, list[dict[str, Any]]] = {}
    for entity in changed_entities:
        if not isinstance(entity, dict):
            continue
        for risk_ref in entity.get("risk_refs", []):
            changed_entities_by_risk.setdefault(str(risk_ref), []).append(entity)
    changed_node_by_path: dict[str, list[str]] = {}
    changed_node_ranges: dict[str, dict[str, int]] = {}
    for entity in changed_entities:
        path = entity.get("path", "")
        for rng in entity.get("ranges", []):
            start = rng.get("start_line", 0)
            end = rng.get("end_line", 0)
            node_id = f"changed_code:{path}#L{start}-L{end}"
            nodes.append({
                "id": node_id,
                "kind": "changed_code",
                "label": f"Changed: {path} L{start}-L{end}",
                "data": {"path": path, "start_line": start, "end_line": end},
                "sourceRefs": [source_ref(diff_risk_path)],
            })
            changed_node_by_path.setdefault(path.replace("\\", "/"), []).append(node_id)
            changed_node_ranges[node_id] = {"start_line": int(start), "end_line": int(end)}
            for risk_ref in entity.get("risk_refs", []):
                edges.append({
                    "kind": "touches",
                    "from": node_id,
                    "to": f"risk:{risk_ref}",
                    "traceability": {
                        "sourceRefs": [source_ref(diff_risk_path)],
                        "confidence": "high",
                        "assumptions": [],
                    },
                })
    risks = diff_risk_test.get("risks", [])
    risk_by_id = {str(risk.get("risk_id", "")): risk for risk in risks if isinstance(risk, dict)}
    for risk in risks:
        risk_id = risk.get("risk_id", "")
        risk_source_refs = risk.get("source_refs", [])
        if not risk_source_refs:
            unsupported_claims.append({"risk_id": risk_id, "reason": "risk source_refs missing"})
        nodes.append({
            "id": f"risk:{risk_id}",
            "kind": "risk",
            "label": risk.get("title", f"Risk {risk_id}"),
            "data": {
                "severity": risk.get("severity", "medium"),
                "required_test_layers": risk.get("required_test_layers", []),
            },
            "sourceRefs": risk_source_refs,
        })
    return precheck_node_id, risks, risk_by_id, changed_entities_by_risk, changed_node_by_path, changed_node_ranges
