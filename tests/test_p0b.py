"""Tests for P0b QEG export."""

from __future__ import annotations

import json
from pathlib import Path

from hate.p0b import ExportError, export_qeg


def test_p0b_export_minimal_fixture() -> None:
    """P0b export generates all required artifacts from minimal fixture."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/input")
    out_dir = Path("fixtures/golden/p0b-qeg-minimal/test-output")

    result = export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)

    assert result["export_status"] == "success"
    assert result["exit_code"] == 0
    assert "qeg-bundle.json" in result["generated"]
    assert "evidence-map.json" in result["generated"]
    assert "qeg-export-report.json" in result["generated"]
    assert "qeg-export-summary.md" in result["generated"]
    assert result["publish_gate_override"] is False

    # Verify generated files exist
    assert (out_dir / "qeg-bundle.json").exists()
    assert (out_dir / "evidence-map.json").exists()
    assert (out_dir / "qeg-export-report.json").exists()
    assert (out_dir / "qeg-export-summary.md").exists()

    # Verify qeg-bundle.json structure
    bundle = json.loads((out_dir / "qeg-bundle.json").read_text())
    assert bundle["metadata"]["qegVersion"] == "HATE/v1"
    assert bundle["metadata"]["runId"] == "1001"
    assert len(bundle["nodes"]) >= 2  # At least gate_verdict + run
    assert len(bundle["edges"]) >= 1  # At least one edge

    # Verify gate_verdict node exists
    precheck_nodes = [n for n in bundle["nodes"] if n["kind"] == "gate_verdict"]
    assert len(precheck_nodes) == 1
    assert precheck_nodes[0]["data"]["decision"] == "eligible"
    assert precheck_nodes[0]["data"]["qeg_export_allowed"] is True

    # Verify evidence-map.json structure
    ev_map = json.loads((out_dir / "evidence-map.json").read_text())
    assert ev_map["schema_version"] == "HATE/v1"
    assert ev_map["run_id"] == "1001"
    assert "risks" in ev_map
    assert "tests" in ev_map
    assert "evidence" in ev_map
    assert "links" in ev_map
    assert "gaps" in ev_map

    # Verify qeg-export-report.json structure
    report = json.loads((out_dir / "qeg-export-report.json").read_text())
    assert report["schema_version"] == "HATE/v1"
    assert report["export_status"] == "success"
    assert report["publish_gate_override"] is False
    assert "completeness" in report

    # Verify summary.md is public-safe (no absolute paths leaked)
    summary = (out_dir / "qeg-export-summary.md").read_text()
    assert "publish_gate_override=false" in summary
    assert "C:\\Users" not in summary  # No absolute Windows paths


def test_p0b_export_hard_dq_raises() -> None:
    """P0b export raises ExportError when precheck decision is hard_dq."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/input")
    out_dir = Path("fixtures/golden/p0b-qeg-minimal/test-hard-dq-output")

    # Modify precheck-decision.json to hard_dq
    p0a_dir = fixture_dir / "p0a"
    precheck_path = p0a_dir / "precheck-decision.json"
    original_content = precheck_path.read_text()
    original = json.loads(original_content)

    # Write hard_dq version (deep copy via json roundtrip)
    hard_dq_json = json.dumps(original, indent=2)
    hard_dq_data = json.loads(hard_dq_json)
    hard_dq_data["payload"]["decision"] = "hard_dq"
    hard_dq_data["payload"]["qeg_export_allowed"] = False
    precheck_path.write_text(json.dumps(hard_dq_data, indent=2))

    try:
        export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)
        assert False, "Expected ExportError"
    except ExportError as exc:
        assert exc.exit_code == 2
        assert "hard_dq" in str(exc).lower()
    finally:
        # Restore original content exactly
        precheck_path.write_text(original_content)


def test_p0b_export_missing_artifacts_raises() -> None:
    """P0b export raises ExportError when required P0a artifacts are missing."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/input")
    out_dir = Path("fixtures/golden/p0b-qeg-minimal/test-missing-output")

    # Temporarily remove required artifact
    p0a_dir = fixture_dir / "p0a"
    run_path = p0a_dir / "HATE-run.json"
    original = run_path.read_text()
    run_path.unlink()

    try:
        export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)
        assert False, "Expected ExportError"
    except ExportError as exc:
        assert exc.exit_code == 2
        assert "Missing" in str(exc)
        assert "HATE-run.json" in str(exc)
    finally:
        # Restore original
        run_path.write_text(original)


def test_p0b_cli_export_qeg() -> None:
    """CLI `hate export qeg` generates expected artifacts."""
    import subprocess

    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/input")
    out_dir = Path("fixtures/golden/p0b-qeg-minimal/test-cli-output")

    result = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "export", "qeg",
            "--fixture", str(fixture_dir),
            "--out", str(out_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["export_status"] == "success"
    assert len(output["generated"]) >= 4