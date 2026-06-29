"""Coverage adapter entrypoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..p0a_coverage_adapters import _parse_cobertura, _parse_coveragepy_json, _parse_jacoco, _parse_lcov

__all__ = ["parse_coverage_file"]


def parse_coverage_file(path: Path, input_format: str, *, test_ids: list[str] | None = None) -> dict[str, Any]:
    """Parse a coverage fixture and return payloads plus diagnostics.

    This public wrapper keeps adapter conformance tests out of P0a internals while
    preserving the exact parser behavior used by generate_p0a.
    """
    context = {
        "run_id": "adapter-coverage",
        "run_attempt": 1,
        "commit_sha": "0" * 40,
    }
    created_at = "2026-06-29T00:00:00Z"
    source_version = "coverage-adapter-test"
    test_records = [
        {"payload": {"canonical_test_id": test_id}}
        for test_id in (test_ids or ["junit:tests/test_example.py::test_example"])
    ]
    parsers = {
        "lcov": lambda: _parse_lcov(path, context, created_at, source_version, test_records),
        "cobertura": lambda: _parse_cobertura(path, context, created_at, source_version, test_records),
        "coveragepy-xml": lambda: _parse_cobertura(path, context, created_at, source_version, test_records),
        "jacoco": lambda: _parse_jacoco(path, context, created_at, source_version, test_records),
        "coverage.py": lambda: _parse_coveragepy_json(path, context, created_at, source_version),
        "coveragepy-json": lambda: _parse_coveragepy_json(path, context, created_at, source_version),
    }
    if input_format not in parsers:
        raise ValueError(f"unsupported coverage input format: {input_format}")
    records = parsers[input_format]()
    payloads = [record["payload"] for record in records]
    return {
        "input_format": input_format,
        "sourceRef": str(path),
        "coverage_slices": payloads,
        "parser_diagnostics": _coverage_diagnostics(input_format, payloads),
    }


def _coverage_diagnostics(input_format: str, payloads: list[dict[str, Any]]) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    for payload in payloads:
        context_lines = {str(item.get("line")) for item in payload.get("contexts", []) if "line" in item}
        hit_lines = set((payload.get("line_hits") or {}).keys())
        if input_format in {"coverage.py", "coveragepy-json"} and (not payload.get("contexts") or not hit_lines <= context_lines):
            diagnostics.append(
                {
                    "code": "contextless_lines",
                    "severity": "warning",
                    "message": f"coverage slice has no contexts: {payload.get('file', 'unknown')}",
                }
            )
        if payload.get("branch_hits") == [] and input_format in {"lcov", "jacoco"}:
            diagnostics.append(
                {
                    "code": "branch_coverage_absent",
                    "severity": "info",
                    "message": f"branch coverage absent or not reported: {payload.get('file', 'unknown')}",
                }
            )
    return diagnostics
