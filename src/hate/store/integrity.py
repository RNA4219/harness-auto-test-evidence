"""保存済みrunの整合性を、ファイルを書き換えずに検証する。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .atomic_write import compute_file_hash
from .bundle_validation import prepare_bundle
from .compatibility import manifest_schema_findings
from .indexes import HardDQFinding, IndexEntry, IndexLookupError, StoreIndex
from .json_io import strict_json_loads
from .models import LocalStoreError, StoreManifest
from .references import resolve_store_reference

if TYPE_CHECKING:
    from .local_store import LocalStore


def _verify_index(
    index: StoreIndex, key: str, expected_hash: str | None, diagnostics: list[dict[str, Any]],
    *, manifest_cache: dict[Path, StoreManifest] | None = None,
) -> IndexEntry | None:
    try:
        reference = resolve_store_reference(
            index, key, verify_record=True, require_complete=True, manifest_cache=manifest_cache,
        )
        entry = reference.entry
        if manifest_cache is not None:
            manifest_cache[reference.path.parent] = reference.manifest
    except IndexLookupError:
        diagnostics.append({"issue": "missing_index_entry", "index_type": index.index_type, "key": key})
    except (LocalStoreError, HardDQFinding, OSError) as exc:
        diagnostics.append({
            "issue": "invalid_index_reference", "index_type": index.index_type, "key": key, "error": str(exc),
            "validation": getattr(exc, "diagnostics", []),
        })
    else:
        if expected_hash is not None and entry.hash.lower() != expected_hash.lower():
            diagnostics.append({
                "issue": "index_record_hash_mismatch", "index_type": index.index_type,
                "key": key, "expected": expected_hash, "actual": entry.hash,
            })
        return entry
    return None


def _verify_bundle(
    path: Path, manifest: StoreManifest, expected_hash: str | None, diagnostics: list[dict[str, Any]],
    *, check_artifacts: bool = True,
) -> None:
    if not path.is_file():
        diagnostics.append({"issue": "missing_bundle", "expected_path": str(path)})
        return
    try:
        actual_hash = compute_file_hash(path)
        payload = strict_json_loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("bundle must be a JSON object")
        prepared = prepare_bundle(payload, path)
        bundle_id = prepared.bundle_id
    except LocalStoreError as exc:
        diagnostics.extend({**item, "path": str(path)} for item in exc.diagnostics)
        return
    except (OSError, ValueError) as exc:
        diagnostics.append({"issue": "bundle_unreadable", "path": str(path), "error": str(exc)})
        return
    if (expected_hash is not None and actual_hash.lower() != expected_hash.lower()) or bundle_id != manifest.bundle_id:
        diagnostics.append({
            "issue": "bundle_hash_mismatch", "expected": expected_hash, "actual": actual_hash,
            "expected_bundle_id": manifest.bundle_id, "actual_bundle_id": bundle_id,
        })
    # 一覧とhashが両方消えていても、検証済みbundle本体から欠落を検出する。
    manifest_hashes = {key: value.lower() for key, value in manifest.content_hashes.items()}
    if check_artifacts and (set(manifest.artifact_ids) != set(prepared.artifacts) or manifest_hashes != prepared.content_hashes):
        diagnostics.append({"issue": "bundle_artifact_manifest_mismatch"})


def _verify_artifacts(
    bundle_dir: Path, manifest: StoreManifest, index: StoreIndex | None, diagnostics: list[dict[str, Any]],
) -> None:
    manifest_cache = {bundle_dir.resolve(): manifest}
    for artifact_id in sorted(set(manifest.artifact_ids) | set(manifest.content_hashes)):
        expected_hash = manifest.content_hashes.get(artifact_id)
        if expected_hash is None:
            diagnostics.append({"issue": "missing_artifact_hash", "artifact_id": artifact_id})
        if artifact_id not in manifest.artifact_ids:
            diagnostics.append({"issue": "unlisted_artifact_hash", "artifact_id": artifact_id})
        path = bundle_dir / f"{artifact_id}.json"
        if not path.is_file():
            diagnostics.append({"issue": "missing_artifact", "artifact_id": artifact_id, "expected_path": str(path)})
        else:
            try:
                actual_hash = compute_file_hash(path)
            except OSError as exc:
                diagnostics.append({"issue": "artifact_unreadable", "artifact_id": artifact_id, "error": str(exc)})
            else:
                if expected_hash is not None and actual_hash.lower() != expected_hash.lower():
                    diagnostics.append({
                        "issue": "hash_mismatch", "artifact_id": artifact_id,
                        "expected": expected_hash, "actual": actual_hash,
                    })
        if index is not None:
            _verify_index(index, artifact_id, expected_hash, diagnostics, manifest_cache=manifest_cache)


def verify_bundle_copy(
    bundle_dir: Path, manifest: StoreManifest, *, index: StoreIndex | None = None,
) -> list[dict[str, Any]]:
    """runの最新aliasに依存せず、履歴上の保存実体を検証する。"""
    diagnostics: list[dict[str, Any]] = []
    if manifest.completed is not True:
        diagnostics.append({"issue": "manifest_not_complete"})
    if manifest.run_id != bundle_dir.parent.name or manifest.bundle_id != bundle_dir.name:
        diagnostics.append({"issue": "manifest_path_mismatch"})
    _verify_bundle(bundle_dir / "qeg-bundle.json", manifest, None, diagnostics)
    _verify_artifacts(bundle_dir, manifest, index, diagnostics)
    return diagnostics


def verify_bundle_alias(store: LocalStore, manifest: StoreManifest, diagnostics: list[dict[str, Any]]) -> None:
    """共有bundle索引の参照先自身のハッシュとcanonical IDを確認する。"""
    entry = _verify_index(store.index_manager.bundles_index, manifest.bundle_id, None, diagnostics)
    if entry is not None:
        _verify_bundle(store.store_root / entry.value, manifest, entry.hash, diagnostics, check_artifacts=False)


def verify_saved_import(store: LocalStore, bundle_dir: Path, manifest: StoreManifest) -> list[dict[str, Any]]:
    unsupported = manifest_schema_findings(manifest)
    if unsupported:
        return unsupported
    diagnostics = verify_bundle_copy(bundle_dir, manifest)
    manifest_cache = {bundle_dir.resolve(): manifest}
    try:
        store.index_manager.load_all()
    except (IndexLookupError, OSError) as exc:
        diagnostics.append({"issue": "index_unreadable", "error": str(exc)})
        return diagnostics
    verify_bundle_alias(store, manifest, diagnostics)
    run_entry = _verify_index(
        store.index_manager.runs_index, manifest.run_id, None, diagnostics, manifest_cache=manifest_cache,
    )
    if run_entry is not None:
        reference = resolve_store_reference(store.index_manager.runs_index, manifest.run_id, manifest_cache=manifest_cache)
        if reference.path.parent != bundle_dir.resolve():
            diagnostics.extend(manifest_schema_findings(reference.manifest))
            diagnostics.extend(verify_bundle_copy(reference.path.parent, reference.manifest))
    for artifact_id in manifest.artifact_ids:
        _verify_index(
            store.index_manager.artifacts_index, artifact_id, manifest.content_hashes.get(artifact_id), diagnostics,
            manifest_cache=manifest_cache,
        )
    return diagnostics


def verify_run_integrity(store: LocalStore, run_id: str) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    try:
        store.index_manager.load_all()
        reference = resolve_store_reference(store.index_manager.runs_index, run_id)
    except (LocalStoreError, IndexLookupError, HardDQFinding, OSError) as exc:
        diagnostics.append({"issue": "invalid_run_reference", "run_id": run_id, "error": str(exc), "validation": getattr(exc, "diagnostics", [])})
        return _integrity_result(run_id, diagnostics)
    manifest, entry, bundle_path = reference.manifest, reference.entry, reference.path
    if manifest.completed is not True:
        diagnostics.append({"issue": "manifest_not_complete", "run_id": run_id})
    if manifest.run_id != run_id or entry.metadata.get("bundle_id") != manifest.bundle_id:
        diagnostics.append({"issue": "manifest_index_mismatch", "run_id": run_id})
    _verify_bundle(bundle_path, manifest, entry.hash, diagnostics)
    # 同じcanonical IDでもJSONキー順により保存バイト列は異なり得る。
    verify_bundle_alias(store, manifest, diagnostics)
    _verify_artifacts(bundle_path.parent, manifest, store.index_manager.artifacts_index, diagnostics)
    if manifest.legal_hold.get("status") == "active":
        diagnostics.append({"info": "legal_hold_active", "reason": manifest.legal_hold.get("reason")})
    return _integrity_result(run_id, diagnostics)


def _integrity_result(run_id: str, diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "HATE/v1", "record_type": "integrity_verification", "run_id": run_id,
        "integrity_ok": not any("issue" in item for item in diagnostics), "diagnostics": diagnostics,
    }
