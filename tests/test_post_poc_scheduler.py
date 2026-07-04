from __future__ import annotations

import json
from pathlib import Path

from hate.post_poc.scheduler import (
    build_hosted_scheduler_report,
    build_scheduler_dispatch_plan,
    evaluate_scheduler_fixture,
    write_scheduler_dispatch_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc" / "scheduler"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "hosted-scheduler-runtime-report.schema.json"
DISPATCH_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "hosted-scheduler-dispatch-manifest.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "hosted-scheduler-runtime-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert report["worker_state"]["record_type"] == "hosted-scheduler-worker-state"
    for event in report["lease_events"]:
        assert event["record_type"] == "hosted-scheduler-lease-event"
        assert event["sourceRefs"]
    for result in report["job_results"]:
        assert result["record_type"] == "hosted-scheduler-job-result"
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def _assert_dispatch_manifest_contract(manifest: dict) -> None:
    schema = json.loads(DISPATCH_SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(manifest)
    assert manifest["schema_version"] == "HATE/v1"
    assert manifest["record_type"] == "hosted-scheduler-dispatch-manifest"
    assert manifest["max_concurrency"] >= 1
    for entry in manifest["dispatch_entries"]:
        assert set(schema["properties"]["dispatch_entries"]["items"]["required"]) <= set(entry)
        assert entry["record_type"] == "hosted-scheduler-dispatch-entry"
        assert entry["sourceRefs"]


def test_task_postpoc_001_canonical_fixture_paths_exist() -> None:
    for name in [
        "lease-acquire-heartbeat",
        "stale-lease-recovered",
        "cancel-requested",
        "retry-budget-exhausted",
        "resume-token-missing",
    ]:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_lease_acquire_heartbeat_fixture_passes() -> None:
    result = evaluate_scheduler_fixture(_fixture("lease-acquire-heartbeat"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    assert result["report"]["worker_state"]["lease_state"] == "completed"
    assert result["report"]["summary"]["job_result_count"] == 1
    _assert_report_contract(result["report"])


def test_stale_lease_recovered_holds_but_preserves_resume_token() -> None:
    result = evaluate_scheduler_fixture(_fixture("stale-lease-recovered"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "scheduler_worker_heartbeat_missing"
    assert "scheduler_lease_expired" in _codes(result["report"])
    assert result["report"]["worker_state"]["resume_token"] == "resume-job-002"
    assert result["report"]["worker_state"]["lease_state"] == "available"


def test_cancel_without_actor_holds_and_writes_event() -> None:
    result = evaluate_scheduler_fixture(_fixture("cancel-requested"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "scheduler_cancel_without_actor"
    assert result["report"]["lease_events"][0]["after_state"] == "cancel_requested"


def test_retry_budget_exhausted_holds() -> None:
    result = evaluate_scheduler_fixture(_fixture("retry-budget-exhausted"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "scheduler_retry_budget_exhausted"
    assert result["report"]["worker_state"]["lease_state"] == "failed"


def test_resume_token_missing_holds() -> None:
    result = evaluate_scheduler_fixture(_fixture("resume-token-missing"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "scheduler_resume_token_missing"


def test_failed_job_requires_failure_kind_excerpt_and_cleanup() -> None:
    report = build_hosted_scheduler_report({
        "job": {
            "worker_id": "worker-a",
            "lease_id": "lease-006",
            "job_id": "job-006",
            "lease_state": "leased",
        },
        "events": [{"event_type": "job_failed", "cleanup_status": "failed", "sourceRefs": ["failure"]}],
    })

    assert report["overall_status"] == "hold"
    assert "scheduler_cleanup_failed" in _codes(report)
    assert report["job_results"][0]["status"] == "failed"


def test_hosted_scheduler_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["hosted-scheduler-runtime-report"] == "schemas/HATE/v1/hosted-scheduler-runtime-report.schema.json"
    assert records["hosted-scheduler-dispatch-manifest"] == "schemas/HATE/v1/hosted-scheduler-dispatch-manifest.schema.json"


def test_scheduler_dispatch_plan_shards_jobs_deterministically() -> None:
    plan = build_scheduler_dispatch_plan({
        "queue_id": "bulk",
        "max_concurrency": 2,
        "jobs": [
            {"job_id": "job-c", "repo_id": "repo-c", "suite_id": "unit", "priority": 20, "sourceRef": "job://c"},
            {"job_id": "job-a", "repo_id": "repo-a", "suite_id": "unit", "priority": 10, "sourceRef": "job://a"},
            {"job_id": "job-b", "repo_id": "repo-b", "suite_id": "unit", "priority": 10, "sourceRef": "job://b"},
        ],
    }, source_refs=["fixture://scheduler/dispatch"])

    assert plan["record_type"] == "hosted-scheduler-dispatch-plan"
    assert plan["summary"]["ready_for_dispatch"] is True
    assert plan["summary"]["job_count"] == 3
    assert plan["summary"]["shard_count"] == 2
    assert [entry["job_id"] for entry in plan["dispatch_entries"]] == ["job-a", "job-b", "job-c"]
    assert {entry["shard_id"] for entry in plan["dispatch_entries"]} == {"bulk:shard-1", "bulk:shard-2"}
    assert plan["sourceRefs"] == ["fixture://scheduler/dispatch"]


def test_scheduler_dispatch_plan_requires_resume_token_for_partial_result() -> None:
    plan = build_scheduler_dispatch_plan({
        "queue_id": "bulk",
        "max_concurrency": 1,
        "jobs": [
            {
                "job_id": "job-partial",
                "repo_id": "repo-a",
                "suite_id": "unit",
                "partial_result_ref": "artifact://partial/job-partial.json",
            }
        ],
    })

    assert plan["summary"]["ready_for_dispatch"] is False
    assert "scheduler_resume_token_missing" in _codes(plan)


def test_scheduler_dispatch_plan_detects_duplicate_jobs_and_retry_budget() -> None:
    plan = build_scheduler_dispatch_plan({
        "queue_id": "bulk",
        "max_concurrency": 2,
        "jobs": [
            {"job_id": "job-a", "repo_id": "repo-a", "suite_id": "unit", "attempt": 1, "max_attempts": 1},
            {"job_id": "job-a", "repo_id": "repo-a", "suite_id": "integration", "attempt": 0, "max_attempts": 2},
        ],
    })

    assert "scheduler_dispatch_duplicate_job" in _codes(plan)
    assert "scheduler_retry_budget_exhausted" in _codes(plan)


def test_scheduler_dispatch_plan_rejects_invalid_concurrency_or_empty_jobs() -> None:
    plan = build_scheduler_dispatch_plan({"queue_id": "bulk", "max_concurrency": 0, "jobs": []})

    assert "scheduler_dispatch_concurrency_invalid" in _codes(plan)
    assert "scheduler_dispatch_jobs_missing" in _codes(plan)
    assert plan["dispatch_entries"] == []


def test_scheduler_dispatch_manifest_write_contract(tmp_path: Path) -> None:
    plan = build_scheduler_dispatch_plan({
        "queue_id": "bulk",
        "max_concurrency": 1,
        "jobs": [{"job_id": "job-a", "repo_id": "repo-a", "suite_id": "unit"}],
    }, source_refs=["fixture://scheduler/manifest"])
    out_path = tmp_path / "scheduler-dispatch.json"

    artifact = write_scheduler_dispatch_manifest(plan, out_path)

    assert artifact["record_type"] == "hosted-scheduler-dispatch-manifest-artifact"
    assert artifact["dispatch_entry_count"] == 1
    assert artifact["sourceRefs"] == ["fixture://scheduler/manifest"]
    manifest = json.loads(out_path.read_text(encoding="utf-8"))
    assert manifest["record_type"] == "hosted-scheduler-dispatch-manifest"
    _assert_dispatch_manifest_contract(manifest)
    assert manifest["dispatch_entries"][0]["job_id"] == "job-a"
