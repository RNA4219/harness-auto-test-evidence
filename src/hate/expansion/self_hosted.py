"""Self-hosted installation evaluation for HATE-GAP-031."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SelfHostedFinding:
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


def evaluate_self_hosted_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_self_hosted_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "self-hosted-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_self_hosted_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "self-hosted-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["self-hosted"])
    self_hosted_config = _normalize_self_hosted_config(input_data.get("self_hosted_config", input_data))
    findings = _findings_for(self_hosted_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "self-hosted-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "self_hosted_config": self_hosted_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "installer_contract_defined": self_hosted_config["installer_contract_defined"],
            "configuration_schema_defined": self_hosted_config["configuration_schema_defined"],
            "upgrade_plan_defined": self_hosted_config["upgrade_plan_defined"],
            "rollback_supported": self_hosted_config["rollback_supported"],
            "backup_prerequisite_defined": self_hosted_config["backup_prerequisite_defined"],
            "offline_verification_supported": self_hosted_config["offline_verification_supported"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_self_hosted_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    return {
        "installer_contract_defined": bool(config.get("installer_contract_defined", False)),
        "configuration_schema_defined": bool(config.get("configuration_schema_defined", False)),
        "upgrade_plan_defined": bool(config.get("upgrade_plan_defined", False)),
        "rollback_supported": bool(config.get("rollback_supported", False)),
        "backup_prerequisite_defined": bool(config.get("backup_prerequisite_defined", False)),
        "offline_verification_supported": bool(config.get("offline_verification_supported", False)),
        "air_gapped_mode": bool(config.get("air_gapped_mode", False)),
        "current_version": str(config.get("current_version") or ""),
        "target_version": str(config.get("target_version") or ""),
        "downgrade_requested": bool(config.get("downgrade_requested", False)),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[SelfHostedFinding]:
    findings: list[SelfHostedFinding] = []
    if not config["installer_contract_defined"]:
        findings.append(_finding(
            "self_hosted_installer_contract_missing",
            "Self-hosted installation requires installer contract.",
            source_ref,
        ))
    if not config["configuration_schema_defined"]:
        findings.append(_finding(
            "self_hosted_config_schema_missing",
            "Self-hosted installation requires configuration schema.",
            source_ref,
        ))
    if not config["upgrade_plan_defined"]:
        findings.append(_finding(
            "self_hosted_upgrade_plan_missing",
            "Self-hosted installation requires upgrade plan.",
            source_ref,
        ))
    if not config["rollback_supported"]:
        findings.append(_finding(
            "self_hosted_rollback_required",
            "Self-hosted installation requires rollback support.",
            source_ref,
        ))
    if not config["backup_prerequisite_defined"]:
        findings.append(_finding(
            "self_hosted_backup_prerequisite_missing",
            "Self-hosted installation requires backup prerequisite.",
            source_ref,
        ))
    if not config["offline_verification_supported"]:
        findings.append(_finding(
            "self_hosted_offline_verification_missing",
            "Self-hosted installation requires offline package verification.",
            source_ref,
        ))
    if config["downgrade_requested"] and not config["rollback_supported"]:
        findings.append(_finding(
            "self_hosted_downgrade_without_rollback",
            "Downgrade requires rollback support.",
            source_ref,
        ))
    return findings


def _finding(code: str, message: str, source_ref: str) -> SelfHostedFinding:
    return SelfHostedFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
