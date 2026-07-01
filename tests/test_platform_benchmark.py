"""Tests for platform benchmark fixture report."""

from __future__ import annotations

import json
from pathlib import Path

from hate.scale import build_platform_benchmark_report


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "platform" / "benchmark"
SCHEMAS = ROOT / "schemas" / "HATE" / "v1"


def test_platform_benchmark_fixture_paths_exist() -> None:
    for name in [
        "small-deterministic",
        "expired-debt-distribution",
        "external-hold-distribution",
        "stale-cache-distribution",
        "degraded-query",
        "measured-baseline-metadata",
    ]:
        assert (FIXTURES / name / "fixture.json").exists()


def test_small_benchmark_is_deterministic_for_same_seed() -> None:
    fixture = _fixture("small-deterministic")

    first = build_platform_benchmark_report(fixture["input"], fixture["fixture_id"])
    second = build_platform_benchmark_report(fixture["input"], fixture["fixture_id"])

    assert first == second
    assert first["overall_status"] == fixture["expected"]["overall_status"]
    assert first["summary"]["repo_count"] == fixture["expected"]["repo_count"]
    assert first["summary"]["finding_count"] == fixture["expected"]["finding_count"]
    assert first["deterministic_hash"].startswith("sha256:")


def test_expired_debt_distribution_appears() -> None:
    fixture = _fixture("expired-debt-distribution")

    report = build_platform_benchmark_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["distribution"]["expired_accepted_debt"] == fixture["expected"]["expired_accepted_debt"]


def test_external_hold_distribution_is_separated_from_owned_failures() -> None:
    fixture = _fixture("external-hold-distribution")

    report = build_platform_benchmark_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["distribution"]["external_repo_holds"] == fixture["expected"]["external_repo_holds"]
    assert report["summary"]["finding_count_class"] == fixture["expected"]["finding_count_class"]


def test_stale_cache_candidates_are_present() -> None:
    fixture = _fixture("stale-cache-distribution")

    report = build_platform_benchmark_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["distribution"]["stale_cache_candidates"] == fixture["expected"]["stale_cache_candidates"]


def test_degraded_query_is_reported_when_budget_exceeded() -> None:
    fixture = _fixture("degraded-query")

    report = build_platform_benchmark_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert fixture["expected"]["finding_code"] in _codes(report)
    assert fixture["expected"]["degradation"] in report["degradations"]


def test_measured_baseline_metadata_is_required_and_preserved() -> None:
    fixture = _fixture("measured-baseline-metadata")

    report = build_platform_benchmark_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["baseline"]["hardware_class"] == fixture["expected"]["hardware_class"]
    assert report["baseline"]["policy_hash"] == fixture["expected"]["policy_hash"]


def test_degraded_pass_without_scope_limit_holds() -> None:
    fixture = _fixture("degraded-query")
    fixture["input"]["claims_pass_without_scope_limit"] = True

    report = build_platform_benchmark_report(fixture["input"], "degraded-without-scope")

    assert report["overall_status"] == "hold"
    assert "platform_benchmark_degraded_pass_without_scope_limit" in _codes(report)


def test_platform_benchmark_schema_registered() -> None:
    schema = json.loads((SCHEMAS / "platform-benchmark-report.schema.json").read_text(encoding="utf-8"))
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "platform-benchmark-report"
    assert any(record["record_type"] == "platform-benchmark-report" for record in registry["records"])


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> set[str]:
    return {finding["code"] for finding in report["findings"]}
