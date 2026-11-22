"""索引を退避し、未確定の取り込み・索引補完を復元する。呼出側はstore lockを保持する。"""

from __future__ import annotations

import os
import shutil
import warnings
from pathlib import Path
from types import TracebackType
from typing import Any, Literal
from uuid import uuid4

from .atomic_write import AtomicWriteError, atomic_write_bytes, atomic_write_json, compute_file_hash
from .indexes import MultiIndexManager
from .json_io import strict_json_loads
from .models import LocalStoreError
from .versioning import validate_store_version


class StoreRecoveryError(LocalStoreError):
    """退避情報を保持して、復元完了まで通常操作を止める。"""


def _inside(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()) or resolved == root.resolve():
        raise StoreRecoveryError("recovery path is outside store", "recovery", path)
    return resolved


def _stage(root: Path) -> Path:
    stage = _inside(root, root / "migrations" / "pending-import")
    if stage.parent != (root / "migrations").resolve():
        raise StoreRecoveryError("unexpected recovery directory", "recovery", stage)
    return stage


def _archive(root: Path, stage: Path) -> Path:
    destination = _inside(root, root / "quarantine" / f"import-{uuid4().hex}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(_inside(root, stage), destination)
    return destination


def _discard_committed(root: Path, stage: Path) -> None:
    if _inside(root, stage) != _stage(root):
        raise StoreRecoveryError("unexpected recovery directory", "recovery", stage)
    try:
        shutil.rmtree(stage)
    except OSError as exc:
        warnings.warn(f"committed import recovery files retained: {stage}: {exc}", RuntimeWarning, stacklevel=2)


def _read_journal(root: Path, stage: Path) -> dict[str, Any]:
    data = strict_json_loads((stage / "journal.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or type(data.get("version")) is not int or data.get("version") not in {1, 2} or data.get("state") not in {"pending", "committed"}:
        raise ValueError("invalid import journal")
    if data["version"] == 2 and data.get("operation") != "indexes":
        raise ValueError("invalid index transaction operation")
    bundle = _inside(root / "runs", root / data["bundle_dir"])
    if len(bundle.relative_to((root / "runs").resolve()).parts) < 2:
        raise ValueError("invalid bundle directory in journal")
    expected = {index.index_path.name for index in MultiIndexManager(root)._all_indexes()}
    records = data["indexes"]
    if not isinstance(records, list) or len(records) != len(expected):
        raise ValueError("invalid index snapshot inventory")
    if {item["name"] for item in records} != expected:
        raise ValueError("unknown index in snapshot")
    if any(type(item["exists"]) is not bool for item in records):
        raise ValueError("invalid index existence state")
    if type(data["bundle_existed"]) is not bool:
        raise ValueError("invalid bundle existence state")
    return data


def recover_pending_import(root: Path) -> Path | None:
    validate_store_version(root)
    stage = _stage(root)
    if not stage.exists():
        return None
    try:
        journal_path = stage / "journal.json"
        if not journal_path.exists():
            # journalの公開前は本体・索引を変更していない。
            return _archive(root, stage)
        journal = _read_journal(root, stage)
        if journal["state"] == "committed":
            _discard_committed(root, stage)
            return None
        # 復元に必要な全バックアップを確認してから対象へ書き込む。
        for item in journal["indexes"]:
            if item["exists"]:
                backup = _inside(root, stage / "before" / item["name"])
                if compute_file_hash(backup) != item["hash"]:
                    raise ValueError(f"index backup hash mismatch: {item['name']}")
        bundle = _inside(root / "runs", root / journal["bundle_dir"])
        failed_bundle = _inside(root, stage / "failed-bundle")
        if journal["version"] == 1 and bundle.exists():
            if failed_bundle.exists():
                # 前回の復元が既存の空ディレクトリーを戻した後に中断した場合。
                if not journal["bundle_existed"] or any(bundle.iterdir()):
                    raise ValueError("both pending and quarantined bundle exist")
            else:
                os.replace(bundle, failed_bundle)
        for item in journal["indexes"]:
            target = _inside(root, root / "indexes" / item["name"])
            if item["exists"]:
                atomic_write_bytes(target, (stage / "before" / item["name"]).read_bytes(), root)
            else:
                target.unlink(missing_ok=True)
        if journal["version"] == 1 and journal["bundle_existed"]:
            bundle.mkdir(parents=True, exist_ok=True)
        return _archive(root, stage)
    except StoreRecoveryError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AtomicWriteError) as exc:
        raise StoreRecoveryError(
            f"import recovery required: {exc}", "recovery", stage,
            [{"issue": "recovery_required", "recovery_path": str(stage)}],
        ) from exc


class ImportTransaction:
    """index_onlyでは索引だけを復元し、保存済みbundleの配置・内容を保持する。"""

    def __init__(self, root: Path, bundle_dir: Path, *, index_only: bool = False) -> None:
        self.root = root.resolve()
        self.bundle_dir = _inside(self.root / "runs", bundle_dir)
        self.stage = _stage(self.root)
        self.journal: dict[str, Any] = {}
        self.committed = False
        self.quarantine_path: Path | None = None
        self.index_only = index_only

    def __enter__(self) -> ImportTransaction:
        validate_store_version(self.root)
        if not self.index_only and self.bundle_dir.exists() and any(self.bundle_dir.iterdir()):
            raise LocalStoreError("incomplete bundle requires recovery before retry", "import_bundle", self.bundle_dir)
        self.stage.mkdir(parents=True)
        try:
            snapshots = []
            for index in MultiIndexManager(self.root)._all_indexes():
                exists = index.index_path.exists()
                item: dict[str, Any] = {"name": index.index_path.name, "exists": exists}
                if exists:
                    backup = self.stage / "before" / index.index_path.name
                    atomic_write_bytes(backup, index.index_path.read_bytes(), self.root)
                    item["hash"] = compute_file_hash(backup)
                snapshots.append(item)
            self.journal = {
                "version": 1, "state": "pending",
                "bundle_dir": str(self.bundle_dir.relative_to(self.root)),
                "bundle_existed": self.bundle_dir.exists(), "indexes": snapshots,
            }
            if self.index_only:
                # 旧readerが完成済みbundleを隔離しないよう、未対応版として拒否させる。
                self.journal.update(version=2, operation="indexes")
            atomic_write_json(self.stage / "journal.json", self.journal, self.root)
        except BaseException:
            self.quarantine_path = recover_pending_import(self.root)
            raise
        return self

    def commit(self) -> None:
        validate_store_version(self.root)
        journal = {**self.journal, "state": "committed"}
        try:
            atomic_write_json(self.stage / "journal.json", journal, self.root)
        except AtomicWriteError as exc:
            if any(item.get("published") for item in exc.diagnostics):
                self.committed = True
                raise StoreRecoveryError(
                    "import commit durability uncertain; recovery metadata retained", "recovery", self.stage,
                    [{"issue": "commit_durability_uncertain", "committed": True}],
                ) from exc
            raise
        self.committed = True
        _discard_committed(self.root, self.stage)

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None,
    ) -> Literal[False]:
        if not self.committed:
            # 版情報が変わったストアでは、失敗記録の追記も復元も開始しない。
            validate_store_version(self.root)
            if exc is not None:
                self.journal["failure"] = {
                    "exception": type(exc).__name__, "message": str(exc), "phase": getattr(exc, "phase", "unknown"),
                }
                try:
                    atomic_write_json(self.stage / "journal.json", self.journal, self.root)
                except (AtomicWriteError, OSError) as journal_error:
                    warnings.warn(f"import failure details could not be saved: {journal_error}", RuntimeWarning, stacklevel=2)
            self.quarantine_path = recover_pending_import(self.root)
            if exc is None:
                raise LocalStoreError("import transaction was not committed", "import_bundle", self.stage)
        return False
