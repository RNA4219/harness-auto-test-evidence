"""Tests for connecting expansion reports to CLI and release-pack inputs."""

from __future__ import annotations

import json
from pathlib import Path

from hate.cli import main
from hate.expansion_runner import EXPANSION_REPORT_TYPES, run_expansion_suite
from hate.release import assemble_release_candidate_pack


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion"


def test_positive_expansion_suite_generates_release_pack_reports(tmp_path: Path) -> None:
    manifest = run_expansion_suite(
        fixtures_root=FIXTURES,
        out_dir=tmp_path,
        case_kind="positive",
    )

    assert manifest["overall_status"] == "pass"
    assert manifest["missing_areas"] == []
    assert any(path.endswith("impact-analysis-uat-report.json") for path in manifest["generated_uat_reports"])
    assert set(manifest["report_types"]) == set(EXPANSION_REPORT_TYPES)
    for record_type in EXPANSION_REPORT_TYPES:
        report_path = tmp_path / f"{record_type}.json"
        assert report_path.exists(), f"missing generated report: {record_type}"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["record_type"] == record_type
    uat_report = json.loads((tmp_path / "impact-analysis-uat-report.json").read_text(encoding="utf-8"))
    assert uat_report["record_type"] == "expansion-uat-report"
    assert uat_report["gap_id"] == "HATE-GAP-049"
    assert uat_report["overall_status"] == "pass"


def test_generated_expansion_reports_satisfy_release_required_inputs(tmp_path: Path) -> None:
    run_expansion_suite(
        fixtures_root=FIXTURES,
        out_dir=tmp_path,
        case_kind="positive",
    )
    reports = [
        json.loads((tmp_path / f"{record_type}.json").read_text(encoding="utf-8"))
        for record_type in EXPANSION_REPORT_TYPES
    ]

    pack = assemble_release_candidate_pack({
        "release_id": "rc-expansion-connected",
        "source_version": "test",
        "required_reports": list(EXPANSION_REPORT_TYPES),
        "reports": reports,
    })

    assert pack["missing_required_reports"] == []
    assert pack["verdict"] == "ready"
    assert pack["summary"]["release_ready"] is True


def test_expansion_cli_run_writes_manifest_and_reports(tmp_path: Path) -> None:
    exit_code = main([
        "expansion",
        "run",
        "--fixtures-root",
        str(FIXTURES),
        "--out",
        str(tmp_path),
        "--case-kind",
        "positive",
        "--area",
        "impact-analysis",
    ])

    assert exit_code == 0
    manifest = json.loads((tmp_path / "expansion-run-report.json").read_text(encoding="utf-8"))
    assert manifest["overall_status"] == "pass"
    assert manifest["report_types"] == ["impact-analysis-report"]
    assert (tmp_path / "impact-analysis-report.json").exists()
    assert (tmp_path / "impact-analysis-uat-report.json").exists()
