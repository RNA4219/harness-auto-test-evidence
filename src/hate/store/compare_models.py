"""比較結果の公開データ型。compareからのimport経路も維持する。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .report_serialization import report_data, report_hash


class ComparisonResult(str, Enum):  # noqa: UP042 - 既存のstr(Enum)表現を維持する。
    """Comparison result classification."""
    IMPROVEMENT = "improvement"
    REGRESSION = "regression"
    NO_CHANGE = "no_change"
    INCOMPARABLE = "incomparable"  # Cannot compare (missing baseline, different schema)


@dataclass
class ArtifactDiff:
    """Difference between two artifact versions."""
    artifact_id: str
    baseline_hash: str | None
    current_hash: str | None
    result: ComparisonResult
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "artifact_id": self.artifact_id,
            "baseline_hash": self.baseline_hash,
            "current_hash": self.current_hash,
            "result": self.result.value,
            "details": self.details,
        }


@dataclass
class ComparisonReport:
    """Byte-stable comparison report."""
    bundle_id: str  # Non-default first
    run_id: str  # Non-default first
    schema_version: str = "HATE/v1"
    record_type: str = "store_comparison_report"
    baseline_bundle_id: str | None = None
    baseline_selection_method: str = ""
    is_filename_sort_baseline: bool = False  # True if baseline selected by filename (invalid)
    comparison_result: ComparisonResult = ComparisonResult.NO_CHANGE
    improvements: int = 0
    regressions: int = 0
    no_changes: int = 0
    artifacts_compared: int = 0
    artifacts_missing_in_baseline: int = 0
    artifacts_missing_in_current: int = 0
    comparison_hash: str = ""  # Deterministic hash of comparison content
    artifact_diffs: list[ArtifactDiff] = field(default_factory=list)
    compared_at: str = ""
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    baseline_run_id: str = ""

    def to_dict(self, *, include_observation: bool = False) -> dict[str, Any]:
        """Convert to dict with sorted keys for byte-stability."""
        data = {
            "schema_version": self.schema_version,
            "record_type": self.record_type,
            "bundle_id": self.bundle_id,
            "run_id": self.run_id,
            "baseline_bundle_id": self.baseline_bundle_id,
            "baseline_run_id": self.baseline_run_id,
            "baseline_selection_method": self.baseline_selection_method,
            "is_filename_sort_baseline": self.is_filename_sort_baseline,
            "comparison_result": self.comparison_result.value,
            "improvements": self.improvements,
            "regressions": self.regressions,
            "no_changes": self.no_changes,
            "artifacts_compared": self.artifacts_compared,
            "artifacts_missing_in_baseline": self.artifacts_missing_in_baseline,
            "artifacts_missing_in_current": self.artifacts_missing_in_current,
            "comparison_hash": self.comparison_hash,
            "artifact_diffs": [d.to_dict() for d in self.artifact_diffs],
            "compared_at": self.compared_at,
            "diagnostics": self.diagnostics,
        }
        return report_data(data, observation_field="compared_at", include_observation=include_observation)

    def compute_hash(self) -> str:
        """Compute deterministic hash of comparison report."""
        return report_hash(self.to_dict(), hash_field="comparison_hash", observation_field="compared_at")


@dataclass
class CompareError(Exception):
    """Error during comparison operation."""
    message: str
    bundle_id: str
    baseline_bundle_id: str | None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        return f"CompareError: {self.message} for bundle {self.bundle_id}"
