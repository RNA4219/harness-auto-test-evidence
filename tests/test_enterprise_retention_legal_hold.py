"""UAT tests for enterprise retention and legal hold controls."""

from __future__ import annotations

import json
from pathlib import Path

from hate.enterprise import build_retention_legal_hold_report, evaluate_legal_hold, evaluate_retention_policy


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "enterprise" / "retention-legal-hold"
SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "HATE"
    / "v1"
    / "enterprise-control-report.schema.json"
)
NOW = "2026-06-30T00:00:00+00:00"


def load_fixture(name: str) -> dict:
    with (FIXTURE_ROOT / name / "fixture.json").open(encoding="utf-8") as f:
        return json.load(f)


def test_packet_fixture_paths_exist() -> None:
    for name in [
        "retention-valid",
        "legal-hold-active",
        "purge-eligible-metadata",
        "missing-retention-policy",
        "legal-hold-lost",
        "purge-attempt-on-legal-hold",
    ]:
        assert (FIXTURE_ROOT / name / "fixture.json").exists()


def test_retention_valid_passes() -> None:
    fixture = load_fixture("retention-valid")
    result = evaluate_retention_policy(**fixture["input"], now=NOW).to_dict()

    assert result["action"] == "retain"
    assert result["readiness_effect"] == "pass"
    assert result["canonical_evidence_deleted"] is False


def test_legal_hold_active_is_preserved_and_visible() -> None:
    fixture = load_fixture("legal-hold-active")
    result = evaluate_retention_policy(**fixture["input"], now=NOW).to_dict()
    hold = evaluate_legal_hold(fixture["input"]["resource"])

    assert result["reason"] == "retention_expired_but_legal_hold_active"
    assert result["action"] == "retain"
    assert hold["status"] == "legal_hold_active"


def test_expired_without_hold_is_metadata_purge_eligible_only() -> None:
    fixture = load_fixture("purge-eligible-metadata")
    result = evaluate_retention_policy(**fixture["input"], now=NOW).to_dict()

    assert result["action"] == "metadata_purge_eligible"
    assert result["readiness_effect"] == "soft_gap"
    assert result["purge_eligible_metadata_only"] is True
    assert result["canonical_evidence_deleted"] is False


def test_missing_retention_policy_is_hard_dq_in_release() -> None:
    fixture = load_fixture("missing-retention-policy")
    result = evaluate_retention_policy(**fixture["input"], now=NOW).to_dict()

    assert result["reason"] == "missing_retention_policy"
    assert result["readiness_effect"] == "hard_dq"
    assert result["findings"][0]["code"] == "missing_retention_policy"


def test_legal_hold_lost_is_hard_dq() -> None:
    fixture = load_fixture("legal-hold-lost")
    result = evaluate_retention_policy(**fixture["input"], now=NOW).to_dict()

    assert result["reason"] == "legal_hold_lost"
    assert result["legal_hold_preserved"] is False
    assert result["readiness_effect"] == "hard_dq"


def test_purge_attempt_on_legal_hold_is_blocked() -> None:
    fixture = load_fixture("purge-attempt-on-legal-hold")
    result = evaluate_retention_policy(**fixture["input"], now=NOW).to_dict()

    assert result["action"] == "blocked_by_legal_hold"
    assert result["readiness_effect"] == "hard_dq"
    assert result["canonical_evidence_deleted"] is False


def test_report_aggregates_worst_effect() -> None:
    resources = [
        load_fixture("retention-valid")["input"]["resource"],
        load_fixture("missing-retention-policy")["input"]["resource"],
    ]
    report = build_retention_legal_hold_report(resources, profile="release", now=NOW)

    assert report["record_type"] == "enterprise-control-report"
    assert report["summary"]["readiness_effect"] == "hard_dq"
    assert report["summary"]["retention_evaluation_count"] == 2
    assert report["findings"][0]["code"] == "missing_retention_policy"


def test_enterprise_control_schema_defines_retention_section() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert "retention_evaluations" in schema["properties"]
    required = set(schema["$defs"]["enterprise_retention_evaluation"]["required"])
    assert {
        "retention_policy_id",
        "purge_eligible_metadata_only",
        "canonical_evidence_deleted",
        "legal_hold_preserved",
    } <= required
