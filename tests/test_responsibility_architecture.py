from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
def _load_scope_gate():
    import importlib.util

    path = ROOT / "tools/ci/responsibility_scope_gate.py"
    spec = importlib.util.spec_from_file_location("hate_responsibility_scope_gate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

FORBIDDEN = ("p1b", "p2p3", "platform_cli", "release", "gap_closure", "expansion_runner", "validation_cycles")

def test_public_cli_handler_only_reaches_post_p1a_through_bridge() -> None:
    source = (ROOT / "src/hate/cli_handlers.py").read_text(encoding="utf-8")
    for module in FORBIDDEN:
        assert f"from .{module}" not in source
        assert f"import {module}" not in source
    assert "from .bridge.router import" in source

def test_frozen_provider_isolated_under_compat_package() -> None:
    source = (ROOT / "src/hate/compat/v0_2/handlers.py").read_text(encoding="utf-8")
    assert "def dispatch_compat_cli" in source

def test_scope_gate_rejects_post_p1a_core_and_ownerless_records() -> None:
    import copy
    import json

    _check = _load_scope_gate()._check

    registry = json.loads((ROOT / "governance/responsibility-registry.json").read_text(encoding="utf-8"))
    schemas = json.loads((ROOT / "schemas/HATE/v1/schema-registry.json").read_text(encoding="utf-8"))
    modified = copy.deepcopy(registry)
    target = next(item for item in modified["record_types"] if item["classification"] == "compat")
    target["classification"] = "core"
    target["owner_repo"] = "harness-auto-test-evidence"
    findings = _check(modified, schemas)
    assert any("post-P1a record classified core" in finding for finding in findings)


def test_scope_gate_rejects_unregistered_record_type() -> None:
    import copy
    import json

    _check = _load_scope_gate()._check

    registry = json.loads((ROOT / "governance/responsibility-registry.json").read_text(encoding="utf-8"))
    schemas = json.loads((ROOT / "schemas/HATE/v1/schema-registry.json").read_text(encoding="utf-8"))
    modified_schemas = copy.deepcopy(schemas)
    modified_schemas["records"].append(
        {
            "record_type": "forbidden-new-business-verdict",
            "schema": "schemas/HATE/v1/forbidden.schema.json",
            "phase": "P2",
        }
    )
    findings = _check(registry, modified_schemas)
    assert any("record registry mismatch" in finding for finding in findings)


def test_every_bridge_leaf_matches_runtime_route() -> None:
    import argparse
    import json

    from hate.bridge.router import _route_for
    from hate.cli import build_parser

    registry = json.loads((ROOT / "governance/responsibility-registry.json").read_text(encoding="utf-8"))
    expected = {item["cli"]: item for item in registry["cli_surfaces"] if item["classification"] == "bridge"}
    checked = set()

    def visit(parser, selectors, parts):
        actions = [action for action in parser._actions if isinstance(action, argparse._SubParsersAction)]
        if not actions:
            command = " ".join(parts)
            if command in expected:
                route = _route_for(argparse.Namespace(**selectors))
                assert route.command_path == command
                assert route.canonical_owner == expected[command]["owner_repo"], command
                assert route.canonical_contract == expected[command]["canonical_contract"], command
                checked.add(command)
        for action in actions:
            for name, child in action.choices.items():
                visit(child, {**selectors, action.dest: name}, [*parts, name])

    visit(build_parser(), {}, [])
    assert checked == set(expected)


@pytest.mark.parametrize("field", ["owner_repo", "canonical_contract"])
def test_scope_gate_rejects_cli_route_metadata_drift(field) -> None:
    import json

    registry = json.loads((ROOT / "governance/responsibility-registry.json").read_text(encoding="utf-8"))
    schemas = json.loads((ROOT / "schemas/HATE/v1/schema-registry.json").read_text(encoding="utf-8"))
    target = next(item for item in registry["cli_surfaces"] if item["cli"] == "platform verdict")
    target[field] = "incorrect"
    findings = _load_scope_gate()._check(registry, schemas)
    assert any("CLI route mismatch: platform verdict" in finding for finding in findings)


def test_unregistered_platform_command_has_no_fallback_owner(capsys, tmp_path) -> None:
    from argparse import Namespace

    from hate.bridge.router import dispatch_bridge
    from hate.cli import build_parser

    args = Namespace(command="platform", platform_command="unregistered", bridge_provider="handoff", out=tmp_path / "out")
    assert dispatch_bridge(args, build_parser()) == 2
    assert "unregistered bridge command" in capsys.readouterr().err
    assert not args.out.exists()
