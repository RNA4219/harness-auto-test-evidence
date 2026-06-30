"""Tests for HATE gap closure report generation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.cli import main
from hate.gap_closure import generate_gap_closure_report


ROOT = Path(__file__).resolve().parents[1]


def test_generate_gap_closure_report_marks_all_26_gaps_uat_ready(tmp_path: Path) -> None:
    report = generate_gap_closure_report(ROOT, tmp_path, source_version="test")

    assert report["record_type"] == "gap-closure-report"
    assert report["overall_status"] == "checker_ready"
    assert report["summary"]["gap_count"] == 26
    assert report["summary"]["checker_ready_count"] == 0
    assert report["summary"]["implemented_count"] == 26
    assert report["summary"]["hold_count"] == 0
    assert report["summary"]["fixture_ref_count"] == 76
    assert report["summary"]["behavior_checked_count"] == 76
    assert report["summary"]["uat_report_count"] == 26
    assert report["summary"]["workflow_alignment_status"] == "uat_ready"
    assert report["findings"] == []
    assert report["workflow_alignment"]["status"] == "uat_ready"
    assert {check["check_id"] for check in report["workflow_alignment"]["checks"]} == {
        "workflow_task_seed_sync",
        "workflow_acceptance_records",
        "workflow_acceptance_index",
        "workflow_completion_trace",
        "workflow_birdseye_invariants",
        "workflow_evidence_minimum_fields",
        "workflow_coverage_policy",
        "workflow_priority_score_policy",
        "workflow_metrics_kpi_policy",
        "workflow_feature_detection_policy",
        "workflow_security_release_evidence_policy",
    }
    task_seed_sync = next(
        check for check in report["workflow_alignment"]["checks"] if check["check_id"] == "workflow_task_seed_sync"
    )
    assert task_seed_sync["task_seed_count"] == 26
    completion_trace = next(
        check for check in report["workflow_alignment"]["checks"] if check["check_id"] == "workflow_completion_trace"
    )
    assert completion_trace["implemented_trace_count"] == 26

    gap_ids = {gap["gap_id"] for gap in report["gaps"]}
    assert gap_ids == {f"HATE-GAP-{index:03d}" for index in range(1, 27)}
    assert all(gap["positive_fixture_count"] >= 1 for gap in report["gaps"])
    assert all(gap["negative_fixture_count"] >= 1 for gap in report["gaps"])
    assert all(gap["behavior_checked_count"] >= 2 for gap in report["gaps"])
    assert all(len(gap["uat_reports"]) == 1 for gap in report["gaps"])
    gap_001 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-001")
    assert gap_001["status"] == "implemented"
    gap_002 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-002")
    assert gap_002["status"] == "implemented"
    gap_003 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-003")
    assert gap_003["status"] == "implemented"
    assert gap_003["behavior_checked_count"] == 5
    gap_004 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-004")
    assert gap_004["status"] == "implemented"
    assert gap_004["behavior_checked_count"] == 5
    gap_005 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-005")
    assert gap_005["status"] == "implemented"
    assert gap_005["behavior_checked_count"] == 6
    gap_006 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-006")
    assert gap_006["status"] == "implemented"
    assert gap_006["positive_fixture_count"] == 1
    assert gap_006["negative_fixture_count"] == 5
    assert gap_006["behavior_checked_count"] == 6
    gap_007 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-007")
    assert gap_007["status"] == "implemented"
    assert gap_007["positive_fixture_count"] == 1
    assert gap_007["negative_fixture_count"] == 1
    assert gap_007["behavior_checked_count"] == 2
    gap_008 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-008")
    assert gap_008["status"] == "implemented"
    assert gap_008["positive_fixture_count"] == 1
    assert gap_008["negative_fixture_count"] == 1
    assert gap_008["behavior_checked_count"] == 2
    gap_009 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-009")
    assert gap_009["status"] == "implemented"
    assert gap_009["positive_fixture_count"] == 1
    assert gap_009["negative_fixture_count"] == 1
    assert gap_009["behavior_checked_count"] == 2
    gap_010 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-010")
    assert gap_010["status"] == "implemented"
    assert gap_010["positive_fixture_count"] == 1
    assert gap_010["negative_fixture_count"] == 1
    assert gap_010["behavior_checked_count"] == 2
    gap_011 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-011")
    assert gap_011["status"] == "implemented"
    assert gap_011["positive_fixture_count"] == 1
    assert gap_011["negative_fixture_count"] == 1
    assert gap_011["behavior_checked_count"] == 2
    gap_012 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-012")
    assert gap_012["status"] == "implemented"
    assert gap_012["positive_fixture_count"] == 1
    assert gap_012["negative_fixture_count"] == 1
    assert gap_012["behavior_checked_count"] == 2
    gap_013 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-013")
    assert gap_013["status"] == "implemented"
    assert gap_013["positive_fixture_count"] == 1
    assert gap_013["negative_fixture_count"] == 1
    assert gap_013["behavior_checked_count"] == 2
    gap_014 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-014")
    assert gap_014["status"] == "implemented"
    assert gap_014["positive_fixture_count"] == 1
    assert gap_014["negative_fixture_count"] == 1
    assert gap_014["behavior_checked_count"] == 2
    gap_015 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-015")
    assert gap_015["status"] == "implemented"
    assert gap_015["positive_fixture_count"] == 1
    assert gap_015["negative_fixture_count"] == 1
    assert gap_015["behavior_checked_count"] == 2
    gap_016 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-016")
    assert gap_016["status"] == "implemented"
    assert gap_016["positive_fixture_count"] == 1
    assert gap_016["negative_fixture_count"] == 1
    assert gap_016["behavior_checked_count"] == 2
    gap_017 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-017")
    assert gap_017["status"] == "implemented"
    assert gap_017["positive_fixture_count"] == 1
    assert gap_017["negative_fixture_count"] == 1
    assert gap_017["behavior_checked_count"] == 2
    gap_018 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-018")
    assert gap_018["status"] == "implemented"
    assert gap_018["positive_fixture_count"] == 1
    assert gap_018["negative_fixture_count"] == 1
    assert gap_018["behavior_checked_count"] == 2
    gap_019 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-019")
    assert gap_019["status"] == "implemented"
    assert gap_019["positive_fixture_count"] == 1
    assert gap_019["negative_fixture_count"] == 1
    assert gap_019["behavior_checked_count"] == 2
    gap_020 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-020")
    assert gap_020["status"] == "implemented"
    assert gap_020["positive_fixture_count"] == 6
    assert gap_020["negative_fixture_count"] == 6
    assert gap_020["behavior_checked_count"] == 12
    assert gap_020["implementation_evidence"]["runtime_module"] == "src/hate/product_e2e.py"
    assert gap_020["implementation_evidence"]["tests"] == ["tests/test_product_e2e.py"]
    gap_021 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-021")
    assert gap_021["status"] == "implemented"
    assert gap_021["positive_fixture_count"] == 1
    assert gap_021["negative_fixture_count"] == 1
    assert gap_021["behavior_checked_count"] == 2
    assert gap_021["implementation_evidence"]["runtime_module"] == "src/hate/workflow_task_seed.py"
    assert gap_021["implementation_evidence"]["tests"] == ["tests/test_workflow_task_seed.py"]
    gap_022 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-022")
    assert gap_022["status"] == "implemented"
    assert gap_022["positive_fixture_count"] == 1
    assert gap_022["negative_fixture_count"] == 1
    assert gap_022["behavior_checked_count"] == 2
    assert gap_022["implementation_evidence"]["runtime_module"] == "src/hate/workflow_acceptance.py"
    assert gap_022["implementation_evidence"]["tests"] == ["tests/test_workflow_acceptance.py"]
    gap_023 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-023")
    assert gap_023["status"] == "implemented"
    assert gap_023["positive_fixture_count"] == 1
    assert gap_023["negative_fixture_count"] == 1
    assert gap_023["behavior_checked_count"] == 2
    assert gap_023["implementation_evidence"]["runtime_module"] == "src/hate/workflow_evidence.py"
    assert gap_023["implementation_evidence"]["tests"] == ["tests/test_workflow_evidence.py"]
    gap_024 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-024")
    assert gap_024["status"] == "implemented"
    assert gap_024["positive_fixture_count"] == 1
    assert gap_024["negative_fixture_count"] == 1
    assert gap_024["behavior_checked_count"] == 2
    assert gap_024["implementation_evidence"]["runtime_module"] == "src/hate/workflow_birdseye.py"
    assert gap_024["implementation_evidence"]["tests"] == ["tests/test_workflow_birdseye.py"]
    gap_025 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-025")
    assert gap_025["status"] == "implemented"
    assert gap_025["positive_fixture_count"] == 1
    assert gap_025["negative_fixture_count"] == 1
    assert gap_025["behavior_checked_count"] == 2
    assert gap_025["implementation_evidence"]["runtime_module"] == "src/hate/workflow_plugin.py"
    assert gap_025["implementation_evidence"]["tests"] == ["tests/test_workflow_plugin.py"]
    gap_026 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-026")
    assert gap_026["status"] == "implemented"
    assert gap_026["positive_fixture_count"] == 1
    assert gap_026["negative_fixture_count"] == 1
    assert gap_026["behavior_checked_count"] == 2
    assert gap_026["implementation_evidence"]["runtime_module"] == "src/hate/workflow_completion.py"
    assert gap_026["implementation_evidence"]["tests"] == ["tests/test_workflow_completion.py"]

    report_path = tmp_path / "gap-closure-report.json"
    assert report_path.exists()
    assert json.loads(report_path.read_text(encoding="utf-8")) == report

    uat_dir = tmp_path / "uat-reports"
    uat_paths = sorted(uat_dir.glob("*.json"))
    assert len(uat_paths) == 26
    sample = json.loads((uat_dir / "workflow-evidence-uat-report.json").read_text(encoding="utf-8"))
    assert sample["record_type"] == "gap-closure-uat-report"
    assert sample["status"] == "implemented"
    assert sample["decision"] == "awaiting_acceptance"
    assert sample["gap_ids"] == ["HATE-GAP-023"]
    assert sample["behavior_checked_count"] == 2


def test_cli_gap_closure_writes_report(tmp_path: Path) -> None:
    exit_code = main([
        "gap",
        "closure",
        "--repo-root",
        str(ROOT),
        "--out",
        str(tmp_path),
        "--source-version",
        "cli-test",
    ])

    assert exit_code == 0
    report = json.loads((tmp_path / "gap-closure-report.json").read_text(encoding="utf-8"))
    assert report["source_version"] == "cli-test"
    assert report["overall_status"] == "checker_ready"
    assert report["summary"]["uat_report_count"] == 26
    assert report["summary"]["implemented_count"] == 26
    assert (tmp_path / "uat-reports" / "workflow-completion-uat-report.json").is_file()
