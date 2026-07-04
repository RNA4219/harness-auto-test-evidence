"""Recurring real-repo evaluation helpers for HATE-GAP-044."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RecurringEvalFinding:
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


def normalize_recurring_eval_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw or {})
    return {
        "repo_roster": _list_of_dicts(config.get("repo_roster", [])),
        "required_repo_classes": _strings(config.get("required_repo_classes", [])),
        "runs": _list_of_dicts(config.get("runs", [])),
        "trend_windows": _list_of_dicts(config.get("trend_windows", [])),
        "retry_isolation_rules": _list_of_dicts(config.get("retry_isolation_rules", [])),
        "timeout_budget_by_class": dict(config.get("timeout_budget_by_class", {}) or {}),
        "trend_privacy_safe": bool(config.get("trend_privacy_safe", False)),
        "regression_detected": bool(config.get("regression_detected", False)),
        "timeout_hides_missing_evidence": bool(config.get("timeout_hides_missing_evidence", False)),
        "quarantine_policy_present": bool(config.get("quarantine_policy_present", False)),
    }


def recurring_eval_summary(config: dict[str, Any]) -> dict[str, Any]:
    covered = {repo.get("class") for repo in config["repo_roster"] if repo.get("class")}
    missing = sorted(set(config["required_repo_classes"]) - covered)
    return {
        "repo_count": len(config["repo_roster"]),
        "run_count": len(config["runs"]),
        "trend_window_count": len(config["trend_windows"]),
        "retry_isolation_rule_count": len(config["retry_isolation_rules"]),
        "missing_required_repo_classes": missing,
        "trend_privacy_safe": config["trend_privacy_safe"],
        "quarantine_policy_present": config["quarantine_policy_present"],
    }


def recurring_eval_diagnostics(config: dict[str, Any]) -> dict[str, Any]:
    repo_ids = [str(repo.get("repo") or "") for repo in config["repo_roster"] if repo.get("repo")]
    missing_owner = sorted(str(repo.get("repo") or "repo") for repo in config["repo_roster"] if not repo.get("owner"))
    missing_source_ref = sorted(str(repo.get("repo") or "repo") for repo in config["repo_roster"] if not repo.get("sourceRef"))
    external_unclassified = sorted(
        str(repo.get("repo") or "repo")
        for repo in config["repo_roster"]
        if repo.get("ownership") == "external" and not repo.get("external_hold_reason")
    )
    stale_or_unhealthy = sorted(
        str(repo.get("repo") or "repo")
        for repo in config["repo_roster"]
        if repo.get("stale") or repo.get("health") in {"stale", "quarantined", "unknown"}
    )
    runs_missing_identity: list[str] = []
    runs_with_baseline_profile_mismatch: list[str] = []
    runs_with_timeout_budget_exceeded: list[str] = []
    runs_without_privacy_fingerprint: list[str] = []
    parser_gap_without_review: list[str] = []
    for run in config["runs"]:
        run_id = str(run.get("run_id") or "run")
        if not run.get("roster_hash") or not run.get("policy_hash") or not run.get("environment_fingerprint"):
            runs_missing_identity.append(run_id)
        if run.get("baseline_profile") and run.get("current_profile") and run.get("baseline_profile") != run.get("current_profile"):
            runs_with_baseline_profile_mismatch.append(run_id)
        repo_class = str(run.get("repo_class") or "")
        budget = config["timeout_budget_by_class"].get(repo_class)
        if budget is not None and int(run.get("duration_seconds", 0) or 0) > int(budget):
            runs_with_timeout_budget_exceeded.append(run_id)
        if not run.get("privacy_fingerprint"):
            runs_without_privacy_fingerprint.append(run_id)
        if run.get("parser_gap") and not run.get("manual_review_outcome"):
            parser_gap_without_review.append(run_id)
    window_ids = [str(window.get("window_id") or "") for window in config["trend_windows"] if window.get("window_id")]
    unsafe_trend_windows = sorted(
        str(window.get("window_id") or "trend-window")
        for window in config["trend_windows"]
        if not window.get("aggregate_only") or window.get("contains_raw_repo_name") or int(window.get("sample_size", 0) or 0) < 2
    )
    retry_rules_without_reason = sorted(
        str(rule.get("rule_id") or "retry-rule")
        for rule in config["retry_isolation_rules"]
        if not rule.get("failure_class") or "max_retries" not in rule or "quarantine_after" not in rule
    )
    return {
        "duplicate_repos": sorted({item for item in repo_ids if repo_ids.count(item) > 1}),
        "missing_owner_repos": missing_owner,
        "missing_source_ref_repos": missing_source_ref,
        "external_unclassified_repos": external_unclassified,
        "stale_or_unhealthy_repos": stale_or_unhealthy,
        "runs_missing_identity": sorted(runs_missing_identity),
        "runs_with_baseline_profile_mismatch": sorted(runs_with_baseline_profile_mismatch),
        "runs_with_timeout_budget_exceeded": sorted(runs_with_timeout_budget_exceeded),
        "runs_without_privacy_fingerprint": sorted(runs_without_privacy_fingerprint),
        "parser_gap_without_review_runs": sorted(parser_gap_without_review),
        "duplicate_trend_windows": sorted({item for item in window_ids if window_ids.count(item) > 1}),
        "unsafe_trend_windows": unsafe_trend_windows,
        "retry_rules_without_isolation": retry_rules_without_reason,
    }


def recurring_eval_diagnostic_summary(diagnostics: dict[str, Any]) -> dict[str, Any]:
    return {
        "duplicate_repo_count": len(diagnostics["duplicate_repos"]),
        "missing_owner_repo_count": len(diagnostics["missing_owner_repos"]),
        "external_unclassified_repo_count": len(diagnostics["external_unclassified_repos"]),
        "stale_or_unhealthy_repo_count": len(diagnostics["stale_or_unhealthy_repos"]),
        "run_identity_gap_count": len(diagnostics["runs_missing_identity"]),
        "profile_mismatch_run_count": len(diagnostics["runs_with_baseline_profile_mismatch"]),
        "timeout_budget_exceeded_run_count": len(diagnostics["runs_with_timeout_budget_exceeded"]),
        "unsafe_trend_window_count": len(diagnostics["unsafe_trend_windows"]),
        "retry_isolation_gap_count": len(diagnostics["retry_rules_without_isolation"]),
    }


def recurring_eval_findings(
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    source_ref: str,
) -> list[RecurringEvalFinding]:
    findings: list[RecurringEvalFinding] = []
    missing = recurring_eval_summary(config)["missing_required_repo_classes"]
    if missing:
        findings.append(_finding("recurring_eval_repo_class_missing", f"Evaluation roster missing repo classes: {', '.join(missing)}.", source_ref))
    for run in config["runs"]:
        if not run.get("baseline_ref") or not run.get("current_result_ref"):
            findings.append(_finding("recurring_eval_baseline_or_current_missing", "Evaluation run requires baseline and current result refs.", source_ref))
        if run.get("parser_gap") and not run.get("manual_review_outcome"):
            findings.append(_finding("recurring_eval_parser_gap_without_review", "Parser gap requires manual review outcome.", source_ref))
    if not config["timeout_budget_by_class"]:
        findings.append(_finding("recurring_eval_timeout_budget_missing", "Timeout and resource budgets must be per repo class.", source_ref))
    if config["regression_detected"]:
        findings.append(_finding("recurring_eval_regression_detected", "Recurring real repo evaluation detected regression.", source_ref))
    if config["timeout_hides_missing_evidence"]:
        findings.append(_finding("recurring_eval_timeout_hidden_evidence_denied", "Timeout must not hide missing evidence.", source_ref))
    if not config["trend_privacy_safe"]:
        findings.append(_finding("recurring_eval_trend_privacy_unsafe", "Trend reporting must be aggregate and privacy-safe.", source_ref))
    if not config["quarantine_policy_present"]:
        findings.append(_finding("recurring_eval_quarantine_policy_missing", "Recurring eval requires stale/external/quarantine policy.", source_ref))
    if diagnostics["duplicate_repos"]:
        findings.append(_finding("recurring_eval_duplicate_repo", "Recurring eval roster contains duplicate repo ids.", source_ref))
    if diagnostics["missing_owner_repos"] or diagnostics["missing_source_ref_repos"]:
        findings.append(_finding("recurring_eval_roster_metadata_incomplete", "Recurring eval roster requires owner and sourceRef.", source_ref))
    if diagnostics["external_unclassified_repos"]:
        findings.append(_finding("recurring_eval_external_boundary_unclassified", "External repos require explicit external hold reason.", source_ref))
    if diagnostics["stale_or_unhealthy_repos"]:
        findings.append(_finding("recurring_eval_stale_repo_quarantined", "Stale or unhealthy repos must be quarantined or excluded.", source_ref))
    if diagnostics["runs_missing_identity"]:
        findings.append(_finding("recurring_eval_run_identity_missing", "Recurring eval runs require roster_hash, policy_hash, and environment_fingerprint.", source_ref))
    if diagnostics["runs_with_baseline_profile_mismatch"]:
        findings.append(_finding("recurring_eval_baseline_profile_mismatch", "Baseline/current profile mismatch cannot be compared silently.", source_ref))
    if diagnostics["runs_with_timeout_budget_exceeded"]:
        findings.append(_finding("recurring_eval_timeout_budget_exceeded", "Run duration exceeded class timeout budget.", source_ref))
    if diagnostics["runs_without_privacy_fingerprint"]:
        findings.append(_finding("recurring_eval_privacy_fingerprint_missing", "Run trend data requires privacy-safe fingerprint.", source_ref))
    if diagnostics["unsafe_trend_windows"]:
        findings.append(_finding("recurring_eval_trend_window_unsafe", "Trend windows must be aggregate, non-identifying, and sufficiently sampled.", source_ref))
    if diagnostics["retry_rules_without_isolation"]:
        findings.append(_finding("recurring_eval_retry_isolation_missing", "Retry rules require failure class, max retries, and quarantine threshold.", source_ref))
    return findings


def _finding(code: str, message: str, source_ref: str) -> RecurringEvalFinding:
    return RecurringEvalFinding(code=code, severity="high", message=message, sourceRef=source_ref)


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value if str(item)] if isinstance(value, list) else []
