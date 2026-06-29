"""UAT tests for migration compatibility dry-run reports."""

from __future__ import annotations

import json
from pathlib import Path

from hate.migration import build_migration_compatibility_report, evaluate_migration_compatibility


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "migration" / "compatibility"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "HATE" / "v1" / "migration-compatibility-report.schema.json"
REGISTRY_PATH = Path(__file__).resolve().parents[1] / "schemas" / "HATE" / "v1" / "schema-registry.json"


def load_fixture(name: str) -> dict:
    with (FIXTURE_ROOT / name / "fixture.json").open(encoding="utf-8") as f:
        return json.load(f)


def test_packet_fixture_paths_exist() -> None:
    for name in [
        "minor-compatible",
        "patch-compatible",
        "unsupported-major",
        "hash-changed",
        "source-ref-lost",
        "canonical-mutated",
    ]:
        assert (FIXTURE_ROOT / name / "fixture.json").exists()


def test_minor_compatible_schema_migration_passes() -> None:
    fixture = load_fixture("minor-compatible")
    decision = evaluate_migration_compatibility(**fixture["input"]).to_dict()

    assert decision["readiness_effect"] == "pass"
    assert decision["reason"] == "minor_compatible"
    assert decision["source_refs_preserved"] is True
    assert decision["legal_hold_preserved"] is True


def test_patch_compatible_schema_migration_passes() -> None:
    fixture = load_fixture("patch-compatible")
    decision = evaluate_migration_compatibility(**fixture["input"]).to_dict()

    assert decision["readiness_effect"] == "pass"
    assert decision["reason"] == "patch_compatible"
    assert decision["canonical_source_mutated"] is False


def test_unsupported_major_is_hard_dq_in_release() -> None:
    fixture = load_fixture("unsupported-major")
    decision = evaluate_migration_compatibility(**fixture["input"]).to_dict()

    assert decision["readiness_effect"] == "hard_dq"
    assert decision["decision"] == "blocked"
    assert decision["findings"][0]["code"] == "unsupported_major_version"


def test_hash_changed_is_hard_dq() -> None:
    fixture = load_fixture("hash-changed")
    decision = evaluate_migration_compatibility(**fixture["input"]).to_dict()

    assert decision["readiness_effect"] == "hard_dq"
    assert any(finding["code"] == "source_hash_mismatch" for finding in decision["findings"])


def test_source_ref_lost_is_hard_dq() -> None:
    fixture = load_fixture("source-ref-lost")
    decision = evaluate_migration_compatibility(**fixture["input"]).to_dict()

    assert decision["source_refs_preserved"] is False
    assert any(finding["code"] == "source_ref_lost" for finding in decision["findings"])


def test_canonical_source_mutation_is_hard_dq() -> None:
    fixture = load_fixture("canonical-mutated")
    decision = evaluate_migration_compatibility(**fixture["input"]).to_dict()

    assert decision["canonical_source_mutated"] is True
    assert decision["readiness_effect"] == "hard_dq"
    assert any(finding["code"] == "canonical_source_mutated" for finding in decision["findings"])


def test_report_summarizes_decisions_and_findings() -> None:
    scenarios = [
        load_fixture("minor-compatible")["input"],
        load_fixture("unsupported-major")["input"],
    ]
    report = build_migration_compatibility_report(scenarios, profile="release")

    assert report["record_type"] == "migration-compatibility-report"
    assert report["summary"]["decision_count"] == 2
    assert report["summary"]["readiness_effect"] == "hard_dq"
    assert report["summary"]["pass_count"] == 1
    assert report["summary"]["hard_dq_count"] == 1


def test_schema_and_registry_define_migration_report() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "migration-compatibility-report"
    assert "migration_decision" in schema["$defs"]
    records = {item["record_type"]: item["schema"] for item in registry["records"]}
    assert records["migration-compatibility-report"] == "schemas/HATE/v1/migration-compatibility-report.schema.json"
