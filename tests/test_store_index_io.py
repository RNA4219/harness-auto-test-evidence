from __future__ import annotations

import json
import os

import pytest

from hate.store.atomic_write import AtomicWriteError, compute_file_hash
from hate.store.indexes import HardDQFinding, IndexEntry, IndexLookupError, StoreIndex


@pytest.fixture
def index(tmp_path):
    return StoreIndex("runs", tmp_path / "indexes" / "runs.jsonl", tmp_path)


def _entry(key):
    return IndexEntry(key, f"runs/{key}.json", "sha256:" + "0" * 64)


def test_reload_replaces_cached_entries_instead_of_merging(index):
    index.entries = {"old": _entry("old"), "current": _entry("current")}
    index.save()
    index.index_path.write_text(_entry("current").to_jsonl() + "\n", encoding="utf-8")
    index.load()
    assert set(index.entries) == {"current"}


def test_corrupt_reload_does_not_publish_partially_loaded_entries(index):
    index.entries = {"previous": _entry("previous")}
    index.save()
    index.index_path.write_text(_entry("new").to_jsonl() + "\n{broken\n", encoding="utf-8")
    with pytest.raises(IndexLookupError):
        index.load()
    assert set(index.entries) == {"previous"}


@pytest.mark.parametrize("invalid", [b"[]\n", b'{"key": 4}\n', b"\xff\n"])
def test_invalid_index_records_raise_index_error(index, invalid):
    index.index_path.parent.mkdir()
    index.index_path.write_bytes(invalid)
    with pytest.raises(IndexLookupError):
        index.load()


def test_saved_hash_matches_actual_bytes_and_preserves_unrelated_temporary(index):
    index.index_path.parent.mkdir()
    unrelated = index.index_path.with_suffix(".tmp")
    unrelated.write_bytes(b"unrelated file")
    index.entries = {"first": _entry("first")}
    saved_hash = index.save()
    assert saved_hash == compute_file_hash(index.index_path)
    assert unrelated.read_bytes() == b"unrelated file"


def test_failed_index_fsync_preserves_previous_bytes(index, monkeypatch):
    index.entries = {"first": _entry("first")}
    index.save()
    previous = index.index_path.read_bytes()
    index.entries["second"] = _entry("second")

    def failed_sync(fd):
        raise OSError("simulated index fsync failure")

    monkeypatch.setattr(os, "fsync", failed_sync)
    with pytest.raises(AtomicWriteError):
        index.save()
    assert index.index_path.read_bytes() == previous


@pytest.mark.parametrize("same_value", [True, False])
def test_duplicate_snapshot_keys_rejected_without_overwriting_cache(index, same_value):
    index.entries = {"previous": _entry("previous")}
    index.save()
    first = _entry("duplicate")
    second = _entry("duplicate")
    if not same_value:
        second.value = "runs/another.json"
    content = first.to_jsonl() + "\n\n" + second.to_jsonl() + "\n"
    index.index_path.write_text(content, encoding="utf-8")
    before = index.index_path.read_bytes()
    with pytest.raises(IndexLookupError) as error:
        index.load()
    assert error.value.key == "duplicate"
    assert error.value.diagnostics == [{"issue": "duplicate_index_key", "first_line": 1, "line_number": 3}]
    assert set(index.entries) == {"previous"}
    assert index.index_path.read_bytes() == before


@pytest.mark.parametrize("field,value", [("key", " "), ("value", " "), ("hash", "bad"), ("metadata", {"amount": float("nan")})])
def test_invalid_entries_are_rejected_on_load_and_save(index, field, value):
    index.entries = {"previous": _entry("previous")}
    index.save()
    before = index.index_path.read_bytes()
    invalid = _entry("new")
    setattr(invalid, field, value)
    index.entries["new"] = invalid
    with pytest.raises(IndexLookupError):
        index.save()
    assert index.index_path.read_bytes() == before
    raw = {"key": "new", "value": "runs/new.json", "hash": "sha256:" + "0" * 64, "metadata": {}}
    raw[field] = value
    index.index_path.write_text(json.dumps(raw) + "\n", encoding="utf-8")
    with pytest.raises(IndexLookupError):
        index.load()


def test_mapping_key_mismatch_cannot_be_saved(index):
    index.entries = {"first": _entry("first")}
    index.save()
    before = index.index_path.read_bytes()
    index.entries["second"] = _entry("first")
    with pytest.raises(IndexLookupError):
        index.save()
    assert index.index_path.read_bytes() == before


@pytest.mark.parametrize("options", [{"key": " "}, {"value": None}, {"record_hash": "bad"}, {"metadata": []}, {"metadata": {"amount": float("inf")}}])
def test_invalid_add_preserves_cached_snapshot(index, options):
    index.entries = {"previous": _entry("previous")}
    values = {"key": "new", "value": "runs/new.json", "record_hash": "sha256:" + "0" * 64, **options}
    with pytest.raises(HardDQFinding):
        index.add_entry(**values)
    assert set(index.entries) == {"previous"}


def test_explicit_alias_update_still_serializes_one_key(index):
    index.add_entry("run-1", "runs/first.json", "sha256:" + "0" * 64)
    index.add_entry("run-1", "runs/second.json", "sha256:" + "1" * 64)
    index.save()
    index.load()
    assert index.entries["run-1"].value == "runs/second.json"
    assert len(index.index_path.read_text(encoding="utf-8").splitlines()) == 1
