"""GitHub Action/App integration evaluator for HATE-GAP-005."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


SURFACE_REQUIRED_PERMISSIONS = {
    "check_run": {"checks:write", "pull-requests:read"},
    "pr_comment": {"issues:write", "pull-requests:read"},
    "changed_files": {"pull-requests:read", "contents:read"},
    "workflow_run": {"actions:read"},
}

FORBIDDEN_NORMAL_PR_PERMISSIONS = {"administration:write", "contents:write", "actions:write"}
UNSAFE_MARKERS = ("secret", "token", "private_key", "unsafe", "raw_artifact_path")


@dataclass
class GitHubFinding:
    code: str
    severity: str
    message: str
    source_refs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "source_refs": self.source_refs,
        }


@dataclass
class GitHubIntegrationDecision:
    surface: str
    actor: str
    permissions: list[str]
    status: str
    readiness_effect: str
    annotation_count: int
    unsafe_artifact_count: int
    redacted_annotation_count: int
    run_id: str
    previous_run_id: str
    rerun_linked: bool
    canonical_evidence_mutated: bool
    findings: list[GitHubFinding]
    audit_event: dict[str, Any]

    def as_report(self, *, source_version: str, source_refs: list[str]) -> dict[str, Any]:
        report = {
            "schema_version": "HATE/v1",
            "record_type": "github-integration-report",
            "source_version": source_version,
            "status": self.status,
            "readiness_effect": self.readiness_effect,
            "surface": self.surface,
            "actor": self.actor,
            "permissions": self.permissions,
            "annotation_count": self.annotation_count,
            "unsafe_artifact_count": self.unsafe_artifact_count,
            "redacted_annotation_count": self.redacted_annotation_count,
            "run_id": self.run_id,
            "previous_run_id": self.previous_run_id,
            "rerun_linked": self.rerun_linked,
            "canonical_evidence_mutated": self.canonical_evidence_mutated,
            "audit_events": [self.audit_event],
            "findings": [finding.as_dict() for finding in self.findings],
            "sourceRefs": source_refs,
        }
        if self.findings:
            report["finding_code"] = self.findings[0].code
        return report


def evaluate_github_integration_fixture(payload: dict[str, Any], *, source_version: str = "unknown") -> dict[str, Any]:
    data = payload.get("input", {})
    decision = evaluate_github_integration(data)
    return decision.as_report(source_version=source_version, source_refs=[str(payload.get("fixture_id") or "github-fixture")])


def evaluate_github_integration(data: dict[str, Any]) -> GitHubIntegrationDecision:
    surface = str(data.get("surface") or "check_run")
    actor = str(data.get("actor") or ("github_app" if surface in {"check_run", "pr_comment"} else "github_action"))
    permissions = sorted(str(item) for item in data.get("permissions", []))
    permission_set = set(permissions)
    annotations = data.get("annotations", [])
    annotation_count = len(annotations) if isinstance(annotations, list) else int(data.get("annotation_count") or 0)
    unsafe_artifact_count = int(data.get("unsafe_artifacts") or 0)
    redacted_annotation_count = int(data.get("redacted_annotations") or 0)
    run_id = str(data.get("run_id") or "run-current")
    previous_run_id = str(data.get("previous_run_id") or "")
    rerun = bool(data.get("rerun"))
    rerun_linked = bool(data.get("rerun_linked")) or bool(rerun and previous_run_id and run_id)
    canonical_mutated = bool(data.get("canonical_evidence_mutated"))

    findings: list[GitHubFinding] = []
    missing_permissions = sorted(SURFACE_REQUIRED_PERMISSIONS.get(surface, set()) - permission_set)
    explicit_required = str(data.get("required") or "")
    if explicit_required and explicit_required not in permission_set:
        missing_permissions.append(explicit_required)
    if missing_permissions:
        findings.append(_finding(
            "github_permission_denied",
            "high",
            f"missing GitHub permissions: {', '.join(sorted(set(missing_permissions)))}",
        ))

    broad_permissions = sorted(permission_set & FORBIDDEN_NORMAL_PR_PERMISSIONS)
    if broad_permissions and surface in {"check_run", "pr_comment", "changed_files"}:
        findings.append(_finding(
            "github_broad_permission_denied",
            "critical",
            f"normal PR loop must not request broad permissions: {', '.join(broad_permissions)}",
        ))

    if _annotations_leak_unsafe_data(annotations) or (unsafe_artifact_count and redacted_annotation_count < unsafe_artifact_count):
        findings.append(_finding(
            "github_unsafe_annotation_denied",
            "critical",
            "GitHub annotations must redact unsafe artifact data and raw paths",
        ))

    if rerun and not rerun_linked:
        findings.append(_finding(
            "github_rerun_missing_evidence_link",
            "high",
            "rerun must link the previous evidence run id",
        ))

    if canonical_mutated:
        findings.append(_finding(
            "github_canonical_mutation_denied",
            "critical",
            "GitHub surface must not mutate canonical HATE evidence",
        ))

    status = "hold" if findings else "pass"
    audit_event = _audit_event(
        surface=surface,
        actor=actor,
        permissions=permissions,
        decision="allow" if status == "pass" else "deny",
        finding_code=findings[0].code if findings else "",
        run_id=run_id,
        previous_run_id=previous_run_id,
    )
    return GitHubIntegrationDecision(
        surface=surface,
        actor=actor,
        permissions=permissions,
        status=status,
        readiness_effect="hold" if findings else "none",
        annotation_count=annotation_count,
        unsafe_artifact_count=unsafe_artifact_count,
        redacted_annotation_count=redacted_annotation_count,
        run_id=run_id,
        previous_run_id=previous_run_id,
        rerun_linked=rerun_linked,
        canonical_evidence_mutated=canonical_mutated,
        findings=findings,
        audit_event=audit_event,
    )


def _annotations_leak_unsafe_data(annotations: Any) -> bool:
    if not isinstance(annotations, list):
        return False
    for annotation in annotations:
        if not isinstance(annotation, dict):
            continue
        if annotation.get("safe") is False:
            return True
        if annotation.get("safe") is True:
            continue
        text = " ".join(str(annotation.get(key, "")) for key in ("message", "path", "raw_details")).lower()
        if any(marker in text for marker in UNSAFE_MARKERS):
            return True
    return False


def _finding(code: str, severity: str, message: str) -> GitHubFinding:
    return GitHubFinding(
        code=code,
        severity=severity,
        message=message,
        source_refs=["docs/process/GITHUB_INTEGRATION_CONTRACT.md"],
    )


def _audit_event(
    *,
    surface: str,
    actor: str,
    permissions: list[str],
    decision: str,
    finding_code: str,
    run_id: str,
    previous_run_id: str,
) -> dict[str, Any]:
    return {
        "event_type": "github_integration_decision",
        "surface": surface,
        "actor": actor,
        "permissions": permissions,
        "decision": decision,
        "finding_code": finding_code,
        "run_id": run_id,
        "previous_run_id": previous_run_id,
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
