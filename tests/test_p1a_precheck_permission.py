"""既存bundleのprecheck不許可を評価成功・高信頼へ置き換えない。"""

from __future__ import annotations

import copy
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
    bundle, report = _read(SOURCE / "qeg-bundle.json"), _read(SOURCE / "qeg-export-report.json")
    return bundle, report, tmp_path / "qeg-bundle.json", tmp_path / "qeg-export-report.json"


def _data(bundle):
    return next(node["data"] for node in bundle["nodes"] if node["id"].startswith("hate_precheck:"))


def _evaluate(bundle, report, bundle_path, report_path, out):
    _write(bundle_path, bundle)
    _write(report_path, report)
    before = bundle_path.read_bytes(), report_path.read_bytes()
    result = p1a.evaluate_trust(bundle_path, report_path, out)
    assert (bundle_path.read_bytes(), report_path.read_bytes()) == before
    doctor = _read(out / "doctor-report.json")
    assert not doctor["release_gate_override"] and not doctor["publish_gate_override"]
    return result, [item for item in doctor["findings"] if item["category"] == "precheck" and item["blocking"]]


@pytest.mark.parametrize("decision", ["eligible", "conditional", "ineligible", "hard_dq"])
@pytest.mark.parametrize("allowed", [True, False])
@pytest.mark.parametrize("exit_code", [0, 2])
@pytest.mark.parametrize("dq_hits", [[], [{"code": "HATE-DQ-002", "message": "schema invalid"}]])
def test_any_denial_survives_conflicting_permission_flags(decision, allowed, exit_code, dq_hits, tmp_path):
    bundle, report, bp, rp = _inputs(tmp_path)
    data = _data(bundle)
    data.update(decision=decision, qeg_export_allowed=allowed, exit_code=exit_code, dq_hits=dq_hits)
    denied = decision in {"ineligible", "hard_dq"} or not allowed or exit_code == 2 or bool(dq_hits)
    result, findings = _evaluate(bundle, report, bp, rp, tmp_path / "trust")
    assert len(findings) == int(denied)
    if denied:
        assert result["trust_status"] == "partial" and result["score_confidence"] == "low" and result["exit_code"] == 0
        finding = findings[0]
        assert finding["issue"] == "precheck_export_not_allowed" and finding["severity"] == "high"
        assert finding["finding_code"] == "HATE-DOC-PRE-001" and finding["precheck_payload"] == data
        assert finding["validation_path"] == ["nodes", 0, "data"]
        fields = {item["field"] for item in finding["violations"]}
        assert ("decision" in fields) == (decision in {"ineligible", "hard_dq"})
        assert ("qeg_export_allowed" in fields) == (not allowed)
        assert ("exit_code" in fields) == (exit_code == 2)
        assert ("dq_hits" in fields) == bool(dq_hits)
        assert all(item["validation_path"] == ["nodes", 0, "data", item["field"]] for item in finding["violations"])
    else:
        assert result["score_confidence"] == ("medium" if decision == "conditional" else "high")


@pytest.mark.parametrize("field", ["decision", "exit_code", "qeg_export_allowed"])
def test_missing_original_permission_is_blocking_without_backfilling(field, tmp_path):
    bundle, report, bp, rp = _inputs(tmp_path)
    del _data(bundle)[field]
    result, findings = _evaluate(bundle, report, bp, rp, tmp_path / "trust")
    assert result["score_confidence"] == "low" and findings[0]["issue"] == "precheck_permission_invalid"
    assert findings[0]["violations"][0]["field"] == field
    assert field not in _data(_read(bp))


@pytest.mark.parametrize(("field", "value"), [("decision", ""), ("decision", "unknown"), ("decision", "ELIGIBLE"),
                                             ("exit_code", -1), ("exit_code", 1), ("exit_code", 3)])
def test_unknown_semantic_values_are_diagnosed_after_processing(field, value, tmp_path):
    bundle, report, bp, rp = _inputs(tmp_path)
    _data(bundle)[field] = value
    result, findings = _evaluate(bundle, report, bp, rp, tmp_path / "trust")
    assert result["exit_code"] == 0 and result["score_confidence"] == "low"
    assert findings[0]["issue"] == "precheck_permission_invalid"
    assert findings[0]["violations"][0]["validation_path"][-1] == field


@pytest.mark.parametrize("name", OPERATIONS)
@pytest.mark.parametrize(("field", "value"), [
    ("qeg_export_allowed", "false"), ("qeg_export_allowed", 0), ("qeg_export_allowed", None),
    ("exit_code", False), ("exit_code", "0"), ("exit_code", 0.5), ("exit_code", None),
    ("dq_hits", None), ("dq_hits", {}), ("dq_hits", ["DQ"]),
])
def test_malformed_permission_stops_all_api_and_cli_outputs(name, field, value, tmp_path, capsys):
    bundle, report, bp, rp = _inputs(tmp_path)
    _data(bundle)[field] = value
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
        assert caught.value.exit_code == 1 and f"data.{field}" in str(caught.value)
        args = ["trust", "evaluate"] if name == "trust" else [name]
        assert cli.main([*args, "--bundle", str(bp), "--report", str(rp), "--out", str(destination)]) == 1
        stderr = capsys.readouterr().err
        assert f"data.{field}" in stderr and "Traceback" not in stderr
    assert not (tmp_path / "new").exists()
    assert list(out.iterdir()) == [saved] and saved.read_bytes() == b"preserved"
    assert (bp.read_bytes(), rp.read_bytes()) == before


@pytest.mark.parametrize(("token", "result"), [("0.0", "high"), ("-0e0", "high"), ("2e0", "low"),
                                              ("1e-9999", "invalid"), ("2.00000000000000001", "invalid"),
                                              ("1.99999999999999999", "invalid")])
def test_exit_code_uses_original_json_number_before_rounding(token, result, tmp_path):
    bundle, report, bp, rp = _inputs(tmp_path)
    text = json.dumps(bundle)
    assert text.count('"exit_code": 0') == 1
    bp.write_text(text.replace('"exit_code": 0', f'"exit_code": {token}'), encoding="utf-8")
    _write(rp, report)
    if result == "invalid":
        with pytest.raises(p1a.TrustError, match="exit_code"):
            p1a.evaluate_trust(bp, rp, tmp_path / "trust")
        assert not (tmp_path / "trust").exists()
    else:
        assert p1a.evaluate_trust(bp, rp, tmp_path / "trust")["score_confidence"] == result


def test_denial_reaches_replay_doctor_explanation_and_recommendation(tmp_path):
    bundle, report, bp, rp = _inputs(tmp_path)
    _data(bundle).update(decision="hard_dq", exit_code=2, qeg_export_allowed=False,
                         dq_hits=[{"code": "HATE-DQ-002"}], reasons=["Original evidence is invalid"])
    result, findings = _evaluate(bundle, report, bp, rp, tmp_path / "trust")
    assert result["score_confidence"] == "low"
    for name, operation in (("replay", p1a.replay_trust), ("doctor", p1a.doctor_trust)):
        operation(bp, rp, tmp_path / name)
        assert [item for item in _read(tmp_path / name / "doctor-report.json")["findings"]
                if item["category"] == "precheck" and item["blocking"]] == findings
    for mode in ("why-excluded", "why-score-changed"):
        p1a.explain_trust(bp, rp, tmp_path / mode, mode=mode)
        reasons = _read(tmp_path / mode / "explain-report.json")["reason_tree"]
        reason = next(item for item in reasons if item["category"] == "precheck")
        assert reason["evidence_status"] == "ineligible" and reason["blocking"]
        assert reason["violations"] == findings[0]["violations"] and reason["source_refs"]
    for selector in ("all", "precheck", "precheck_permission"):
        p1a.recommend_trust(bp, rp, tmp_path / selector, gap_id=selector)
        recommendation = _read(tmp_path / selector / "recommendation-report.json")["recommendations"][0]
        assert recommendation["gap_id"] == "precheck_permission" and recommendation["blocking"]
        assert recommendation["precheck_payload"] == _data(bundle) and recommendation["recommended_actions"]


@pytest.mark.parametrize("reverse", [True, False])
def test_one_permitted_node_cannot_cancel_another_nodes_denial(reverse, tmp_path):
    bundle, report, bp, rp = _inputs(tmp_path)
    node = copy.deepcopy(bundle["nodes"][0])
    node["id"] += ":second-source"
    node["data"]["qeg_export_allowed"] = False
    bundle["nodes"].append(node)
    if reverse:
        bundle["nodes"].reverse()
    result, findings = _evaluate(bundle, report, bp, rp, tmp_path / "trust")
    assert result["score_confidence"] == "low" and len(findings) == 1
    assert findings[0]["precheck_node_id"] == node["id"]


def test_denial_takes_priority_over_nonblocking_soft_gap(tmp_path):
    bundle, report, bp, rp = _inputs(tmp_path)
    _data(bundle).update(decision="conditional", qeg_export_allowed=False, soft_gaps=[{"message": "Optional context missing"}])
    result, findings = _evaluate(bundle, report, bp, rp, tmp_path / "trust")
    assert result["score_confidence"] == "low" and len(findings) == 1
    all_precheck = [item for item in _read(tmp_path / "trust/doctor-report.json")["findings"] if item["category"] == "precheck"]
    assert {item["severity"] for item in all_precheck} == {"high", "medium"}


def test_non_hate_gate_is_not_subject_to_hate_permission_contract(tmp_path):
    bundle, report, bp, rp = _inputs(tmp_path)
    node = bundle["nodes"][0]
    old_id = node["id"]
    node.update(id="external:gate", data={"decision": "go", "exit_code": "external", "qeg_export_allowed": "external"})
    bundle["edges"] = [edge for edge in bundle["edges"] if edge["from"] != old_id]
    result, findings = _evaluate(bundle, report, bp, rp, tmp_path / "trust")
    assert result["score_confidence"] == "high" and not findings
