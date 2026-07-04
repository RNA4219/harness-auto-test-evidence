"""Value measurement helpers for HATE-GAP-047."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_METRICS = {
    "review_time_saved",
    "risk_debt_burn_down",
    "release_blocker_lead_time",
    "repeat_finding_rate",
    "avoided_unsupported_claims",
}

LOWER_IS_BETTER = {"release_blocker_lead_time", "repeat_finding_rate"}


@dataclass(frozen=True)
class ValueFinding:
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


def normalize_value_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw or {})
    return {
        "aggregate_metrics": _list_of_dicts(config.get("aggregate_metrics", [])),
        "roi_inputs": dict(config.get("roi_inputs", {}) or {}),
        "counterfactual": dict(config.get("counterfactual", {}) or {}),
        "confidence": float(config.get("confidence", 0.0) or 0.0),
        "limitations": _strings(config.get("limitations", [])),
        "sample_size": int(config.get("sample_size", 0) or 0),
        "minimum_sample_size": int(config.get("minimum_sample_size", 10) or 10),
        "baseline_present": bool(config.get("baseline_present", False)),
        "individual_ranking_present": bool(config.get("individual_ranking_present", False)),
        "noisy_signal_counts_as_value": bool(config.get("noisy_signal_counts_as_value", False)),
        "safe_evidence_refs": _strings(config.get("safe_evidence_refs", [])),
        "privacy_aggregate_only": bool(config.get("privacy_aggregate_only", False)),
        "raw_user_metric_present": bool(config.get("raw_user_metric_present", False)),
    }


def value_summary(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "aggregate_metric_count": len(config["aggregate_metrics"]),
        "confidence": config["confidence"],
        "sample_size": config["sample_size"],
        "minimum_sample_size": config["minimum_sample_size"],
        "baseline_present": config["baseline_present"],
        "counterfactual_present": bool(config["counterfactual"]),
        "safe_evidence_ref_count": len(config["safe_evidence_refs"]),
        "privacy_aggregate_only": config["privacy_aggregate_only"],
    }


def value_diagnostics(config: dict[str, Any]) -> dict[str, Any]:
    observed_metrics = {str(metric.get("metric_id") or "") for metric in config["aggregate_metrics"]}
    evidence_refs = set(config["safe_evidence_refs"])
    missing_evidence_metrics = sorted(
        str(metric.get("metric_id") or "metric")
        for metric in config["aggregate_metrics"]
        if not metric.get("sourceRef") and not set(_strings(metric.get("evidence_refs", []))).intersection(evidence_refs)
    )
    missing_confidence_interval = sorted(
        str(metric.get("metric_id") or "metric")
        for metric in config["aggregate_metrics"]
        if not metric.get("confidence_interval")
    )
    wrong_direction_metrics = []
    for metric in config["aggregate_metrics"]:
        metric_id = str(metric.get("metric_id") or "")
        delta = float(metric.get("delta", 0) or 0)
        if metric_id in LOWER_IS_BETTER and delta > 0:
            wrong_direction_metrics.append(metric_id)
        if metric_id not in LOWER_IS_BETTER and delta < 0:
            wrong_direction_metrics.append(metric_id)
    causal_claim_without_counterfactual = sorted(
        str(metric.get("metric_id") or "metric")
        for metric in config["aggregate_metrics"]
        if metric.get("causal_claim") and not config["counterfactual"]
    )
    return {
        "missing_required_metrics": sorted(REQUIRED_METRICS - observed_metrics),
        "missing_evidence_metrics": missing_evidence_metrics,
        "missing_confidence_interval_metrics": missing_confidence_interval,
        "wrong_direction_metrics": sorted(set(wrong_direction_metrics)),
        "causal_claim_without_counterfactual": causal_claim_without_counterfactual,
        "sample_size_below_minimum": config["sample_size"] < config["minimum_sample_size"],
        "roi_inputs_missing_period_or_cost_basis": not bool(config["roi_inputs"].get("period") and config["roi_inputs"].get("cost_basis")),
        "counterfactual_missing_basis": bool(config["counterfactual"]) and not bool(config["counterfactual"].get("basis") and config["counterfactual"].get("sourceRef")),
        "privacy_violation": bool(config["raw_user_metric_present"] or not config["privacy_aggregate_only"]),
    }


def value_diagnostic_summary(diagnostics: dict[str, Any]) -> dict[str, Any]:
    return {
        "missing_required_metric_count": len(diagnostics["missing_required_metrics"]),
        "missing_evidence_metric_count": len(diagnostics["missing_evidence_metrics"]),
        "missing_confidence_interval_metric_count": len(diagnostics["missing_confidence_interval_metrics"]),
        "wrong_direction_metric_count": len(diagnostics["wrong_direction_metrics"]),
        "causal_claim_without_counterfactual_count": len(diagnostics["causal_claim_without_counterfactual"]),
    }


def value_findings(
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    source_ref: str,
) -> list[ValueFinding]:
    findings: list[ValueFinding] = []
    if diagnostics["missing_required_metrics"]:
        findings.append(_finding("value_measurement_required_metric_missing", f"Value report missing metrics: {', '.join(diagnostics['missing_required_metrics'])}.", source_ref))
    if not config["safe_evidence_refs"] or diagnostics["missing_evidence_metrics"]:
        findings.append(_finding("value_measurement_safe_evidence_refs_missing", "ROI must be explainable from safe evidence refs.", source_ref))
    if config["individual_ranking_present"]:
        findings.append(_finding("value_measurement_individual_leaderboard_denied", "Individual developer ranking is denied.", source_ref))
    if config["noisy_signal_counts_as_value"]:
        findings.append(_finding("value_measurement_noisy_signal_denied", "Detection volume alone must not improve value score.", source_ref))
    if not config["baseline_present"]:
        findings.append(_finding("value_measurement_missing_baseline_hold", "Missing baseline must produce hold or soft gap.", source_ref))
    if config["confidence"] < 0.5 or config["sample_size"] <= 0 or not config["limitations"]:
        findings.append(_finding("value_measurement_executive_summary_incomplete", "Executive summary requires confidence, sample size, and limitations.", source_ref))
    if diagnostics["sample_size_below_minimum"]:
        findings.append(_finding("value_measurement_sample_size_too_small", "Value measurement sample size is below configured minimum.", source_ref))
    if diagnostics["roi_inputs_missing_period_or_cost_basis"]:
        findings.append(_finding("value_measurement_roi_basis_missing", "ROI inputs require period and cost basis.", source_ref))
    if diagnostics["counterfactual_missing_basis"] or diagnostics["causal_claim_without_counterfactual"]:
        findings.append(_finding("value_measurement_counterfactual_missing", "Causal value claims require counterfactual basis and sourceRef.", source_ref))
    if diagnostics["missing_confidence_interval_metrics"]:
        findings.append(_finding("value_measurement_confidence_interval_missing", "Aggregate metrics require confidence intervals.", source_ref))
    if diagnostics["wrong_direction_metrics"]:
        findings.append(_finding("value_measurement_metric_direction_suspicious", "Metric delta direction contradicts metric semantics.", source_ref))
    if diagnostics["privacy_violation"]:
        findings.append(_finding("value_measurement_privacy_aggregation_denied", "Value measurement must be aggregate and privacy-safe.", source_ref))
    return findings


def _finding(code: str, message: str, source_ref: str) -> ValueFinding:
    return ValueFinding(code=code, severity="high", message=message, sourceRef=source_ref)


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value if str(item)] if isinstance(value, list) else []
