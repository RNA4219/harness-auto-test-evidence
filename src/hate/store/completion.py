"""manifestの完了候補を検証し、保存が成功してから呼出側へ確定状態を返す。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import atomic_write as writer
from .compatibility import manifest_schema_findings
from .integrity import verify_bundle_copy
from .manifest_validation import manifest_errors
from .models import StoreManifest
from .versioning import validate_store_version


def complete_manifest_write(
    manifest_path: Path, manifest_content: dict[str, Any], store_root: Path, bundle_files: list[Path],
) -> dict[str, Any]:
    errors = manifest_errors(manifest_content)
    if errors:
        raise writer.AtomicWriteError("Invalid store manifest", manifest_path, "manifest", errors)
    root = store_root.resolve()
    validate_store_version(root)
    writer._validate_path_within_store(manifest_path, root)
    expected = root / "runs" / manifest_content["run_id"] / manifest_content["bundle_id"] / "store-manifest.json"
    if manifest_path.resolve() != expected.resolve():
        raise writer.AtomicWriteError(
            "Manifest location does not match its identity", manifest_path, "manifest",
            [{"issue": "manifest_path_mismatch", "expected_path": str(expected)}],
        )
    # 補助ファイルの指定も確認するが、必須ファイルは呼出側の一覧から独立して検証する。
    diagnostics: list[dict[str, Any]] = []
    for path in bundle_files:
        writer._validate_path_within_store(path, root)
        try:
            if not path.is_file():
                diagnostics.append({"issue": "missing_or_non_file_bundle_member", "path": str(path)})
        except OSError as exc:
            diagnostics.append({"issue": "bundle_member_unreadable", "path": str(path), "error": str(exc)})
    status = manifest_content.get("import_status", {})
    candidate = {
        **manifest_content, "completed": True,
        "import_status": {**status, "phase": "completed", "diagnostics": status.get("diagnostics", [])},
    }
    manifest = StoreManifest.from_dict(candidate)
    unsupported = manifest_schema_findings(manifest)
    if unsupported:
        raise writer.AtomicWriteError("Stored schema is unsupported", manifest_path, "manifest", unsupported)
    diagnostics.extend(verify_bundle_copy(manifest_path.resolve().parent, manifest))
    if diagnostics:
        raise writer.AtomicWriteError("Bundle verification failed before completion", manifest_path, "manifest", diagnostics)
    validate_store_version(root)
    writer.atomic_write_json(manifest_path, candidate, root)
    # 公開済みでも同期エラーなら上へ例外を返す。呼出側の成功状態はここでのみ更新する。
    manifest_content.clear()
    manifest_content.update(candidate)
    return manifest_content
