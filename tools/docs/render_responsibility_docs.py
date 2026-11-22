"""Render responsibility freeze summaries into canonical documentation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "governance" / "responsibility-registry.json"
TARGETS = [ROOT / "README.md", ROOT / "docs/process/BLUEPRINT.md", ROOT / "docs/process/GUARDRAILS.md", ROOT / "docs/process/RUNBOOK.md", ROOT / "docs/process/EVALUATION.md", ROOT / "docs/process/RELEASE_MIGRATION_POLICY.md"]
START = "<!-- responsibility-freeze:start -->"
END = "<!-- responsibility-freeze:end -->"

def _block(registry: dict) -> str:
    cli, records = registry["cli_surfaces"], registry["record_types"]
    owners = sorted({item["owner_repo"] for item in cli if item["classification"] == "bridge"})
    lines = [START, "## Responsibility Freeze (generated)", "", "| 境界 | 現在値 |", "|---|---:|", f"| core CLI leaf | {sum(item['classification']=='core' for item in cli)} |", f"| bridge CLI leaf | {sum(item['classification']=='bridge' for item in cli)} |", f"| core HATE/v1 record type | {sum(item['classification']=='core' for item in records)} |", f"| compat HATE/v1 record type | {sum(item['classification']=='compat' for item in records)} |", "", f"- canonical owner: {', '.join(owners)}", "- P1b以降は compat-v0.2 または明示的な handoff のみ。", "- product_ready=false。QEG verdict、Go/No-Go、waiver、approval、publish authorityは外部責務。", "- deprecated since: 0.3.0; remove after: 1.0.0（v0.xでは物理削除しない）。", "- machine-readable source: governance/responsibility-registry.json", END]
    return "\n".join(lines)

def _compact_block(registry: dict) -> str:
    cli, records = registry["cli_surfaces"], registry["record_types"]
    counts = f"core_cli={sum(item['classification']=='core' for item in cli)}, bridge_cli={sum(item['classification']=='bridge' for item in cli)}, core_records={sum(item['classification']=='core' for item in records)}, compat_records={sum(item['classification']=='compat' for item in records)}"
    return "\n".join([START, "## Responsibility Freeze (generated)", counts, "P1b+ is bridge-only; product_ready=false; external release authority; remove_after=1.0.0.", END])


def _render(text: str, block: str) -> str:
    if START not in text:
        return text.rstrip() + "\n\n" + block + "\n"
    before, tail = text.split(START, 1)
    _, after = tail.split(END, 1)
    return before.rstrip() + "\n\n" + block + after.rstrip() + "\n"

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    block = _block(registry)
    stale = []
    for path in TARGETS:
        current = path.read_text(encoding="utf-8")
        rendered = _render(current, _compact_block(registry) if path.name == "RUNBOOK.md" else block)
        if args.write:
            path.write_text(rendered, encoding="utf-8")
        elif current != rendered:
            stale.append(str(path.relative_to(ROOT)))
    if stale:
        print("stale responsibility docs: " + ", ".join(stale))
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
