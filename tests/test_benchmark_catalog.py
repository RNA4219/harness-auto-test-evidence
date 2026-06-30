"""Tests for HATE-GAP-018 benchmark catalog evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.scale import build_benchmark_catalog_report, evaluate_benchmark_catalog_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "performance" / "benchmark"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "scale-performance-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "scale-performance-report"
    assert report["overall_status"] in {"pass", "soft_gap", "hold", "blocked"}
    assert report["readiness_effect"] in {"pass", "soft_gap", "hold", "hard_dq"}
    assert "benchmark_catalog" in report


def test_canonical_gap_018_fixture_paths_exist() -> None:
    assert (FIXTURES / "medium-repo-pass" / "fixture.json").is_file()
    assert (FIXTURES / "budget-exceeded" / "fixture.json").is_file()


def test_medium_repo_pass_fixture_passes() -> None:
    result = evaluate_benchmark_catalog_fixture(_fixture("medium-repo-pass"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])
    assert result["report"]["benchmark_catalog"]["repo_class"] == "medium"
    assert result["report"]["pagination"]["required"] is True
    assert result["report"]["pagination"]["tested"] is True


def test_budget_exceeded_fixture_holds() -> None:
    result = evaluate_benchmark_catalog_fixture(_fixture("budget-exceeded"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "performance_budget_exceeded"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_large_benchmark_requires_manifest_only_fixture() -> None:
    report = build_benchmark_catalog_report({
        "repo_class": "large",
        "duration_seconds": 240,
        "budget_seconds": 300,
        "manifest_only_large_fixture": False,
    })

    assert report["overall_status"] == "blocked"
    assert "performance_large_raw_fixture_committed" in _codes(report)


def test_large_processing_must_be_streaming_or_chunked() -> None:
    report = build_benchmark_catalog_report({
        "repo_class": "large",
        "duration_seconds": 240,
        "budget_seconds": 300,
        "streaming_or_chunked": False,
    })

    assert report["overall_status"] == "blocked"
    assert "performance_unbounded_processing" in _codes(report)


def test_pagination_and_cache_invalidation_are_required_for_large_shapes() -> None:
    report = build_benchmark_catalog_report({
        "repo_class": "medium",
        "duration_seconds": 90,
        "budget_seconds": 120,
        "pagination_tested": False,
        "cache_invalidation_tested": False,
    })

    assert report["overall_status"] == "hold"
    assert "performance_pagination_not_tested" in _codes(report)
    assert "performance_cache_invalidation_not_tested" in _codes(report)


def test_unknown_repo_class_holds() -> None:
    report = build_benchmark_catalog_report({
        "repo_class": "tiny-custom",
        "duration_seconds": 1,
        "budget_seconds": 10,
    })

    assert report["overall_status"] == "hold"
    assert "performance_unknown_repo_class" in _codes(report)


def test_scale_performance_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["scale-performance-report"] == "schemas/HATE/v1/scale-performance-report.schema.json"
