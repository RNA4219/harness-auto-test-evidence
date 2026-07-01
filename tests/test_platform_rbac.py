"""Tests for platform RBAC matrix decisions."""

from __future__ import annotations

import json
from pathlib import Path

from hate.p0a_schema import _validate_schema_value
from hate.platform_rbac import build_platform_rbac_report


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "platform" / "rbac"
SCHEMAS = ROOT / "schemas" / "HATE" / "v1"


def test_platform_rbac_fixture_paths_exist() -> None:
    for name in [
        "admin-policy-change",
        "developer-debt-accept-denied",
        "auditor-read-only",
        "cross-tenant-hidden",
        "raw-artifact-approval",
        "raw-artifact-missing-approval",
    ]:
        assert (FIXTURES / name / "fixture.json").exists()


def test_admin_policy_change_is_allowed() -> None:
    fixture = _fixture("admin-policy-change")

    report = build_platform_rbac_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["decision"]["decision"] == fixture["expected"]["decision"]
    assert report["decision"]["reason"] == fixture["expected"]["reason"]
    assert report["decision"]["http_status"] == fixture["expected"]["http_status"]


def test_developer_debt_accept_is_denied() -> None:
    fixture = _fixture("developer-debt-accept-denied")

    report = build_platform_rbac_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["decision"]["decision"] == fixture["expected"]["decision"]
    assert report["decision"]["reason"] == fixture["expected"]["reason"]
    assert report["decision"]["restricted_payload_loaded"] is False


def test_auditor_is_read_only() -> None:
    fixture = _fixture("auditor-read-only")

    report = build_platform_rbac_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["decision"]["decision"] == fixture["expected"]["decision"]
    assert report["decision"]["reason"] == fixture["expected"]["reason"]


def test_cross_tenant_resource_is_hidden_without_leaking_raw_path() -> None:
    fixture = _fixture("cross-tenant-hidden")

    report = build_platform_rbac_report(fixture["input"], fixture["fixture_id"])
    denial = report["decision"]["denial_record"]

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["decision"]["decision"] == fixture["expected"]["decision"]
    assert report["decision"]["reason"] == fixture["expected"]["reason"]
    assert report["decision"]["http_status"] == fixture["expected"]["http_status"]
    assert report["decision"]["tenant_visible"] is fixture["expected"]["tenant_visible"]
    assert denial["resource_id"] == fixture["expected"]["safe_resource_id"]
    assert "C:\\" not in str(denial)
    assert "secret" not in str(denial).lower()


def test_raw_artifact_access_requires_approval_purpose_expiry_and_audit() -> None:
    fixture = _fixture("raw-artifact-approval")

    report = build_platform_rbac_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["decision"]["decision"] == fixture["expected"]["decision"]
    assert report["decision"]["reason"] == fixture["expected"]["reason"]
    assert report["decision"]["raw_artifact_returned"] is fixture["expected"]["raw_artifact_returned"]


def test_raw_artifact_access_denies_missing_approval_event() -> None:
    fixture = _fixture("raw-artifact-missing-approval")

    report = build_platform_rbac_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["decision"]["decision"] == fixture["expected"]["decision"]
    assert report["decision"]["reason"] == fixture["expected"]["reason"]
    assert report["decision"]["raw_artifact_returned"] is fixture["expected"]["raw_artifact_returned"]


def test_viewer_never_receives_raw_artifact_body() -> None:
    fixture = _fixture("raw-artifact-approval")
    fixture["input"]["request"]["actor"]["role"] = "viewer"

    report = build_platform_rbac_report(fixture["input"], "viewer-raw-denied")

    assert report["overall_status"] == "pass"
    assert report["decision"]["decision"] == "deny"
    assert report["decision"]["reason"] == "raw_artifact_role_denied"
    assert report["decision"]["raw_artifact_returned"] is False


def test_platform_rbac_schema_registered() -> None:
    schema = json.loads((SCHEMAS / "platform-rbac-matrix-report.schema.json").read_text(encoding="utf-8"))
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "platform-rbac-matrix-report"
    assert any(record["record_type"] == "platform-rbac-matrix-report" for record in registry["records"])


def test_platform_rbac_report_matches_artifact_schema() -> None:
    schema = json.loads((SCHEMAS / "platform-rbac-matrix-report.schema.json").read_text(encoding="utf-8"))

    for fixture_name in ["admin-policy-change", "cross-tenant-hidden"]:
        fixture = _fixture(fixture_name)
        report = build_platform_rbac_report(fixture["input"], fixture["fixture_id"])
        assert _validate_schema_value(report, schema, "$") == []


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))
