"""Tests for release candidate pack validator spec fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from hate.release import assemble_release_candidate_pack


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "release-candidate-pack"


def test_release_candidate_pack_spec_fixture_paths_exist() -> None:
    for name in [
        "all-required-reports-pass",
        "missing-required-report",
        "qeg-approval-claimed",
        "unsafe-artifact-included",
        "open-manual-review",
    ]:
        assert (FIXTURES / name / "fixture.json").exists()


def test_all_required_reports_pass_is_deterministic_ready_pack() -> None:
    fixture = _fixture("all-required-reports-pass")

    first = assemble_release_candidate_pack(fixture["input"])
    second = assemble_release_candidate_pack(fixture["input"])

    assert first["verdict"] == fixture["expected"]["verdict"]
    assert first["summary"]["release_ready"] is fixture["expected"]["release_ready"]
    assert first["pack_hash"] == second["pack_hash"]
    assert first["qeg_refs"]["approval_claimed"] is False


def test_missing_required_report_lists_exact_id_and_path() -> None:
    fixture = _fixture("missing-required-report")

    pack = assemble_release_candidate_pack(fixture["input"])
    missing = pack["missing_required_reports"][0]

    assert pack["verdict"] == fixture["expected"]["verdict"]
    assert missing["report_id"] == fixture["expected"]["missing_report_id"]
    assert missing["path"] == fixture["expected"]["missing_path"]


def test_qeg_approval_claim_is_blocked_and_suppressed() -> None:
    fixture = _fixture("qeg-approval-claimed")

    pack = assemble_release_candidate_pack(fixture["input"])

    assert pack["verdict"] == fixture["expected"]["verdict"]
    assert pack["qeg_approval_claimed"] is fixture["expected"]["qeg_approval_claimed"]
    assert fixture["expected"]["blocker_code"] in _codes(pack)


def test_unsafe_artifact_included_is_excluded_and_blocks() -> None:
    fixture = _fixture("unsafe-artifact-included")

    pack = assemble_release_candidate_pack(fixture["input"])
    excluded = pack["evidence_room_manifest"]["excluded_artifacts"][0]

    assert pack["verdict"] == fixture["expected"]["verdict"]
    assert excluded["reason"] == fixture["expected"]["excluded_reason"]
    assert fixture["expected"]["blocker_code"] in _codes(pack)


def test_open_manual_review_blocks_release_pack() -> None:
    fixture = _fixture("open-manual-review")

    pack = assemble_release_candidate_pack(fixture["input"])

    assert pack["verdict"] == fixture["expected"]["verdict"]
    assert pack["manual_review_state"]["status"] == fixture["expected"]["manual_review_status"]
    assert fixture["expected"]["blocker_code"] in _codes(pack)


def test_qeg_validate_failure_blocks_release_pack() -> None:
    fixture = _fixture("all-required-reports-pass")
    fixture["input"]["qeg_refs"]["validate_status"] = "failed"

    pack = assemble_release_candidate_pack(fixture["input"])

    assert pack["verdict"] == "blocked"
    assert "qeg_validate_failed" in _codes(pack)


def test_stale_required_report_hash_blocks_release_pack() -> None:
    fixture = _fixture("all-required-reports-pass")
    fixture["input"]["required_reports"][0]["hash"] = "hash-stale"

    pack = assemble_release_candidate_pack(fixture["input"])

    assert pack["verdict"] == "blocked"
    assert "stale_required_report_hash" in _codes(pack)


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(pack: dict) -> set[str]:
    return {blocker["code"] for blocker in pack["blockers"]}
