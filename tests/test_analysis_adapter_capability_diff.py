"""Tests for HATE-GAP-060 adapter capability diff evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.analysis.adapter_capability_diff import (
    build_adapter_capability_diff_report,
    evaluate_adapter_capability_diff_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "adapter-capability-diff"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "adapter-capability-diff-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "adapter-capability-diff-report"
    assert report["overall_status"] in {"pass", "hold", "blocked"}
    assert report["readiness_effect"] in {"none", "hold", "blocked"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_060_fixture_paths_exist() -> None:
    assert (FIXTURES / "lossless-normalization-pass" / "fixture.json").is_file()
    assert (FIXTURES / "lossy-field-drop-hold" / "fixture.json").is_file()


def test_lossless_normalization_fixture_passes() -> None:
    result = evaluate_adapter_capability_diff_fixture(_fixture("lossless-normalization-pass"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_lossy_field_drop_fixture_holds() -> None:
    result = evaluate_adapter_capability_diff_fixture(_fixture("lossy-field-drop-hold"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "adapter_capability_diff_lossy_field_drop_hold"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_claim_drift_detected_holds() -> None:
    report = build_adapter_capability_diff_report({
        "raw_field_map": {"field_a": {"type": "string"}},
        "normalized_field_map": {"field_a": {"type": "string"}},
        "lossy_transforms": [],
        "lossy_field_drop_detected": False,
        "claim_drift_detected": True,
        "unsupported_dialect_detected": False,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_transforms": 50, "max_field_drops": 10},
    })

    assert report["overall_status"] == "hold"
    assert "adapter_capability_diff_claim_drift" in _codes(report)


def test_unsupported_dialect_detected_holds() -> None:
    report = build_adapter_capability_diff_report({
        "raw_field_map": {"field_a": {"type": "string"}},
        "normalized_field_map": {"field_a": {"type": "string"}},
        "lossy_transforms": [],
        "lossy_field_drop_detected": False,
        "claim_drift_detected": False,
        "unsupported_dialect_detected": True,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_transforms": 50, "max_field_drops": 10},
    })

    assert report["overall_status"] == "hold"
    assert "adapter_capability_diff_unsupported_dialect_feature" in _codes(report)


def test_dropped_fields_without_flag_holds() -> None:
    report = build_adapter_capability_diff_report({
        "raw_field_map": {"field_a": {"type": "string"}, "field_b": {"type": "number"}},
        "normalized_field_map": {"field_a": {"type": "string"}},
        "lossy_transforms": [],
        "lossy_field_drop_detected": False,
        "claim_drift_detected": False,
        "unsupported_dialect_detected": False,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_transforms": 50, "max_field_drops": 10},
    })

    assert report["overall_status"] == "hold"
    assert "adapter_capability_diff_lossy_field_drop_hold" in _codes(report)


def test_confidence_below_threshold_holds() -> None:
    report = build_adapter_capability_diff_report({
        "raw_field_map": {"field_a": {"type": "string"}},
        "normalized_field_map": {"field_a": {"type": "string"}},
        "lossy_transforms": [],
        "lossy_field_drop_detected": False,
        "claim_drift_detected": False,
        "unsupported_dialect_detected": False,
        "confidence": 0.5,
        "limits": {"confidence_threshold": 0.7, "max_transforms": 50, "max_field_drops": 10},
    })

    assert report["overall_status"] == "hold"
    assert "adapter_capability_diff_lossy_field_drop_hold" in _codes(report)


def test_adapter_capability_diff_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["adapter-capability-diff-report"] == "schemas/HATE/v1/adapter-capability-diff-report.schema.json"