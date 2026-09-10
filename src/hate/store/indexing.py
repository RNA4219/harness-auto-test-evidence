"""現行bundle配置の索引生成と、保存済みコピーからの参照復元。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .atomic_write import compute_file_hash
from .compatibility import manifest_schema_findings
from .indexes import MultiIndexManager, StoreIndex
from .integrity import verify_bundle_copy
from .locking import store_session
from .models import LocalStoreError, StoreManifest
from .references import resolve_store_reference
from .timestamps import timestamp_key
from .transaction import ImportTransaction


def _location(root: Path, directory: Path) -> Path:
    directory = directory.resolve()
    if directory.parent.parent != root / "runs":
        raise LocalStoreError("bundle must be under runs/<run_id>/<bundle_id>", "build_indexes", directory)
    return directory


def _verified_copy(root: Path, directory: Path, cache: dict[Path, StoreManifest]) -> StoreManifest:
    from .local_store import read_store_manifest

    directory = _location(root, directory)
    if directory not in cache:
        manifest = read_store_manifest(directory, require_complete=True)
        unsupported = manifest_schema_findings(manifest)
        if unsupported:
            raise LocalStoreError("Stored schema is unsupported", "build_indexes", directory, unsupported)
        diagnostics = verify_bundle_copy(directory, manifest)
        if diagnostics:
            raise LocalStoreError("bundle failed integrity verification", "build_indexes", directory, diagnostics)
        cache[directory] = manifest
    return cache[directory]


def _verified_alias(index: StoreIndex, key: str, cache: dict[Path, StoreManifest]) -> Path:
    # cacheは保存実体の検証済みコピー専用。参照解決の読込だけで埋めない。
    reference = resolve_store_reference(
        index, key, operation="build_indexes", verify_record=True, require_complete=True, manifest_cache=cache,
    )
    _verified_copy(index.store_root, reference.path.parent, cache)
    return reference.path.parent


def populate_bundle_indexes(
    manager: MultiIndexManager, bundle_dir: Path, run_id: str, bundle_id: str,
    content_hashes: dict[str, str], *, preserve_existing: bool = False,
    verified: dict[Path, StoreManifest] | None = None,
) -> None:
    """読込済みmanagerを更新する。呼出側が検証・排他・transaction・保存を担う。"""
    cache = {} if verified is None else verified
    relative = bundle_dir.relative_to(manager.store_root)
    bundle_path = relative / "qeg-bundle.json"
    bundle_hash = compute_file_hash(bundle_dir / "qeg-bundle.json")
    entries = [
        (manager.runs_index, run_id, bundle_path, bundle_hash, {"bundle_id": bundle_id}),
        (manager.bundles_index, bundle_id, bundle_path, bundle_hash, {"run_id": run_id}),
    ]
    entries.extend(
        (manager.artifacts_index, artifact_id, relative / f"{artifact_id}.json", digest,
         {"run_id": run_id, "bundle_id": bundle_id})
        for artifact_id, digest in content_hashes.items()
    )
    for index, key, path, digest, metadata in entries:
        if preserve_existing and key in index.entries:
            _verified_alias(index, key, cache)
        else:
            index.add_entry(key, str(path), digest, metadata)


def _latest_run_copy(root: Path, directory: Path, cache: dict[Path, StoreManifest]) -> Path:
    from .local_store import read_store_manifest

    candidates = []
    for path in directory.parent.glob("*/store-manifest.json"):
        _location(root, path.parent)
        manifest = read_store_manifest(path.parent)
        if manifest.completed:
            candidates.append((timestamp_key(manifest.created_at, operation="build_indexes", path=path), path.parent))
    latest = max(stamp for stamp, _ in candidates)
    matches = [path for stamp, path in candidates if stamp == latest]
    if len(matches) != 1:
        raise LocalStoreError("latest run is ambiguous: equal manifest timestamps", "build_indexes", directory.parent)
    _verified_copy(root, matches[0], cache)
    return matches[0]


def build_indexes_for_bundle(store_root: Path, bundle_dir: Path, manifest: dict[str, Any]) -> dict[str, str]:
    """検証済みの保存実体から索引を補完する。既存aliasと証跡は保持する。"""
    root = store_root.resolve()
    directory = _location(root, bundle_dir)
    supplied = StoreManifest.from_dict(manifest)
    with store_session(root):
        cache: dict[Path, StoreManifest] = {}
        saved = _verified_copy(root, directory, cache)
        if saved.to_dict() != supplied.to_dict():
            raise LocalStoreError("supplied manifest does not match saved manifest", "build_indexes", directory)
        manager = MultiIndexManager(root)
        manager.load_all()
        if saved.run_id in manager.runs_index.entries:
            run_copy = _verified_alias(manager.runs_index, saved.run_id, cache)
        else:
            run_copy = _latest_run_copy(root, directory, cache)
        for target in dict.fromkeys([run_copy, directory]):
            item = _verified_copy(root, target, cache)
            populate_bundle_indexes(
                manager, target, item.run_id, item.bundle_id, item.content_hashes,
                preserve_existing=True, verified=cache,
            )
        with ImportTransaction(root, directory, index_only=True) as transaction:
            hashes = manager.save_all()
            transaction.commit()
        return hashes
