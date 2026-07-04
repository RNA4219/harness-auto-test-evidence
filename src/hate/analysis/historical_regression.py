"""Historical regression analysis for HATE-GAP-057."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HistoricalRegressionFinding:
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


def evaluate_historical_regression_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_historical_regression_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "historical-regression-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_historical_regression_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "historical-regression-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["historical-regression"])
    regression_config = _normalize_regression_config(input_data.get("regression_config", input_data))
    baseline_window_days = _calculate_window_days(regression_config["baseline_window"])
    diagnostics = _derive_diagnostics(regression_config, baseline_window_days)
    findings = _findings_for(regression_config, diagnostics, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "historical-regression-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "regression_config": regression_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "trend_metric_count": len(regression_config["trend_metrics"]),
            "recurrence_count": len(regression_config["recurrences"]),
            "time_series_count": len(regression_config["time_series"]),
            "baseline_window_days": baseline_window_days,
            "derived_recurrence_count": len(diagnostics["derived_recurrences"]),
            "regressing_metric_count": len(diagnostics["regressing_metric_ids"]),
            "invalid_window": diagnostics["invalid_window"],
            "stale_window": diagnostics["stale_window"],
            "confidence": regression_config["confidence"],
            "finding_count": len(findings),
        },
        "baseline_window": regression_config["baseline_window"],
        "trend_metrics": regression_config["trend_metrics"],
        "recurrences": regression_config["recurrences"],
        "time_series": regression_config["time_series"],
        "historical_regression_diagnostics": diagnostics,
        "analysis_scope": regression_config["analysis_scope"],
        "input_refs": regression_config["input_refs"],
        "confidence": regression_config["confidence"],
        "limits": regression_config["limits"],
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_regression_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    baseline_window = _normalize_baseline_window(config.get("baseline_window", {}))
    trend_metrics = [
        _normalize_trend_metric(m)
        for m in config.get("trend_metrics", [])
        if isinstance(m, dict)
    ]
    recurrences = [
        _normalize_recurrence(r)
        for r in config.get("recurrences", [])
        if isinstance(r, dict)
    ]
    time_series = [
        _normalize_time_series_point(p)
        for p in config.get("time_series", [])
        if isinstance(p, dict)
    ]
    return {
        "baseline_window": baseline_window,
        "trend_metrics": trend_metrics,
        "recurrences": recurrences,
        "time_series": time_series,
        "parser_regression_detected": bool(config.get("parser_regression_detected", False)),
        "recurring_failure_pattern": bool(config.get("recurring_failure_pattern", False)),
        "risk_debt_burn_rate": float(config.get("risk_debt_burn_rate", 0.0) or 0.0),
        "analysis_scope": str(config.get("analysis_scope", "") or ""),
        "input_refs": [str(ref) for ref in config.get("input_refs", []) if str(ref)],
        "confidence": float(config.get("confidence", 0.0) or 0.0),
        "limits": _normalize_limits(config.get("limits", {})),
    }


def _normalize_baseline_window(w: dict[str, Any]) -> dict[str, Any]:
    return {
        "window_id": str(w.get("window_id", "") or ""),
        "start_date": str(w.get("start_date", "") or ""),
        "end_date": str(w.get("end_date", "") or ""),
        "baseline_metrics": dict(w.get("baseline_metrics", {}) or {}),
    }


def _normalize_trend_metric(m: dict[str, Any]) -> dict[str, Any]:
    return {
        "metric_id": str(m.get("metric_id", "") or ""),
        "metric_type": str(m.get("metric_type", "") or ""),
        "value": float(m.get("value", 0.0) or 0.0),
        "trend_direction": str(m.get("trend_direction", "") or ""),
        "confidence": float(m.get("confidence", 0.0) or 0.0),
        "sourceRef": str(m.get("sourceRef", "") or ""),
        "rationale": str(m.get("rationale", "") or ""),
    }


def _normalize_recurrence(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "recurrence_id": str(r.get("recurrence_id", "") or ""),
        "failure_pattern": str(r.get("failure_pattern", "") or ""),
        "occurrence_count": int(r.get("occurrence_count", 0) or 0),
        "resolved": bool(r.get("resolved", False)),
        "severity": str(r.get("severity", "") or ""),
        "sourceRef": str(r.get("sourceRef", "") or ""),
        "rationale": str(r.get("rationale", "") or ""),
    }


def _normalize_time_series_point(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "point_id": str(p.get("point_id", "") or ""),
        "timestamp": str(p.get("timestamp", "") or ""),
        "metric_type": str(p.get("metric_type", "") or ""),
        "value": float(p.get("value", 0.0) or 0.0),
        "failure_pattern": str(p.get("failure_pattern", "") or ""),
        "status": str(p.get("status", "") or ""),
        "sourceRef": str(p.get("sourceRef", "") or ""),
    }


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_trend_metrics": int(limits.get("max_trend_metrics", 50) or 50),
        "max_recurrences": int(limits.get("max_recurrences", 20) or 20),
        "max_time_series_points": int(limits.get("max_time_series_points", 500) or 500),
        "risk_debt_threshold": float(limits.get("risk_debt_threshold", 0.3) or 0.3),
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
        "min_baseline_window_days": int(limits.get("min_baseline_window_days", 7) or 7),
        "max_baseline_window_days": int(limits.get("max_baseline_window_days", 90) or 90),
    }


def _calculate_window_days(window: dict[str, Any]) -> int:
    try:
        from datetime import datetime
        start = datetime.fromisoformat(str(window.get("start_date", "")).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(window.get("end_date", "")).replace("Z", "+00:00"))
        return max(0, int((end - start).days))
    except Exception:
        return 0


def _derive_diagnostics(config: dict[str, Any], baseline_window_days: int) -> dict[str, Any]:
    baseline_metrics = config["baseline_window"]["baseline_metrics"]
    regressing_metric_ids = sorted(
        metric["metric_id"]
        for metric in config["trend_metrics"]
        if metric["metric_id"] and _metric_regressed(metric, baseline_metrics)
    )
    derived_recurrences = _derive_recurrences(config["time_series"])
    duplicate_recurrence_ids = _duplicates([r["recurrence_id"] for r in config["recurrences"] if r["recurrence_id"]])
    missing_source_ref_ids = sorted(
        [
            *[m["metric_id"] for m in config["trend_metrics"] if m["metric_id"] and not m["sourceRef"]],
            *[r["recurrence_id"] for r in config["recurrences"] if r["recurrence_id"] and not r["sourceRef"]],
            *[p["point_id"] for p in config["time_series"] if p["point_id"] and not p["sourceRef"]],
        ]
    )
    return {
        "regressing_metric_ids": regressing_metric_ids,
        "derived_recurrences": derived_recurrences,
        "duplicate_recurrence_ids": sorted(duplicate_recurrence_ids),
        "missing_source_ref_ids": missing_source_ref_ids,
        "invalid_window": baseline_window_days <= 0,
        "stale_window": baseline_window_days > config["limits"]["max_baseline_window_days"],
        "too_short_window": 0 < baseline_window_days < config["limits"]["min_baseline_window_days"],
    }


def _metric_regressed(metric: dict[str, Any], baseline_metrics: dict[str, Any]) -> bool:
    baseline = baseline_metrics.get(metric["metric_type"])
    if baseline is None:
        return metric["trend_direction"] in {"up", "down"} and metric["metric_type"] in _REGRESSION_DIRECTIONS
    try:
        baseline_value = float(baseline)
    except (TypeError, ValueError):
        return False
    current = metric["value"]
    direction = _REGRESSION_DIRECTIONS.get(metric["metric_type"])
    if direction == "up_is_bad":
        return current > baseline_value
    if direction == "down_is_bad":
        return current < baseline_value
    return False


_REGRESSION_DIRECTIONS = {
    "failure_rate": "up_is_bad",
    "flake_rate": "up_is_bad",
    "timeout_rate": "up_is_bad",
    "risk_debt": "up_is_bad",
    "parser_error_rate": "up_is_bad",
    "coverage": "down_is_bad",
    "mutation_score": "down_is_bad",
}


def _derive_recurrences(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    source_refs: dict[str, str] = {}
    for point in points:
        if point["status"] not in {"failed", "error", "timeout"} or not point["failure_pattern"]:
            continue
        counts[point["failure_pattern"]] = counts.get(point["failure_pattern"], 0) + 1
        source_refs.setdefault(point["failure_pattern"], point["sourceRef"])
    return [
        {
            "failure_pattern": pattern,
            "occurrence_count": count,
            "sourceRef": source_refs.get(pattern, ""),
        }
        for pattern, count in sorted(counts.items())
        if count >= 3
    ]


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def _findings_for(
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    source_ref: str,
) -> list[HistoricalRegressionFinding]:
    findings: list[HistoricalRegressionFinding] = []

    # HATE-GAP-057 primary negative: recurring failure blocked
    recurring_failures = [
        r for r in config["recurrences"]
        if r.get("occurrence_count", 0) >= 3 and not r.get("resolved")
    ]

    if recurring_failures:
        findings.append(_finding(
            "historical_regression_recurring_failure_blocked",
            "Recurring failure pattern detected with 3+ occurrences unresolved.",
            source_ref,
        ))

    if diagnostics["derived_recurrences"]:
        findings.append(_finding(
            "historical_regression_recurring_failure_blocked",
            "Recurring failure pattern inferred from time series.",
            source_ref,
        ))

    if diagnostics["regressing_metric_ids"]:
        findings.append(_finding(
            "historical_regression_trend_degradation_detected",
            f"Historical trend metrics regressed: {', '.join(diagnostics['regressing_metric_ids'])}.",
            source_ref,
        ))

    if diagnostics["invalid_window"]:
        findings.append(_finding(
            "historical_regression_baseline_window_invalid",
            "Baseline window is invalid or empty.",
            source_ref,
        ))

    if diagnostics["too_short_window"] or diagnostics["stale_window"]:
        findings.append(_finding(
            "historical_regression_baseline_window_out_of_policy",
            "Baseline window is outside configured policy bounds.",
            source_ref,
        ))

    if diagnostics["duplicate_recurrence_ids"]:
        findings.append(_finding(
            "historical_regression_duplicate_recurrence_id",
            f"Duplicate recurrence ids detected: {', '.join(diagnostics['duplicate_recurrence_ids'])}.",
            source_ref,
        ))

    if config.get("recurring_failure_pattern"):
        findings.append(_finding(
            "historical_regression_recurring_failure_blocked",
            "Recurring failure pattern flag set.",
            source_ref,
        ))

    # Parser regression detection
    if config.get("parser_regression_detected"):
        findings.append(_finding(
            "historical_regression_parser_regression_detected",
            "Parser regression detected.",
            source_ref,
        ))

    # Risk debt burn rate check
    if config.get("risk_debt_burn_rate", 0.0) > config["limits"].get("risk_debt_threshold", 0.3):
        findings.append(_finding(
            "historical_regression_risk_debt_burn_up",
            f"Risk debt burn rate {config['risk_debt_burn_rate']} exceeds threshold {config['limits']['risk_debt_threshold']}.",
            source_ref,
        ))

    # Check for missing sourceRef on recurrences
    for r in config["recurrences"]:
        if not r.get("sourceRef"):
            findings.append(_finding(
                "historical_regression_recurring_failure_blocked",
                f"Recurrence '{r.get('recurrence_id')}' missing sourceRef.",
                source_ref,
            ))

    for missing_id in diagnostics["missing_source_ref_ids"]:
        if not any(missing_id == r.get("recurrence_id") for r in config["recurrences"]):
            findings.append(_finding(
                "historical_regression_source_ref_missing",
                f"Historical regression item '{missing_id}' missing sourceRef.",
                source_ref,
            ))

    if len(config["trend_metrics"]) > config["limits"]["max_trend_metrics"]:
        findings.append(_finding(
            "historical_regression_trend_metric_budget_exceeded",
            f"Trend metric count {len(config['trend_metrics'])} exceeds limit {config['limits']['max_trend_metrics']}.",
            source_ref,
        ))

    if len(config["recurrences"]) > config["limits"]["max_recurrences"]:
        findings.append(_finding(
            "historical_regression_recurrence_budget_exceeded",
            f"Recurrence count {len(config['recurrences'])} exceeds limit {config['limits']['max_recurrences']}.",
            source_ref,
        ))

    if len(config["time_series"]) > config["limits"]["max_time_series_points"]:
        findings.append(_finding(
            "historical_regression_time_series_budget_exceeded",
            f"Time series count {len(config['time_series'])} exceeds limit {config['limits']['max_time_series_points']}.",
            source_ref,
        ))

    # Confidence threshold check
    if config["confidence"] < config["limits"]["confidence_threshold"]:
        findings.append(_finding(
            "historical_regression_recurring_failure_blocked",
            f"Historical regression confidence {config['confidence']} below threshold {config['limits']['confidence_threshold']}.",
            source_ref,
        ))

    return findings


def _finding(code: str, message: str, source_ref: str) -> HistoricalRegressionFinding:
    return HistoricalRegressionFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
