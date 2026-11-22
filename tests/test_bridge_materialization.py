from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from hate.bridge.materializer import BridgeMaterializeError, BridgeRecoveryError, materialize_bridge_result


def _packet(tmp_path: Path, *, relative: bool = False) -> tuple[Path, Path]:
    packet = tmp_path / "packet"
    packet.mkdir()
    request = {
        "schema_version": "HATE-bridge/v1",
        "record_type": "bridge_request",
        "bridge_id": "hate-bridge-" + "a" * 24,
        "original_command": "workflow map",
        "owner": "workflow-cookbook",
        "canonical_contract": "agent-protocols/HATE-bridge-consumer/v1",
        "status": "handoff_required",
        "input_refs": [],
        "expected_output_types": ["legacy:workflow-map"],
        "sourceRefs": [],
    }
    outputs = []
    for name in ("one.json", "two.json"):
        source = packet / name
        source.write_text(json.dumps({"name": name}), encoding="utf-8")
        outputs.append({
            "record_type": "legacy:workflow-map",
            "path": name if relative else str(source),
            "target_name": name,
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        })
    result = {
        "schema_version": "HATE-bridge/v1",
        "record_type": "bridge_result",
        "bridge_id": request["bridge_id"],
        "owner": request["owner"],
        "status": "completed",
        "output_refs": outputs,
        "diagnostics": [],
        "sourceRefs": [],
    }
    request_path, result_path = packet / "request.json", packet / "result.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    result_path.write_text(json.dumps(result), encoding="utf-8")
    return request_path, result_path


def test_result_relative_paths_are_resolved_against_result_file(tmp_path, monkeypatch):
    request, result = _packet(tmp_path, relative=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    out = tmp_path / "out"
    report = materialize_bridge_result(request, result, out)
    assert report["generated"] == ["one.json", "two.json"]
    assert (out / "one.json").read_bytes() == (result.parent / "one.json").read_bytes()


@pytest.mark.parametrize("second_name", ["one.json", "ONE.JSON"])
def test_duplicate_output_names_are_rejected_before_publishing(tmp_path, second_name):
    request, result = _packet(tmp_path)
    data = json.loads(result.read_text(encoding="utf-8"))
    data["output_refs"][1]["target_name"] = second_name
    result.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    (out / "one.json").write_bytes(b"original")
    with pytest.raises(BridgeMaterializeError, match="duplicate target_name"):
        materialize_bridge_result(request, result, out)
    assert {path.name: path.read_bytes() for path in out.iterdir()} == {"one.json": b"original"}


@pytest.mark.parametrize("existing", [True, False])
def test_publish_failure_restores_the_previous_output_set(tmp_path, monkeypatch, existing):
    request, result = _packet(tmp_path)
    out = tmp_path / "out"
    originals = {"one.json": b"old one", "two.json": b"old two", "keep.txt": b"keep"}
    if existing:
        out.mkdir()
        for name, content in originals.items():
            (out / name).write_bytes(content)
    replace = os.replace
    failed = False

    def fail_second_publish(source, destination):
        nonlocal failed
        destination = Path(destination)
        if destination == out / "two.json" and not failed:
            failed = True
            raise OSError("simulated write failure")
        return replace(source, destination)

    monkeypatch.setattr("hate.bridge.materializer.os.replace", fail_second_publish)
    with pytest.raises(BridgeMaterializeError, match="publish"):
        materialize_bridge_result(request, result, out)
    if existing:
        assert {path.name: path.read_bytes() for path in out.iterdir()} == originals
    else:
        assert not out.exists()
    assert not list(tmp_path.glob(".hate-materialize-*"))


def test_existing_directory_conflict_does_not_publish_any_file(tmp_path):
    request, result = _packet(tmp_path)
    out = tmp_path / "out"
    (out / "two.json").mkdir(parents=True)
    (out / "one.json").write_bytes(b"original")
    with pytest.raises(BridgeMaterializeError, match="directory"):
        materialize_bridge_result(request, result, out)
    assert (out / "one.json").read_bytes() == b"original"
    assert (out / "two.json").is_dir()


def test_invalid_utf8_packet_reports_a_materialize_error(tmp_path):
    request, result = _packet(tmp_path)
    result.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(BridgeMaterializeError, match="cannot read JSON"):
        materialize_bridge_result(request, result, tmp_path / "out")


def test_success_preserves_unrelated_files_and_publishes_every_verified_output(tmp_path):
    request, result = _packet(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep.txt").write_bytes(b"unrelated")
    (out / "one.json").write_bytes(b"previous")
    materialize_bridge_result(request, result, out)
    for entry in json.loads(result.read_text(encoding="utf-8"))["output_refs"]:
        assert hashlib.sha256((out / entry["target_name"]).read_bytes()).hexdigest() == entry["sha256"]
    assert (out / "keep.txt").read_bytes() == b"unrelated"
    assert not list(tmp_path.glob(".hate-materialize-*"))


def test_rollback_failure_preserves_recovery_files(tmp_path, monkeypatch):
    request, result = _packet(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "one.json").write_bytes(b"old one")
    (out / "two.json").write_bytes(b"old two")
    replace = os.replace

    def fail_publication_and_restore(source, destination):
        if Path(destination) == out / "two.json":
            raise OSError("simulated unavailable destination")
        return replace(source, destination)

    monkeypatch.setattr("hate.bridge.materializer.os.replace", fail_publication_and_restore)
    with pytest.raises(BridgeRecoveryError, match="recovery files retained") as error:
        materialize_bridge_result(request, result, out)
    recovery = list(tmp_path.glob(".hate-materialize-*"))
    assert len(recovery) == 1
    assert str(recovery[0]) in str(error.value)
    metadata = json.loads((recovery[0] / "recovery.json").read_text(encoding="utf-8"))
    assert metadata["out_dir"] == str(out.resolve())
    assert metadata["directory_existed"] is True
    assert metadata["targets"] == [{"name": "one.json", "existed": True}, {"name": "two.json", "existed": True}]
    assert (recovery[0] / "backups" / "two.json").read_bytes() == b"old two"
    assert (out / "one.json").read_bytes() == b"old one"


def test_interrupted_publication_restores_existing_outputs(tmp_path, monkeypatch):
    request, result = _packet(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    originals = {"one.json": b"old one", "two.json": b"old two"}
    for name, content in originals.items():
        (out / name).write_bytes(content)
    replace = os.replace
    interrupted = False

    def interrupt_second_publish(source, destination):
        nonlocal interrupted
        if Path(destination) == out / "two.json" and not interrupted:
            interrupted = True
            raise KeyboardInterrupt
        return replace(source, destination)

    monkeypatch.setattr("hate.bridge.materializer.os.replace", interrupt_second_publish)
    with pytest.raises(KeyboardInterrupt):
        materialize_bridge_result(request, result, out)
    assert {path.name: path.read_bytes() for path in out.iterdir()} == originals
