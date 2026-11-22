from __future__ import annotations

import os
from pathlib import Path

import pytest

from hate.store import atomic_write as writer


def test_short_writes_are_completed_before_publication(tmp_path, monkeypatch):
    target = tmp_path / "state.json"
    content = {"message": "日本語の保存" * 10}
    original_write = os.write
    monkeypatch.setattr(writer.os, "write", lambda fd, data: original_write(fd, data[:7]))
    writer.atomic_write_json(target, content, tmp_path)
    assert writer.compute_file_hash(target) == writer.compute_json_hash_for_write(content)


def test_zero_length_write_fails_without_replacing_previous_file(tmp_path, monkeypatch):
    target = tmp_path / "state.json"
    target.write_bytes(b"previous")
    monkeypatch.setattr(writer.os, "write", lambda fd, data: 0)
    with pytest.raises(writer.AtomicWriteError) as raised:
        writer.atomic_write_json(target, {"new": True}, tmp_path)
    assert raised.value.phase == "write"
    assert target.read_bytes() == b"previous"
    assert not list(tmp_path.glob(".tmp-*"))


def test_failed_replacement_preserves_previous_file_and_unrelated_backup(tmp_path, monkeypatch):
    target = tmp_path / "state.json"
    target.write_bytes(b"previous")
    backup = tmp_path / "state.json.bak"
    backup.write_bytes(b"unrelated backup")
    original_move = writer.shutil.move

    def fail_replace(*args):
        raise OSError("simulated replacement failure")

    def fail_legacy_publication(source, destination, *args, **kwargs):
        if Path(destination) == target:
            raise OSError("simulated replacement failure")
        return original_move(source, destination, *args, **kwargs)

    monkeypatch.setattr(writer.os, "replace", fail_replace)
    monkeypatch.setattr(writer.shutil, "move", fail_legacy_publication)
    with pytest.raises(writer.AtomicWriteError):
        writer.atomic_write_json(target, {"new": True}, tmp_path)
    assert target.read_bytes() == b"previous"
    assert backup.read_bytes() == b"unrelated backup"
    assert not list(tmp_path.glob(".tmp-*"))


def test_failed_fsync_reports_phase_and_keeps_previous_file(tmp_path, monkeypatch):
    target = tmp_path / "state.json"
    target.write_bytes(b"previous")

    def unavailable_sync(fd):
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(writer.os, "fsync", unavailable_sync)
    with pytest.raises(writer.AtomicWriteError) as raised:
        writer.atomic_write_json(target, {"new": True}, tmp_path)
    assert raised.value.phase == "fsync"
    assert raised.value.diagnostics[0]["published"] is False
    assert target.read_bytes() == b"previous"


def test_directory_sync_failure_reports_that_replacement_has_happened(tmp_path, monkeypatch):
    target = tmp_path / "state.json"

    def unavailable_directory_sync(parent):
        raise OSError("simulated directory sync failure")

    monkeypatch.setattr(writer, "_sync_parent_directory", unavailable_directory_sync, raising=False)
    with pytest.raises(writer.AtomicWriteError) as raised:
        writer.atomic_write_json(target, {"new": True}, tmp_path)
    assert raised.value.phase == "fsync"
    assert raised.value.diagnostics[0]["published"] is True
    assert target.is_file()


def test_interrupt_closes_descriptor_and_removes_unpublished_temporary(tmp_path, monkeypatch):
    descriptors = []

    def interrupted_write(fd, data):
        descriptors.append(fd)
        raise KeyboardInterrupt

    monkeypatch.setattr(writer.os, "write", interrupted_write)
    try:
        with pytest.raises(KeyboardInterrupt):
            writer.atomic_write_json(tmp_path / "state.json", {"new": True}, tmp_path)
        with pytest.raises(OSError):
            os.fstat(descriptors[0])
        assert not list(tmp_path.glob(".tmp-*"))
    finally:
        for fd in descriptors:
            try:
                os.close(fd)
            except OSError:
                pass


def test_invalid_json_number_does_not_create_output_directory(tmp_path):
    target = tmp_path / "new" / "state.json"
    with pytest.raises(writer.AtomicWriteError):
        writer.atomic_write_json(target, {"number": float("nan")}, tmp_path)
    assert not target.parent.exists()
