"""Tests for HATE-GAP-050 test recommendation engine evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.analysis.test_recommendation import (
    build_test_recommendation_report,
    evaluate_test_recommendation_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "test-recommendation"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "test-recommendation-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "test-recommendation-report"
    assert report["overall_status"] in {"pass", "hold", "blocked"}
    assert report["readiness_effect"] in {"none", "hold", "blocked"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_050_fixture_paths_exist() -> None:
    assert (FIXTURES / "missing-oracle-actionable" / "fixture.json").is_file()
    assert (FIXTURES / "generic-advice-denied" / "fixture.json").is_file()


def test_missing_oracle_actionable_fixture_passes() -> None:
    result = evaluate_test_recommendation_fixture(_fixture("missing-oracle-actionable"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_generic_advice_denied_fixture_holds() -> None:
    result = evaluate_test_recommendation_fixture(_fixture("generic-advice-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "test_recommendation_generic_advice_denied"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_verification_command_holds() -> None:
    report = build_test_recommendation_report({
        "recommendations": [{"action": "a", "target": "t", "confidence": 0.9, "sourceRef": "r:1", "rationale": "r", "actionable": True}],
        "required_oracles": [{"oracle_id": "o1", "risk_id": "r1", "confidence": 0.9, "sourceRef": "o:1", "rationale": "r", "verified": True}],
        "verification_commands": [{"command_id": "c1", "recommendation_id": "r1", "confidence": 0.9, "sourceRef": "c:1", "rationale": "r", "verified": False}],
        "actionable_taxonomy_used": True,
        "oracle_validation_enabled": True,
        "command_verification_enabled": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "test_recommendation_missing_verification_command" in _codes(report)


def test_missing_required_oracle_holds() -> None:
    report = build_test_recommendation_report({
        "recommendations": [{"action": "a", "target": "t", "confidence": 0.9, "sourceRef": "r:1", "rationale": "r", "actionable": True}],
        "required_oracles": [{"oracle_id": "o1", "risk_id": "r1", "confidence": 0.9, "sourceRef": "o:1", "rationale": "r", "verified": False}],
        "verification_commands": [{"command_id": "c1", "recommendation_id": "r1", "confidence": 0.9, "sourceRef": "c:1", "rationale": "r", "verified": True}],
        "actionable_taxonomy_used": True,
        "oracle_validation_enabled": True,
        "command_verification_enabled": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "test_recommendation_missing_required_oracle" in _codes(report)


def test_non_actionable_recommendation_holds() -> None:
    report = build_test_recommendation_report({
        "recommendations": [{"action": "a", "target": "t", "confidence": 0.9, "sourceRef": "r:1", "rationale": "r", "actionable": False}],
        "required_oracles": [{"oracle_id": "o1", "risk_id": "r1", "confidence": 0.9, "sourceRef": "o:1", "rationale": "r", "verified": True}],
        "verification_commands": [{"command_id": "c1", "recommendation_id": "r1", "confidence": 0.9, "sourceRef": "c:1", "rationale": "r", "verified": True}],
        "actionable_taxonomy_used": True,
        "oracle_validation_enabled": True,
        "command_verification_enabled": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "test_recommendation_generic_advice_denied" in _codes(report)


def test_oracle_validation_disabled_holds() -> None:
    report = build_test_recommendation_report({
        "recommendations": [{"action": "a", "target": "t", "confidence": 0.9, "sourceRef": "r:1", "rationale": "r", "actionable": True}],
        "required_oracles": [{"oracle_id": "o1", "risk_id": "r1", "confidence": 0.9, "sourceRef": "o:1", "rationale": "r", "verified": True}],
        "verification_commands": [{"command_id": "c1", "recommendation_id": "r1", "confidence": 0.9, "sourceRef": "c:1", "rationale": "r", "verified": True}],
        "actionable_taxonomy_used": True,
        "oracle_validation_enabled": False,
        "command_verification_enabled": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "test_recommendation_missing_required_oracle" in _codes(report)


def test_command_verification_disabled_holds() -> None:
    report = build_test_recommendation_report({
        "recommendations": [{"action": "a", "target": "t", "confidence": 0.9, "sourceRef": "r:1", "rationale": "r", "actionable": True}],
        "required_oracles": [{"oracle_id": "o1", "risk_id": "r1", "confidence": 0.9, "sourceRef": "o:1", "rationale": "r", "verified": True}],
        "verification_commands": [{"command_id": "c1", "recommendation_id": "r1", "confidence": 0.9, "sourceRef": "c:1", "rationale": "r", "verified": True}],
        "actionable_taxonomy_used": True,
        "oracle_validation_enabled": True,
        "command_verification_enabled": False,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    assert report["overall_status"] == "hold"
    assert "test_recommendation_missing_verification_command" in _codes(report)


def test_test_recommendation_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["test-recommendation-report"] == "schemas/HATE/v1/test-recommendation-report.schema.json"