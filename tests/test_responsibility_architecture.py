from pathlib import Path

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

