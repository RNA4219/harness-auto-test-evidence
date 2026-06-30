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
    findings = _findings_for(regression_config, source_refs[0])
    status = "hold" if findings else "pass"
    baseline_window_days = _calculate_window_days(regression_config["baseline_window"])
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
            "baseline_window_days": baseline_window_days,
            "confidence": regression_config["confidence"],
            "finding_count": len(findings),
        },
        "baseline_window": regression_config["baseline_window"],
        "trend_metrics": regression_config["trend_metrics"],
        "recurrences": regression_config["recurrences"],
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
    return {
        "baseline_window": baseline_window,
        "trend_metrics": trend_metrics,
        "recurrences": recurrences,
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


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_trend_metrics": int(limits.get("max_trend_metrics", 50) or 50),
        "max_recurrences": int(limits.get("max_recurrences", 20) or 20),
        "risk_debt_threshold": float(limits.get("risk_debt_threshold", 0.3) or 0.3),
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
    }


def _calculate_window_days(window: dict[str, Any]) -> int:
    try:
        from datetime import datetime
        start = datetime.fromisoformat(str(window.get("start_date", "")).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(window.get("end_date", "")).replace("Z", "+00:00"))
        return max(0, int((end - start).days))
    except Exception:
        return 0


def _findings_for(config: dict[str, Any], source_ref: str) -> list[HistoricalRegressionFinding]:
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