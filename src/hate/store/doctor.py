"""ローカルストアを読み取り専用で診断する。未確定journalは通常操作と同じく先に復元する。"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from .compatibility import manifest_schema_findings
from .doctor_inventory import StoreInventory, finding, scan_store
from .doctor_types import DiagnosisFinding as DiagnosisFinding
from .doctor_types import DiagnosisSeverity as DiagnosisSeverity
from .doctor_types import DoctorError as DoctorError
from .doctor_types import DoctorReport as DoctorReport
from .doctor_types import build_report
from .indexes import HardDQFinding, IndexLookupError
from .integrity import verify_bundle_copy
from .local_store import LocalStore, LocalStoreError, read_store_manifest
from .locking import store_operation
from .references import resolve_store_reference
from .report_serialization import relative_diagnostics


def _diagnose_copy(bundle_dir: Path, inventory: StoreInventory | None = None) -> list[DiagnosisFinding]:
    manifest_path = bundle_dir / "store-manifest.json"
    try:
        manifest = read_store_manifest(bundle_dir)
    except LocalStoreError as exc:
        categories = {
            "legal_hold" if item.get("field", "").startswith("legal_hold") else "manifest"
            for item in exc.diagnostics
        } or {"manifest"}
        return [
            finding(category, "invalid_manifest", manifest_path, error=str(exc), validation=exc.diagnostics)
            for category in sorted(categories)
        ]

    findings = []
    for diagnostic in verify_bundle_copy(bundle_dir, manifest):
        issue = diagnostic["issue"]
        category = "artifact" if "artifact" in issue or "artifact_id" in diagnostic or issue == "hash_mismatch" else "manifest"
        affected_path = Path(diagnostic.get("path", bundle_dir))
        item = finding(category, issue, affected_path, **{key: value for key, value in diagnostic.items() if key not in {"issue", "path"}})
        item.artifact_id = diagnostic.get("artifact_id")
        findings.append(item)
    if inventory is not None:
        artifacts = inventory.indexes.get("artifacts")
        if artifacts is not None:
            for artifact_id in manifest.artifact_ids:
                entry = artifacts.entries.get(artifact_id)
                if entry is None:
                    findings.append(finding("index", "missing_index_entry", bundle_dir, index_type="artifacts", key=artifact_id))
                elif entry.hash.lower() != manifest.content_hashes.get(artifact_id, "").lower():
                    findings.append(finding("index", "index_record_hash_mismatch", bundle_dir, index_type="artifacts", key=artifact_id))
    for diagnostic in manifest_schema_findings(manifest):
        item = finding("schema", diagnostic["issue"], manifest_path, **{key: value for key, value in diagnostic.items() if key != "issue"})
        item.severity = DiagnosisSeverity.SOFT_DQ
        item.remediation = "Verify schema compatibility and migrate before replay."
        findings.append(item)
    for item in findings:
        item.bundle_id = manifest.bundle_id
        item.diagnostics["run_id"] = manifest.run_id
    return findings


def _report(
    root: Path, scope: str, findings: list[DiagnosisFinding], *,
    bundle_id: str | None = None, run_id: str | None = None, copies: int = 1,
) -> DoctorReport:
    # 正規化した内容でIDを付け、オブジェクトの絶対パスと元の所見は保持する。
    normalized = relative_diagnostics([item.to_dict() for item in findings], root)
    ordered = sorted(
        zip(normalized, findings, strict=True),
        key=lambda pair: json.dumps({**pair[0], "finding_id": ""}, sort_keys=True, ensure_ascii=False),
    )
    findings = [replace(item, finding_id=f"{bundle_id or scope}_F{number:03d}") for number, (_, item) in enumerate(ordered)]
    count = sum(item.severity == DiagnosisSeverity.HARD_DQ for item in findings)
    return build_report(
        bundle_id, scope, findings, f"Checked {copies} stored bundle copies; {count} hard-DQ findings.",
        run_id=run_id, store_root=root,
    )


@store_operation
def diagnose_bundle(store: LocalStore, bundle_id: str, *, run_id: str | None = None) -> DoctorReport:
    """指定コピーを診断する。run省略時は従来のbundle索引aliasを使う。"""
    try:
        if run_id is None:
            store.index_manager.bundles_index.load()
            entry = store.index_manager.bundles_index.lookup(bundle_id, verify_record=False)
            bundle_dir = (store.store_root / entry.value).resolve().parent
        else:
            bundle_dir = (store.store_root / "runs" / run_id / bundle_id).resolve()
        if bundle_dir.parent.parent != store.store_root / "runs" or bundle_dir.name != bundle_id:
            raise LocalStoreError("Invalid bundle location", "doctor", bundle_dir)
    except (LocalStoreError, HardDQFinding, IndexLookupError, OSError) as exc:
        return _report(store.store_root, "single_bundle", [finding(
            "index", "bundle_unresolved", store.store_root, error=str(exc), validation=getattr(exc, "diagnostics", []),
        )], bundle_id=bundle_id, run_id=run_id, copies=0)
    findings = _diagnose_copy(bundle_dir)
    if run_id is None:
        try:
            resolve_store_reference(store.index_manager.bundles_index, bundle_id, verify_record=True)
        except (LocalStoreError, HardDQFinding, IndexLookupError, OSError) as exc:
            item = finding(
                "index", "invalid_bundle_reference", store.index_manager.bundles_index.index_path,
                key=bundle_id, error=str(exc), validation=getattr(exc, "diagnostics", []), run_id=bundle_dir.parent.name,
            )
            item.bundle_id = bundle_id
            findings.append(item)
    return _report(store.store_root, "single_bundle", findings, bundle_id=bundle_id, run_id=bundle_dir.parent.name)


def _diagnose_inventory(root: Path, inventory: StoreInventory, scope: str, *, run_id: str | None = None) -> DoctorReport:
    findings = list(inventory.findings)
    for (stored_run, bundle_id), bundle_dir in sorted(inventory.copies.items()):
        for item in _diagnose_copy(bundle_dir, inventory):
            item.bundle_id = bundle_id
            item.diagnostics["run_id"] = stored_run
            findings.append(item)
    return _report(root, scope, findings, run_id=run_id, copies=len(inventory.copies))


@store_operation
def diagnose_run(store: LocalStore, run_id: str) -> DoctorReport:
    """未完了・索引未登録を含むrunの全コピーを診断する。"""
    inventory = scan_store(store.store_root, run_id=run_id)
    if not inventory.copies:
        inventory.findings.append(finding("manifest", "run_has_no_bundles", store.store_root / "runs" / run_id))
    return _diagnose_inventory(store.store_root, inventory, "run", run_id=run_id)


@store_operation
def diagnose_full_store(store: LocalStore) -> DoctorReport:
    """独立した各索引とruns配下の実体を照合し、壊れた索引があっても診断を続ける。"""
    return _diagnose_inventory(store.store_root, scan_store(store.store_root), "full_store")
