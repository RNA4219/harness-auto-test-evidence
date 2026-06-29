"""Stable product error catalog for support operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ErrorCatalogEntry:
    """Stable user-facing error catalog entry."""

    error_code: str
    category: str
    error_class: str
    severity: str
    user_message: str
    operator_message: str
    remediation: str
    owner_action: str
    retryable: bool = False
    related_reports: tuple[str, ...] = ()
    safe_diagnostic_fields: tuple[str, ...] = (
        "error_code",
        "severity",
        "message",
        "remediation",
        "sourceRefs",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "category": self.category,
            "error_class": self.error_class,
            "severity": self.severity,
            "user_message": self.user_message,
            "operator_message": self.operator_message,
            "remediation": self.remediation,
            "owner_action": self.owner_action,
            "retryable": self.retryable,
            "related_reports": list(self.related_reports),
            "safe_diagnostic_fields": list(self.safe_diagnostic_fields),
        }


ERROR_CATALOG: dict[str, ErrorCatalogEntry] = {
    "HATE-SCH-001": ErrorCatalogEntry(
        "HATE-SCH-001",
        "SCH",
        "schema_validation",
        "error",
        "Schema validation failed.",
        "Record does not satisfy the registered schema.",
        "Validate record_type and required fields against schema-registry.json.",
        "Fix schema fields or regenerate the affected report.",
        False,
        ("schema-registry.json", "doctor-report.json"),
    ),
    "HATE-SCH-002": ErrorCatalogEntry(
        "HATE-SCH-002",
        "SCH",
        "unsupported_schema_version",
        "error",
        "Schema version is unsupported.",
        "Input requires migration or safe rejection.",
        "Use the migration guide or rerun with a supported schema version.",
        "Add migration evidence or reject the bundle safely.",
        False,
        ("migration-report.json", "schema-registry.json"),
    ),
    "HATE-ADP-001": ErrorCatalogEntry(
        "HATE-ADP-001",
        "ADP",
        "adapter_parse_failed",
        "error",
        "Adapter parse failed.",
        "Source test or coverage artifact could not be parsed.",
        "Check source artifact format, encoding, and adapter version.",
        "Attach sanitized parser diagnostics and sourceRef.",
        False,
        ("adapter-conformance-report.json",),
    ),
    "HATE-ART-001": ErrorCatalogEntry(
        "HATE-ART-001",
        "ART",
        "artifact_missing",
        "error",
        "Referenced artifact is missing.",
        "Artifact resolver could not find a referenced artifact.",
        "Check artifact path, upload step, and resolver map.",
        "Regenerate artifact manifest or restore the missing artifact.",
        False,
        ("artifact-resolver-map.json", "store-doctor-report.json"),
    ),
    "HATE-ART-003": ErrorCatalogEntry(
        "HATE-ART-003",
        "ART",
        "unsafe_artifact_blocked",
        "hard_dq",
        "Unsafe artifact was blocked.",
        "Secret, PII, unsafe URL, or restricted path was detected.",
        "Review privacy/quarantine report and redaction findings.",
        "Quarantine, redact, or remove the unsafe artifact from export surfaces.",
        False,
        ("artifact-safety-report.json", "safe-diagnostic-bundle.json"),
    ),
    "HATE-DQ-007": ErrorCatalogEntry(
        "HATE-DQ-007",
        "DQ",
        "risk_without_execution",
        "hard_dq",
        "High-risk changed path has no execution evidence.",
        "Risk coverage matrix found a high/critical risk without executable evidence.",
        "Add test evidence, contract evidence, mutation evidence, or manual review with owner.",
        "Assign risk owner and provide an executable oracle or accepted debt record.",
        False,
        ("risk-coverage-matrix.json", "manual-review-request.json"),
    ),
    "HATE-SEC-001": ErrorCatalogEntry(
        "HATE-SEC-001",
        "SEC",
        "secret_detected",
        "hard_dq",
        "Secret was detected in an artifact or summary candidate.",
        "Unsafe data must not be included in diagnostic bundles.",
        "Quarantine the artifact and update redaction rules.",
        "Rotate exposed credential if it may be real and attach security review evidence.",
        False,
        ("artifact-safety-report.json", "security-review-record.json"),
    ),
    "HATE-EXP-001": ErrorCatalogEntry(
        "HATE-EXP-001",
        "EXP",
        "optional_export_failed",
        "warning",
        "Optional external export failed.",
        "Connector/export failure is non-gating for local-first evidence.",
        "Check connector configuration and retry the dry-run.",
        "Keep local evidence intact and attach redacted connector diagnostics.",
        True,
        ("enterprise-control-report.json", "support-ops-report.json"),
    ),
    "HATE-SYS-001": ErrorCatalogEntry(
        "HATE-SYS-001",
        "SYS",
        "unexpected_internal_error",
        "error",
        "Unexpected internal error.",
        "Support needs a safe diagnostic bundle to triage.",
        "Generate a diagnostic bundle and attach version/profile summaries.",
        "Open a support issue with the safe diagnostic bundle.",
        True,
        ("support-ops-report.json", "safe-diagnostic-bundle.json"),
    ),
}

FINDING_CODE_TO_ERROR_CODE = {
    "schema_invalid": "HATE-SCH-001",
    "unsupported_schema_version": "HATE-SCH-002",
    "adapter_parse_failed": "HATE-ADP-001",
    "artifact_missing": "HATE-ART-001",
    "unsafe_artifact_blocked": "HATE-ART-003",
    "unsafe_log_field_redacted": "HATE-SEC-001",
    "raw_artifact_in_diagnostic_bundle": "HATE-ART-003",
    "secret_detected": "HATE-SEC-001",
    "risk_without_oracle": "HATE-DQ-007",
    "optional_export_failed": "HATE-EXP-001",
    "unexpected_internal_error": "HATE-SYS-001",
}


def lookup_error_code(error_code: str) -> ErrorCatalogEntry | None:
    """Look up a stable error catalog entry."""

    return ERROR_CATALOG.get(error_code)


def map_findings_to_error_records(findings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Map findings to safe, user-facing error records.

    Unknown error codes are findings with hold effect rather than pass.
    """

    records: list[dict[str, Any]] = []
    catalog_findings: list[dict[str, Any]] = []
    for index, finding in enumerate(findings):
        error_code = str(finding.get("error_code") or FINDING_CODE_TO_ERROR_CODE.get(str(finding.get("code")), ""))
        entry = lookup_error_code(error_code)
        if not entry:
            catalog_findings.append({
                "code": "unknown_error_code",
                "severity": "high",
                "readiness_effect": "hold",
                "message": f"Unknown or missing error code for finding {finding.get('code', index)}.",
                "sourceRef": _source_ref(finding, index),
            })
            continue
        if not entry.remediation or not entry.owner_action:
            catalog_findings.append({
                "code": "catalog_entry_missing_remediation",
                "severity": "high",
                "readiness_effect": "hold",
                "message": f"Catalog entry {entry.error_code} is missing remediation or owner action.",
                "sourceRef": _source_ref(finding, index),
            })
            continue
        records.append({
            "schema_version": "HATE/v1",
            "record_type": "support-error-record",
            "error_code": entry.error_code,
            "category": entry.category,
            "error_class": entry.error_class,
            "severity": entry.severity,
            "message": entry.user_message,
            "operator_message": entry.operator_message,
            "remediation": entry.remediation,
            "owner_action": entry.owner_action,
            "retryable": entry.retryable,
            "related_reports": list(entry.related_reports),
            "sourceRefs": [ref for ref in [finding.get("sourceRef")] if ref],
            "safe_for_summary": True,
        })
    return records, catalog_findings


def build_error_catalog_report(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Build support-ops compatible error catalog mapping report."""

    error_records, catalog_findings = map_findings_to_error_records(findings)
    return {
        "schema_version": "HATE/v1",
        "record_type": "support-error-catalog-report",
        "error_records": error_records,
        "findings": catalog_findings,
        "summary": {
            "known_error_count": len(error_records),
            "catalog_finding_count": len(catalog_findings),
            "readiness_effect": "hold" if catalog_findings else "pass",
        },
        "sourceRefs": sorted({ref for record in error_records for ref in record.get("sourceRefs", [])}),
    }


def _source_ref(finding: dict[str, Any], index: int) -> str:
    return str(finding.get("sourceRef") or f"findings/{index}")
