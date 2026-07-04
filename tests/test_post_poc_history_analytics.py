from __future__ import annotations

import json
from pathlib import Path

from hate.post_poc.history_analytics import (
    build_history_analytics_report,
    build_history_materialization_plan,
    evaluate_history_analytics_fixture,
    write_history_materialization_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc" / "history"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "history-analytics-report.schema.json"
MATERIALIZATION_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "history-materialization-manifest.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "history-analytics-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert report["query"]["record_type"] == "history-analytics-query"
    assert report["result"]["record_type"] == "history-analytics-result"
    assert report["trend_window"]["record_type"] == "history-trend-window"
    assert report["trend_window"]["sourceRefs"]
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def _assert_materialization_manifest_contract(manifest: dict) -> None:
    schema = json.loads(MATERIALIZATION_SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(manifest)
    assert manifest["schema_version"] == "HATE/v1"
    assert manifest["record_type"] == "history-materialization-manifest"
    for entry in manifest["entries"]:
        assert set(schema["properties"]["entries"]["items"]["required"]) <= set(entry)
        assert entry["cache_key"]
        assert entry["sample_fingerprint"]
        assert entry["materialized_ref"]


def test_task_postpoc_008_canonical_fixture_paths_exist() -> None:
    for name in [
        "flake-rate-trend",
        "debt-aging-trend",
        "baseline-drift",
        "stale-data-holds",
        "query-budget-exceeded",
    ]:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_flake_rate_trend_is_deterministic_and_passes() -> None:
    result = evaluate_history_analytics_fixture(_fixture("flake-rate-trend"))
    repeat = evaluate_history_analytics_fixture(_fixture("flake-rate-trend"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["report"]["result"]["metrics"] == repeat["report"]["result"]["metrics"]
    assert result["report"]["result"]["metrics"]["flake_rate"] == 0.03
    assert result["report"]["result"]["metrics"]["repo_health_score"] == 0.9
    assert result["report"]["summary"]["sample_count"] == 2
    _assert_report_contract(result["report"])


def test_debt_aging_trend_passes_with_expected_metric() -> None:
    result = evaluate_history_analytics_fixture(_fixture("debt-aging-trend"))

    assert result["status"] == "pass"
    assert result["report"]["result"]["metrics"]["debt_age"] == 28.0
    assert result["report"]["result"]["metrics"]["manual_review_latency"] == 15.0


def test_baseline_drift_counts_regression_clusters_without_unexplained_hold() -> None:
    result = evaluate_history_analytics_fixture(_fixture("baseline-drift"))

    assert result["status"] == "pass"
    assert result["report"]["result"]["metrics"]["baseline_drift"] == 0.035
    assert result["report"]["result"]["metrics"]["regression_cluster_count"] == 2


def test_stale_data_holds() -> None:
    result = evaluate_history_analytics_fixture(_fixture("stale-data-holds"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "history_stale_data"
    assert result["report"]["readiness_effect"] == "hold"


def test_query_budget_exceeded_is_explicit_not_empty_pass() -> None:
    result = evaluate_history_analytics_fixture(_fixture("query-budget-exceeded"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "history_query_budget_exceeded"
    assert result["report"]["result"]["sample_count"] == 2
    assert result["report"]["summary"]["actual_runtime_ms"] == 250


def test_history_window_too_small_holds() -> None:
    report = build_history_analytics_report({
        "query": {
            "window_start": "2026-07-01T00:00:00Z",
            "window_end": "2026-07-03T00:00:00Z",
            "performance_budget_ms": 1000,
            "actual_runtime_ms": 10,
            "min_sample_count": 2,
        },
        "samples": [
            {
                "run_id": "only-run",
                "test_count": 10,
                "flake_count": 0,
                "evidence_age_days": 1,
                "debt_age_days": 0,
                "repo_health_score": 0.9,
                "baseline_score": 0.9,
                "current_score": 0.9,
            }
        ],
    })

    assert report["overall_status"] == "hold"
    assert "history_window_too_small" in _codes(report)


def test_missing_metric_source_holds() -> None:
    report = build_history_analytics_report({
        "query": {
            "window_start": "2026-07-01T00:00:00Z",
            "window_end": "2026-07-03T00:00:00Z",
            "performance_budget_ms": 1000,
            "actual_runtime_ms": 10,
            "min_sample_count": 2,
            "required_metrics": ["baseline_drift", "repo_health_score"],
        },
        "samples": [
            {"run_id": "a", "test_count": 1, "flake_count": 0},
            {"run_id": "b", "test_count": 1, "flake_count": 0},
        ],
    })

    assert report["overall_status"] == "hold"
    assert "history_metric_source_missing" in _codes(report)


def test_unexplained_regression_cluster_holds() -> None:
    report = build_history_analytics_report({
        "query": {
            "window_start": "2026-07-01T00:00:00Z",
            "window_end": "2026-07-03T00:00:00Z",
            "performance_budget_ms": 1000,
            "actual_runtime_ms": 10,
            "min_sample_count": 2,
        },
        "samples": [
            {
                "run_id": "a",
                "test_count": 10,
                "flake_count": 0,
                "repo_health_score": 0.9,
                "baseline_score": 0.9,
                "current_score": 0.8,
                "unexplained_regression_clusters": 1,
            },
            {
                "run_id": "b",
                "test_count": 10,
                "flake_count": 0,
                "repo_health_score": 0.9,
                "baseline_score": 0.9,
                "current_score": 0.88,
            },
        ],
    })

    assert report["overall_status"] == "hold"
    assert "history_regression_cluster_unexplained" in _codes(report)


def test_history_analytics_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["history-analytics-report"] == "schemas/HATE/v1/history-analytics-report.schema.json"
    assert records["history-materialization-manifest"] == "schemas/HATE/v1/history-materialization-manifest.schema.json"


def test_history_materialization_plan_recomputes_without_previous_manifest() -> None:
    fixture = _fixture("flake-rate-trend")

    plan = build_history_materialization_plan(fixture["input"], source_refs=["fixture://history/flake-rate"])

    assert plan["record_type"] == "history-materialization-plan"
    assert plan["incremental"]["strategy"] == "sample-fingerprint"
    assert plan["summary"]["recompute_count"] == 2
    assert plan["summary"]["reused_count"] == 0
    assert plan["summary"]["drop_count"] == 0
    assert all(entry["materialization_action"] == "recompute" for entry in plan["entries"])
    assert all(entry["cache_key"] and entry["sample_fingerprint"] for entry in plan["entries"])
    assert plan["sourceRefs"] == ["fixture://history/flake-rate"]


def test_history_materialization_plan_reuses_unchanged_entries() -> None:
    fixture = _fixture("flake-rate-trend")
    first = build_history_materialization_plan(fixture["input"])
    previous_manifest = {
        "entries": [
            {
                "cache_key": entry["cache_key"],
                "sample_id": entry["sample_id"],
                "repo_id": entry["repo_id"],
                "suite_id": entry["suite_id"],
                "sample_fingerprint": entry["sample_fingerprint"],
                "materialized_ref": f"history-cache://warm/{entry['sample_id']}",
            }
            for entry in first["entries"]
        ]
    }

    second = build_history_materialization_plan(fixture["input"], previous_manifest=previous_manifest)

    assert second["summary"]["reused_count"] == 2
    assert second["summary"]["recompute_count"] == 0
    assert {entry["materialization_action"] for entry in second["entries"]} == {"reuse"}
    assert all(entry["materialized_ref"].startswith("history-cache://warm/") for entry in second["entries"])


def test_history_materialization_plan_recomputes_changed_entry_and_drops_missing_previous() -> None:
    fixture = _fixture("flake-rate-trend")
    first = build_history_materialization_plan(fixture["input"])
    previous_manifest = {
        "entries": [
            {
                "cache_key": entry["cache_key"],
                "sample_id": entry["sample_id"],
                "repo_id": entry["repo_id"],
                "suite_id": entry["suite_id"],
                "sample_fingerprint": entry["sample_fingerprint"],
                "materialized_ref": f"history-cache://warm/{entry['sample_id']}",
            }
            for entry in first["entries"]
        ] + [
            {
                "cache_key": "stale-key",
                "sample_id": "removed-run",
                "repo_id": "repo-a",
                "suite_id": "unit",
                "sample_fingerprint": "old",
                "materialized_ref": "history-cache://removed-run",
            }
        ]
    }
    changed_input = json.loads(json.dumps(fixture["input"]))
    changed_input["samples"][0]["flake_count"] += 1

    plan = build_history_materialization_plan(changed_input, previous_manifest=previous_manifest)

    assert plan["summary"]["reused_count"] == 1
    assert plan["summary"]["recompute_count"] == 1
    assert plan["summary"]["drop_count"] == 1
    actions = {entry["sample_id"]: entry["materialization_action"] for entry in plan["entries"]}
    assert actions["removed-run"] == "drop"
    assert "recompute" in actions.values()


def test_history_materialization_manifest_write_contract(tmp_path: Path) -> None:
    fixture = _fixture("flake-rate-trend")
    plan = build_history_materialization_plan(fixture["input"], source_refs=["fixture://history/materialization"])
    out_path = tmp_path / "history-materialization.json"

    artifact = write_history_materialization_manifest(plan, out_path)

    assert artifact["record_type"] == "history-materialization-manifest-artifact"
    assert artifact["entry_count"] == 2
    assert artifact["sourceRefs"] == ["fixture://history/materialization"]
    manifest = json.loads(out_path.read_text(encoding="utf-8"))
    assert manifest["record_type"] == "history-materialization-manifest"
    _assert_materialization_manifest_contract(manifest)
    assert len(manifest["entries"]) == 2
    assert all(entry["cache_key"] and entry["sample_fingerprint"] for entry in manifest["entries"])


def test_history_materialization_plan_holds_on_stale_samples() -> None:
    fixture = _fixture("stale-data-holds")

    plan = build_history_materialization_plan(fixture["input"])

    assert "history_stale_data" in _codes(plan)
