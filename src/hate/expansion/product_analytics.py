"""Product analytics evaluation for HATE-GAP-036."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProductAnalyticsFinding:
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


def evaluate_product_analytics_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_product_analytics_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "product-analytics-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_product_analytics_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "product-analytics-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["product-analytics"])
    analytics_config = _normalize_analytics_config(
        input_data.get("analytics_config", input_data)
    )
    findings = _findings_for(analytics_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "product-analytics-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "analytics_config": analytics_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "event_allowlist_defined": analytics_config["event_allowlist_defined"],
            "event_count": len(analytics_config["events"]),
            "opt_in_required": analytics_config["opt_in_required"],
            "tenant_opt_in": analytics_config["tenant_opt_in"],
            "aggregate_only": analytics_config["aggregate_only"],
            "suppression_rules_defined": analytics_config["suppression_rules_defined"],
            "usage_report_defined": analytics_config["usage_report_defined"],
            "adoption_kpi_count": len(analytics_config["adoption_kpis"]),
            "raw_path_present": analytics_config["raw_path_present"],
            "raw_artifact_ref_present": analytics_config["raw_artifact_ref_present"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_analytics_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    events = [
        str(event) for event in config.get("events", []) if str(event)
    ]
    adoption_kpis = [
        str(kpi) for kpi in config.get("adoption_kpis", []) if str(kpi)
    ]
    unknown_events = _collect_unknown_events(events, config)
    return {
        "event_allowlist_defined": bool(config.get("event_allowlist_defined", False)),
        "events": events,
        "unknown_events": unknown_events,
        "opt_in_required": bool(config.get("opt_in_required", False)),
        "tenant_opt_in": bool(config.get("tenant_opt_in", False)),
        "aggregate_only": bool(config.get("aggregate_only", False)),
        "suppression_rules_defined": bool(config.get("suppression_rules_defined", False)),
        "usage_report_defined": bool(config.get("usage_report_defined", False)),
        "adoption_kpis": adoption_kpis,
        "raw_path_present": bool(config.get("raw_path_present", False)),
        "raw_artifact_ref_present": bool(config.get("raw_artifact_ref_present", False)),
    }


def _collect_unknown_events(events: list[str], config: dict[str, Any]) -> list[str]:
    # Assume allowlist is stored somewhere; for now, check against common events
    # In real implementation, this would check against a defined allowlist
    allowlist = set(config.get("event_allowlist", []))
    if not allowlist:
        return []
    return [event for event in events if event not in allowlist]


def _findings_for(config: dict[str, Any], source_ref: str) -> list[ProductAnalyticsFinding]:
    findings: list[ProductAnalyticsFinding] = []

    if not config["event_allowlist_defined"]:
        findings.append(_finding(
            "product_analytics_event_allowlist_missing",
            "Product analytics requires event allowlist definition.",
            source_ref,
        ))

    if config["unknown_events"]:
        findings.append(_finding(
            "product_analytics_unknown_event",
            f"Product analytics found unknown events: {', '.join(config['unknown_events'])}.",
            source_ref,
        ))

    if config["opt_in_required"] and not config["tenant_opt_in"]:
        findings.append(_finding(
            "product_analytics_opt_in_missing",
            "Product analytics requires tenant opt-in for tracking.",
            source_ref,
        ))

    if config["raw_path_present"]:
        findings.append(_finding(
            "product_analytics_raw_path_event_denied",
            "Product analytics raw path events are not allowed in aggregate-only mode.",
            source_ref,
        ))

    if config["raw_artifact_ref_present"]:
        findings.append(_finding(
            "product_analytics_raw_artifact_ref_denied",
            "Product analytics raw artifact references are not allowed in aggregate-only mode.",
            source_ref,
        ))

    if not config["suppression_rules_defined"]:
        findings.append(_finding(
            "product_analytics_suppression_rules_missing",
            "Product analytics requires suppression rules definition.",
            source_ref,
        ))

    if not config["usage_report_defined"]:
        findings.append(_finding(
            "product_analytics_usage_report_missing",
            "Product analytics requires usage report definition.",
            source_ref,
        ))

    if not config["adoption_kpis"]:
        findings.append(_finding(
            "product_analytics_adoption_kpi_missing",
            "Product analytics requires at least one adoption KPI.",
            source_ref,
        ))

    return findings


def _finding(code: str, message: str, source_ref: str) -> ProductAnalyticsFinding:
    return ProductAnalyticsFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )