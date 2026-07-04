from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .common import apply_productization_contract_tree, productization_envelope


@dataclass(frozen=True)
class SchedulerFinding:
    code: str
    severity: str
    message: str
    sourceRef: str
    readiness_effect: str = "hold"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRef": self.sourceRef,
            "readiness_effect": self.readiness_effect,
        }


def evaluate_scheduler_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_hosted_scheduler_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "hosted-scheduler-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_hosted_scheduler_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "hosted-scheduler-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["hosted-scheduler"])
    job = _normalize_job(input_data.get("job", input_data))
    events = [_normalize_event(event) for event in input_data.get("events", [])]
    state, lease_events, job_results, findings = _reduce_events(job, events, source_refs[0])
    status = "hold" if findings else "pass"
    report = {
        "schema_version": "HATE/v1",
        "record_type": "hosted-scheduler-runtime-report",
        "report_id": report_id,
        **productization_envelope(input_data, report_id=report_id, source_refs=source_refs),
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "worker_state": state,
        "lease_events": lease_events,
        "job_results": job_results,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "event_count": len(events),
            "lease_event_count": len(lease_events),
            "job_result_count": len(job_results),
            "finding_count": len(findings),
            "final_lease_state": state["lease_state"],
            "resume_token_present": bool(state["resume_token"]),
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(report, source_refs=source_refs)


def build_scheduler_dispatch_plan(
    input_data: dict[str, Any],
    *,
    plan_id: str = "hosted-scheduler-dispatch-plan",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["hosted-scheduler-dispatch"])
    max_concurrency = int(input_data.get("max_concurrency", 1))
    queue_id = str(input_data.get("queue_id") or "default")
    jobs = [_normalize_dispatch_job(job) for job in input_data.get("jobs", [])]
    if not jobs and input_data.get("job"):
        jobs = [_normalize_dispatch_job(input_data["job"])]
    dispatch_entries = _dispatch_entries_for(queue_id, jobs, max_concurrency)
    findings = _dispatch_findings(jobs, dispatch_entries, max_concurrency, source_refs[0])
    plan = {
        "schema_version": "HATE/v1",
        "record_type": "hosted-scheduler-dispatch-plan",
        "plan_id": plan_id,
        **productization_envelope(input_data, report_id=plan_id, source_refs=source_refs),
        "readiness_effect": "hold" if findings else "none",
        "queue_id": queue_id,
        "max_concurrency": max_concurrency,
        "dispatch_entries": dispatch_entries,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "job_count": len(jobs),
            "dispatch_entry_count": len(dispatch_entries),
            "shard_count": len({entry["shard_id"] for entry in dispatch_entries}),
            "resume_required_count": sum(1 for entry in dispatch_entries if entry["resume_required"]),
            "finding_count": len(findings),
            "ready_for_dispatch": not findings,
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(plan, source_refs=source_refs)


def write_scheduler_dispatch_manifest(plan: dict[str, Any], out_path: str | Path) -> dict[str, Any]:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "HATE/v1",
        "record_type": "hosted-scheduler-dispatch-manifest",
        "plan_id": str(plan.get("plan_id") or ""),
        **productization_envelope(plan, report_id=str(plan.get("plan_id") or "hosted-scheduler-dispatch-manifest"), source_refs=list(plan.get("sourceRefs", []))),
        "readiness_effect": str(plan.get("readiness_effect") or "none"),
        "queue_id": str(plan.get("queue_id") or ""),
        "max_concurrency": int(plan.get("max_concurrency") or 1),
        "dispatch_entries": list(plan.get("dispatch_entries", [])),
        "sourceRefs": list(plan.get("sourceRefs", [])),
    }
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {
        "schema_version": "HATE/v1",
        "record_type": "hosted-scheduler-dispatch-manifest-artifact",
        **productization_envelope(manifest, report_id=f"{manifest['plan_id']}:artifact", source_refs=manifest["sourceRefs"]),
        "readiness_effect": manifest["readiness_effect"],
        "artifact_path": str(path),
        "dispatch_entry_count": len(manifest["dispatch_entries"]),
        "sourceRefs": manifest["sourceRefs"],
    }


def _normalize_dispatch_job(raw: dict[str, Any]) -> dict[str, Any]:
    job = _normalize_job(raw)
    job.update({
        "repo_id": str(raw.get("repo_id") or ""),
        "suite_id": str(raw.get("suite_id") or ""),
        "priority": int(raw.get("priority") or 100),
        "estimated_cost": int(raw.get("estimated_cost") or 1),
        "sourceRef": str(raw.get("sourceRef") or raw.get("job_id") or "dispatch-job"),
    })
    return job


def _dispatch_entries_for(queue_id: str, jobs: list[dict[str, Any]], max_concurrency: int) -> list[dict[str, Any]]:
    if max_concurrency < 1:
        return []
    ordered = sorted(jobs, key=lambda job: (job["priority"], job["repo_id"], job["suite_id"], job["job_id"]))
    entries: list[dict[str, Any]] = []
    for index, job in enumerate(ordered):
        shard_index = index % max_concurrency
        dispatch_key = _stable_digest({
            "queue_id": queue_id,
            "job_id": job["job_id"],
            "repo_id": job["repo_id"],
            "suite_id": job["suite_id"],
            "attempt": job["attempt"],
        })
        entries.append({
            "record_type": "hosted-scheduler-dispatch-entry",
            "dispatch_key": dispatch_key,
            "queue_id": queue_id,
            "shard_id": f"{queue_id}:shard-{shard_index + 1}",
            "job_id": job["job_id"],
            "job_kind": job["job_kind"],
            "repo_id": job["repo_id"],
            "suite_id": job["suite_id"],
            "priority": job["priority"],
            "estimated_cost": job["estimated_cost"],
            "attempt": job["attempt"],
            "max_attempts": job["max_attempts"],
            "resume_required": bool(job["partial_result_ref"]),
            "resume_token": job["resume_token"],
            "partial_result_ref": job["partial_result_ref"],
            "sourceRefs": [job["sourceRef"]],
        })
    return entries


def _dispatch_findings(
    jobs: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    max_concurrency: int,
    source_ref: str,
) -> list[SchedulerFinding]:
    findings: list[SchedulerFinding] = []
    if max_concurrency < 1:
        findings.append(_finding("scheduler_dispatch_concurrency_invalid", "Dispatch plan requires max_concurrency >= 1.", source_ref))
    if not jobs:
        findings.append(_finding("scheduler_dispatch_jobs_missing", "Dispatch plan requires at least one job.", source_ref))
    job_ids = [job["job_id"] for job in jobs]
    if any(not job_id for job_id in job_ids):
        findings.append(_finding("scheduler_dispatch_job_id_missing", "Every dispatch job requires job_id.", source_ref))
    duplicates = sorted({job_id for job_id in job_ids if job_id and job_ids.count(job_id) > 1})
    if duplicates:
        findings.append(_finding("scheduler_dispatch_duplicate_job", f"Duplicate dispatch jobs: {', '.join(duplicates)}.", source_ref))
    if any(entry["resume_required"] and not entry["resume_token"] for entry in entries):
        findings.append(_finding("scheduler_resume_token_missing", "Dispatch entries with partial results require resume_token.", source_ref))
    if any(entry["attempt"] >= entry["max_attempts"] for entry in entries):
        findings.append(_finding("scheduler_retry_budget_exhausted", "Dispatch entry attempt is at or above max_attempts.", source_ref))
    return findings


def _normalize_job(raw: dict[str, Any]) -> dict[str, Any]:
    job = dict(raw or {})
    return {
        "worker_id": str(job.get("worker_id") or ""),
        "queue_id": str(job.get("queue_id") or "default"),
        "lease_id": str(job.get("lease_id") or ""),
        "job_id": str(job.get("job_id") or ""),
        "job_kind": str(job.get("job_kind") or "repo_suite_run"),
        "lease_state": str(job.get("lease_state") or "available"),
        "heartbeat_at": str(job.get("heartbeat_at") or ""),
        "lease_expires_at": str(job.get("lease_expires_at") or ""),
        "retry_after": str(job.get("retry_after") or ""),
        "attempt": int(job.get("attempt") or 0),
        "max_attempts": int(job.get("max_attempts") or 1),
        "resume_token": str(job.get("resume_token") or ""),
        "partial_result_ref": str(job.get("partial_result_ref") or ""),
        "cleanup_status": str(job.get("cleanup_status") or "not_started"),
    }


def _normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    event = dict(raw or {})
    return {
        "event_type": str(event.get("event_type") or ""),
        "worker_id": str(event.get("worker_id") or ""),
        "lease_expires_at": str(event.get("lease_expires_at") or ""),
        "heartbeat_at": str(event.get("heartbeat_at") or ""),
        "actor": str(event.get("actor") or ""),
        "reason": str(event.get("reason") or ""),
        "retry_after": str(event.get("retry_after") or ""),
        "resume_token": str(event.get("resume_token") or ""),
        "partial_result_ref": str(event.get("partial_result_ref") or ""),
        "cleanup_status": str(event.get("cleanup_status") or ""),
        "result_hash": str(event.get("result_hash") or ""),
        "failure_kind": str(event.get("failure_kind") or ""),
        "excerpt_ref": str(event.get("excerpt_ref") or ""),
        "sourceRefs": [str(item) for item in event.get("sourceRefs", [])],
    }


def _reduce_events(
    job: dict[str, Any],
    events: list[dict[str, Any]],
    source_ref: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[SchedulerFinding]]:
    state = dict(job)
    lease_events: list[dict[str, Any]] = []
    job_results: list[dict[str, Any]] = []
    findings: list[SchedulerFinding] = []
    heartbeat_seen = bool(state["heartbeat_at"])

    for index, event in enumerate(events):
        event_type = event["event_type"]
        event_ref = event["sourceRefs"][0] if event["sourceRefs"] else f"{source_ref}#/events/{index}"
        before = state["lease_state"]

        if event_type == "lease_acquired":
            if not event["worker_id"] or not event["lease_expires_at"]:
                findings.append(_finding("scheduler_worker_heartbeat_missing", "Lease acquisition requires worker_id and lease_expires_at.", event_ref))
            state["worker_id"] = event["worker_id"] or state["worker_id"]
            state["lease_expires_at"] = event["lease_expires_at"] or state["lease_expires_at"]
            state["lease_state"] = "leased"
        elif event_type == "heartbeat_seen":
            if not event["heartbeat_at"] or (state["heartbeat_at"] and event["heartbeat_at"] < state["heartbeat_at"]):
                findings.append(_finding("scheduler_worker_heartbeat_missing", "Heartbeat is missing or non-monotonic.", event_ref))
            state["heartbeat_at"] = event["heartbeat_at"] or state["heartbeat_at"]
            heartbeat_seen = True
            state["lease_state"] = "leased"
        elif event_type == "cancel_requested":
            if not event["actor"] or not event["reason"]:
                findings.append(_finding("scheduler_cancel_without_actor", "Cancellation requires actor and reason.", event_ref))
            state["lease_state"] = "cancel_requested"
        elif event_type == "lease_expired":
            if not heartbeat_seen:
                findings.append(_finding("scheduler_worker_heartbeat_missing", "Lease expired without observed heartbeat.", event_ref))
            findings.append(_finding("scheduler_lease_expired", "Expired lease cannot be treated as pass.", event_ref))
            state["lease_state"] = "expired"
        elif event_type == "retry_scheduled":
            if state["attempt"] >= state["max_attempts"]:
                findings.append(_finding("scheduler_retry_budget_exhausted", "Retry requested after max_attempts was reached.", event_ref))
                state["lease_state"] = "failed"
            else:
                state["attempt"] += 1
                state["retry_after"] = event["retry_after"] or state["retry_after"]
                state["resume_token"] = event["resume_token"] or state["resume_token"]
                state["partial_result_ref"] = event["partial_result_ref"] or state["partial_result_ref"]
                if state["partial_result_ref"] and not state["resume_token"]:
                    findings.append(_finding("scheduler_resume_token_missing", "Partial result retry requires resume_token.", event_ref))
                state["lease_state"] = "available"
        elif event_type == "job_completed":
            if not event["result_hash"] or not event["sourceRefs"]:
                findings.append(_finding("scheduler_cleanup_failed", "Completed job requires result_hash and sourceRefs.", event_ref))
            state["cleanup_status"] = event["cleanup_status"] or state["cleanup_status"]
            state["lease_state"] = "completed"
            job_results.append(_job_result(state, event, "completed"))
        elif event_type == "job_failed":
            if not event["failure_kind"] or not event["excerpt_ref"]:
                findings.append(_finding("scheduler_cleanup_failed", "Failed job requires failure_kind and excerpt_ref.", event_ref))
            if event["cleanup_status"] and event["cleanup_status"] != "complete":
                findings.append(_finding("scheduler_cleanup_failed", "Failed job cleanup did not complete.", event_ref))
            state["cleanup_status"] = event["cleanup_status"] or state["cleanup_status"]
            state["lease_state"] = "failed"
            job_results.append(_job_result(state, event, "failed"))
        else:
            findings.append(_finding("scheduler_cleanup_failed", f"Unsupported scheduler event: {event_type}.", event_ref))

        lease_events.append({
            "record_type": "hosted-scheduler-lease-event",
            "event_type": event_type,
            "before_state": before,
            "after_state": state["lease_state"],
            "worker_id": state["worker_id"],
            "queue_id": state["queue_id"],
            "lease_id": state["lease_id"],
            "job_id": state["job_id"],
            "sourceRefs": event["sourceRefs"] or [event_ref],
        })

    if state["partial_result_ref"] and not state["resume_token"] and not any(item.code == "scheduler_resume_token_missing" for item in findings):
        findings.append(_finding("scheduler_resume_token_missing", "Partial result requires resume_token.", source_ref))

    state["record_type"] = "hosted-scheduler-worker-state"
    return state, lease_events, job_results, findings


def _job_result(state: dict[str, Any], event: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "record_type": "hosted-scheduler-job-result",
        "job_id": state["job_id"],
        "worker_id": state["worker_id"],
        "queue_id": state["queue_id"],
        "lease_id": state["lease_id"],
        "status": status,
        "result_hash": event["result_hash"],
        "failure_kind": event["failure_kind"],
        "excerpt_ref": event["excerpt_ref"],
        "cleanup_status": state["cleanup_status"],
        "sourceRefs": event["sourceRefs"],
    }


def _finding(code: str, message: str, source_ref: str) -> SchedulerFinding:
    return SchedulerFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )


def _stable_digest(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
