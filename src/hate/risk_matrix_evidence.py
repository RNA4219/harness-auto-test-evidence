"""Evidence matching policy for risk coverage matrix evaluation."""

from __future__ import annotations

from typing import Any


def classify_evidence_for_risk(
    risk_id: str,
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    requirement_refs: list[str],
) -> dict[str, Any]:
    risk_node_id = f"risk:{risk_id}"
    connected_evidence = []
    has_static_blocker = False

    for edge in edges:
        if edge.get("kind") == "blocked_by" and edge.get("from") == risk_node_id:
            to_id = edge.get("to", "")
            to_node = nodes.get(to_id)
            if to_node:
                kind = to_node.get("kind", "")
                if kind == "finding":
                    has_static_blocker = True
                elif kind in {"contract", "mutation", "manual_review", "execution"}:
                    connected_evidence.append(to_node)

    if requirement_refs:
        _append_requirement_scoped_evidence(
            requirement_refs=requirement_refs,
            nodes=nodes,
            edges=edges,
            connected_evidence=connected_evidence,
        )
    else:
        _append_legacy_requirement_evidence(
            nodes=nodes,
            edges=edges,
            connected_evidence=connected_evidence,
        )

    unique_evidence = _dedupe_evidence_nodes(connected_evidence)
    if not unique_evidence and not has_static_blocker:
        return {"primary_class": None, "evidence_nodes": [], "has_oracle": False, "all_classes": [], "has_static_blocker": False}

    evidence_classes_found: set[str] = set()
    has_oracle = False

    for node in unique_evidence:
        node_class, node_has_oracle = _classify_evidence_node(node)
        if node_class:
            evidence_classes_found.add(node_class)
        has_oracle = has_oracle or node_has_oracle

    return {
        "primary_class": _select_primary_evidence_class(evidence_classes_found),
        "evidence_nodes": [node["id"] for node in unique_evidence],
        "has_oracle": has_oracle,
        "all_classes": sorted(evidence_classes_found),
        "has_static_blocker": has_static_blocker,
    }


def _append_requirement_scoped_evidence(
    *,
    requirement_refs: list[str],
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    connected_evidence: list[dict[str, Any]],
) -> None:
    valid_requirement_ids = {f"requirement:{req_id}" for req_id in requirement_refs}

    for edge in edges:
        if edge.get("kind") in {"supported_by", "reviewed_by"}:
            from_id = edge.get("from", "")
            if from_id in valid_requirement_ids:
                to_id = edge.get("to", "")
                to_node = nodes.get(to_id)
                if to_node and to_node.get("kind") != "finding":
                    connected_evidence.append(to_node)

    for req_id in requirement_refs:
        _append_requirement_execution_chain(
            req_node_id=f"requirement:{req_id}",
            nodes=nodes,
            edges=edges,
            connected_evidence=connected_evidence,
        )


def _append_legacy_requirement_evidence(
    *,
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    connected_evidence: list[dict[str, Any]],
) -> None:
    for edge in edges:
        if edge.get("kind") in {"supported_by", "reviewed_by"}:
            from_id = edge.get("from", "")
            if from_id.startswith("requirement:"):
                _append_requirement_execution_chain(
                    req_node_id=from_id,
                    nodes=nodes,
                    edges=edges,
                    connected_evidence=connected_evidence,
                )


def _append_requirement_execution_chain(
    *,
    req_node_id: str,
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    connected_evidence: list[dict[str, Any]],
) -> None:
    req_edges = [edge for edge in edges if edge.get("from") == req_node_id and edge.get("kind") == "requires_test"]
    for req_edge in req_edges:
        test_id = req_edge.get("to", "")
        test_node = nodes.get(test_id)
        if test_node:
            exec_edges = [edge for edge in edges if edge.get("from") == test_id and edge.get("kind") == "executed_by"]
            for exec_edge in exec_edges:
                exec_id = exec_edge.get("to", "")
                exec_node = nodes.get(exec_id)
                if exec_node:
                    connected_evidence.append(exec_node)


def _dedupe_evidence_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_ids = set()
    unique_evidence = []
    for node in nodes:
        node_id = node.get("id", "")
        if node_id not in seen_ids:
            seen_ids.add(node_id)
            unique_evidence.append(node)
    return unique_evidence


def _classify_evidence_node(node: dict[str, Any]) -> tuple[str | None, bool]:
    kind = node.get("kind", "")
    data = node.get("data", {})

    if kind == "execution":
        payload = data.get("payload", {})
        status = payload.get("status", "")
        has_assertions = payload.get("has_assertions", True)
        if status in {"passed", "failed"} and has_assertions:
            return "executable_oracle", True
        return "coverage_only", False

    if kind == "contract":
        status = data.get("payload", {}).get("status", "")
        return "contract_check", status == "passed"

    if kind == "mutation":
        status = data.get("payload", {}).get("status", "")
        return "mutation_score", status == "killed"

    if kind == "coverage":
        return "coverage_only", False

    if kind == "manual_review":
        status = data.get("status", "") or data.get("data", {}).get("status", "")
        if status == "approved":
            return "manual_review", True

    return None, False


def _select_primary_evidence_class(classes: set[str]) -> str | None:
    priority = ["executable_oracle", "contract_check", "mutation_score", "static_finding", "manual_review", "coverage_only"]
    for cls in priority:
        if cls in classes:
            return cls
    return None
