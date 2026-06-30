"""Tests for HATE-GAP-020 product E2E UAT journey evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.product_e2e import build_product_e2e_report, evaluate_product_e2e_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "e2e"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "product-e2e-uat-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


CANONICAL_FIXTURES = {
    "developer-pr-loop": ("pass", ""),
    "developer-pr-loop/parser-failure": ("hold", "e2e_developer_parser_failure"),
    "qa-risk-review": ("pass", ""),
    "qa-risk-review/no-oracle": ("hold", "e2e_qa_risk_without_oracle"),
    "release-review": ("pass", ""),
    "release-review/qeg-invalid": ("hold", "e2e_release_qeg_approval_overclaim"),
    "admin-governance": ("pass", ""),
    "admin-governance/rbac-denied": ("hold", "e2e_admin_rbac_denied"),
    "security-quarantine": ("pass", ""),
    "security-quarantine/block": ("hold", "e2e_security_quarantine_block"),
    "support-triage": ("pass", ""),
    "support-triage/raw-artifact-denied": ("hold", "e2e_support_raw_artifact_denied"),
}


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "product-e2e-uat-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert isinstance(report["journeys"], list)
    assert set(schema["properties"]["journeys"]["items"]["required"]) <= set(report["journeys"][0])
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "journey", "readiness_effect"} <= set(finding)


def test_canonical_gap_020_fixture_paths_exist() -> None:
    for name in CANONICAL_FIXTURES:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_all_canonical_fixtures_match_expected_status_and_finding() -> None:
    for name, (expected_status, expected_code) in CANONICAL_FIXTURES.items():
        result = evaluate_product_e2e_fixture(_fixture(name))

        assert result["status"] == expected_status
        assert result["finding_code"] == expected_code
        assert result["readiness_effect"] == ("hold" if expected_status == "hold" else "none")
        _assert_report_contract(result["report"])


def test_required_uat_evidence_is_enforced() -> None:
    report = build_product_e2e_report({
        "journey": "developer_pr_loop",
        "precheck": "eligible",
        "emitted_evidence": ["product-e2e-uat-report.json"],
    })

    assert report["overall_status"] == "hold"
    assert "e2e_required_evidence_missing" in _codes(report)


def test_visual_evidence_is_required_for_ui_involved_journey() -> None:
    report = build_product_e2e_report({
        "journey": "release_review",
        "release_pack_status": "ready",
        "qeg_claim": "advisory_only",
        "visual_evidence": False,
    })

    assert report["overall_status"] == "hold"
    assert "e2e_visual_evidence_missing" in _codes(report)


def test_happy_path_only_is_hold() -> None:
    report = build_product_e2e_report({
        "journey": "qa_risk_review",
        "risk_count": 1,
        "oracle_count": 1,
        "has_negative_case": False,
    })

    assert report["overall_status"] == "hold"
    assert "e2e_happy_path_only" in _codes(report)


def test_admin_governance_requires_rbac_negative_case() -> None:
    report = build_product_e2e_report({
        "journey": "admin_governance",
        "role": "admin",
        "action": "update_policy",
        "rbac_negative_case": False,
    })

    assert report["overall_status"] == "hold"
    assert "e2e_rbac_negative_missing" in _codes(report)


def test_admin_governance_requires_audit_event() -> None:
    report = build_product_e2e_report({
        "journey": "admin_governance",
        "role": "admin",
        "action": "update_policy",
        "audit_event": False,
    })

    assert report["overall_status"] == "hold"
    assert "e2e_admin_audit_event_missing" in _codes(report)


def test_support_scope_safety_blocks_secret_pii_and_customer_source() -> None:
    report = build_product_e2e_report({
        "journey": "support_triage",
        "diagnostic_bundle": "safe",
        "raw_artifact_export": False,
        "exposes_secret": True,
    })

    assert report["overall_status"] == "hold"
    assert "e2e_scope_safety_violation" in _codes(report)


def test_full_six_journey_positive_suite_can_pass() -> None:
    report = build_product_e2e_report({
        "journeys": [
            _fixture("developer-pr-loop")["input"],
            _fixture("qa-risk-review")["input"],
            _fixture("release-review")["input"],
            _fixture("admin-governance")["input"],
            _fixture("security-quarantine")["input"],
            _fixture("support-triage")["input"],
        ],
    })

    assert report["overall_status"] == "pass"
    assert report["findings"] == []
    assert report["summary"]["journey_count"] == 6


def test_unknown_journey_holds() -> None:
    report = build_product_e2e_report({"journey": "unknown"})

    assert report["overall_status"] == "hold"
    assert "e2e_unknown_journey" in _codes(report)


def test_product_e2e_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["product-e2e-uat-report"] == "schemas/HATE/v1/product-e2e-uat-report.schema.json"
