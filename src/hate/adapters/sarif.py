"""SARIF static finding parser."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = ["parse_sarif_file"]


def parse_sarif_file(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed SARIF JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("SARIF root must be an object")

    findings: list[dict[str, Any]] = []
    for run_index, run in enumerate(data.get("runs", [])):
        tool = run.get("tool", {}).get("driver", {}) if isinstance(run, dict) else {}
        tool_name = str(tool.get("name", "unknown"))
        for result_index, result in enumerate(run.get("results", [])):
            locations = result.get("locations", []) if isinstance(result, dict) else []
            if not locations:
                raise ValueError("SARIF result missing physicalLocation")
            for location_index, location in enumerate(locations):
                physical = location.get("physicalLocation") if isinstance(location, dict) else None
                if not isinstance(physical, dict):
                    raise ValueError("SARIF result missing physicalLocation")
                artifact = physical.get("artifactLocation", {})
                region = physical.get("region", {})
                uri = artifact.get("uri")
                if not uri:
                    raise ValueError("SARIF result missing artifact uri")
                findings.append(
                    {
                        "rule_id": result.get("ruleId", ""),
                        "severity": result.get("level", "warning"),
                        "message": _sarif_message(result.get("message", {})),
                        "file": _normalize_path(str(uri)),
                        "line": int(region.get("startLine", 1)),
                        "end_line": int(region.get("endLine", region.get("startLine", 1))),
                        "suppressed": bool(result.get("suppressions")),
                        "suppressions": result.get("suppressions", []),
                        "changed_path": bool(result.get("properties", {}).get("changed_path", False)),
                        "tool": tool_name,
                        "sourceRef": f"{source}#/runs/{run_index}/results/{result_index}/locations/{location_index}",
                    }
                )
    return {"findings": findings, "parser_diagnostics": [], "sourceRef": str(source)}


def _sarif_message(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("text") or message.get("markdown") or "")
    return str(message or "")


def _normalize_path(path: str) -> str:
    path = path.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path
