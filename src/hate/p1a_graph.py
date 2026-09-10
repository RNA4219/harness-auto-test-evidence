"""QEGの参照整合性と、実在するnodeを結ぶlineageの検証。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .execution_status import has_execution_result

_RELATION_KINDS = {
    "touches": {("changed_code", "risk")},
    "requires_test": {("risk", "test"), ("risk", "test_placement")},
    "evidenced_by": {
        ("test", "execution_evidence"), ("test", "evidence_artifact"),
        ("execution_evidence", "evidence_artifact"),
    },
}


@dataclass(frozen=True)
class GraphAnalysis:
    issues: list[dict[str, Any]]
    has_risk_test_links: bool
    all_risk_tests_executed: bool
    has_changed_risk_links: bool
    unexecuted_risk_tests: list[str]

    @property
    def valid(self) -> bool:
        return not self.issues


def valid_source_refs(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(ref, str) and bool(ref.strip()) for ref in value)


def has_any_source_refs(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> bool:
    refs = [node.get("sourceRefs", []) for node in nodes]
    refs.extend(edge.get("traceability", {}).get("sourceRefs", []) for edge in edges)
    return any(isinstance(items, list) and any(isinstance(ref, str) and ref.strip() for ref in items) for items in refs)


def analyze_graph(bundle: dict[str, Any], run_id: str) -> GraphAnalysis:
    nodes = bundle.get("nodes", [])
    counts = Counter(node.get("id", "") for node in nodes)
    issues: list[dict[str, Any]] = []
    for node_id, count in sorted(counts.items()):
        if not node_id.strip():
            issues.append({"issue": "missing_node_id", "node_id": node_id, "message": "node has no usable ID"})
        elif count > 1:
            issues.append({"issue": "duplicate_node_id", "node_id": node_id, "count": count,
                           "message": f"node ID is ambiguous: {node_id}"})
    kinds = {node["id"]: node.get("kind", "") for node in nodes
             if node.get("id", "").strip() and counts[node["id"]] == 1}
    risk_tests: set[str] = set()
    placements: set[str] = set()
    executed_tests: set[str] = set()
    execution_ids = {node["id"] for node in nodes if node.get("id", "").strip() and node.get("kind") == "execution_evidence"
                     and has_execution_result(node.get("data", {})) and counts[node["id"]] == 1}
    changed_risk_links = False
    for index, edge in enumerate(bundle.get("edges", [])):
        kind, source, target = edge.get("kind", ""), edge.get("from", ""), edge.get("to", "")
        external_export = (
            kind == "decides" and kinds.get(source) == "gate_verdict"
            and bool(run_id) and target == f"qeg_export:{run_id}"
        )
        missing = [field for field, node_id in [("from", source), ("to", target)]
                   if node_id not in kinds and not (field == "to" and external_export)]
        if missing:
            issues.append({"issue": "unresolved_edge_endpoint", "edge_index": index, "fields": missing,
                           "from": source, "to": target,
                           "message": f"edge {index} has missing or ambiguous endpoints: {', '.join(missing)}"})
            continue
        expected = _RELATION_KINDS.get(kind)
        wrong_kinds = expected and (kinds.get(source), kinds.get(target)) not in expected
        if wrong_kinds or (kind == "decides" and not external_export):
            issues.append({"issue": "edge_kind_mismatch", "edge_index": index, "kind": kind,
                           "from": source, "to": target,
                           "message": f"edge {index} ({kind}) connects incompatible node kinds"})
            continue
        if not valid_source_refs(edge.get("traceability", {}).get("sourceRefs")):
            continue
        if kind == "requires_test" and kinds.get(target) == "test":
            risk_tests.add(target)
        elif kind == "requires_test" and kinds.get(target) == "test_placement":
            placements.add(target)
        elif kind == "evidenced_by" and target in execution_ids:
            executed_tests.add(source)
        elif kind == "touches":
            changed_risk_links = True
    unexecuted = sorted((risk_tests - executed_tests) | placements)
    return GraphAnalysis(issues, bool(risk_tests), bool(risk_tests) and not unexecuted, changed_risk_links, unexecuted)
