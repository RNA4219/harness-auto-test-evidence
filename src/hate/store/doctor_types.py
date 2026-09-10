"""診断結果の公開型とレポート集計。既存doctorのimport経路も維持する。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .report_serialization import relative_diagnostics, report_data, report_hash


class DiagnosisSeverity(str, Enum):  # noqa: UP042 - 既存のstr(Enum)表現を維持する。
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
    run_id: str | None = None
    _store_root: Path | None = field(default=None, repr=False, compare=False, kw_only=True)

    def to_dict(self, *, include_observation: bool = False) -> dict[str, Any]:
        """観測時刻を任意で含め、辞書キーを再帰的に整列した証跡を返す。"""
        data = {
            "schema_version": self.schema_version,
            "record_type": self.record_type,
            "bundle_id": self.bundle_id,
            "run_id": self.run_id,
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
        if self._store_root is not None:
            data["findings"] = relative_diagnostics([item.to_dict() for item in self.findings], self._store_root)
        return report_data(data, observation_field="diagnosed_at", include_observation=include_observation)

    def compute_hash(self) -> str:
        """Compute deterministic hash of doctor report."""
        return report_hash(self.to_dict(), hash_field="diagnosis_hash", observation_field="diagnosed_at")


@dataclass
class DoctorError(Exception):
    """Error during diagnosis operation."""
    message: str
    bundle_id: str | None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        return f"DoctorError: {self.message}"


def build_report(
    bundle_id: str | None,
    scope: str,
    findings: list[DiagnosisFinding],
    summary: str,
    *,
    run_id: str | None = None,
    store_root: Path | None = None,
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
        diagnosed_at=datetime.now(UTC).isoformat(),
        summary=summary,
        run_id=run_id,
        _store_root=store_root.resolve() if store_root is not None else None,
    )

    report.diagnosis_hash = report.compute_hash()

    return report
