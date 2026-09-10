"""ローカル保存形式の索引参照とmanifestの識別子を照合する。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .indexes import IndexEntry, StoreIndex
from .models import LocalStoreError, StoreManifest


@dataclass
class StoreReference:
    entry: IndexEntry
    path: Path
    manifest: StoreManifest


def resolve_store_reference(
    index: StoreIndex, key: str, *, operation: str = "resolve_reference", verify_record: bool = False,
    require_complete: bool = False, manifest_cache: Mapping[Path, StoreManifest] | None = None,
) -> StoreReference:
    from .local_store import read_store_manifest

    entry = index.lookup(key, verify_record=False)
    root = index.store_root.resolve()
    path = (root / entry.value).resolve()
    directory = path.parent
    filename = f"{key}.json" if index.index_type == "artifacts" else "qeg-bundle.json"
    if index.index_type not in {"runs", "bundles", "artifacts"} or directory.parent.parent != root / "runs" or path.name != filename:
        raise LocalStoreError(
            "Index does not reference the canonical stored record", operation, index.index_path,
            [{"issue": "invalid_index_location", "index_type": index.index_type, "key": key, "record_path": str(path)}],
        )
    manifest = manifest_cache.get(directory) if manifest_cache is not None else None
    if manifest is None:
        manifest = read_store_manifest(directory)
    if require_complete and not manifest.completed:
        raise LocalStoreError("Referenced bundle is not complete", operation, directory / "store-manifest.json")
    if index.index_type == "runs":
        expected_key = manifest.run_id
        metadata = {"bundle_id": manifest.bundle_id}
    elif index.index_type == "bundles":
        expected_key = manifest.bundle_id
        metadata = {"run_id": manifest.run_id}
    else:
        expected_key = key if key in manifest.artifact_ids else ""
        metadata = {"run_id": manifest.run_id, "bundle_id": manifest.bundle_id}
    if key != expected_key or any(entry.metadata.get(name) != value for name, value in metadata.items()):
        raise LocalStoreError(
            "Index identity does not match saved manifest", operation, index.index_path,
            [{"issue": "index_identity_mismatch", "index_type": index.index_type, "key": key}],
        )
    if index.index_type == "artifacts" and entry.hash.lower() != manifest.content_hashes.get(key, "").lower():
        raise LocalStoreError(
            "Artifact index hash does not match saved manifest", operation, index.index_path,
            [{"issue": "index_record_hash_mismatch", "index_type": index.index_type, "key": key}],
        )
    if verify_record:
        index.lookup(key, verify_record=True)
    return StoreReference(entry, path, manifest)
