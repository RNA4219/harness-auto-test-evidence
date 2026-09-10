"""未実行のreportを成功や実行要件の充足へ変えず、元の状態を残す。"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from hate import cli, p1a
from hate.p0a import PrecheckError, generate_p0a
from hate.p0b import ExportError, export_qeg

SOURCE = Path("fixtures/golden/p0b-qeg-minimal/input")
EXPECTED = Path("fixtures/golden/p0b-qeg-minimal/expected")
OPERATIONS = {"trust": p1a.evaluate_trust, "replay": p1a.replay_trust, "doctor": p1a.doctor_trust,
              "explain": p1a.explain_trust, "recommend": p1a.recommend_trust}


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _snapshot(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _native_source(tmp_path, family, status, **extra):
    source = tmp_path / "input"
    shutil.copytree("fixtures/golden/p0a-minimal/input", source)
    if family == "pytest":
        report = {"tests": [{"nodeid": "tests/state.py::test", "outcome": status, "duration": 0.1, **extra}]}
        canonical = "pytest:tests/state.py::test"
    else:
        report = {"testResults": [{"name": "state.test.js", "assertionResults": [
            {"fullName": "state test", "title": "test", "status": status, "duration": 100, **extra},
        ]}]}
        canonical = f"{family}:state.test.js::state test"
    _write(source / f"{family}-report.json", report)
    return source, canonical


def _native_pipeline(tmp_path, family, status, **extra):
    source, canonical = _native_source(tmp_path, family, status, **extra)
    before = _snapshot(source)
    run = tmp_path / "run"
    assert generate_p0a(source, run / "p0a")["decision"] == "eligible"
    _write(run / "diff-risk-test.json", {
        "risks": [{"risk_id": "state-risk", "severity": "high", "title": "Required test", "source_refs": ["spec.md"]}],
        "test_obligations": [{"risk_id": "state-risk", "expected_test_refs": [canonical], "required_evidence_kinds": ["execution"]}],
    })
    export = export_qeg(run, run / "export")
    bundle = _read(run / "export/qeg-bundle.json")
    execution = next(node for node in bundle["nodes"] if node["kind"] == "execution_evidence" and node["label"].endswith(canonical))
    trust = p1a.evaluate_trust(run / "export/qeg-bundle.json", run / "export/qeg-export-report.json", run / "trust")
    assert _snapshot(source) == before
    return export, execution["data"], trust, _read(run / "trust/aete-score.json"), run


@pytest.mark.parametrize(("family", "reported", "canonical", "executed"), [
    ("pytest", "xfail", "skipped", False), ("pytest", "xfailed", "skipped", False),
    ("pytest", "xpass", "passed", True), ("pytest", "xpassed", "passed", True),
    ("pytest", "error", "error", True), ("pytest", "unknown-new-state", "inconclusive", False),
] + [(family, status, canonical, executed) for family in ("jest", "vitest")
     for status, canonical, executed in (("passed", "passed", True), ("failed", "failed", True),
                                        ("pending", "skipped", False), ("todo", "skipped", False),
                                        ("disabled", "skipped", False), ("focused", "inconclusive", False))])
def test_native_outcome_keeps_source_and_does_not_satisfy_unexecuted_test(family, reported, canonical, executed, tmp_path):
    export, data, trust, score, run = _native_pipeline(tmp_path, family, reported)
    assert data["status"] == canonical and data["source_status"] == reported
    assert export["missing_executions"] == int(not executed)
    if not executed:
        assert export["export_status"] == "partial" and trust["score_confidence"] == "medium"
        assert score["dimensions"]["traceability_lineage"] == 3
        assert (run / "export/risk-debt-register.json").exists()
        assert (run / "export/manual-bb-bridge-requests.jsonl").exists()
    if reported in {"xfail", "xfailed", "xpass", "xpassed"}:
        assert data["xfail"] is True
    if reported in {"xpass", "xpassed"}:
        assert data["xpass"] is True
    if reported == "todo":
        assert data["todo"] is True


@pytest.mark.parametrize("declared", [True, False])
def test_jest_collection_only_flag_overrides_pass_and_merges_duration_warning(declared, tmp_path):
    export, data, trust, score, run = _native_pipeline(tmp_path, "jest", "passed", wouldRun=declared, duration=None)
    assert data["wouldRun"] is declared and data["source_status"] == "passed"
    assert data["status"] == ("inconclusive" if declared else "passed")
    assert export["missing_executions"] == int(declared)
    codes = {item["code"] for item in data["parser_diagnostics"]}
    assert "duration_not_reported" in codes and ("test_not_executed" in codes) is declared
    if declared:
        assert trust["score_confidence"] == "medium" and score["dimensions"]["traceability_lineage"] == 3
        assert any(item["issue"] == "test_not_executed" for item in _read(run / "trust/retry-aggregation.json")["issues"])


@pytest.mark.parametrize("family", ["pytest", "jest", "vitest"])
@pytest.mark.parametrize(("field", "value"), [("state", None), ("state", False), ("state", []), ("state", ""),
                                               ("wouldRun", None), ("wouldRun", "false"), ("wouldRun", 1), ("wouldRun", [])])
def test_malformed_state_declarations_produce_hard_dq_with_valid_adapter(family, field, value, tmp_path, capsys):
    root, _ = _native_source(tmp_path, family, value if field == "state" else "passed", **({"wouldRun": value} if field != "state" else {}))
    original = _snapshot(root)
    out = tmp_path / "p0a"
    with pytest.raises(PrecheckError) as caught:
        generate_p0a(root, out)
    assert caught.value.exit_code == 2
    diagnostic = "wouldRun" if field != "state" else "outcome" if family == "pytest" else "status"
    decision = _read(out / "precheck-decision.json")["payload"]
    assert decision["qeg_export_allowed"] is False
    assert any(hit["code"] == "HATE-DQ-002" and diagnostic in hit["message"] for hit in decision["dq_hits"])
    assert cli.main(["p0a", "--input", str(root), "--out", str(out)]) == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err and _snapshot(root) == original


@pytest.mark.parametrize(("status", "would_run", "executed"), [
    ("skipped", False, False), ("inconclusive", False, False), ("unknown", False, False),
    ("passed", True, False), ("failed", True, False), ("passed", False, True),
    ("failed", False, True), ("error", False, True), ("flaky", False, True),
])
def test_p0b_record_presence_alone_does_not_establish_execution(status, would_run, executed, tmp_path):
    root = tmp_path / "input"
    shutil.copytree(SOURCE, root)
    path = root / "p0a/HATE-test-results.ndjson"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    records[-1]["payload"].update(status=status, wouldRun=would_run)
    path.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")
    before = _snapshot(root)
    result = export_qeg(root, tmp_path / "export")
    assert result["missing_executions"] == int(not executed)
    assert result["export_status"] == ("success" if executed else "partial")
    if not executed:
        gap = _read(tmp_path / "export/qeg-export-report.json")["missing_execution"][0]
        assert gap["reason"] == "test result does not establish execution" and gap["test_node_id"].startswith("test:")
    assert _snapshot(root) == before


def test_observed_run_satisfies_requirement_without_dropping_unexecuted_observation(tmp_path):
    root = tmp_path / "input"
    shutil.copytree(SOURCE, root)
    path = root / "p0a/HATE-test-results.ndjson"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    unexecuted = copy.deepcopy(records[-1])
    unexecuted["payload"].update(wouldRun=True)
    path.write_text("".join(json.dumps(item) + "\n" for item in [*records, unexecuted]), encoding="utf-8")
    out = tmp_path / "export"
    assert export_qeg(root, out)["missing_executions"] == 0
    nodes = [node for node in _read(out / "qeg-bundle.json")["nodes"] if node["kind"] == "execution_evidence"]
    assert len(nodes) == 3 and sum(node["data"].get("wouldRun") is True for node in nodes) == 1


@pytest.mark.parametrize(("field", "value"), [("wouldRun", None), ("wouldRun", "false"), ("wouldRun", 1),
                                               ("status", []), ("source_status", {})])
def test_p0b_state_type_errors_preserve_outputs(field, value, tmp_path, capsys):
    root, out = tmp_path / "input", tmp_path / "existing"
    shutil.copytree(SOURCE, root)
    export_qeg(root, out)
    path = root / "p0a/HATE-test-results.ndjson"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    records[-1]["payload"][field] = value
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    before, original = _snapshot(out), _snapshot(root)
    for destination in (out, tmp_path / "new"):
        with pytest.raises(ExportError) as caught:
            export_qeg(root, destination)
        assert caught.value.exit_code == 1
        assert field in str(caught.value) and "HATE-test-results.ndjson:2" in str(caught.value)
        assert cli.main(["export", "qeg", "--fixture", str(root), "--out", str(destination)]) == 1
        stderr = capsys.readouterr().err
        assert field in stderr and "Traceback" not in stderr
    assert _snapshot(out) == before and _snapshot(root) == original and not (tmp_path / "new").exists()


def test_unexecuted_obligation_is_explained_and_recommended(tmp_path):
    _, _, _, _, run = _native_pipeline(tmp_path, "jest", "passed", wouldRun=True)
    bp, rp = run / "export/qeg-bundle.json", run / "export/qeg-export-report.json"
    p1a.explain_trust(bp, rp, run / "explain")
    reasons = _read(run / "explain/explain-report.json")["reason_tree"]
    assert any(item["category"] == "missing_execution" and item["source_refs"]
               and item["summary"] == "test result does not establish execution" for item in reasons)
    p1a.recommend_trust(bp, rp, run / "recommend")
    recommendations = _read(run / "recommend/recommendation-report.json")["recommendations"]
    assert any(item["gap_id"] == "missing_execution" and item["recommended_manual_layer"] == "manual-scripted"
               and item["expected_test_ref"] == "jest:state.test.js::state test" for item in recommendations)


def test_existing_bundle_cannot_reclassify_collection_as_success(tmp_path):
    bundle = _read(EXPECTED / "qeg-bundle.json")
    for node in bundle["nodes"]:
        if node["kind"] == "execution_evidence":
            node["data"].update(status="passed", wouldRun=True)
    bp, rp = tmp_path / "bundle.json", EXPECTED / "qeg-export-report.json"
    _write(bp, bundle)
    before = bp.read_bytes()
    for operation in (p1a.evaluate_trust, p1a.replay_trust):
        out = tmp_path / operation.__name__
        result = operation(bp, rp, out)
        assert result["score_confidence"] == "medium"
        dimensions = _read(out / "aete-score.json")["dimensions"]
        assert dimensions["traceability_lineage"] == 3 and dimensions["oracle_strength"] == 1
        assert dimensions["cross_signal_corroboration"] < 3
        assert all(item["aggregate_status"] == "inconclusive" for item in _read(out / "retry-aggregation.json")["aggregates"])
        assert any(item["issue"] == "test_not_executed" for item in _read(out / "doctor-report.json")["findings"])
    assert bp.read_bytes() == before


@pytest.mark.parametrize("command", OPERATIONS)
@pytest.mark.parametrize(("field", "value"), [("wouldRun", None), ("wouldRun", "false"), ("wouldRun", 1),
                                               ("status", []), ("source_status", {})])
def test_p1a_state_type_errors_preserve_existing_outputs_at_all_entries(command, field, value, tmp_path, capsys):
    bundle = _read(EXPECTED / "qeg-bundle.json")
    next(node for node in bundle["nodes"] if node["kind"] == "execution_evidence")["data"][field] = value
    bp, rp = tmp_path / "bundle.json", EXPECTED / "qeg-export-report.json"
    _write(bp, bundle)
    out = tmp_path / "existing"
    out.mkdir()
    (out / "aete-score.json").write_bytes(b"previous score")
    before, original = _snapshot(out), bp.read_bytes()
    for destination in (out, tmp_path / "new"):
        with pytest.raises(p1a.TrustError) as caught:
            OPERATIONS[command](bp, rp, destination)
        assert caught.value.exit_code == 1 and field in str(caught.value)
        args = ["trust", "evaluate"] if command == "trust" else [command]
        assert cli.main([*args, "--bundle", str(bp), "--report", str(rp), "--out", str(destination)]) == 1
        stderr = capsys.readouterr().err
        assert field in stderr and "Traceback" not in stderr
    assert _snapshot(out) == before and bp.read_bytes() == original and not (tmp_path / "new").exists()
