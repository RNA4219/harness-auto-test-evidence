"""Corruption Doctor Module for HATE Local Store.

Diagnoses corruption and data quality issues in store bundles.
Identifies hard-DQ (blocking) and soft-DQ (non-blocking) findings.

Key invariants:
- Corrupt manifest is hard-DQ
- Missing artifact is hard-DQ
- Hash mismatch is hard-DQ
- Legal hold lost is hard-DQ
- Doctor findings are comprehensive and actionable

No-Go conditions:
- Doctor silently ignores corruption
- Hard-DQ is downgraded to warning
- Corruption diagnostics are incomplete
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .atomic_write import compute_file_hash, compute_json_hash_for_write
from .indexes import HardDQFinding, IndexEntry
from .local_store import LocalStore, StoreManifest, LocalStoreError


class DiagnosisSeverity(str, Enum):
    """Severity level for diagnosis findings."""
    HARD_DQ = "hard_dq"  # Blocking - must be fixed
    SOFT_DQ = "soft_dq"  # Non-blocking - should be fixed
    WARNING = "warning"  # Advisory - optional fix
    INFO = "info"  # Informational - no action needed


@dataclass
class DiagnosisFinding:
    """A single diagnosis finding."""
    finding_id: str  # Non-default first
    severity: DiagnosisSeverity  # Non-default first
    category: str  # Non-default first: "manifest", "artifact", "index", "legal_hold", "schema"
    message: str  # Non-default first
    bundle_id: str | None = None
    artifact_id: str | None = None
    path: str | None = None
    expected: Any | None = None
    actual: Any | None = None
    remediation: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "finding_id": self.finding_id,
            "bundle_id": self.bundle_id,
            "artifact_id": self.artifact_id,
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
            "path": self.path,
            "expected": self.expected,
            "actual": self.actual,
            "remediation": self.remediation,
            "diagnostics": self.diagnostics,
        }


@dataclass
class DoctorReport:
    """Comprehensive corruption diagnosis report."""
    diagnosis_scope: str  # Non-default first: "single_bundle", "run", "full_store"
    bundle_id: str | None = None
    schema_version: str = "HATE/v1"
    record_type: str = "store_doctor_report"
    total_findings: int = 0
    hard_dq_count: int = 0
    soft_dq_count: int = 0
    warning_count: int = 0
    healthy: bool = True  # True if no hard_dq findings
    diagnosis_hash: str = ""
    findings: list[DiagnosisFinding] = field(default_factory=list)
    diagnosed_at: str = ""
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with sorted keys for byte-stability."""
        return {
            "schema_version": self.schema_version,
            "record_type": self.record_type,
            "bundle_id": self.bundle_id,
            "diagnosis_scope": self.diagnosis_scope,
            "total_findings": self.total_findings,
            "hard_dq_count": self.hard_dq_count,
            "soft_dq_count": self.soft_dq_count,
            "warning_count": self.warning_count,
            "healthy": self.healthy,
            "diagnosis_hash": self.diagnosis_hash,
            "findings": [f.to_dict() for f in self.findings],
            "diagnosed_at": self.diagnosed_at,
            "summary": self.summary,
        }

    def compute_hash(self) -> str:
        """Compute deterministic hash of doctor report."""
        return compute_json_hash_for_write(self.to_dict())


@dataclass
class DoctorError(Exception):
    """Error during diagnosis operation."""
    message: str
    bundle_id: str | None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        return f"DoctorError: {self.message}"


def diagnose_bundle(store: LocalStore, bundle_id: str) -> DoctorReport:
    """Diagnose a single bundle for corruption and data quality issues.

    Args:
        store: Local store instance
        bundle_id: Bundle to diagnose

    Returns:
        Comprehensive diagnosis report
    """
    findings: list[DiagnosisFinding] = []
    finding_counter = 0

    # Phase 1: Check manifest
    manifest_findings, manifest = _diagnose_manifest(store, bundle_id)
    for f in manifest_findings:
        f.finding_id = f"{bundle_id}_F{finding_counter:03d}"
        finding_counter += 1
        findings.append(f)

    # If manifest is corrupt, stop further diagnosis
    if any(f.severity == DiagnosisSeverity.HARD_DQ and f.category == "manifest" for f in findings):
        return _build_report(
            bundle_id=bundle_id,
            scope="single_bundle",
            findings=findings,
            summary="Bundle manifest is corrupt. Cannot continue diagnosis.",
        )

    # Phase 2: Check artifacts
    if manifest:
        artifact_findings = _diagnose_artifacts(store, bundle_id, manifest)
        for f in artifact_findings:
            f.finding_id = f"{bundle_id}_F{finding_counter:03d}"
            finding_counter += 1
            findings.append(f)

    # Phase 3: Check legal hold
    if manifest:
        legal_hold_findings = _diagnose_legal_hold(bundle_id, manifest)
        for f in legal_hold_findings:
            f.finding_id = f"{bundle_id}_F{finding_counter:03d}"
            finding_counter += 1
            findings.append(f)

    # Phase 4: Check schema compatibility
    if manifest:
        schema_findings = _diagnose_schema(bundle_id, manifest)
        for f in schema_findings:
            f.finding_id = f"{bundle_id}_F{finding_counter:03d}"
            finding_counter += 1
            findings.append(f)

    # Build summary
    hard_dqs = [f for f in findings if f.severity == DiagnosisSeverity.HARD_DQ]
    if hard_dqs:
        summary = f"Bundle has {len(hard_dqs)} hard-DQ findings requiring immediate fix."
    else:
        summary = "Bundle is healthy (no hard-DQ findings)."

    return _build_report(
        bundle_id=bundle_id,
        scope="single_bundle",
        findings=findings,
        summary=summary,
    )


def diagnose_run(store: LocalStore, run_id: str) -> DoctorReport:
    """Diagnose all bundles in a run.

    Args:
        store: Local store instance
        run_id: Run ID to diagnose

    Returns:
        Comprehensive diagnosis report for the run
    """
    findings: list[DiagnosisFinding] = []
    finding_counter = 0

    bundle_ids = store.list_bundles_for_run(run_id)

    for bundle_id in bundle_ids:
        bundle_report = diagnose_bundle(store, bundle_id)
        for f in bundle_report.findings:
            f.finding_id = f"{run_id}_F{finding_counter:03d}"
            finding_counter += 1
            findings.append(f)

    hard_dqs = [f for f in findings if f.severity == DiagnosisSeverity.HARD_DQ]
    summary = f"Run {run_id} has {len(bundle_ids)} bundles, {len(hard_dqs)} hard-DQ findings."

    return _build_report(
        bundle_id=None,
        scope="run",
        findings=findings,
        summary=summary,
    )


def diagnose_full_store(store: LocalStore) -> DoctorReport:
    """Diagnose entire store for corruption.

    Args:
        store: Local store instance

    Returns:
        Comprehensive diagnosis report for the store
    """
    findings: list[DiagnosisFinding] = []
    finding_counter = 0

    # Get all bundles from index
    bundle_ids = store.list_all_bundles()

    for bundle_id in bundle_ids:
        bundle_report = diagnose_bundle(store, bundle_id)
        for f in bundle_report.findings:
            f.finding_id = f"store_F{finding_counter:03d}"
            finding_counter += 1
            findings.append(f)

    # Check index consistency
    index_findings = _diagnose_indexes(store)
    for f in index_findings:
        f.finding_id = f"store_F{finding_counter:03d}"
        finding_counter += 1
        findings.append(f)

    hard_dqs = [f for f in findings if f.severity == DiagnosisSeverity.HARD_DQ]
    summary = f"Store has {len(bundle_ids)} bundles, {len(hard_dqs)} hard-DQ findings."

    return _build_report(
        bundle_id=None,
        scope="full_store",
        findings=findings,
        summary=summary,
    )


def _diagnose_manifest(
    store: LocalStore, bundle_id: str
) -> tuple[list[DiagnosisFinding], StoreManifest | None]:
    """Diagnose manifest for corruption."""
    findings: list[DiagnosisFinding] = []
    manifest = None

    # First try to read manifest - this handles path resolution
    try:
        manifest = store.read_manifest_by_bundle(bundle_id)
    except LocalStoreError as e:
        # If read fails, check various error types
        error_str = str(e)
        if "not found" in error_str.lower() or "missing" in error_str.lower():
            findings.append(DiagnosisFinding(
                finding_id="",  # Will be assigned later
                severity=DiagnosisSeverity.HARD_DQ,
                category="manifest",
                message="Manifest file missing or bundle not found",
                bundle_id=bundle_id,
                artifact_id=None,
                path=None,
                expected="Valid bundle with manifest",
                actual=f"Error: {e}",
                remediation="Re-import bundle from source or restore from backup",
                diagnostics={"error": str(e)},
            ))
        else:
            findings.append(DiagnosisFinding(
                finding_id="",  # Will be assigned later
                severity=DiagnosisSeverity.HARD_DQ,
                category="manifest",
                message="Manifest file corrupt or unreadable",
                bundle_id=bundle_id,
                artifact_id=None,
                path=None,
                expected="Valid JSON manifest",
                actual=f"Parse error: {e}",
                remediation="Re-import bundle from source",
                diagnostics={"error": str(e)},
            ))
        return findings, None

    # Check manifest completed flag
    if not manifest.completed:
        findings.append(DiagnosisFinding(
            finding_id="",  # Will be assigned later
            severity=DiagnosisSeverity.HARD_DQ,
            category="manifest",
            message="Bundle not marked as completed",
            bundle_id=bundle_id,
            artifact_id=None,
            path=None,
            expected="completed: true",
            actual="completed: false",
            remediation="Complete bundle import or quarantine incomplete bundle",
            diagnostics={},
        ))

    # Check manifest has required fields
    required_fields = ["bundle_id", "run_id", "created_at", "artifact_ids"]
    for field in required_fields:
        if not hasattr(manifest, field) or getattr(manifest, field) is None:
            findings.append(DiagnosisFinding(
                finding_id="",  # Will be assigned later
                severity=DiagnosisSeverity.HARD_DQ,
                category="manifest",
                message=f"Manifest missing required field: {field}",
                bundle_id=bundle_id,
                artifact_id=None,
                path=None,
                expected=f"Field '{field}' present",
                actual="Field missing or null",
                remediation="Re-import bundle with complete metadata",
                diagnostics={"missing_field": field},
            ))

    return findings, manifest


def _diagnose_artifacts(
    store: LocalStore, bundle_id: str, manifest: StoreManifest
) -> list[DiagnosisFinding]:
    """Diagnose artifacts for corruption."""
    findings: list[DiagnosisFinding] = []

    # Get run_id from manifest to construct correct path
    run_id = manifest.run_id

    for artifact_id in manifest.artifact_ids:
        # Correct path: runs/{run_id}/{bundle_id}/{artifact_id}.json
        artifact_path = store.store_root / "runs" / run_id / bundle_id / f"{artifact_id}.json"

        # Check artifact exists
        if not artifact_path.exists():
            findings.append(DiagnosisFinding(
                finding_id="",  # Will be assigned later
                severity=DiagnosisSeverity.HARD_DQ,
                category="artifact",
                message=f"Artifact file missing: {artifact_id}",
                bundle_id=bundle_id,
                artifact_id=artifact_id,
                path=str(artifact_path),
                expected=f"{artifact_id}.json file",
                actual="File not found",
                remediation="Re-import artifact from source bundle",
                diagnostics={},
            ))
            continue

        # Check artifact hash matches manifest
        expected_hash = manifest.content_hashes.get(artifact_id)
        if expected_hash:
            try:
                actual_hash = compute_file_hash(artifact_path)
                if actual_hash != expected_hash:
                    findings.append(DiagnosisFinding(
                        finding_id="",  # Will be assigned later
                        severity=DiagnosisSeverity.HARD_DQ,
                        category="artifact",
                        message=f"Artifact hash mismatch: {artifact_id}",
                        bundle_id=bundle_id,
                        artifact_id=artifact_id,
                        path=str(artifact_path),
                        expected=expected_hash,
                        actual=actual_hash,
                        remediation="Re-import artifact or restore from backup",
                        diagnostics={"expected_hash": expected_hash, "actual_hash": actual_hash},
                    ))
            except Exception as e:
                findings.append(DiagnosisFinding(
                    finding_id="",  # Will be assigned later
                    severity=DiagnosisSeverity.HARD_DQ,
                    category="artifact",
                    message=f"Artifact file unreadable: {artifact_id}",
                    bundle_id=bundle_id,
                    artifact_id=artifact_id,
                    path=str(artifact_path),
                    expected="Readable artifact file",
                    actual=f"Read error: {e}",
                    remediation="Re-import artifact from source",
                    diagnostics={"error": str(e)},
                ))

    return findings


def _diagnose_legal_hold(bundle_id: str, manifest: StoreManifest) -> list[DiagnosisFinding]:
    """Diagnose legal hold metadata."""
    findings: list[DiagnosisFinding] = []

    legal_hold = manifest.legal_hold

    if not legal_hold:
        findings.append(DiagnosisFinding(
            finding_id="",  # Will be assigned later
            severity=DiagnosisSeverity.HARD_DQ,
            category="legal_hold",
            message="Legal hold metadata missing",
            bundle_id=bundle_id,
            artifact_id=None,
            path=None,
            expected="legal_hold object with required fields",
            actual="legal_hold is null or missing",
            remediation="Add legal hold metadata before proceeding",
            diagnostics={},
        ))
        return findings

    # Check required fields
    required_fields = {"status", "reason", "held_since"}
    for field in required_fields:
        if field not in legal_hold:
            findings.append(DiagnosisFinding(
                finding_id="",  # Will be assigned later
                severity=DiagnosisSeverity.HARD_DQ,
                category="legal_hold",
                message=f"Legal hold missing required field: {field}",
                bundle_id=bundle_id,
                artifact_id=None,
                path=None,
                expected=f"Field '{field}' in legal_hold",
                actual="Field missing",
                remediation="Add missing legal hold field",
                diagnostics={"missing_field": field},
            ))

    return findings


def _diagnose_schema(bundle_id: str, manifest: StoreManifest) -> list[DiagnosisFinding]:
    """Diagnose schema compatibility."""
    findings: list[DiagnosisFinding] = []

    schema_versions = manifest.schema_versions
    bundle_schema = schema_versions.get("bundle", "unknown")

    supported_versions = {"HATE/v1"}
    migration_required_versions = {"HATE/v0.9", "HATE/v0.8"}

    if bundle_schema in supported_versions:
        # Schema is compatible
        pass
    elif bundle_schema in migration_required_versions:
        findings.append(DiagnosisFinding(
            finding_id="",  # Will be assigned later
            severity=DiagnosisSeverity.SOFT_DQ,
            category="schema",
            message=f"Schema version requires migration: {bundle_schema}",
            bundle_id=bundle_id,
            artifact_id=None,
            path=None,
            expected="HATE/v1",
            actual=bundle_schema,
            remediation="Run schema migration before replay",
            diagnostics={"current_schema": bundle_schema},
        ))
    else:
        findings.append(DiagnosisFinding(
            finding_id="",  # Will be assigned later
            severity=DiagnosisSeverity.SOFT_DQ,
            category="schema",
            message=f"Unknown schema version: {bundle_schema}",
            bundle_id=bundle_id,
            artifact_id=None,
            path=None,
            expected="Known schema version",
            actual=bundle_schema,
            remediation="Verify schema compatibility or quarantine bundle",
            diagnostics={"current_schema": bundle_schema},
        ))

    return findings


def _diagnose_indexes(store: LocalStore) -> list[DiagnosisFinding]:
    """Diagnose index consistency."""
    findings: list[DiagnosisFinding] = []

    # Check that all indexed bundles exist in store
    bundle_ids_from_index = store.list_all_bundles()

    for bundle_id in bundle_ids_from_index:
        bundle_path = store.store_root / bundle_id
        if not bundle_path.exists():
            findings.append(DiagnosisFinding(
                finding_id="",  # Will be assigned later
                severity=DiagnosisSeverity.HARD_DQ,
                category="index",
                message=f"Index references missing bundle directory: {bundle_id}",
                bundle_id=bundle_id,
                artifact_id=None,
                path=str(bundle_path),
                expected="Bundle directory exists",
                actual="Directory not found",
                remediation="Remove stale index entry or restore bundle",
                diagnostics={},
            ))

    # Check that all store bundles are indexed
    for bundle_dir in store.store_root.iterdir():
        if bundle_dir.is_dir() and bundle_dir.name not in ["indexes", "quarantine"]:
            if bundle_dir.name not in bundle_ids_from_index:
                findings.append(DiagnosisFinding(
                    finding_id="",  # Will be assigned later
                    severity=DiagnosisSeverity.SOFT_DQ,
                    category="index",
                    message=f"Bundle not indexed: {bundle_dir.name}",
                    bundle_id=bundle_dir.name,
                    artifact_id=None,
                    path=str(bundle_dir),
                    expected="Bundle in index",
                    actual="Bundle not in index",
                    remediation="Rebuild index or remove orphaned bundle",
                    diagnostics={},
                ))

    return findings


def _build_report(
    bundle_id: str | None,
    scope: str,
    findings: list[DiagnosisFinding],
    summary: str,
) -> DoctorReport:
    """Build doctor report from findings."""
    hard_dq_count = sum(1 for f in findings if f.severity == DiagnosisSeverity.HARD_DQ)
    soft_dq_count = sum(1 for f in findings if f.severity == DiagnosisSeverity.SOFT_DQ)
    warning_count = sum(1 for f in findings if f.severity == DiagnosisSeverity.WARNING)

    report = DoctorReport(
        bundle_id=bundle_id,
        diagnosis_scope=scope,
        total_findings=len(findings),
        hard_dq_count=hard_dq_count,
        soft_dq_count=soft_dq_count,
        warning_count=warning_count,
        healthy=hard_dq_count == 0,
        diagnosis_hash="",  # Will be computed after
        findings=findings,
        diagnosed_at=datetime.now(timezone.utc).isoformat(),
        summary=summary,
    )

    report.diagnosis_hash = report.compute_hash()

    return report