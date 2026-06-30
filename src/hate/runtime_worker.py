from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


RETRYABLE_ERRORS = {"transient_io", "rate_limited"}
NON_RETRYABLE_FAILURES = {"schema_invalid_input"}
POISON_ERRORS = {"invariant_violation"}


@dataclass
class WorkerJobState:
    job_id: str
    tenant_id: str
    kind: str
    status: str
    idempotency_key: str
    attempts: int = 0
    worker_events: list[str] = field(default_factory=list)
    audit_events: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "tenant_id": self.tenant_id,
            "kind": self.kind,
            "status": self.status,
            "idempotency_key": self.idempotency_key,
            "attempts": self.attempts,
            "worker_events": self.worker_events,
            "audit_events": self.audit_events,
            "artifacts": self.artifacts,
            "findings": self.findings,
        }


def evaluate_worker_runtime_fixture(payload: dict[str, Any], *, source_version: str = "unknown") -> dict[str, Any]:
    """Evaluate hosted worker runtime lifecycle behavior from a fixture payload."""
    input_data = payload.get("input", {})
    job = _build_initial_job(input_data)
    idempotency_seen: dict[str, str] = {}
    duplicate_job_id = _check_idempotency(job, idempotency_seen)
    if duplicate_job_id:
        job.audit_events.append(_audit("idempotent_duplicate", f"returned existing job {duplicate_job_id}"))

    if not job.findings:
        for event in input_data.get("worker_events", []):
            _apply_worker_event(job, str(event), input_data)

        error_class = input_data.get("error_class")
        if error_class:
            _apply_error(job, str(error_class), input_data)

        if input_data.get("cancel_requested"):
            _cancel_job(job, input_data)

    if job.status == "succeeded" and not job.artifacts:
        job.artifacts.append(_artifact_for_job(job, input_data))

    decision = _decision_for_job(job)
    return {
        "schema_version": "HATE/v1",
        "record_type": "worker-runtime-report",
        "source_version": source_version,
        "fixture_id": payload.get("fixture_id"),
        "gap_id": payload.get("gap_id", "HATE-GAP-001"),
        "status": decision["status"],
        "readiness_effect": decision["readiness_effect"],
        "finding_code": decision.get("finding_code", ""),
        "job": job.to_dict(),
        "sourceRefs": [payload.get("fixture_id", "runtime-worker-fixture")],
    }


def _build_initial_job(input_data: dict[str, Any]) -> WorkerJobState:
    job = input_data.get("job", {})
    idempotency_key = str(job.get("idempotency_key") or "")
    state = WorkerJobState(
        job_id=str(job.get("job_id") or f"job-{idempotency_key or 'missing'}"),
        tenant_id=str(job.get("tenant_id") or "tenant-local"),
        kind=str(job.get("kind") or "ingest"),
        status=str(job.get("status") or "queued"),
        idempotency_key=idempotency_key,
    )
    if not idempotency_key and state.status == "queued":
        state.status = "failed"
        state.findings.append(_finding("worker_idempotency_key_missing", "Mutating job creation requires idempotency key."))
    return state


def _check_idempotency(job: WorkerJobState, idempotency_seen: dict[str, str]) -> str:
    existing = idempotency_seen.get(job.idempotency_key)
    if existing:
        return existing
    if job.idempotency_key:
        idempotency_seen[job.idempotency_key] = job.job_id
    return ""


def _apply_worker_event(job: WorkerJobState, event: str, input_data: dict[str, Any]) -> None:
    allowed = {
        "queued": {"leased", "cancelling"},
        "leased": {"running", "cancelling"},
        "running": {"succeeded", "retry_wait", "failed", "poison", "cancelling"},
        "retry_wait": {"queued"},
        "cancelling": {"cancelled"},
    }
    if event not in allowed.get(job.status, set()):
        job.status = "poison"
        job.findings.append(_finding("worker_invalid_transition", f"Invalid transition to {event}."))
        job.audit_events.append(_audit("worker_invalid_transition", f"job entered poison from invalid transition to {event}"))
        return
    job.status = event
    job.worker_events.append(event)
    if event == "leased":
        job.attempts += 1
        job.audit_events.append(_audit("lease_acquired", f"attempt {job.attempts} lease acquired"))
    if event == "succeeded":
        job.artifacts.append(_artifact_for_job(job, input_data))


def _apply_error(job: WorkerJobState, error_class: str, input_data: dict[str, Any]) -> None:
    max_attempts = int(input_data.get("retry_policy", {}).get("max_attempts", 3))
    if error_class in RETRYABLE_ERRORS and job.attempts < max_attempts:
        job.status = "retry_wait"
        job.worker_events.append("retry_wait")
        job.audit_events.append(_audit("retry_scheduled", f"{error_class} retry scheduled"))
        return
    if error_class in POISON_ERRORS:
        job.status = "poison"
        job.findings.append(_finding("worker_poison_message", "Invariant violation moved job to poison."))
        job.audit_events.append(_audit("poison_message", "poison state emitted and visible"))
        return
    if error_class in NON_RETRYABLE_FAILURES or error_class in RETRYABLE_ERRORS:
        job.status = "failed"
        job.findings.append(_finding("worker_job_failed", f"{error_class} failed the job."))
        job.audit_events.append(_audit("job_failed", f"{error_class} terminal failure"))
        return
    if error_class == "unsafe_artifact":
        job.status = "succeeded_with_quarantine"
        job.artifacts.append(_artifact_for_job(job, input_data, safety_status="quarantined"))
        job.audit_events.append(_audit("artifact_quarantined", "unsafe artifact quarantined"))


def _cancel_job(job: WorkerJobState, input_data: dict[str, Any]) -> None:
    if job.status not in {"queued", "leased", "running"}:
        return
    job.status = "cancelled"
    job.worker_events.extend(["cancelling", "cancelled"])
    if input_data.get("partial_evidence"):
        job.artifacts.append(_artifact_for_job(job, input_data, retention_class="partial"))
    job.audit_events.append(_audit("job_cancelled", "cancellation preserved partial evidence"))


def _artifact_for_job(
    job: WorkerJobState,
    input_data: dict[str, Any],
    *,
    safety_status: str = "safe",
    retention_class: str = "standard",
) -> dict[str, str]:
    content = json.dumps(
        {
            "job_id": job.job_id,
            "tenant_id": job.tenant_id,
            "kind": job.kind,
            "payload": input_data.get("artifact_payload", "canonical-bundle"),
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return {
        "artifact_id": f"artifact-{job.job_id}",
        "job_id": job.job_id,
        "hash": f"sha256:{digest}",
        "safety_status": safety_status,
        "retention_class": retention_class,
    }


def _decision_for_job(job: WorkerJobState) -> dict[str, str]:
    if job.findings:
        return {
            "status": "hold",
            "readiness_effect": "hold",
            "finding_code": job.findings[0]["code"],
        }
    if job.status in {"succeeded", "cancelled", "succeeded_with_quarantine"}:
        return {"status": "pass", "readiness_effect": "none"}
    return {
        "status": "hold",
        "readiness_effect": "hold",
        "finding_code": "worker_did_not_reach_terminal_state",
    }


def _audit(event_type: str, message: str) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "message": message,
        "source": "runtime_worker",
    }


def _finding(code: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "severity": "high",
        "message": message,
    }
