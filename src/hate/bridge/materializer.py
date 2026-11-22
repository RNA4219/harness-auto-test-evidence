"""Fail-closed HATE-bridge result materializer."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .schemas import BridgeValidationError, validate_bridge_record


class BridgeMaterializeError(ValueError):
    pass


class BridgeRecoveryError(BridgeMaterializeError):
    """復元にも失敗した場合、一時領域のバックアップを保持する。"""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BridgeMaterializeError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BridgeMaterializeError(f"JSON root must be an object: {path}")
    return value


def _validate_pair(request: dict[str, Any], result: dict[str, Any]) -> None:
    try:
        validate_bridge_record(request, "bridge-request")
        validate_bridge_record(result, "bridge-result")
    except BridgeValidationError as exc:
        raise BridgeMaterializeError(str(exc)) from exc
    for field in ("bridge_id", "owner", "sourceRefs"):
        if result.get(field) != request.get(field):
            raise BridgeMaterializeError(f"request/result {field} mismatch")
    if result.get("status") != "completed":
        raise BridgeMaterializeError("only completed bridge results can be materialized")
    expected = set(request["expected_output_types"])
    actual = {item["record_type"] for item in result["output_refs"]}
    missing = sorted(expected - actual)
    if missing:
        raise BridgeMaterializeError(f"bridge result is missing expected output types: {', '.join(missing)}")


def _output_sources(result: dict[str, Any], result_path: Path, out_dir: Path) -> list[tuple[Path, str, str]]:
    sources: list[tuple[Path, str, str]] = []
    target_names: set[str] = set()
    if out_dir.exists() and not out_dir.is_dir():
        raise BridgeMaterializeError(f"output path is not a directory: {out_dir}")
    for output in result["output_refs"]:
        source = Path(output["path"])
        if not source.is_absolute():
            source = result_path.parent / source
        target_name = output["target_name"]
        if (
            target_name in {"", ".", ".."}
            or PurePosixPath(target_name).name != target_name
            or PureWindowsPath(target_name).name != target_name
            or any(char in target_name for char in '<>:"/\\|?*\x00')
            or target_name.endswith((" ", "."))
        ):
            raise BridgeMaterializeError(f"unsafe target_name: {target_name}")
        key = target_name.casefold()
        if key in target_names:
            raise BridgeMaterializeError(f"duplicate target_name: {target_name}")
        target_names.add(key)
        if (out_dir / target_name).is_dir():
            raise BridgeMaterializeError(f"target conflicts with a directory: {target_name}")
        if not source.is_file():
            raise BridgeMaterializeError(f"bridge output does not exist: {source}")
        sources.append((source, target_name, output["sha256"]))
    return sources


def _publish(stage: Path, out_dir: Path, names: list[str]) -> None:
    backups = stage / "backups"
    backups.mkdir()
    existed = out_dir.exists()
    recovery = {
        "out_dir": str(out_dir.resolve()),
        "directory_existed": existed,
        "targets": [
            {"name": name, "existed": (out_dir / name).exists() or (out_dir / name).is_symlink()}
            for name in names
        ],
    }
    (stage / "recovery.json").write_text(json.dumps(recovery, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    saved: list[str] = []
    published: list[str] = []
    created = False
    try:
        out_dir.mkdir(exist_ok=True)
        created = not existed
        for name in names:
            target = out_dir / name
            if target.is_dir():
                raise IsADirectoryError(f"target conflicts with a directory: {target}")
            if target.exists() or target.is_symlink():
                os.replace(target, backups / name)
                saved.append(name)
            os.replace(stage / "files" / name, target)
            published.append(name)
    except BaseException as exc:
        recovery_errors = []
        for name in reversed(names):
            try:
                if name in saved:
                    os.replace(backups / name, out_dir / name)
                elif name in published:
                    (out_dir / name).unlink()
            except OSError as recovery_exc:
                recovery_errors.append(f"{name}: {recovery_exc}")
        if created and not recovery_errors:
            try:
                out_dir.rmdir()
            except OSError as recovery_exc:
                recovery_errors.append(str(recovery_exc))
        if recovery_errors:
            raise BridgeRecoveryError(
                f"bridge publish failed ({exc}); rollback incomplete: {'; '.join(recovery_errors)}; "
                f"recovery files retained at {stage}"
            ) from exc
        if not isinstance(exc, OSError):
            raise
        raise BridgeMaterializeError(f"bridge publish failed; previous outputs restored: {exc}") from exc


def materialize_bridge_result(request_path: Path, result_path: Path, out_dir: Path) -> dict[str, Any]:
    request = _load(request_path)
    result = _load(result_path)
    _validate_pair(request, result)
    sources = _output_sources(result, result_path.resolve(), out_dir)
    parent = out_dir.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".hate-materialize-", dir=parent))
    preserve_stage = False
    try:
        files = stage / "files"
        files.mkdir()
        for source, target_name, expected_hash in sources:
            staged = files / target_name
            shutil.copyfile(source, staged)
            with staged.open("rb") as stream:
                actual_hash = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual_hash != expected_hash:
                raise BridgeMaterializeError(f"bridge output hash mismatch: {source}")
        _publish(stage, out_dir, [name for _, name, _ in sources])
    except BridgeRecoveryError:
        preserve_stage = True
        raise
    except BridgeMaterializeError:
        raise
    except OSError as exc:
        raise BridgeMaterializeError(f"cannot materialize bridge outputs: {exc}") from exc
    except BaseException:
        preserve_stage = True
        raise
    finally:
        if not preserve_stage:
            # 削除対象を、今回作成した一時領域の親と名前で確認する。
            if stage.resolve().parent != parent or not stage.name.startswith(".hate-materialize-"):
                raise BridgeRecoveryError(f"unexpected staging path; retained at {stage}")
            try:
                shutil.rmtree(stage)
            except OSError as exc:
                print(f"HATE-W-BRIDGE: staging cleanup failed; retained at {stage}: {exc}", file=sys.stderr)

    return {
        "status": "materialized",
        "bridge_id": request["bridge_id"],
        "canonical_owner": request["owner"],
        "generated": [target for _, target, _ in sources],
        "out_dir": str(out_dir),
    }


def dispatch_materialize(args: Any) -> int:
    if getattr(args, "bridge_command", None) != "materialize":
        print("HATE-E-BRIDGE: unsupported bridge command", file=sys.stderr)
        return 2
    try:
        result = materialize_bridge_result(args.request, args.result, args.out)
    except (BridgeMaterializeError, OSError) as exc:
        print(f"HATE-E-BRIDGE: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0
