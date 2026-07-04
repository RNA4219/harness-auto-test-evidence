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
    assert isinstance(report["derived_recommendations"], list)
    assert {
        "derived_recommendations",
        "recommendations_missing_command",
        "recommendations_missing_oracle",
        "missing_source_ref_ids",
        "stale_or_generic_recommendation_ids",
    } <= set(report["test_recommendation_diagnostics"])
    assert {
        "signal_count",
        "derived_recommendation_count",
        "missing_command_count",
        "missing_oracle_count",
    } <= set(report["summary"])
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


def test_recommendations_are_derived_from_signals() -> None:
    report = build_test_recommendation_report({
        "signals": [
            {"signal_id": "sig-oracle", "signal_type": "no_oracle", "risk_id": "risk:payment", "sourceRef": "risk:payment"},
            {"signal_id": "sig-flaky", "signal_type": "mixed_outcome", "test_id": "test:retry", "sourceRef": "test:retry"},
            {"signal_id": "sig-impact", "signal_type": "affected_test", "test_id": "test:impact", "sourceRef": "test:impact"},
            {"signal_id": "sig-review", "signal_type": "manual_review_required", "risk_id": "risk:manual", "sourceRef": "risk:manual"},
            {"signal_id": "sig-mutation", "signal_type": "mutation_survived", "requirement_id": "req:oracle", "sourceRef": "req:oracle"},
        ],
        "actionable_taxonomy_used": True,
        "oracle_validation_enabled": True,
        "command_verification_enabled": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    actions = {item["action"] for item in report["derived_recommendations"]}
    commands = {item["verification_command"] for item in report["derived_recommendations"]}
    assert report["overall_status"] == "pass"
    assert actions == {"add_or_modify_test", "rerun_test", "manual_review", "add_test"}
    assert "run targeted test with oracle" in commands
    assert report["summary"]["signal_count"] == 5
    assert report["summary"]["derived_recommendation_count"] == 5
    _assert_report_contract(report)


def test_missing_command_or_oracle_and_source_ref_holds() -> None:
    report = build_test_recommendation_report({
        "recommendations": [{
            "recommendation_id": "rec:checkout",
            "action": "add_or_modify_test",
            "target": "test:checkout",
            "required_oracle_id": "oracle:checkout",
            "confidence": 0.9,
            "rationale": "Critical checkout risk needs executable oracle.",
            "actionable": True,
        }],
        "required_oracles": [],
        "verification_commands": [],
        "actionable_taxonomy_used": True,
        "oracle_validation_enabled": True,
        "command_verification_enabled": True,
        "confidence": 0.9,
        "limits": {"confidence_threshold": 0.7},
    })

    codes = _codes(report)
    assert report["overall_status"] == "hold"
    assert "test_recommendation_missing_verification_command" in codes
    assert "test_recommendation_missing_required_oracle" in codes
    assert "test_recommendation_source_ref_missing" in codes
    assert report["summary"]["missing_command_count"] == 1
    assert report["summary"]["missing_oracle_count"] == 1
    _assert_report_contract(report)


def test_generic_signal_and_budget_excess_holds() -> None:
    report = build_test_recommendation_report({
        "recommendations": [
            {"recommendation_id": "rec:1", "action": "rerun_test", "target": "test:1", "confidence": 0.9, "sourceRef": "test:1", "rationale": "r", "actionable": True},
            {"recommendation_id": "rec:2", "action": "rerun_test", "target": "test:2", "confidence": 0.9, "sourceRef": "test:2", "rationale": "r", "actionable": True},
        ],
        "required_oracles": [
            {"oracle_id": "oracle:1", "risk_id": "risk:1", "confidence": 0.9, "sourceRef": "oracle:1", "rationale": "r", "verified": True},
            {"oracle_id": "oracle:2", "risk_id": "risk:2", "confidence": 0.9, "sourceRef": "oracle:2", "rationale": "r", "verified": True},
        ],
        "verification_commands": [
            {"command_id": "cmd:1", "recommendation_id": "rec:1", "confidence": 0.9, "sourceRef": "cmd:1", "rationale": "r", "verified": True},
            {"command_id": "cmd:2", "recommendation_id": "rec:2", "confidence": 0.9, "sourceRef": "cmd:2", "rationale": "r", "verified": True},
        ],
        "signals": [{"signal_id": "sig:unknown", "signal_type": "unclear_signal", "test_id": "test:unknown", "sourceRef": "test:unknown"}],
        "actionable_taxonomy_used": True,
        "oracle_validation_enabled": True,
        "command_verification_enabled": True,
        "confidence": 0.9,
        "limits": {
            "confidence_threshold": 0.7,
            "max_recommendations": 1,
            "max_oracles": 1,
            "max_commands": 1,
        },
    })

    codes = _codes(report)
    assert report["overall_status"] == "hold"
    assert "test_recommendation_generic_advice_denied" in codes
    assert "test_recommendation_budget_exceeded" in codes
    assert "test_recommendation_oracle_budget_exceeded" in codes
    assert "test_recommendation_command_budget_exceeded" in codes
    _assert_report_contract(report)


def test_test_recommendation_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["test-recommendation-report"] == "schemas/HATE/v1/test-recommendation-report.schema.json"
