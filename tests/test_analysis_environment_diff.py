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


def test_environment_diff_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["environment-diff-report"] == "schemas/HATE/v1/environment-diff-report.schema.json"