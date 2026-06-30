"""Tests for HATE-GAP-056 contradiction detection evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.analysis.contradiction_detection import (
    build_contradiction_report,
    evaluate_contradiction_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "contradiction-detection"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "contradiction-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "contradiction-report"
    assert report["overall_status"] in {"pass", "hold", "blocked"}
    assert report["readiness_effect"] in {"none", "hold", "blocked"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_056_fixture_paths_exist() -> None:
    assert (FIXTURES / "consistent-evidence-pass" / "fixture.json").is_file()
    assert (FIXTURES / "pass-with-critical-finding-blocked" / "fixture.json").is_file()


def test_consistent_evidence_fixture_passes() -> None:
    result = evaluate_contradiction_fixture(_fixture("consistent-evidence-pass"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_pass_with_critical_finding_fixture_holds() -> None:
    result = evaluate_contradiction_fixture(_fixture("pass-with-critical-finding-blocked"))

    assert result["status"] == "blocked"
    assert result["finding_code"] == "contradiction_pass_with_critical_finding_blocked"
    assert result["readiness_effect"] == "blocked"
    _assert_report_contract(result["report"])


def test_coverage_mutation_not_aligned_holds() -> None:
    report = build_contradiction_report({
        "contradictions": [{"contradiction_id": "c1", "contradiction_type": "coverage_mismatch", "severity": "high", "sourceRef": "c:1", "rationale": ""}],
        "blocking_effects": [],
        "claim_impacts": [],
        "pass_status_with_critical": False,
        "critical_finding_present": False,
        "coverage_mutation_aligned": False,
        "contract_schema_aligned": True,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_contradictions": 50, "max_blocking_effects": 20},
    })

    assert report["overall_status"] == "hold"
    assert "contradiction_coverage_up_mutation_down" in _codes(report)


def test_contract_schema_not_aligned_holds() -> None:
    report = build_contradiction_report({
        "contradictions": [{"contradiction_id": "c1", "contradiction_type": "schema_mismatch", "severity": "medium", "sourceRef": "c:1", "rationale": ""}],
        "blocking_effects": [],
        "claim_impacts": [],
        "pass_status_with_critical": False,
        "critical_finding_present": False,
        "coverage_mutation_aligned": True,
        "contract_schema_aligned": False,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_contradictions": 50, "max_blocking_effects": 20},
    })

    assert report["overall_status"] == "hold"
    assert "contradiction_contract_schema_conflict" in _codes(report)


def test_contradiction_without_source_ref_holds() -> None:
    report = build_contradiction_report({
        "contradictions": [{"contradiction_id": "c1", "contradiction_type": "verdict_mismatch", "severity": "high", "sourceRef": "", "rationale": ""}],
        "blocking_effects": [],
        "claim_impacts": [],
        "pass_status_with_critical": False,
        "critical_finding_present": False,
        "coverage_mutation_aligned": True,
        "contract_schema_aligned": True,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_contradictions": 50, "max_blocking_effects": 20},
    })

    assert report["overall_status"] == "hold"
    assert "contradiction_pass_with_critical_finding_blocked" in _codes(report)


def test_confidence_below_threshold_holds() -> None:
    report = build_contradiction_report({
        "contradictions": [],
        "blocking_effects": [],
        "claim_impacts": [],
        "pass_status_with_critical": False,
        "critical_finding_present": False,
        "coverage_mutation_aligned": True,
        "contract_schema_aligned": True,
        "confidence": 0.5,
        "limits": {"confidence_threshold": 0.7, "max_contradictions": 50, "max_blocking_effects": 20},
    })

    assert report["overall_status"] == "hold"
    assert "contradiction_pass_with_critical_finding_blocked" in _codes(report)


def test_contradiction_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["contradiction-report"] == "schemas/HATE/v1/contradiction-report.schema.json"
