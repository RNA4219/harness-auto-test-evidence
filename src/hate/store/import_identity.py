"""短縮IDを再利用する前に、既存索引の実体と完全な内容hashを照合する。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .atomic_write import compute_json_hash
from .bundle_validation import PreparedBundle
from .indexes import HardDQFinding, IndexLookupError, MultiIndexManager
from .json_io import strict_json_loads
from .models import LocalStoreError, StoreManifest
from .references import resolve_store_reference


def validate_import_identity(manager: MultiIndexManager, prepared: PreparedBundle, data: dict[str, Any]) -> None:
    """衝突や既存参照の異常を、取り込みtransactionを開始する前に返す。"""
    manifests: dict[Path, StoreManifest] = {}
    try:
        manager.bundles_index.load()
        manager.artifacts_index.load()
        if prepared.bundle_id in manager.bundles_index.entries:
            reference = resolve_store_reference(
                manager.bundles_index, prepared.bundle_id, verify_record=True, require_complete=True, manifest_cache=manifests,
            )
            manifests[reference.path.parent] = reference.manifest
            saved = strict_json_loads(reference.path.read_text(encoding="utf-8"))
            if not isinstance(saved, dict):
                raise ValueError("stored bundle must be an object")
            saved_hash = compute_json_hash(saved)
            incoming_hash = prepared.canonical_hash or compute_json_hash(data)
            if saved_hash != incoming_hash:
                raise LocalStoreError(
                    "Bundle ID refers to different canonical content", "import_bundle", reference.path,
                    [{"issue": "bundle_id_collision", "bundle_id": prepared.bundle_id,
                      "stored_hash": saved_hash, "incoming_hash": incoming_hash}],
                )
        for artifact_id, digest in prepared.content_hashes.items():
            if artifact_id not in manager.artifacts_index.entries:
                continue
            reference = resolve_store_reference(
                manager.artifacts_index, artifact_id, verify_record=True, require_complete=True, manifest_cache=manifests,
            )
            manifests[reference.path.parent] = reference.manifest
            if reference.entry.hash.lower() != digest.lower():
                raise LocalStoreError(
                    "Artifact ID refers to different stored content", "import_bundle", reference.path,
                    [{"issue": "artifact_id_collision", "artifact_id": artifact_id,
                      "stored_hash": reference.entry.hash, "incoming_hash": digest}],
                )
    except LocalStoreError:
        raise
    except (HardDQFinding, IndexLookupError, OSError, ValueError) as exc:
        raise LocalStoreError(
            "Existing import identity cannot be verified", "import_bundle", manager.store_root,
            [{"issue": "import_identity_unverified", "error": str(exc), "validation": getattr(exc, "diagnostics", [])}],
        ) from exc
