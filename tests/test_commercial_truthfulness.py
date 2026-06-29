"""UAT tests for commercial truthfulness gates."""

from __future__ import annotations

import json
from pathlib import Path

from hate.commercial import build_commercial_truthfulness_report, evaluate_claim


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "commercial" / "truthfulness"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "HATE" / "v1" / "commercial-truthfulness-report.schema.json"
REGISTRY_PATH = Path(__file__).resolve().parents[1] / "schemas" / "HATE" / "v1" / "schema-registry.json"


def load_fixture(name: str) -> dict:
    with (FIXTURE_ROOT / name / "fixture.json").open(encoding="utf-8") as f:
        return json.load(f)


def test_packet_fixture_paths_exist() -> None:
    for name in [
        "supported-security-claim",
        "supported-scale-claim",
        "unsupported-enterprise-claim",
        "unsupported-release-claim",
        "manual-waiver-attempt",
        "evidence-missing-source-ref",
    ]:
        assert (FIXTURE_ROOT / name / "fixture.json").exists()


def test_supported_security_claim_passes_with_evidence() -> None:
    fixture = load_fixture("supported-security-claim")
    decision = evaluate_claim(**fixture["input"]).to_dict()

    assert decision["readiness_effect"] == "pass"
    assert decision["observed_evidence"] == decision["required_evidence"]
    assert decision["evidence_report_refs"] == decision["required_evidence"]
    assert decision["source_contract_refs"]
    assert decision["implementation_refs"]
    assert decision["release_eligible"] is True
    assert decision["blocker_state"] == "none"
    assert decision["reason"] == "claim_supported_by_evidence"
    assert decision["procurement_response_text"].startswith("Implemented and evidence-backed")


def test_supported_scale_claim_passes_with_evidence() -> None:
    fixture = load_fixture("supported-scale-claim")
    decision = evaluate_claim(**fixture["input"]).to_dict()

    assert decision["readiness_effect"] == "pass"
    assert "scale-performance-report" in decision["observed_evidence"]


def test_unsupported_enterprise_claim_is_hard_dq_when_worded_available() -> None:
    fixture = load_fixture("unsupported-enterprise-claim")
    decision = evaluate_claim(**fixture["input"]).to_dict()

    assert decision["readiness_effect"] == "hard_dq"
    assert decision["release_eligible"] is False
    assert decision["blocker_state"] == "hard_dq"
    assert any(f["code"] == "planned_or_unsupported_claim_marked_available" for f in decision["findings"])
    assert any(f["code"] == "unsupported_critical_claim" for f in decision["findings"])


def test_unsupported_release_claim_is_hard_dq() -> None:
    fixture = load_fixture("unsupported-release-claim")
    decision = evaluate_claim(**fixture["input"]).to_dict()

    assert decision["decision"] == "blocked"
    assert decision["readiness_effect"] == "hard_dq"


def test_manual_review_cannot_auto_waive_unsupported_claim() -> None:
    fixture = load_fixture("manual-waiver-attempt")
    decision = evaluate_claim(**fixture["input"]).to_dict()

    assert decision["manual_review_refs"] == ["manual-review-claim-001"]
    assert any(f["code"] == "manual_review_cannot_waive_unsupported_claim" for f in decision["findings"])


def test_missing_source_ref_is_hold_even_with_evidence() -> None:
    fixture = load_fixture("evidence-missing-source-ref")
    decision = evaluate_claim(**fixture["input"]).to_dict()

    assert decision["readiness_effect"] == "hold"
    assert decision["findings"][0]["code"] == "claim_missing_source_ref"


def test_report_aggregates_claims_and_findings() -> None:
    report = build_commercial_truthfulness_report({
        "profile": "release",
        "claims": [
            load_fixture("supported-security-claim")["input"]["claim"],
            load_fixture("unsupported-release-claim")["input"]["claim"],
        ],
        "evidence_records": load_fixture("supported-security-claim")["input"]["evidence_records"],
    })

    assert report["record_type"] == "commercial-truthfulness-report"
    assert report["summary"]["claim_count"] == 2
    assert report["summary"]["readiness_effect"] == "hard_dq"
    assert report["summary"]["supported_claim_count"] == 1
    assert report["summary"]["release_eligible_claim_count"] == 1


def test_schema_and_registry_define_commercial_truthfulness_report() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "commercial-truthfulness-report"
    assert "commercial_claim_decision" in schema["$defs"]
    required = set(schema["$defs"]["commercial_claim_decision"]["required"])
    assert {
        "surface",
        "source_contract_refs",
        "implementation_refs",
        "evidence_report_refs",
        "release_eligible",
        "blocker_state",
        "procurement_response_text",
    }.issubset(required)
    records = {item["record_type"]: item["schema"] for item in registry["records"]}
    assert records["commercial-truthfulness-report"] == "schemas/HATE/v1/commercial-truthfulness-report.schema.json"
