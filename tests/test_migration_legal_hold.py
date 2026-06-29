"""UAT tests for legal hold migration preservation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.migration import build_legal_hold_migration_report, evaluate_legal_hold_migration


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "migration" / "legal-hold"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "HATE" / "v1" / "migration-compatibility-report.schema.json"


def load_fixture(name: str) -> dict:
    with (FIXTURE_ROOT / name / "fixture.json").open(encoding="utf-8") as f:
        return json.load(f)


def test_packet_fixture_paths_exist() -> None:
    for name in [
        "hold-preserved",
        "retention-transition",
        "export-preserves-hold",
        "hold-lost",
        "purge-during-hold",
        "replay-drops-hold",
    ]:
        assert (FIXTURE_ROOT / name / "fixture.json").exists()


def test_hold_preserved_passes() -> None:
    fixture = load_fixture("hold-preserved")
    result = evaluate_legal_hold_migration(fixture["input"])

    assert result["readiness_effect"] == "pass"
    assert result["legal_hold_preserved"] is True
    assert result["findings"] == []


def test_retention_transition_respects_active_hold() -> None:
    fixture = load_fixture("retention-transition")
    result = evaluate_legal_hold_migration(fixture["input"])

    assert result["readiness_effect"] == "pass"
    assert result["legal_hold_preserved"] is True


def test_export_preserves_hold_metadata() -> None:
    fixture = load_fixture("export-preserves-hold")
    result = evaluate_legal_hold_migration(fixture["input"])

    assert result["legal_hold_preserved"] is True
    assert result["readiness_effect"] == "hard_dq"
    assert any(finding["code"] == "legal_hold_blocks_mutation" for finding in result["findings"])


def test_hold_lost_is_hard_dq() -> None:
    fixture = load_fixture("hold-lost")
    result = evaluate_legal_hold_migration(fixture["input"])

    assert result["legal_hold_preserved"] is False
    assert result["readiness_effect"] == "hard_dq"
    assert any(finding["code"] == "legal_hold_lost" for finding in result["findings"])


def test_purge_during_hold_is_blocked() -> None:
    fixture = load_fixture("purge-during-hold")
    result = evaluate_legal_hold_migration(fixture["input"])

    assert result["mutation_blocked"] is True
    assert result["readiness_effect"] == "hard_dq"
    assert any(finding["code"] == "legal_hold_blocks_mutation" for finding in result["findings"])


def test_replay_drops_hold_is_hard_dq() -> None:
    fixture = load_fixture("replay-drops-hold")
    result = evaluate_legal_hold_migration(fixture["input"])

    assert result["readiness_effect"] == "hard_dq"
    assert any(finding["code"] == "replay_drops_legal_hold" for finding in result["findings"])


def test_report_links_compatibility_and_enterprise_findings() -> None:
    report = build_legal_hold_migration_report([
        load_fixture("hold-preserved")["input"],
        load_fixture("hold-lost")["input"],
    ])

    assert report["record_type"] == "migration-compatibility-report"
    assert report["summary"]["transition_count"] == 2
    assert report["summary"]["readiness_effect"] == "hard_dq"
    assert report["legal_hold_transitions"][1]["compatibility_decision"]["legal_hold_preserved"] is False


def test_schema_defines_legal_hold_transitions() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert "legal_hold_transitions" in schema["properties"]
    assert "legal_hold_transition" in schema["$defs"]
    required = set(schema["$defs"]["legal_hold_transition"]["required"])
    assert {"operation", "legal_hold_preserved", "compatibility_decision"} <= required
