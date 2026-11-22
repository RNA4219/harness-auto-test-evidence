from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hate.store import LocalStore
from hate.store.locking import store_lock

pytestmark = pytest.mark.subprocess


def _run(code, root, directory):
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(root), str(directory)],
        env=env, capture_output=True, text=True, timeout=20,
    )


def _saved(tmp_path):
    source = tmp_path / "source.json"
    source.write_text('{"nodes": [{"id": "test-1", "kind": "test"}]}', encoding="utf-8")
    store = LocalStore(tmp_path / "store")
    hold = dict(status="active", reason="retain", held_since="2026-09-10T00:00:00Z", authorized_by="test")
    result = store.import_bundle(source, "run-1", "revision-1", hold)
    assert result.success
    return store, result.manifest_path.parent


_BUILD = """
import json, sys
from pathlib import Path
from hate.store.indexes import build_indexes_for_bundle
root, directory = Path(sys.argv[1]), Path(sys.argv[2])
manifest = json.loads((directory / 'store-manifest.json').read_text(encoding='utf-8'))
"""


@pytest.mark.parametrize("existing_indexes", [False, True])
def test_next_open_recovers_interrupted_index_update_without_moving_evidence(tmp_path, existing_indexes):
    store, directory = _saved(tmp_path)
    indexes = store.store_root / "indexes"
    for path in indexes.glob("*.jsonl"):
        if existing_indexes:
            path.write_bytes(b"")
        else:
            path.unlink()
    before = {path.name: path.read_bytes() for path in indexes.glob("*.jsonl")}
    evidence = {path.name: path.read_bytes() for path in directory.glob("*.json")}
    code = _BUILD + """
import os
from hate.store.indexes import StoreIndex
save = StoreIndex.save
def interrupted(index):
    result = save(index)
    if index.index_type == 'bundles':
        os._exit(19)
    return result
StoreIndex.save = interrupted
build_indexes_for_bundle(root, directory, manifest)
"""
    result = _run(code, store.store_root, directory)
    assert result.returncode == 19, result.stderr
    journal = store.store_root / "migrations" / "pending-import" / "journal.json"
    assert json.loads(journal.read_text(encoding="utf-8"))["operation"] == "indexes"
    LocalStore(store.store_root)
    assert {path.name: path.read_bytes() for path in indexes.glob("*.jsonl")} == before
    assert {path.name: path.read_bytes() for path in directory.glob("*.json")} == evidence
    assert not journal.exists()
    result = _run(_BUILD + "build_indexes_for_bundle(root, directory, manifest)", store.store_root, directory)
    assert result.returncode == 0, result.stderr
    assert store.verify_integrity("run-1")["integrity_ok"]


def test_builder_obeys_store_lock_in_another_process(tmp_path):
    store, directory = _saved(tmp_path)
    code = _BUILD + """
from hate.store import LocalStoreError
try:
    build_indexes_for_bundle(root, directory, manifest)
except LocalStoreError as exc:
    if exc.operation == 'lock':
        sys.exit(23)
    raise
"""
    with store_lock(store.store_root):
        result = _run(code, store.store_root, directory)
        assert result.returncode == 23, result.stderr
    result = _run(code, store.store_root, directory)
    assert result.returncode == 0, result.stderr
