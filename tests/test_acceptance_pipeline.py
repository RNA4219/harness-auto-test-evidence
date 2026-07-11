"""End-to-end acceptance tests for HATE itself."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.e2e
def test_hate_cli_acceptance_pipeline(tmp_path: Path) -> None:
    """Run the HATE CLI from P0a through P2/P3 and verify advisory boundaries."""
    p0a_out = tmp_path / "p0a"
    p0b_fixture = tmp_path / "p0b-input"
    p0b_out = tmp_path / "p0b"
    trust_out = tmp_path / "trust"
    workflow_out = tmp_path / "workflow"
    product_out = tmp_path / "product"

    p0a = run_hate(
        "p0a",
        "--input",
        str(ROOT / "fixtures/golden/p0a-minimal/input"),
        "--out",
        str(p0a_out),
        "--source-version",
        "acceptance",
    )
    assert p0a["decision"] == "eligible"

    p0b_fixture.mkdir()
    shutil.copytree(p0a_out, p0b_fixture / "p0a")
    shutil.copy2(ROOT / "fixtures/golden/p0b-qeg-minimal/input/diff-risk-test.json", p0b_fixture / "diff-risk-test.json")

    p0b = run_hate("export", "qeg", "--fixture", str(p0b_fixture), "--out", str(p0b_out))
    assert p0b["export_status"] == "success"
    assert p0b["missing_executions"] == 0
    assert p0b["publish_gate_override"] is False
    bundle = read_json(p0b_out / "qeg-bundle.json")
    assert any(node["kind"] == "evidence_strength" for node in bundle["nodes"])
    assert any(item["kind"] == "HATE-evidence-strength" for item in bundle["metadata"]["inputArtifacts"])

    trust = run_hate(
        "trust",
        "evaluate",
        "--bundle",
        str(p0b_out / "qeg-bundle.json"),
        "--report",
        str(p0b_out / "qeg-export-report.json"),
        "--out",
        str(trust_out),
    )
    assert trust["trust_status"] == "success"
    assert trust["doctor_findings"] == 0
    assert trust["publish_gate_override"] is False

    workflow = run_hate(
        "workflow",
        "map",
        "--bundle",
        str(p0b_out / "qeg-bundle.json"),
        "--report",
        str(p0b_out / "qeg-export-report.json"),
        "--trust",
        str(trust_out),
        "--out",
        str(workflow_out),
    )
    assert workflow["workflow_status"] == "success"
    assert workflow["publish_gate_override"] is False
    assert workflow["release_gate_override"] is False
    assert workflow["shipyard_state_override"] is False

    product = run_hate(
        "product",
        "readiness",
        "--bundle",
        str(p0b_out / "qeg-bundle.json"),
        "--trust",
        str(trust_out),
        "--workflow",
        str(workflow_out),
        "--out",
        str(product_out),
    )
    assert product["product_status"] == "go"
    assert product["prg_coverage"] == "7/7"
    assert product["publish_gate_override"] is False
    assert product["release_gate_override"] is False

    product_report = read_json(product_out / "product-readiness-report.json")
    assert product_report["summary"]["degraded_by_doctor_findings"] is False
    assert product_report["summary"]["degraded_by_unverified_acceptance"] is False
    assert product_report["boundaries"]["hosted_saas_claim"] is False

    assert not find_forbidden_text(tmp_path, ["C:/Users", "C:\\Users"])
    assert not any(path.name.startswith("test-output") or path.name.startswith("test-cli-output") for path in tmp_path.rglob("*"))


def test_hate_acceptance_detects_product_hold_when_required_input_is_missing(tmp_path: Path) -> None:
    """Product readiness must not stay green when upstream advisory artifacts are missing."""
    trust_dir = tmp_path / "trust"
    workflow_dir = tmp_path / "workflow"
    product_out = tmp_path / "product"
    shutil.copytree(ROOT / "fixtures/golden/p1a-trust-minimal/expected", trust_dir)
    shutil.copytree(ROOT / "fixtures/golden/p1b-workflow-minimal/expected", workflow_dir)
    (trust_dir / "adapter-conformance-report.json").unlink()

    product = run_hate(
        "product",
        "readiness",
        "--bundle",
        str(ROOT / "fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json"),
        "--trust",
        str(trust_dir),
        "--workflow",
        str(workflow_dir),
        "--out",
        str(product_out),
    )

    report = read_json(product_out / "product-readiness-report.json")
    assert product["product_status"] == "hold"
    assert report["summary"]["degraded_by_input_artifacts"] is True
    assert report["evidence_summary"]["missing_input_artifacts"][0]["artifact_ref"] == "adapter-conformance-report.json"


def run_hate(*args: str) -> dict[str, Any]:
    env = os.environ.copy()
    pythonpath = str(ROOT / "src")
    env["PYTHONPATH"] = pythonpath if not env.get("PYTHONPATH") else pythonpath + os.pathsep + env["PYTHONPATH"]
    result = subprocess.run(
        [sys.executable, "-m", "hate", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_forbidden_text(root: Path, needles: list[str]) -> list[Path]:
    hits: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(needle in text for needle in needles):
            hits.append(path)
    return hits
