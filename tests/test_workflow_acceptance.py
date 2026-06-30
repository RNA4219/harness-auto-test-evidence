"""Tests for HATE-GAP-022 workflow acceptance linkage evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.workflow_acceptance import build_acceptance_linkage_report, evaluate_acceptance_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "workflow" / "acceptance"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "workflow-acceptance-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _linked_input() -> dict:
    return {
        "task_status": "done",
        "acceptance_record": {
            "path": "docs/acceptance/AC-20260630-01.md",
            "state": "accepted",
            "headings": ["Scope", "Requirements", "Verification", "Evidence", "Open Risks", "Decision"],
            "evidence_refs": ["workflow-acceptance-uat-report.json"],
            "scope_matches_tested_behavior": True,
            "verified_report_coverage": True,
        },
    }


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "workflow-acceptance-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert set(schema["properties"]["acceptance_linkage"]["required"]) <= set(report["acceptance_linkage"])
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_022_fixture_paths_exist() -> None:
    assert (FIXTURES / "done-linked" / "fixture.json").is_file()
    assert (FIXTURES / "done-without-record" / "fixture.json").is_file()


def test_done_linked_fixture_passes() -> None:
    result = evaluate_acceptance_fixture(_fixture("done-linked"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_done_without_record_fixture_holds() -> None:
    result = evaluate_acceptance_fixture(_fixture("done-without-record"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "done_task_missing_acceptance"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_exception_reason_allows_done_without_acceptance_record() -> None:
    report = build_acceptance_linkage_report({
        "task_status": "done",
        "acceptance_record": None,
        "exception_reason": "emergency patch acceptance generated separately",
    })

    assert report["overall_status"] == "pass"
    assert report["findings"] == []


def test_acceptance_record_path_must_be_canonical() -> None:
    data = _linked_input()
    data["acceptance_record"]["path"] = "docs/acceptance/latest.md"

    report = build_acceptance_linkage_report(data)

    assert report["overall_status"] == "hold"
    assert "acceptance_record_path_invalid" in _codes(report)


def test_acceptance_record_must_exist_or_be_generated() -> None:
    data = _linked_input()
    data["acceptance_record"]["path_exists"] = False

    report = build_acceptance_linkage_report(data)

    assert report["overall_status"] == "hold"
    assert "acceptance_record_missing" in _codes(report)


def test_acceptance_record_requires_headings() -> None:
    data = _linked_input()
    data["acceptance_record"]["headings"] = ["Scope", "Decision"]

    report = build_acceptance_linkage_report(data)

    assert report["overall_status"] == "hold"
    assert "acceptance_required_heading_missing" in _codes(report)


def test_acceptance_scope_cannot_exceed_tested_behavior() -> None:
    data = _linked_input()
    data["acceptance_record"]["scope_matches_tested_behavior"] = False

    report = build_acceptance_linkage_report(data)

    assert report["overall_status"] == "hold"
    assert "acceptance_scope_too_broad" in _codes(report)


def test_acceptance_cited_report_must_verify_requirement_coverage() -> None:
    data = _linked_input()
    data["acceptance_record"]["verified_report_coverage"] = False

    report = build_acceptance_linkage_report(data)

    assert report["overall_status"] == "hold"
    assert "acceptance_report_coverage_unverified" in _codes(report)


def test_held_acceptance_for_done_task_requires_exception() -> None:
    data = _linked_input()
    data["acceptance_record"]["state"] = "held"

    report = build_acceptance_linkage_report(data)

    assert report["overall_status"] == "hold"
    assert "done_task_acceptance_held_without_exception" in _codes(report)


def test_invalid_acceptance_state_holds() -> None:
    data = _linked_input()
    data["acceptance_record"]["state"] = "ready"

    report = build_acceptance_linkage_report(data)

    assert report["overall_status"] == "hold"
    assert "acceptance_state_invalid" in _codes(report)


def test_workflow_acceptance_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["workflow-acceptance-report"] == "schemas/HATE/v1/workflow-acceptance-report.schema.json"
