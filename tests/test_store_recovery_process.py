from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from hate.store import LocalStore, LocalStoreError

pytestmark = pytest.mark.subprocess


def _process(code, *args):
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    return subprocess.run([sys.executable, "-B", "-c", code, *map(str, args)], env=env, capture_output=True, text=True, timeout=20)


def _store(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps({"nodes": [{"id": "test-1", "kind": "test_result"}]}), encoding="utf-8")
    hold = dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    store = LocalStore(tmp_path / "store")
    assert store.import_bundle(source, "original", "revision-1", hold).success
    return store, source


@pytest.mark.parametrize("publish_manifest", [False, True])
def test_next_open_recovers_import_interrupted_by_process_exit(tmp_path, publish_manifest):
    store, source = _store(tmp_path)
    index_dir = store.store_root / "indexes"
    before = {path.name: path.read_bytes() for path in index_dir.glob("*.jsonl")}
    code = """
import os, sys
from pathlib import Path
import hate.store.local_store as module
store = module.LocalStore(Path(sys.argv[1]))
complete = module.complete_manifest_write
def exit_at_manifest(**kwargs):
    if sys.argv[3] == 'True':
        complete(**kwargs)
    os._exit(19)
module.complete_manifest_write = exit_at_manifest
store.import_bundle(Path(sys.argv[2]), 'interrupted', 'revision-2', dict(status='none', reason='test', held_since='2026-09-10T00:00:00Z', authorized_by='test'))
"""
    result = _process(code, store.store_root, source, publish_manifest)
    assert result.returncode == 19, result.stderr
    reopened = LocalStore(store.store_root)
    assert reopened.list_runs() == ["original"]
    assert reopened.list_bundles_for_run("interrupted") == []
    assert reopened.verify_integrity("original")["integrity_ok"]
    assert {path.name: path.read_bytes() for path in index_dir.glob("*.jsonl")} == before


def test_other_process_cannot_observe_or_write_a_locked_store(tmp_path):
    from hate.store.locking import store_lock

    store, _ = _store(tmp_path)
    code = """
import sys
from pathlib import Path
from hate.store import LocalStore, LocalStoreError
try:
    LocalStore(Path(sys.argv[1])).list_runs()
except LocalStoreError:
    sys.exit(23)
"""
    with store_lock(store.store_root):
        with store_lock(store.store_root):
            result = _process(code, store.store_root)
            assert result.returncode == 23, result.stderr
    result = _process(code, store.store_root)
    assert result.returncode == 0, result.stderr


def test_already_open_store_in_another_thread_respects_lock(tmp_path):
    from hate.store.locking import store_lock

    store, source = _store(tmp_path)
    another = LocalStore(store.store_root)
    with ThreadPoolExecutor(max_workers=1) as pool, store_lock(store.store_root):
        read = pool.submit(another.list_runs)
        with pytest.raises(LocalStoreError, match="store busy"):
            read.result(timeout=10)
        write = pool.submit(
            another.import_bundle, source, "concurrent", "revision-2",
            dict(status="none", reason="test", held_since="2026-09-10T00:00:00Z", authorized_by="test"),
        )
        with pytest.raises(LocalStoreError, match="store busy"):
            write.result(timeout=10)
    assert store.list_runs() == ["original"]
