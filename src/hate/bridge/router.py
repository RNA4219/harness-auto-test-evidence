"""Post-P1a bridge router with frozen compat and explicit handoff providers."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

from ..compat.v0_2 import dispatch_compat_cli
from .inputs import LOCAL_OUTPUT_ARGUMENTS, TEMPORARY_PREFIX, collect_inputs
from .protocol import BridgeRoute
from .routes import BRIDGE_COMMANDS as BRIDGE_COMMANDS
from .routes import route_for_command
from .schemas import validate_bridge_record

PROVIDERS = frozenset({"compat-v0.2", "handoff"})
_WARNING_EMITTED = False

OptionScalar = str | int | float | bool | None
CommandOption = OptionScalar | list[OptionScalar]


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
    return route_for_command(_command_path(args))


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


def _handoff_base(args: argparse.Namespace, route: BridgeRoute) -> Path | None:
    for name in ("out", "manifest_out"):
        value = getattr(args, name, None)
        if isinstance(value, Path):
            return value if name == "out" and route.directory_output else value.parent
    return None


def _command_options(args: argparse.Namespace, route: BridgeRoute) -> dict[str, CommandOption]:
    # 未指定のPath引数もpath_argumentsの契約に従い、実行オプションへ混在させない。
    excluded = {"command", "bridge_provider", *LOCAL_OUTPUT_ARGUMENTS, *(name for name, _ in route.path_arguments)}
    options: dict[str, CommandOption] = {}
    for name, value in sorted(vars(args).items()):
        if name in excluded or name.endswith("_command") or isinstance(value, Path):
            continue
        if value is None or isinstance(value, str | int | float | bool):
            options[name] = value
        elif isinstance(value, list) and all(item is None or isinstance(item, str | int | float | bool) for item in value):
            options[name] = list(value)
        else:
            raise ValueError(f"unsupported bridge option type: {name}")
    return options


def _write_handoff(args: argparse.Namespace, route: BridgeRoute) -> int:
    base = _handoff_base(args, route)
    input_refs, path_arguments = collect_inputs(vars(args), route.path_arguments, base)
    command_options = _command_options(args, route)
    identity = {
        "command": route.command_path,
        "owner": route.canonical_owner,
        "canonical_contract": route.canonical_contract,
        "command_options": command_options,
        "input_refs": input_refs,
        "path_arguments": path_arguments,
        "expected_output_types": list(route.expected_output_types),
    }
    bridge_id = "hate-bridge-" + hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()[:24]
    source_refs = list(dict.fromkeys(Path(item["path"]).as_uri() for item in input_refs))
    request = {
        "schema_version": "HATE-bridge/v1",
        "record_type": "bridge_request",
        "bridge_id": bridge_id,
        "original_command": route.command_path,
        "owner": route.canonical_owner,
        "canonical_contract": route.canonical_contract,
        "command_options": command_options,
        "status": "handoff_required",
        "input_refs": input_refs,
        "path_arguments": path_arguments,
        "expected_output_types": list(route.expected_output_types),
        "sourceRefs": source_refs,
    }
    validate_bridge_record(request, "bridge-request")
    out_dir = base if base is not None else Path.cwd() / ".hate" / "bridge" / bridge_id
    out_dir.mkdir(parents=True, exist_ok=True)
    destination = out_dir / "bridge-request.json"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=out_dir, prefix=TEMPORARY_PREFIX, suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(request, ensure_ascii=False, indent=2) + "\n")
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
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
    try:
        route = _route_for(args)
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
