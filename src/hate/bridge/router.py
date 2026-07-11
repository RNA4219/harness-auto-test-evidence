"""Post-P1a bridge router with frozen compat and explicit handoff providers."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import sys
from pathlib import Path

from ..compat.v0_2 import dispatch_compat_cli
from .protocol import BridgeRoute
from .schemas import validate_bridge_record

BRIDGE_COMMANDS = frozenset(
    {"workflow", "product", "release", "gap", "expansion", "real-repo", "platform", "validation"}
)
PROVIDERS = frozenset({"compat-v0.2", "handoff"})
_WARNING_EMITTED = False

_ROUTE_OWNERS = {
    "workflow": ("workflow-cookbook", "agent-protocols/HATE-bridge-consumer/v1"),
    "product": ("product-ops-evidence", "POE/v1"),
    "release": ("quality-evidence-graph", "QEG/v1"),
    "gap": ("workflow-cookbook", "workflow-cookbook/HATE-bridge-consumer/v1"),
    "expansion": ("workflow-cookbook", "workflow-cookbook/HATE-bridge-consumer/v1"),
    "real-repo": ("shipyard-cp", "RunSystemPacket"),
    "validation": ("workflow-cookbook", "five-tool-validation-manifest/v1"),
}

_PLATFORM_OWNERS = {
    "run": ("shipyard-cp", "RunSystemPacket"),
    "history": ("workflow-cookbook", "HATE-evidence-export/v1"),
    "history-analytics": ("product-ops-evidence", "POE/v1"),
    "history-materialize": ("workflow-cookbook", "HATE-evidence-export/v1"),
    "compare": ("agent-gatefield", "AgentAssessment/v1"),
    "schedule": ("shipyard-cp", "RunSystemPacket"),
    "assign": ("agent-state-gate", "HumanQueueItem/v1"),
    "score": ("agent-gatefield", "AgentAssessment/v1"),
    "verdict": ("quality-evidence-graph", "QEG/v1"),
    "triage": ("agent-state-gate", "HumanQueueItem/v1"),
    "baseline": ("quality-evidence-graph", "QEG/v1"),
    "notify": ("product-ops-evidence", "POE/v1"),
    "plugin": ("harness-auto-test-evidence", "HATE/v1"),
    "policy": ("agent-gatefield", "GatePolicy/v1"),
    "report": ("product-ops-evidence", "POE/v1"),
    "serve": ("product-ops-evidence", "POE/v1"),
    "findings": ("agent-state-gate", "AgentAssessment/v1"),
    "debt": ("agent-state-gate", "AgentAssessment/v1"),
    "review": ("manual-bb-test-harness", "manual_case_set/v1"),
}


def _command_path(args: argparse.Namespace) -> str:
    parts = [str(args.command)]
    prefixes = (
        "workflow",
        "product",
        "release",
        "gap",
        "expansion",
        "real_repo",
        "platform",
        "platform_baseline",
        "platform_notify",
        "platform_plugin",
        "platform_policy",
        "platform_report",
        "validation",
    )
    for prefix in prefixes:
        value = getattr(args, f"{prefix}_command", None)
        if value:
            parts.append(str(value))
    return " ".join(parts)


def _route_for(args: argparse.Namespace) -> BridgeRoute:
    command_path = _command_path(args)
    if args.command == "platform":
        owner, contract = _PLATFORM_OWNERS.get(
            getattr(args, "platform_command", ""),
            ("product-ops-evidence", "POE/v1"),
        )
    else:
        owner, contract = _ROUTE_OWNERS[args.command]
    expected = (f"legacy:{command_path.replace(' ', '-')}",)
    return BridgeRoute(command_path, owner, contract, expected)


def _selected_provider(args: argparse.Namespace) -> str:
    selected = getattr(args, "bridge_provider", None) or os.environ.get("HATE_BRIDGE_PROVIDER") or "compat-v0.2"
    if selected not in PROVIDERS:
        raise ValueError(f"unknown bridge provider: {selected}")
    return selected


def _warn_once(route: BridgeRoute) -> None:
    global _WARNING_EMITTED
    if not _WARNING_EMITTED:
        print(
            "HATE-W-BRIDGE-DEPRECATED: post-P1a compatibility behavior is frozen; "
            f"canonical owner is {route.canonical_owner}; remove_after={route.remove_after}",
            file=sys.stderr,
        )
        _WARNING_EMITTED = True


def _compat_metadata(route: BridgeRoute) -> dict[str, str]:
    return {
        "compatibility_provider": "compat-v0.2",
        "canonical_owner": route.canonical_owner,
        "deprecated_since": route.deprecated_since,
        "remove_after": route.remove_after,
    }


def _run_compat(args: argparse.Namespace, parser: argparse.ArgumentParser, route: BridgeRoute) -> int:
    _warn_once(route)
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exit_code = dispatch_compat_cli(args, parser)
    rendered = stdout.getvalue()
    if exit_code == 0:
        try:
            payload = json.loads(rendered)
        except json.JSONDecodeError:
            if rendered:
                print(rendered, end="")
        else:
            if isinstance(payload, dict):
                payload.update(_compat_metadata(route))
            print(json.dumps(payload, ensure_ascii=False))
    elif rendered:
        print(rendered, end="")
    return exit_code


def _hash_path(path: Path) -> tuple[str, str]:
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest(), "file"
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        relative = child.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(child.read_bytes()).digest())
    return digest.hexdigest(), "directory"


def _input_refs(args: argparse.Namespace) -> list[dict[str, str]]:
    excluded = {"out", "manifest_out", "bridge_provider"}
    refs: list[dict[str, str]] = []
    for argument, value in sorted(vars(args).items()):
        if argument in excluded or not isinstance(value, Path) or not value.exists():
            continue
        sha256, kind = _hash_path(value)
        refs.append(
            {
                "argument": argument,
                "path": str(value.resolve()),
                "sha256": sha256,
                "kind": kind,
            }
        )
    return refs


def _handoff_dir(args: argparse.Namespace, bridge_id: str) -> Path:
    for name in ("out", "manifest_out"):
        value = getattr(args, name, None)
        if isinstance(value, Path):
            return value.parent if value.suffix else value
    return Path.cwd() / ".hate" / "bridge" / bridge_id


def _write_handoff(args: argparse.Namespace, route: BridgeRoute) -> int:
    input_refs = _input_refs(args)
    identity = {
        "command": route.command_path,
        "owner": route.canonical_owner,
        "input_refs": input_refs,
        "expected_output_types": list(route.expected_output_types),
    }
    bridge_id = "hate-bridge-" + hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:24]
    source_refs = [f"file://{item['path'].replace(os.sep, '/')}" for item in input_refs]
    request = {
        "schema_version": "HATE-bridge/v1",
        "record_type": "bridge_request",
        "bridge_id": bridge_id,
        "original_command": route.command_path,
        "owner": route.canonical_owner,
        "canonical_contract": route.canonical_contract,
        "status": "handoff_required",
        "input_refs": input_refs,
        "expected_output_types": list(route.expected_output_types),
        "sourceRefs": source_refs,
    }
    validate_bridge_record(request, "bridge-request")
    out_dir = _handoff_dir(args, bridge_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    destination = out_dir / "bridge-request.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    print(
        json.dumps(
            {
                "status": "handoff_required",
                "bridge_provider": "handoff",
                "bridge_request": str(destination),
                "canonical_owner": route.canonical_owner,
            },
            ensure_ascii=False,
        )
    )
    return 0


def dispatch_bridge(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    route = _route_for(args)
    try:
        provider = _selected_provider(args)
    except ValueError as exc:
        print(f"HATE-E-BRIDGE: {exc}", file=sys.stderr)
        return 2
    if provider == "handoff":
        try:
            return _write_handoff(args, route)
        except (OSError, ValueError) as exc:
            print(f"HATE-E-BRIDGE: {exc}", file=sys.stderr)
            return 2
    return _run_compat(args, parser, route)
