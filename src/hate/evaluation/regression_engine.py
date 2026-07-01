"""Regression classification for recurring real-repo evaluation."""

from __future__ import annotations

from typing import Any


DECISION_ORDER = {
    "blocked": 0,
    "hold": 1,
    "soft_gap": 2,
    "eligible": 3,
    "pass": 3,
}
DEFAULT_RECORD_DROP_RATIO = 0.5
DEFAULT_RUNTIME_DRIFT_RATIO = 1.5


def classify_real_repo_regressions(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return regression classifications for a real-repo evaluation input."""
    regressions: list[dict[str, Any]] = []
    baseline_decision = str(data.get("baseline_decision") or "")
    current_decision = str(data.get("current_decision") or "")
    baseline_record_count = _optional_int(data.get("baseline_record_count"))
    current_record_count = _optional_int(data.get("current_record_count"))
    baseline_runtime_ms = _optional_int(data.get("baseline_runtime_ms"))
    runtime_ms = _optional_int(data.get("runtime_ms"))
    baseline_failure_kind = str(data.get("baseline_failure_kind") or "")
    current_failure_kind = str(data.get("failure_kind") or data.get("current_failure_kind") or "")
    ownership_scope = str(data.get("ownership_scope") or "owned")
    command_exit_code = data.get("command_exit_code")
    timed_out = bool(data.get("timeout_recorded") or data.get("timed_out"))
    record_drop_ratio = float(data.get("record_drop_ratio") or DEFAULT_RECORD_DROP_RATIO)
    runtime_drift_ratio = float(data.get("runtime_drift_ratio") or DEFAULT_RUNTIME_DRIFT_RATIO)

    if ownership_scope == "external" and _external_hold(current_decision, command_exit_code, timed_out, current_failure_kind):
        regressions.append(_regression(
            "external_hold_detected",
            "real_repo_external_hold_detected",
            "External repository hold is retained as product evidence but is not a HATE implementation failure.",
            {
                "ownership_scope": ownership_scope,
                "current_decision": current_decision,
                "command_exit_code": command_exit_code,
                "current_failure_kind": current_failure_kind,
                "timeout_recorded": timed_out,
                "implementation_failure": False,
            },
        ))
    if _decision_downgraded(baseline_decision, current_decision):
        regressions.append(_regression(
            "status_regression",
            "real_repo_regression_detected",
            "Current decision is weaker than the stored baseline decision.",
            {"baseline_decision": baseline_decision, "current_decision": current_decision},
        ))
    if _record_count_collapsed(baseline_record_count, current_record_count, record_drop_ratio):
        regressions.append(_regression(
            "record_count_collapse",
            "real_repo_record_count_collapse",
            "Current record count collapsed relative to baseline.",
            {
                "baseline_record_count": baseline_record_count,
                "current_record_count": current_record_count,
                "record_drop_ratio": record_drop_ratio,
            },
        ))
    if _runtime_drifted(baseline_runtime_ms, runtime_ms, runtime_drift_ratio):
        regressions.append(_regression(
            "runtime_drift",
            "real_repo_runtime_drift",
            "Current runtime drifted beyond the configured baseline ratio.",
            {
                "baseline_runtime_ms": baseline_runtime_ms,
                "current_runtime_ms": runtime_ms,
                "runtime_drift_ratio": runtime_drift_ratio,
            },
        ))
    if current_failure_kind and current_failure_kind != baseline_failure_kind:
        regressions.append(_regression(
            "failure_kind_new",
            "real_repo_failure_kind_new",
            "Current run introduced a failure kind not present in the baseline.",
            {
                "baseline_failure_kind": baseline_failure_kind,
                "current_failure_kind": current_failure_kind,
            },
        ))
    return regressions


def _decision_downgraded(baseline: str, current: str) -> bool:
    if not baseline or not current:
        return False
    return DECISION_ORDER.get(current, 0) < DECISION_ORDER.get(baseline, 0)


def _record_count_collapsed(baseline: int | None, current: int | None, ratio: float) -> bool:
    if baseline is None or current is None or baseline <= 0:
        return False
    return current < max(1, int(baseline * ratio))


def _runtime_drifted(baseline: int | None, current: int | None, ratio: float) -> bool:
    if baseline is None or current is None or baseline <= 0:
        return False
    return current > int(baseline * ratio)


def _external_hold(current_decision: str, command_exit_code: Any, timed_out: bool, failure_kind: str) -> bool:
    if current_decision in {"hold", "blocked"}:
        return True
    if command_exit_code is not None and int(command_exit_code) != 0:
        return True
    return timed_out or bool(failure_kind)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _regression(regression_class: str, code: str, message: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "regression_class": regression_class,
        "code": code,
        "readiness_effect": "hold",
        "message": message,
        "evidence": evidence,
    }
