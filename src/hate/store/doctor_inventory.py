"""索引が壊れていても、実ディレクトリーから診断対象を収集する。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .atomic_write import compute_file_hash
from .doctor_types import DiagnosisFinding, DiagnosisSeverity
from .indexes import HardDQFinding, IndexLookupError, MultiIndexManager, StoreIndex
from .models import LocalStoreError, StoreManifest
from .references import resolve_store_reference


def finding(category: str, issue: str, path: Path, **details: object) -> DiagnosisFinding:
    return DiagnosisFinding(
        finding_id="", severity=DiagnosisSeverity.HARD_DQ, category=category,
        message=issue.replace("_", " "), path=str(path),
        remediation="Preserve the affected data; restore from a verified source or index snapshot.",
        diagnostics={"issue": issue, **details},
    )


@dataclass
class StoreInventory:
    copies: dict[tuple[str, str], Path] = field(default_factory=dict)
    indexes: dict[str, StoreIndex] = field(default_factory=dict)
    findings: list[DiagnosisFinding] = field(default_factory=list)


def _directories(path: Path, inventory: StoreInventory) -> list[Path]:
    try:
        children = sorted(path.iterdir())
    except OSError as exc:
        inventory.findings.append(finding("manifest", "directory_unreadable", path, error=str(exc)))
        return []
    directories = []
    for child in children:
        if child.is_dir() and child.resolve().parent == path.resolve():
            directories.append(child)
        else:
            inventory.findings.append(finding("manifest", "unexpected_store_entry", child))
    return directories


def scan_store(root: Path, *, run_id: str | None = None) -> StoreInventory:
    inventory = StoreInventory()
    runs_root = root / "runs"
    run_dirs = _directories(runs_root, inventory)
    for run_dir in run_dirs:
        if run_id is not None and run_dir.name != run_id:
            continue
        for bundle_dir in _directories(run_dir, inventory):
            inventory.copies[run_dir.name, bundle_dir.name] = bundle_dir

    # 新しいmanagerを使い、壊れた索引に以前のキャッシュが残ることを防ぐ。
    manifest_cache: dict[Path, StoreManifest] = {}
    for index in MultiIndexManager(root)._all_indexes():
        try:
            index.load()
        except (IndexLookupError, OSError) as exc:
            inventory.findings.append(finding("index", "index_unreadable", index.index_path, error=str(exc)))
            continue
        inventory.indexes[index.index_type] = index
        for entry in index.iter_entries():
            path = (root / entry.value).resolve()
            if not path.is_relative_to(root):
                inventory.findings.append(finding("index", "invalid_index_location", index.index_path, key=entry.key))
                continue
            parts = path.relative_to(root).parts
            copy_key = (parts[1], parts[2]) if len(parts) == 4 and parts[0] == "runs" else None
            if run_id is not None and (copy_key is None or copy_key[0] != run_id):
                continue
            if index.index_type in {"runs", "bundles"}:
                if copy_key is None or path.name != "qeg-bundle.json":
                    inventory.findings.append(finding("index", "invalid_bundle_reference", index.index_path, key=entry.key))
                    continue
                inventory.copies[copy_key] = path.parent
                expected_key = copy_key[0] if index.index_type == "runs" else copy_key[1]
                metadata_key = "bundle_id" if index.index_type == "runs" else "run_id"
                expected_metadata = copy_key[1] if index.index_type == "runs" else copy_key[0]
                if entry.key != expected_key or entry.metadata.get(metadata_key) != expected_metadata:
                    inventory.findings.append(finding("index", "index_identity_mismatch", index.index_path, key=entry.key))
            elif index.index_type == "artifacts":
                try:
                    reference = resolve_store_reference(index, entry.key, require_complete=True, manifest_cache=manifest_cache)
                    manifest_cache[reference.path.parent] = reference.manifest
                except (LocalStoreError, HardDQFinding, IndexLookupError, OSError) as exc:
                    inventory.findings.append(finding("index", "invalid_artifact_reference", index.index_path, key=entry.key, error=str(exc)))
            try:
                actual_hash = compute_file_hash(path)
            except OSError as exc:
                inventory.findings.append(finding("index", "index_record_unreadable", path, index_type=index.index_type, key=entry.key, error=str(exc)))
            else:
                if actual_hash.lower() != entry.hash.lower():
                    inventory.findings.append(finding("index", "index_hash_mismatch", path, index_type=index.index_type, key=entry.key))

    # run/bundle索引は最新コピーのalias。過去コピーとのパス一致は要求しない。
    for (stored_run, bundle_id), bundle_dir in sorted(inventory.copies.items()):
        for index_type, key in (("runs", stored_run), ("bundles", bundle_id)):
            loaded_index = inventory.indexes.get(index_type)
            if loaded_index is not None and key not in loaded_index.entries:
                inventory.findings.append(finding("index", "missing_index_entry", bundle_dir, index_type=index_type, key=key))
    return inventory
