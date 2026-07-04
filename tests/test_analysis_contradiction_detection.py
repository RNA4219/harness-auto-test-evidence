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
    assert "contradiction_diagnostics" in report
    assert {
        "evidence_record_count",
        "derived_contradiction_count",
        "blocked_claim_reference_count",
        "duplicate_contradiction_count",
    } <= set(report["summary"])
    assert {
        "derived_contradictions",
        "blocked_claim_refs",
        "duplicate_contradiction_ids",
        "missing_source_ref_ids",
    } <= set(report["contradiction_diagnostics"])
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


def test_pass_with_critical_is_inferred_from_evidence_records() -> None:
    report = build_contradiction_report({
        "contradictions": [],
        "blocking_effects": [],
        "claim_impacts": [],
        "evidence_records": [
            {
                "record_id": "ev-critical",
                "record_type": "test_result",
                "status": "pass",
                "severity": "critical",
                "readiness_effect": "none",
                "sourceRef": "evidence:critical",
            }
        ],
        "pass_status_with_critical": False,
        "critical_finding_present": False,
        "coverage_mutation_aligned": True,
        "contract_schema_aligned": True,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_contradictions": 50, "max_blocking_effects": 20},
    })

    assert report["overall_status"] == "blocked"
    assert "contradiction_pass_with_critical_finding_blocked" in _codes(report)
    assert report["summary"]["derived_contradiction_count"] == 1


def test_coverage_up_mutation_down_is_inferred_for_same_requirement() -> None:
    report = build_contradiction_report({
        "contradictions": [],
        "blocking_effects": [],
        "claim_impacts": [],
        "evidence_records": [
            {
                "record_id": "coverage",
                "record_type": "metric",
                "metric_type": "coverage",
                "requirement_ref": "REQ-1",
                "baseline_value": 0.80,
                "current_value": 0.95,
                "sourceRef": "metric:coverage",
            },
            {
                "record_id": "mutation",
                "record_type": "metric",
                "metric_type": "mutation",
                "requirement_ref": "REQ-1",
                "baseline_value": 0.70,
                "current_value": 0.40,
                "sourceRef": "metric:mutation",
            },
        ],
        "pass_status_with_critical": False,
        "critical_finding_present": False,
        "coverage_mutation_aligned": True,
        "contract_schema_aligned": True,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_contradictions": 50, "max_blocking_effects": 20},
    })

    assert report["overall_status"] == "hold"
    assert "contradiction_coverage_up_mutation_down" in _codes(report)
    assert report["contradiction_diagnostics"]["derived_contradictions"][0]["subject_ref"] == "REQ-1"


def test_contract_schema_conflict_is_inferred_from_evidence_versions() -> None:
    report = build_contradiction_report({
        "contradictions": [],
        "blocking_effects": [],
        "claim_impacts": [],
        "evidence_records": [
            {
                "record_id": "contract-1",
                "record_type": "contract_check",
                "status": "pass",
                "schema_version": "HATE/v2",
                "expected_schema_version": "HATE/v1",
                "sourceRef": "contract:1",
            }
        ],
        "pass_status_with_critical": False,
        "critical_finding_present": False,
        "coverage_mutation_aligned": True,
        "contract_schema_aligned": True,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_contradictions": 50, "max_blocking_effects": 20},
    })

    assert report["overall_status"] == "hold"
    assert "contradiction_contract_schema_conflict" in _codes(report)


def test_release_claim_using_blocked_evidence_blocks() -> None:
    report = build_contradiction_report({
        "contradictions": [],
        "blocking_effects": [],
        "claim_impacts": [],
        "evidence_records": [
            {
                "record_id": "ev-blocked",
                "record_type": "finding",
                "status": "blocked",
                "readiness_effect": "blocked",
                "sourceRef": "finding:blocked",
            }
        ],
        "release_claims": [
            {
                "claim_id": "release-ready",
                "status": "ready",
                "evidence_refs": ["ev-blocked"],
                "sourceRef": "claim:release",
            }
        ],
        "pass_status_with_critical": False,
        "critical_finding_present": False,
        "coverage_mutation_aligned": True,
        "contract_schema_aligned": True,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_contradictions": 50, "max_blocking_effects": 20},
    })

    assert report["overall_status"] == "blocked"
    assert "contradiction_release_claim_uses_blocked_evidence" in _codes(report)
    assert report["contradiction_diagnostics"]["blocked_claim_refs"] == ["release-ready"]


def test_duplicate_and_budget_excess_holds() -> None:
    report = build_contradiction_report({
        "contradictions": [
            {"contradiction_id": "dup", "contradiction_type": "verdict_mismatch", "severity": "high", "sourceRef": "c:1", "rationale": ""},
            {"contradiction_id": "dup", "contradiction_type": "verdict_mismatch", "severity": "high", "sourceRef": "c:2", "rationale": ""},
        ],
        "blocking_effects": [
            {"effect_id": "b1", "effect_type": "claim_block", "blocked_claim": "claim-1", "sourceRef": "b:1"},
            {"effect_id": "b2", "effect_type": "claim_block", "blocked_claim": "claim-2", "sourceRef": "b:2"},
        ],
        "claim_impacts": [
            {"claim_id": "i1", "impact_type": "overclaim", "impact_severity": "high", "sourceRef": "i:1"},
            {"claim_id": "i2", "impact_type": "overclaim", "impact_severity": "high", "sourceRef": "i:2"},
        ],
        "pass_status_with_critical": False,
        "critical_finding_present": False,
        "coverage_mutation_aligned": True,
        "contract_schema_aligned": True,
        "confidence": 0.95,
        "limits": {
            "confidence_threshold": 0.7,
            "max_contradictions": 1,
            "max_blocking_effects": 1,
            "max_claim_impacts": 1,
        },
    })

    assert report["overall_status"] == "hold"
    assert "contradiction_duplicate_id" in _codes(report)
    assert "contradiction_budget_exceeded" in _codes(report)
    assert "contradiction_blocking_effect_budget_exceeded" in _codes(report)
    assert "contradiction_claim_impact_budget_exceeded" in _codes(report)


def test_contradiction_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["contradiction-report"] == "schemas/HATE/v1/contradiction-report.schema.json"
