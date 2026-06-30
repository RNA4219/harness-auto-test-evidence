"""Adapter marketplace evaluation for HATE-GAP-035."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AdapterMarketplaceFinding:
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


def evaluate_adapter_marketplace_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_adapter_marketplace_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "adapter-marketplace-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_adapter_marketplace_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "adapter-marketplace-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["adapter-marketplace"])
    plugin_config = _normalize_plugin_config(
        input_data.get("plugin_config", input_data)
    )
    findings = _findings_for(plugin_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "adapter-marketplace-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "plugin_config": plugin_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "plugin_manifest_present": plugin_config["plugin_manifest_present"],
            "signature_present": plugin_config["signature_present"],
            "signature_verified": plugin_config["signature_verified"],
            "compatibility_range": plugin_config["compatibility_range"],
            "host_version": plugin_config["host_version"],
            "is_compatible": plugin_config["is_compatible"],
            "conformance_evidence_present": plugin_config["conformance_evidence_present"],
            "deprecation_status": plugin_config["deprecation_status"],
            "revocation_record_present": plugin_config["revocation_record_present"],
            "requested_install": plugin_config["requested_install"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_plugin_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    compatibility_range = str(config.get("compatibility_range", "") or "")
    host_version = str(config.get("host_version", "") or "")
    is_compatible = _check_compatibility(compatibility_range, host_version)
    return {
        "plugin_manifest_present": bool(config.get("plugin_manifest_present", False)),
        "plugin_id": str(config.get("plugin_id", "") or ""),
        "publisher_id": str(config.get("publisher_id", "") or ""),
        "signature_present": bool(config.get("signature_present", False)),
        "signature_verified": bool(config.get("signature_verified", False)),
        "compatibility_range": compatibility_range,
        "host_version": host_version,
        "is_compatible": is_compatible,
        "conformance_evidence_present": bool(config.get("conformance_evidence_present", False)),
        "deprecation_status": str(config.get("deprecation_status", "") or ""),
        "revocation_record_present": bool(config.get("revocation_record_present", False)),
        "requested_install": bool(config.get("requested_install", False)),
    }


def _check_compatibility(compatibility_range: str, host_version: str) -> bool:
    if not compatibility_range or not host_version:
        return False
    # Simple version check: assume range like ">=1.0.0,<2.0.0"
    try:
        if compatibility_range.startswith(">="):
            min_version = compatibility_range.split(">=")[1].split(",")[0].strip()
            return host_version >= min_version
        return False
    except Exception:
        return False


def _findings_for(config: dict[str, Any], source_ref: str) -> list[AdapterMarketplaceFinding]:
    findings: list[AdapterMarketplaceFinding] = []

    if not config["plugin_manifest_present"]:
        findings.append(_finding(
            "adapter_marketplace_manifest_missing",
            "Adapter marketplace requires plugin manifest.",
            source_ref,
        ))

    if config["plugin_manifest_present"] and not config["publisher_id"]:
        findings.append(_finding(
            "adapter_marketplace_publisher_missing",
            "Adapter marketplace requires publisher ID in manifest.",
            source_ref,
        ))

    if config["plugin_manifest_present"] and config["requested_install"]:
        if not config["signature_present"]:
            findings.append(_finding(
                "adapter_marketplace_signature_missing",
                "Adapter marketplace requires signature for plugin installation.",
                source_ref,
            ))
        elif not config["signature_verified"]:
            findings.append(_finding(
                "adapter_marketplace_signature_invalid",
                "Adapter marketplace plugin signature verification failed.",
                source_ref,
            ))

    if config["plugin_manifest_present"] and config["requested_install"]:
        if not config["compatibility_range"]:
            findings.append(_finding(
                "adapter_marketplace_compatibility_missing",
                "Adapter marketplace requires compatibility range for plugin.",
                source_ref,
            ))
        elif not config["is_compatible"]:
            findings.append(_finding(
                "adapter_marketplace_incompatible_host",
                f"Adapter marketplace plugin incompatible with host version {config['host_version']}.",
                source_ref,
            ))

    if config["plugin_manifest_present"] and config["requested_install"]:
        if not config["conformance_evidence_present"]:
            findings.append(_finding(
                "adapter_marketplace_conformance_missing",
                "Adapter marketplace requires conformance evidence for plugin.",
                source_ref,
            ))

    if config["deprecation_status"] == "deprecated" and config["requested_install"]:
        findings.append(_finding(
            "adapter_marketplace_deprecated_hold",
            "Adapter marketplace plugin is deprecated and requires approval for installation.",
            source_ref,
        ))

    if config["revocation_record_present"] and config["requested_install"]:
        findings.append(_finding(
            "adapter_marketplace_revoked_plugin_denied",
            "Adapter marketplace plugin is revoked and cannot be installed.",
            source_ref,
        ))

    return findings


def _finding(code: str, message: str, source_ref: str) -> AdapterMarketplaceFinding:
    return AdapterMarketplaceFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )