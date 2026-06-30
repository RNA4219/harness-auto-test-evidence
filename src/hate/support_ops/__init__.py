"""Support operations reports for observability, diagnostics, and incidents."""

from hate.support_ops.diagnostics import (
    DiagnosticBundleResult,
    build_diagnostic_bundle,
    build_diagnostics_report,
    build_support_diagnostics_gap_report,
    evaluate_support_diagnostics_fixture,
)
from hate.support_ops.error_catalog import (
    ErrorCatalogEntry,
    build_error_catalog_report,
    lookup_error_code,
    map_findings_to_error_records,
)
from hate.support_ops.observability import (
    ObservabilityReport,
    build_observability_gap_report,
    build_support_ops_report,
    evaluate_observability_fixture,
    validate_alerts,
    validate_logs,
    validate_metrics,
    validate_spans,
)

__all__ = [
    "DiagnosticBundleResult",
    "ErrorCatalogEntry",
    "ObservabilityReport",
    "build_diagnostic_bundle",
    "build_diagnostics_report",
    "build_error_catalog_report",
    "build_observability_gap_report",
    "build_support_diagnostics_gap_report",
    "build_support_ops_report",
    "evaluate_observability_fixture",
    "evaluate_support_diagnostics_fixture",
    "lookup_error_code",
    "map_findings_to_error_records",
    "validate_alerts",
    "validate_logs",
    "validate_metrics",
    "validate_spans",
]
