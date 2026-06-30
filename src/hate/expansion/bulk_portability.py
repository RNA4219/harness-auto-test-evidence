"""Bulk portability evaluation for HATE-GAP-029."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BulkPortabilityFinding:
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


def evaluate_bulk_portability_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_bulk_portability_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "bulk-portability-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_bulk_portability_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "bulk-portability-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["bulk-portability"])
    portability_config = _normalize_portability_config(input_data.get("portability_config", input_data))
    findings = _findings_for(portability_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "bulk-portability-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "portability_config": portability_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "chunk_manifest_defined": portability_config["chunk_manifest_defined"],
            "resume_token_supported": portability_config["resume_token_supported"],
            "integrity_manifest_defined": portability_config["integrity_manifest_defined"],
            "tenant_boundary_enforced": portability_config["tenant_boundary_enforced"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_portability_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    return {
        "chunk_manifest_defined": bool(config.get("chunk_manifest_defined", False)),
        "resume_token_supported": bool(config.get("resume_token_supported", False)),
        "integrity_manifest_defined": bool(config.get("integrity_manifest_defined", False)),
        "partial_failure_handling": bool(config.get("partial_failure_handling", False)),
        "tenant_boundary_enforced": bool(config.get("tenant_boundary_enforced", False)),
        "source_tenant": str(config.get("source_tenant") or ""),
        "target_tenant": str(config.get("target_tenant") or ""),
        "migration_size_mb": int(config.get("migration_size_mb", 0) or 0),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[BulkPortabilityFinding]:
    findings: list[BulkPortabilityFinding] = []
    if not config["chunk_manifest_defined"]:
        findings.append(_finding(
            "bulk_portability_chunk_manifest_missing",
            "Bulk import/export requires chunk manifest definition.",
            source_ref,
        ))
    if not config["resume_token_supported"]:
        findings.append(_finding(
            "bulk_portability_resume_token_missing",
            "Bulk import/export requires resume token support for resumability.",
            source_ref,
        ))
    if not config["integrity_manifest_defined"]:
        findings.append(_finding(
            "bulk_portability_integrity_manifest_missing",
            "Bulk import/export requires integrity manifest.",
            source_ref,
        ))
    if not config["partial_failure_handling"]:
        findings.append(_finding(
            "bulk_portability_partial_failure_missing",
            "Bulk import/export requires partial failure handling.",
            source_ref,
        ))
    if not config["tenant_boundary_enforced"]:
        findings.append(_finding(
            "bulk_portability_tenant_boundary_missing",
            "Bulk import/export requires tenant boundary enforcement.",
            source_ref,
        ))
    if config["source_tenant"] and config["target_tenant"]:
        if config["source_tenant"] != config["target_tenant"]:
            findings.append(_finding(
                "bulk_portability_cross_tenant_import_denied",
                "Cross-tenant bulk import is denied without explicit authorization.",
                source_ref,
            ))
    return findings


def _finding(code: str, message: str, source_ref: str) -> BulkPortabilityFinding:
    return BulkPortabilityFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )