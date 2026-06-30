"""Tests for HATE-GAP-019 release channel and migration evidence policy."""

from __future__ import annotations

import json
from pathlib import Path

from hate.release_channel import build_release_channel_report, evaluate_release_channel_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "release" / "channel"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "release-channel-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "release-channel-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert set(schema["properties"]["channel_matrix"]["required"]) <= set(report["channel_matrix"])
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_019_fixture_paths_exist() -> None:
    assert (FIXTURES / "minor-compatible" / "fixture.json").is_file()
    assert (FIXTURES / "breaking-without-migration" / "fixture.json").is_file()


def test_minor_compatible_fixture_passes() -> None:
    result = evaluate_release_channel_fixture(_fixture("minor-compatible"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])
    assert result["report"]["channel_matrix"]["change_type"] == "minor"
    assert result["report"]["channel_matrix"]["rollback_plan"] is True


def test_breaking_without_migration_fixture_holds() -> None:
    result = evaluate_release_channel_fixture(_fixture("breaking-without-migration"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "release_breaking_without_migration"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_migration_required_release_requires_artifacts() -> None:
    report = build_release_channel_report({
        "change_type": "breaking",
        "migration_required": True,
        "migration_plan": True,
        "rollback_plan": True,
    })

    assert report["overall_status"] == "hold"
    assert "release_migration_artifact_missing" in _codes(report)


def test_major_or_breaking_release_requires_deprecation_notice() -> None:
    report = build_release_channel_report({
        "change_type": "major",
        "migration_required": True,
        "migration_plan": True,
        "rollback_plan": True,
        "deprecation_notice": False,
        "migration_artifacts": {
            "migration_guide": True,
            "schema_diff": True,
            "replay_impact": True,
            "compatibility_matrix": True,
        },
    })

    assert report["overall_status"] == "hold"
    assert "release_deprecation_notice_missing" in _codes(report)


def test_release_gates_are_required() -> None:
    report = build_release_channel_report({
        "change_type": "minor",
        "rollback_plan": True,
        "release_gates": ["RG-1", "RG-2"],
    })

    assert report["overall_status"] == "hold"
    assert "release_gate_evidence_missing" in _codes(report)


def test_previous_stable_must_safe_reject_future_schema() -> None:
    report = build_release_channel_report({
        "change_type": "minor",
        "rollback_plan": True,
        "previous_stable_safe_reject": False,
    })

    assert report["overall_status"] == "hold"
    assert "release_previous_stable_safe_reject_missing" in _codes(report)


def test_release_notes_must_include_rollback_and_compatibility() -> None:
    report = build_release_channel_report({
        "change_type": "minor",
        "rollback_plan": True,
        "release_notes": {"summary": "incomplete"},
    })

    assert report["overall_status"] == "hold"
    assert "release_notes_incomplete" in _codes(report)


def test_complete_breaking_release_can_pass() -> None:
    report = build_release_channel_report({
        "change_type": "breaking",
        "migration_required": True,
        "migration_plan": True,
        "rollback_plan": True,
        "deprecation_notice": True,
        "migration_artifacts": {
            "migration_guide": True,
            "schema_diff": True,
            "replay_impact": True,
            "compatibility_matrix": True,
        },
    })

    assert report["overall_status"] == "pass"
    assert report["findings"] == []


def test_release_channel_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["release-channel-report"] == "schemas/HATE/v1/release-channel-report.schema.json"
