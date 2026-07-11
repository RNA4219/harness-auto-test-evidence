"""Generate and check the HATE v0.3 responsibility registry."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "governance" / "responsibility-registry.json"
SCHEMA_REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"
CORE_PHASES = {"P0a", "P0b", "P1a"}
CORE_COMMANDS = {"p0a", "export", "trust", "replay", "compare", "explain", "recommend", "doctor", "store", "bridge"}
PRODUCT_TERMS = {"dashboard", "notification", "incident", "slo", "support", "adoption", "commercial", "entitlement", "residency", "retention", "roadmap", "usage", "customer", "portfolio", "product", "deployment", "localization", "accessibility"}

def _owner_for_name(name: str) -> tuple[str, str]:
    normalized = name.replace("_", "-").lower()
    if any(term in normalized for term in PRODUCT_TERMS):
        return "product-ops-evidence", "POE/v1"
    if any(term in normalized for term in ("release", "waiver", "approval", "gate-decision")):
        return "quality-evidence-graph", "QEG/v1"
    if any(term in normalized for term in ("triage", "human-queue", "assessment", "assignment")):
        return "agent-state-gate", "HumanQueueItem/v1"
    if any(term in normalized for term in ("score", "verdict", "policy", "baseline")):
        return "agent-gatefield", "AgentAssessment/v1"
    if any(term in normalized for term in ("manual", "review", "oracle")):
        return "manual-bb-test-harness", "manual_case_set/v1"
    if any(term in normalized for term in ("schedule", "run-system", "worker")):
        return "shipyard-cp", "RunSystemPacket"
    if any(term in normalized for term in ("task-seed", "acceptance", "evidence")):
        return "agent-protocols", "Evidence/v1"
    return "workflow-cookbook", "HATE-bridge-consumer/v1"

def _leaf_commands() -> list[str]:
    sys.path.insert(0, str(ROOT / "src"))
    from hate.cli import build_parser
    parser = build_parser()
    root_action = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
    commands: list[str] = []
    def visit(prefix: list[str], command_parser: argparse.ArgumentParser) -> None:
        nested = [action for action in command_parser._actions if isinstance(action, argparse._SubParsersAction)]
        if not nested:
            commands.append(" ".join(prefix))
            return
        for action in nested:
            for name, child in action.choices.items():
                visit([*prefix, name], child)
    for name, child in root_action.choices.items():
        visit([name], child)
    return sorted(commands)

def _cli_owner(command: str) -> tuple[str, str]:
    parts = command.split()
    return _owner_for_name(parts[1] if parts[0] == "platform" and len(parts) > 1 else command)

def _build_registry(schema_registry: dict[str, Any]) -> dict[str, Any]:
    cli_surfaces = []
    for command in _leaf_commands():
        is_core = command.split()[0] in CORE_COMMANDS
        owner, contract = ("harness-auto-test-evidence", "HATE/v1") if is_core else _cli_owner(command)
        cli_surfaces.append({"cli": command, "classification": "core" if is_core else "bridge", "implementation_provider": "native" if is_core else "compat-v0.2", "owner_repo": owner, "canonical_contract": contract, "replacement": None if is_core else f"{owner}:{contract}", "deprecated_since": None if is_core else "0.3.0", "remove_after": None if is_core else "1.0.0"})
    record_types = []
    for record in sorted(schema_registry["records"], key=lambda item: item["record_type"]):
        phase = str(record.get("phase", ""))
        is_core = phase in CORE_PHASES
        owner, contract = ("harness-auto-test-evidence", "HATE/v1") if is_core else _owner_for_name(str(record["record_type"]))
        record_types.append({"record_type": record["record_type"], "schema": record["schema"], "phase": phase, "classification": "core" if is_core else "compat", "owner_repo": owner, "canonical_contract": contract, "replacement": None if is_core else f"{owner}:{contract}", "deprecated_since": None if is_core else "0.3.0", "remove_after": None if is_core else "1.0.0"})
    return {"schema_version": "HATE-responsibility/v1", "registry_version": "0.3.0", "core_scope": ["test-and-ci-ingest", "normalization-and-provenance", "artifact-safety", "AETE", "QEG-export", "schema-and-adapter-plugin-contracts", "local-evidence-history-and-replay"], "authority_constraints": {"product_ready": False, "release_authority": "external", "forbidden_in_hate": ["business-state-mutation", "final-verdict", "waiver-approval", "publish-authority", "new-post-P1a-domain-logic"]}, "cli_surfaces": cli_surfaces, "record_types": record_types}

def _annotate_schema_registry(schema_registry: dict[str, Any], registry: dict[str, Any]) -> None:
    by_type = {item["record_type"]: item for item in registry["record_types"]}
    for record in schema_registry["records"]:
        responsibility = by_type[record["record_type"]]
        if responsibility["classification"] == "core":
            continue
        record.update({"canonical_owner": responsibility["owner_repo"], "canonical_contract": responsibility["canonical_contract"], "compatibility_provider": "compat-v0.2", "deprecated_since": "0.3.0", "remove_after": "1.0.0"})

def _check(registry: dict[str, Any], schema_registry: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    expected_cli, actual_cli = set(_leaf_commands()), {item["cli"] for item in registry.get("cli_surfaces", [])}
    if expected_cli != actual_cli:
        findings.append(f"CLI registry mismatch missing={sorted(expected_cli-actual_cli)} extra={sorted(actual_cli-expected_cli)}")
    expected_records = {item["record_type"] for item in schema_registry["records"]}
    actual_records = {item["record_type"] for item in registry.get("record_types", [])}
    if expected_records != actual_records:
        findings.append(f"record registry mismatch missing={sorted(expected_records-actual_records)} extra={sorted(actual_records-expected_records)}")
    for item in registry.get("record_types", []):
        if item["classification"] == "core" and item["phase"] not in CORE_PHASES:
            findings.append(f"post-P1a record classified core: {item['record_type']}")
        if item["classification"] != "core" and (not item.get("owner_repo") or item["owner_repo"] == "harness-auto-test-evidence"):
            findings.append(f"post-P1a record has no external owner: {item['record_type']}")
    by_type = {item["record_type"]: item for item in registry.get("record_types", [])}
    for record in schema_registry["records"]:
        item = by_type.get(record["record_type"])
        if not item or item["classification"] == "core":
            continue
        for key in ("canonical_owner", "canonical_contract", "compatibility_provider", "deprecated_since", "remove_after"):
            if record.get(key) is None:
                findings.append(f"schema registry metadata missing {record['record_type']}.{key}")
    return findings

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    schema_registry = json.loads(SCHEMA_REGISTRY.read_text(encoding="utf-8"))
    generated = _build_registry(schema_registry)
    if args.write:
        REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        _annotate_schema_registry(schema_registry, generated)
        REGISTRY.write_text(json.dumps(generated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        SCHEMA_REGISTRY.write_text(json.dumps(schema_registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0
    if not REGISTRY.exists():
        print("responsibility registry is missing", file=sys.stderr)
        return 1
    current = json.loads(REGISTRY.read_text(encoding="utf-8"))
    findings = _check(current, schema_registry)
    if current != generated:
        findings.append("responsibility registry is stale; run responsibility_scope_gate.py --write")
    for finding in findings:
        print(f"HATE-SCOPE-GATE: {finding}", file=sys.stderr)
    return 1 if findings else 0

if __name__ == "__main__":
    raise SystemExit(main())
