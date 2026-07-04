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
    assert {"capability_claims", "observed_capabilities", "capability_diagnostics"} <= set(report)
    assert {
        "dropped_field_count",
        "type_change_count",
        "claim_drift_count",
        "unsupported_feature_count",
    } <= set(report["summary"])
    assert {
        "covered_raw_fields",
        "dropped_fields",
        "type_changes",
        "claim_drifts",
        "unsupported_features",
    } <= set(report["capability_diagnostics"])
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


def test_raw_field_references_allow_lossless_renamed_normalization() -> None:
    report = build_adapter_capability_diff_report({
        "raw_field_map": {
            "pytest.nodeid": {"type": "string"},
            "pytest.duration": {"type": "number"},
        },
        "normalized_field_map": {
            "test_id": {"type": "string", "raw_field": "pytest.nodeid"},
            "duration_ms": {"type": "number", "source_field": "pytest.duration"},
        },
        "lossy_transforms": [],
        "lossy_field_drop_detected": False,
        "claim_drift_detected": False,
        "unsupported_dialect_detected": False,
        "confidence": 0.91,
        "limits": {"confidence_threshold": 0.7, "max_transforms": 50, "max_field_drops": 10},
    })

    assert report["overall_status"] == "pass"
    assert report["summary"]["dropped_field_count"] == 0
    assert set(report["capability_diagnostics"]["covered_raw_fields"]) == {"pytest.nodeid", "pytest.duration"}


def test_type_degradation_holds_even_when_field_is_present() -> None:
    report = build_adapter_capability_diff_report({
        "raw_field_map": {"coverage.contexts": {"type": "array"}},
        "normalized_field_map": {"coverage_contexts": {"type": "string", "raw_field": "coverage.contexts"}},
        "lossy_transforms": [],
        "lossy_field_drop_detected": False,
        "claim_drift_detected": False,
        "unsupported_dialect_detected": False,
        "confidence": 0.94,
        "limits": {"confidence_threshold": 0.7, "max_transforms": 50, "max_field_drops": 10},
    })

    assert report["overall_status"] == "hold"
    assert "adapter_capability_diff_type_degradation" in _codes(report)
    assert report["summary"]["type_change_count"] == 1
    assert report["capability_diagnostics"]["type_changes"][0]["raw_field"] == "coverage.contexts"


def test_capability_claim_drift_is_inferred_from_claims_and_observations() -> None:
    report = build_adapter_capability_diff_report({
        "raw_field_map": {"nodeid": {"type": "string"}},
        "normalized_field_map": {"nodeid": {"type": "string"}},
        "capability_claims": {"rerun_index": True, "coverage_contexts": True},
        "observed_capabilities": {"rerun_index": False, "coverage_contexts": True},
        "lossy_transforms": [],
        "lossy_field_drop_detected": False,
        "claim_drift_detected": False,
        "unsupported_dialect_detected": False,
        "confidence": 0.93,
        "limits": {"confidence_threshold": 0.7, "max_transforms": 50, "max_field_drops": 10},
    })

    assert report["overall_status"] == "hold"
    assert "adapter_capability_diff_claim_drift" in _codes(report)
    assert report["summary"]["claim_drift_count"] == 1
    assert report["capability_diagnostics"]["claim_drifts"] == ["rerun_index"]


def test_capability_diff_budget_excess_is_reported_separately() -> None:
    report = build_adapter_capability_diff_report({
        "raw_field_map": {"a": {"type": "string"}, "b": {"type": "string"}, "c": {"type": "string"}},
        "normalized_field_map": {},
        "lossy_transforms": [
            {"transform_id": "t1", "field_name": "a", "transform_type": "drop", "sourceRef": "src:a"},
            {"transform_id": "t2", "field_name": "b", "transform_type": "drop", "sourceRef": "src:b"},
        ],
        "lossy_field_drop_detected": False,
        "claim_drift_detected": False,
        "unsupported_dialect_detected": False,
        "confidence": 0.88,
        "limits": {"confidence_threshold": 0.7, "max_transforms": 1, "max_field_drops": 1},
    })

    assert report["overall_status"] == "hold"
    assert "adapter_capability_diff_field_drop_budget_exceeded" in _codes(report)
    assert "adapter_capability_diff_transform_budget_exceeded" in _codes(report)


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
