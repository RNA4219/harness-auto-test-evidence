"""Tests for HATE-GAP-005 GitHub integration contract."""

from __future__ import annotations

import json
from pathlib import Path

from hate.github_integration import evaluate_github_integration, evaluate_github_integration_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "github"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "github-integration-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def test_pr_check_success_allows_safe_annotations() -> None:
    report = evaluate_github_integration_fixture(_fixture("pr-check-success"), source_version="test")

    assert report["record_type"] == "github-integration-report"
    assert report["status"] == "pass"
    assert report["readiness_effect"] == "none"
    assert report["surface"] == "check_run"
    assert report["audit_events"][0]["decision"] == "allow"
    assert report["findings"] == []


def test_permission_denied_is_structured_hold() -> None:
    report = evaluate_github_integration_fixture(_fixture("permission-denied"), source_version="test")

    assert report["status"] == "hold"
    assert report["finding_code"] == "github_permission_denied"
    assert "checks:write" not in report["permissions"]
    assert report["audit_events"][0]["decision"] == "deny"


def test_rerun_preserves_previous_run_link() -> None:
    report = evaluate_github_integration_fixture(_fixture("rerun-preserves-run-id-link"), source_version="test")

    assert report["status"] == "pass"
    assert report["run_id"] == "run-002"
    assert report["previous_run_id"] == "run-001"
    assert report["rerun_linked"] is True
    assert report["canonical_evidence_mutated"] is False


def test_unsafe_artifact_redacted_passes_without_raw_leak() -> None:
    report = evaluate_github_integration_fixture(_fixture("unsafe-artifact-redacted"), source_version="test")

    assert report["status"] == "pass"
    assert report["unsafe_artifact_count"] == 2
    assert report["redacted_annotation_count"] == 2
    assert report["findings"] == []


def test_broad_admin_permission_is_denied_for_normal_pr_loop() -> None:
    report = evaluate_github_integration_fixture(_fixture("broad-admin-permission-denied"), source_version="test")

    assert report["status"] == "hold"
    assert report["finding_code"] == "github_broad_permission_denied"
    assert "administration:write" in report["permissions"]


def test_unsafe_annotation_is_denied() -> None:
    report = evaluate_github_integration_fixture(_fixture("unsafe-annotation-denied"), source_version="test")

    assert report["status"] == "hold"
    assert report["finding_code"] == "github_unsafe_annotation_denied"
    assert report["unsafe_artifact_count"] == 1


def test_rerun_without_previous_link_is_denied() -> None:
    decision = evaluate_github_integration(
        {
            "surface": "workflow_run",
            "permissions": ["actions:read"],
            "rerun": True,
            "run_id": "run-002",
            "previous_run_id": "",
        }
    )

    assert decision.status == "hold"
    assert decision.findings[0].code == "github_rerun_missing_evidence_link"


def test_canonical_mutation_is_denied() -> None:
    decision = evaluate_github_integration(
        {
            "surface": "check_run",
            "permissions": ["checks:write", "pull-requests:read"],
            "canonical_evidence_mutated": True,
        }
    )

    assert decision.status == "hold"
    assert decision.findings[0].code == "github_canonical_mutation_denied"


def test_schema_registered_for_github_integration_report() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "github-integration-report"
    assert "canonical_evidence_mutated" in schema["required"]
    records = {record["record_type"]: record for record in registry["records"]}
    assert records["github-integration-report"]["schema"] == "schemas/HATE/v1/github-integration-report.schema.json"
    assert records["github-integration-report"]["phase"] == "P3"
    assert records["github-integration-report"]["unknown_field_policy"] == "warn"
