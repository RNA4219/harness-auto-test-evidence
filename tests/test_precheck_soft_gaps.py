"""precheckの条件付き理由をexportからP1aの所見・説明・補完まで保持する。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hate import cli, p1a
from hate.p0a import generate_p0a
from hate.p0b import export_qeg
from hate.schema_resources import read_schema, validate_schema_instance

GAP = {"gap_id": "missing_optional_context", "message": "補助情報が未提示", "profile": "strict",
       "extension": {"artifact_ids": ["context"], "detail": [1, True, None]}}
OPERATIONS = {"trust": p1a.evaluate_trust, "replay": p1a.replay_trust, "doctor": p1a.doctor_trust,
              "explain": p1a.explain_trust, "recommend": p1a.recommend_trust}


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _inputs(tmp_path, *, decision="conditional"):
    root = tmp_path / "input"
    shutil.copytree(Path("fixtures/golden/p0b-qeg-minimal/input"), root)
    path = root / "p0a/precheck-decision.json"
    record = _read(path)
    record["payload"].update(decision=decision, soft_gaps=[GAP], reasons=[GAP["message"], "条件付き採用"])
    _write(path, record)
    out = tmp_path / "export"
    export_qeg(root, out)
    return root, out / "qeg-bundle.json", out / "qeg-export-report.json"


def _verdict(bundle):
    return next(node for node in bundle["nodes"] if node["id"].startswith("hate_precheck:"))


def _findings(out):
    return [finding for finding in _read(out / "doctor-report.json")["findings"] if finding["category"] == "precheck"]


@pytest.mark.parametrize("decision", ["conditional", "eligible"])
def test_export_preserves_complete_gap_objects_and_reasons(decision, tmp_path):
    root, bundle_path, report_path = _inputs(tmp_path, decision=decision)
    payload = _read(root / "p0a/precheck-decision.json")["payload"]
    bundle = _read(bundle_path)
    data = _verdict(bundle)["data"]
    for field in ("decision", "exit_code", "qeg_export_allowed", "dq_hits", "soft_gaps", "reasons"):
        assert data[field] == payload[field]
    assert not validate_schema_instance(bundle, read_schema("qeg-bundle.schema.json"))
    # optional gapをparser failureや別のriskへ変換せず、export充足度の既存ルーブリックを維持する。
    assert bundle["completeness"] == _read(report_path)["completeness"]
    assert bundle["completeness"]["score"] == 1 and not bundle["completeness"]["parserFailures"]
    assert "Precheck soft gaps: 1" in (bundle_path.parent / "qeg-export-summary.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("decision", ["conditional", "eligible"])
def test_same_gap_reaches_evaluate_replay_doctor_and_confidence(decision, tmp_path):
    _, bundle_path, report_path = _inputs(tmp_path)
    bundle = _read(bundle_path)
    _verdict(bundle)["data"]["decision"] = decision
    _write(bundle_path, bundle)
    before = bundle_path.read_bytes(), report_path.read_bytes()
    expected = None
    for name, operation in list(OPERATIONS.items())[:3]:
        out = tmp_path / name
        result = operation(bundle_path, report_path, out)
        if name != "doctor":
            assert result["trust_status"] == "partial" and result["score_confidence"] == "medium"
            assert _read(out / "aete-score.json")["score_confidence"] == "medium"
        findings = _findings(out)
        assert len(findings) == 1
        finding = findings[0]
        assert finding["gap"] == GAP and finding["precheck_reasons"] == [GAP["message"], "条件付き採用"]
        assert finding["severity"] == "medium" and finding["blocking"] is False
        assert finding["finding_code"] == "HATE-DOC-PRE-001"
        assert finding["validation_path"] == ["nodes", 0, "data", "soft_gaps", 0]
        assert "qeg-bundle.json" in finding["source_refs"]
        assert "precheck" not in _read(out / "doctor-report.json")["summary"]["blocking_categories"]
        if expected is None:
            expected = findings
        assert findings == expected
    assert (bundle_path.read_bytes(), report_path.read_bytes()) == before


@pytest.mark.parametrize("mode", ["why-soft-gap", "why-score-changed"])
def test_explain_uses_precheck_details_with_source_refs(mode, tmp_path):
    _, bundle_path, report_path = _inputs(tmp_path)
    p1a.explain_trust(bundle_path, report_path, tmp_path / "explain", mode=mode)
    report = _read(tmp_path / "explain/explain-report.json")
    reason = next(item for item in report["reason_tree"] if item["category"] == "precheck")
    assert reason["gap"] == GAP and reason["summary"] == GAP["message"]
    assert reason["evidence_status"] == "soft_gap" and report["summary"]["traceability_complete"]


@pytest.mark.parametrize("selector", ["all", "precheck", GAP["gap_id"], "missing_execution", "unknown"])
def test_recommend_filters_precheck_and_keeps_actionable_evidence(selector, tmp_path):
    _, bundle_path, report_path = _inputs(tmp_path)
    out = tmp_path / "recommend"
    result = p1a.recommend_trust(bundle_path, report_path, out, gap_id=selector)
    assert result["recommendation_count"] == (1 if selector in {"all", "precheck", GAP["gap_id"]} else 0)
    for item in _read(out / "recommendation-report.json")["recommendations"]:
        assert item["gap"] == GAP and item["recommended_actions"] and item["source_refs"]


@pytest.mark.parametrize("with_reasons", [True, False])
def test_legacy_conditional_does_not_claim_no_gaps_or_invent_details(with_reasons, tmp_path):
    _, bundle_path, report_path = _inputs(tmp_path)
    bundle = _read(bundle_path)
    data = _verdict(bundle)["data"]
    del data["soft_gaps"]
    if not with_reasons:
        del data["reasons"]
    _write(bundle_path, bundle)
    result = p1a.evaluate_trust(bundle_path, report_path, tmp_path / "trust")
    assert result["score_confidence"] == "medium"
    finding = _findings(tmp_path / "trust")[0]
    assert finding["issue"] == "precheck_soft_gap_details_missing" and finding["gap"] is None
    assert _verdict(_read(bundle_path))["data"] == data


@pytest.mark.parametrize("name", OPERATIONS)
@pytest.mark.parametrize(("field", "value", "diagnostic"), [
    ("soft_gaps", None, "soft_gaps"), ("soft_gaps", {}, "soft_gaps"),
    ("soft_gaps", ["gap"], "soft_gaps[0]"), ("reasons", "reason", "reasons"),
    ("reasons", [None], "reasons[0]"), ("decision", False, "decision"),
])
def test_malformed_declared_precheck_stops_every_api_and_cli_before_output(name, field, value, diagnostic, tmp_path, capsys):
    _, bundle_path, report_path = _inputs(tmp_path)
    bundle = _read(bundle_path)
    _verdict(bundle)["data"][field] = value
    _write(bundle_path, bundle)
    out = tmp_path / "out"
    out.mkdir()
    (out / "existing.json").write_bytes(b"existing output")
    before = bundle_path.read_bytes(), report_path.read_bytes()
    with pytest.raises(p1a.TrustError, match=rf"data\.{diagnostic.split('[')[0]}") as caught:
        OPERATIONS[name](bundle_path, report_path, out)
    assert caught.value.exit_code == 1
    args = ["trust", "evaluate"] if name == "trust" else [name]
    assert cli.main([*args, "--bundle", str(bundle_path), "--report", str(report_path), "--out", str(out)]) == 1
    stderr = capsys.readouterr().err
    assert diagnostic in stderr and "Traceback" not in stderr
    assert list(out.iterdir()) == [out / "existing.json"] and (out / "existing.json").read_bytes() == b"existing output"
    assert (bundle_path.read_bytes(), report_path.read_bytes()) == before


@pytest.mark.parametrize("message", [None, {}, ["extension"], 123, "", "   "])
def test_open_gap_object_contract_preserves_unknown_fields_without_stringifying_messages(message, tmp_path):
    _, bundle_path, report_path = _inputs(tmp_path)
    bundle = _read(bundle_path)
    _verdict(bundle)["data"]["soft_gaps"][0]["message"] = message
    _write(bundle_path, bundle)
    p1a.doctor_trust(bundle_path, report_path, tmp_path / "doctor")
    finding = _findings(tmp_path / "doctor")[0]
    assert finding["gap"]["message"] == message and finding["message"] == "Precheck declares a soft gap."


def test_foreign_gate_verdict_is_not_interpreted_as_hate_precheck(tmp_path):
    _, bundle_path, report_path = _inputs(tmp_path)
    bundle = _read(bundle_path)
    node = _verdict(bundle)
    old_id = node["id"]
    node["id"] = "external_gate:release"
    node["data"]["soft_gaps"] = "external contract"
    bundle["edges"] = [edge for edge in bundle["edges"] if edge["from"] != old_id]
    _write(bundle_path, bundle)
    p1a.doctor_trust(bundle_path, report_path, tmp_path / "doctor")
    assert not _findings(tmp_path / "doctor")


def test_real_strict_profile_gap_survives_p0a_export_and_p1a(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(Path("fixtures/golden/p0a-minimal/input"), source)
    (source / "artifacts/external-link.txt").write_text("https://example.invalid/fixture", encoding="utf-8")
    run = tmp_path / "run"
    result = generate_p0a(source, run / "p0a", profile="strict")
    assert result["decision"] == "conditional"
    payload = _read(run / "p0a/precheck-decision.json")["payload"]
    export_qeg(run, tmp_path / "export")
    bundle_path, report_path = tmp_path / "export/qeg-bundle.json", tmp_path / "export/qeg-export-report.json"
    assert _verdict(_read(bundle_path))["data"]["soft_gaps"] == payload["soft_gaps"]
    p1a.evaluate_trust(bundle_path, report_path, tmp_path / "trust")
    assert _findings(tmp_path / "trust")[0]["gap"] == payload["soft_gaps"][0]
    assert payload["soft_gaps"][0]["gap_id"] == "unsafe_artifact_profile_gap"


def test_provenance_failure_keeps_low_confidence_when_precheck_also_has_gap(tmp_path):
    _, bundle_path, report_path = _inputs(tmp_path)
    report = _read(report_path)
    report["commit_sha"] = "invalid"
    _write(report_path, report)
    assert p1a.evaluate_trust(bundle_path, report_path, tmp_path / "trust")["score_confidence"] == "low"


def test_legacy_eligible_without_optional_details_stays_compatible(tmp_path):
    _, bundle_path, report_path = _inputs(tmp_path)
    p1a.evaluate_trust(bundle_path, report_path, tmp_path / "conditional")
    bundle = _read(bundle_path)
    data = _verdict(bundle)["data"]
    data["decision"] = "eligible"
    for field in ("soft_gaps", "reasons", "dq_hits"):
        data.pop(field)
    _write(bundle_path, bundle)
    result = p1a.evaluate_trust(bundle_path, report_path, tmp_path / "eligible")
    assert result["score_confidence"] == "high" and not _findings(tmp_path / "eligible")
    # gapの種類に根拠のない減点は加えず、信頼度と所見に反映する。
    for field in ("dimensions", "weighted_score"):
        assert _read(tmp_path / "eligible/aete-score.json")[field] == _read(tmp_path / "conditional/aete-score.json")[field]
