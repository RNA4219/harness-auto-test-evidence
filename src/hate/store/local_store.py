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

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .atomic_write import (
    AtomicWriteError,
    atomic_write_json,
    complete_manifest_write,
)
from .bundle_validation import PreparedBundle, prepare_bundle
from .compatibility import manifest_schema_findings
from .import_identity import validate_import_identity
from .indexes import MultiIndexManager
from .indexing import populate_bundle_indexes
from .integrity import verify_run_integrity, verify_saved_import
from .json_io import strict_json_loads
from .locking import store_operation
from .models import ImportBundleResult as ImportBundleResult
from .models import LocalStoreError as LocalStoreError
from .models import StoreManifest as StoreManifest
from .references import resolve_store_reference
from .transaction import ImportTransaction, StoreRecoveryError
from .versioning import STORE_SCHEMA_VERSION, STORE_VERSION, StoreVersionError, new_store_version


def _read_object(path: Path, operation: str) -> dict[str, Any]:
    try:
        data = strict_json_loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("stored JSON must be an object")
    except (OSError, ValueError) as exc:
        raise LocalStoreError(
            message=f"JSON could not be read: {exc}", operation=operation, path=path,
            diagnostics=[{"error": str(exc)}],
        ) from exc
    return data


def read_store_manifest(bundle_dir: Path, *, require_complete: bool = False) -> StoreManifest:
    """保存先とmanifestの識別子を照合する。doctorは未完了状態も読める。"""
    path = bundle_dir / "store-manifest.json"
    try:
        manifest = StoreManifest.from_dict(_read_object(path, "read_manifest"))
        if manifest.run_id != bundle_dir.parent.name or manifest.bundle_id != bundle_dir.name:
            raise LocalStoreError("Manifest identifiers do not match its path", "read_manifest", path)
        if require_complete and manifest.completed is not True:
            raise LocalStoreError("Manifest is not complete", "read_manifest", path)
    except LocalStoreError as exc:
        exc.path = path
        raise
    return manifest


def _read_bundle_data(path: Path, operation: str, manifest: StoreManifest) -> dict[str, Any]:
    diagnostics = manifest_schema_findings(manifest)
    if diagnostics:
        raise LocalStoreError("Stored schema is unsupported", operation, path.parent / "store-manifest.json", diagnostics)
    data = _read_object(path, operation)
    prepared = prepare_bundle(data, path)
    if prepared.bundle_id != manifest.bundle_id:
        raise LocalStoreError("Bundle content identifier mismatch", operation, path)
    return data


class LocalStore:
    """Immutable local store for HATE evidence bundles.

    Current local store directory structure:

    .hate/
      store-version.json
      runs/<run_id>/<bundle_id>/
        qeg-bundle.json
        artifact-<content-hash>.json
        store-manifest.json
      indexes/
        runs.jsonl
        bundles.jsonl
        evidence.jsonl
        risks.jsonl
        artifacts.jsonl
        requirements.jsonl
        source-refs.jsonl
      locks/
      migrations/
      quarantine/
    """

    def __init__(self, store_root: Path, producer_version: str = "unknown") -> None:
        self.store_root = store_root.resolve()
        new_store_version(self.store_root, producer_version)
        self.producer_version = producer_version
        self.index_manager = MultiIndexManager(self.store_root)

        # Create store structure
        self._ensure_store_structure()

    @store_operation
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
            version_content = new_store_version(self.store_root, self.producer_version)
            atomic_write_json(version_path, version_content, self.store_root)

    @store_operation
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
        if not isinstance(run_id, str) or not run_id.strip() or Path(run_id).name != run_id or run_id in {".", ".."}:
            raise LocalStoreError("run_id must be a non-empty directory name", "import_bundle")
        if not isinstance(legal_hold, dict) or not legal_hold:
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

        bundle_data = _read_object(bundle_path, "import_bundle")

        prepared = prepare_bundle(bundle_data, bundle_path)
        bundle_id = prepared.bundle_id

        source_refs = [str(bundle_path)] if sourceRefs is None else sourceRefs
        # ファイルや索引を書き始める前に、同じ公開スキーマで入力を検証する。
        StoreManifest.from_dict(StoreManifest(
            run_id, bundle_id, source_version, {"core": STORE_SCHEMA_VERSION, "store": STORE_VERSION},
            [], {}, {}, legal_hold, retention_policy_id,
            datetime.now(UTC).isoformat(), self.producer_version, False, source_refs,
        ).to_dict())

        # Determine bundle directory
        # Use simple structure: runs/<run_id>/<bundle_id>/ (no repo_hash for local)
        bundle_dir = self.store_root / "runs" / run_id / bundle_id
        validate_import_identity(self.index_manager, prepared, bundle_data)

        # Check if bundle already exists (append-only, no overwrite)
        manifest_path = bundle_dir / "store-manifest.json"
        if manifest_path.exists():
            manifest = read_store_manifest(bundle_dir, require_complete=True)
            diagnostics = verify_saved_import(self, bundle_dir, manifest)
            if diagnostics:
                raise LocalStoreError(
                    "Existing bundle failed integrity verification", "import_bundle", manifest_path, diagnostics,
                )
            return ImportBundleResult(
                success=True,
                run_id=run_id,
                bundle_id=bundle_id,
                manifest_path=manifest_path,
                index_hashes=None,
                diagnostics=[{"info": "bundle_already_exists", "path": str(bundle_dir)}],
            )

        transaction = ImportTransaction(self.store_root, bundle_dir)
        try:
            with transaction:
                result = self._write_import(
                    bundle_data, bundle_dir, run_id, bundle_id, source_version,
                    legal_hold, retention_policy_id, source_refs, prepared,
                )
                transaction.commit()
            return result
        except (StoreRecoveryError, StoreVersionError):
            raise
        except Exception as exc:
            self.index_manager.load_all()
            return ImportBundleResult(
                success=False, run_id=run_id, bundle_id=bundle_id, manifest_path=None, index_hashes=None,
                diagnostics=[{
                    "issue": "atomic_write_failed" if isinstance(exc, AtomicWriteError) else "import_failed",
                    "error": str(exc), "phase": getattr(exc, "phase", "unknown"),
                    "quarantine_path": str(transaction.quarantine_path) if transaction.quarantine_path else None,
                }],
            )

    def _write_import(
        self, bundle_data: dict[str, Any], bundle_dir: Path, run_id: str, bundle_id: str,
        source_version: str, legal_hold: dict[str, Any], retention_policy_id: str, source_refs: list[str],
        prepared: PreparedBundle,
    ) -> ImportBundleResult:
        bundle_dest = bundle_dir / "qeg-bundle.json"
        atomic_write_json(bundle_dest, bundle_data, self.store_root)
        bundle_files = [bundle_dest]
        artifact_ids = list(prepared.artifacts)
        content_hashes = prepared.content_hashes
        for artifact_id, node in prepared.artifacts.items():
            destination = bundle_dir / f"{artifact_id}.json"
            atomic_write_json(destination, node, self.store_root)
            bundle_files.append(destination)
        self.index_manager.load_all()
        populate_bundle_indexes(self.index_manager, bundle_dir, run_id, bundle_id, content_hashes)
        index_hashes = self.index_manager.save_all()
        manifest_path = bundle_dir / "store-manifest.json"
        manifest = StoreManifest(
            run_id, bundle_id, source_version, {"core": STORE_SCHEMA_VERSION, "store": STORE_VERSION},
            artifact_ids, content_hashes, index_hashes, legal_hold, retention_policy_id,
            datetime.now(UTC).isoformat(), self.producer_version, False, source_refs,
        )
        complete_manifest_write(
            manifest_path=manifest_path, manifest_content=manifest.to_dict(),
            store_root=self.store_root, bundle_files=bundle_files,
        )
        return ImportBundleResult(True, run_id, bundle_id, manifest_path, index_hashes)

    @store_operation
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
        self.index_manager.bundles_index.load()
        reference = resolve_store_reference(
            self.index_manager.bundles_index, bundle_id, operation="read_bundle", verify_record=True, require_complete=True,
        )
        return _read_bundle_data(reference.path, "read_bundle", reference.manifest)

    @store_operation
    def read_bundle_by_run(self, run_id: str) -> dict[str, Any]:
        """Read the bundle for a run.

        Args:
            run_id: Run identifier

        Returns:
            Bundle data
        """
        self.index_manager.runs_index.load()
        reference = resolve_store_reference(
            self.index_manager.runs_index, run_id, operation="read_bundle_by_run", verify_record=True, require_complete=True,
        )
        return _read_bundle_data(reference.path, "read_bundle_by_run", reference.manifest)

    @store_operation
    def read_manifest(self, run_id: str) -> StoreManifest:
        """Read the store manifest for a run.

        Args:
            run_id: Run identifier

        Returns:
            StoreManifest object
        """
        # Find bundle directory from run index
        self.index_manager.runs_index.load()
        return resolve_store_reference(self.index_manager.runs_index, run_id, operation="read_manifest").manifest

    @store_operation
    def list_runs(self) -> list[str]:
        """List all run IDs in the store."""
        self.index_manager.load_all()
        return sorted(self.index_manager.runs_index.entries.keys())

    @store_operation
    def list_bundles(self) -> list[str]:
        """List all bundle IDs in the store."""
        self.index_manager.load_all()
        return sorted(self.index_manager.bundles_index.entries.keys())

    def list_all_bundles(self) -> list[str]:
        """List all bundle IDs in the store (alias for list_bundles)."""
        return self.list_bundles()

    @store_operation
    def list_bundles_for_run(self, run_id: str) -> list[str]:
        """List all bundle IDs for a specific run.

        Args:
            run_id: Run identifier

        Returns:
            List of bundle IDs for this run
        """
        run_dir = (self.store_root / "runs" / run_id).resolve()
        if not run_dir.is_relative_to(self.store_root / "runs"):
            raise LocalStoreError("run path is outside store", "list_bundles_for_run", run_dir)
        bundle_ids: list[str] = []
        for path in run_dir.glob("*/store-manifest.json"):
            manifest = read_store_manifest(path.parent)
            if manifest.completed is not True:
                continue
            if manifest.run_id != run_id:
                raise LocalStoreError("run history manifest mismatch", "list_bundles_for_run", path)
            bundle_ids.append(path.parent.name)
        return sorted(bundle_ids)

    @store_operation
    def read_manifest_by_bundle(self, bundle_id: str, *, run_id: str | None = None) -> StoreManifest:
        """Read the store manifest by bundle ID.

        Args:
            bundle_id: Bundle identifier

        Returns:
            StoreManifest object
        """
        if run_id is not None:
            bundle_dir = self.store_root / "runs" / run_id / bundle_id
            if bundle_dir.resolve().parent.parent != self.store_root / "runs":
                raise LocalStoreError("Invalid bundle location", "read_manifest_by_bundle", bundle_dir)
        else:
            self.index_manager.bundles_index.load()
            return resolve_store_reference(
                self.index_manager.bundles_index, bundle_id, operation="read_manifest_by_bundle",
            ).manifest
        manifest_path = bundle_dir / "store-manifest.json"

        if not manifest_path.exists():
            raise LocalStoreError(
                message=f"Manifest not found for bundle: {bundle_id}",
                operation="read_manifest_by_bundle",
                path=manifest_path,
            )

        manifest = read_store_manifest(bundle_dir)
        if manifest.bundle_id != bundle_id:
            raise LocalStoreError("Bundle index identifier mismatch", "read_manifest_by_bundle", manifest_path)
        return manifest

    @store_operation
    def verify_integrity(self, run_id: str) -> dict[str, Any]:
        """対象runと現在の索引参照を、ファイルを書き換えずに検証する。"""
        return verify_run_integrity(self, run_id)

    @store_operation
    def is_legal_hold_active(self, run_id: str) -> bool:
        """Check if legal hold is active for a run."""
        manifest = self.read_manifest(run_id)
        return manifest.legal_hold.get("status") == "active"

    @store_operation
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

        unsupported = manifest_schema_findings(manifest)
        if unsupported:
            path = self.store_root / "runs" / manifest.run_id / manifest.bundle_id / "store-manifest.json"
            raise LocalStoreError("Stored schema is unsupported", "update_legal_hold", path, unsupported)

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

        # 開始日時は保持への遷移時に記録し、保持中の理由修正では変更しない。
        held_since = manifest.legal_hold["held_since"]
        if new_status == "active" and current_status != "active":
            held_since = datetime.now(UTC).isoformat()
        new_legal_hold: dict[str, Any] = {
            "status": new_status,
            "reason": reason,
            "held_since": held_since,
            "authorized_by": authorized_by,
        }

        if new_status == "released":
            if current_status == "released":
                # 同じ状態の再申告で、元の解除日時・承認証跡を作り直さない。
                for name in ("released_at", "release_authorization"):
                    if name in manifest.legal_hold:
                        new_legal_hold[name] = manifest.legal_hold[name]
            else:
                new_legal_hold["released_at"] = datetime.now(UTC).isoformat()
                new_legal_hold["release_authorization"] = {"authorized_by": authorized_by}

        # Find bundle directory
        entry = self.index_manager.runs_index.lookup(run_id, verify_record=False)
        bundle_dir = self.store_root / Path(entry.value).parent
        manifest_path = bundle_dir / "store-manifest.json"

        # Update manifest
        updated_data = manifest.to_dict()
        updated_data["legal_hold"] = new_legal_hold
        updated_manifest = StoreManifest.from_dict(updated_data)

        # Write atomically
        atomic_write_json(manifest_path, updated_data, self.store_root)

        return updated_manifest
