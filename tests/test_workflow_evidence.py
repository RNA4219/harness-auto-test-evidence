"""Tests for HATE-GAP-023 workflow Evidence protocol evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.workflow_evidence import build_evidence_protocol_report, evaluate_evidence_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "workflow" / "evidence"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "workflow-evidence-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _valid_evidence(evidence_class: str = "command_execution") -> dict:
    evidence = {
        "evidence": {
            "evidence_id": "ev_fixture",
            "evidence_class": evidence_class,
            "source_tool": "Codex",
            "command_or_action": "uv run pytest -q",
            "exit_status": 0,
            "artifact_refs": ["fixtures/gap-closure/expected/gap-closure-report.json"],
            "hashes": {"fixtures/gap-closure/expected/gap-closure-report.json": "sha256:fixture"},
            "decision_or_status": "passed",
            "timestamp": "2026-06-30T00:00:00Z",
            "sourceRefs": ["WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md#evidence-protocol"],
        }
    }
    if evidence_class == "review_record":
        evidence["evidence"]["scope"] = "HATE-GAP-023"
    return evidence


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "workflow-evidence-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_023_fixture_paths_exist() -> None:
    assert (FIXTURES / "command-recorded" / "fixture.json").is_file()
    assert (FIXTURES / "artifact-missing-hash" / "fixture.json").is_file()


def test_command_recorded_fixture_passes() -> None:
    result = evaluate_evidence_fixture(_fixture("command-recorded"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_artifact_missing_hash_fixture_holds() -> None:
    result = evaluate_evidence_fixture(_fixture("artifact-missing-hash"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "evidence_artifact_missing_hash"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_required_fields_hold() -> None:
    report = build_evidence_protocol_report({"evidence": {"evidence_class": "command_execution"}})

    assert report["overall_status"] == "hold"
    assert "evidence_missing_required_field" in _codes(report)


def test_unknown_evidence_class_holds() -> None:
    data = _valid_evidence("unknown")

    report = build_evidence_protocol_report(data)

    assert report["overall_status"] == "hold"
    assert "evidence_class_unknown" in _codes(report)


def test_command_execution_requires_exit_status() -> None:
    data = _valid_evidence("command_execution")
    del data["evidence"]["exit_status"]

    report = build_evidence_protocol_report(data)

    assert report["overall_status"] == "hold"
    assert "evidence_command_missing_exit_status" in _codes(report)


def test_review_record_requires_scope() -> None:
    data = _valid_evidence("review_record")
    del data["evidence"]["scope"]

    report = build_evidence_protocol_report(data)

    assert report["overall_status"] == "hold"
    assert "evidence_review_missing_scope" in _codes(report)


def test_all_required_evidence_classes_can_pass() -> None:
    for evidence_class in [
        "command_execution",
        "artifact_generation",
        "decision_record",
        "review_record",
        "runtime_event",
    ]:
        report = build_evidence_protocol_report(_valid_evidence(evidence_class))

        assert report["overall_status"] == "pass"
        assert report["findings"] == []


def test_empty_hash_value_counts_as_missing_hash() -> None:
    data = _valid_evidence("artifact_generation")
    ref = data["evidence"]["artifact_refs"][0]
    data["evidence"]["hashes"][ref] = ""

    report = build_evidence_protocol_report(data)

    assert report["overall_status"] == "hold"
    assert "evidence_artifact_missing_hash" in _codes(report)


def test_workflow_evidence_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["workflow-evidence-report"] == "schemas/HATE/v1/workflow-evidence-report.schema.json"
