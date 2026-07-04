from __future__ import annotations

import json
from pathlib import Path

from hate.post_poc.baseline import (
    build_baseline_promotion_report,
    build_baseline_review_packet,
    evaluate_baseline_fixture,
    write_baseline_review_packet,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc" / "baseline"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "baseline-promotion-report.schema.json"
REVIEW_PACKET_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "baseline-review-packet.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "baseline-promotion-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert report["baseline_state"]["record_type"] == "baseline-state"
    for request in report["promotion_requests"]:
        assert request["record_type"] == "baseline-promotion-request"
        assert request["sourceRefs"]
    for decision in report["promotion_decisions"]:
        assert decision["record_type"] == "baseline-promotion-decision"
        assert decision["sourceRefs"]
    for event in report["immutability_events"]:
        assert event["record_type"] == "baseline-immutability-event"
        assert event["sourceRefs"]
        assert "before_state" in event
        assert "after_state" in event
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def _assert_review_packet_contract(packet: dict) -> None:
    schema = json.loads(REVIEW_PACKET_SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(packet)
    assert packet["schema_version"] == "HATE/v1"
    assert packet["record_type"] == "baseline-review-packet"
    assert packet["comparison"]["record_type"] == "baseline-review-comparison"
    assert set(schema["properties"]["comparison"]["required"]) <= set(packet["comparison"])
    for item in packet["review_items"]:
        assert set(schema["properties"]["review_items"]["items"]["required"]) <= set(item)
        assert item["record_type"] == "baseline-review-item"
        assert item["status"] in {"satisfied", "missing"}
    for finding in packet["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)
    assert set(schema["properties"]["summary"]["required"]) <= set(packet["summary"])


def test_task_postpoc_004_canonical_fixture_paths_exist() -> None:
    for name in [
        "propose-approve-freeze",
        "self-approval-denied",
        "expired-baseline-denied",
        "revoked-baseline-denied",
        "unapproved-comparison-holds",
    ]:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_propose_approve_freeze_passes_and_records_immutable_events() -> None:
    result = evaluate_baseline_fixture(_fixture("propose-approve-freeze"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    report = result["report"]
    assert report["baseline_state"]["state"] == "frozen"
    assert report["summary"]["comparison_allowed"] is True
    assert report["summary"]["request_count"] == 1
    assert report["summary"]["decision_count"] == 2
    assert report["summary"]["immutability_event_count"] == 3
    assert report["immutability_events"][-1]["before_state"] == "approved"
    assert report["immutability_events"][-1]["after_state"] == "frozen"
    assert report["immutability_events"][-1]["after_hash"] == "sha256:frozen-1001"
    _assert_report_contract(report)


def test_self_approval_is_denied() -> None:
    result = evaluate_baseline_fixture(_fixture("self-approval-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "baseline_self_approval_denied"
    assert result["report"]["baseline_state"]["state"] == "proposed"
    assert result["report"]["promotion_decisions"][0]["reviewer"] == "alice"


def test_expired_baseline_is_denied_for_comparison() -> None:
    result = evaluate_baseline_fixture(_fixture("expired-baseline-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "baseline_expired"
    assert "baseline_unapproved_for_comparison" in _codes(result["report"])
    assert result["report"]["baseline_state"]["state"] == "expired"


def test_revoked_baseline_is_denied_for_comparison() -> None:
    result = evaluate_baseline_fixture(_fixture("revoked-baseline-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "baseline_revoked"
    assert "baseline_unapproved_for_comparison" in _codes(result["report"])
    assert result["report"]["baseline_state"]["state"] == "revoked"


def test_unapproved_comparison_holds() -> None:
    result = evaluate_baseline_fixture(_fixture("unapproved-comparison-holds"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "baseline_unapproved_for_comparison"
    assert result["report"]["baseline_state"]["state"] == "proposed"
    assert result["report"]["summary"]["comparison_allowed"] is False


def test_candidate_missing_evidence_holds() -> None:
    report = build_baseline_promotion_report({
        "baseline": {
            "baseline_id": "base-missing-evidence",
            "repo_id": "repo-main",
            "suite_id": "pytest",
            "actor": "alice",
            "policy_hash": "policy-sha256-001",
        },
        "events": [{"event_type": "proposed", "candidate_run_id": "run-missing"}],
    })

    assert report["overall_status"] == "hold"
    assert "baseline_candidate_missing_evidence" in _codes(report)
    assert report["promotion_requests"][0]["candidate_run_id"] == "run-missing"


def test_approval_missing_reviewer_holds() -> None:
    report = build_baseline_promotion_report({
        "baseline": {
            "baseline_id": "base-missing-reviewer",
            "repo_id": "repo-main",
            "suite_id": "pytest",
            "actor": "alice",
            "policy_hash": "policy-sha256-001",
        },
        "events": [
            {
                "event_type": "proposed",
                "candidate_run_id": "run-6001",
                "evidence_refs": ["artifact://runs/run-6001/product-readiness.json"],
            },
            {"event_type": "approved"},
        ],
    })

    assert report["overall_status"] == "hold"
    assert "baseline_approval_missing_reviewer" in _codes(report)
    assert report["baseline_state"]["state"] == "proposed"


def test_external_oss_baseline_requires_external_refs_and_observation_floor() -> None:
    report = build_baseline_promotion_report({
        "baseline": {
            "baseline_id": "base-external-thin",
            "repo_id": "requests",
            "suite_id": "pytest",
            "ownership_scope": "external",
            "actor": "alice",
            "reviewer": "bob",
            "candidate_run_id": "run-external-1",
            "evidence_refs": ["artifact://runs/run-external-1/report.json"],
            "policy_hash": "policy-sha256-oss",
            "expires_at": "2026-08-01T00:00:00Z",
            "observation_count": 1,
        },
        "events": [{"event_type": "approved", "reviewer": "bob"}],
    })

    assert report["overall_status"] == "hold"
    assert "baseline_external_reference_missing" in _codes(report)
    assert "baseline_external_observation_floor_missing" in _codes(report)
    assert report["summary"]["comparison_allowed"] is False


def test_external_oss_baseline_can_be_approved_with_refs_and_repeated_observations() -> None:
    report = build_baseline_promotion_report({
        "baseline": {
            "baseline_id": "base-external-ready",
            "repo_id": "click",
            "suite_id": "pytest",
            "ownership_scope": "external",
            "actor": "alice",
            "candidate_run_id": "run-external-2",
            "evidence_refs": ["artifact://runs/run-external-2/report.json"],
            "policy_hash": "policy-sha256-oss",
            "expires_at": "2026-08-01T00:00:00Z",
        },
        "events": [{
            "event_type": "approved",
            "reviewer": "bob",
            "external_run_ref": "https://github.com/pallets/click/actions/runs/1",
            "external_decision_ref": "artifact://external/click/maintainer-decision.json",
            "observation_count": 2,
        }],
    })

    assert report["overall_status"] == "pass"
    assert report["baseline_state"]["ownership_scope"] == "external"
    assert report["baseline_state"]["external_run_ref"].startswith("https://github.com/")
    assert report["baseline_state"]["observation_count"] == 2
    assert report["promotion_decisions"][0]["external_decision_ref"] == "artifact://external/click/maintainer-decision.json"


def test_baseline_promotion_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["baseline-promotion-report"] == "schemas/HATE/v1/baseline-promotion-report.schema.json"
    assert records["baseline-review-packet"] == "schemas/HATE/v1/baseline-review-packet.schema.json"


def test_baseline_review_packet_ready_when_required_items_are_satisfied() -> None:
    input_data = _fixture("propose-approve-freeze")["input"]
    input_data = json.loads(json.dumps(input_data))
    input_data["comparison"] = {
        "previous_baseline_ref": "baseline://base-1000",
        "previous_score": 0.92,
        "candidate_score": 0.95,
        "previous_regression_count": 1,
        "candidate_regression_count": 0,
        "comparison_artifact_ref": "artifact://baseline/base-1001/comparison.json",
    }

    packet = build_baseline_review_packet(input_data, source_refs=["fixture://baseline/review-ready"])

    assert packet["record_type"] == "baseline-review-packet"
    _assert_review_packet_contract(packet)
    assert packet["summary"]["ready_for_review"] is True
    assert packet["summary"]["score_delta"] == 0.03
    assert packet["summary"]["regression_count_delta"] == -1
    assert packet["findings"] == []
    assert {item["status"] for item in packet["review_items"]} == {"satisfied"}
    assert packet["sourceRefs"] == ["fixture://baseline/review-ready"]


def test_baseline_review_packet_blocks_missing_comparison_artifact() -> None:
    packet = build_baseline_review_packet(_fixture("propose-approve-freeze")["input"])

    _assert_review_packet_contract(packet)
    assert packet["summary"]["ready_for_review"] is False
    assert "baseline_review_item_missing" in _codes(packet)
    missing = [item["item_id"] for item in packet["review_items"] if item["status"] == "missing"]
    assert "comparison_artifact" in missing


def test_baseline_review_packet_blocks_new_regressions() -> None:
    input_data = json.loads(json.dumps(_fixture("propose-approve-freeze")["input"]))
    input_data["comparison"] = {
        "previous_baseline_ref": "baseline://base-1000",
        "previous_score": 0.95,
        "candidate_score": 0.9,
        "previous_regression_count": 0,
        "candidate_regression_count": 2,
        "comparison_artifact_ref": "artifact://baseline/base-1001/comparison.json",
    }

    packet = build_baseline_review_packet(input_data)

    assert packet["summary"]["ready_for_review"] is False
    assert packet["summary"]["regression_count_delta"] == 2
    missing = [item["item_id"] for item in packet["review_items"] if item["status"] == "missing"]
    assert "regression_delta" in missing


def test_baseline_review_packet_is_blocked_by_promotion_findings() -> None:
    input_data = json.loads(json.dumps(_fixture("self-approval-denied")["input"]))
    input_data["comparison"] = {
        "previous_baseline_ref": "baseline://base-old",
        "previous_score": 0.9,
        "candidate_score": 0.91,
        "comparison_artifact_ref": "artifact://baseline/self-approval/comparison.json",
    }

    packet = build_baseline_review_packet(input_data)

    assert packet["summary"]["ready_for_review"] is False
    assert "baseline_review_blocked_by_promotion_findings" in _codes(packet)


def test_baseline_review_packet_artifact_write_contract(tmp_path: Path) -> None:
    input_data = json.loads(json.dumps(_fixture("propose-approve-freeze")["input"]))
    input_data["comparison"] = {
        "previous_baseline_ref": "baseline://base-1000",
        "previous_score": 0.92,
        "candidate_score": 0.95,
        "comparison_artifact_ref": "artifact://baseline/base-1001/comparison.json",
    }
    packet = build_baseline_review_packet(input_data, source_refs=["fixture://baseline/review-artifact"])
    out_path = tmp_path / "baseline-review-packet.json"

    artifact = write_baseline_review_packet(packet, out_path)

    assert artifact["record_type"] == "baseline-review-packet-artifact"
    assert artifact["baseline_id"] == packet["baseline_id"]
    assert artifact["review_item_count"] == len(packet["review_items"])
    assert artifact["sourceRefs"] == ["fixture://baseline/review-artifact"]
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["record_type"] == "baseline-review-packet"
