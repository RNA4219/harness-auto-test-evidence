"""P1A support module - backward compatibility shim.

All functions are now implemented in the p1a_internal package.
This module provides backward compatibility for existing imports.

See REFACTORING_PLAN.md for the module split rationale.
"""

from __future__ import annotations

# Re-export all functions and constants from p1a_internal package
from hate.p1a_internal import (
    # Constants
    SCHEMA_VERSION,
    ADAPTER_REGISTRY_VERSION,
    AETE_DIMENSIONS,
    RUBRIC_VERSION,
    PROFILE_VERSION,
    # Adapter registry functions
    _build_adapter_registry,
    _adapter_manifest,
    _adapter_manifest_is_complete,
    _build_adapter_capability_manifest,
    # Adapter conformance functions
    _build_adapter_conformance_report,
    _adapter_conformance_results,
    # AETE scoring functions
    _score_dimensions_with_signals,
    _score_dimensions,
    _dimension_signal,
    _dimension_rationale,
    _score_confidence,
    # Artifact resolver functions
    _build_artifact_resolver_map,
    _resolution_status,
    # Doctor report functions
    _build_doctor_report,
    _doctor_finding,
    _count_by,
    _all_source_refs_non_empty,
    # Identity functions
    _build_canonical_identity_index,
    _identity_components,
    _normalized_canonical_test_id,
    _stable_mapping,
    _duplicates,
    # Retry aggregation functions
    _build_retry_aggregation,
    _merge_matrix,
    _matrix_group_id,
    _execution_sort_key,
    _shard_total,
    _aggregate_status,
    # Recommendations functions
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