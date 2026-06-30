"""Tests for HATE-GAP-013 agent quality evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.evaluation import build_agent_quality_report, evaluate_agent_quality_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "fixtures" / "evaluation" / "agent-quality"
SCHEMA_PATH = ROOT / "schemas" / "HATE" / "v1" / "agent-quality-report.schema.json"
REGISTRY_PATH = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name / "fixture.json").read_text(encoding="utf-8"))


def test_contract_fixture_paths_exist() -> None:
    for name in ["oracle-backed", "avoidance-detected"]:
        assert (FIXTURE_ROOT / name / "fixture.json").exists()


def test_oracle_backed_agent_output_passes() -> None:
    fixture = load_fixture("oracle-backed")

    result = evaluate_agent_quality_fixture(fixture)
    report = build_agent_quality_report(fixture["input"], fixture["fixture_id"])

    assert result["status"] == fixture["expected"]["status"]
    assert result["finding_code"] == ""
    assert report["overall_status"] == "pass"
    assert report["score"] == 1.0
    assert report["summary"]["oracle_count"] == 1


def test_avoidance_signal_holds_with_expected_code() -> None:
    fixture = load_fixture("avoidance-detected")

    result = evaluate_agent_quality_fixture(fixture)
    report = build_agent_quality_report(fixture["input"], fixture["fixture_id"])

    assert result["status"] == fixture["expected"]["status"]
    assert result["finding_code"] == fixture["expected"]["finding_code"]
    assert report["overall_status"] == "hold"
    assert report["summary"]["manual_review_required"] is True
    assert report["findings"][0]["code"] == "agent_quality_avoidance_detected"


def test_missing_oracle_invalid_reviewer_and_retention_are_hold_findings() -> None:
    report = build_agent_quality_report({
        "agent_output": {
            "oracle_refs": [],
            "reviewer_decision": "auto_waived",
            "retained": False,
            "retention_days": 0,
        }
    })

    codes = {finding["code"] for finding in report["findings"]}
    assert report["overall_status"] == "hold"
    assert "agent_quality_oracle_missing" in codes
    assert "agent_quality_reviewer_decision_invalid" in codes
    assert "agent_quality_retention_missing" in codes


def test_reviewer_needs_review_requires_record_ref() -> None:
    report = build_agent_quality_report({
        "agent_output": {
            "oracle_refs": ["contract_check"],
            "reviewer_decision": "needs_review",
        }
    })

    assert report["overall_status"] == "hold"
    assert report["findings"][0]["code"] == "agent_quality_reviewer_record_missing"


def test_schema_and_registry_contract() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "agent-quality-report"
    assert set(schema["required"]) >= {"score", "dimensions", "reviewer", "retention"}
    assert any(record["record_type"] == "agent-quality-report" for record in registry["records"])
