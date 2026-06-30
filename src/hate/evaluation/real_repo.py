"""Recurring real repository evaluation reports.

Real repository trials are product evidence only when they preserve baseline
comparison, timeout visibility, and subset limitations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REGRESSION_DECISION_ORDER = {
    "blocked": 0,
    "hold": 1,
    "soft_gap": 2,
    "eligible": 3,
    "pass": 3,
}
DEFAULT_TIMEOUT_MS = 900_000


@dataclass(frozen=True)
class RealRepoEvaluationFinding:
    code: str
    severity: str
    readiness_effect: str
    message: str
    sourceRef: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "readiness_effect": self.readiness_effect,
            "message": self.message,
            "sourceRef": self.sourceRef,
        }


def evaluate_real_repo_fixture(payload: dict[str, Any]) -> dict[str, str]:
    """Evaluate a product gap real-repo fixture."""
    report = build_real_repo_evaluation_report(
        payload.get("input", {}),
        report_id=payload.get("fixture_id", "real-repo-evaluation"),
        source_refs=[_fixture_source_ref(payload)],
    )
    finding_code = report["findings"][0]["code"] if report["findings"] else ""
    return {
        "status": report["overall_status"],
        "finding_code": finding_code,
        "readiness_effect": "hold" if report["overall_status"] == "hold" else "none",
    }


def build_real_repo_evaluation_report(
    data: dict[str, Any],
    report_id: str = "real-repo-evaluation",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Build a recurring real repository baseline comparison report."""
    source_refs = source_refs or [f"fixtures/evaluation/real-repo/{report_id}/fixture.json"]
    repo_id = str(data.get("repo_id") or "")
    baseline_decision = str(data.get("baseline_decision") or "")
    current_decision = str(data.get("current_decision") or "")
    timeout_ms = int(data.get("timeout_ms") or DEFAULT_TIMEOUT_MS)
    runtime_ms = int(data.get("runtime_ms") or 0)
    runtime_budget_ms = int(data.get("runtime_budget_ms") or timeout_ms)
    baseline_record_count = _optional_int(data.get("baseline_record_count"))
    current_record_count = _optional_int(data.get("current_record_count"))
    parser_status = str(data.get("parser_status") or "passed")
    unsafe_artifact_findings = int(data.get("unsafe_artifact_findings") or 0)
    subset = bool(data.get("subset") or data.get("subset_command"))
    subset_label = str(data.get("subset_label") or "")

    findings: list[RealRepoEvaluationFinding] = []
    if not repo_id:
        findings.append(_finding(
            "real_repo_repo_id_missing",
            "hold",
            "Repository roster entry is missing repo_id.",
            source_refs[0],
        ))
    if _decision_downgraded(baseline_decision, current_decision):
        findings.append(_finding(
            "real_repo_regression_detected",
            "hold",
            "Current decision is weaker than the stored baseline decision.",
            source_refs[0],
        ))
    if parser_status == "failed":
        findings.append(_finding(
            "real_repo_parser_failure",
            "hold",
            "Real repository evaluation parser failed.",
            source_refs[0],
        ))
    if _record_count_collapsed(baseline_record_count, current_record_count):
        findings.append(_finding(
            "real_repo_record_count_collapse",
            "hold",
            "Current record count collapsed relative to baseline.",
            source_refs[0],
        ))
    if runtime_ms and runtime_ms > runtime_budget_ms:
        findings.append(_finding(
            "real_repo_runtime_budget_exceeded",
            "hold",
            "Real repository evaluation exceeded runtime budget.",
            source_refs[0],
        ))
    if data.get("timeout_recorded") or data.get("timed_out"):
        findings.append(_finding(
            "real_repo_timeout_recorded",
            "hold",
            "Timeout is retained as evidence and cannot be silent.",
            source_refs[0],
        ))
    if unsafe_artifact_findings > 0:
        findings.append(_finding(
            "real_repo_unsafe_artifact_finding",
            "hold",
            "New unsafe artifact finding appeared in real repository trial.",
            source_refs[0],
        ))
    if subset and not subset_label:
        findings.append(_finding(
            "real_repo_subset_unlabeled",
            "hold",
            "Subset evaluation must be labeled and cannot prove full-suite readiness.",
            source_refs[0],
        ))

    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "real-repo-evaluation-report",
        "report_id": report_id,
        "overall_status": status,
        "repo_id": repo_id,
        "baseline": {
            "decision": baseline_decision,
            "record_count": baseline_record_count,
        },
        "current": {
            "decision": current_decision,
            "record_count": current_record_count,
            "parser_status": parser_status,
            "runtime_ms": runtime_ms,
            "unsafe_artifact_findings": unsafe_artifact_findings,
        },
        "timeout_ms": timeout_ms,
        "runtime_budget_ms": runtime_budget_ms,
        "timeout_recorded": bool(data.get("timeout_recorded") or data.get("timed_out")),
        "subset": {
            "is_subset": subset,
            "label": subset_label,
            "limitation_visible": (not subset) or bool(subset_label),
            "proves_full_suite": False if subset else True,
        },
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "finding_count": len(findings),
            "regression_detected": any(
                finding.code.startswith("real_repo_regression") for finding in findings
            ),
            "timeout_recorded": bool(data.get("timeout_recorded") or data.get("timed_out")),
            "subset_limited": subset,
        },
        "sourceRefs": source_refs,
    }


def _decision_downgraded(baseline: str, current: str) -> bool:
    if not baseline or not current:
        return False
    return REGRESSION_DECISION_ORDER.get(current, 0) < REGRESSION_DECISION_ORDER.get(baseline, 0)


def _record_count_collapsed(baseline: int | None, current: int | None) -> bool:
    if baseline is None or current is None or baseline <= 0:
        return False
    return current < max(1, int(baseline * 0.5))


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _finding(
    code: str,
    readiness_effect: str,
    message: str,
    source_ref: str,
) -> RealRepoEvaluationFinding:
    return RealRepoEvaluationFinding(
        code=code,
        severity="high",
        readiness_effect=readiness_effect,
        message=message,
        sourceRef=source_ref,
    )


def _fixture_source_ref(payload: dict[str, Any]) -> str:
    fixture_id = str(payload.get("fixture_id") or "fixture")
    return f"fixtures/evaluation/real-repo/{fixture_id}/fixture.json"
