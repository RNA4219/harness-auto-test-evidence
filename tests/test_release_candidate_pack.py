"""Tests for release candidate pack assembly."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion_runner import EXPANSION_REPORT_TYPES
from hate.release import RELEASE_PACK_REQUIRED_REPORT_TYPES, assemble_release_candidate_pack


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "release" / "candidate-pack"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "HATE" / "v1" / "release-candidate-pack.schema.json"
REGISTRY_PATH = Path(__file__).resolve().parents[1] / "schemas" / "HATE" / "v1" / "schema-registry.json"


def load_fixture(name: str) -> dict:
    with (FIXTURE_ROOT / name / "fixture.json").open(encoding="utf-8") as f:
        return json.load(f)


def test_packet_fixture_paths_exist() -> None:
    for name in [
        "all-green",
        "missing-required-report",
        "security-hard-dq",
        "commercial-unsupported-claim",
        "non-deterministic-input",
        "legal-hold-preserved",
    ]:
        assert (FIXTURE_ROOT / name / "fixture.json").exists()


def test_all_green_release_candidate_is_ready() -> None:
    fixture = load_fixture("all-green")
    pack = assemble_release_candidate_pack(fixture["input"])

    assert pack["record_type"] == "release-candidate-pack"
    assert pack["verdict"] == "ready"
    assert pack["readiness_effect"] == "pass"
    assert pack["summary"]["release_ready"] is True
    assert pack["missing_required_reports"] == []
    assert pack["blockers"] == []
    assert pack["qeg_approval_claimed"] is False
    assert pack["qeg_verdict_override"] is False
    assert pack["evidence_room_manifest"]["unsafe_artifact_excluded_count"] == 1


def test_missing_required_report_is_hard_dq() -> None:
    fixture = load_fixture("missing-required-report")
    pack = assemble_release_candidate_pack(fixture["input"])

    assert pack["verdict"] == "blocked"
    assert "support-ops-report" in pack["missing_required_reports"]
    assert any(blocker["code"] == "missing_required_report" for blocker in pack["blockers"])
    assert pack["summary"]["hard_dq_count"] >= 1


def test_security_hard_dq_and_quarantined_export_block_release() -> None:
    fixture = load_fixture("security-hard-dq")
    pack = assemble_release_candidate_pack(fixture["input"])
    blocker_codes = {blocker["code"] for blocker in pack["blockers"]}

    assert pack["verdict"] == "blocked"
    assert {"dependency_hard_dq", "quarantined_artifact_exported"}.issubset(blocker_codes)
    assert pack["evidence_room_manifest"]["excluded_artifacts"][0]["attempted_export"] is True


def test_unsupported_commercial_claim_blocks_release() -> None:
    fixture = load_fixture("commercial-unsupported-claim")
    pack = assemble_release_candidate_pack(fixture["input"])

    assert pack["commercial_claim_state"]["status"] == "blocked"
    assert any(blocker["code"] == "unsupported_commercial_claim" for blocker in pack["blockers"])
    assert pack["summary"]["release_ready"] is False


def test_pack_hash_is_deterministic_for_shuffled_input() -> None:
    all_green = assemble_release_candidate_pack(load_fixture("all-green")["input"])
    shuffled = assemble_release_candidate_pack(load_fixture("non-deterministic-input")["input"])

    assert all_green["reports"] == shuffled["reports"]
    assert all_green["evidence_room_manifest"] == shuffled["evidence_room_manifest"]
    assert all_green["pack_hash"] == shuffled["pack_hash"]


def test_legal_hold_refs_are_preserved() -> None:
    fixture = load_fixture("legal-hold-preserved")
    pack = assemble_release_candidate_pack(fixture["input"])

    assert pack["verdict"] == "ready"
    assert pack["legal_hold"]["preserved"] is True
    assert pack["legal_hold"]["held_report_refs"] == fixture["expected"]["held_report_refs"]


def test_qeg_approval_claim_is_blocked_and_not_emitted() -> None:
    fixture = load_fixture("all-green")
    input_data = {**fixture["input"], "qeg_approval_claimed": True}
    pack = assemble_release_candidate_pack(input_data)

    assert pack["qeg_approval_claimed"] is False
    assert any(blocker["code"] == "qeg_approval_claimed" for blocker in pack["blockers"])
    assert pack["verdict"] == "blocked"


def test_schema_and_registry_define_release_candidate_pack() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "release-candidate-pack"
    assert "report_entry" in schema["$defs"]
    assert "evidence_room_excluded_artifact" in schema["$defs"]
    records = {item["record_type"]: item["schema"] for item in registry["records"]}
    assert records["release-candidate-pack"] == "schemas/HATE/v1/release-candidate-pack.schema.json"


def test_release_pack_requires_connected_expansion_reports() -> None:
    assert set(EXPANSION_REPORT_TYPES).issubset(set(RELEASE_PACK_REQUIRED_REPORT_TYPES))


def test_release_pack_requires_product_grade_canonical_reports() -> None:
    required = set(RELEASE_PACK_REQUIRED_REPORT_TYPES)

    assert {
        "adapter-conformance-report",
        "schema_validation_report",
        "store_replay_report",
        "security-quarantine-report",
        "api-contract-report",
        "dashboard-uat-report",
        "enterprise-control-report",
        "scale-performance-report",
        "migration-compatibility-report",
        "commercial-truthfulness-report",
        "support-ops-report",
    }.issubset(required)
