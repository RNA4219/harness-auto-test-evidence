"""Rollout adoption helpers for HATE-GAP-041."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ALLOWED_STATUS_TRANSITIONS = {
    "planned": {"bootstrapping", "deferred"},
    "bootstrapping": {"active", "held", "deferred"},
    "active": {"expanding", "held", "retired"},
    "expanding": {"active", "held", "retired"},
    "held": {"bootstrapping", "active", "retired"},
    "deferred": {"planned", "bootstrapping"},
    "retired": set(),
}


@dataclass(frozen=True)
class RolloutFinding:
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


def normalize_rollout_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw or {})
    return {
        "waves": _list_of_dicts(config.get("waves", [])),
        "repo_statuses": _list_of_dicts(config.get("repo_statuses", [])),
        "exceptions": _list_of_dicts(config.get("exceptions", [])),
        "portfolio_metrics": _list_of_dicts(config.get("portfolio_metrics", [])),
        "rollback_plan": dict(config.get("rollback_plan", {}) or {}),
        "portfolio_metrics_safe": bool(config.get("portfolio_metrics_safe", False)),
        "rollback_plan_present": bool(config.get("rollback_plan_present", False)),
        "illegal_status_transition_detected": bool(config.get("illegal_status_transition_detected", False)),
    }


def rollout_summary(config: dict[str, Any]) -> dict[str, Any]:
    expired = [item for item in config["exceptions"] if item.get("expired")]
    return {
        "wave_count": len(config["waves"]),
        "repo_status_count": len(config["repo_statuses"]),
        "exception_count": len(config["exceptions"]),
        "expired_exception_count": len(expired),
        "portfolio_metric_count": len(config["portfolio_metrics"]),
        "portfolio_metrics_safe": config["portfolio_metrics_safe"],
        "rollback_plan_present": config["rollback_plan_present"],
    }


def rollout_diagnostics(config: dict[str, Any]) -> dict[str, Any]:
    wave_ids = [str(wave.get("wave_id") or "") for wave in config["waves"] if wave.get("wave_id")]
    repo_ids = [str(repo.get("repo") or "") for repo in config["repo_statuses"] if repo.get("repo")]
    waves_missing_source_ref = sorted(
        str(wave.get("wave_id") or "wave")
        for wave in config["waves"]
        if not wave.get("sourceRef") or not wave.get("entry_criteria_ref") or not wave.get("exit_criteria_ref")
    )
    waves_without_order = sorted(
        str(wave.get("wave_id") or "wave")
        for wave in config["waves"]
        if "order" not in wave
    )
    invalid_transitions = []
    adoption_gap_repos = []
    missing_repo_metadata = []
    for repo in config["repo_statuses"]:
        repo_id = str(repo.get("repo") or "repo")
        previous = str(repo.get("previous_status") or "")
        status = str(repo.get("status") or "")
        if previous and status and status not in ALLOWED_STATUS_TRANSITIONS.get(previous, set()):
            invalid_transitions.append(repo_id)
        if repo.get("adoption_gap"):
            adoption_gap_repos.append(repo_id)
        if not repo.get("owner") or not repo.get("wave_id") or not repo.get("sourceRef"):
            missing_repo_metadata.append(repo_id)
    exceptions_missing_expiry_or_review = sorted(
        str(exception.get("exception_id") or "exception")
        for exception in config["exceptions"]
        if not exception.get("owner") or not exception.get("scope") or not exception.get("expiry") or not exception.get("sourceRef") or not exception.get("reviewer")
    )
    broad_exceptions = sorted(
        str(exception.get("exception_id") or "exception")
        for exception in config["exceptions"]
        if exception.get("scope") in {"global", "all", "*"}
    )
    unsafe_metrics = sorted(
        str(metric.get("metric_id") or "metric")
        for metric in config["portfolio_metrics"]
        if not metric.get("aggregate_only") or metric.get("contains_raw_repo_name") or metric.get("contains_test_name")
    )
    rollback = config["rollback_plan"]
    rollback_incomplete = not bool(
        rollback.get("owner")
        and rollback.get("tested_at")
        and rollback.get("drill_ref")
        and rollback.get("sourceRef")
    )
    return {
        "duplicate_waves": sorted({item for item in wave_ids if wave_ids.count(item) > 1}),
        "duplicate_repos": sorted({item for item in repo_ids if repo_ids.count(item) > 1}),
        "waves_missing_source_ref": waves_missing_source_ref,
        "waves_without_order": waves_without_order,
        "invalid_status_transition_repos": sorted(invalid_transitions),
        "adoption_gap_repos": sorted(adoption_gap_repos),
        "missing_repo_metadata": sorted(missing_repo_metadata),
        "exceptions_missing_expiry_or_review": exceptions_missing_expiry_or_review,
        "broad_exceptions": broad_exceptions,
        "unsafe_portfolio_metrics": unsafe_metrics,
        "rollback_plan_incomplete": rollback_incomplete,
    }


def rollout_diagnostic_summary(diagnostics: dict[str, Any]) -> dict[str, Any]:
    return {
        "duplicate_wave_count": len(diagnostics["duplicate_waves"]),
        "duplicate_repo_count": len(diagnostics["duplicate_repos"]),
        "wave_source_ref_gap_count": len(diagnostics["waves_missing_source_ref"]),
        "invalid_status_transition_count": len(diagnostics["invalid_status_transition_repos"]),
        "adoption_gap_count": len(diagnostics["adoption_gap_repos"]),
        "exception_review_gap_count": len(diagnostics["exceptions_missing_expiry_or_review"]),
        "unsafe_portfolio_metric_count": len(diagnostics["unsafe_portfolio_metrics"]),
    }


def rollout_findings(
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    source_ref: str,
) -> list[RolloutFinding]:
    findings: list[RolloutFinding] = []
    if not config["waves"]:
        findings.append(_finding("rollout_adoption_wave_missing", "Rollout requires at least one staged wave.", source_ref))
    for wave in config["waves"]:
        missing = [key for key in ("owner", "policy_template", "entry_criteria", "exit_criteria") if not wave.get(key)]
        if missing:
            findings.append(_finding("rollout_adoption_wave_incomplete", f"Rollout wave missing fields: {', '.join(missing)}.", source_ref))
    for exception in config["exceptions"]:
        if exception.get("expired"):
            findings.append(_finding("rollout_adoption_expired_exception_blocks", "Expired rollout exception blocks product readiness.", source_ref))
        if not exception.get("owner") or not exception.get("scope"):
            findings.append(_finding("rollout_adoption_exception_missing_owner_scope", "Rollout exception requires owner and scope.", source_ref))
    if config["illegal_status_transition_detected"] or diagnostics["invalid_status_transition_repos"]:
        findings.append(_finding("rollout_adoption_illegal_status_transition", "Illegal repo onboarding status transition detected.", source_ref))
    if not config["portfolio_metrics_safe"] or diagnostics["unsafe_portfolio_metrics"]:
        findings.append(_finding("rollout_adoption_portfolio_metrics_unsafe", "Portfolio adoption metrics must avoid raw code and test names.", source_ref))
    if not config["rollback_plan_present"] or diagnostics["rollback_plan_incomplete"]:
        findings.append(_finding("rollout_adoption_rollback_plan_missing", "Rollout requires rollback evidence.", source_ref))
    if diagnostics["duplicate_waves"] or diagnostics["duplicate_repos"]:
        findings.append(_finding("rollout_adoption_duplicate_record", "Rollout waves and repo statuses require stable unique ids.", source_ref))
    if diagnostics["waves_missing_source_ref"] or diagnostics["waves_without_order"]:
        findings.append(_finding("rollout_adoption_wave_traceability_missing", "Rollout waves require sourceRef, criteria refs, and order.", source_ref))
    if diagnostics["missing_repo_metadata"]:
        findings.append(_finding("rollout_adoption_repo_metadata_missing", "Repo status records require owner, wave_id, and sourceRef.", source_ref))
    if diagnostics["adoption_gap_repos"]:
        findings.append(_finding("rollout_adoption_gap_unresolved", "Unresolved adoption gaps block rollout readiness.", source_ref))
    if diagnostics["exceptions_missing_expiry_or_review"]:
        findings.append(_finding("rollout_adoption_exception_review_incomplete", "Rollout exceptions require expiry, reviewer, and sourceRef.", source_ref))
    if diagnostics["broad_exceptions"]:
        findings.append(_finding("rollout_adoption_broad_exception_denied", "Global rollout exception is denied.", source_ref))
    return findings


def _finding(code: str, message: str, source_ref: str) -> RolloutFinding:
    return RolloutFinding(code=code, severity="high", message=message, sourceRef=source_ref)


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []
