"""Fail-closed HATE-bridge result materializer."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from .schemas import BridgeValidationError, validate_bridge_record


class BridgeMaterializeError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
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


def materialize_bridge_result(request_path: Path, result_path: Path, out_dir: Path) -> dict[str, Any]:
    request = _load(request_path)
    result = _load(result_path)
    _validate_pair(request, result)

    verified: list[tuple[Path, str]] = []
    for output in result["output_refs"]:
        source = Path(output["path"])
        target_name = output["target_name"]
        if Path(target_name).name != target_name or target_name in {"", ".", ".."}:
            raise BridgeMaterializeError(f"unsafe target_name: {target_name}")
        if not source.is_file():
            raise BridgeMaterializeError(f"bridge output does not exist: {source}")
        import hashlib

        actual_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        if actual_hash != output["sha256"]:
            raise BridgeMaterializeError(f"bridge output hash mismatch: {source}")
        verified.append((source, target_name))

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".hate-materialize-", dir=out_dir.parent) as temp:
        stage = Path(temp)
        for source, target_name in verified:
            shutil.copy2(source, stage / target_name)
        out_dir.mkdir(parents=True, exist_ok=True)
        for _, target_name in verified:
            os.replace(stage / target_name, out_dir / target_name)

    return {
        "status": "materialized",
        "bridge_id": request["bridge_id"],
        "canonical_owner": request["owner"],
        "generated": [target for _, target in verified],
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
