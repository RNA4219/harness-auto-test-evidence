from __future__ import annotations

import json
from pathlib import Path

from hate.evidence_graph import build_evidence_graph


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "graph" / "model"


def load_bundle(name: str) -> dict:
    with (FIXTURES / name / "bundle.json").open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    assert isinstance(data, dict)
    return data


def codes(graph: dict) -> set[str]:
    return {finding["code"] for finding in graph["findings"]}


def edge_kinds(graph: dict) -> set[str]:
    return {edge["kind"] for edge in graph["edges"]}


def test_requirement_test_coverage_graph_edges_are_built() -> None:
    graph = build_evidence_graph(load_bundle("requirement-test-coverage"))

    assert graph["summary"]["hard_finding_count"] == 0
    assert {"requires_test", "executed_by", "covered_by", "supported_by", "derived_from"} <= edge_kinds(graph)
    assert [node["id"] for node in graph["nodes"]] == sorted(node["id"] for node in graph["nodes"])


def test_static_finding_blocks_risk_and_contradicts_claim() -> None:
    graph = build_evidence_graph(load_bundle("risk-static-finding"))

    assert "blocked_by" in edge_kinds(graph)
    assert "contradicted_by" in edge_kinds(graph)


def test_contract_and_mutation_evidence_support_requirement() -> None:
    graph = build_evidence_graph(load_bundle("contract-mutation-evidence"))

    supported_edges = [edge for edge in graph["edges"] if edge["kind"] == "supported_by"]
    assert {edge["to"] for edge in supported_edges} == {"contract:contract-billing", "mutation:mutation-billing"}


def test_orphan_evidence_is_hard_finding() -> None:
    assert codes(build_evidence_graph(load_bundle("orphan-evidence"))) == {"orphan_evidence"}


def test_cycle_in_requires_is_hard_finding() -> None:
    assert "cycle_in_requires" in codes(build_evidence_graph(load_bundle("cycle-in-requires")))


def test_unknown_edge_kind_is_hard_finding() -> None:
    assert codes(build_evidence_graph(load_bundle("unknown-edge-kind"))) == {"unknown_edge_kind"}
