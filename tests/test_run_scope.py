"""別run/attempt/commitの証跡を現在のrunへ混ぜないための境界検証。"""

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
ENVELOPES = (
    "HATE-run.json", "HATE-test-results.ndjson", "HATE-coverage.ndjson", "artifact-manifest.json",
    "precheck-decision.json", "record.json", "HATE-contract.ndjson", "HATE-mutation.ndjson", "HATE-evidence-strength.ndjson",
)
OPERATIONS = {"trust": p1a.evaluate_trust, "replay": p1a.replay_trust, "doctor": p1a.doctor_trust,
              "explain": p1a.explain_trust, "recommend": p1a.recommend_trust}


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def _fixture(tmp_path):
    root = tmp_path / "input"
    shutil.copytree(SOURCE, root)
    template = json.loads((root / "p0a/HATE-test-results.ndjson").read_text(encoding="utf-8").splitlines()[0])
    for name in ENVELOPES:
        path = root / "p0a" / name
        if not path.exists():
            fixture = {
                "HATE-contract.ndjson": Path("fixtures/adapters/pact/contract-evidence/HATE-contract.ndjson"),
                "HATE-mutation.ndjson": Path("fixtures/adapters/stryker/mutation-evidence/HATE-mutation.ndjson"),
            }.get(name)
            if fixture is not None:
                shutil.copy2(fixture, path)
                continue
            record = copy.deepcopy(template)
            record["record_type"] = "evidence_strength"
            record["payload"] = {
                "test_id": template["payload"]["canonical_test_id"], "flake_score": "unknown", "mutation_score": "unknown",
                "sample_size": 0, "computed_at": template["created_at"], "inputs": [],
            }
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    return root


def _change(path, field, value, *, remove=False):
    if path.suffix == ".ndjson":
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        records = [_read(path)]
    if remove:
        records[0].pop(field)
    else:
        records[0][field] = value
    if path.suffix == ".ndjson":
        path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    else:
        _write(path, records[0])


@pytest.mark.parametrize("name", ENVELOPES)
@pytest.mark.parametrize(("field", "value"), [("run_id", "foreign-run"), ("run_attempt", 9), ("commit_sha", "b" * 40)])
def test_p0b_checks_all_current_run_envelopes_before_output(name, field, value, tmp_path, capsys):
    root = _fixture(tmp_path)
    _change(root / "p0a" / name, field, value)
    out = tmp_path / "out"
    out.mkdir()
    sentinel = out / "qeg-bundle.json"
    sentinel.write_bytes(b"previous bundle")
    with pytest.raises(ExportError, match=field) as exc:
        export_qeg(root, out)
    assert exc.value.exit_code == 1 and "mismatch" in str(exc.value)
    assert cli.main(["export", "qeg", "--fixture", str(root), "--out", str(out)]) == 1
    captured = capsys.readouterr()
    assert "HATE-E-EXPORT" in captured.err and "Traceback" not in captured.err
    assert sentinel.read_bytes() == b"previous bundle" and list(out.iterdir()) == [sentinel]


@pytest.mark.parametrize("name", ENVELOPES)
@pytest.mark.parametrize("field", ["run_id", "run_attempt", "commit_sha"])
def test_p0b_does_not_invent_missing_envelope_identity(name, field, tmp_path):
    root = _fixture(tmp_path)
    _change(root / "p0a" / name, field, None, remove=True)
    with pytest.raises(ExportError, match=field) as exc:
        export_qeg(root, tmp_path / "out")
    assert exc.value.exit_code == 1 and name in str(exc.value)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("name", ["HATE-run.json", "HATE-coverage.ndjson", "precheck-decision.json"])
@pytest.mark.parametrize(("field", "value"), [
    ("run_id", 1001), ("run_id", " "), ("run_attempt", True), ("run_attempt", 1.5), ("run_attempt", 0),
    ("run_attempt", "1"), ("commit_sha", []), ("commit_sha", "invalid"), ("commit_sha", "a" * 40 + "\n"),
])
def test_p0b_rejects_wrong_identity_types_and_formats(name, field, value, tmp_path):
    root = _fixture(tmp_path)
    _change(root / "p0a" / name, field, value)
    with pytest.raises(ExportError, match=field):
        export_qeg(root, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("name", ["HATE-run.json", "HATE-coverage.ndjson", "artifact-manifest.json"])
@pytest.mark.parametrize("token", ["1.00000000000000001", "0.99999999999999999", "NaN", "1e999"])
def test_p0b_run_numbers_are_checked_before_float_rounding(name, token, tmp_path):
    root = _fixture(tmp_path)
    path = root / "p0a" / name
    _change(path, "run_attempt", "REPLACE_NUMBER")
    path.write_text(path.read_text(encoding="utf-8").replace('"REPLACE_NUMBER"', token), encoding="utf-8")
    with pytest.raises(ExportError, match=name):
        export_qeg(root, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(("name", "data"), [
    ("HATE-run.json", b"[]"), ("artifact-manifest.json", b"{"), ("record.json", b"\xff"),
    ("HATE-coverage.ndjson", b"\nnull\n"), ("HATE-contract.ndjson", b"\n{\n"),
])
def test_p0b_reader_failures_are_typed_and_located(name, data, tmp_path, capsys):
    root = _fixture(tmp_path)
    (root / "p0a" / name).write_bytes(data)
    with pytest.raises(ExportError, match=name) as exc:
        export_qeg(root, tmp_path / "out")
    assert exc.value.exit_code == 1 and exc.value.__cause__ is not None
    assert cli.main(["export", "qeg", "--fixture", str(root), "--out", str(tmp_path / "out")]) == 1
    assert "Traceback" not in capsys.readouterr().err


@pytest.mark.parametrize("target", ["ci", "diff", "sarif"])
def test_declared_context_identity_is_checked_without_requiring_native_sarif_fields(target, tmp_path):
    root = _fixture(tmp_path)
    if target == "ci":
        path = root / "p0a/HATE-run.json"
        data = _read(path)
        data["payload"]["ci"]["run_attempt"] = 9
    elif target == "diff":
        path = root / "diff-risk-test.json"
        data = _read(path)
        data["commit_sha"] = "b" * 40
    else:
        path = root / "p0a/HATE-static.sarif"
        data = {"version": "2.1.0", "runs": [], "run_id": "foreign-run"}
    _write(path, data)
    with pytest.raises(ExportError, match="mismatch"):
        export_qeg(root, tmp_path / "out")


def test_p0b_normalizes_integral_attempts_and_retains_commit_without_mutating_sources(tmp_path):
    root = _fixture(tmp_path)
    for name in ENVELOPES:
        _change(root / "p0a" / name, "run_attempt", 1.0)
        _change(root / "p0a" / name, "commit_sha", "0123456789ABCDEF0123456789ABCDEF01234567")
    before = {name: (root / "p0a" / name).read_bytes() for name in ENVELOPES}
    export_qeg(root, tmp_path / "out")
    bundle = _read(tmp_path / "out/qeg-bundle.json")
    assert type(bundle["metadata"]["runAttempt"]) is int and bundle["metadata"]["runAttempt"] == 1
    assert bundle["metadata"]["commitSha"] == "0123456789ABCDEF0123456789ABCDEF01234567"
    for node in bundle["nodes"]:
        if node["kind"] == "execution_evidence":
            assert node["data"]["commit_sha"].lower() == bundle["metadata"]["commitSha"].lower()
            assert type(node["data"]["run_attempt"]) is int
    assert before == {name: (root / "p0a" / name).read_bytes() for name in ENVELOPES}
    assert p1a.evaluate_trust(tmp_path / "out/qeg-bundle.json", tmp_path / "out/qeg-export-report.json", tmp_path / "trust")["trust_status"] == "success"


def _trust_input(tmp_path):
    bundle = _read(EXPECTED / "qeg-bundle.json")
    report = _read(EXPECTED / "qeg-export-report.json")
    return bundle, report, tmp_path / "bundle.json", tmp_path / "report.json", tmp_path / "out"


@pytest.mark.parametrize("command", OPERATIONS)
@pytest.mark.parametrize(("field", "value"), [
    ("run_id", "foreign-run"), ("run_attempt", 9), ("commit_sha", "b" * 40),
    ("run_id", False), ("run_attempt", True), ("run_attempt", 1.5), ("commit_sha", []),
])
def test_p1a_checks_execution_identity_in_all_entrypoints(command, field, value, tmp_path, capsys):
    bundle, report, bundle_path, report_path, out = _trust_input(tmp_path)
    node = next(node for node in bundle["nodes"] if node["kind"] == "execution_evidence")
    node["data"][field] = value
    _write(bundle_path, bundle)
    _write(report_path, report)
    out.mkdir()
    sentinel = out / "aete-score.json"
    sentinel.write_bytes(b"previous score")
    with pytest.raises(p1a.TrustError, match=field) as exc:
        OPERATIONS[command](bundle_path, report_path, out)
    assert exc.value.exit_code == 1 and "nodes[" in str(exc.value)
    args = ["trust", "evaluate"] if command == "trust" else [command]
    assert cli.main([*args, "--bundle", str(bundle_path), "--report", str(report_path), "--out", str(out)]) == 1
    assert "Traceback" not in capsys.readouterr().err
    assert sentinel.read_bytes() == b"previous score" and list(out.iterdir()) == [sentinel]


@pytest.mark.parametrize("kind", ["run", "gate_verdict", "test", "coverage", "contract_evidence", "mutation_evidence", "evidence_strength", "evidence_artifact"])
def test_other_current_run_node_declarations_cannot_escape_scope_check(kind, tmp_path):
    bundle, report, bundle_path, report_path, out = _trust_input(tmp_path)
    bundle["nodes"].append({"id": "scope:other", "kind": kind, "label": "scope", "data": {"run_id": "foreign"}, "sourceRefs": ["source.json"]})
    _write(bundle_path, bundle)
    _write(report_path, report)
    with pytest.raises(p1a.TrustError, match="run_id.*mismatch"):
        p1a.evaluate_trust(bundle_path, report_path, out)
    assert not out.exists()


@pytest.mark.parametrize("target", ["report", "metadata", "run-ci"])
def test_p1a_cross_file_commit_and_embedded_ci_scope_are_checked(target, tmp_path):
    bundle, report, bundle_path, report_path, out = _trust_input(tmp_path)
    if target == "report":
        report["commit_sha"] = "b" * 40
    elif target == "metadata":
        bundle["metadata"]["commitSha"] = "b" * 40
    else:
        node = next(node for node in bundle["nodes"] if node["kind"] == "run")
        node["data"]["ci"]["run_attempt"] = 9
    _write(bundle_path, bundle)
    _write(report_path, report)
    with pytest.raises(p1a.TrustError, match="mismatch"):
        p1a.evaluate_trust(bundle_path, report_path, out)


@pytest.mark.parametrize("target", ["metadata", "execution"])
def test_invalid_declared_commit_remains_a_blocking_provenance_finding(target, tmp_path):
    bundle, report, bundle_path, report_path, out = _trust_input(tmp_path)
    if target == "metadata":
        bundle["metadata"]["commitSha"] = "invalid"
    else:
        next(node for node in bundle["nodes"] if node["kind"] == "execution_evidence")["data"]["commit_sha"] = "invalid"
    _write(bundle_path, bundle)
    _write(report_path, report)
    result = p1a.evaluate_trust(bundle_path, report_path, out)
    assert result["trust_status"] == "partial" and result["score_confidence"] == "low"
    doctor = _read(out / "doctor-report.json")
    assert any(finding.get("issue") == "invalid_commit_sha" and finding["blocking"] for finding in doctor["findings"])


def test_legacy_bundle_without_optional_commit_and_node_identity_is_not_backfilled(tmp_path):
    bundle, report, bundle_path, report_path, out = _trust_input(tmp_path)
    bundle["metadata"].pop("commitSha")
    for node in bundle["nodes"]:
        for field in ("run_id", "run_attempt", "commit_sha"):
            node["data"].pop(field, None)
    _write(bundle_path, bundle)
    _write(report_path, report)
    before = bundle_path.read_bytes()
    assert p1a.evaluate_trust(bundle_path, report_path, out)["trust_status"] == "success"
    assert bundle_path.read_bytes() == before


def test_p1a_attempt_lexeme_in_execution_is_not_rounded(tmp_path):
    bundle, report, bundle_path, report_path, out = _trust_input(tmp_path)
    next(node for node in bundle["nodes"] if node["kind"] == "execution_evidence")["data"]["run_attempt"] = "NUMBER"
    bundle_path.write_text(json.dumps(bundle).replace('"NUMBER"', "1.00000000000000001"), encoding="utf-8")
    _write(report_path, report)
    with pytest.raises(p1a.TrustError, match="run_attempt"):
        p1a.evaluate_trust(bundle_path, report_path, out)


def test_historical_defect_node_is_not_relabelled_as_current_run(tmp_path):
    bundle, report, bundle_path, report_path, out = _trust_input(tmp_path)
    historical = {"run_id": "past-run", "run_attempt": 9, "commit_sha": "b" * 40}
    bundle["nodes"].append({"id": "defect:past", "kind": "escaped_defect", "label": "past defect",
                            "data": historical, "sourceRefs": ["history.json"]})
    _write(bundle_path, bundle)
    _write(report_path, report)
    result = p1a.evaluate_trust(bundle_path, report_path, out)
    assert result["trust_status"] == "success"
    assert _read(bundle_path)["nodes"][-1]["data"] == historical


def test_malformed_ci_container_does_not_hide_declared_run_scope(tmp_path):
    bundle, report, bundle_path, report_path, out = _trust_input(tmp_path)
    next(node for node in bundle["nodes"] if node["kind"] == "run")["data"]["ci"] = [{"run_attempt": 9}]
    _write(bundle_path, bundle)
    _write(report_path, report)
    with pytest.raises(p1a.TrustError, match="data.ci must be a JSON object"):
        p1a.evaluate_trust(bundle_path, report_path, out)


@pytest.mark.parametrize("engine", ["p0a", "p0b-json", "p0b-ndjson", "p1a-bundle", "p1a-report"])
@pytest.mark.parametrize("same_value", [True, False])
def test_duplicate_identity_keys_are_not_silently_overwritten(engine, same_value, tmp_path):
    out = tmp_path / "out"
    if engine == "p0a":
        source = tmp_path / "input"
        shutil.copytree("fixtures/golden/p0a-minimal/input", source)
        path = source / "github-context.json"
        value, key = _read(path), "run_attempt"
        error = PrecheckError
    elif engine.startswith("p0b"):
        source = _fixture(tmp_path)
        path = source / "p0a" / ("HATE-run.json" if engine == "p0b-json" else "HATE-test-results.ndjson")
        value = _read(path) if engine == "p0b-json" else json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        key, error = "run_id", ExportError
    else:
        bundle, report, bundle_path, report_path, out = _trust_input(tmp_path)
        _write(bundle_path, bundle)
        _write(report_path, report)
        path = bundle_path if engine == "p1a-bundle" else report_path
        value = bundle if engine == "p1a-bundle" else report
        key, error = ("metadata" if engine == "p1a-bundle" else "run_id"), p1a.TrustError
    first = value[key] if same_value else "foreign"
    text = '{' + json.dumps(key) + ':' + json.dumps(first) + ',' + json.dumps(value)[1:]
    path.write_text(text, encoding="utf-8")
    with pytest.raises(error, match="duplicate JSON object key") as exc:
        if engine == "p0a":
            generate_p0a(source, out)
        elif engine.startswith("p0b"):
            export_qeg(source, out)
        else:
            p1a.evaluate_trust(bundle_path, report_path, out)
    assert exc.value.exit_code == 1
    assert not out.exists()
