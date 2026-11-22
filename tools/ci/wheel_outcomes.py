"""インストール済みwheelで未実行状態と実行要件の接続を確認する。"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def smoke_execution_outcomes(python: Path, root: Path, fixture: Path) -> None:
    source, run = root / "outcome-source", root / "outcome-run"
    shutil.copytree(fixture, source)
    run.mkdir()
    assertion = {"fullName": "state test", "title": "test", "status": "passed", "wouldRun": True, "duration": None}
    native = {"testResults": [{"name": "state.test.js", "assertionResults": [assertion]}]}
    native_path = source / "jest-report.json"
    _write(native_path, native)
    _write(run / "diff-risk-test.json", {
        "risks": [{"risk_id": "state-risk", "severity": "high", "title": "Required test", "source_refs": ["spec.md"]}],
        "test_obligations": [{"risk_id": "state-risk", "expected_test_refs": ["jest:state.test.js::state test"],
                              "required_evidence_kinds": ["execution"]}],
    })
    p0a = ["p0a", "--input", str(source), "--out", str(run / "p0a")]
    export = ["export", "qeg", "--fixture", str(run), "--out", str(run / "export")]
    bp, rp = run / "export/qeg-bundle.json", run / "export/qeg-export-report.json"
    trust = ["trust", "evaluate", "--bundle", str(bp), "--report", str(rp), "--out", str(run / "trust")]
    before = native_path.read_bytes()
    _invoke(python, root, p0a)
    result = _invoke(python, root, export)
    assert result["export_status"] == "partial" and result["missing_executions"] == 1
    bundle = _read(bp)
    data = next(node["data"] for node in bundle["nodes"] if node["kind"] == "execution_evidence"
                and node["label"].endswith("jest:state.test.js::state test"))
    assert data["source_status"] == "passed" and data["status"] == "inconclusive" and data["wouldRun"] is True
    assert {item["code"] for item in data["parser_diagnostics"]} == {"test_not_executed", "duration_not_reported"}
    assert _invoke(python, root, trust)["score_confidence"] == "medium"
    assert _read(run / "trust/aete-score.json")["dimensions"]["traceability_lineage"] == 3
    assert native_path.read_bytes() == before
    assert (run / "export/risk-debt-register.json").exists()
    assert (run / "export/manual-bb-bridge-requests.jsonl").exists()

    # collection-onlyの宣言は、既存bundle内のpassedにも優先する。
    for node in bundle["nodes"]:
        if node["kind"] == "execution_evidence" and node["data"].get("wouldRun") is True:
            node["data"]["status"] = "passed"
    _write(bp, bundle)
    assert _invoke(python, root, trust)["score_confidence"] == "medium"
    assert any(item["issue"] == "test_not_executed" for item in _read(run / "trust/doctor-report.json")["findings"])

    assertion["wouldRun"] = False
    _write(native_path, native)
    _invoke(python, root, p0a)
    result = _invoke(python, root, export)
    assert result["export_status"] == "success" and result["missing_executions"] == 0
    assert not (run / "export/risk-debt-register.json").exists()
    assert not (run / "export/manual-bb-bridge-requests.jsonl").exists()
    assertion["wouldRun"] = "false"
    _write(native_path, native)
    invalid = subprocess.run([str(python), "-m", "hate", *p0a], cwd=root, capture_output=True,
                             text=True, check=False, timeout=30)
    assert invalid.returncode == 2 and "Traceback" not in invalid.stdout + invalid.stderr
    decision = _read(run / "p0a/precheck-decision.json")["payload"]
    assert decision["qeg_export_allowed"] is False
    assert any(hit["code"] == "HATE-DQ-002" and "wouldRun" in hit["message"] for hit in decision["dq_hits"])


def _invoke(python: Path, root: Path, arguments: list[str]) -> dict[str, Any]:
    result = subprocess.run([str(python), "-m", "hate", *arguments], cwd=root, capture_output=True,
                            text=True, check=True, timeout=30)
    return json.loads(result.stdout)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")
