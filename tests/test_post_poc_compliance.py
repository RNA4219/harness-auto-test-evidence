from __future__ import annotations

import json
from pathlib import Path

from hate.post_poc.compliance import build_compliance_report, evaluate_compliance_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc" / "compliance"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "compliance-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "compliance-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert report["compliance_evidence_pack"]["record_type"] == "compliance-evidence-pack"
    assert report["procurement_questionnaire_export"]["record_type"] == "procurement-questionnaire-export"
    for claim in report["control_claims"]:
        assert claim["record_type"] == "control-claim-record"
        assert {"control_id", "claim_class", "claim_text", "evidence_refs", "expires_at"} <= set(claim)
    for decision in report["review_decisions"]:
        assert decision["record_type"] == "compliance-review-decision"
        assert {"control_id", "reviewer", "review_status", "reviewed_at", "expires_at"} <= set(decision)
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_task_postpoc_014_canonical_fixture_paths_exist() -> None:
    for name in [
        "procurement-pack-valid",
        "control-evidence-missing",
        "stale-control-claim",
        "reviewer-missing",
        "restricted-export-denied",
    ]:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_procurement_pack_valid_passes_and_links_claims_to_evidence() -> None:
    result = evaluate_compliance_fixture(_fixture("procurement-pack-valid"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["report"]["summary"]["customer_safe_export"] is True
    assert all(claim["evidence_refs"] for claim in result["report"]["control_claims"])
    _assert_report_contract(result["report"])


def test_control_evidence_missing_holds() -> None:
    result = evaluate_compliance_fixture(_fixture("control-evidence-missing"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "compliance_control_evidence_missing"


def test_stale_control_claim_holds() -> None:
    result = evaluate_compliance_fixture(_fixture("stale-control-claim"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "compliance_claim_stale"


def test_reviewer_missing_holds() -> None:
    result = evaluate_compliance_fixture(_fixture("reviewer-missing"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "compliance_reviewer_missing"


def test_restricted_export_denied() -> None:
    result = evaluate_compliance_fixture(_fixture("restricted-export-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "compliance_export_contains_restricted_data"
    assert result["report"]["summary"]["restricted_data_present"] is True


def test_procurement_answer_without_support_holds() -> None:
    report = build_compliance_report({
        "claims": [
            {
                "control_id": "CTRL-DATA-001",
                "claim_class": "data_flow",
                "claim_text": "Data flow claim is unsupported.",
                "evidence_refs": ["evidence://data/flow"],
                "expires_at": "2026-12-31T00:00:00Z",
                "supported": False,
            }
        ],
        "decisions": [
            {
                "control_id": "CTRL-DATA-001",
                "reviewer": "compliance-owner",
                "review_status": "approved",
                "reviewed_at": "2026-07-03T02:00:00Z",
                "expires_at": "2026-12-31T00:00:00Z",
            }
        ],
        "export": {"customer_safe_export": True, "redaction_report_ref": "artifact://redaction/data", "restricted_data_present": False},
    })

    assert report["overall_status"] == "hold"
    assert "procurement_answer_unsupported" in _codes(report)


def test_review_decision_expiry_holds() -> None:
    report = build_compliance_report({
        "claims": [
            {
                "control_id": "CTRL-VULN-001",
                "claim_class": "vulnerability_response",
                "claim_text": "Vulnerability response is documented.",
                "evidence_refs": ["evidence://security/vuln-response"],
                "expires_at": "2026-12-31T00:00:00Z",
            }
        ],
        "decisions": [
            {
                "control_id": "CTRL-VULN-001",
                "reviewer": "security-owner",
                "review_status": "approved",
                "reviewed_at": "2026-01-01T02:00:00Z",
                "expires_at": "2026-01-02T00:00:00Z",
            }
        ],
        "export": {"customer_safe_export": True, "redaction_report_ref": "artifact://redaction/vuln", "restricted_data_present": False},
    })

    assert report["overall_status"] == "hold"
    assert "compliance_claim_stale" in _codes(report)


def test_compliance_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["compliance-report"] == "schemas/HATE/v1/compliance-report.schema.json"
