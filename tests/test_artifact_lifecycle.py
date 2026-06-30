"""Tests for HATE-GAP-016 artifact lifecycle state machine."""

from __future__ import annotations

import json
from pathlib import Path

from hate.security import build_artifact_lifecycle_report, evaluate_artifact_lifecycle_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "artifacts" / "lifecycle"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "artifact-lifecycle-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "artifact-lifecycle-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for transition in report["transitions"]:
        required = schema["properties"]["transitions"]["items"]["required"]
        assert set(required) <= set(transition)
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_016_fixture_paths_exist() -> None:
    assert (FIXTURES / "safe-retained" / "fixture.json").is_file()
    assert (FIXTURES / "legal-hold-delete-denied" / "fixture.json").is_file()


def test_safe_retained_fixture_passes() -> None:
    result = evaluate_artifact_lifecycle_fixture(_fixture("safe-retained"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])
    transition = result["report"]["transitions"][0]
    assert transition["target_state"] == "safe"
    assert transition["safe_for_summary"] is True


def test_legal_hold_delete_is_denied() -> None:
    result = evaluate_artifact_lifecycle_fixture(_fixture("legal-hold-delete-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "artifact_legal_hold_delete_denied"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])
    transition = result["report"]["transitions"][0]
    assert transition["target_state"] == "blocked"
    assert transition["delete_allowed"] is False


def test_delete_without_legal_hold_is_allowed() -> None:
    report = build_artifact_lifecycle_report({
        "artifact_state": "safe",
        "action": "delete",
        "legal_hold": False,
    })

    assert report["overall_status"] == "pass"
    assert report["transitions"][0]["target_state"] == "deleted"
    assert report["transitions"][0]["delete_allowed"] is True


def test_quarantine_requires_reason_for_new_quarantine() -> None:
    report = build_artifact_lifecycle_report({
        "artifact_state": "safe",
        "action": "quarantine",
    })

    assert report["overall_status"] == "hold"
    assert "artifact_quarantine_reason_missing" in _codes(report)


def test_release_requires_quarantined_state_and_review_metadata() -> None:
    report = build_artifact_lifecycle_report({
        "artifact_state": "safe",
        "action": "release",
    })

    assert report["overall_status"] == "hold"
    assert "artifact_release_requires_quarantine" in _codes(report)
    assert "artifact_release_review_missing" in _codes(report)


def test_release_from_quarantine_with_review_passes() -> None:
    report = build_artifact_lifecycle_report({
        "artifact_state": "quarantined",
        "action": "release",
        "release_actor": "security-reviewer",
        "release_reason": "redacted-safe-reference",
    })

    assert report["overall_status"] == "pass"
    assert report["transitions"][0]["target_state"] == "released"
    assert report["transitions"][0]["safe_for_summary"] is True


def test_batch_lifecycle_report_aggregates_findings() -> None:
    report = build_artifact_lifecycle_report({
        "artifacts": [
            {"artifact_id": "a1", "artifact_state": "safe"},
            {"artifact_id": "a2", "artifact_state": "safe", "action": "delete", "legal_hold": True},
        ]
    })

    assert report["overall_status"] == "hold"
    assert report["summary"]["transition_count"] == 2
    assert report["summary"]["legal_hold_block_count"] == 1


def test_artifact_lifecycle_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["artifact-lifecycle-report"] == "schemas/HATE/v1/artifact-lifecycle-report.schema.json"
