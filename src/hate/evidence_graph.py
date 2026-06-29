from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from .evidence_envelope import source_refs


NODE_KINDS = {
    "requirement",
    "risk",
    "test",
    "execution",
    "coverage",
    "finding",
    "artifact",
    "manual_review",
    "release_claim",
    "contract",
    "mutation",
}

EDGE_KINDS = {
    "requires_test",
    "executed_by",
    "covered_by",
    "supported_by",
    "contradicted_by",
    "blocked_by",
    "reviewed_by",
    "derived_from",
}


@dataclass(frozen=True)
class GraphFinding:
    code: str
    severity: str
    message: str
    sourceRefs: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRefs": self.sourceRefs,
        }


def build_evidence_graph(bundle: dict[str, Any]) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    findings: list[GraphFinding] = []

    def node(node_id: str, kind: str, label: str, data: dict[str, Any] | None = None, refs: list[str] | None = None) -> None:
        if kind not in NODE_KINDS:
            findings.append(GraphFinding("unknown_node_kind", "hard", f"unknown node kind: {kind}", refs or []))
            return
        nodes[node_id] = {
            "id": node_id,
            "kind": kind,
            "label": label,
            "data": data or {},
            "sourceRefs": sorted(set(refs or [])),
        }

    def edge(from_id: str, to_id: str, kind: str, refs: list[str] | None = None) -> None:
        if kind not in EDGE_KINDS:
            findings.append(GraphFinding("unknown_edge_kind", "hard", f"unknown edge kind: {kind}", refs or []))
            return
        if from_id not in nodes or to_id not in nodes:
            findings.append(GraphFinding("missing_graph_node", "hard", f"edge references missing node: {from_id}->{to_id}", refs or []))
            return
        edges.append({"from": from_id, "to": to_id, "kind": kind, "sourceRefs": sorted(set(refs or []))})

    for requirement in bundle.get("requirements", []):
        if isinstance(requirement, dict):
            req_id = str(requirement.get("id") or "")
            node(f"requirement:{req_id}", "requirement", req_id, requirement, _refs(requirement))
    for risk in bundle.get("risks", []):
        if isinstance(risk, dict):
            risk_id = str(risk.get("id") or "")
            node(f"risk:{risk_id}", "risk", risk_id, risk, _refs(risk))
    for claim in bundle.get("claims", []):
        if not isinstance(claim, dict):
            continue
        claim_id = str(claim.get("id") or "")
        refs = _refs(claim)
        node(f"release_claim:{claim_id}", "release_claim", claim_id, claim, refs)
        if not claim.get("requirement_refs"):
            findings.append(GraphFinding("missing_requirement_ref", "hard", f"claim has no requirement_refs: {claim_id}", refs))
        for req_id in claim.get("requirement_refs", []):
            if f"requirement:{req_id}" in nodes:
                edge(f"release_claim:{claim_id}", f"requirement:{req_id}", "derived_from", refs)
        for risk_id in claim.get("risk_refs", []):
            if f"risk:{risk_id}" in nodes:
                edge(f"release_claim:{claim_id}", f"risk:{risk_id}", "derived_from", refs)

    for record in [item for item in bundle.get("records", []) if isinstance(item, dict)]:
        _add_record(record, nodes, node, edge, findings)
    for review in [item for item in bundle.get("manual_reviews", []) if isinstance(item, dict)]:
        _add_manual_review(review, nodes, node, edge)

    for item in bundle.get("edges", []):
        if isinstance(item, dict):
            edge(str(item.get("from", "")), str(item.get("to", "")), str(item.get("kind", "")), _refs(item))

    _flag_orphans(nodes, edges, findings)
    if _has_cycle([item for item in edges if item["kind"] == "requires_test"]):
        findings.append(GraphFinding("cycle_in_requires", "hard", "requires_test edge cycle detected", ["graph://edges/requires_test"]))

    return {
        "schema_version": "HATE/evidence-graph/v1",
        "record_type": "evidence_graph",
        "nodes": sorted(nodes.values(), key=lambda item: item["id"]),
        "edges": sorted(edges, key=lambda item: (item["kind"], item["from"], item["to"])),
        "findings": [finding.as_dict() for finding in sorted(findings, key=lambda item: (item.code, item.message))],
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "hard_finding_count": sum(1 for finding in findings if finding.severity == "hard"),
        },
    }


def _add_record(record: dict[str, Any], nodes: dict[str, dict[str, Any]], node, edge, findings: list[GraphFinding]) -> None:
    kind = str(record.get("record_kind") or record.get("record_type") or "")
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    refs = source_refs(record)
    record_id = str(record.get("record_id") or _record_id(kind, payload, refs))
    if kind == "test_result":
        test_id = str(payload.get("canonical_test_id") or record_id)
        node(f"test:{test_id}", "test", test_id, payload, refs)
        node(f"execution:{record_id}", "execution", record_id, record, refs)
        edge(f"test:{test_id}", f"execution:{record_id}", "executed_by", refs)
        for req_id in payload.get("requirement_refs", []):
            if f"requirement:{req_id}" in nodes:
                edge(f"requirement:{req_id}", f"test:{test_id}", "requires_test", refs)
                edge(f"requirement:{req_id}", f"execution:{record_id}", "supported_by", refs)
    elif kind == "coverage_slice":
        node(f"coverage:{record_id}", "coverage", record_id, record, refs)
        for req_id in payload.get("requirement_refs", []):
            if f"requirement:{req_id}" in nodes:
                edge(f"requirement:{req_id}", f"coverage:{record_id}", "covered_by", refs)
    elif kind == "static_finding":
        node(f"finding:{record_id}", "finding", record_id, record, refs)
        for risk_id in payload.get("risk_refs", []):
            if f"risk:{risk_id}" in nodes:
                edge(f"risk:{risk_id}", f"finding:{record_id}", "blocked_by", refs)
        if payload.get("severity") in {"error", "critical"}:
            for claim_id in payload.get("claim_refs", []):
                if f"release_claim:{claim_id}" in nodes:
                    edge(f"release_claim:{claim_id}", f"finding:{record_id}", "contradicted_by", refs)
    elif kind == "contract_evidence":
        node(f"contract:{record_id}", "contract", record_id, record, refs)
        relation = "supported_by" if payload.get("status") == "passed" else "contradicted_by"
        for req_id in payload.get("requirement_refs", []):
            if f"requirement:{req_id}" in nodes:
                edge(f"requirement:{req_id}", f"contract:{record_id}", relation, refs)
    elif kind == "mutation_evidence":
        node(f"mutation:{record_id}", "mutation", record_id, record, refs)
        relation = "supported_by" if payload.get("status") == "killed" else "contradicted_by"
        for req_id in payload.get("requirement_refs", []):
            if f"requirement:{req_id}" in nodes:
                edge(f"requirement:{req_id}", f"mutation:{record_id}", relation, refs)


def _add_manual_review(review: dict[str, Any], nodes: dict[str, dict[str, Any]], node, edge) -> None:
    review_id = str(review.get("id") or "manual-review")
    refs = _refs(review)
    node(f"manual_review:{review_id}", "manual_review", review_id, review, refs)
    relation = "reviewed_by" if review.get("status") == "approved" else "blocked_by"
    for req_id in review.get("requirement_refs", []):
        if f"requirement:{req_id}" in nodes:
            edge(f"requirement:{req_id}", f"manual_review:{review_id}", relation, refs)


def _flag_orphans(nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]], findings: list[GraphFinding]) -> None:
    connected = {edge["from"] for edge in edges}.union(edge["to"] for edge in edges)
    for item in nodes.values():
        if item["kind"] in {"execution", "coverage", "finding", "contract", "mutation", "manual_review"} and item["id"] not in connected:
            findings.append(GraphFinding("orphan_evidence", "hard", f"evidence node has no graph edge: {item['id']}", item["sourceRefs"]))


def _has_cycle(edges: list[dict[str, Any]]) -> bool:
    graph: dict[str, list[str]] = {}
    for edge in edges:
        graph.setdefault(edge["from"], []).append(edge["to"])
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in visited:
            return False
        visiting.add(node_id)
        for child in graph.get(node_id, []):
            if visit(child):
                return True
        visiting.remove(node_id)
        visited.add(node_id)
        return False

    return any(visit(node_id) for node_id in graph)


def _refs(item: dict[str, Any]) -> list[str]:
    refs = item.get("sourceRefs", item.get("source_refs", []))
    if isinstance(refs, str):
        return [refs]
    if isinstance(refs, list):
        return [str(ref) for ref in refs if str(ref)]
    return []


def _record_id(kind: str, payload: dict[str, Any], refs: list[str]) -> str:
    digest = hashlib.sha256(f"{kind}|{payload}|{sorted(refs)}".encode("utf-8")).hexdigest()[:12]
    return f"{kind}-{digest}"
