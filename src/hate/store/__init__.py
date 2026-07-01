"""HATE Local Store Module.

Implements immutable local store with atomic write guarantees per HATE-PG-006A:
- Atomic write: temp write → fsync/rename → manifest complete
- Content-addressed artifacts (hash-based identity)
- Multi-dimensional indexes (run_id, requirement_ref, risk_ref, sourceRef, artifact_id)
- Legal hold metadata (mandatory, not optional)
- Append-only completed bundles

HATE-PG-006B additions:
- Replay produces byte-stable reports from canonical bundle contents
- Compare detects improvement, regression, no-change
- Doctor diagnoses corruption and data quality issues
"""

from __future__ import annotations

from .atomic_write import (
    AtomicWriteError,
    atomic_write_json,
    complete_manifest_write,
    quarantine_partial_write,
    compute_json_hash,
    compute_json_hash_for_write,
    compute_file_hash,
)
from .local_store import (
    LocalStore,
    LocalStoreError,
    ImportBundleResult,
    StoreManifest,
)
from .indexes import (
    StoreIndex,
    IndexEntry,
    IndexLookupError,
    HardDQFinding,
)
from .replay import (
    ReplayError,
    ReplayReport,
    BaselineInfo,
    build_store_replay_report,
    replay_bundle,
    select_baseline_by_timestamp,
    select_baseline_by_filename_sort,
    SUPPORTED_SCHEMA_VERSIONS,
    MIGRATION_REQUIRED_VERSIONS,
)
from .compare import (
    CompareError,
    ComparisonReport,
    ComparisonResult,
    ArtifactDiff,
    compare_bundle_to_baseline,
    compare_bundles_direct,
)
from .doctor import (
    DoctorError,
    DoctorReport,
    DiagnosisFinding,
    DiagnosisSeverity,
    diagnose_bundle,
    diagnose_run,
    diagnose_full_store,
)
from .migration_rebuild import (
    StoreMigrationFinding,
    build_store_migration_report,
    evaluate_store_migration_fixture,
)

# Legacy imports (from store_legacy.py for backward compatibility)
from hate.store_legacy import (
    StoreError,
    ingest_local_store,
    query_local_store,
    read_history_index,
)

__all__ = [
    "AtomicWriteError",
    "atomic_write_json",
    "complete_manifest_write",
    "quarantine_partial_write",
    "compute_json_hash",
    "compute_json_hash_for_write",
    "compute_file_hash",
    "LocalStore",
    "LocalStoreError",
    "ImportBundleResult",
    "StoreManifest",
    "StoreIndex",
    "IndexEntry",
    "IndexLookupError",
    "HardDQFinding",
    # HATE-PG-006B additions
    "ReplayError",
    "ReplayReport",
    "BaselineInfo",
    "build_store_replay_report",
    "replay_bundle",
    "select_baseline_by_timestamp",
    "select_baseline_by_filename_sort",
    "SUPPORTED_SCHEMA_VERSIONS",
    "MIGRATION_REQUIRED_VERSIONS",
    "CompareError",
    "ComparisonReport",
    "ComparisonResult",
    "ArtifactDiff",
    "compare_bundle_to_baseline",
    "compare_bundles_direct",
    "DoctorError",
    "DoctorReport",
    "DiagnosisFinding",
    "DiagnosisSeverity",
    "diagnose_bundle",
    "diagnose_run",
    "diagnose_full_store",
    "StoreMigrationFinding",
    "build_store_migration_report",
    "evaluate_store_migration_fixture",
    # Legacy exports
    "StoreError",
    "ingest_local_store",
    "query_local_store",
    "read_history_index",
]
