"""Support operations observability report modeling.

The report validates structured logs, aggregate metrics, alerts, and incident
triggers without exposing raw artifacts, secrets, PII, or customer paths.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|token|secret|bearer|password|private[_-]?key|AKIA[0-9A-Z]{16})"
)
PATH_PATTERN = re.compile(r"(?i)([A-Z]:\\Users\\|/home/|/Users/|\\\\[^\\]+\\)")
REQUIRED_LOG_FIELDS = {"event_id", "level", "message", "correlation_id", "sourceRef"}
RELEASE_METRICS = {"hard_dq_count", "soft_gap_count", "readiness_latency_ms"}
REQUIRED_GAP_METRICS = {"job_duration_seconds"}
REQUIRED_GAP_LOG_FIELDS = {"run_id"}


@dataclass
class ObservabilityReport:
    """Support ops report output."""

    report_id: str
    overall_status: str
    logs: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, Any]] = field(default_factory=list)
    spans: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    incidents: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    sourceRefs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "HATE/v1",
            "record_type": "support-ops-report",
            "report_id": self.report_id,
            "overall_status": self.overall_status,
            "logs": self.logs,
            "metrics": self.metrics,
            "spans": self.spans,
            "alerts": self.alerts,
            "incidents": self.incidents,
            "findings": self.findings,
            "summary": {
                "log_count": len(self.logs),
                "metric_count": len(self.metrics),
                "span_count": len(self.spans),
                "alert_count": len(self.alerts),
                "incident_count": len(self.incidents),
                "finding_count": len(self.findings),
                "hard_dq_count": sum(1 for item in self.findings if item.get("readiness_effect") == "hard_dq"),
                "hold_count": sum(1 for item in self.findings if item.get("readiness_effect") == "hold"),
            },
            "sourceRefs": self.sourceRefs,
        }


def build_support_ops_report(data: dict[str, Any]) -> dict[str, Any]:
    """Build a support ops report from logs, metrics, and alerts."""
    report_id = data.get("report_id", "support-ops-report")
    logs, log_findings = validate_logs(data.get("logs", []), report_id)
    metrics, metric_findings = validate_metrics(
        data.get("metrics", []),
        profile=data.get("profile", "default"),
        report_id=report_id,
    )
    spans, span_findings = validate_spans(data.get("spans", []), report_id)
    alerts, incidents, alert_findings = validate_alerts(data.get("alerts", []), metrics, report_id)

    findings = log_findings + metric_findings + span_findings + alert_findings
    overall_status = _status_from_findings(findings)
    return ObservabilityReport(
        report_id=report_id,
        overall_status=overall_status,
        logs=logs,
        metrics=metrics,
        spans=spans,
        alerts=alerts,
        incidents=incidents,
        findings=findings,
        sourceRefs=data.get("sourceRefs", []),
    ).to_dict()


def evaluate_observability_fixture(payload: dict[str, Any]) -> dict[str, str]:
    """Evaluate the product gap observability fixture contract."""
    data = payload.get("input", {})
    report = build_observability_gap_report(data, payload.get("fixture_id", "observability-gap"))
    finding_code = report["findings"][0]["code"] if report["findings"] else ""
    return {
        "status": report["overall_status"],
        "finding_code": finding_code,
        "readiness_effect": "hold" if report["overall_status"] == "hold" else "none",
    }


def build_observability_gap_report(data: dict[str, Any], report_id: str = "observability-gap") -> dict[str, Any]:
    """Build the compact report used by HATE-GAP-010 closure fixtures."""
    metric_names = _names_from_list(data.get("metrics", []))
    log_fields = _names_from_list(data.get("logs", []))
    spans_input = data.get("spans", [])
    spans = _span_dicts_from_list(spans_input)
    findings: list[dict[str, Any]] = []

    missing_metrics = sorted(REQUIRED_GAP_METRICS - metric_names)
    for metric_name in missing_metrics:
        findings.append(_finding(
            "observability_missing_metric",
            "hold",
            f"Required observability metric is missing: {metric_name}",
            report_id,
            f"metrics/{metric_name}",
        ))

    missing_log_fields = sorted(REQUIRED_GAP_LOG_FIELDS - log_fields)
    for field_name in missing_log_fields:
        findings.append(_finding(
            "observability_missing_log_field",
            "hold",
            f"Required observability log field is missing: {field_name}",
            report_id,
            f"logs/{field_name}",
        ))

    if not spans:
        findings.append(_finding(
            "observability_missing_trace_span",
            "hold",
            "At least one trace span is required for run correlation.",
            report_id,
            "spans",
        ))

    return ObservabilityReport(
        report_id=report_id,
        overall_status=_status_from_findings(findings),
        logs=[{"field": name, "status": "present"} for name in sorted(log_fields)],
        metrics=[{"name": name, "status": "present"} for name in sorted(metric_names)],
        spans=spans,
        findings=findings,
        sourceRefs=[f"fixtures/ops/observability/{report_id}/fixture.json"],
    ).to_dict()


def validate_logs(logs: list[dict[str, Any]], report_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate structured log events and redact unsafe fields."""
    safe_logs: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for index, event in enumerate(logs):
        missing = sorted(REQUIRED_LOG_FIELDS - set(event))
        if missing:
            findings.append(_finding(
                "structured_log_missing_field",
                "hold",
                f"Structured log missing required fields: {missing}",
                report_id,
                f"logs/{index}",
            ))
        safe_event = {}
        redacted = False
        for key, value in event.items():
            if key in {"raw_artifact", "raw_stack", "raw_log", "artifact_content"}:
                redacted = True
                continue
            if isinstance(value, str):
                clean = _redact_text(value)
                redacted = redacted or clean != value
                safe_event[key] = clean
            else:
                safe_event[key] = value
        safe_event["redaction_status"] = "redacted" if redacted else event.get("redaction_status", "not_required")
        if redacted:
            findings.append(_finding(
                "unsafe_log_field_redacted",
                "hold",
                "Unsafe log field was redacted or removed.",
                report_id,
                f"logs/{index}",
            ))
        safe_logs.append(safe_event)
    return safe_logs, findings


def validate_metrics(
    metrics: list[dict[str, Any]],
    profile: str,
    report_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate metric status and release-critical metric coverage."""
    findings: list[dict[str, Any]] = []
    metric_names = {item.get("name") for item in metrics}
    if profile in {"product", "release"}:
        missing = sorted(RELEASE_METRICS - metric_names)
        for name in missing:
            findings.append(_finding(
                "missing_release_metric",
                "hold",
                f"Release-critical metric is missing: {name}",
                report_id,
                f"metrics/{name}",
            ))
    safe_metrics = []
    for index, metric in enumerate(metrics):
        safe_metric = dict(metric)
        labels = safe_metric.get("labels", {})
        if isinstance(labels, dict) and len(labels) > int(safe_metric.get("max_label_count", 20)):
            findings.append(_finding(
                "metric_cardinality_exceeded",
                "hold",
                "Metric label cardinality exceeds configured budget.",
                report_id,
                f"metrics/{index}",
            ))
        safe_metric.setdefault("status", "pass")
        safe_metric.setdefault("sourceRef", f"metrics/{index}")
        safe_metrics.append(safe_metric)
    return safe_metrics, findings


def validate_spans(spans: list[dict[str, Any]] | list[str], report_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate trace span shape for support operations reporting."""
    findings: list[dict[str, Any]] = []
    safe_spans = _span_dicts_from_list(spans)
    for index, span in enumerate(safe_spans):
        if not span.get("name"):
            findings.append(_finding(
                "trace_span_missing_name",
                "hold",
                "Trace span is missing a name.",
                report_id,
                f"spans/{index}",
            ))
        if "duration_ms" in span and span["duration_ms"] < 0:
            findings.append(_finding(
                "trace_span_invalid_duration",
                "hold",
                "Trace span duration must be non-negative.",
                report_id,
                f"spans/{index}",
            ))
    return safe_spans, findings


def validate_alerts(
    alerts: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    report_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Project alert rules and incident triggers from metrics."""
    metric_map = {item.get("name"): item for item in metrics}
    findings: list[dict[str, Any]] = []
    safe_alerts: list[dict[str, Any]] = []
    incidents: list[dict[str, Any]] = []
    for index, alert in enumerate(alerts):
        metric_name = alert.get("metric")
        threshold = alert.get("threshold")
        comparison = alert.get("comparison", ">")
        metric = metric_map.get(metric_name)
        if not metric:
            findings.append(_finding(
                "alert_metric_missing",
                "hold",
                f"Alert references missing metric: {metric_name}",
                report_id,
                f"alerts/{index}",
            ))
            continue
        value = metric.get("value", 0)
        triggered = _compare(value, threshold, comparison)
        safe_alert = {
            **alert,
            "triggered": triggered,
            "sourceRef": alert.get("sourceRef", f"alerts/{index}"),
        }
        safe_alerts.append(safe_alert)
        if triggered:
            incidents.append({
                "incident_id": f"inc-{report_id}-{index}",
                "class": alert.get("incident_class", "INC-5"),
                "severity": alert.get("severity", "sev3"),
                "status": "triggered",
                "metric": metric_name,
                "value": value,
                "threshold": threshold,
                "sourceRef": safe_alert["sourceRef"],
            })
    return safe_alerts, incidents, findings


def _compare(value: int | float, threshold: int | float, comparison: str) -> bool:
    if comparison == ">=":
        return value >= threshold
    if comparison == "<":
        return value < threshold
    if comparison == "<=":
        return value <= threshold
    if comparison == "==":
        return value == threshold
    return value > threshold


def _redact_text(value: str) -> str:
    value = SECRET_PATTERN.sub("[REDACTED]", value)
    value = PATH_PATTERN.sub("[REDACTED_PATH]", value)
    return value


def _names_from_list(items: list[Any]) -> set[str]:
    names: set[str] = set()
    for item in items:
        if isinstance(item, str):
            names.add(item)
        elif isinstance(item, dict):
            name = item.get("name") or item.get("field")
            if isinstance(name, str):
                names.add(name)
    return names


def _span_dicts_from_list(items: list[Any]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if isinstance(item, str):
            spans.append({"name": item, "status": "present", "sourceRef": f"spans/{index}"})
        elif isinstance(item, dict):
            span = dict(item)
            span.setdefault("sourceRef", f"spans/{index}")
            spans.append(span)
    return spans


def _finding(
    code: str,
    effect: str,
    message: str,
    report_id: str,
    source_ref: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "critical" if effect == "hard_dq" else effect,
        "readiness_effect": effect,
        "message": message,
        "sourceRef": f"fixtures/support-ops/observability/{report_id}/fixture.json#{source_ref}",
    }


def _status_from_findings(findings: list[dict[str, Any]]) -> str:
    if any(item.get("readiness_effect") == "hard_dq" for item in findings):
        return "blocked"
    if any(item.get("readiness_effect") == "hold" for item in findings):
        return "hold"
    if any(item.get("readiness_effect") == "soft_gap" for item in findings):
        return "soft_gap"
    return "pass"
