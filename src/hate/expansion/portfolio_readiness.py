"""Third-wave portfolio readiness evaluations for HATE-GAP-041..048."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class PortfolioFinding:
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


Rule = Callable[[dict[str, Any], str], list[PortfolioFinding]]


def evaluate_rollout_adoption_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_fixture(payload, build_rollout_adoption_report, "rollout-adoption-fixture")


def evaluate_provider_integration_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_fixture(payload, build_provider_integration_report, "provider-integration-fixture")


def evaluate_runner_dialect_coverage_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_fixture(payload, build_runner_dialect_coverage_report, "runner-dialect-coverage-fixture")


def evaluate_recurring_real_repo_eval_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_fixture(payload, build_recurring_real_repo_eval_report, "recurring-real-repo-eval-fixture")


def evaluate_governance_review_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_fixture(payload, build_governance_review_report, "governance-review-fixture")


def evaluate_security_procurement_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_fixture(payload, build_security_procurement_report, "security-procurement-fixture")


def evaluate_value_measurement_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_fixture(payload, build_value_measurement_report, "value-measurement-fixture")


def evaluate_developer_experience_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_fixture(payload, build_developer_experience_report, "developer-experience-fixture")


def build_rollout_adoption_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "rollout-adoption-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    config = _normalize_rollout_config(input_data.get("rollout_config", input_data))
    return _build_report(
        record_type="rollout-adoption-report",
        report_id=report_id,
        config_key="rollout_config",
        config=config,
        source_refs=source_refs or input_data.get("sourceRefs") or ["rollout-adoption"],
        summary=_rollout_summary(config),
        findings=_rollout_findings(config, _first_source(source_refs, input_data, "rollout-adoption")),
    )


def build_provider_integration_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "provider-integration-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    config = _normalize_provider_config(input_data.get("provider_config", input_data))
    return _build_report(
        record_type="provider-integration-report",
        report_id=report_id,
        config_key="provider_config",
        config=config,
        source_refs=source_refs or input_data.get("sourceRefs") or ["provider-integration"],
        summary=_provider_summary(config),
        findings=_provider_findings(config, _first_source(source_refs, input_data, "provider-integration")),
    )


def build_runner_dialect_coverage_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "runner-dialect-coverage-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    config = _normalize_runner_config(input_data.get("runner_config", input_data))
    return _build_report(
        record_type="runner-dialect-coverage-report",
        report_id=report_id,
        config_key="runner_config",
        config=config,
        source_refs=source_refs or input_data.get("sourceRefs") or ["runner-dialect-coverage"],
        summary=_runner_summary(config),
        findings=_runner_findings(config, _first_source(source_refs, input_data, "runner-dialect-coverage")),
    )


def build_recurring_real_repo_eval_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "recurring-real-repo-eval-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    config = _normalize_recurring_eval_config(input_data.get("evaluation_config", input_data))
    return _build_report(
        record_type="recurring-real-repo-eval-report",
        report_id=report_id,
        config_key="evaluation_config",
        config=config,
        source_refs=source_refs or input_data.get("sourceRefs") or ["recurring-real-repo-eval"],
        summary=_recurring_eval_summary(config),
        findings=_recurring_eval_findings(config, _first_source(source_refs, input_data, "recurring-real-repo-eval")),
    )


def build_governance_review_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "governance-review-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    config = _normalize_governance_config(input_data.get("governance_config", input_data))
    return _build_report(
        record_type="governance-review-report",
        report_id=report_id,
        config_key="governance_config",
        config=config,
        source_refs=source_refs or input_data.get("sourceRefs") or ["governance-review"],
        summary=_governance_summary(config),
        findings=_governance_findings(config, _first_source(source_refs, input_data, "governance-review")),
    )


def build_security_procurement_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "security-procurement-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    config = _normalize_procurement_config(input_data.get("procurement_config", input_data))
    return _build_report(
        record_type="security-procurement-report",
        report_id=report_id,
        config_key="procurement_config",
        config=config,
        source_refs=source_refs or input_data.get("sourceRefs") or ["security-procurement"],
        summary=_procurement_summary(config),
        findings=_procurement_findings(config, _first_source(source_refs, input_data, "security-procurement")),
    )


def build_value_measurement_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "value-measurement-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    config = _normalize_value_config(input_data.get("value_config", input_data))
    return _build_report(
        record_type="value-measurement-report",
        report_id=report_id,
        config_key="value_config",
        config=config,
        source_refs=source_refs or input_data.get("sourceRefs") or ["value-measurement"],
        summary=_value_summary(config),
        findings=_value_findings(config, _first_source(source_refs, input_data, "value-measurement")),
    )


def build_developer_experience_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "developer-experience-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    config = _normalize_dx_config(input_data.get("dx_config", input_data))
    return _build_report(
        record_type="developer-experience-report",
        report_id=report_id,
        config_key="dx_config",
        config=config,
        source_refs=source_refs or input_data.get("sourceRefs") or ["developer-experience"],
        summary=_dx_summary(config),
        findings=_dx_findings(config, _first_source(source_refs, input_data, "developer-experience")),
    )


def _evaluate_fixture(payload: dict[str, Any], builder: Callable[..., dict[str, Any]], fallback_id: str) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = builder(
        input_data,
        report_id=str(payload.get("fixture_id") or fallback_id),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def _build_report(
    *,
    record_type: str,
    report_id: str,
    config_key: str,
    config: dict[str, Any],
    source_refs: list[str],
    summary: dict[str, Any],
    findings: list[PortfolioFinding],
) -> dict[str, Any]:
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": record_type,
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        config_key: config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {**summary, "finding_count": len(findings)},
        "sourceRefs": sorted({str(ref) for ref in source_refs}),
    }


def _first_source(source_refs: list[str] | None, input_data: dict[str, Any], fallback: str) -> str:
    refs = source_refs or input_data.get("sourceRefs") or [fallback]
    return str(refs[0]) if refs else fallback


def _finding(code: str, message: str, source_ref: str, severity: str = "high") -> PortfolioFinding:
    return PortfolioFinding(code=code, severity=severity, message=message, sourceRef=source_ref)


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value if str(item)] if isinstance(value, list) else []


def _normalize_rollout_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw or {})
    return {
        "waves": _list_of_dicts(config.get("waves", [])),
        "repo_statuses": _list_of_dicts(config.get("repo_statuses", [])),
        "exceptions": _list_of_dicts(config.get("exceptions", [])),
        "portfolio_metrics_safe": bool(config.get("portfolio_metrics_safe", False)),
        "rollback_plan_present": bool(config.get("rollback_plan_present", False)),
        "illegal_status_transition_detected": bool(config.get("illegal_status_transition_detected", False)),
    }


def _rollout_summary(config: dict[str, Any]) -> dict[str, Any]:
    expired = [item for item in config["exceptions"] if item.get("expired")]
    return {
        "wave_count": len(config["waves"]),
        "repo_status_count": len(config["repo_statuses"]),
        "exception_count": len(config["exceptions"]),
        "expired_exception_count": len(expired),
        "portfolio_metrics_safe": config["portfolio_metrics_safe"],
        "rollback_plan_present": config["rollback_plan_present"],
    }


def _rollout_findings(config: dict[str, Any], source_ref: str) -> list[PortfolioFinding]:
    findings: list[PortfolioFinding] = []
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
    if config["illegal_status_transition_detected"]:
        findings.append(_finding("rollout_adoption_illegal_status_transition", "Illegal repo onboarding status transition detected.", source_ref))
    if not config["portfolio_metrics_safe"]:
        findings.append(_finding("rollout_adoption_portfolio_metrics_unsafe", "Portfolio adoption metrics must avoid raw code and test names.", source_ref))
    if not config["rollback_plan_present"]:
        findings.append(_finding("rollout_adoption_rollback_plan_missing", "Rollout requires rollback evidence.", source_ref))
    return findings


def _normalize_provider_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw or {})
    return {
        "providers": _list_of_dicts(config.get("providers", [])),
        "required_providers": _strings(config.get("required_providers", [])),
        "minimum_permissions_declared": bool(config.get("minimum_permissions_declared", False)),
        "ambiguous_identity_detected": bool(config.get("ambiguous_identity_detected", False)),
        "overbroad_permission_detected": bool(config.get("overbroad_permission_detected", False)),
    }


def _provider_summary(config: dict[str, Any]) -> dict[str, Any]:
    covered = {provider.get("provider") for provider in config["providers"] if provider.get("support_state") in {"supported", "partial"}}
    missing = sorted(set(config["required_providers"]) - covered)
    return {
        "provider_count": len(config["providers"]),
        "required_provider_count": len(config["required_providers"]),
        "missing_required_providers": missing,
        "minimum_permissions_declared": config["minimum_permissions_declared"],
    }


def _provider_findings(config: dict[str, Any], source_ref: str) -> list[PortfolioFinding]:
    findings: list[PortfolioFinding] = []
    missing = _provider_summary(config)["missing_required_providers"]
    if missing:
        findings.append(_finding("provider_integration_required_provider_missing", f"Provider matrix missing: {', '.join(missing)}.", source_ref))
    for provider in config["providers"]:
        missing_fields = [
            key
            for key in ("commit_identity", "review_identity", "run_attempt", "artifact_lifetime", "annotation_target", "rerun_semantics")
            if not provider.get(key)
        ]
        if missing_fields:
            findings.append(_finding("provider_integration_identity_semantics_incomplete", f"{provider.get('provider', 'provider')} missing: {', '.join(missing_fields)}.", source_ref))
    if not config["minimum_permissions_declared"]:
        findings.append(_finding("provider_integration_minimum_permissions_missing", "Provider integrations must declare minimum permissions.", source_ref))
    if config["ambiguous_identity_detected"]:
        findings.append(_finding("provider_integration_ambiguous_identity_hard_dq", "Ambiguous provider identity must not become silent advisory output.", source_ref))
    if config["overbroad_permission_detected"]:
        findings.append(_finding("provider_integration_overbroad_permission_denied", "Broad or admin provider permission is denied.", source_ref))
    return findings


def _normalize_runner_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw or {})
    return {
        "runner_families": _list_of_dicts(config.get("runner_families", [])),
        "dialects": _list_of_dicts(config.get("dialects", [])),
        "required_families": _strings(config.get("required_families", [])),
        "unsupported_capability_gap_detected": bool(config.get("unsupported_capability_gap_detected", False)),
        "claim_without_conformance_detected": bool(config.get("claim_without_conformance_detected", False)),
    }


def _runner_summary(config: dict[str, Any]) -> dict[str, Any]:
    covered = {family.get("family") for family in config["runner_families"] if family.get("support_state") in {"supported", "partial"}}
    missing = sorted(set(config["required_families"]) - covered)
    return {
        "runner_family_count": len(config["runner_families"]),
        "dialect_count": len(config["dialects"]),
        "missing_required_families": missing,
    }


def _runner_findings(config: dict[str, Any], source_ref: str) -> list[PortfolioFinding]:
    findings: list[PortfolioFinding] = []
    missing = _runner_summary(config)["missing_required_families"]
    if missing:
        findings.append(_finding("runner_dialect_required_family_missing", f"Runner family coverage missing: {', '.join(missing)}.", source_ref))
    for dialect in config["dialects"]:
        if not dialect.get("conformance_fixture_ref"):
            findings.append(_finding("runner_dialect_conformance_fixture_missing", f"{dialect.get('dialect', 'dialect')} missing conformance fixture.", source_ref))
    if config["unsupported_capability_gap_detected"]:
        findings.append(_finding("runner_dialect_unsupported_capability_gap", "Unsupported runner output must emit a capability gap.", source_ref))
    if config["claim_without_conformance_detected"]:
        findings.append(_finding("runner_dialect_claim_without_conformance", "Runner support claim without conformance fixture blocks product-ready.", source_ref))
    return findings


def _normalize_recurring_eval_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw or {})
    return {
        "repo_roster": _list_of_dicts(config.get("repo_roster", [])),
        "required_repo_classes": _strings(config.get("required_repo_classes", [])),
        "runs": _list_of_dicts(config.get("runs", [])),
        "timeout_budget_by_class": dict(config.get("timeout_budget_by_class", {}) or {}),
        "trend_privacy_safe": bool(config.get("trend_privacy_safe", False)),
        "regression_detected": bool(config.get("regression_detected", False)),
        "timeout_hides_missing_evidence": bool(config.get("timeout_hides_missing_evidence", False)),
    }


def _recurring_eval_summary(config: dict[str, Any]) -> dict[str, Any]:
    covered = {repo.get("class") for repo in config["repo_roster"] if repo.get("class")}
    missing = sorted(set(config["required_repo_classes"]) - covered)
    return {
        "repo_count": len(config["repo_roster"]),
        "run_count": len(config["runs"]),
        "missing_required_repo_classes": missing,
        "trend_privacy_safe": config["trend_privacy_safe"],
    }


def _recurring_eval_findings(config: dict[str, Any], source_ref: str) -> list[PortfolioFinding]:
    findings: list[PortfolioFinding] = []
    missing = _recurring_eval_summary(config)["missing_required_repo_classes"]
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
    return findings


def _normalize_governance_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw or {})
    return {
        "policy_templates": _list_of_dicts(config.get("policy_templates", [])),
        "exception_requests": _list_of_dicts(config.get("exception_requests", [])),
        "review_packet": dict(config.get("review_packet", {}) or {}),
        "self_approval_detected": bool(config.get("self_approval_detected", False)),
    }


def _governance_summary(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy_template_count": len(config["policy_templates"]),
        "exception_request_count": len(config["exception_requests"]),
        "expired_exception_count": int(config["review_packet"].get("expired_exception_count", 0) or 0),
        "unresolved_high_risk_debt_count": int(config["review_packet"].get("unresolved_high_risk_debt_count", 0) or 0),
    }


def _governance_findings(config: dict[str, Any], source_ref: str) -> list[PortfolioFinding]:
    findings: list[PortfolioFinding] = []
    for template in config["policy_templates"]:
        missing = [key for key in ("author", "approver", "effective_date", "review_cadence", "rollback_owner") if not template.get(key)]
        if missing:
            findings.append(_finding("governance_policy_template_incomplete", f"Policy template missing: {', '.join(missing)}.", source_ref))
    for request in config["exception_requests"]:
        missing = [key for key in ("owner", "expiry", "rationale", "affected_risks", "compensating_evidence", "reviewer_decision") if not request.get(key)]
        if missing:
            findings.append(_finding("governance_exception_request_incomplete", f"Exception request missing: {', '.join(missing)}.", source_ref))
    summary = _governance_summary(config)
    if summary["expired_exception_count"] or summary["unresolved_high_risk_debt_count"]:
        findings.append(_finding("governance_review_packet_blockers_present", "Governance packet contains expired exceptions or unresolved high-risk debt.", source_ref))
    if config["self_approval_detected"]:
        findings.append(_finding("governance_self_approval_denied", "Self-approval or service-account exception approval is denied.", source_ref))
    return findings


def _normalize_procurement_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw or {})
    return {
        "security_review_packet": dict(config.get("security_review_packet", {}) or {}),
        "control_claims": _list_of_dicts(config.get("control_claims", [])),
        "vulnerability_slas": _list_of_dicts(config.get("vulnerability_slas", [])),
        "procurement_export_safe": bool(config.get("procurement_export_safe", False)),
        "raw_artifact_in_export": bool(config.get("raw_artifact_in_export", False)),
    }


def _procurement_summary(config: dict[str, Any]) -> dict[str, Any]:
    unsupported = [claim for claim in config["control_claims"] if claim.get("claim_class") == "unsupported"]
    overdue = [sla for sla in config["vulnerability_slas"] if sla.get("overdue")]
    return {
        "control_claim_count": len(config["control_claims"]),
        "unsupported_claim_count": len(unsupported),
        "overdue_vulnerability_sla_count": len(overdue),
        "procurement_export_safe": config["procurement_export_safe"],
    }


def _procurement_findings(config: dict[str, Any], source_ref: str) -> list[PortfolioFinding]:
    findings: list[PortfolioFinding] = []
    packet = config["security_review_packet"]
    missing_packet = [key for key in ("architecture", "data_flow", "data_classes", "subprocessors", "encryption", "secrets_handling", "retention_summary") if not packet.get(key)]
    if missing_packet:
        findings.append(_finding("security_procurement_packet_incomplete", f"Security review packet missing: {', '.join(missing_packet)}.", source_ref))
    for claim in config["control_claims"]:
        if claim.get("claim_class") == "unsupported":
            findings.append(_finding("security_procurement_unsupported_certification_claim", "Unsupported certification or control claim blocks product-ready.", source_ref))
    for sla in config["vulnerability_slas"]:
        if sla.get("severity") == "critical" and sla.get("overdue"):
            findings.append(_finding("security_procurement_overdue_critical_vulnerability", "Overdue critical vulnerability response blocks release pack.", source_ref))
    if not config["procurement_export_safe"] or config["raw_artifact_in_export"]:
        findings.append(_finding("security_procurement_raw_artifact_export_denied", "Procurement export must contain only safe summaries and approved evidence refs.", source_ref))
    return findings


def _normalize_value_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw or {})
    return {
        "aggregate_metrics": _list_of_dicts(config.get("aggregate_metrics", [])),
        "roi_inputs": dict(config.get("roi_inputs", {}) or {}),
        "confidence": float(config.get("confidence", 0.0) or 0.0),
        "limitations": _strings(config.get("limitations", [])),
        "sample_size": int(config.get("sample_size", 0) or 0),
        "baseline_present": bool(config.get("baseline_present", False)),
        "individual_ranking_present": bool(config.get("individual_ranking_present", False)),
        "noisy_signal_counts_as_value": bool(config.get("noisy_signal_counts_as_value", False)),
        "safe_evidence_refs": _strings(config.get("safe_evidence_refs", [])),
    }


def _value_summary(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "aggregate_metric_count": len(config["aggregate_metrics"]),
        "confidence": config["confidence"],
        "sample_size": config["sample_size"],
        "baseline_present": config["baseline_present"],
        "safe_evidence_ref_count": len(config["safe_evidence_refs"]),
    }


def _value_findings(config: dict[str, Any], source_ref: str) -> list[PortfolioFinding]:
    findings: list[PortfolioFinding] = []
    required_metrics = {"review_time_saved", "risk_debt_burn_down", "release_blocker_lead_time", "repeat_finding_rate", "avoided_unsupported_claims"}
    observed_metrics = {metric.get("metric_id") for metric in config["aggregate_metrics"]}
    missing = sorted(required_metrics - observed_metrics)
    if missing:
        findings.append(_finding("value_measurement_required_metric_missing", f"Value report missing metrics: {', '.join(missing)}.", source_ref))
    if not config["safe_evidence_refs"]:
        findings.append(_finding("value_measurement_safe_evidence_refs_missing", "ROI must be explainable from safe evidence refs.", source_ref))
    if config["individual_ranking_present"]:
        findings.append(_finding("value_measurement_individual_leaderboard_denied", "Individual developer ranking is denied.", source_ref))
    if config["noisy_signal_counts_as_value"]:
        findings.append(_finding("value_measurement_noisy_signal_denied", "Detection volume alone must not improve value score.", source_ref))
    if not config["baseline_present"]:
        findings.append(_finding("value_measurement_missing_baseline_hold", "Missing baseline must produce hold or soft gap.", source_ref))
    if config["confidence"] < 0.5 or config["sample_size"] <= 0 or not config["limitations"]:
        findings.append(_finding("value_measurement_executive_summary_incomplete", "Executive summary requires confidence, sample size, and limitations.", source_ref))
    return findings


def _normalize_dx_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw or {})
    return {
        "feedback_groups": _list_of_dicts(config.get("feedback_groups", [])),
        "local_explain_available": bool(config.get("local_explain_available", False)),
        "local_replay_available": bool(config.get("local_replay_available", False)),
        "suppression_controls": dict(config.get("suppression_controls", {}) or {}),
        "recommendation_quality_score": float(config.get("recommendation_quality_score", 0.0) or 0.0),
        "latency_ms": int(config.get("latency_ms", 0) or 0),
        "raw_secret_present": bool(config.get("raw_secret_present", False)),
        "broad_suppression_detected": bool(config.get("broad_suppression_detected", False)),
        "stable_deep_links": bool(config.get("stable_deep_links", False)),
    }


def _dx_summary(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "feedback_group_count": len(config["feedback_groups"]),
        "local_explain_available": config["local_explain_available"],
        "local_replay_available": config["local_replay_available"],
        "recommendation_quality_score": config["recommendation_quality_score"],
        "latency_ms": config["latency_ms"],
    }


def _dx_findings(config: dict[str, Any], source_ref: str) -> list[PortfolioFinding]:
    findings: list[PortfolioFinding] = []
    for group in config["feedback_groups"]:
        missing = [key for key in ("fix_action", "risk_impact", "owner", "blocking_status", "deep_link") if not group.get(key)]
        if missing:
            findings.append(_finding("developer_experience_feedback_group_incomplete", f"PR/MR feedback group missing: {', '.join(missing)}.", source_ref))
    if not config["feedback_groups"]:
        findings.append(_finding("developer_experience_feedback_group_missing", "PR/MR feedback must group findings by fix action and risk.", source_ref))
    if not config["stable_deep_links"]:
        findings.append(_finding("developer_experience_deep_links_unstable", "Developer feedback requires stable deep links.", source_ref))
    if not config["local_explain_available"] or not config["local_replay_available"]:
        findings.append(_finding("developer_experience_local_loop_missing", "Local explain and replay must be available.", source_ref))
    if not config["suppression_controls"].get("owner") or not config["suppression_controls"].get("expiry_required"):
        findings.append(_finding("developer_experience_suppression_controls_incomplete", "Suppressions require owner and expiry.", source_ref))
    if config["broad_suppression_detected"]:
        findings.append(_finding("developer_experience_broad_suppression_denied", "Broad suppression is denied.", source_ref))
    if config["recommendation_quality_score"] < 0.7:
        findings.append(_finding("developer_experience_recommendation_quality_low", "Recommendation quality score is below release threshold.", source_ref))
    if config["latency_ms"] > 5000:
        findings.append(_finding("developer_experience_latency_budget_exceeded", "Developer feedback latency budget exceeded.", source_ref))
    if config["raw_secret_present"]:
        findings.append(_finding("developer_experience_raw_secret_denied", "Developer feedback must not expose raw secrets.", source_ref))
    return findings
