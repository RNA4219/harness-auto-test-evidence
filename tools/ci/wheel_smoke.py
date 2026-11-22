from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from wheel_outcomes import smoke_execution_outcomes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install a wheel outside the repository and run core smoke checks.")
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    args = parser.parse_args(argv)

    wheel = args.wheel.resolve()
    fixture = args.fixture.resolve()
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv executable is required for wheel smoke")

    with tempfile.TemporaryDirectory(prefix="hate-wheel-smoke-") as raw:
        root = Path(raw)
        venv = root / "venv"
        _run([uv, "venv", str(venv)])
        python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        _run([uv, "pip", "install", "--python", str(python), str(wheel)])
        _run([str(python), "-m", "hate", "--help"], cwd=root)
        _run(
            [
                str(python),
                "-m",
                "hate",
                "p0a",
                "--input",
                str(fixture),
                "--out",
                str(root / "p0a-output"),
                "--source-version",
                "wheel-smoke",
            ],
            cwd=root,
        )
        _cli_error_smoke(python, root)
        _trust_graph_smoke(python, root)
        _trust_provenance_smoke(python, root)
        _trust_retry_smoke(python, root)
        _p0b_history_smoke(python, root)
        _p0a_history_smoke(python, root, fixture)
        _p0a_test_values_smoke(python, root, fixture)
        smoke_execution_outcomes(python, root, fixture)
        _run_scope_smoke(python, root)
        _precheck_permission_smoke(python, root)
        _precheck_soft_gap_smoke(python, root)
        _trust_precheck_permission_smoke(python, root)
        _export_metadata_smoke(python, root)
        _p0b_output_schema_smoke(python, root)
        _p0b_output_lifecycle_smoke(python, root)
        _bridge_smoke(python, root)
        _run(
            [str(python), "-c", (
                "from pathlib import Path; from hate.store import LocalStore, StoreManifest; "
                "import json; from hate.store.compare import compare_bundles_direct; "
                "from hate.store.models import StoreManifest as ManifestModel; "
                "from hate.schema_resources import read_schema, validate_schema_instance; "
                "from hate.store.replay import replay_bundle, build_store_replay_report; "
                "from hate.store.doctor import diagnose_bundle, diagnose_full_store; "
                "from hate.store.atomic_write import is_complete_manifest; "
                "from hate.store.indexes import build_indexes_for_bundle; "
                "assert StoreManifest is ManifestModel; "
                "root = Path.cwd(); source = root / 'store-source.json'; "
                "payload = {'metadata': {'qegVersion': 'HATE/v1', 'runId': 'source-run', 'runAttempt': 1, "
                "'createdAt': '2026-09-10T00:00:00Z', 'profile': 'smoke', 'inputArtifacts': [], 'debugOnly': False}, "
                "'nodes': [{'id': 'test:smoke', 'kind': 'test', 'label': 'Smoke test', "
                "'data': {'status': 'passed'}, 'sourceRefs': []}], 'edges': [], "
                "'completeness': {'score': 1, 'partial': False, 'parserFailures': [], "
                "'unsupportedClaims': [], 'excludedArtifacts': []}}; "
                "source.write_text(json.dumps(payload), encoding='utf-8'); "
                "store = LocalStore(root / 'local-store'); "
                "hold = dict(status='none', reason='smoke', held_since='2026-09-10T00:00:00Z', authorized_by='smoke'); "
                "result = store.import_bundle(source, 'run-1', 'wheel-smoke', hold); "
                "assert result.success; reopened = LocalStore(store.store_root); "
                "assert reopened.read_bundle_by_run('run-1') == payload; "
                "assert reopened.verify_integrity('run-1')['integrity_ok']; "
                "assert store.import_bundle(source, 'run-2', 'wheel-smoke', hold).success; "
                "assert reopened.list_bundles_for_run('run-1') == [result.bundle_id]; "
                "assert is_complete_manifest(result.manifest_path); "
                "updated = reopened.update_legal_hold('run-1', 'active', 'review', 'smoke'); "
                "assert updated.to_dict()['import_status']['phase'] == 'completed'; "
                "saved_manifest = reopened.read_manifest('run-1').to_dict(); "
                "assert validate_schema_instance({**saved_manifest, 'import_status': {'phase': 'failed'}}, read_schema('store-manifest.schema.json')); "
                "assert saved_manifest == json.loads(result.manifest_path.read_text(encoding='utf-8')); "
                "manifest_bytes = result.manifest_path.read_bytes(); "
                "(store.store_root / 'indexes' / 'runs.jsonl').write_bytes(b''); "
                "assert len(build_indexes_for_bundle(store.store_root, result.manifest_path.parent, saved_manifest)) == 7; "
                "assert result.manifest_path.read_bytes() == manifest_bytes; "
                "assert reopened.verify_integrity('run-1')['integrity_ok']; "
                "build_indexes_for_bundle(store.store_root, store.store_root / 'runs' / 'run-2' / result.bundle_id, "
                "reopened.read_manifest_by_bundle(result.bundle_id, run_id='run-2').to_dict()); "
                "assert diagnose_full_store(reopened).findings == []; "
                "diagnosis = diagnose_bundle(reopened, result.bundle_id, run_id='run-1'); "
                "assert diagnosis.run_id == 'run-1' and diagnosis.healthy; "
                "assert diagnosis.diagnosis_hash == diagnosis.compute_hash(); "
                "assert 'diagnosed_at' not in diagnosis.to_dict(); "
                "assert diagnosis.to_dict(include_observation=True)['diagnosed_at'] == diagnosis.diagnosed_at; "
                "assert diagnosis.to_dict() == diagnose_bundle(reopened, result.bundle_id, run_id='run-1').to_dict(); "
                "replayed = replay_bundle(reopened, result.bundle_id, baseline_ref='run:run-2', run_id='run-1'); "
                "assert replayed.schema_compatible and replayed.integrity_ok and replayed.artifacts_replayed == 1; "
                "assert replayed.replay_hash == replayed.compute_hash(); "
                "comparison = compare_bundles_direct(reopened, result.bundle_id, result.bundle_id, run_id_a='run-1', run_id_b='run-2'); "
                "assert comparison.comparison_result.value == 'no_change'; "
                "assert comparison.comparison_hash == comparison.compute_hash(); "
                "report = build_store_replay_report(replayed, comparison_report=comparison, doctor_report=diagnosis); "
                "assert report['readiness_effect'] == 'pass'; "
                "assert build_store_replay_report(json.loads(json.dumps(report))) == report; "
                "other_diagnosis = diagnose_bundle(reopened, result.bundle_id, run_id='run-2'); "
                "assert build_store_replay_report(replayed, doctor_report=other_diagnosis)['readiness_effect'] == 'hard_dq'; "
                "assert 'replayed_at' not in report; "
                "assert report['baseline_resolution']['baseline_run_id'] == 'run-2'; "
                "saved_manifest['schema_versions']['store'] = '2.0.0'; "
                "result.manifest_path.write_text(json.dumps(saved_manifest), encoding='utf-8'); "
                "unsupported = replay_bundle(reopened, result.bundle_id, run_id='run-1'); "
                "assert unsupported.migration_hold and unsupported.artifacts_replayed == 0; "
                "unsupported_report = build_store_replay_report(unsupported, doctor_report=diagnose_bundle(reopened, result.bundle_id, run_id='run-1')); "
                "assert unsupported_report['readiness_effect'] == 'hold'; "
                "assert unsupported_report['corruption_findings'][0]['diagnostics']; "
                "assert not validate_schema_instance(unsupported_report, read_schema('store-replay-report.schema.json')); "
                "assert build_store_replay_report(json.loads(json.dumps(unsupported_report))) == unsupported_report"
            )], cwd=root,
        )
        _run(
            [
                str(python),
                "-c",
                "from hate.bridge.schemas import load_bridge_schema; "
                "from hate.p0a_schema import _load_hate_schema; "
                "assert _load_hate_schema('run.schema.json')['title']; "
                "assert load_bridge_schema('bridge-request')['title']",
            ],
            cwd=root,
        )
    return 0


def _cli_error_smoke(python: Path, root: Path) -> None:
    source = root / "invalid-input"
    source.mkdir()
    (source / "github-context.json").write_text("{", encoding="utf-8")
    bad_run = root / "invalid-run-input"
    bad_run.mkdir()
    (bad_run / "github-context.json").write_text(json.dumps({
        "repository": "smoke", "workflow": "ci", "job": "test", "run_id": "1",
        "run_attempt": True, "started_at": "2026-09-10T00:00:00Z",
    }), encoding="utf-8")
    bundle, report = root / "bundle.json", root / "report.json"
    bundle.write_text(json.dumps({"metadata": {"runId": "1", "runAttempt": 1}}), encoding="utf-8")
    report.write_text(json.dumps({"run_id": "2", "run_attempt": 1}), encoding="utf-8")
    cases = [
        (["p0a", "--input", str(source)], 1, "HATE-E-CLI:", "cannot read JSON input"),
        (["trust", "evaluate", "--bundle", str(source / "missing.json"),
          "--report", str(source / "report.json")], 2, "HATE-E-TRUST:", "not found"),
        (["p0a", "--input", str(bad_run)], 1, "HATE-E-CLI:", "run_attempt"),
        (["trust", "evaluate", "--bundle", str(bundle), "--report", str(report)],
         1, "HATE-E-TRUST:", "run_id mismatch"),
    ]
    for command, code, prefix, diagnostic in cases:
        result = subprocess.run(
            [str(python), "-m", "hate", *command, "--out", str(root / "error-output")],
            cwd=root, capture_output=True, text=True, timeout=30, check=False,
        )
        assert result.returncode == code, result.stderr
        assert result.stdout == ""
        assert prefix in result.stderr
        assert diagnostic in result.stderr
        assert "Traceback" not in result.stderr


def _trust_graph_smoke(python: Path, root: Path) -> None:
    bundle = {
        "metadata": {"qegVersion": "HATE/v1", "runId": "1", "runAttempt": 1,
                     "createdAt": "2026-09-10T00:00:00Z", "profile": "default", "inputArtifacts": [], "debugOnly": False},
        "nodes": [{"id": "risk:1", "kind": "risk", "label": "risk", "data": {}, "sourceRefs": ["risk.json"]}],
        "edges": [{"kind": "requires_test", "from": "risk:1", "to": "test:missing",
                   "traceability": {"sourceRefs": ["risk.json"], "confidence": "high", "assumptions": []}}],
        "completeness": {"score": 1, "partial": False, "parserFailures": [], "unsupportedClaims": [], "excludedArtifacts": []},
    }
    bundle_path, report_path, out = root / "graph-bundle.json", root / "graph-report.json", root / "graph-output"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    report_path.write_text(json.dumps({"run_id": "1", "run_attempt": 1}), encoding="utf-8")
    command = [str(python), "-m", "hate", "trust", "evaluate", "--bundle", str(bundle_path),
               "--report", str(report_path), "--out", str(out)]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(result.stdout)["trust_status"] == "partial"
    findings = json.loads((out / "doctor-report.json").read_text(encoding="utf-8"))["findings"]
    assert any(item.get("issue") == "unresolved_edge_endpoint" and item["blocking"] for item in findings)
    assert json.loads((out / "aete-score.json").read_text(encoding="utf-8"))["dimensions"]["traceability_lineage"] == 1
    score_before = (out / "aete-score.json").read_bytes()
    bundle["nodes"] = None
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    rejected = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False, timeout=30)
    assert rejected.returncode == 1 and rejected.stdout == ""
    assert "HATE-E-TRUST:" in rejected.stderr and "nodes" in rejected.stderr
    assert "Traceback" not in rejected.stderr
    assert (out / "aete-score.json").read_bytes() == score_before


def _trust_provenance_smoke(python: Path, root: Path) -> None:
    bundle_path, report_path, out = root / "provenance-bundle.json", root / "provenance-report.json", root / "provenance-output"
    bundle = json.loads((root / "graph-bundle.json").read_text(encoding="utf-8"))
    bundle["nodes"] = [{"id": "artifact:1", "kind": "evidence_artifact", "label": "trace",
                        "data": {"path": "trace.zip", "sha256": "a" * 64}, "sourceRefs": ["manifest.json"]}]
    bundle["edges"] = []
    report = {"run_id": "1", "run_attempt": 1, "commit_sha": "a" * 40}
    command = [str(python), "-m", "hate", "trust", "evaluate", "--bundle", str(bundle_path),
               "--report", str(report_path), "--out", str(out)]
    for invalid_time in (False, True):
        if invalid_time:
            bundle["metadata"]["createdAt"] = "2026-09-10T00:00:00+01:99"
        bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
        score = json.loads((out / "aete-score.json").read_text(encoding="utf-8"))
        assert score["dimensions"]["provenance_integrity"] == (1 if invalid_time else 3)
        assert score["weighted_score"] == (0.17 if invalid_time else 0.25)
        assert score["dimension_weights"]["provenance_integrity"] == 20
        assert score["aggregation_method"] == "weighted_mean"
        assert score["score_confidence"] == ("low" if invalid_time else "high")
        assert json.loads(result.stdout)["trust_status"] == ("partial" if invalid_time else "success")
        findings = json.loads((out / "doctor-report.json").read_text(encoding="utf-8"))["findings"]
        if invalid_time:
            assert any(item.get("issue") == "invalid_created_at" and item["blocking"] for item in findings)

    compare_out = root / "score-comparison"
    compare_command = [str(python), "-m", "hate", "compare", "--base", str(out), "--head", str(out),
                       "--out", str(compare_out)]
    compared = subprocess.run(compare_command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(compared.stdout)["compare_status"] == "stable"
    before = (compare_out / "compare-report.json").read_bytes()
    score["weighted_score"] = 0.999
    (out / "aete-score.json").write_text(json.dumps(score), encoding="utf-8")
    rejected = subprocess.run(compare_command, cwd=root, capture_output=True, text=True, check=False, timeout=30)
    assert rejected.returncode == 1 and rejected.stdout == ""
    assert "HATE-E-COMPARE:" in rejected.stderr and "weighted_score" in rejected.stderr and "replay" in rejected.stderr
    assert "Traceback" not in rejected.stderr
    assert (compare_out / "compare-report.json").read_bytes() == before


def _p0b_output_schema_smoke(python: Path, root: Path) -> None:
    source, out = root / "output-schema-input", root / "output-schema-export"
    shutil.copytree(root / "p0a-output", source / "p0a")
    path = source / "p0a/HATE-run.json"
    original = path.read_bytes()
    command = [str(python), "-m", "hate", "export", "qeg", "--fixture", str(source), "--out", str(out)]
    subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
    saved = {item.name: item.read_bytes() for item in out.iterdir() if item.is_file()}
    for value in ("", None, 42):
        record = json.loads(original)
        record["created_at"] = value
        path.write_text(json.dumps(record), encoding="utf-8")
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False, timeout=30)
        assert result.returncode == 1 and "Generated qeg-bundle.json failed schema validation" in result.stderr
        assert "metadata.createdAt" in result.stderr and "Traceback" not in result.stderr
        assert {item.name: item.read_bytes() for item in out.iterdir() if item.is_file()} == saved
    new_out = root / "output-schema-new"
    result = subprocess.run([*command[:-1], str(new_out)], cwd=root, capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 1 and not new_out.exists()


def _p0b_output_lifecycle_smoke(python: Path, root: Path) -> None:
    source, out = root / "output-lifecycle-input", root / "output-lifecycle-export"
    shutil.copytree(root / "p0a-output", source / "p0a")
    diff_path = source / "diff-risk-test.json"
    diff = {
        "risks": [{"risk_id": "lifecycle-risk", "severity": "high", "title": "Unexecuted test", "source_refs": ["spec.md"]}],
        "test_obligations": [{"risk_id": "lifecycle-risk", "expected_test_refs": ["tests/missing_lifecycle.py::test_missing"]}],
    }
    diff_path.write_text(json.dumps(diff), encoding="utf-8")
    command = [str(python), "-m", "hate", "export", "qeg", "--fixture", str(source), "--out", str(out)]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(result.stdout)["missing_executions"] == 1
    sidecars = {"risk-debt-register.json", "manual-bb-bridge-requests.jsonl"}
    assert all((out / name).is_file() for name in sidecars)
    (out / "operator-notes.md").write_bytes(b"keep")
    saved = {item.name: item.read_bytes() for item in out.iterdir() if item.is_file()}
    lifecycle = source / "risk-debt-lifecycle.json"
    for declaration, diagnostic in (({"age_days": "unknown"}, "$.items[0].age_days"),
                                    ({"owner": "\ud800"}, "Cannot serialize risk-debt-register.json")):
        lifecycle.write_text(json.dumps({"items": [{"risk_id": "lifecycle-risk", **declaration}]}), encoding="utf-8")
        for destination in (out, root / "output-lifecycle-new"):
            result = subprocess.run([*command[:-1], str(destination)], cwd=root, capture_output=True, text=True, check=False, timeout=30)
            assert result.returncode == 1 and diagnostic in result.stderr and "Traceback" not in result.stderr
            assert {item.name: item.read_bytes() for item in out.iterdir() if item.is_file()} == saved
            assert not (root / "output-lifecycle-new").exists()
    lifecycle.write_text('{"items": []}', encoding="utf-8")
    diff["test_obligations"] = []
    diff_path.write_text(json.dumps(diff), encoding="utf-8")
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
    status = json.loads(result.stdout)
    assert status["missing_executions"] == 0 and sidecars.isdisjoint(status["generated"])
    assert all(not (out / name).exists() for name in sidecars)
    assert (out / "operator-notes.md").read_bytes() == b"keep"


def _export_metadata_smoke(python: Path, root: Path) -> None:
    source, out = root / "export-metadata-input", root / "export-metadata-output"
    shutil.copytree(root / "p0a-output", source / "p0a")
    subprocess.run([str(python), "-m", "hate", "export", "qeg", "--fixture", str(source), "--out", str(out)],
                   cwd=root, capture_output=True, text=True, check=True, timeout=30)
    bp, rp = out / "qeg-bundle.json", out / "qeg-export-report.json"
    original_bundle, original_report = bp.read_bytes(), rp.read_bytes()
    common = ["--bundle", str(bp), "--report", str(rp)]
    trust = root / "export-metadata-trust"
    evaluate = [str(python), "-m", "hate", "trust", "evaluate", *common, "--out", str(trust)]
    for case in ("debug_only", "invalid_schema", "schema_errors", "partial", "unknown_status", "current_schema"):
        bundle, report = json.loads(original_bundle), json.loads(original_report)
        if case == "debug_only":
            bundle["metadata"]["debugOnly"] = True
        elif case == "invalid_schema":
            report["qeg_schema_compatibility"]["valid"] = False
        elif case == "schema_errors":
            report["qeg_schema_compatibility"]["errors"] = ["Original export validation failed"]
        elif case == "current_schema":
            bundle["metadata"]["qegVersion"] = "unknown"
        else:
            report["export_status"] = "partial" if case == "partial" else "failed"
        bp.write_text(json.dumps(bundle), encoding="utf-8")
        rp.write_text(json.dumps(report), encoding="utf-8")
        result = subprocess.run(evaluate, cwd=root, capture_output=True, text=True, check=True, timeout=30)
        status = json.loads(result.stdout)
        assert status["trust_status"] == "partial" and status["score_confidence"] == ("medium" if case == "partial" else "low")
        category = "schema" if case == "current_schema" else "export"
        for name, args in (("explain", ["explain", "--mode", "why-score-changed"]), ("recommend", ["recommend", "--gap", "all"])):
            subprocess.run([str(python), "-m", "hate", *args, *common, "--out", str(root / f"metadata-{name}")],
                           cwd=root, capture_output=True, text=True, check=True, timeout=30)
        reasons = json.loads((root / "metadata-explain/explain-report.json").read_text(encoding="utf-8"))["reason_tree"]
        assert any(item["category"] == category and item["blocking"] == (case != "partial") for item in reasons)
        actions = json.loads((root / "metadata-recommend/recommendation-report.json").read_text(encoding="utf-8"))["recommendations"]
        assert any(item.get("blocking") == (case != "partial") for item in actions)
    saved = (trust / "aete-score.json").read_bytes()
    bp.write_bytes(original_bundle)
    report = json.loads(original_report)
    report["qeg_schema_compatibility"]["valid"] = "false"
    rp.write_text(json.dumps(report), encoding="utf-8")
    result = subprocess.run(evaluate, cwd=root, capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 1 and "qeg_schema_compatibility" in result.stderr and "Traceback" not in result.stderr
    assert (trust / "aete-score.json").read_bytes() == saved


def _trust_precheck_permission_smoke(python: Path, root: Path) -> None:
    source, out = root / "trust-permission-input", root / "trust-permission-export"
    shutil.copytree(root / "p0a-output", source / "p0a")
    subprocess.run([str(python), "-m", "hate", "export", "qeg", "--fixture", str(source), "--out", str(out)],
                   cwd=root, capture_output=True, text=True, check=True, timeout=30)
    path = out / "qeg-bundle.json"
    original = path.read_bytes()
    trust = root / "trust-permission-result"
    common = ["--bundle", str(path), "--report", str(out / "qeg-export-report.json")]
    command = [str(python), "-m", "hate", "trust", "evaluate", *common, "--out", str(trust)]
    for changes in ({"decision": "ineligible"}, {"qeg_export_allowed": False}, {"exit_code": 2},
                    {"dq_hits": [{"code": "HATE-DQ-002"}]}, {"decision": "unknown"}):
        bundle = json.loads(original)
        next(node["data"] for node in bundle["nodes"] if node["id"].startswith("hate_precheck:")).update(changes)
        path.write_text(json.dumps(bundle), encoding="utf-8")
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
        status = json.loads(result.stdout)
        assert status["trust_status"] == "partial" and status["score_confidence"] == "low"
        doctor = json.loads((trust / "doctor-report.json").read_text(encoding="utf-8"))
        assert any(item["category"] == "precheck" and item["blocking"] for item in doctor["findings"])
    for name, args in (("explain", ["explain", "--mode", "why-excluded"]),
                       ("recommend", ["recommend", "--gap", "precheck_permission"])):
        subprocess.run([str(python), "-m", "hate", *args, *common, "--out", str(root / f"permission-{name}")],
                       cwd=root, capture_output=True, text=True, check=True, timeout=30)
    explain = json.loads((root / "permission-explain/explain-report.json").read_text(encoding="utf-8"))
    recommend = json.loads((root / "permission-recommend/recommendation-report.json").read_text(encoding="utf-8"))
    assert any(item.get("blocking") for item in explain["reason_tree"])
    assert any(item.get("blocking") for item in recommend["recommendations"])
    saved_score = (trust / "aete-score.json").read_bytes()
    bundle = json.loads(original)
    next(node["data"] for node in bundle["nodes"] if node["id"].startswith("hate_precheck:"))["qeg_export_allowed"] = "false"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 1 and "qeg_export_allowed" in result.stderr and "Traceback" not in result.stderr
    assert (trust / "aete-score.json").read_bytes() == saved_score


def _precheck_soft_gap_smoke(python: Path, root: Path) -> None:
    source, out = root / "soft-gap-input", root / "soft-gap-export"
    shutil.copytree(root / "p0a-output", source / "p0a")
    path = source / "p0a/precheck-decision.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    gap = {"gap_id": "missing_context", "message": "Optional context is unavailable", "profile": "strict"}
    record["payload"].update(decision="conditional", soft_gaps=[gap], reasons=[gap["message"]])
    path.write_text(json.dumps(record), encoding="utf-8")
    command = [str(python), "-m", "hate", "export", "qeg", "--fixture", str(source), "--out", str(out)]
    subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
    for name, args in (("trust", ["trust", "evaluate"]), ("explain", ["explain"]),
                       ("recommend", ["recommend", "--gap", "all"])):
        command = [str(python), "-m", "hate", *args, "--bundle", str(out / "qeg-bundle.json"),
                   "--report", str(out / "qeg-export-report.json"), "--out", str(root / f"soft-gap-{name}")]
        subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
    score = json.loads((root / "soft-gap-trust/aete-score.json").read_text(encoding="utf-8"))
    doctor = json.loads((root / "soft-gap-trust/doctor-report.json").read_text(encoding="utf-8"))
    explain = json.loads((root / "soft-gap-explain/explain-report.json").read_text(encoding="utf-8"))
    recommend = json.loads((root / "soft-gap-recommend/recommendation-report.json").read_text(encoding="utf-8"))
    assert score["score_confidence"] == "medium"
    finding = next(item for item in doctor["findings"] if item["category"] == "precheck")
    assert finding["gap"] == gap and not finding["blocking"]
    assert any(item.get("gap") == gap for item in explain["reason_tree"])
    assert any(item.get("gap") == gap for item in recommend["recommendations"])


def _precheck_permission_smoke(python: Path, root: Path) -> None:
    source, out = root / "precheck-input", root / "precheck-export"
    shutil.copytree(root / "p0a-output", source / "p0a")
    path = source / "p0a/precheck-decision.json"
    original = path.read_text(encoding="utf-8")
    command = [str(python), "-m", "hate", "export", "qeg", "--fixture", str(source), "--out", str(out)]
    subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
    saved = {item.name: item.read_bytes() for item in out.iterdir() if item.is_file()}
    for changes, code in (
        ({"decision": "ineligible", "exit_code": 2, "qeg_export_allowed": False}, 2),
        ({"qeg_export_allowed": False}, 2),
        ({"exit_code": 2}, 2),
        ({"dq_hits": [{"code": "HATE-DQ-002"}]}, 2),
        ({"decision": "unknown"}, 1),
        ({"qeg_export_allowed": "false"}, 1),
    ):
        record = json.loads(original)
        record["payload"].update(changes)
        path.write_text(json.dumps(record), encoding="utf-8")
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False, timeout=30)
        assert result.returncode == code and "Traceback" not in result.stderr
        assert {item.name: item.read_bytes() for item in out.iterdir() if item.is_file()} == saved
        if code == 1:
            assert "HATE-E-EXPORT" in result.stderr and "precheck-decision.json" in result.stderr
        else:
            assert "reason" in json.loads(result.stderr)


def _p0a_test_values_smoke(python: Path, root: Path, fixture: Path) -> None:
    source, run = root / "test-values-input", root / "test-values-run"
    shutil.copytree(fixture, source)
    pytest_report = {"tests": [{"nodeid": "tests/duration.py::test", "outcome": "passed",
                                "setup": {"duration": 0.01}, "call": {"duration": 0.25}, "teardown": {"duration": 0.02}}]}
    (source / "pytest-report.json").write_text(json.dumps(pytest_report), encoding="utf-8")
    for family in ("jest", "vitest"):
        report = {"testResults": [{"name": "duration.test.js", "assertionResults": [
            {"fullName": "duration test", "title": "test", "status": "passed", "duration": None},
        ]}]}
        (source / f"{family}-report.json").write_text(json.dumps(report), encoding="utf-8")
    command = [str(python), "-m", "hate", "p0a", "--input", str(source), "--out", str(run / "p0a")]
    subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
    subprocess.run([str(python), "-m", "hate", "export", "qeg", "--fixture", str(run), "--out", str(run / "export")],
                   cwd=root, capture_output=True, text=True, check=True, timeout=30)
    bundle = json.loads((run / "export/qeg-bundle.json").read_text(encoding="utf-8"))
    executions = [node for node in bundle["nodes"] if node["kind"] == "execution_evidence"]
    assert next(node for node in executions if "pytest:" in node["label"])["data"]["duration_ms"] == 280
    for family in ("jest", "vitest"):
        data = next(node for node in executions if f"{family}:" in node["label"])["data"]
        assert data["duration_ms"] == 0 and data["parser_diagnostics"][0]["code"] == "duration_not_reported"
    for family in ("junit", "pytest", "jest", "vitest"):
        path = source / ("junit.xml" if family == "junit" else f"{family}-report.json")
        original = path.read_bytes()
        if family == "junit":
            path.write_text('<testsuite><testcase name="test" time="oops"/></testsuite>', encoding="utf-8")
            diagnostic = ".time"
        else:
            changed = json.loads(original)
            row = changed["tests"][0] if family == "pytest" else changed["testResults"][0]["assertionResults"][0]
            row["nodeid" if family == "pytest" else "duration"] = None if family == "pytest" else False
            path.write_text(json.dumps(changed), encoding="utf-8")
            diagnostic = ".nodeid" if family == "pytest" else ".duration"
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False, timeout=30)
        assert result.returncode == 2 and "Traceback" not in result.stderr
        verdict = json.loads((run / "p0a/precheck-decision.json").read_text(encoding="utf-8"))["payload"]
        assert verdict["decision"] == "hard_dq" and verdict["qeg_export_allowed"] is False
        assert any(hit["code"] == "HATE-DQ-002" and diagnostic in hit["message"] for hit in verdict["dq_hits"])
        path.write_bytes(original)


def _run_scope_smoke(python: Path, root: Path) -> None:
    source = root / "run-scope-input"
    shutil.copytree(root / "p0a-output", source / "p0a")
    path = source / "p0a/HATE-test-results.ndjson"
    original = path.read_text(encoding="utf-8")
    out, trust = root / "run-scope-export", root / "run-scope-trust"
    export = [str(python), "-m", "hate", "export", "qeg", "--fixture", str(source), "--out", str(out)]
    subprocess.run(export, cwd=root, capture_output=True, text=True, check=True, timeout=30)
    saved_bundle = (out / "qeg-bundle.json").read_bytes()
    for field, value in (("run_id", "foreign-run"), ("run_attempt", 999), ("commit_sha", "b" * 40)):
        records = [json.loads(line) for line in original.splitlines()]
        records[0][field] = value
        path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
        result = subprocess.run(export, cwd=root, capture_output=True, text=True, check=False, timeout=30)
        assert result.returncode == 1 and field in result.stderr and "Traceback" not in result.stderr
        assert (out / "qeg-bundle.json").read_bytes() == saved_bundle
    bundle = json.loads(saved_bundle)
    report = json.loads((out / "qeg-export-report.json").read_text(encoding="utf-8"))
    assert bundle["metadata"]["commitSha"] == report["commit_sha"]
    command = [str(python), "-m", "hate", "trust", "evaluate", "--bundle", str(out / "qeg-bundle.json"),
               "--report", str(out / "qeg-export-report.json"), "--out", str(trust)]
    subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
    saved_score = (trust / "aete-score.json").read_bytes()
    for field, value in (("run_id", "foreign-run"), ("run_attempt", 999), ("commit_sha", "b" * 40)):
        changed = json.loads(saved_bundle)
        next(node for node in changed["nodes"] if node["kind"] == "execution_evidence")["data"][field] = value
        (out / "qeg-bundle.json").write_text(json.dumps(changed), encoding="utf-8")
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False, timeout=30)
        assert result.returncode == 1 and field in result.stderr and "Traceback" not in result.stderr
        assert (trust / "aete-score.json").read_bytes() == saved_score


def _p0a_history_smoke(python: Path, root: Path, fixture: Path) -> None:
    source = root / "adapter-history-source"
    shutil.copytree(fixture, source)
    run = root / "adapter-history-run"
    rows = [{"nodeid": "tests/test_auth.py::same", "outcome": status, "retry_index": index,
             "matrix": {"os": "linux"}, "shard_index": 0, "shard_total": 1}
            for index, status in enumerate(("failed", "passed"))]
    path = source / "pytest-report.json"
    path.write_text(json.dumps({"tests": rows}), encoding="utf-8")
    p0a = [str(python), "-m", "hate", "p0a", "--input", str(source), "--out", str(run / "p0a")]
    export = [str(python), "-m", "hate", "export", "qeg", "--fixture", str(run), "--out", str(run / "export")]
    trust = [str(python), "-m", "hate", "trust", "evaluate", "--bundle", str(run / "export/qeg-bundle.json"),
             "--report", str(run / "export/qeg-export-report.json"), "--out", str(run / "trust")]
    for command in (p0a, export, trust):
        subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
    records = [json.loads(line) for line in (run / "p0a/HATE-test-results.ndjson").read_text(encoding="utf-8").splitlines()]
    records = [record for record in records if record["payload"]["framework"] == "pytest"]
    assert len(records) == len({record["record_id"] for record in records}) == 2
    assert all(record["payload"]["matrix"] == {"os": "linux"} for record in records)
    aggregation = json.loads((run / "trust/retry-aggregation.json").read_text(encoding="utf-8"))
    assert aggregation["summary"]["flaky_count"] == 1
    rows = [{"nodeid": "tests/test_auth.py::same", "outcome": "passed", "reruns": 2, "flaky": True}]
    path.write_text(json.dumps({"tests": rows}), encoding="utf-8")
    for command in (p0a, export, trust):
        subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
    aggregation = json.loads((run / "trust/retry-aggregation.json").read_text(encoding="utf-8"))
    assert aggregation["summary"]["declared_flaky_count"] == aggregation["summary"]["inconclusive_count"] == 1
    score = json.loads((run / "trust/aete-score.json").read_text(encoding="utf-8"))
    assert score["dimensions"]["determinism_flakiness"] == 0 and score["score_confidence"] == "medium"
    rows[0]["retry_index"] = True
    path.write_text(json.dumps({"tests": rows}), encoding="utf-8")
    result = subprocess.run(p0a, cwd=root, capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 2 and "Traceback" not in result.stderr
    decision = json.loads((run / "p0a/precheck-decision.json").read_text(encoding="utf-8"))["payload"]
    assert decision["decision"] == "hard_dq" and not decision["qeg_export_allowed"]
    assert any("retry_index" in hit["message"] for hit in decision["dq_hits"])


def _p0b_history_smoke(python: Path, root: Path) -> None:
    fixture = root / "history-input"
    shutil.copytree(root / "p0a-output", fixture / "p0a")
    path = fixture / "p0a/HATE-test-results.ndjson"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    first = records[0]
    second = json.loads(json.dumps(first))
    first["payload"].update(status="failed", retry_index=0, matrix={"os": "linux"}, shard_index=0, shard_total=1)
    second["record_id"] += "-retry-1"
    second["payload"].update(status="passed", retry_index=1, matrix={"os": "linux"}, shard_index=0, shard_total=1)
    records.append(second)
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    out, trust = root / "history-export", root / "history-trust"
    command = [str(python), "-m", "hate", "export", "qeg", "--fixture", str(fixture), "--out", str(out)]
    subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
    bundle = json.loads((out / "qeg-bundle.json").read_text(encoding="utf-8"))
    assert len({node["id"] for node in bundle["nodes"]}) == len(bundle["nodes"])
    executions = [node for node in bundle["nodes"] if node["kind"] == "execution_evidence"]
    assert len(executions) == len(records)
    assert all(node["data"].get("source_record_id") for node in executions)
    subprocess.run([str(python), "-m", "hate", "trust", "evaluate", "--bundle", str(out / "qeg-bundle.json"),
                    "--report", str(out / "qeg-export-report.json"), "--out", str(trust)],
                   cwd=root, capture_output=True, text=True, check=True, timeout=30)
    aggregation = json.loads((trust / "retry-aggregation.json").read_text(encoding="utf-8"))
    assert aggregation["summary"]["flaky_count"] == 1
    score = json.loads((trust / "aete-score.json").read_text(encoding="utf-8"))
    assert score["dimensions"]["determinism_flakiness"] == 0
    before = (out / "qeg-bundle.json").read_bytes()
    records[0]["payload"]["retry_index"] = True
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    invalid = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False, timeout=30)
    assert invalid.returncode == 1 and "retry_index" in invalid.stderr and "Traceback" not in invalid.stderr
    assert (out / "qeg-bundle.json").read_bytes() == before


def _trust_retry_smoke(python: Path, root: Path) -> None:
    bundle = json.loads((root / "graph-bundle.json").read_text(encoding="utf-8"))
    bundle["nodes"] = [{"id": "test:1", "kind": "test", "label": "test",
                        "data": {"canonical_test_id": "pytest:tests/a.py::test_a"}, "sourceRefs": ["test.json"]}]
    bundle["edges"] = []
    for index, (system, status) in enumerate([("linux", "failed"), ("windows", "passed")]):
        node_id = f"execution:{index}"
        bundle["nodes"].append({"id": node_id, "kind": "execution_evidence", "label": "execution",
                                "data": {"status": status, "matrix": {"os": system}}, "sourceRefs": ["test.json"]})
        bundle["edges"].append({"kind": "evidenced_by", "from": "test:1", "to": node_id,
                                "traceability": {"sourceRefs": ["test.json"], "confidence": "high", "assumptions": []}})
    bundle["nodes"].append({"id": "artifact:trace", "kind": "evidence_artifact", "label": "trace",
                            "data": {"path": "trace.zip", "sha256": "a" * 64}, "sourceRefs": ["manifest.json"]})
    bundle["edges"].append({"kind": "evidenced_by", "from": "test:1", "to": "artifact:trace",
                            "traceability": {"sourceRefs": ["manifest.json"], "confidence": "high", "assumptions": []}})
    bundle_path, report_path, out = root / "retry-bundle.json", root / "retry-report.json", root / "retry-output"
    report_path.write_text(json.dumps({"run_id": "1", "run_attempt": 1, "commit_sha": "a" * 40}), encoding="utf-8")
    command = [str(python), "-m", "hate", "trust", "evaluate", "--bundle", str(bundle_path),
               "--report", str(report_path), "--out", str(out)]
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(result.stdout)["trust_status"] == "success"
    aggregation = json.loads((out / "retry-aggregation.json").read_text(encoding="utf-8"))
    assert aggregation["summary"]["aggregate_count"] == 2 and aggregation["summary"]["flaky_count"] == 0
    for index, node in enumerate([node for node in bundle["nodes"] if node["kind"] == "execution_evidence"], 1):
        node["data"] = {"status": "passed", "shard_index": index, "shard_total": 2}
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(result.stdout)["trust_status"] == "partial"
    aggregation = json.loads((out / "retry-aggregation.json").read_text(encoding="utf-8"))
    assert aggregation["aggregates"][0]["aggregate_status"] == "inconclusive"
    score = json.loads((out / "aete-score.json").read_text(encoding="utf-8"))
    assert score["dimensions"]["determinism_flakiness"] == 1 and score["score_confidence"] == "medium"
    before = (out / "aete-score.json").read_bytes()
    bundle["nodes"][1]["data"]["retry_index"] = True
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    rejected = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False, timeout=30)
    assert rejected.returncode == 1 and rejected.stdout == ""
    assert "retry_index" in rejected.stderr and "Traceback" not in rejected.stderr
    assert (out / "aete-score.json").read_bytes() == before


def _bridge_smoke(python: Path, root: Path) -> None:
    history = root / "history source #1.jsonl"
    history.write_text("", encoding="utf-8")
    store = root / "new store"
    command = [
        str(python), "-m", "hate", "real-repo", "history-ingest",
        "--history", str(history), "--store", str(store), "--bridge-provider", "handoff",
    ]
    _run(command, cwd=root)
    requests = list((root / ".hate" / "bridge").glob("*/bridge-request.json"))
    assert len(requests) == 1
    request = json.loads(requests[0].read_text(encoding="utf-8"))
    assert request["path_arguments"]["store"] == {
        "path": str(store.resolve()), "role": "destination", "exists": False,
    }
    assert request["sourceRefs"] == [history.resolve().as_uri()]
    assert [ref["argument"] for ref in request["input_refs"]] == ["history"]
    assert not store.exists()
    _run(command, cwd=root)
    assert list((root / ".hate" / "bridge").glob("*/bridge-request.json")) == requests
    assert json.loads(requests[0].read_text(encoding="utf-8")) == request


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
