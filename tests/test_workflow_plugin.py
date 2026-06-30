"""Tests for HATE-GAP-025 workflow plugin integration evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.workflow_plugin import build_workflow_plugin_report, evaluate_workflow_plugin_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "workflow" / "plugin"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "workflow-plugin-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "workflow-plugin-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_025_fixture_paths_exist() -> None:
    assert (FIXTURES / "cross-repo-valid" / "fixture.json").is_file()
    assert (FIXTURES / "task-acceptance-drift" / "fixture.json").is_file()


def test_cross_repo_valid_fixture_passes() -> None:
    result = evaluate_workflow_plugin_fixture(_fixture("cross-repo-valid"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_task_acceptance_drift_fixture_holds() -> None:
    result = evaluate_workflow_plugin_fixture(_fixture("task-acceptance-drift"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "workflow_task_acceptance_drift"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_cross_repo_config_holds() -> None:
    report = build_workflow_plugin_report({"plugin_config": {"repositories": ["harness-auto-test-evidence"]}})

    assert report["overall_status"] == "hold"
    assert "workflow_plugin_cross_repo_config_missing" in _codes(report)


def test_missing_required_surfaces_hold() -> None:
    report = build_workflow_plugin_report({"plugin_config": {"repositories": ["hate", "workflow-cookbook"]}})

    assert report["overall_status"] == "hold"
    assert "workflow_plugin_task_sync_missing" in _codes(report)
    assert "workflow_plugin_acceptance_sync_missing" in _codes(report)
    assert "workflow_plugin_docs_stale_check_missing" in _codes(report)
    assert "workflow_plugin_schema_invalid" in _codes(report)


def test_missing_reference_holds() -> None:
    report = build_workflow_plugin_report({
        "plugin_config": {
            "repositories": ["hate", "workflow-cookbook"],
            "task_sync": True,
            "acceptance_sync": True,
            "docs_stale_check": True,
            "schema_valid": True,
            "missing_acceptance": ["AC-HATE-GAP-025"],
        }
    })

    assert report["overall_status"] == "hold"
    assert "workflow_plugin_missing_reference" in _codes(report)


def test_product_ready_claim_with_stale_docs_holds() -> None:
    report = build_workflow_plugin_report({
        "plugin_config": {
            "repositories": ["hate", "workflow-cookbook"],
            "task_sync": True,
            "acceptance_sync": True,
            "docs_stale_check": True,
            "schema_valid": True,
            "product_ready_claim": True,
        },
        "sync_result": {"docs_stale": True},
    })

    assert report["overall_status"] == "hold"
    assert "workflow_plugin_docs_stale_ignored" in _codes(report)


def test_evidence_bridge_surface_is_required() -> None:
    report = build_workflow_plugin_report({
        "plugin_config": {
            "repositories": ["hate", "workflow-cookbook"],
            "task_sync": True,
            "acceptance_sync": True,
            "docs_stale_check": True,
            "schema_valid": True,
            "evidence_bridge": False,
        }
    })

    assert report["overall_status"] == "hold"
    assert "workflow_plugin_evidence_bridge_missing" in _codes(report)


def test_evidence_bridge_records_missing_holds() -> None:
    report = build_workflow_plugin_report({
        "plugin_config": {
            "repositories": ["hate", "workflow-cookbook"],
            "task_sync": True,
            "acceptance_sync": True,
            "docs_stale_check": True,
            "schema_valid": True,
        },
        "sync_result": {"evidence_bridge_records_missing": True},
    })

    assert report["overall_status"] == "hold"
    assert "workflow_plugin_evidence_bridge_records_missing" in _codes(report)


def test_workflow_plugin_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["workflow-plugin-report"] == "schemas/HATE/v1/workflow-plugin-report.schema.json"
