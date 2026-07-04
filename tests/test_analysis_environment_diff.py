"""Tests for HATE-GAP-055 environment diff evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.analysis.environment_diff import (
    build_environment_diff_report,
    evaluate_environment_diff_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "environment-diff"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "environment-diff-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "environment-diff-report"
    assert report["overall_status"] in {"pass", "hold", "blocked"}
    assert report["readiness_effect"] in {"none", "hold", "blocked"}
    assert "environment_diff_diagnostics" in report
    assert {
        "derived_delta_count",
        "missing_snapshot_count",
        "duplicate_attempt_count",
        "unexplained_derived_delta_count",
    } <= set(report["summary"])
    assert {
        "derived_deltas",
        "missing_snapshot_attempt_ids",
        "duplicate_attempt_ids",
        "unexplained_derived_delta_ids",
    } <= set(report["environment_diff_diagnostics"])
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_055_fixture_paths_exist() -> None:
    assert (FIXTURES / "runtime-version-drift-explained" / "fixture.json").is_file()
    assert (FIXTURES / "unexplained-env-drift-hold" / "fixture.json").is_file()


def test_runtime_version_drift_explained_fixture_passes() -> None:
    result = evaluate_environment_diff_fixture(_fixture("runtime-version-drift-explained"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_unexplained_env_drift_fixture_holds() -> None:
    result = evaluate_environment_diff_fixture(_fixture("unexplained-env-drift-hold"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "environment_diff_unexplained_drift_hold"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_runtime_version_drift_not_explained_holds() -> None:
    report = build_environment_diff_report({
        "environment_deltas": [{"delta_id": "d1", "delta_type": "runtime_version_drift", "category": "runtime", "severity": "high", "confidence": 0.9, "sourceRef": "d:1", "rationale": "r", "explained": False}],
        "attempts_compared": [{"attempt_id": "a1", "environment_ref": "env:1", "timestamp": "2024-01-01T00:00:00Z"}],
        "drift_classes": [{"class_id": "c1", "class_type": "runtime_version", "drift_count": 1, "severity": "high"}],
        "runtime_version_drift_explained": False,
        "cache_state_known": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "environment_diff_unexplained_drift_hold" in _codes(report)


def test_cache_state_unknown_holds() -> None:
    report = build_environment_diff_report({
        "environment_deltas": [{"delta_id": "d1", "delta_type": "os_drift", "category": "os", "severity": "low", "confidence": 0.9, "sourceRef": "d:1", "rationale": "r", "explained": True}],
        "attempts_compared": [{"attempt_id": "a1", "environment_ref": "env:1", "timestamp": "2024-01-01T00:00:00Z"}],
        "drift_classes": [{"class_id": "c1", "class_type": "os", "drift_count": 1, "severity": "low"}],
        "runtime_version_drift_explained": True,
        "cache_state_known": False,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "environment_diff_cache_state_unknown" in _codes(report)


def test_delta_without_source_ref_holds() -> None:
    report = build_environment_diff_report({
        "environment_deltas": [{"delta_id": "d1", "delta_type": "runtime_version_drift", "category": "runtime", "severity": "high", "confidence": 0.9, "sourceRef": "", "rationale": "r", "explained": False}],
        "attempts_compared": [{"attempt_id": "a1", "environment_ref": "env:1", "timestamp": "2024-01-01T00:00:00Z"}],
        "drift_classes": [{"class_id": "c1", "class_type": "runtime_version", "drift_count": 1, "severity": "high"}],
        "runtime_version_drift_explained": True,
        "cache_state_known": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "environment_diff_unexplained_drift_hold" in _codes(report)


def test_snapshot_derived_unexplained_dependency_drift_holds() -> None:
    report = build_environment_diff_report({
        "environment_deltas": [],
        "attempts_compared": [
            {
                "attempt_id": "a1",
                "environment_ref": "env:1",
                "timestamp": "2024-01-01T00:00:00Z",
                "snapshot": {"python_version": "3.11.8", "lockfile_hash": "sha256:old"},
            },
            {
                "attempt_id": "a2",
                "environment_ref": "env:2",
                "timestamp": "2024-01-01T01:00:00Z",
                "snapshot": {"python_version": "3.11.8", "lockfile_hash": "sha256:new"},
            },
        ],
        "drift_classes": [],
        "runtime_version_drift_explained": True,
        "cache_state_known": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "environment_diff_unexplained_derived_drift_hold" in _codes(report)
    assert report["summary"]["derived_delta_count"] == 1
    assert report["environment_diff_diagnostics"]["derived_deltas"][0]["delta_type"] == "dependency_drift"


def test_duplicate_attempt_and_missing_snapshot_hold() -> None:
    report = build_environment_diff_report({
        "environment_deltas": [],
        "attempts_compared": [
            {"attempt_id": "a1", "environment_ref": "env:1", "timestamp": "2024-01-01T00:00:00Z"},
            {"attempt_id": "a1", "environment_ref": "env:2", "timestamp": "2024-01-01T01:00:00Z"},
        ],
        "drift_classes": [],
        "runtime_version_drift_explained": True,
        "cache_state_known": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "environment_diff_attempt_snapshot_missing" in _codes(report)
    assert "environment_diff_duplicate_attempt_id" in _codes(report)
    assert report["summary"]["missing_snapshot_count"] == 2
    assert report["summary"]["duplicate_attempt_count"] == 1


def test_environment_diff_budget_excess_holds() -> None:
    report = build_environment_diff_report({
        "environment_deltas": [
            {"delta_id": "d1", "delta_type": "os_drift", "category": "os", "severity": "low", "confidence": 0.9, "sourceRef": "d:1", "rationale": "r", "explained": True},
            {"delta_id": "d2", "delta_type": "cache_drift", "category": "cache", "severity": "low", "confidence": 0.9, "sourceRef": "d:2", "rationale": "r", "explained": True},
        ],
        "attempts_compared": [
            {"attempt_id": "a1", "environment_ref": "env:1", "timestamp": "2024-01-01T00:00:00Z", "snapshot": {"os": "ubuntu"}},
            {"attempt_id": "a2", "environment_ref": "env:2", "timestamp": "2024-01-01T01:00:00Z", "snapshot": {"os": "ubuntu"}},
        ],
        "drift_classes": [
            {"class_id": "c1", "class_type": "os", "drift_count": 1, "severity": "low"},
            {"class_id": "c2", "class_type": "cache", "drift_count": 1, "severity": "low"},
        ],
        "runtime_version_drift_explained": True,
        "cache_state_known": True,
        "confidence": 0.9,
        "limits": {"max_deltas": 1, "max_attempts": 1, "max_drift_classes": 1, "confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "environment_diff_delta_budget_exceeded" in _codes(report)
    assert "environment_diff_attempt_budget_exceeded" in _codes(report)
    assert "environment_diff_drift_class_budget_exceeded" in _codes(report)


def test_environment_diff_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["environment-diff-report"] == "schemas/HATE/v1/environment-diff-report.schema.json"
