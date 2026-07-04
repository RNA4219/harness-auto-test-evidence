from __future__ import annotations

import json
from pathlib import Path

from hate.post_poc.capacity import (
    build_capacity_regression_packet,
    build_capacity_report,
    evaluate_capacity_fixture,
    write_capacity_regression_packet,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc" / "capacity"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "capacity-report.schema.json"
REGRESSION_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "capacity-regression-packet.schema.json"
DEGRADATION_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "capacity-degradation-mode-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    degradation_schema = json.loads(DEGRADATION_SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "capacity-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert report["baseline_record"]["record_type"] == "capacity-baseline-record"
    assert report["degradation_report"]["record_type"] == "capacity-degradation-mode-report"
    assert set(degradation_schema["required"]) <= set(report["degradation_report"])
    assert isinstance(report["degradation_report"]["degradation_modes"], list)
    assert isinstance(report["degradation_report"]["budget_exceeded_scenarios"], list)
    assert isinstance(report["degradation_report"]["timeout_count"], int)
    for run in report["benchmark_runs"]:
        assert run["record_type"] == "capacity-benchmark-run"
        for field in [
            "scenario_id",
            "dataset_hash",
            "repo_count",
            "finding_count",
            "duration_ms",
            "peak_memory_mb",
            "cache_hit_rate",
            "timeout_count",
            "degradation_mode",
            "budget_status",
        ]:
            assert field in run
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def _assert_regression_packet_contract(packet: dict) -> None:
    schema = json.loads(REGRESSION_SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(packet)
    assert packet["schema_version"] == "HATE/v1"
    assert packet["record_type"] == "capacity-regression-packet"
    assert isinstance(packet["comparisons"], list)
    assert isinstance(packet["findings"], list)
    assert isinstance(packet["sourceRefs"], list)
    for comparison in packet["comparisons"]:
        assert set(schema["properties"]["comparisons"]["items"]["required"]) <= set(comparison)
        assert comparison["record_type"] == "capacity-regression-comparison"
        assert comparison["comparison_status"] in {"compared", "missing_previous"}
        assert isinstance(comparison["regression_detected"], bool)
        assert isinstance(comparison["regression_reasons"], list)
    for finding in packet["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)
    assert set(schema["properties"]["summary"]["required"]) <= set(packet["summary"])


def test_task_postpoc_013_canonical_fixture_paths_exist() -> None:
    for name in [
        "100-repo-baseline",
        "1000-repo-baseline",
        "1m-findings-baseline",
        "warm-cache-improves",
        "budget-exceeded-holds",
    ]:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_100_repo_baseline_passes_with_machine_profile_and_dataset_hash() -> None:
    result = evaluate_capacity_fixture(_fixture("100-repo-baseline"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["report"]["summary"]["machine_profile_present"] is True
    assert result["report"]["benchmark_runs"][0]["dataset_hash"].startswith("sha256:")
    _assert_report_contract(result["report"])


def test_1000_repo_baseline_is_measured_not_report_only() -> None:
    result = evaluate_capacity_fixture(_fixture("1000-repo-baseline"))

    assert result["status"] == "pass"
    run = result["report"]["benchmark_runs"][0]
    assert run["scenario_id"] == "1000-repo-roster"
    assert run["repo_count"] == 1000
    assert run["duration_ms"] > 0
    assert run["peak_memory_mb"] > 0


def test_1m_findings_baseline_passes_with_streamed_degradation_mode() -> None:
    result = evaluate_capacity_fixture(_fixture("1m-findings-baseline"))

    assert result["status"] == "pass"
    assert result["report"]["benchmark_runs"][0]["finding_count"] == 1000000
    assert result["report"]["benchmark_runs"][0]["degradation_mode"] == "streamed"


def test_warm_cache_improves_over_cold_cache() -> None:
    result = evaluate_capacity_fixture(_fixture("warm-cache-improves"))
    runs = {run["scenario_id"]: run for run in result["report"]["benchmark_runs"]}

    assert result["status"] == "pass"
    assert runs["warm-cache"]["duration_ms"] < runs["cold-cache"]["duration_ms"]
    assert runs["warm-cache"]["cache_hit_rate"] > runs["cold-cache"]["cache_hit_rate"]


def test_budget_exceeded_holds_with_explicit_degradation_mode() -> None:
    result = evaluate_capacity_fixture(_fixture("budget-exceeded-holds"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "capacity_runtime_budget_exceeded"
    assert "timeout_partitioned" in result["report"]["degradation_report"]["degradation_modes"]


def test_budget_failure_without_degradation_mode_holds() -> None:
    report = build_capacity_report({
        "machine_profile": {"profile_id": "dev", "cpu_model": "cpu"},
        "runs": [
            {
                "scenario_id": "large-monorepo",
                "dataset_hash": "sha256:capacity-large",
                "repo_count": 1,
                "finding_count": 1000000,
                "duration_ms": 700000,
                "peak_memory_mb": 7000,
                "timeout_count": 1,
                "runtime_budget_ms": 420000,
                "memory_budget_mb": 8192,
            }
        ],
    })

    assert report["overall_status"] == "hold"
    assert "capacity_degradation_mode_missing" in _codes(report)


def test_missing_machine_profile_or_baseline_holds() -> None:
    report = build_capacity_report({"runs": []})

    assert report["overall_status"] == "hold"
    assert "capacity_baseline_missing" in _codes(report)


def test_non_reproducible_dataset_hash_holds() -> None:
    report = build_capacity_report({
        "machine_profile": {"profile_id": "dev", "cpu_model": "cpu"},
        "runs": [
            {
                "scenario_id": "100-repo-roster",
                "dataset_hash": "floating-dataset",
                "repo_count": 100,
                "finding_count": 1,
                "duration_ms": 10,
                "peak_memory_mb": 10,
                "degradation_mode": "normal",
            }
        ],
    })

    assert report["overall_status"] == "hold"
    assert "capacity_dataset_not_reproducible" in _codes(report)


def test_memory_budget_exceeded_holds() -> None:
    report = build_capacity_report({
        "machine_profile": {"profile_id": "dev", "cpu_model": "cpu"},
        "runs": [
            {
                "scenario_id": "1m-findings",
                "dataset_hash": "sha256:capacity-memory",
                "repo_count": 1000,
                "finding_count": 1000000,
                "duration_ms": 10,
                "peak_memory_mb": 9000,
                "degradation_mode": "spill_to_disk",
                "memory_budget_mb": 8192,
            }
        ],
    })

    assert report["overall_status"] == "hold"
    assert "capacity_memory_budget_exceeded" in _codes(report)


def test_capacity_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["capacity-report"] == "schemas/HATE/v1/capacity-report.schema.json"
    assert records["capacity-degradation-mode-report"] == "schemas/HATE/v1/capacity-degradation-mode-report.schema.json"
    assert records["capacity-regression-packet"] == "schemas/HATE/v1/capacity-regression-packet.schema.json"


def test_capacity_regression_packet_passes_without_degradation() -> None:
    previous = _fixture("100-repo-baseline")["input"]
    current = json.loads(json.dumps(previous))
    current["runs"][0]["duration_ms"] = previous["runs"][0]["duration_ms"]
    current["runs"][0]["peak_memory_mb"] = previous["runs"][0]["peak_memory_mb"]

    packet = build_capacity_regression_packet(current, previous, source_refs=["fixture://capacity/regression-pass"])

    assert packet["record_type"] == "capacity-regression-packet"
    _assert_regression_packet_contract(packet)
    assert packet["summary"]["ready_for_capacity_promotion"] is True
    assert packet["summary"]["regression_count"] == 0
    assert packet["findings"] == []
    assert packet["sourceRefs"] == ["fixture://capacity/regression-pass"]


def test_capacity_regression_packet_detects_runtime_and_memory_regression() -> None:
    previous = _fixture("1000-repo-baseline")["input"]
    current = json.loads(json.dumps(previous))
    current["runs"][0]["duration_ms"] = int(previous["runs"][0]["duration_ms"] * 1.5)
    current["runs"][0]["peak_memory_mb"] = int(previous["runs"][0]["peak_memory_mb"] * 1.4)

    packet = build_capacity_regression_packet(current, previous)

    _assert_regression_packet_contract(packet)
    assert packet["summary"]["ready_for_capacity_promotion"] is False
    reasons = packet["comparisons"][0]["regression_reasons"]
    assert "capacity_runtime_regression" in reasons
    assert "capacity_memory_regression" in reasons
    assert "capacity_runtime_regression" in _codes(packet)
    assert "capacity_memory_regression" in _codes(packet)


def test_capacity_regression_packet_detects_cache_regression() -> None:
    previous = _fixture("warm-cache-improves")["input"]
    current = json.loads(json.dumps(previous))
    current["runs"][1]["cache_hit_rate"] = 0.2

    packet = build_capacity_regression_packet(current, previous)
    warm = [item for item in packet["comparisons"] if item["scenario_id"] == "warm-cache"][0]

    assert warm["regression_detected"] is True
    assert "capacity_cache_regression" in warm["regression_reasons"]


def test_capacity_regression_packet_blocks_missing_previous_baseline() -> None:
    current = _fixture("100-repo-baseline")["input"]
    previous = {"machine_profile": current["machine_profile"], "runs": []}

    packet = build_capacity_regression_packet(current, previous)

    assert packet["summary"]["missing_previous_count"] == 1
    assert "capacity_previous_baseline_missing" in _codes(packet)


def test_capacity_regression_packet_artifact_write_contract(tmp_path: Path) -> None:
    previous = _fixture("100-repo-baseline")["input"]
    current = json.loads(json.dumps(previous))
    packet = build_capacity_regression_packet(current, previous, source_refs=["fixture://capacity/regression-artifact"])
    out_path = tmp_path / "capacity-regression.json"

    artifact = write_capacity_regression_packet(packet, out_path)

    assert artifact["record_type"] == "capacity-regression-packet-artifact"
    assert artifact["comparison_count"] == len(packet["comparisons"])
    assert artifact["sourceRefs"] == ["fixture://capacity/regression-artifact"]
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["record_type"] == "capacity-regression-packet"
