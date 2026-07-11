from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "docs" / "process" / "post-poc-gap-registry.json"
TARGETS = {
    ROOT / "docs" / "process" / "POST_POC_REQUIREMENTS_GAP_AUDIT.md": ("## 2. Gap Register", "## 3. Implementation Order", "requirements"),
    ROOT / "docs" / "process" / "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md": ("## 2. Gap-by-Gap Spec Traceability", "## 3. Spec Closure Checklist", "traceability"),
    ROOT / "docs" / "process" / "POST_POC_IMPLEMENTATION_GAP_CHECKLIST.md": ("## 2. Spec-to-Implementation Gap Matrix", "## 3. Workflow Task Seeds", "implementation"),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render canonical Post-PoC status tables.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    errors = _validate_registry(registry)
    if errors:
        print(*errors, sep="\n", file=sys.stderr)
        return 2
    stale = []
    for path, (start_heading, end_heading, view) in TARGETS.items():
        current = path.read_text(encoding="utf-8")
        rendered = _replace_section(current, start_heading, end_heading, _render_view(view, registry["gaps"]))
        if rendered == current:
            continue
        if args.check:
            stale.append(str(path.relative_to(ROOT)))
        else:
            path.write_text(rendered, encoding="utf-8", newline="\n")
    if stale:
        print("Post-PoC generated status is stale:", *[f"- {path}" for path in stale], sep="\n", file=sys.stderr)
        return 1
    return 0


def _validate_registry(registry: dict[str, Any]) -> list[str]:
    errors = []
    gaps = registry.get("gaps")
    if not isinstance(gaps, list) or not gaps:
        return ["registry.gaps must be a non-empty array"]
    seen = set()
    required = {"gap_id", "area", "local_slice_status", "product_status", "remaining_work", "implementation_refs", "test_refs", "acceptance_ref"}
    for index, raw in enumerate(gaps):
        if not isinstance(raw, dict):
            errors.append(f"gaps[{index}] must be an object")
            continue
        missing = sorted(required.difference(raw))
        if missing:
            errors.append(f"gaps[{index}] missing: {', '.join(missing)}")
            continue
        gap_id = str(raw["gap_id"])
        if gap_id in seen:
            errors.append(f"duplicate gap_id: {gap_id}")
        seen.add(gap_id)
        if raw["local_slice_status"] not in {"open", "in_progress", "accepted"}:
            errors.append(f"{gap_id}: invalid local_slice_status")
        if raw["product_status"] not in {"open", "held", "closed"}:
            errors.append(f"{gap_id}: invalid product_status")
        for ref in [*raw["implementation_refs"], *raw["test_refs"], raw["acceptance_ref"]]:
            if not (ROOT / str(ref)).exists():
                errors.append(f"{gap_id}: missing ref {ref}")
    if registry.get("product_ready") is not False:
        errors.append("product_ready must remain false without external approval")
    if registry.get("release_authority") != "external":
        errors.append("release_authority must remain external")
    return errors


def _replace_section(text: str, start_heading: str, end_heading: str, body: str) -> str:
    start = text.find(start_heading)
    end = text.find(end_heading)
    if start < 0 or end < 0 or end <= start:
        raise ValueError(f"Cannot locate generated section: {start_heading} -> {end_heading}")
    return f"{text[:start]}{start_heading}\n\n{body.rstrip()}\n\n{text[end:]}"


def _render_view(view: str, gaps: list[dict[str, Any]]) -> str:
    if view == "requirements":
        header = "| Gap ID | Area | Local Slice | Product Status | Remaining Work | Acceptance Evidence |\n|---|---|---|---|---|---|"
        rows = [f"| {_cell(g['gap_id'])} | {_cell(g['area'])} | {_cell(g['local_slice_status'])} | {_cell(g['product_status'])} | {_cell(g['remaining_work'])} | {_cell(g['acceptance_ref'])} |" for g in gaps]
        intro = "The JSON registry post-poc-gap-registry.json is canonical. Local evidence acceptance does not close production or hosted-operation gaps."
        marker = "POST_POC_REQUIREMENTS"
    elif view == "traceability":
        header = "| Gap ID | Local Slice | Product Status | Implementation | Tests | Acceptance | Remaining Work |\n|---|---|---|---|---|---|---|"
        rows = [f"| {_cell(g['gap_id'])} | {_cell(g['local_slice_status'])} | {_cell(g['product_status'])} | {_refs(g['implementation_refs'])} | {_refs(g['test_refs'])} | {_cell(g['acceptance_ref'])} | {_cell(g['remaining_work'])} |" for g in gaps]
        intro = "Legend: local_slice_status=accepted proves the bounded local evidence slice; product_status=open keeps broader productization work visible. Task seeds remain in POST_POC_IMPLEMENTATION_GAP_CHECKLIST.md."
        marker = "POST_POC_TRACEABILITY"
    else:
        header = "| Task ID | Gap ID | Local Slice | Product Status | Acceptance | Blocking Product Work |\n|---|---|---|---|---|---|"
        rows = [f"| TASK-POSTPOC-{i:03d} | {_cell(g['gap_id'])} | {_cell(g['local_slice_status'])} | {_cell(g['product_status'])} | {_cell(g['acceptance_ref'])} | {_cell(g['remaining_work'])} |" for i, g in enumerate(gaps, start=1)]
        intro = "Task status is generated from the canonical registry. Accepted local slices must not be interpreted as closed production gaps."
        marker = "POST_POC_IMPLEMENTATION"
    return "\n".join([intro, "", f"<!-- BEGIN GENERATED:{marker} -->", header, *rows, f"<!-- END GENERATED:{marker} -->"])


def _refs(refs: list[str]) -> str:
    return "<br>".join(_cell(ref) for ref in refs)


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
