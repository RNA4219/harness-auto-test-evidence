"""Dependency compliance evaluation for HATE-GAP-034."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ALLOWED_SBOM_FORMATS = {"cyclonedx-json", "spdx-json", "syft-json"}


@dataclass(frozen=True)
class DependencyComplianceFinding:
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


def evaluate_dependency_compliance_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_dependency_compliance_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "dependency-compliance-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_dependency_compliance_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "dependency-compliance-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["dependency-compliance"])
    compliance_config = _normalize_compliance_config(
        input_data.get("compliance_config", input_data)
    )
    findings = _findings_for(compliance_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "dependency-compliance-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "compliance_config": compliance_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "sbom_present": compliance_config["sbom_present"],
            "sbom_format": compliance_config["sbom_format"],
            "license_policy_defined": compliance_config["license_policy_defined"],
            "vulnerability_policy_defined": compliance_config["vulnerability_policy_defined"],
            "denied_license_count": len(compliance_config["denied_licenses_found"]),
            "vulnerability_exception_expired_count": compliance_config["vulnerability_exception_expired_count"],
            "provenance_attestation_present": compliance_config["provenance_attestation_present"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_compliance_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    packages = [
        _normalize_package(pkg)
        for pkg in config.get("packages", [])
        if isinstance(pkg, dict)
    ]
    exceptions = [
        _normalize_exception(exc)
        for exc in config.get("exceptions", [])
        if isinstance(exc, dict)
    ]
    denied_licenses_found = _collect_denied_licenses(packages, config)
    vulnerability_exception_expired_count = _count_expired_exceptions(exceptions)
    return {
        "sbom_present": bool(config.get("sbom_present", False)),
        "sbom_format": str(config.get("sbom_format", "") or ""),
        "packages": packages,
        "license_policy_defined": bool(config.get("license_policy_defined", False)),
        "allowed_licenses": [
            str(lic) for lic in config.get("allowed_licenses", []) if str(lic)
        ],
        "denied_licenses": [
            str(lic) for lic in config.get("denied_licenses", []) if str(lic)
        ],
        "denied_licenses_found": denied_licenses_found,
        "vulnerability_policy_defined": bool(config.get("vulnerability_policy_defined", False)),
        "vulnerability_max_age_days": int(config.get("vulnerability_max_age_days", 0) or 0),
        "exceptions": exceptions,
        "vulnerability_exception_expired_count": vulnerability_exception_expired_count,
        "provenance_attestation_present": bool(config.get("provenance_attestation_present", False)),
    }


def _normalize_package(pkg: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(pkg.get("name", "") or ""),
        "version": str(pkg.get("version", "") or ""),
        "license": str(pkg.get("license", "") or ""),
        "purl": str(pkg.get("purl", "") or ""),
        "vulnerabilities": [
            str(vuln) for vuln in pkg.get("vulnerabilities", []) if str(vuln)
        ],
    }


def _normalize_exception(exc: dict[str, Any]) -> dict[str, Any]:
    return {
        "package": str(exc.get("package", "") or ""),
        "reason": str(exc.get("reason", "") or ""),
        "owner": str(exc.get("owner", "") or ""),
        "expires_at": str(exc.get("expires_at", "") or ""),
    }


def _collect_denied_licenses(packages: list[dict[str, Any]], config: dict[str, Any]) -> list[str]:
    denied_licenses = set(config.get("denied_licenses", []))
    found: list[str] = []
    for pkg in packages:
        license_id = pkg.get("license", "")
        if license_id and license_id in denied_licenses:
            found.append(license_id)
    return sorted(set(found))


def _count_expired_exceptions(exceptions: list[dict[str, Any]]) -> int:
    from datetime import datetime, timezone
    expired_count = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    for exc in exceptions:
        expires_at = exc.get("expires_at", "")
        if expires_at and expires_at < now_iso:
            expired_count += 1
    return expired_count


def _findings_for(config: dict[str, Any], source_ref: str) -> list[DependencyComplianceFinding]:
    findings: list[DependencyComplianceFinding] = []
    if not config["sbom_present"]:
        findings.append(_finding(
            "dependency_compliance_sbom_missing",
            "Dependency compliance requires SBOM artifact.",
            source_ref,
        ))
    if config["sbom_present"] and config["sbom_format"] not in ALLOWED_SBOM_FORMATS:
        findings.append(_finding(
            "dependency_compliance_sbom_format_unsupported",
            f"Dependency compliance SBOM format '{config['sbom_format']}' is not supported.",
            source_ref,
        ))
    if not config["license_policy_defined"]:
        findings.append(_finding(
            "dependency_compliance_license_policy_missing",
            "Dependency compliance requires license policy definition.",
            source_ref,
        ))
    if config["denied_licenses_found"]:
        findings.append(_finding(
            "dependency_compliance_denied_license",
            f"Dependency compliance found denied licenses: {', '.join(config['denied_licenses_found'])}.",
            source_ref,
        ))
    if not config["vulnerability_policy_defined"]:
        findings.append(_finding(
            "dependency_compliance_vulnerability_policy_missing",
            "Dependency compliance requires vulnerability policy definition.",
            source_ref,
        ))
    if config["vulnerability_exception_expired_count"] > 0:
        findings.append(_finding(
            "dependency_compliance_vulnerability_exception_expired",
            f"Dependency compliance found {config['vulnerability_exception_expired_count']} expired vulnerability exceptions.",
            source_ref,
        ))
    for exc in config["exceptions"]:
        if not exc.get("owner"):
            findings.append(_finding(
                "dependency_compliance_exception_missing_owner",
                f"Dependency compliance exception for '{exc.get('package')}' missing owner.",
                source_ref,
            ))
    if not config["provenance_attestation_present"]:
        findings.append(_finding(
            "dependency_compliance_provenance_missing",
            "Dependency compliance requires provenance attestation.",
            source_ref,
        ))
    return findings


def _finding(code: str, message: str, source_ref: str) -> DependencyComplianceFinding:
    return DependencyComplianceFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )