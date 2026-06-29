"""UAT tests for scale performance budget evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.scale import PerformanceBudgetInput, evaluate_performance_budget


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "scale" / "performance"
SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "HATE"
    / "v1"
    / "scale-performance-report.schema.json"
)


def load_fixture(name: str) -> dict:
    with (FIXTURE_ROOT / name / "fixture.json").open(encoding="utf-8") as f:
        return json.load(f)


def report_from_fixture(name: str) -> tuple[dict, dict]:
    fixture = load_fixture(name)
    return evaluate_performance_budget(PerformanceBudgetInput.from_dict(fixture["input"])), fixture["expected"]


def test_packet_fixture_paths_exist() -> None:
    for name in [
        "budget-pass",
        "budget-soft-gap",
        "budget-hold",
        "quadratic-risk",
        "missing-metrics",
    ]:
        assert (FIXTURE_ROOT / name / "fixture.json").exists()


def test_budget_pass_has_no_findings() -> None:
    report, expected = report_from_fixture("budget-pass")

    assert report["overall_status"] == expected["overall_status"]
    assert report["readiness_effect"] == expected["readiness_effect"]
    assert len(report["findings"]) == expected["finding_count"]
    assert all(item["readiness_effect"] == "pass" for item in report["budgets"])


def test_budget_soft_gap_by_profile_threshold() -> None:
    report, expected = report_from_fixture("budget-soft-gap")

    assert report["overall_status"] == expected["overall_status"]
    assert report["readiness_effect"] == expected["readiness_effect"]
    assert report["findings"][0]["code"] == expected["finding_code"]
    assert report["budgets"][0]["operation"] == "ingest"
    assert report["budgets"][0]["readiness_effect"] == "soft_gap"


def test_budget_hold_for_product_profile() -> None:
    report, expected = report_from_fixture("budget-hold")

    assert report["overall_status"] == expected["overall_status"]
    assert report["readiness_effect"] == expected["readiness_effect"]
    finding = report["findings"][0]
    assert finding["operation"] == expected["operation"]
    assert finding["readiness_effect"] == "hold"


def test_quadratic_risk_is_hard_dq() -> None:
    report, expected = report_from_fixture("quadratic-risk")

    assert report["overall_status"] == expected["overall_status"]
    assert report["readiness_effect"] == expected["readiness_effect"]
    assert any(item["code"] == expected["finding_code"] for item in report["findings"])
    assert report["estimated_counters"]["pairwise_comparisons"] == 10_000_000_000


def test_missing_metrics_are_hard_dq_in_release_profile() -> None:
    report, expected = report_from_fixture("missing-metrics")

    assert report["overall_status"] == expected["overall_status"]
    assert report["readiness_effect"] == expected["readiness_effect"]
    missing = [item for item in report["findings"] if item["code"] == expected["finding_code"]]
    assert [item["operation"] for item in missing] == expected["missing_operations"]
    assert all(item["readiness_effect"] == "hard_dq" for item in missing)


def test_report_includes_dataset_thresholds_counters_profile_and_source_refs() -> None:
    report, _expected = report_from_fixture("budget-pass")

    assert report["scenario_id"] == "budget-pass"
    assert report["profile"] == "product"
    assert report["dataset_shape"]["tests"] == 1000
    assert report["estimated_counters"]["peak_memory_mb"] == 256
    assert report["budgets"][0]["target_ms"] == 300000
    assert report["sourceRefs"] == ["fixtures/scale/performance/budget-pass/fixture.json"]


def test_schema_exposes_performance_budget_fields() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    properties = schema["properties"]

    assert "scenario_id" in properties
    assert "profile" in properties
    assert "dataset_shape" in properties
    assert "estimated_counters" in properties
    assert "readiness_effect" in properties
    assert "sourceRefs" in properties
