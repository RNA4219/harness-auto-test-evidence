"""Immutable Local Store for HATE.

Implements immutable append-only store for canonical evidence bundles.
All completed bundles are content-addressed with stable hashes.

Key invariants:
- Canonical bundle content is immutable after import
- Legal hold metadata is mandatory (NOT optional)
- Append-only for completed bundles
- Partial/incomplete writes are quarantined

No-Go conditions:
- External export mutates canonical bundle
- Artifact content addressed only by filename
- Partial write appears as valid run
- Legal hold metadata is optional
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .atomic_write import (
    AtomicWriteError,
    atomic_write_json,
    complete_manifest_write,
    compute_json_hash,
    compute_json_hash_for_write,
    compute_file_hash,
    is_complete_manifest,
    quarantine_partial_write,
)
from .indexes import (
    StoreIndex,
    IndexEntry,
    HardDQFinding,
    IndexLookupError,
    MultiIndexManager,
)


@dataclass
class LocalStoreError(Exception):
    """Error in local store operation."""
    message: str
    operation: str
    path: Path | None = None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        return f"LocalStoreError({self.operation}): {self.message}"


@dataclass
class StoreManifest:
    """Immutable store manifest for a bundle."""
    run_id: str
    bundle_id: str
    source_version: str
    schema_versions: dict[str, str]
    artifact_ids: list[str]
    content_hashes: dict[str, str]
    index_hashes: dict[str, str]
    legal_hold: dict[str, Any]  # Mandatory, NOT optional
    retention_policy_id: str
    created_at: str
    producer_version: str
    completed: bool
    sourceRefs: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoreManifest":
        """Create manifest from dict."""
        return cls(
            run_id=data["run_id"],
            bundle_id=data["bundle_id"],
            source_version=data["source_version"],
            schema_versions=data["schema_versions"],
            artifact_ids=data["artifact_ids"],
            content_hashes=data["content_hashes"],
            index_hashes=data["index_hashes"],
            legal_hold=data["legal_hold"],  # Mandatory
            retention_policy_id=data["retention_policy_id"],
            created_at=data["created_at"],
            producer_version=data["producer_version"],
            completed=data.get("completed", False),
            sourceRefs=data["sourceRefs"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dict."""
        return {
            "schema_version": "HATE/v1",
            "record_type": "store_manifest",
            "run_id": self.run_id,
            "bundle_id": self.bundle_id,
            "source_version": self.source_version,
            "schema_versions": self.schema_versions,
            "artifact_ids": self.artifact_ids,
            "content_hashes": self.content_hashes,
            "index_hashes": self.index_hashes,
            "legal_hold": self.legal_hold,  # Mandatory
            "retention_policy_id": self.retention_policy_id,
            "created_at": self.created_at,
            "producer_version": self.producer_version,
            "completed": self.completed,
            "sourceRefs": self.sourceRefs,
        }


@dataclass
class ImportBundleResult:
    """Result of bundle import operation."""
    success: bool
    run_id: str
    bundle_id: str
    manifest_path: Path | None
    index_hashes: dict[str, str] | None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dict."""
        return {
            "schema_version": "HATE/v1",
            "record_type": "import_bundle_result",
            "success": self.success,
            "run_id": self.run_id,
            "bundle_id": self.bundle_id,
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "index_hashes": self.index_hashes,
            "diagnostics": self.diagnostics,
        }


class LocalStore:
    """Immutable local store for HATE evidence bundles.

    Store directory structure (per PRODUCT_GRADE_IMPLEMENTATION_SPEC.md 4.3):

    .hate/
      store-version.json
      runs/<repo_hash>/<run_id>/<attempt>/
        input-manifest.json
        canonical-bundle/
        derived/
        validation/
        audit/
      indexes/
        runs.jsonl
        bundles.jsonl
        evidence.jsonl
        risk-debt.jsonl
        artifacts.jsonl
        audit-events.jsonl
      locks/
      migrations/
      quarantine/
    """

    def __init__(self, store_root: Path, producer_version: str = "unknown") -> None:
        self.store_root = store_root.resolve()
        self.producer_version = producer_version
        self.index_manager = MultiIndexManager(self.store_root)

        # Create store structure
        self._ensure_store_structure()

    def _ensure_store_structure(self) -> None:
        """Create store directory structure."""
        dirs = [
            self.store_root,
            self.store_root / "runs",
            self.store_root / "indexes",
            self.store_root / "locks",
            self.store_root / "migrations",
            self.store_root / "quarantine",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        # Create store-version.json
        version_path = self.store_root / "store-version.json"
        if not version_path.exists():
            version_content = {
                "schema_version": "HATE/v1",
                "store_version": "1.0.0",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "producer_version": self.producer_version,
            }
            atomic_write_json(version_path, version_content, self.store_root)

    def import_bundle(
        self,
        bundle_path: Path,
        run_id: str,
        source_version: str,
        legal_hold: dict[str, Any],  # Mandatory - caller must provide
        retention_policy_id: str = "default-90-days",
        sourceRefs: list[str] | None = None,
    ) -> ImportBundleResult:
        """Import a bundle into the store.

        Import process:
        1. Compute content-addressed bundle_id from bundle hash
        2. Create bundle directory under runs/
        3. Copy bundle files atomically
        4. Compute hashes for all artifacts
        5. Build indexes
        6. Write store manifest atomically with completed=true

        Args:
            bundle_path: Path to QEG bundle JSON file
            run_id: Run identifier
            source_version: Source version (e.g., git SHA)
            legal_hold: Legal hold metadata (MANDATORY)
            retention_policy_id: Retention policy identifier
            sourceRefs: Source references for provenance

        Returns:
            ImportBundleResult with success status and diagnostics

        Raises:
            LocalStoreError: If import fails
            HardDQFinding: If DQ condition detected
        """
        # Validate legal_hold is provided and has required fields
        if not legal_hold:
            raise LocalStoreError(
                message="legal_hold metadata is MANDATORY and cannot be empty",
                operation="import_bundle",
                diagnostics=[{"issue": "missing_legal_hold"}],
            )

        required_hold_fields = ["status", "reason", "held_since", "authorized_by"]
        missing_fields = [f for f in required_hold_fields if f not in legal_hold]
        if missing_fields:
            raise LocalStoreError(
                message=f"legal_hold missing required fields: {missing_fields}",
                operation="import_bundle",
                diagnostics=[{"issue": "invalid_legal_hold", "missing_fields": missing_fields}],
            )

        # Validate bundle exists
        if not bundle_path.exists():
            raise LocalStoreError(
                message=f"Bundle file not found: {bundle_path}",
                operation="import_bundle",
                path=bundle_path,
            )

        # Read bundle
        try:
            with bundle_path.open("r", encoding="utf-8") as f:
                bundle_data = json.load(f)
        except json.JSONDecodeError as e:
            raise LocalStoreError(
                message=f"Bundle JSON invalid: {e}",
                operation="import_bundle",
                path=bundle_path,
                diagnostics=[{"error": str(e)}],
            )

        # Compute content-addressed bundle_id
        bundle_hash = compute_json_hash(bundle_data)
        bundle_id = f"bundle-{bundle_hash.split(':')[1][:16]}"

        # Determine bundle directory
        # Use simple structure: runs/<run_id>/<bundle_id>/ (no repo_hash for local)
        bundle_dir = self.store_root / "runs" / run_id / bundle_id

        # Check if bundle already exists (append-only, no overwrite)
        manifest_path = bundle_dir / "store-manifest.json"
        if is_complete_manifest(manifest_path):
            return ImportBundleResult(
                success=True,
                run_id=run_id,
                bundle_id=bundle_id,
                manifest_path=manifest_path,
                index_hashes=None,
                diagnostics=[{"info": "bundle_already_exists", "path": str(bundle_dir)}],
            )

        # Prepare bundle directory
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # Files to write
        bundle_files = []
        partial_files = []

        try:
            # Write bundle file first, then compute hash from actual file
            # This ensures manifest hash matches the file content format (indent=2)
            bundle_dest = bundle_dir / "qeg-bundle.json"
            atomic_write_json(bundle_dest, bundle_data, self.store_root)
            bundle_files.append(bundle_dest)

            # Compute hash from actual written file
            bundle_hash = compute_file_hash(bundle_dest)

            # Compute artifact hashes from bundle nodes
            artifact_ids = []
            content_hashes = {}

            # Extract artifacts from bundle nodes
            nodes = bundle_data.get("nodes", [])
            for node in nodes:
                node_id = node.get("id", "")
                node_kind = node.get("kind", "")

                if node_kind in ["test_result", "coverage_slice", "static_finding", "contract_evidence", "mutation_evidence"]:
                    # Compute hash in write format (indent=2) BEFORE writing
                    # This allows us to use hash-based artifact_id as filename
                    artifact_hash = compute_json_hash_for_write(node)
                    artifact_id = f"artifact-{artifact_hash.split(':')[1][:16]}"
                    artifact_ids.append(artifact_id)
                    content_hashes[artifact_id] = artifact_hash

                    # Write artifact file (filename matches artifact_id)
                    artifact_dest = bundle_dir / f"{artifact_id}.json"
                    atomic_write_json(artifact_dest, node, self.store_root)
                    bundle_files.append(artifact_dest)

            # Build indexes
            self.index_manager.load_all()

            # Add run index
            self.index_manager.runs_index.add_entry(
                key=run_id,
                value=str(bundle_dir.relative_to(self.store_root) / "qeg-bundle.json"),
                record_hash=bundle_hash,
                metadata={"bundle_id": bundle_id},
            )

            # Add bundle index
            self.index_manager.bundles_index.add_entry(
                key=bundle_id,
                value=str(bundle_dir.relative_to(self.store_root) / "qeg-bundle.json"),
                record_hash=bundle_hash,
                metadata={"run_id": run_id},
            )

            # Add artifact indexes
            for artifact_id in artifact_ids:
                self.index_manager.artifacts_index.add_entry(
                    key=artifact_id,
                    value=str(bundle_dir.relative_to(self.store_root) / f"{artifact_id}.json"),
                    record_hash=content_hashes[artifact_id],
                    metadata={"run_id": run_id, "bundle_id": bundle_id},
                )

            # Save indexes and get hashes
            index_hashes = self.index_manager.save_all()

            # Create manifest content
            manifest_content = {
                "schema_version": "HATE/v1",
                "record_type": "store_manifest",
                "run_id": run_id,
                "bundle_id": bundle_id,
                "source_version": source_version,
                "schema_versions": {
                    "core": "HATE/v1",
                    "store": "1.0.0",
                },
                "artifact_ids": artifact_ids,
                "content_hashes": content_hashes,
                "index_hashes": index_hashes,
                "legal_hold": legal_hold,  # Mandatory
                "retention_policy_id": retention_policy_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "producer_version": self.producer_version,
                "completed": False,  # Will be set to True by complete_manifest_write
                "sourceRefs": sourceRefs or [str(bundle_path)],
            }

            # Write manifest atomically with completion
            complete_manifest_write(
                manifest_path=manifest_path,
                manifest_content=manifest_content,
                store_root=self.store_root,
                bundle_files=bundle_files,
            )

            return ImportBundleResult(
                success=True,
                run_id=run_id,
                bundle_id=bundle_id,
                manifest_path=manifest_path,
                index_hashes=index_hashes,
                diagnostics=[],
            )

        except AtomicWriteError as e:
            # Quarantine partial write
            quarantine_path = quarantine_partial_write(
                store_root=self.store_root,
                run_id=run_id,
                partial_files=bundle_files + partial_files,
                error=e,
            )

            return ImportBundleResult(
                success=False,
                run_id=run_id,
                bundle_id=bundle_id,
                manifest_path=None,
                index_hashes=None,
                diagnostics=[
                    {
                        "issue": "atomic_write_failed",
                        "phase": e.phase,
                        "message": e.message,
                        "quarantine_path": str(quarantine_path),
                    }
                ],
            )

        except Exception as e:
            # Quarantine partial write
            error = AtomicWriteError(
                message=str(e),
                path=bundle_dir,
                phase="unknown",
                diagnostics=[{"exception": type(e).__name__}],
            )
            quarantine_path = quarantine_partial_write(
                store_root=self.store_root,
                run_id=run_id,
                partial_files=bundle_files + partial_files,
                error=error,
            )

            return ImportBundleResult(
                success=False,
                run_id=run_id,
                bundle_id=bundle_id,
                manifest_path=None,
                index_hashes=None,
                diagnostics=[
                    {
                        "issue": "import_failed",
                        "error": str(e),
                        "quarantine_path": str(quarantine_path),
                    }
                ],
            )

    def read_bundle(self, bundle_id: str) -> dict[str, Any]:
        """Read a bundle by content-addressed ID.

        Args:
            bundle_id: Content-addressed bundle identifier

        Returns:
            Bundle data

        Raises:
            IndexLookupError: If bundle not found
            HardDQFinding: If index references missing bundle
        """
        entry = self.index_manager.bundles_index.lookup(bundle_id, verify_record=True)
        bundle_path = self.store_root / entry.value

        with bundle_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def read_bundle_by_run(self, run_id: str) -> dict[str, Any]:
        """Read the bundle for a run.

        Args:
            run_id: Run identifier

        Returns:
            Bundle data
        """
        entry = self.index_manager.runs_index.lookup(run_id, verify_record=True)
        bundle_path = self.store_root / entry.value

        with bundle_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def read_manifest(self, run_id: str) -> StoreManifest:
        """Read the store manifest for a run.

        Args:
            run_id: Run identifier

        Returns:
            StoreManifest object
        """
        # Find bundle directory from run index
        entry = self.index_manager.runs_index.lookup(run_id, verify_record=False)
        bundle_dir = self.store_root / Path(entry.value).parent
        manifest_path = bundle_dir / "store-manifest.json"

        if not manifest_path.exists():
            raise LocalStoreError(
                message=f"Manifest not found for run: {run_id}",
                operation="read_manifest",
                path=manifest_path,
            )

        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return StoreManifest.from_dict(data)

    def list_runs(self) -> list[str]:
        """List all run IDs in the store."""
        self.index_manager.load_all()
        return sorted(self.index_manager.runs_index.entries.keys())

    def list_bundles(self) -> list[str]:
        """List all bundle IDs in the store."""
        self.index_manager.load_all()
        return sorted(self.index_manager.bundles_index.entries.keys())

    def list_all_bundles(self) -> list[str]:
        """List all bundle IDs in the store (alias for list_bundles)."""
        return self.list_bundles()

    def list_bundles_for_run(self, run_id: str) -> list[str]:
        """List all bundle IDs for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            List of bundle IDs for this run
        """
        self.index_manager.load_all()
        bundle_ids = []
        for bundle_id, entry in self.index_manager.bundles_index.entries.items():
            if entry.metadata.get("run_id") == run_id:
                bundle_ids.append(bundle_id)
        return sorted(bundle_ids)

    def read_manifest_by_bundle(self, bundle_id: str) -> StoreManifest:
        """Read the store manifest by bundle ID.

        Args:
            bundle_id: Bundle identifier

        Returns:
            StoreManifest object
        """
        entry = self.index_manager.bundles_index.lookup(bundle_id, verify_record=False)
        bundle_dir = self.store_root / Path(entry.value).parent
        manifest_path = bundle_dir / "store-manifest.json"

        if not manifest_path.exists():
            raise LocalStoreError(
                message=f"Manifest not found for bundle: {bundle_id}",
                operation="read_manifest_by_bundle",
                path=manifest_path,
            )

        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return StoreManifest.from_dict(data)

    def verify_integrity(self, run_id: str) -> dict[str, Any]:
        """Verify integrity of a stored run.

        Checks:
        - Manifest exists and is complete
        - All referenced artifacts exist
        - All hashes match
        - Index entries are valid

        Args:
            run_id: Run identifier

        Returns:
            Verification result with diagnostics
        """
        manifest = self.read_manifest(run_id)

        # Find bundle directory
        entry = self.index_manager.runs_index.lookup(run_id, verify_record=False)
        bundle_dir = self.store_root / Path(entry.value).parent

        diagnostics = []
        integrity_ok = True

        # Check manifest completeness
        if not manifest.completed:
            diagnostics.append({
                "issue": "manifest_not_complete",
                "run_id": run_id,
            })
            integrity_ok = False

        # Check artifacts exist and hashes match
        for artifact_id, expected_hash in manifest.content_hashes.items():
            artifact_path = bundle_dir / f"{artifact_id}.json"
            if not artifact_path.exists():
                diagnostics.append({
                    "issue": "missing_artifact",
                    "artifact_id": artifact_id,
                    "expected_path": str(artifact_path),
                })
                integrity_ok = False
            else:
                actual_hash = compute_file_hash(artifact_path)
                if actual_hash != expected_hash:
                    diagnostics.append({
                        "issue": "hash_mismatch",
                        "artifact_id": artifact_id,
                        "expected": expected_hash,
                        "actual": actual_hash,
                    })
                    integrity_ok = False

        # Verify index hashes
        self.index_manager.load_all()
        current_index_hashes = {}
        for index in self.index_manager._all_indexes():
            current_index_hashes[index.index_type] = index.save()

        for index_type, expected_hash in manifest.index_hashes.items():
            actual_hash = current_index_hashes.get(index_type, "")
            if actual_hash != expected_hash:
                diagnostics.append({
                    "issue": "index_hash_mismatch",
                    "index_type": index_type,
                    "expected": expected_hash,
                    "actual": actual_hash,
                })
                integrity_ok = False

        # Check legal hold
        if manifest.legal_hold.get("status") == "active":
            diagnostics.append({
                "info": "legal_hold_active",
                "reason": manifest.legal_hold.get("reason"),
            })

        return {
            "schema_version": "HATE/v1",
            "record_type": "integrity_verification",
            "run_id": run_id,
            "integrity_ok": integrity_ok,
            "diagnostics": diagnostics,
        }

    def is_legal_hold_active(self, run_id: str) -> bool:
        """Check if legal hold is active for a run."""
        manifest = self.read_manifest(run_id)
        return manifest.legal_hold.get("status") == "active"

    def update_legal_hold(
        self,
        run_id: str,
        new_status: str,
        reason: str,
        authorized_by: str,
    ) -> StoreManifest:
        """Update legal hold status for a run.

        Legal hold can be updated, but must always be present.
        Status transitions must be authorized.

        Args:
            run_id: Run identifier
            new_status: New status (none, active, released, pending)
            reason: Reason for the hold/release
            authorized_by: User or role authorizing the change

        Returns:
            Updated manifest

        Raises:
            LocalStoreError: If update fails or unauthorized
        """
        manifest = self.read_manifest(run_id)

        # Validate status transition
        current_status = manifest.legal_hold.get("status")
        if current_status == "active" and new_status == "released":
            # Release requires explicit authorization
            if not authorized_by:
                raise LocalStoreError(
                    message="Legal hold release requires authorization",
                    operation="update_legal_hold",
                    diagnostics=[{"issue": "missing_authorization"}],
                )

        # Update legal hold
        new_legal_hold = {
            "status": new_status,
            "reason": reason,
            "held_since": manifest.legal_hold.get("held_since") or datetime.now(timezone.utc).isoformat(),
            "authorized_by": authorized_by,
        }

        if new_status == "released":
            new_legal_hold["released_at"] = datetime.now(timezone.utc).isoformat()
            new_legal_hold["release_authorization"] = {"authorized_by": authorized_by}

        # Find bundle directory
        entry = self.index_manager.runs_index.lookup(run_id, verify_record=False)
        bundle_dir = self.store_root / Path(entry.value).parent
        manifest_path = bundle_dir / "store-manifest.json"

        # Update manifest
        updated_data = manifest.to_dict()
        updated_data["legal_hold"] = new_legal_hold

        # Write atomically
        atomic_write_json(manifest_path, updated_data, self.store_root)

        return StoreManifest.from_dict(updated_data)