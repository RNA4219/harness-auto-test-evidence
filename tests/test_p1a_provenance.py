"""P1aのprovenance形式と、入力不足を反映する信頼度の回帰テスト。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hate import cli
from hate.p1a import doctor_trust, evaluate_trust, replay_trust
from hate.schema_resources import read_schema, validate_schema_instance

FIXTURE = Path("fixtures/golden/p0b-qeg-minimal/expected")


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _inputs():
    return _read(FIXTURE / "qeg-bundle.json"), _read(FIXTURE / "qeg-export-report.json")


def _artifact(bundle, digest):
    bundle["nodes"].append({
        "id": f"artifact:{len(bundle['nodes'])}", "kind": "evidence_artifact", "label": "artifact",
        "data": {"path": "artifacts/trace.zip", "sha256": digest}, "sourceRefs": ["manifest.json"],
    })


def _set_matching_commit(bundle, report, commit):
    report["commit_sha"] = commit
    bundle["metadata"]["commitSha"] = commit
    for node in bundle["nodes"]:
        if "commit_sha" in node.get("data", {}):
            node["data"]["commit_sha"] = commit


def _run(bundle, report, tmp_path, operation=evaluate_trust):
    paths = tmp_path / "bundle.json", tmp_path / "report.json"
    for path, value in zip(paths, (bundle, report), strict=True):
        path.write_text(json.dumps(value), encoding="utf-8")
    before = [path.read_bytes() for path in paths]
    out = tmp_path / "out"
    result = operation(*paths, out)
    doctor = _read(out / "doctor-report.json")
    assert not validate_schema_instance(doctor, read_schema("doctor-report.schema.json"))
    assert [path.read_bytes() for path in paths] == before
    return result, doctor, out


@pytest.mark.parametrize("commit", ["", "not-a-commit", "a" * 6, "a" * 65, "a" * 40 + "\n"])
def test_invalid_commit_is_a_blocking_provenance_finding(commit, tmp_path):
    bundle, report = _inputs()
    report["commit_sha"] = commit
    result, doctor, out = _run(bundle, report, tmp_path)
    assert result["trust_status"] == "partial"
    assert result["score_confidence"] == "low"
    assert _read(out / "aete-score.json")["dimensions"]["provenance_integrity"] <= 1
    finding = next(item for item in doctor["findings"] if item.get("issue") == "invalid_commit_sha")
    assert finding["category"] == "provenance" and finding["blocking"]
    assert finding["finding_code"] == "HATE-DOC-PROV-001"
    assert finding["validation_path"] == ["commit_sha"]


@pytest.mark.parametrize("target", ["bundle", "report"])
@pytest.mark.parametrize("timestamp", [
    "", "not-a-date", "2026-06-28", "2026-06-28T00:01:00", "2026-02-30T00:00:00Z",
    "2026-06-28T00:01:00+01:99", "2026-06-28T00:01:00+24:00",
    "2026-06-28T00:01:00Z\n",
])
def test_invalid_timestamp_cannot_establish_provenance(target, timestamp, tmp_path):
    bundle, report = _inputs()
    if target == "bundle":
        bundle["metadata"]["createdAt"] = timestamp
    else:
        report["created_at"] = timestamp
    result, doctor, out = _run(bundle, report, tmp_path)
    assert result["trust_status"] == "partial" and result["score_confidence"] == "low"
    assert _read(out / "aete-score.json")["dimensions"]["provenance_integrity"] <= 1
    finding = next(item for item in doctor["findings"] if item.get("issue") == "invalid_created_at")
    assert finding["validation_path"] == (["metadata", "createdAt"] if target == "bundle" else ["created_at"])


@pytest.mark.parametrize("digest", ["", "invalid", "a" * 63, "a" * 65, "g" * 64, "a" * 64 + "\n", None, True, {}])
def test_one_valid_hash_does_not_hide_an_invalid_declared_artifact(digest, tmp_path):
    bundle, report = _inputs()
    _artifact(bundle, "a" * 64)
    _artifact(bundle, digest)
    result, doctor, out = _run(bundle, report, tmp_path)
    assert result["trust_status"] == "partial" and result["score_confidence"] == "low"
    assert _read(out / "aete-score.json")["dimensions"]["provenance_integrity"] == 1
    finding = next(item for item in doctor["findings"] if item.get("issue") == "invalid_artifact_sha256")
    assert finding["validation_path"] == ["nodes", len(bundle["nodes"]) - 1, "data", "sha256"]


@pytest.mark.parametrize("digest", ["a" * 64, "A" * 64, "sha256:" + "a" * 64])
@pytest.mark.parametrize("timestamp", ["2026-06-28T00:01:00Z", "2026-06-28t00:01:00z", "2026-06-28T09:01:00.123456789+09:00"])
def test_valid_declared_hash_is_base_provenance_without_tamper_resistance(digest, timestamp, tmp_path):
    bundle, report = _inputs()
    bundle["metadata"]["createdAt"] = timestamp
    _set_matching_commit(bundle, report, "A" * 7)
    _artifact(bundle, digest)
    result, doctor, out = _run(bundle, report, tmp_path)
    score = _read(out / "aete-score.json")
    assert result["trust_status"] == "success" and result["score_confidence"] == "high"
    assert doctor["findings"] == []
    assert score["dimensions"]["provenance_integrity"] == 3
    observed = next(item["observed"] for item in score["dimension_signals"] if item["dimension"] == "provenance_integrity")
    assert observed["valid_artifact_hash_count"] == 1
    assert observed["artifact_content_verified"] is False
    assert observed["tamper_resistance_verified"] is False


def test_optional_artifact_absence_is_partial_provenance_without_invented_errors(tmp_path):
    result, doctor, out = _run(*_inputs(), tmp_path)
    assert result["trust_status"] == "success" and result["score_confidence"] == "high"
    assert doctor["findings"] == []
    assert _read(out / "aete-score.json")["dimensions"]["provenance_integrity"] == 1


def test_declared_artifact_requires_hash_but_report_timestamp_is_optional(tmp_path):
    bundle, report = _inputs()
    report.pop("created_at")
    _set_matching_commit(bundle, report, "a" * 64)
    _artifact(bundle, "a" * 64)
    result, doctor, out = _run(bundle, report, tmp_path)
    assert result["score_confidence"] == "high" and doctor["findings"] == []
    assert _read(out / "aete-score.json")["dimensions"]["provenance_integrity"] == 3
    del bundle["nodes"][-1]["data"]["sha256"]
    result, doctor, out = _run(bundle, report, tmp_path)
    assert result["trust_status"] == "partial" and result["score_confidence"] == "low"
    assert any(item.get("issue") == "invalid_artifact_sha256" for item in doctor["findings"])


def test_invalid_provenance_takes_priority_over_partial_confidence(tmp_path):
    bundle, report = _inputs()
    report["commit_sha"] = "invalid"
    report["missing_execution"] = [{"reason": "unexecuted test"}]
    result, _, _ = _run(bundle, report, tmp_path)
    assert result["score_confidence"] == "low"


@pytest.mark.parametrize(("target", "field"), [
    (target, field)
    for target in ("bundle-completeness", "report-completeness", "report")
    for field in ("unsupportedClaims", "excludedArtifacts", "parserFailures", "partial")
    if target != "report" or field in {"unsupportedClaims", "excludedArtifacts"}
])
def test_completeness_gaps_from_either_input_lower_confidence(target, field, tmp_path):
    bundle, report = _inputs()
    container = bundle["completeness"] if target == "bundle-completeness" else report.setdefault("completeness", {}) if target == "report-completeness" else report
    container[field] = True if field == "partial" else [{"reason": "input evidence gap"}]
    result, _, out = _run(bundle, report, tmp_path)
    assert result["score_confidence"] == "medium"
    assert _read(out / "aete-score.json")["score_confidence"] == "medium"


@pytest.mark.parametrize("operation", [evaluate_trust, replay_trust, doctor_trust])
def test_missing_commit_is_diagnosed_across_public_operations(operation, tmp_path):
    bundle, report = _inputs()
    del report["commit_sha"]
    _, doctor, _ = _run(bundle, report, tmp_path, operation)
    assert any(item.get("issue") == "invalid_commit_sha" and item["blocking"] for item in doctor["findings"])


def test_cli_and_replay_keep_the_same_provenance_diagnosis(tmp_path, capsys):
    bundle, report = _inputs()
    _artifact(bundle, "bad-digest")
    result, doctor, out = _run(bundle, report, tmp_path)
    args = ["--bundle", str(tmp_path / "bundle.json"), "--report", str(tmp_path / "report.json")]
    assert cli.main(["trust", "evaluate", *args, "--out", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["trust_status"] == "partial"
    score = _read(out / "aete-score.json")
    replay = tmp_path / "replay"
    replay_trust(tmp_path / "bundle.json", tmp_path / "report.json", replay)
    assert _read(replay / "aete-score.json") == score
    assert _read(replay / "doctor-report.json") == doctor
    assert result["score_confidence"] == "low"
