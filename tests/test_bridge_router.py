from __future__ import annotations

import hashlib
import json
from argparse import Namespace
from pathlib import Path

from hate.bridge.materializer import dispatch_materialize, materialize_bridge_result
from hate.bridge.router import dispatch_bridge
from hate.cli import build_parser


def _workflow_args(tmp_path: Path, provider: str | None = "handoff") -> Namespace:
    inputs = {}
    for name in ("bundle", "report"):
        path = tmp_path / f"{name}.json"
        path.write_text("{}", encoding="utf-8")
        inputs[name] = path
    trust = tmp_path / "trust"
    trust.mkdir()
    return Namespace(
        command="workflow",
        workflow_command="map",
        bundle=inputs["bundle"],
        report=inputs["report"],
        trust=trust,
        out=tmp_path / "out",
        rand_requirements=None,
        rand_audit=None,
        shipyard_worker_result=None,
        shipyard_run_system_packet=None,
        source_version=None,
        bridge_provider=provider,
    )


def test_handoff_generates_valid_deterministic_request_without_compat(monkeypatch, tmp_path: Path) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("compat provider must not run")

    monkeypatch.setattr("hate.bridge.router.dispatch_compat_cli", forbidden)
    args = _workflow_args(tmp_path)
    assert dispatch_bridge(args, build_parser()) == 0
    request_path = tmp_path / "out" / "bridge-request.json"
    first = json.loads(request_path.read_text(encoding="utf-8"))
    assert first["status"] == "handoff_required"
    assert first["owner"] == "workflow-cookbook"
    assert first["input_refs"]
    assert all(len(item["sha256"]) == 64 for item in first["input_refs"])
    assert dispatch_bridge(args, build_parser()) == 0
    second = json.loads(request_path.read_text(encoding="utf-8"))
    assert second["bridge_id"] == first["bridge_id"]


def test_cli_provider_overrides_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HATE_BRIDGE_PROVIDER", "compat-v0.2")
    args = _workflow_args(tmp_path, "handoff")
    assert dispatch_bridge(args, build_parser()) == 0
    assert (tmp_path / "out" / "bridge-request.json").exists()


def test_compat_stdout_adds_migration_metadata(monkeypatch, capsys, tmp_path: Path) -> None:
    args = _workflow_args(tmp_path, "compat-v0.2")

    def compat(*unused):
        print(json.dumps({"generated": ["legacy.json"], "status": "pass"}))
        return 0

    monkeypatch.setattr("hate.bridge.router.dispatch_compat_cli", compat)
    assert dispatch_bridge(args, build_parser()) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["compatibility_provider"] == "compat-v0.2"
    assert payload["canonical_owner"] == "workflow-cookbook"
    assert payload["deprecated_since"] == "0.3.0"
    assert payload["remove_after"] == "1.0.0"


def _request_and_result(tmp_path: Path) -> tuple[Path, Path, Path]:
    args = _workflow_args(tmp_path, "handoff")
    assert dispatch_bridge(args, build_parser()) == 0
    request_path = tmp_path / "out" / "bridge-request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    artifact = tmp_path / "external" / "legacy.json"
    artifact.parent.mkdir()
    artifact.write_text(json.dumps({"schema_version": "HATE/v1", "record_type": "legacy"}), encoding="utf-8")
    sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()
    result = {
        "schema_version": "HATE-bridge/v1",
        "record_type": "bridge_result",
        "bridge_id": request["bridge_id"],
        "owner": request["owner"],
        "status": "completed",
        "output_refs": [
            {
                "record_type": request["expected_output_types"][0],
                "path": str(artifact),
                "target_name": "legacy.json",
                "sha256": sha256,
            }
        ],
        "diagnostics": [],
        "sourceRefs": request["sourceRefs"],
    }
    result_path = tmp_path / "bridge-result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")
    return request_path, result_path, artifact


def test_materialize_valid_result(tmp_path: Path) -> None:
    request, result, _ = _request_and_result(tmp_path)
    out = tmp_path / "legacy-out"
    report = materialize_bridge_result(request, result, out)
    assert report["status"] == "materialized"
    assert (out / "legacy.json").exists()


def test_materialize_hash_mismatch_is_fail_closed(tmp_path: Path) -> None:
    request, result, artifact = _request_and_result(tmp_path)
    artifact.write_text("tampered", encoding="utf-8")
    out = tmp_path / "legacy-out"
    args = Namespace(bridge_command="materialize", request=request, result=result, out=out)
    assert dispatch_materialize(args) == 2
    assert not out.exists()


def test_materialize_owner_mismatch_is_fail_closed(tmp_path: Path) -> None:
    request, result, _ = _request_and_result(tmp_path)
    payload = json.loads(result.read_text(encoding="utf-8"))
    payload["owner"] = "wrong-owner"
    result.write_text(json.dumps(payload), encoding="utf-8")
    out = tmp_path / "legacy-out"
    args = Namespace(bridge_command="materialize", request=request, result=result, out=out)
    assert dispatch_materialize(args) == 2
    assert not out.exists()
