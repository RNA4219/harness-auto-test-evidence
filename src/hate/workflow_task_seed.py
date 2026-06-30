"""Workflow-cookbook Task Seed loop evaluation for HATE-GAP-021."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


HIDDEN_WORK_KEYWORDS = {"future", "optional", "advisory", "later", "todo"}


@dataclass(frozen=True)
class TaskSeedFinding:
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


def evaluate_task_seed_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = dict(payload.get("input", {}))
    report = build_task_seed_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "workflow-task-seed-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
        default_task_id=str(payload.get("task_seed_id") or ""),
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_task_seed_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "workflow-task-seed-report",
    source_refs: list[str] | None = None,
    default_task_id: str = "",
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["workflow-task-seed"])
    seed = _normalize_task_seed(input_data.get("task_seed", input_data), default_task_id)
    findings = _findings_for(seed, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "workflow-task-seed-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "task_seed": seed,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "task_id": seed["task_id"],
            "command_count": len(seed["commands"]),
            "dependency_count": len(seed["dependencies"]),
            "finding_count": len(findings),
            "slice_days": seed["slice_days"],
            "changes_generated_artifacts": seed["changes_generated_artifacts"],
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_task_seed(raw_seed: dict[str, Any], default_task_id: str) -> dict[str, Any]:
    seed = dict(raw_seed or {})
    scope = dict(seed.get("scope") or {})
    requirements = dict(seed.get("requirements") or {})
    return {
        "task_id": str(seed.get("task_id") or default_task_id),
        "objective": str(seed.get("objective") or ""),
        "scope": {
            "in": list(scope.get("in") or []),
            "out": list(scope.get("out") or []),
        },
        "requirements": {
            "behavior": list(requirements.get("behavior") or []),
            "constraints": list(requirements.get("constraints") or []),
        },
        "commands": list(seed.get("commands") or []),
        "dependencies": list(seed.get("dependencies") or []),
        "slice_days": float(seed.get("slice_days", seed.get("estimate_days", 0.5))),
        "packet_size_days": float(seed.get("packet_size_days", seed.get("slice_days", seed.get("estimate_days", 0.5)))),
        "seed_slices": list(seed.get("seed_slices") or []),
        "changes_generated_artifacts": bool(seed.get("changes_generated_artifacts", False)),
        "birdseye_update": bool(seed.get("birdseye_update", not seed.get("changes_generated_artifacts", False))),
        "status": str(seed.get("status") or "planned"),
        "acceptance_record": str(seed.get("acceptance_record") or ""),
        "exception_reason": str(seed.get("exception_reason") or ""),
    }


def _findings_for(seed: dict[str, Any], source_ref: str) -> list[TaskSeedFinding]:
    findings: list[TaskSeedFinding] = []
    if not seed["task_id"]:
        findings.append(_finding("task_seed_missing_task_id", "Task Seed requires stable task_id.", source_ref))
    if not seed["objective"]:
        findings.append(_finding("task_seed_missing_objective", "Task Seed requires concrete objective.", source_ref))
    if not seed["scope"]["in"] or not seed["scope"]["out"]:
        findings.append(_finding("task_seed_missing_scope", "Task Seed requires scope.in and scope.out.", source_ref))
    if not seed["requirements"]["behavior"]:
        findings.append(_finding("task_seed_missing_behavior", "Task Seed requires observable behavior.", source_ref))
    if not seed["requirements"]["constraints"]:
        findings.append(_finding("task_seed_missing_constraints", "Task Seed requires constraints.", source_ref))
    if not seed["commands"]:
        findings.append(_finding("task_seed_missing_commands", "Task Seed requires verification commands.", source_ref))
    if not seed["dependencies"]:
        findings.append(_finding("task_seed_missing_dependencies", "Task Seed requires dependency references.", source_ref))
    if _contains_hidden_work_language(seed):
        findings.append(_finding(
            "task_seed_hides_missing_work",
            "Task Seed must not hide missing implementation behind future, optional, advisory, later, or todo wording.",
            source_ref,
        ))
    if seed["slice_days"] > 0.5:
        findings.append(_finding("task_seed_slice_too_large", "Task Seed target size must be at most 0.5d.", source_ref))
    if seed["packet_size_days"] > 0.5 and not seed["seed_slices"]:
        findings.append(_finding(
            "task_seed_large_packet_unsplit",
            "Large packet must split into schema, runtime, fixture, and UAT seeds.",
            source_ref,
        ))
    if seed["changes_generated_artifacts"] and not seed["birdseye_update"]:
        findings.append(_finding(
            "task_seed_birdseye_update_missing",
            "Task Seed changing generated artifacts must say when Birdseye/codemap is updated.",
            source_ref,
        ))
    if seed["status"] == "done" and not seed["acceptance_record"] and not seed["exception_reason"]:
        findings.append(_finding(
            "task_seed_done_missing_acceptance",
            "Done Task Seed requires acceptance record or documented exception.",
            source_ref,
        ))
    return findings


def _contains_hidden_work_language(seed: dict[str, Any]) -> bool:
    values: list[str] = [seed["objective"]]
    values.extend(seed["scope"]["in"])
    values.extend(seed["scope"]["out"])
    values.extend(seed["requirements"]["behavior"])
    values.extend(seed["requirements"]["constraints"])
    text = " ".join(values).lower()
    return any(keyword in text for keyword in HIDDEN_WORK_KEYWORDS)


def _finding(code: str, message: str, source_ref: str) -> TaskSeedFinding:
    return TaskSeedFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
