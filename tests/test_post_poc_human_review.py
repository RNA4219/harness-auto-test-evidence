from __future__ import annotations

import json
from pathlib import Path

from hate.post_poc.human_review import (
    build_human_review_queue_packet,
    build_human_review_workflow_report,
    evaluate_human_review_fixture,
    write_human_review_queue_packet,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc" / "human-review"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "human-review-workflow-report.schema.json"
QUEUE_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "human-review-queue-packet.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "human-review-workflow-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert report["review_state"]["record_type"] == "human-review-workflow-state"
    for request in report["requests"]:
        assert request["record_type"] == "human-review-workflow-request"
        assert request["sourceRefs"]
    for decision in report["decisions"]:
        assert decision["record_type"] == "human-review-workflow-decision"
        assert decision["sourceRefs"]
    for attachment in report["attachments"]:
        assert attachment["record_type"] == "human-review-evidence-attachment"
        assert attachment["sourceRefs"]
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def _assert_queue_packet_contract(packet: dict) -> None:
    schema = json.loads(QUEUE_SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(packet)
    assert packet["schema_version"] == "HATE/v1"
    assert packet["record_type"] == "human-review-queue-packet"
    assert set(schema["properties"]["queue_item"]["required"]) <= set(packet["queue_item"])
    assert packet["queue_item"]["record_type"] == "human-review-queue-item"
    assert set(schema["properties"]["summary"]["required"]) <= set(packet["summary"])
    for action in packet["allowed_actions"]:
        assert action in {
            "assign_reviewer",
            "attach_evidence",
            "approve",
            "deny",
            "expire",
            "resolve",
            "revoke",
            "supersede",
            "replay",
        }
    for finding in packet["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_task_postpoc_016_canonical_fixture_paths_exist() -> None:
    for name in [
        "approve-with-evidence",
        "deny-with-reason",
        "evidence-missing-holds",
        "revoked-decision",
        "replay-mismatch-holds",
    ]:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_approve_with_evidence_passes_and_replays() -> None:
    result = evaluate_human_review_fixture(_fixture("approve-with-evidence"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["report"]["review_state"]["status"] == "approved"
    assert result["report"]["summary"]["attachment_count"] == 1
    assert result["report"]["decisions"][0]["decision"] == "approve"
    _assert_report_contract(result["report"])


def test_deny_with_reason_passes() -> None:
    result = evaluate_human_review_fixture(_fixture("deny-with-reason"))

    assert result["status"] == "pass"
    assert result["report"]["review_state"]["status"] == "denied"
    assert result["report"]["decisions"][0]["decision_reason"]


def test_evidence_missing_holds() -> None:
    result = evaluate_human_review_fixture(_fixture("evidence-missing-holds"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "human_review_evidence_missing"
    assert result["report"]["readiness_effect"] == "hold"


def test_revoked_decision_holds() -> None:
    result = evaluate_human_review_fixture(_fixture("revoked-decision"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "human_review_revoked"
    assert result["report"]["review_state"]["status"] == "revoked"


def test_replay_mismatch_holds() -> None:
    result = evaluate_human_review_fixture(_fixture("replay-mismatch-holds"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "human_review_replay_mismatch"


def test_missing_reviewer_holds() -> None:
    report = build_human_review_workflow_report({
        "review": {"review_id": "hr-missing-reviewer", "owner": "owner@example.com"},
        "actions": [{"action": "assign_reviewer"}],
    })

    assert report["overall_status"] == "hold"
    assert "human_review_reviewer_missing" in _codes(report)


def test_self_approval_is_denied() -> None:
    report = build_human_review_workflow_report({
        "review": {
            "review_id": "hr-self",
            "owner": "owner@example.com",
            "evidence_refs": ["artifact://manual-review/hr-self/evidence.json"],
        },
        "actions": [
            {"action": "assign_reviewer", "reviewer": "owner@example.com"},
            {"action": "approve", "decision_hash": "sha256:self"},
        ],
    })

    assert report["overall_status"] == "hold"
    assert "human_review_self_approval_denied" in _codes(report)


def test_expire_supersede_and_resolve_are_modeled() -> None:
    expired = build_human_review_workflow_report({
        "review": {"review_id": "hr-expire", "reviewer": "r", "owner": "o"},
        "actions": [{"action": "expire"}],
    })
    superseded = build_human_review_workflow_report({
        "review": {"review_id": "hr-super", "reviewer": "r", "owner": "o"},
        "actions": [{"action": "supersede", "superseded_by": "hr-next"}],
    })
    resolved = build_human_review_workflow_report({
        "review": {
            "review_id": "hr-resolve",
            "reviewer": "r",
            "owner": "o",
            "decision": "deny",
            "status": "denied",
        },
        "actions": [{"action": "resolve"}],
    })

    assert expired["overall_status"] == "hold"
    assert "human_review_expired" in _codes(expired)
    assert superseded["overall_status"] == "pass"
    assert superseded["review_state"]["status"] == "superseded"
    assert resolved["overall_status"] == "pass"
    assert resolved["review_state"]["status"] == "resolved"


def test_human_review_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["human-review-workflow-report"] == "schemas/HATE/v1/human-review-workflow-report.schema.json"
    assert records["human-review-queue-packet"] == "schemas/HATE/v1/human-review-queue-packet.schema.json"


def test_human_review_queue_packet_ready_for_assigned_review() -> None:
    packet = build_human_review_queue_packet({
        "review": {
            "review_id": "hr-ready",
            "operating_record_id": "finding:OPEN",
            "required_decision": "approve_or_reject",
            "reviewer": "reviewer@example.com",
            "owner": "owner@example.com",
            "due_date": "2026-07-04",
            "expiry_date": "2026-07-10",
            "status": "assigned",
        },
        "actions": [],
    }, source_refs=["fixture://human-review/queue-ready"])

    assert packet["record_type"] == "human-review-queue-packet"
    _assert_queue_packet_contract(packet)
    assert packet["summary"]["ready_for_queue"] is True
    assert packet["queue_item"]["review_id"] == "hr-ready"
    assert packet["allowed_actions"] == ["attach_evidence", "approve", "deny", "expire"]
    assert packet["findings"] == []
    assert packet["sourceRefs"] == ["fixture://human-review/queue-ready"]


def test_human_review_queue_packet_requires_sla_fields() -> None:
    packet = build_human_review_queue_packet({
        "review": {
            "review_id": "hr-no-sla",
            "operating_record_id": "finding:OPEN",
            "reviewer": "reviewer@example.com",
            "owner": "owner@example.com",
            "status": "assigned",
        }
    })

    assert packet["summary"]["ready_for_queue"] is False
    assert "human_review_queue_sla_missing" in _codes(packet)


def test_human_review_queue_packet_blocks_workflow_findings() -> None:
    packet = build_human_review_queue_packet(_fixture("evidence-missing-holds")["input"])

    assert packet["summary"]["ready_for_queue"] is False
    assert "human_review_queue_blocked_by_workflow_findings" in _codes(packet)


def test_human_review_queue_packet_allows_resolution_actions_after_decision() -> None:
    packet = build_human_review_queue_packet({
        "review": {
            "review_id": "hr-approved",
            "operating_record_id": "finding:OPEN",
            "required_decision": "approve_or_reject",
            "reviewer": "reviewer@example.com",
            "owner": "owner@example.com",
            "due_date": "2026-07-04",
            "expiry_date": "2026-07-10",
            "decision": "approve",
            "decision_hash": "sha256:decision",
            "status": "approved",
            "evidence_refs": ["artifact://review/evidence.json"],
        }
    })

    assert packet["summary"]["ready_for_queue"] is True
    assert packet["allowed_actions"] == ["resolve", "revoke", "supersede", "replay"]


def test_human_review_queue_packet_artifact_write_contract(tmp_path: Path) -> None:
    packet = build_human_review_queue_packet({
        "review": {
            "review_id": "hr-artifact",
            "operating_record_id": "finding:OPEN",
            "reviewer": "reviewer@example.com",
            "owner": "owner@example.com",
            "due_date": "2026-07-04",
            "expiry_date": "2026-07-10",
            "status": "assigned",
        }
    }, source_refs=["fixture://human-review/queue-artifact"])
    out_path = tmp_path / "human-review-queue.json"

    artifact = write_human_review_queue_packet(packet, out_path)

    assert artifact["record_type"] == "human-review-queue-packet-artifact"
    assert artifact["allowed_action_count"] == len(packet["allowed_actions"])
    assert artifact["sourceRefs"] == ["fixture://human-review/queue-artifact"]
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["record_type"] == "human-review-queue-packet"
    _assert_queue_packet_contract(written)
