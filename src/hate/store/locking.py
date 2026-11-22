"""プロセス終了時にOSが解放する、ローカルストア操作の排他制御。"""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, Concatenate, ParamSpec, TypeVar

from .models import LocalStoreError

if TYPE_CHECKING:
    from .local_store import LocalStore

_LOCAL = threading.local()
P = ParamSpec("P")
R = TypeVar("R")


def _file_lock(stream: BinaryIO, *, release: bool = False) -> None:
    stream.seek(0)
    if sys.platform == "win32":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK if release else msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN if release else fcntl.LOCK_EX | fcntl.LOCK_NB)


@contextmanager
def store_lock(root: Path) -> Iterator[bool]:
    root = root.resolve()
    held: set[Path] = getattr(_LOCAL, "held", set())
    if root in held:
        yield False
        return
    path = root / "locks" / "store.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if path.stat().st_size == 0:
            stream.write(b"\0")
            stream.flush()
        try:
            _file_lock(stream)
        except OSError as exc:
            raise LocalStoreError("store busy or lock unavailable", "lock", path) from exc
        held.add(root)
        _LOCAL.held = held
        try:
            yield True
        finally:
            held.remove(root)
            _file_lock(stream, release=True)


def store_operation(method: Callable[Concatenate[LocalStore, P], R]) -> Callable[Concatenate[LocalStore, P], R]:
    @wraps(method)
    def protected(store: LocalStore, /, *args: P.args, **kwargs: P.kwargs) -> R:
        with store_session(store.store_root):
            return method(store, *args, **kwargs)

    return protected


@contextmanager
def store_session(root: Path) -> Iterator[None]:
    """版情報と復元を確認した操作範囲。単にlockを持つ状態とは区別する。"""
    from .transaction import recover_pending_import
    from .versioning import validate_store_version

    root = root.resolve()
    sessions: set[Path] = getattr(_LOCAL, "sessions", set())
    if root in sessions:
        yield
        return
    # 未対応ストアにlockディレクトリーを新設する前に拒否する。
    validate_store_version(root)
    with store_lock(root):
        validate_store_version(root)
        recover_pending_import(root)
        sessions.add(root)
        _LOCAL.sessions = sessions
        try:
            yield
        finally:
            sessions.remove(root)
