"""Cost governance evaluation for HATE-GAP-039."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CostGovernanceFinding:
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


def evaluate_cost_governance_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_cost_governance_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "cost-governance-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_cost_governance_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "cost-governance-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["cost-governance"])
    cost_config = _normalize_cost_config(input_data.get("cost_config", input_data))
    findings = _findings_for(cost_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "cost-governance-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "cost_config": cost_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "tenant_id": cost_config["tenant_id"],
            "forecast_window_days": cost_config["forecast_window_days"],
            "storage_gb_current": cost_config["storage_gb_current"],
            "storage_gb_forecast": cost_config["storage_gb_forecast"],
            "storage_budget_gb": cost_config["storage_budget_gb"],
            "egress_gb_forecast": cost_config["egress_gb_forecast"],
            "egress_budget_gb": cost_config["egress_budget_gb"],
            "budget_thresholds_defined": cost_config["budget_thresholds_defined"],
            "storage_class_recommendation": cost_config["storage_class_recommendation"],
            "remediation_plan_defined": cost_config["remediation_plan_defined"],
            "non_gating_advisory": cost_config["non_gating_advisory"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_cost_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    return {
        "tenant_id": str(config.get("tenant_id") or ""),
        "forecast_window_days": int(config.get("forecast_window_days", 0) or 0),
        "storage_gb_current": float(config.get("storage_gb_current", 0.0) or 0.0),
        "storage_gb_forecast": float(config.get("storage_gb_forecast", 0.0) or 0.0),
        "storage_budget_gb": float(config.get("storage_budget_gb", 0.0) or 0.0),
        "egress_gb_forecast": float(config.get("egress_gb_forecast", 0.0) or 0.0),
        "egress_budget_gb": float(config.get("egress_budget_gb", 0.0) or 0.0),
        "retention_cost_forecast": float(config.get("retention_cost_forecast", 0.0) or 0.0),
        "budget_thresholds_defined": bool(config.get("budget_thresholds_defined", False)),
        "storage_class_recommendation": str(config.get("storage_class_recommendation") or ""),
        "remediation_plan_defined": bool(config.get("remediation_plan_defined", False)),
        "non_gating_advisory": bool(config.get("non_gating_advisory", False)),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[CostGovernanceFinding]:
    findings: list[CostGovernanceFinding] = []
    if not config["tenant_id"]:
        findings.append(_finding(
            "cost_governance_missing_tenant_scope",
            "Cost governance requires tenant scope.",
            source_ref,
        ))
    if not config["budget_thresholds_defined"]:
        findings.append(_finding(
            "cost_governance_budget_thresholds_missing",
            "Cost governance requires budget thresholds.",
            source_ref,
        ))
    if config["storage_gb_forecast"] > config["storage_budget_gb"]:
        findings.append(_finding(
            "cost_governance_storage_budget_exceeded",
            f"Storage forecast {config['storage_gb_forecast']} GB exceeds budget {config['storage_budget_gb']} GB.",
            source_ref,
        ))
    if config["egress_gb_forecast"] > config["egress_budget_gb"]:
        findings.append(_finding(
            "cost_governance_egress_risk_hold",
            f"Egress forecast {config['egress_gb_forecast']} GB exceeds budget {config['egress_budget_gb']} GB.",
            source_ref,
        ))
    if config["retention_cost_forecast"] > 0 and not config["remediation_plan_defined"]:
        findings.append(_finding(
            "cost_governance_retention_cost_unbounded",
            "Retention cost forecast requires remediation plan.",
            source_ref,
        ))
    if not config["storage_class_recommendation"]:
        findings.append(_finding(
            "cost_governance_storage_recommendation_missing",
            "Cost governance requires storage class recommendation.",
            source_ref,
        ))
    if not config["remediation_plan_defined"]:
        findings.append(_finding(
            "cost_governance_remediation_plan_missing",
            "Cost governance requires remediation plan.",
            source_ref,
        ))
    return findings


def _finding(code: str, message: str, source_ref: str) -> CostGovernanceFinding:
    return CostGovernanceFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )