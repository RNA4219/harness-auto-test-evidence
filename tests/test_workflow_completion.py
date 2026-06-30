"""Tests for HATE-GAP-026 workflow completion governance evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.workflow_completion import build_completion_governance_report, evaluate_completion_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "workflow" / "completion"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "workflow-completion-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "workflow-completion-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_026_fixture_paths_exist() -> None:
    assert (FIXTURES / "scope-safe" / "fixture.json").is_file()
    assert (FIXTURES / "overclaim-detected" / "fixture.json").is_file()


def test_scope_safe_fixture_passes() -> None:
    result = evaluate_completion_fixture(_fixture("scope-safe"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_overclaim_detected_fixture_holds() -> None:
    result = evaluate_completion_fixture(_fixture("overclaim-detected"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "completion_overclaim_detected"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_unknown_completion_claim_holds() -> None:
    report = build_completion_governance_report({
        "completion_claim": {
            "claim": "hosted-ready",
            "scope": "hosted claims",
            "evidence_refs": ["docs/process/WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md"],
        }
    })

    assert report["overall_status"] == "hold"
    assert "completion_claim_unknown" in _codes(report)


def test_implemented_claim_requires_artifacts_and_tests() -> None:
    report = build_completion_governance_report({
        "completion_claim": {
            "claim": "implemented",
            "scope": "GAP-026",
            "evidence_refs": ["src/hate/workflow_completion.py"],
            "code_schema_fixtures_tests_docs_exist": True,
            "tests_pass": False,
        }
    })

    assert report["overall_status"] == "hold"
    assert "completion_implemented_without_artifacts" in _codes(report)


def test_accepted_claim_requires_approved_record() -> None:
    report = build_completion_governance_report({
        "completion_claim": {
            "claim": "accepted",
            "scope": "GAP-026",
            "evidence_refs": ["docs/acceptance/AC-20260630-01.md"],
            "acceptance_record_approved": False,
        }
    })

    assert report["overall_status"] == "hold"
    assert "completion_accepted_without_record" in _codes(report)


def test_product_ready_claim_can_pass_when_all_gates_are_present() -> None:
    report = build_completion_governance_report({
        "completion_claim": {
            "claim": "product-ready",
            "scope": "all product gates",
            "evidence_refs": ["fixtures/gap-closure/expected/gap-closure-report.json"],
            "acceptance_record_approved": True,
            "product_gates_pass": True,
            "release_evidence_matches": True,
        }
    })

    assert report["overall_status"] == "pass"
    assert _codes(report) == []


def test_completion_no_go_checks_are_reported() -> None:
    report = build_completion_governance_report({
        "completion_claim": {
            "claim": "specified",
            "scope": "GAP-026",
            "evidence_refs": ["docs/process/WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md"],
            "done_task_missing_acceptance": True,
            "stale_completion_record": True,
            "release_evidence_matches": False,
            "scope_broader_than_verification": True,
            "generated_artifact_changed_without_birdseye_refresh": True,
        }
    })

    assert report["overall_status"] == "hold"
    assert "completion_done_task_missing_acceptance" in _codes(report)
    assert "completion_record_stale" in _codes(report)
    assert "completion_release_evidence_mismatch" in _codes(report)
    assert "completion_scope_broader_than_verification" in _codes(report)
    assert "completion_generated_artifact_without_birdseye_refresh" in _codes(report)


def test_completion_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["workflow-completion-report"] == "schemas/HATE/v1/workflow-completion-report.schema.json"
