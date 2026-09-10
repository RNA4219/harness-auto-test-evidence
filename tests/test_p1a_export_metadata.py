"""用途制限・export結果・現在のschema検証を信頼度と説明から落とさない。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hate import cli, p1a

SOURCE = Path("fixtures/golden/p0b-qeg-minimal/expected")
OPERATIONS = {"trust": p1a.evaluate_trust, "replay": p1a.replay_trust, "doctor": p1a.doctor_trust,
              "explain": p1a.explain_trust, "recommend": p1a.recommend_trust}


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _inputs(tmp_path):
    return (_read(SOURCE / "qeg-bundle.json"), _read(SOURCE / "qeg-export-report.json"),
            tmp_path / "qeg-bundle.json", tmp_path / "qeg-export-report.json")


def _evaluate(bundle, report, bp, rp, out):
    _write(bp, bundle)
    _write(rp, report)
    before = bp.read_bytes(), rp.read_bytes()
    result = p1a.evaluate_trust(bp, rp, out)
    assert (bp.read_bytes(), rp.read_bytes()) == before
    doctor = _read(out / "doctor-report.json")
    assert not doctor["release_gate_override"] and not doctor["publish_gate_override"]
    return result, doctor


@pytest.mark.parametrize("debug", [True, False])
@pytest.mark.parametrize("valid", [True, False, "missing"])
@pytest.mark.parametrize("errors", [[], ["original schema validation failed"]])
@pytest.mark.parametrize("status", ["success", "partial", "failed"])
def test_export_restrictions_cannot_be_cancelled_by_other_success_flags(debug, valid, errors, status, tmp_path):
    bundle, report, bp, rp = _inputs(tmp_path)
    bundle["metadata"]["debugOnly"] = debug
    report["export_status"] = status
    compatibility = report["qeg_schema_compatibility"]
    compatibility["errors"] = errors
    if valid == "missing":
        del compatibility["valid"]
    else:
        compatibility["valid"] = valid
    result, doctor = _evaluate(bundle, report, bp, rp, tmp_path / "trust")
    findings = [item for item in doctor["findings"] if item["category"] == "export"]
    high = debug or valid is not True or bool(errors) or status == "failed"
    partial = high or status == "partial"
    assert result["score_confidence"] == ("low" if high else "medium" if partial else "high")
    assert result["trust_status"] == ("partial" if partial else "success") and result["exit_code"] == 0
    assert len(findings) == int(debug) + int(valid is not True or bool(errors)) + int(status != "success")
    assert any(item["blocking"] for item in findings) == high
    assert all(item["finding_code"] == "HATE-DOC-EXP-001" and item["source_refs"] for item in findings)
    if debug:
        assert next(item for item in findings if item["issue"] == "diagnostic_only_bundle")["validation_path"] == ["metadata", "debugOnly"]
    if valid is not True or errors:
        finding = next(item for item in findings if item["issue"] == "export_schema_validation_failed")
        assert finding["reported_validation"] == compatibility
        assert (["qeg_schema_compatibility", "valid"] in finding["validation_paths"]) == (valid is not True)
        assert (["qeg_schema_compatibility", "errors"] in finding["validation_paths"]) == bool(errors)


@pytest.mark.parametrize("name", OPERATIONS)
@pytest.mark.parametrize(("where", "field", "value"), [
    ("metadata", "debugOnly", "false"), ("metadata", "debugOnly", 0), ("metadata", "debugOnly", None),
    ("report", "export_status", False), ("report", "export_status", None),
    ("report", "qeg_schema_compatibility", None), ("report", "qeg_schema_compatibility", []),
    ("compatibility", "valid", "false"), ("compatibility", "valid", 0),
    ("compatibility", "errors", "error"), ("compatibility", "errors", {}),
    ("compatibility", "schema", False),
])
def test_malformed_export_metadata_stops_all_entrypoints_before_output(name, where, field, value, tmp_path, capsys):
    bundle, report, bp, rp = _inputs(tmp_path)
    target = bundle["metadata"] if where == "metadata" else report if where == "report" else report["qeg_schema_compatibility"]
    target[field] = value
    _write(bp, bundle)
    _write(rp, report)
    out = tmp_path / "out"
    out.mkdir()
    saved = out / "existing.json"
    saved.write_bytes(b"preserved")
    before = bp.read_bytes(), rp.read_bytes()
    for destination in (out, tmp_path / "new"):
        with pytest.raises(p1a.TrustError) as caught:
            OPERATIONS[name](bp, rp, destination)
        assert caught.value.exit_code == 1 and field in str(caught.value)
        args = ["trust", "evaluate"] if name == "trust" else [name]
        assert cli.main([*args, "--bundle", str(bp), "--report", str(rp), "--out", str(destination)]) == 1
        stderr = capsys.readouterr().err
        assert field in stderr and "Traceback" not in stderr
    assert not (tmp_path / "new").exists()
    assert list(out.iterdir()) == [saved] and saved.read_bytes() == b"preserved"
    assert (bp.read_bytes(), rp.read_bytes()) == before


@pytest.mark.parametrize("blocking", [True, False])
def test_metadata_reaches_replay_doctor_explanation_and_recommendations(blocking, tmp_path):
    bundle, report, bp, rp = _inputs(tmp_path)
    if blocking:
        bundle["metadata"]["debugOnly"] = True
    else:
        report["export_status"] = "partial"
    _, doctor = _evaluate(bundle, report, bp, rp, tmp_path / "trust")
    expected = [item for item in doctor["findings"] if item["category"] == "export"]
    for name, operation in (("replay", p1a.replay_trust), ("doctor", p1a.doctor_trust)):
        operation(bp, rp, tmp_path / name)
        assert [item for item in _read(tmp_path / name / "doctor-report.json")["findings"] if item["category"] == "export"] == expected
    for mode in ("why-score-changed", "why-excluded" if blocking else "why-soft-gap"):
        assert cli.main(["explain", "--mode", mode, "--bundle", str(bp), "--report", str(rp), "--out", str(tmp_path / mode)]) == 0
        reasons = _read(tmp_path / mode / "explain-report.json")["reason_tree"]
        reason = next(item for item in reasons if item["category"] == "export")
        assert reason["blocking"] == blocking and reason["validation_path"] == expected[0]["validation_path"]
        assert reason["evidence_status"] == ("ineligible" if blocking else "soft_gap")
    for selector in ("all", "export_metadata", expected[0]["issue"]):
        p1a.recommend_trust(bp, rp, tmp_path / selector, gap_id=selector)
        recommendation = _read(tmp_path / selector / "recommendation-report.json")["recommendations"][0]
        assert recommendation["blocking"] == blocking and recommendation["recommended_actions"] and recommendation["source_refs"]


@pytest.mark.parametrize("bad_schema", ["missing_debug", "unknown_version", "blank_profile"])
@pytest.mark.parametrize("status", ["success", "partial"])
def test_current_schema_failure_is_low_even_if_export_report_claims_schema_valid(bad_schema, status, tmp_path):
    bundle, report, bp, rp = _inputs(tmp_path)
    if bad_schema == "missing_debug":
        del bundle["metadata"]["debugOnly"]
    elif bad_schema == "unknown_version":
        bundle["metadata"]["qegVersion"] = "unknown"
    else:
        bundle["metadata"]["profile"] = ""
    report["export_status"] = status
    result, doctor = _evaluate(bundle, report, bp, rp, tmp_path / "trust")
    assert report["qeg_schema_compatibility"]["valid"] is True
    assert result["trust_status"] == "partial" and result["score_confidence"] == "low"
    schemas = [item for item in doctor["findings"] if item["category"] == "schema"]
    assert len(schemas) == 1 and schemas[0]["blocking"]
    p1a.explain_trust(bp, rp, tmp_path / "explain", mode="why-score-changed")
    reason = next(item for item in _read(tmp_path / "explain/explain-report.json")["reason_tree"] if item["category"] == "schema")
    assert reason["validation_path"] == schemas[0]["validation_path"] and reason["blocking"]
    p1a.recommend_trust(bp, rp, tmp_path / "recommend", gap_id="bundle_schema")
    recommendation = _read(tmp_path / "recommend/recommendation-report.json")["recommendations"][0]
    assert recommendation["validation_path"] == reason["validation_path"] and recommendation["blocking"]


def test_old_report_without_optional_export_metadata_stays_compatible(tmp_path):
    bundle, report, bp, rp = _inputs(tmp_path)
    del report["export_status"], report["qeg_schema_compatibility"]
    result, doctor = _evaluate(bundle, report, bp, rp, tmp_path / "trust")
    assert result["score_confidence"] == "high" and not doctor["findings"]
    assert "export_status" not in _read(rp) and "qeg_schema_compatibility" not in _read(rp)


def test_structured_original_validation_errors_are_preserved(tmp_path):
    bundle, report, bp, rp = _inputs(tmp_path)
    report["qeg_schema_compatibility"]["errors"] = [{"path": ["nodes", 7], "message": "元の検証エラー", "extension": [1, None]}]
    result, doctor = _evaluate(bundle, report, bp, rp, tmp_path / "trust")
    assert result["score_confidence"] == "low"
    assert doctor["findings"][0]["reported_validation"] == report["qeg_schema_compatibility"]


def test_export_partial_cannot_raise_provenance_failure_confidence(tmp_path):
    bundle, report, bp, rp = _inputs(tmp_path)
    report.update(export_status="partial", commit_sha="invalid")
    result, _ = _evaluate(bundle, report, bp, rp, tmp_path / "trust")
    assert result["score_confidence"] == "low"
