"""Beta acceptance evaluation for HATE-GAP-040."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BetaAcceptanceFinding:
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


def evaluate_beta_acceptance_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_beta_acceptance_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "beta-acceptance-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_beta_acceptance_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "beta-acceptance-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["beta-acceptance"])
    beta_config = _normalize_beta_config(input_data.get("beta_config", input_data))
    findings = _findings_for(beta_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "beta-acceptance-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "beta_config": beta_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "cohort_defined": beta_config["cohort_defined"],
            "cohort_id": beta_config["cohort_id"],
            "customer_evidence_limits_defined": beta_config["customer_evidence_limits_defined"],
            "feedback_items_count": len(beta_config["feedback_items"]),
            "blocker_count": beta_config["blocker_count"],
            "critical_blocker_count": beta_config["critical_blocker_count"],
            "triage_owner": beta_config["triage_owner"],
            "exit_criteria_defined": beta_config["exit_criteria_defined"],
            "exit_criteria_met": beta_config["exit_criteria_met"],
            "acceptance_record_present": beta_config["acceptance_record_present"],
            "customer_secret_present": beta_config["customer_secret_present"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_beta_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    feedback_items = [
        _normalize_feedback_item(item)
        for item in config.get("feedback_items", [])
        if isinstance(item, dict)
    ]
    return {
        "cohort_defined": bool(config.get("cohort_defined", False)),
        "cohort_id": str(config.get("cohort_id") or ""),
        "customer_evidence_limits_defined": bool(config.get("customer_evidence_limits_defined", False)),
        "feedback_items": feedback_items,
        "blocker_count": int(config.get("blocker_count", 0) or 0),
        "critical_blocker_count": int(config.get("critical_blocker_count", 0) or 0),
        "triage_owner": str(config.get("triage_owner") or ""),
        "exit_criteria_defined": bool(config.get("exit_criteria_defined", False)),
        "exit_criteria_met": bool(config.get("exit_criteria_met", False)),
        "acceptance_record_present": bool(config.get("acceptance_record_present", False)),
        "customer_secret_present": bool(config.get("customer_secret_present", False)),
    }


def _normalize_feedback_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "feedback_id": str(item.get("feedback_id") or ""),
        "classification": str(item.get("classification") or ""),
        "severity": str(item.get("severity") or ""),
        "sourceRef": str(item.get("sourceRef") or ""),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[BetaAcceptanceFinding]:
    findings: list[BetaAcceptanceFinding] = []
    if not config["cohort_defined"]:
        findings.append(_finding(
            "beta_acceptance_cohort_missing",
            "Beta acceptance requires cohort definition.",
            source_ref,
        ))
    if not config["customer_evidence_limits_defined"]:
        findings.append(_finding(
            "beta_acceptance_customer_evidence_limits_missing",
            "Beta acceptance requires customer evidence limits.",
            source_ref,
        ))
    unclassified_feedback = [
        item for item in config["feedback_items"]
        if not item.get("classification")
    ]
    if unclassified_feedback:
        findings.append(_finding(
            "beta_acceptance_feedback_unclassified",
            f"Beta acceptance found {len(unclassified_feedback)} unclassified feedback items.",
            source_ref,
        ))
    if config["blocker_count"] > 0:
        findings.append(_finding(
            "beta_acceptance_blocker_feedback_hold",
            f"Beta acceptance has {config['blocker_count']} blocker feedback items.",
            source_ref,
        ))
    if config["critical_blocker_count"] > 0:
        findings.append(_finding(
            "beta_acceptance_critical_blocker_present",
            f"Beta acceptance has {config['critical_blocker_count']} critical blocker items.",
            source_ref,
        ))
    if not config["triage_owner"]:
        findings.append(_finding(
            "beta_acceptance_triage_owner_missing",
            "Beta acceptance requires triage owner.",
            source_ref,
        ))
    if not config["exit_criteria_defined"]:
        findings.append(_finding(
            "beta_acceptance_exit_criteria_missing",
            "Beta acceptance requires exit criteria.",
            source_ref,
        ))
    if not config["exit_criteria_met"]:
        findings.append(_finding(
            "beta_acceptance_exit_criteria_not_met",
            "Beta acceptance exit criteria not met.",
            source_ref,
        ))
    if config["customer_secret_present"]:
        findings.append(_finding(
            "beta_acceptance_customer_secret_denied",
            "Customer secret in beta evidence is denied.",
            source_ref,
        ))
    return findings


def _finding(code: str, message: str, source_ref: str) -> BetaAcceptanceFinding:
    return BetaAcceptanceFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )