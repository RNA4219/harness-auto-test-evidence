"""P1A internal module exports for backward compatibility."""

from __future__ import annotations

from hate.p1a_internal.adapter_registry import (
    SCHEMA_VERSION,
    ADAPTER_REGISTRY_VERSION,
    _build_adapter_registry,
    _adapter_manifest,
    _adapter_manifest_is_complete,
    _build_adapter_capability_manifest,
)
from hate.p1a_internal.adapter_conformance import (
    _build_adapter_conformance_report,
    _adapter_conformance_results,
)
from hate.p1a_internal.aete_scoring import (
    AETE_DIMENSIONS,
    RUBRIC_VERSION,
    PROFILE_VERSION,
    _score_dimensions_with_signals,
    _score_dimensions,
    _dimension_signal,
    _dimension_rationale,
    _score_confidence,
)
from hate.p1a_internal.artifact_resolver import (
    _build_artifact_resolver_map,
    _resolution_status,
)
from hate.p1a_internal.doctor_report import (
    _build_doctor_report,
    _doctor_finding,
    _count_by,
    _all_source_refs_non_empty,
)
from hate.p1a_internal.identity import (
    _build_canonical_identity_index,
    _identity_components,
    _normalized_canonical_test_id,
    _stable_mapping,
    _duplicates,
)
from hate.p1a_internal.retry_aggregation import (
    _build_retry_aggregation,
    _merge_matrix,
    _matrix_group_id,
    _execution_sort_key,
    _shard_total,
    _aggregate_status,
)
from hate.p1a_internal.recommendations import (
    _build_reason_tree,
    _build_recommendations,
    _source_refs_for_risk,
    _build_summary,
)

__all__ = [
    "SCHEMA_VERSION",
    "ADAPTER_REGISTRY_VERSION",
    "AETE_DIMENSIONS",
    "RUBRIC_VERSION",
    "PROFILE_VERSION",
    "_build_adapter_registry",
    "_adapter_manifest",
    "_adapter_manifest_is_complete",
    "_build_adapter_capability_manifest",
    "_build_adapter_conformance_report",
    "_adapter_conformance_results",
    "_score_dimensions_with_signals",
    "_score_dimensions",
    "_dimension_signal",
    "_dimension_rationale",
    "_score_confidence",
    "_build_artifact_resolver_map",
    "_resolution_status",
    "_build_doctor_report",
    "_doctor_finding",
    "_count_by",
    "_all_source_refs_non_empty",
    "_build_canonical_identity_index",
    "_identity_components",
    "_normalized_canonical_test_id",
    "_stable_mapping",
    "_duplicates",
    "_build_retry_aggregation",
    "_merge_matrix",
    "_matrix_group_id",
    "_execution_sort_key",
    "_shard_total",
    "_aggregate_status",
    "_build_reason_tree",
    "_build_recommendations",
    "_source_refs_for_risk",
    "_build_summary",
]