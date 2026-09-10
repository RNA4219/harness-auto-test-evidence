"""P1aの入力構造、参照整合性、実際のlineageに基づく評価の回帰テスト。"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hate import cli
from hate.p1a import TrustError, doctor_trust, evaluate_trust, explain_trust, recommend_trust, replay_trust
from hate.schema_resources import read_schema, validate_schema_instance

FIXTURE = Path("fixtures/golden/p0b-qeg-minimal/expected")
OPERATIONS = {
    "trust": evaluate_trust, "replay": replay_trust, "doctor": doctor_trust,
    "explain": explain_trust, "recommend": recommend_trust,
}


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _set(value, path: tuple, replacement) -> None:
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = replacement


@pytest.mark.parametrize("command", OPERATIONS)
@pytest.mark.parametrize(("target", "field_path", "value"), [
    ("bundle", ("nodes",), None), ("bundle", ("nodes",), {}),
    ("bundle", ("nodes", 0), "node"), ("bundle", ("nodes", 0, "data"), []),
    ("bundle", ("nodes", 0, "kind"), []), ("bundle", ("nodes", 0, "id"), {}),
    ("bundle", ("nodes", 0, "sourceRefs"), "reference"),
    ("bundle", ("nodes", 0, "sourceRefs"), [42]),
    ("bundle", ("edges",), "edge"), ("bundle", ("edges", 0), None),
    ("bundle", ("edges", 0, "from"), []), ("bundle", ("edges", 0, "traceability"), None),
    ("bundle", ("edges", 0, "traceability", "sourceRefs"), "reference"),
    ("bundle", ("metadata", "inputArtifacts"), {}),
    ("bundle", ("metadata", "inputArtifacts", 0), "artifact"),
    ("bundle", ("completeness",), []),
    ("bundle", ("completeness", "unsupportedClaims"), None),
    ("report", ("unsupportedClaims",), [None]),
    ("report", ("excludedArtifacts",), {"reason": "unsafe"}),
    ("report", ("missing_execution",), ["gap"]),
    ("report", ("missing_execution",), [{"risk_id": []}]),
    ("report", ("excludedArtifacts",), [{"reason": {}}]),
])
def test_malformed_structures_are_rejected_before_any_output(
    command: str, target: str, field_path: tuple, value, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    bundle, report = _read(FIXTURE / "qeg-bundle.json"), _read(FIXTURE / "qeg-export-report.json")
    _set(bundle if target == "bundle" else report, field_path, value)
    bundle_path, report_path = tmp_path / "bundle.json", tmp_path / "report.json"
    _write(bundle_path, bundle)
    _write(report_path, report)
    out = tmp_path / "out"
    out.mkdir()
    sentinel = out / "aete-score.json"
    sentinel.write_bytes(b"previous verified score")
    before = sentinel.read_bytes(), sentinel.stat().st_mtime_ns
    with pytest.raises(TrustError) as caught:
        OPERATIONS[command](bundle_path, report_path, out)
    assert caught.value.exit_code == 1
    assert str(field_path[0]) in str(caught.value)
    assert f"{target}.json" in str(caught.value)
    args = ["trust", "evaluate"] if command == "trust" else [command]
    assert cli.main([*args, "--bundle", str(bundle_path), "--report", str(report_path), "--out", str(out)]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "HATE-E-" in captured.err
    assert list(out.iterdir()) == [sentinel]
    assert (sentinel.read_bytes(), sentinel.stat().st_mtime_ns) == before


def _run(bundle: dict, tmp_path: Path, operation=evaluate_trust):
    path, out = tmp_path / "bundle.json", tmp_path / "out"
    _write(path, bundle)
    result = operation(path, FIXTURE / "qeg-export-report.json", out)
    doctor = _read(out / "doctor-report.json")
    assert not validate_schema_instance(doctor, read_schema("doctor-report.schema.json"))
    assert _read(path) == bundle
    return result, doctor, out


@pytest.mark.parametrize("operation", [evaluate_trust, doctor_trust, replay_trust])
@pytest.mark.parametrize("case", ["missing-label", "invalid-confidence", "wrong-version"])
def test_processable_schema_errors_become_blocking_doctor_findings(case: str, operation, tmp_path: Path) -> None:
    bundle = _read(FIXTURE / "qeg-bundle.json")
    if case == "missing-label":
        bundle["nodes"][0].pop("label")
    elif case == "invalid-confidence":
        bundle["edges"][0]["traceability"]["confidence"] = "very-high"
    else:
        bundle["metadata"]["qegVersion"] = "HATE/future"
    result, doctor, _ = _run(bundle, tmp_path, operation)
    findings = [finding for finding in doctor["findings"] if finding["category"] == "schema"]
    assert findings and all(finding["blocking"] for finding in findings)
    assert all(finding["finding_code"] == "HATE-DOC-SCH-001" for finding in findings)
    assert "schema" in doctor["summary"]["blocking_categories"]
    assert result["doctor_status" if operation is doctor_trust else "trust_status"] == "partial"


@pytest.mark.parametrize("case", ["duplicate", "dangling", "wrong-kind", "foreign-export", "foreign-export-node"])
def test_invalid_graph_is_diagnosed_and_cannot_receive_full_lineage(case: str, tmp_path: Path) -> None:
    bundle = _read(FIXTURE / "qeg-bundle.json")
    if case == "duplicate":
        bundle["nodes"].append(copy.deepcopy(bundle["nodes"][0]))
        expected = "duplicate_node_id"
    elif case in {"foreign-export", "foreign-export-node"}:
        edge = next(edge for edge in bundle["edges"] if edge["kind"] == "decides")
        edge["to"] = "qeg_export:another-run"
        expected = "unresolved_edge_endpoint"
        if case == "foreign-export-node":
            bundle["nodes"].append({"id": edge["to"], "kind": "qeg_export", "label": "other run", "data": {},
                                    "sourceRefs": ["other-run.json"]})
            expected = "edge_kind_mismatch"
    else:
        edge = next(edge for edge in bundle["edges"] if edge["kind"] == "requires_test")
        if case == "dangling":
            edge["to"] = "test:missing"
            expected = "unresolved_edge_endpoint"
        else:
            edge["to"] = next(node["id"] for node in bundle["nodes"] if node["kind"] == "coverage")
            expected = "edge_kind_mismatch"
    result, doctor, out = _run(bundle, tmp_path)
    assert result["trust_status"] == "partial"
    assert any(finding.get("issue") == expected and finding["blocking"] for finding in doctor["findings"])
    score = _read(out / "aete-score.json")
    assert score["dimensions"]["traceability_lineage"] <= 1
    trace = next(signal for signal in score["dimension_signals"] if signal["dimension"] == "traceability_lineage")
    assert trace["observed"]["graph_integrity_ok"] is False


@pytest.mark.parametrize("refs", [[], [""], ["   "]])
def test_absent_or_blank_source_refs_never_count_as_complete_evidence(refs: list[str], tmp_path: Path) -> None:
    bundle = _read(FIXTURE / "qeg-bundle.json")
    for node in bundle["nodes"]:
        node["sourceRefs"] = refs
    for edge in bundle["edges"]:
        edge["traceability"]["sourceRefs"] = refs
    result, doctor, out = _run(bundle, tmp_path)
    assert result["trust_status"] == "partial" and doctor["findings"]
    assert _read(out / "aete-score.json")["dimensions"]["traceability_lineage"] == 0


@pytest.mark.parametrize(("case", "expected"), [
    ("no-risk-test-link", 1), ("no-execution-link", 3), ("unrelated-execution", 3),
    ("partially-executed", 3), ("placement-without-execution", 3),
])
def test_lineage_requires_a_connected_risk_test_execution_path(case: str, expected: int, tmp_path: Path) -> None:
    bundle = _read(FIXTURE / "qeg-bundle.json")
    if case == "no-risk-test-link":
        bundle["edges"] = [edge for edge in bundle["edges"] if edge["kind"] != "requires_test"]
    elif case == "no-execution-link":
        bundle["edges"] = [edge for edge in bundle["edges"] if edge["kind"] != "evidenced_by"]
    elif case in {"partially-executed", "placement-without-execution"}:
        target = next(edge["to"] for edge in bundle["edges"] if edge["kind"] == "requires_test")
        bundle["edges"] = [edge for edge in bundle["edges"] if not (
            edge["kind"] == "evidenced_by" and edge["from"] == target
        )]
        if case == "placement-without-execution":
            next(node for node in bundle["nodes"] if node["id"] == target)["kind"] = "test_placement"
    else:
        node = copy.deepcopy(next(node for node in bundle["nodes"] if node["kind"] == "test"))
        node["id"] = "test:unexecuted"
        node["data"]["canonical_test_id"] = "pytest:tests/new.py::test_unexecuted"
        bundle["nodes"].append(node)
        for edge in bundle["edges"]:
            if edge["kind"] == "requires_test":
                edge["to"] = node["id"]
    _, _, out = _run(bundle, tmp_path)
    score = _read(out / "aete-score.json")
    assert score["dimensions"]["traceability_lineage"] == expected


def test_empty_graph_has_no_source_evidence(tmp_path: Path) -> None:
    bundle = _read(FIXTURE / "qeg-bundle.json")
    bundle.update(nodes=[], edges=[])
    result, doctor, out = _run(bundle, tmp_path)
    assert result["trust_status"] == "partial" and doctor["findings"]
    assert _read(out / "aete-score.json")["dimensions"]["traceability_lineage"] == 0


def test_change_relevance_requires_a_real_changed_code_to_risk_link(tmp_path: Path) -> None:
    bundle = _read(FIXTURE / "qeg-bundle.json")
    bundle["edges"] = [edge for edge in bundle["edges"] if edge["kind"] != "touches"]
    _, _, out = _run(bundle, tmp_path)
    score = _read(out / "aete-score.json")
    assert score["dimensions"]["change_relevance"] == 1
    assert score["dimensions"]["traceability_lineage"] == 5


def test_valid_qeg_export_reference_and_extension_edges_remain_supported(tmp_path: Path) -> None:
    bundle = _read(FIXTURE / "qeg-bundle.json")
    bundle["edges"].append({
        "kind": "extension_relation", "from": bundle["nodes"][0]["id"], "to": bundle["nodes"][1]["id"],
        "traceability": {"sourceRefs": ["extension.json"], "confidence": "high", "assumptions": []},
    })
    result, doctor, out = _run(bundle, tmp_path)
    assert result["trust_status"] == "success" and doctor["findings"] == []
    assert _read(out / "aete-score.json")["dimensions"]["traceability_lineage"] == 5


@pytest.mark.parametrize("keep_execution", [True, False])
def test_p0b_attachment_edges_are_valid_but_do_not_replace_execution(keep_execution: bool, tmp_path: Path) -> None:
    bundle = _read(FIXTURE / "qeg-bundle.json")
    test_id = next(node["id"] for node in bundle["nodes"] if node["kind"] == "test")
    if not keep_execution:
        removed = {node["id"] for node in bundle["nodes"] if node["kind"] == "execution_evidence"}
        bundle["nodes"] = [node for node in bundle["nodes"] if node["id"] not in removed]
        bundle["edges"] = [edge for edge in bundle["edges"] if edge["from"] not in removed and edge["to"] not in removed]
    bundle["nodes"].append({
        "id": "artifact:trace", "kind": "evidence_artifact", "label": "trace",
        "data": {"path": "artifacts/trace.zip", "sha256": "a" * 64}, "sourceRefs": ["artifact-manifest.json"],
    })
    # P0bのPlaywright等の添付出力が生成する、正規のtest→artifact関係。
    bundle["edges"].append({
        "kind": "evidenced_by", "from": test_id, "to": "artifact:trace",
        "traceability": {"sourceRefs": ["artifact-manifest.json"], "confidence": "high", "assumptions": []},
    })
    result, doctor, out = _run(bundle, tmp_path)
    assert not any(item.get("issue") == "edge_kind_mismatch" for item in doctor["findings"])
    score = _read(out / "aete-score.json")
    assert score["dimensions"]["traceability_lineage"] == (5 if keep_execution else 3)
    assert result["trust_status"] == ("success" if keep_execution else "partial")
    if not keep_execution:
        assert score["dimensions"]["determinism_flakiness"] == 1
        aggregation = _read(out / "retry-aggregation.json")
        assert all(item["aggregate_status"] == "inconclusive" for item in aggregation["aggregates"])


def test_execution_to_execution_is_not_an_artifact_attachment(tmp_path: Path) -> None:
    bundle = _read(FIXTURE / "qeg-bundle.json")
    executions = [node["id"] for node in bundle["nodes"] if node["kind"] == "execution_evidence"]
    bundle["edges"].append({
        "kind": "evidenced_by", "from": executions[0], "to": executions[1],
        "traceability": {"sourceRefs": ["tests.json"], "confidence": "high", "assumptions": []},
    })
    result, doctor, out = _run(bundle, tmp_path)
    assert result["trust_status"] == "partial"
    assert any(item.get("issue") == "edge_kind_mismatch" for item in doctor["findings"])
    assert _read(out / "aete-score.json")["dimensions"]["traceability_lineage"] == 1
