"""run情報の誤変換・取り違えと未知profileの回帰テスト。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hate import cli
from hate.p0a import PrecheckError, generate_p0a
from hate.p1a import TrustError, doctor_trust, evaluate_trust, explain_trust, recommend_trust, replay_trust

P0A_INPUT = Path("fixtures/golden/p0a-minimal/input")
TRUST_INPUT = Path("fixtures/golden/p0b-qeg-minimal/expected")
TRUST_COMMANDS = ["trust", "replay", "doctor", "explain", "recommend"]
OPERATIONS = {
    "trust": evaluate_trust, "replay": replay_trust, "doctor": doctor_trust,
    "explain": explain_trust, "recommend": recommend_trust,
}


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _snapshot(out: Path) -> dict[str, tuple[bytes, int]]:
    return {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in out.iterdir()}


@pytest.mark.parametrize(("field", "value"), [
    *(('run_attempt', value) for value in [True, False, 1.9, 0, -1, "1.9", "", None, [], {}, "NaN"]),
    *(('run_id', value) for value in [True, False, 1.9, "", "  ", None, [], {}]),
])
def test_p0a_rejects_invalid_run_identity_before_output(
    field: str, value, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    source, out = tmp_path / "input", tmp_path / "out"
    shutil.copytree(P0A_INPUT, source)
    path = source / "github-context.json"
    context = _json(path)
    context[field] = value
    _save(path, context)
    out.mkdir()
    (out / "HATE-run.json").write_bytes(b"previous verified run")
    before = _snapshot(out)
    with pytest.raises(PrecheckError, match=field) as caught:
        generate_p0a(source, out)
    assert caught.value.exit_code == 1
    assert cli.main(["p0a", "--input", str(source), "--out", str(out)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "HATE-E-CLI:" in captured.err and field in captured.err
    assert _snapshot(out) == before


@pytest.mark.parametrize("attempt", [2, 2.0, "2", "02", " 2 "])
def test_p0a_normalizes_ci_run_values_without_changing_identity(attempt, tmp_path: Path) -> None:
    source, out = tmp_path / "input", tmp_path / "out"
    shutil.copytree(P0A_INPUT, source)
    path = source / "github-context.json"
    context = _json(path)
    context.update(run_id=1001, run_attempt=attempt)
    _save(path, context)
    assert generate_p0a(source, out)["exit_code"] == 0
    run = _json(out / "HATE-run.json")
    assert run["run_id"] == "1001"
    assert run["run_attempt"] == 2 and type(run["run_attempt"]) is int
    assert run["payload"]["ci"]["run_attempt"] == 2
    assert run["record_id"] == "run-1001-attempt-2"
    for line in (out / "HATE-test-results.ndjson").read_text(encoding="utf-8").splitlines():
        assert json.loads(line)["run_attempt"] == 2


@pytest.mark.parametrize("profile", ["strict-typo", ""])
def test_p0a_unknown_profile_is_an_input_error(profile: str, tmp_path: Path) -> None:
    out = tmp_path / "out"
    with pytest.raises(PrecheckError, match="unknown profile") as caught:
        generate_p0a(P0A_INPUT, out, profile=profile)
    assert caught.value.exit_code == 1
    assert not out.exists()


@pytest.mark.parametrize("command", ["trust", "replay"])
@pytest.mark.parametrize("profile", ["strict-typo", ""])
def test_trust_unknown_profile_is_an_input_error(
    command: str, profile: str, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "out"
    bundle, report = TRUST_INPUT / "qeg-bundle.json", TRUST_INPUT / "qeg-export-report.json"
    with pytest.raises(TrustError, match="unknown profile") as caught:
        OPERATIONS[command](bundle, report, out, profile=profile)
    assert caught.value.exit_code == 1
    args = ["trust", "evaluate"] if command == "trust" else [command]
    assert cli.main([*args, "--bundle", str(bundle), "--report", str(report), "--out", str(out),
                     "--profile", profile]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "unknown profile" in captured.err
    assert not out.exists()


@pytest.mark.parametrize("command", TRUST_COMMANDS)
@pytest.mark.parametrize(("target", "field", "value"), [
    *(('metadata', 'runAttempt', value) for value in [True, False, 1.9, 0, -1, "2", None, []]),
    *(('report', 'run_attempt', value) for value in [True, 1.9, 0, "2", None]),
    *(('metadata', 'runId', value) for value in [True, 1001, None, {}]),
    *(('report', 'run_id', value) for value in [1001, None, []]),
    ('bundle', 'metadata', None), ('bundle', 'metadata', []),
    ('metadata', 'createdAt', {}), ('report', 'created_at', []), ('report', 'commit_sha', {}),
])
def test_trust_rejects_invalid_identity_fields_before_output(
    command: str, target: str, field: str, value, tmp_path: Path,
) -> None:
    bundle, report = _json(TRUST_INPUT / "qeg-bundle.json"), _json(TRUST_INPUT / "qeg-export-report.json")
    data = {"metadata": bundle["metadata"], "bundle": bundle, "report": report}[target]
    data[field] = value
    bundle_path, report_path = tmp_path / "bundle.json", tmp_path / "report.json"
    _save(bundle_path, bundle)
    _save(report_path, report)
    out = tmp_path / "out"
    out.mkdir()
    (out / "aete-score.json").write_bytes(b"previous verified score")
    before = _snapshot(out)
    with pytest.raises(TrustError, match=field) as caught:
        OPERATIONS[command](bundle_path, report_path, out)
    assert caught.value.exit_code == 1
    assert _snapshot(out) == before
    assert _json(bundle_path) == bundle and _json(report_path) == report


@pytest.mark.parametrize("command", TRUST_COMMANDS)
@pytest.mark.parametrize(("field", "value"), [("run_id", "different-run"), ("run_attempt", 42)])
def test_trust_rejects_a_report_from_another_run_or_attempt(
    command: str, field: str, value, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    report = _json(TRUST_INPUT / "qeg-export-report.json")
    report[field] = value
    path, out = tmp_path / "other-report.json", tmp_path / "out"
    _save(path, report)
    bundle = TRUST_INPUT / "qeg-bundle.json"
    with pytest.raises(TrustError, match="mismatch") as caught:
        OPERATIONS[command](bundle, path, out)
    assert caught.value.exit_code == 1
    args = ["trust", "evaluate"] if command == "trust" else [command]
    assert cli.main([*args, "--bundle", str(bundle), "--report", str(path), "--out", str(out)]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and field in captured.err
    assert str(value) in captured.err and "mismatch" in captured.err
    assert not out.exists()


@pytest.mark.parametrize("field", ["run_id", "run_attempt"])
def test_trust_does_not_invent_identity_when_both_inputs_omit_it(field: str, tmp_path: Path) -> None:
    bundle, report = _json(TRUST_INPUT / "qeg-bundle.json"), _json(TRUST_INPUT / "qeg-export-report.json")
    bundle["metadata"].pop({"run_id": "runId", "run_attempt": "runAttempt"}[field])
    report.pop(field)
    bundle_path, report_path = tmp_path / "bundle.json", tmp_path / "report.json"
    _save(bundle_path, bundle)
    _save(report_path, report)
    with pytest.raises(TrustError, match=field) as caught:
        evaluate_trust(bundle_path, report_path, tmp_path / "out")
    assert caught.value.exit_code == 1
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("identity_source", ["bundle", "report", "both"])
def test_trust_resolves_existing_identity_without_fabricating_provenance(
    identity_source: str, tmp_path: Path,
) -> None:
    bundle, report = _json(TRUST_INPUT / "qeg-bundle.json"), _json(TRUST_INPUT / "qeg-export-report.json")
    bundle["metadata"]["runAttempt"] = 2.0
    report["run_attempt"] = 2
    for node in bundle["nodes"]:
        if "run_attempt" in node.get("data", {}):
            node["data"]["run_attempt"] = 2
    if identity_source == "report":
        bundle["metadata"].pop("runId")
        bundle["metadata"].pop("runAttempt")
    elif identity_source == "bundle":
        report.pop("run_id")
        report.pop("run_attempt")
    bundle_path, report_path = tmp_path / "bundle.json", tmp_path / "report.json"
    _save(bundle_path, bundle)
    _save(report_path, report)
    out = tmp_path / "out"
    assert evaluate_trust(bundle_path, report_path, out)["exit_code"] == 0
    score = _json(out / "aete-score.json")
    assert score["run_id"] == "1001" and score["run_attempt"] == 2
    if identity_source == "report":
        assert score["dimensions"]["provenance_integrity"] == 0
    assert _json(bundle_path) == bundle and _json(report_path) == report


@pytest.mark.parametrize("engine", ["p0a", "trust"])
@pytest.mark.parametrize("token", ["1.00000000000000001", "9007199254740993.1", "1e-400", "NaN", "Infinity"])
def test_run_attempt_is_validated_before_json_float_rounding(engine: str, token: str, tmp_path: Path) -> None:
    if engine == "p0a":
        source = tmp_path / "input"
        shutil.copytree(P0A_INPUT, source)
        path = source / "github-context.json"
        value = _json(path)
        value["run_attempt"] = "ATTEMPT_TOKEN"
    else:
        path = tmp_path / "bundle.json"
        value = _json(TRUST_INPUT / "qeg-bundle.json")
        value["metadata"]["runAttempt"] = "ATTEMPT_TOKEN"
    text = json.dumps(value)
    assert text.count('"ATTEMPT_TOKEN"') == 1
    path.write_text(text.replace('"ATTEMPT_TOKEN"', token), encoding="utf-8")
    with pytest.raises(PrecheckError if engine == "p0a" else TrustError) as caught:
        if engine == "p0a":
            generate_p0a(source, tmp_path / "out")
        else:
            evaluate_trust(path, TRUST_INPUT / "qeg-export-report.json", tmp_path / "out")
    assert caught.value.exit_code == 1
    assert not (tmp_path / "out").exists()


def test_large_integral_json_attempt_keeps_the_original_integer(tmp_path: Path) -> None:
    expected = 9007199254740993
    bundle = _json(TRUST_INPUT / "qeg-bundle.json")
    bundle["metadata"]["runAttempt"] = "ATTEMPT_TOKEN"
    bundle_path, report_path = tmp_path / "bundle.json", tmp_path / "report.json"
    for node in bundle["nodes"]:
        if "run_attempt" in node.get("data", {}):
            node["data"]["run_attempt"] = expected
    bundle_path.write_text(json.dumps(bundle).replace('"ATTEMPT_TOKEN"', f"{expected}.0"), encoding="utf-8")
    report = _json(TRUST_INPUT / "qeg-export-report.json")
    report["run_attempt"] = expected
    _save(report_path, report)
    out = tmp_path / "out"
    assert evaluate_trust(bundle_path, report_path, out)["exit_code"] == 0
    assert _json(out / "aete-score.json")["run_attempt"] == expected
    assert _json(out / "retry-aggregation.json")["run_attempt"] == expected
