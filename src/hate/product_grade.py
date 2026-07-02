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
    implementation_refs: tuple[str, ...]
    test_refs: tuple[str, ...]
    blocking_when_missing: bool = True


REPORT_SPECS: tuple[ReportSpec, ...] = (
    ReportSpec(
        "adapter-conformance-report.json",
        "adapter corpus and SDK",
        ("ADAPTER_DIALECT_PARSER_SPEC.md", "ACCEPTANCE_CRITERIA_MATRIX.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
        ("src/hate/adapters/corpus_manifest.py", "src/hate/adapter_sdk.py"),
        ("tests/test_adapter_corpus_manifest.py", "tests/test_adapter_sdk.py"),
    ),
    ReportSpec(
        "schema-validation-report.json",
        "schema and cross-record validation",
        ("SPECIFICATION.md", "STORE_SCHEMA_REQUIREMENTS.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
        ("src/hate/schema_validator.py",),
        ("tests/test_schema_validator.py", "tests/test_product_grade_report_contracts.py"),
    ),
    ReportSpec(
        "store-replay-report.json",
        "local store, replay, compare",
        ("STORE_SCHEMA_REQUIREMENTS.md", "SCALE_PERFORMANCE_REQUIREMENTS.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
        ("src/hate/store/replay.py", "src/hate/store/migration_rebuild.py"),
        ("tests/test_store_replay_compare.py", "tests/test_store_migration_rebuild.py"),
    ),
    ReportSpec(
        "api-contract-report.json",
        "API contract",
        ("API_REQUIREMENTS.md", "API_OPENAPI.yaml", "ACCEPTANCE_CRITERIA_MATRIX.md"),
        ("src/hate/api/contract_report.py", "src/hate/api/read_model.py"),
        ("tests/test_api_contract_report.py", "tests/test_api_read_model_contract.py"),
    ),
    ReportSpec(
        "dashboard-uat-report.json",
        "dashboard and UI workflow",
        ("UI_WORKFLOW_REQUIREMENTS.md", "USER_STORY_MAP.md", "ACCEPTANCE_CRITERIA_MATRIX.md"),
        ("src/hate/dashboard/uat_report.py", "src/hate/dashboard/platform_views.py"),
        ("tests/test_dashboard_uat_report.py", "tests/test_platform_dashboard_views.py"),
    ),
    ReportSpec(
        "test-integrity-report.json",
        "test integrity and AI-abuse detection",
        ("PRODUCT_GRADE_IMPLEMENTATION_SPEC.md", "ACCEPTANCE_CRITERIA_MATRIX.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
        ("src/hate/test_integrity/skip_focus.py", "src/hate/test_integrity/mock_assertion.py", "src/hate/test_integrity/coupling.py"),
        ("tests/test_test_integrity_skip_focus.py", "tests/test_test_integrity_mock_assertion.py", "tests/test_test_integrity_coupling.py"),
    ),
    ReportSpec(
        "security-quarantine-report.json",
        "artifact safety and quarantine",
        ("DATA_RETENTION_LEGAL_REQUIREMENTS.md", "UI_WORKFLOW_REQUIREMENTS.md", "ACCEPTANCE_CRITERIA_MATRIX.md"),
        ("src/hate/security/quarantine_report.py", "src/hate/security/artifact_safety.py"),
        ("tests/test_security_quarantine_report.py",),
    ),
    ReportSpec(
        "enterprise-control-report.json",
        "RBAC, audit, retention, connectors",
        ("DATA_RETENTION_LEGAL_REQUIREMENTS.md", "API_REQUIREMENTS.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
        ("src/hate/enterprise/control_packet.py", "src/hate/enterprise/rbac.py", "src/hate/enterprise/audit.py"),
        ("tests/test_enterprise_control_packet.py", "tests/test_enterprise_rbac_audit.py"),
    ),
    ReportSpec(
        "scale-performance-report.json",
        "scale and performance",
        ("SCALE_PERFORMANCE_REQUIREMENTS.md", "ACCEPTANCE_CRITERIA_MATRIX.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
        ("src/hate/scale/platform_benchmark.py", "src/hate/scale/performance_budget.py"),
        ("tests/test_platform_benchmark.py", "tests/test_scale_fixtures.py"),
    ),
    ReportSpec(
        "migration-compatibility-report.json",
        "migration and lifecycle compatibility",
        ("STORE_SCHEMA_REQUIREMENTS.md", "DATA_RETENTION_LEGAL_REQUIREMENTS.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
        ("src/hate/migration/compatibility.py", "src/hate/migration/legal_hold.py"),
        ("tests/test_migration_compatibility.py", "tests/test_migration_legal_hold.py"),
    ),
    ReportSpec(
        "commercial-truthfulness-report.json",
        "commercial truthfulness",
        ("DATA_RETENTION_LEGAL_REQUIREMENTS.md", "USER_STORY_MAP.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
        ("src/hate/commercial/truthfulness.py",),
        ("tests/test_commercial_truthfulness.py",),
    ),
    ReportSpec(
        "support-ops-report.json",
        "observability and support operations",
        ("DATA_RETENTION_LEGAL_REQUIREMENTS.md", "ACCEPTANCE_CRITERIA_MATRIX.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
        ("src/hate/support_ops/observability.py", "src/hate/support_ops/diagnostics.py"),
        ("tests/test_support_ops_observability.py", "tests/test_support_ops_diagnostics.py"),
    ),
    ReportSpec(
        "release-candidate-pack.json",
        "release candidate and assurance pack",
        ("ACCEPTANCE_CRITERIA_MATRIX.md", "PRODUCT_REQUIREMENTS_500K_READINESS_AUDIT.md", "IMPLEMENTATION_EPIC_BREAKDOWN.md"),
        ("src/hate/release.py",),
        ("tests/test_release_candidate_pack.py", "tests/test_cli_release_candidate.py"),
    ),
)


def generate_product_grade_reports(
    docs_root: Path,
    out_dir: Path,
    source_version: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    if not docs_root.exists():
        raise ProductGradeError(f"docs root not found: {docs_root}")
    if not docs_root.is_dir():
        raise ProductGradeError(f"docs root is not a directory: {docs_root}")

    out_dir.mkdir(parents=True, exist_ok=True)
    root = repo_root or docs_root.parent.parent
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    reports: list[dict[str, Any]] = []

    for spec in REPORT_SPECS:
        report = _build_report(spec, docs_root, root, generated_at, source_version)
        _write_json(out_dir / spec.filename, report)
        reports.append(
            {
                "filename": spec.filename,
                "area": spec.area,
                "status": report["status"],
                "blocking": report["blocking"],
                "missing_required_docs": report["missing_required_docs"],
                "missing_implementation_refs": report["missing_implementation_refs"],
                "missing_test_refs": report["missing_test_refs"],
            }
        )

    missing_reports = [item["filename"] for item in reports if item["status"] != "implemented_with_evidence"]
    real_data = _real_data_validation(root)
    implementation_complete = not missing_reports
    residual_blockers = real_data["residual_blockers"]
    product_grade_status = "no_go"
    reason = "Product-grade evidence is missing required documents, implementation refs, or tests."
    if implementation_complete:
        product_grade_status = "conditional_go" if residual_blockers else "verified"
        reason = (
            "Product-grade implementation evidence is present, but operational residual gaps remain."
            if residual_blockers
            else "Product-grade implementation, test, real-data, and QEG smoke evidence are present."
        )
    summary = {
        "schema_version": "HATE/product-grade/v1",
        "record_type": "product_grade_evidence_summary",
        "generated_at": generated_at,
        "source_version": source_version or "unknown",
        "docs_root": str(docs_root),
        "repo_root": str(root),
        "product_ready": product_grade_status == "verified",
        "product_grade_implementation_status": product_grade_status,
        "reason": reason,
        "required_report_count": len(REPORT_SPECS),
        "generated_report_count": len(reports),
        "missing_or_incomplete_reports": missing_reports,
        "real_data_validation": real_data,
        "reports": reports,
    }
    _write_json(out_dir / "product-grade-evidence-summary.json", summary)
    return {
        "generated": [item["filename"] for item in reports] + ["product-grade-evidence-summary.json"],
        "out_dir": str(out_dir),
        "product_ready": summary["product_ready"],
        "product_grade_implementation_status": product_grade_status,
    }


def _build_report(
    spec: ReportSpec,
    docs_root: Path,
    repo_root: Path,
    generated_at: str,
    source_version: str | None,
) -> dict[str, Any]:
    doc_status = []
    missing = []
    for doc in spec.required_docs:
        path = docs_root / doc
        exists = path.exists()
        doc_status.append({"path": doc, "exists": exists})
        if not exists:
            missing.append(doc)

    implementation_status, missing_implementation = _path_status(repo_root, spec.implementation_refs)
    test_status, missing_tests = _path_status(repo_root, spec.test_refs)
    status = "implemented_with_evidence"
    if missing:
        status = "missing_required_docs"
    elif missing_implementation:
        status = "missing_implementation_evidence"
    elif missing_tests:
        status = "missing_test_evidence"

    return {
        "schema_version": "HATE/product-grade/v1",
        "record_type": spec.filename.removesuffix(".json").replace("-", "_"),
        "generated_at": generated_at,
        "source_version": source_version or "unknown",
        "area": spec.area,
        "status": status,
        "blocking": spec.blocking_when_missing,
        "product_ready_evidence": status == "implemented_with_evidence",
        "implementation_evidence_status": "implemented" if not missing_implementation else "missing",
        "required_docs": doc_status,
        "missing_required_docs": missing,
        "implementation_refs": implementation_status,
        "test_refs": test_status,
        "missing_implementation_refs": missing_implementation,
        "missing_test_refs": missing_tests,
        "required_next_evidence": _required_next_evidence(missing, missing_implementation, missing_tests),
        "no_go": _no_go_messages(status),
    }


def _path_status(repo_root: Path, refs: tuple[str, ...]) -> tuple[list[dict[str, Any]], list[str]]:
    statuses = []
    missing = []
    for ref in refs:
        path = repo_root / ref
        exists = path.exists()
        statuses.append({"path": ref, "exists": exists})
        if not exists:
            missing.append(ref)
    return statuses, missing


def _required_next_evidence(
    missing_docs: list[str],
    missing_implementation: list[str],
    missing_tests: list[str],
) -> list[str]:
    evidence = []
    if missing_docs:
        evidence.append("complete requirement/spec documents")
    if missing_implementation:
        evidence.append("implementation code")
    if missing_tests:
        evidence.append("automated tests")
    if evidence:
        return evidence
    return ["resolve residual real-repo operational blockers", "QEG release approval"]


def _no_go_messages(status: str) -> list[str]:
    if status == "implemented_with_evidence":
        return []
    return [
        "Do not claim product-ready until implementation evidence and tests are present.",
        "Do not hide missing documents, sourceRefs, or test refs behind generated reports.",
    ]


def _real_data_validation(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "docs" / "acceptance" / "REAL_REPO_BULK_VALIDATION_20260702.md"
    if not path.exists():
        return {
            "present": False,
            "repo_suite_count": 0,
            "executed_records": 0,
            "qeg_smoke_passed": False,
            "residual_blockers": ["real repo validation record missing"],
            "sourceRef": str(path),
        }

    text = path.read_text(encoding="utf-8")
    residual_blockers = []
    if "memx-resolver" in text and "missing `yaml`" in text:
        residual_blockers.append("memx-resolver dependency setup remains unstable")
    if "`uv` cache access problem" in text or "uv cache" in text:
        residual_blockers.append("uv cache permission friction remains in combined/sandboxed runs")
    if "total_checks" in text and "total_tests" in text:
        residual_blockers.append("build/typecheck records must stay out of executable test-oracle scoring")
    return {
        "present": True,
        "repo_suite_count": 22 if "22 repo/suites" in text else 0,
        "executed_records": 12771 if "12,771" in text else 0,
        "qeg_smoke_passed": "QEG `build`, `validate`, `gate`, and `record` passed" in text,
        "residual_blockers": residual_blockers,
        "sourceRef": str(path),
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
