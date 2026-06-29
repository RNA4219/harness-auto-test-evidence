from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ProductGradeError(Exception):
    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class ReportSpec:
    filename: str
    area: str
    required_docs: tuple[str, ...]
    blocking_when_missing: bool = True


REPORT_SPECS: tuple[ReportSpec, ...] = (
    ReportSpec(
        "adapter-conformance-report.json",
        "adapter corpus and SDK",
        ("ADAPTER_DIALECT_PARSER_SPEC.md", "ACCEPTANCE_CRITERIA_MATRIX.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
    ),
    ReportSpec(
        "schema-validation-report.json",
        "schema and cross-record validation",
        ("SPECIFICATION.md", "STORE_SCHEMA_REQUIREMENTS.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
    ),
    ReportSpec(
        "store-replay-report.json",
        "local store, replay, compare",
        ("STORE_SCHEMA_REQUIREMENTS.md", "SCALE_PERFORMANCE_REQUIREMENTS.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
    ),
    ReportSpec(
        "api-contract-report.json",
        "API contract",
        ("API_REQUIREMENTS.md", "API_OPENAPI.yaml", "ACCEPTANCE_CRITERIA_MATRIX.md"),
    ),
    ReportSpec(
        "dashboard-uat-report.json",
        "dashboard and UI workflow",
        ("UI_WORKFLOW_REQUIREMENTS.md", "USER_STORY_MAP.md", "ACCEPTANCE_CRITERIA_MATRIX.md"),
    ),
    ReportSpec(
        "test-integrity-report.json",
        "test integrity and AI-abuse detection",
        ("PRODUCT_GRADE_IMPLEMENTATION_SPEC.md", "ACCEPTANCE_CRITERIA_MATRIX.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
    ),
    ReportSpec(
        "security-quarantine-report.json",
        "artifact safety and quarantine",
        ("DATA_RETENTION_LEGAL_REQUIREMENTS.md", "UI_WORKFLOW_REQUIREMENTS.md", "ACCEPTANCE_CRITERIA_MATRIX.md"),
    ),
    ReportSpec(
        "enterprise-control-report.json",
        "RBAC, audit, retention, connectors",
        ("DATA_RETENTION_LEGAL_REQUIREMENTS.md", "API_REQUIREMENTS.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
    ),
    ReportSpec(
        "scale-performance-report.json",
        "scale and performance",
        ("SCALE_PERFORMANCE_REQUIREMENTS.md", "ACCEPTANCE_CRITERIA_MATRIX.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
    ),
    ReportSpec(
        "migration-compatibility-report.json",
        "migration and lifecycle compatibility",
        ("STORE_SCHEMA_REQUIREMENTS.md", "DATA_RETENTION_LEGAL_REQUIREMENTS.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
    ),
    ReportSpec(
        "commercial-truthfulness-report.json",
        "commercial truthfulness",
        ("DATA_RETENTION_LEGAL_REQUIREMENTS.md", "USER_STORY_MAP.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
    ),
    ReportSpec(
        "support-ops-report.json",
        "observability and support operations",
        ("DATA_RETENTION_LEGAL_REQUIREMENTS.md", "ACCEPTANCE_CRITERIA_MATRIX.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
    ),
    ReportSpec(
        "release-candidate-pack.json",
        "release candidate and assurance pack",
        ("ACCEPTANCE_CRITERIA_MATRIX.md", "PRODUCT_REQUIREMENTS_500K_READINESS_AUDIT.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
    ),
)


def generate_product_grade_reports(docs_root: Path, out_dir: Path, source_version: str | None = None) -> dict[str, Any]:
    if not docs_root.exists():
        raise ProductGradeError(f"docs root not found: {docs_root}")
    if not docs_root.is_dir():
        raise ProductGradeError(f"docs root is not a directory: {docs_root}")

    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    reports: list[dict[str, Any]] = []

    for spec in REPORT_SPECS:
        report = _build_report(spec, docs_root, generated_at, source_version)
        _write_json(out_dir / spec.filename, report)
        reports.append(
            {
                "filename": spec.filename,
                "area": spec.area,
                "status": report["status"],
                "blocking": report["blocking"],
                "missing_required_docs": report["missing_required_docs"],
            }
        )

    missing_reports = [item["filename"] for item in reports if item["status"] != "specified"]
    summary = {
        "schema_version": "HATE/product-grade/v1",
        "record_type": "product_grade_evidence_summary",
        "generated_at": generated_at,
        "source_version": source_version or "unknown",
        "docs_root": str(docs_root),
        "product_ready": False,
        "product_grade_implementation_status": "no_go",
        "reason": "Product-grade evidence reports are generated from requirement/spec documents, but implementation evidence is not complete.",
        "required_report_count": len(REPORT_SPECS),
        "generated_report_count": len(reports),
        "missing_or_incomplete_reports": missing_reports,
        "reports": reports,
    }
    _write_json(out_dir / "product-grade-evidence-summary.json", summary)
    return {
        "generated": [item["filename"] for item in reports] + ["product-grade-evidence-summary.json"],
        "out_dir": str(out_dir),
        "product_ready": False,
        "product_grade_implementation_status": "no_go",
    }


def _build_report(spec: ReportSpec, docs_root: Path, generated_at: str, source_version: str | None) -> dict[str, Any]:
    doc_status = []
    missing = []
    for doc in spec.required_docs:
        path = docs_root / doc
        exists = path.exists()
        doc_status.append({"path": doc, "exists": exists})
        if not exists:
            missing.append(doc)

    status = "specified" if not missing else "missing_required_docs"
    return {
        "schema_version": "HATE/product-grade/v1",
        "record_type": spec.filename.removesuffix(".json").replace("-", "_"),
        "generated_at": generated_at,
        "source_version": source_version or "unknown",
        "area": spec.area,
        "status": status,
        "blocking": spec.blocking_when_missing,
        "product_ready_evidence": False,
        "implementation_evidence_status": "not_implemented",
        "required_docs": doc_status,
        "missing_required_docs": missing,
        "required_next_evidence": [
            "implementation code",
            "positive fixtures",
            "negative fixtures",
            "automated tests",
            "CI evidence",
            "UAT or manual-bb evidence",
        ],
        "no_go": [
            "Do not treat this generated report as implementation completion.",
            "Do not claim product-ready until implementation evidence and UAT pass.",
        ],
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
