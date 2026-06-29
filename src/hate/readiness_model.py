from __future__ import annotations

from typing import Any


def build_product_readiness_from_graph(graph: dict[str, Any], *, fixture_id: str = "graph-model") -> dict[str, Any]:
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    edges = graph.get("edges", [])
    claim_nodes = [node for node in nodes.values() if node.get("kind") == "release_claim"]
    supported = _claim_ids_with_support(edges)
    contradicted = [edge for edge in edges if edge.get("kind") in {"contradicted_by", "blocked_by"}]
    unsupported_claims = []
    hard_dqs = list(graph.get("findings", []))

    for claim in claim_nodes:
        claim_id = str(claim["id"]).removeprefix("release_claim:")
        is_supported = claim["id"] in supported
        if not is_supported:
            unsupported_claims.append(
                {
                    "claim_id": claim_id,
                    "reason": "claim has no supported graph path",
                    "sourceRefs": claim.get("sourceRefs", []),
                }
            )
            if claim.get("data", {}).get("ready") is True:
                hard_dqs.append(
                    {
                        "code": "unsupported_claim_marked_ready",
                        "severity": "hard",
                        "message": f"unsupported claim marked ready: {claim_id}",
                        "sourceRefs": claim.get("sourceRefs", []),
                    }
                )

    overall_status = "block" if hard_dqs or unsupported_claims or contradicted else "go"
    return {
        "schema_version": "HATE/v1",
        "record_type": "product_readiness_report",
        "fixture_id": fixture_id,
        "summary": {
            "overall_status": overall_status,
            "claim_count": len(claim_nodes),
            "unsupported_claim_count": len(unsupported_claims),
            "contradiction_count": len(contradicted),
            "hard_dq_count": len(hard_dqs),
        },
        "graph_summary": graph.get("summary", {}),
        "unsupported_claims": unsupported_claims,
        "contradictions": contradicted,
        "hard_dqs": hard_dqs,
        "soft_gaps": [],
        "sourceRefs": sorted({ref for node in claim_nodes for ref in node.get("sourceRefs", [])}),
    }


def _claim_ids_with_support(edges: list[dict[str, Any]]) -> set[str]:
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
