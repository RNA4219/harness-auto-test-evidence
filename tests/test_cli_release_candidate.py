"""Tests for CLI release candidate command."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from hate.cli import main
from hate.release import assemble_release_candidate_pack, RELEASE_PACK_REQUIRED_REPORT_TYPES

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "release" / "candidate-pack"


def test_cli_release_candidate_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "hate", "release", "candidate", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--readiness" in result.stdout
    assert "--out" in result.stdout
    assert "--dry-run" in result.stdout


def test_cli_release_candidate_from_fixture() -> None:
    """Test release candidate pack generation from fixture input."""
    fixture = json.loads((FIXTURE_ROOT / "all-green" / "fixture.json").read_text(encoding="utf-8"))
    input_data = fixture["input"]

    # Create a temporary readiness directory with reports
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        readiness_dir = Path(tmp) / "readiness"
        readiness_dir.mkdir(parents=True, exist_ok=True)

        # Write each report to the readiness directory
        for report in input_data.get("reports", []):
            report_path = readiness_dir / f"{report['record_type']}.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        out_dir = Path(tmp) / "out"

        # Run CLI command
        exit_code = main([
            "release", "candidate",
            "--readiness", str(readiness_dir),
            "--out", str(out_dir),
            "--release-id", "rc-test",
            "--source-version", "test-1.0",
            "--dry-run",
        ])

        assert exit_code == 0
        assert (out_dir / "release-candidate-pack.json").exists()

        pack = json.loads((out_dir / "release-candidate-pack.json").read_text(encoding="utf-8"))
        assert pack["schema_version"] == "HATE/v1"
        assert pack["record_type"] == "release-candidate-pack"
        assert pack["release_id"] == "rc-test"
        assert pack["source_version"] == "test-1.0"


def test_cli_release_candidate_blocked_without_dry_run() -> None:
    """Test that blocked release candidate pack raises error without --dry-run."""
    fixture = json.loads((FIXTURE_ROOT / "missing-required-report" / "fixture.json").read_text(encoding="utf-8"))
    input_data = fixture["input"]

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        readiness_dir = Path(tmp) / "readiness"
        readiness_dir.mkdir(parents=True, exist_ok=True)

        # Write reports (missing support-ops-report)
        for report in input_data.get("reports", []):
            report_path = readiness_dir / f"{report['record_type']}.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        out_dir = Path(tmp) / "out"

        # Run CLI command without --dry-run should fail
        exit_code = main([
            "release", "candidate",
            "--readiness", str(readiness_dir),
            "--out", str(out_dir),
            "--release-id", "rc-blocked",
        ])

        assert exit_code == 3  # Blocked exit code
        assert (out_dir / "release-candidate-pack.json").exists()


def test_cli_release_candidate_dry_run_succeeds_even_blocked() -> None:
    """Test that --dry-run succeeds even when pack is blocked."""
    fixture = json.loads((FIXTURE_ROOT / "missing-required-report" / "fixture.json").read_text(encoding="utf-8"))
    input_data = fixture["input"]

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        readiness_dir = Path(tmp) / "readiness"
        readiness_dir.mkdir(parents=True, exist_ok=True)

        for report in input_data.get("reports", []):
            report_path = readiness_dir / f"{report['record_type']}.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        out_dir = Path(tmp) / "out"

        exit_code = main([
            "release", "candidate",
            "--readiness", str(readiness_dir),
            "--out", str(out_dir),
            "--release-id", "rc-blocked",
            "--dry-run",
        ])

        assert exit_code == 0
        pack = json.loads((out_dir / "release-candidate-pack.json").read_text(encoding="utf-8"))
        assert pack["verdict"] == "blocked"


def test_cli_release_candidate_missing_readiness_dir() -> None:
    """Test that missing readiness directory raises error."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "out"

        exit_code = main([
            "release", "candidate",
            "--readiness", "/nonexistent/path",
            "--out", str(out_dir),
            "--dry-run",
        ])

        assert exit_code == 2


def test_cli_release_candidate_output_includes_summary() -> None:
    """Test that CLI output includes summary fields."""
    fixture = json.loads((FIXTURE_ROOT / "all-green" / "fixture.json").read_text(encoding="utf-8"))
    input_data = fixture["input"]

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        readiness_dir = Path(tmp) / "readiness"
        readiness_dir.mkdir(parents=True, exist_ok=True)

        for report in input_data.get("reports", []):
            report_path = readiness_dir / f"{report['record_type']}.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        out_dir = Path(tmp) / "out"

        # Capture stdout
        from io import StringIO
        import contextlib

        stdout_capture = StringIO()
        with contextlib.redirect_stdout(stdout_capture):
            exit_code = main([
                "release", "candidate",
                "--readiness", str(readiness_dir),
                "--out", str(out_dir),
                "--release-id", "rc-summary",
                "--dry-run",
            ])

        assert exit_code == 0
        output = json.loads(stdout_capture.getvalue())
        assert "generated" in output
        assert "verdict" in output
        assert "release_ready" in output
        assert "blocker_count" in output