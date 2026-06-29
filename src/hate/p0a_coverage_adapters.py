from __future__ import annotations

import hashlib
import json
import mimetypes
import posixpath
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .p0a_constants import REDACTION_STATUS, SCHEMA_VERSION, SOURCE_TOOL
from .p0a_io import (
    _artifact_kind,
    _dq,
    _file_sha256,
    _read_optional_json,
    _slug,
    _stable_sha256,
    _stable_source_ref,
    _to_posix,
)
from .p0a_records import _envelope

def _parse_lcov(
    path: Path,
    context: dict[str, Any],
    created_at: str,
    source_version: str,
    test_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    records: list[dict[str, Any]] = []
    current_file: str | None = None
    line_hits: dict[str, int] = {}
    branch_hits: list[dict[str, int]] = []
    contexts = [{"test_id": record["payload"]["canonical_test_id"]} for record in test_records]
    def flush() -> None:
        nonlocal current_file, line_hits, branch_hits
        if current_file is None:
            return
        record_suffix = Path(current_file).stem
        payload = {
            "format": "lcov",
            "file": _to_posix(current_file),
            "line_hits": dict(sorted(line_hits.items(), key=lambda kv: int(kv[0]))),
            "branch_hits": branch_hits,
            "contexts": contexts,
        }
        records.append(
            _envelope(
                context,
                "coverage_slice",
                f"coverage-slice-{context['run_id']}-{context['run_attempt']}-{_slug(record_suffix)}",
                created_at,
                source_version,
                payload,
            )
        )
        current_file = None
        line_hits = {}
        branch_hits = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("SF:"):
            flush()
            current_file = line[3:]
        elif line.startswith("DA:"):
            line_no, hits = line[3:].split(",", 1)
            line_hits[str(int(line_no))] = int(hits)
        elif line.startswith("BRDA:"):
            line_no, block, branch, hits = line[5:].split(",", 3)
            branch_hits.append(
                {
                    "line": int(line_no),
                    "block": int(block),
                    "branch": int(branch),
                    "hits": 0 if hits == "-" else int(hits),
                }
            )
        elif line == "end_of_record":
            flush()
    flush()
    return records

def _parse_cobertura(
    path: Path,
    context: dict[str, Any],
    created_at: str,
    source_version: str,
    test_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    root = ET.parse(path).getroot()
    records: list[dict[str, Any]] = []
    contexts = [{"test_id": record["payload"]["canonical_test_id"]} for record in test_records]
    class_index = 0
    for package_node in root.findall(".//package"):
        package_name = package_node.attrib.get("name", "")
        for class_node in package_node.findall(".//class"):
            class_index += 1
            filename = _cobertura_class_path(class_node, package_name, class_index)
            line_hits = _cobertura_line_hits(class_node)
            if not line_hits:
                continue
            payload = {
                "format": "cobertura",
                "file": _normalize_coverage_path(filename, package_name),
                "line_hits": dict(sorted(line_hits.items(), key=lambda kv: int(kv[0]))),
                "branch_hits": [],
                "contexts": contexts,
            }
            records.append(
                _envelope(
                    context,
                    "coverage_slice",
                    f"coverage-slice-{context['run_id']}-{context['run_attempt']}-cobertura-{_slug(payload['file'])}",
                    created_at,
                    source_version,
                    payload,
                )
            )
    if class_index == 0:
        for class_index, class_node in enumerate(root.findall(".//class"), start=1):
            filename = _cobertura_class_path(class_node, "", class_index)
            line_hits = _cobertura_line_hits(class_node)
            if not line_hits:
                continue
            payload = {
                "format": "cobertura",
                "file": _normalize_coverage_path(filename),
                "line_hits": dict(sorted(line_hits.items(), key=lambda kv: int(kv[0]))),
                "branch_hits": [],
                "contexts": contexts,
            }
            records.append(
                _envelope(
                    context,
                    "coverage_slice",
                    f"coverage-slice-{context['run_id']}-{context['run_attempt']}-cobertura-{_slug(payload['file'])}",
                    created_at,
                    source_version,
                    payload,
                )
            )
    return records

def _cobertura_class_path(class_node: ET.Element, package_name: str, class_index: int) -> str:
    filename = class_node.attrib.get("filename")
    if filename:
        return filename
    class_name = class_node.attrib.get("name") or f"cobertura-{class_index}"
    class_path = class_name.replace(".", "/")
    if package_name and not class_path.startswith(package_name.replace(".", "/")):
        return posixpath.join(package_name.replace(".", "/"), class_path)
    return class_path

def _cobertura_line_hits(class_node: ET.Element) -> dict[str, int]:
    line_hits: dict[str, int] = {}
    for line in class_node.findall(".//line"):
        number = line.attrib.get("number")
        if not number:
            continue
        line_hits[str(int(number))] = int(line.attrib.get("hits", "0"))
    return line_hits

def _normalize_coverage_path(raw_path: str, package_name: str = "") -> str:
    normalized = _to_posix(raw_path).strip()
    if not normalized:
        return package_name.replace(".", "/") or "unknown"
    normalized = re.sub(r"^[A-Za-z]:/+", "", normalized)
    normalized = re.sub(r"^/+", "", normalized)
    normalized = re.sub(r"/+", "/", normalized)
    for marker in ("src/", "tests/", "test/", "packages/", "pkg/", "app/", "lib/"):
        index = normalized.find(marker)
        if index >= 0:
            return posixpath.normpath(normalized[index:])
    if package_name and "/" not in normalized:
        normalized = posixpath.join(package_name.replace(".", "/"), normalized)
    return posixpath.normpath(normalized)

def _parse_jacoco(
    path: Path,
    context: dict[str, Any],
    created_at: str,
    source_version: str,
    test_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    root = ET.parse(path).getroot()
    records: list[dict[str, Any]] = []
    contexts = [{"test_id": record["payload"]["canonical_test_id"]} for record in test_records]
    for package in root.findall(".//package"):
        package_name = package.attrib.get("name", "")
        for source_file in package.findall("sourcefile"):
            filename = source_file.attrib.get("name", "")
            if not filename:
                continue
            file_path = _normalize_coverage_path(filename, package_name)
            line_hits = {
                str(int(line.attrib["nr"])): int(line.attrib.get("ci", "0"))
                for line in source_file.findall("line")
                if line.attrib.get("nr")
            }
            if not line_hits:
                continue
            branch_hits = [
                {
                    "line": int(line.attrib["nr"]),
                    "block": 0,
                    "branch": index,
                    "hits": int(line.attrib.get("cb", "0")),
                }
                for index, line in enumerate(source_file.findall("line"))
                if int(line.attrib.get("mb", "0")) + int(line.attrib.get("cb", "0")) > 0
            ]
            payload = {
                "format": "jacoco",
                "file": file_path,
                "line_hits": dict(sorted(line_hits.items(), key=lambda kv: int(kv[0]))),
                "branch_hits": branch_hits,
                "contexts": contexts,
            }
            records.append(
                _envelope(
                    context,
                    "coverage_slice",
                    f"coverage-slice-{context['run_id']}-{context['run_attempt']}-jacoco-{_slug(file_path)}",
                    created_at,
                    source_version,
                    payload,
                )
            )
    return records

def _parse_coveragepy_json(
    path: Path,
    context: dict[str, Any],
    created_at: str,
    source_version: str,
) -> list[dict[str, Any]]:
    """Parse coverage.py JSON export with context data into coverage_slice records."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("coverage.py JSON must be an object")
    meta = data.get("meta", {})
    if not isinstance(meta, dict):
        raise ValueError("coverage.py meta must be an object")
    show_contexts = bool(meta.get("show_contexts", False))
    if not show_contexts:
        raise ValueError("coverage.py JSON must have show_contexts: true for context extraction")
    files = data.get("files", {})
    if not isinstance(files, dict):
        raise ValueError("coverage.py files must be an object")
    records: list[dict[str, Any]] = []
    for file_path, file_data in files.items():
        if not isinstance(file_data, dict):
            continue
        executed_lines = file_data.get("executed_lines", [])
        if not isinstance(executed_lines, list):
            continue
        # Build line_hits from executed_lines
        line_hits: dict[str, int] = {}
        for line_no in executed_lines:
            if isinstance(line_no, int):
                line_hits[str(line_no)] = 1
        # Extract contexts from file_data.contexts
        contexts_data = file_data.get("contexts", {})
        if not isinstance(contexts_data, dict):
            contexts_data = {}
        # Build unique context objects from all line contexts
        seen_contexts: set[tuple[str, int]] = set()
        contexts: list[dict[str, Any]] = []
        for line_key, test_contexts in contexts_data.items():
            if test_contexts is None:
                continue
            if not isinstance(test_contexts, list):
                continue
            for test_id in test_contexts:
                if isinstance(test_id, str) and test_id:
                    context_key = (test_id, int(line_key))
                    if context_key not in seen_contexts:
                        seen_contexts.add(context_key)
                        contexts.append({"test_id": test_id, "line": int(line_key)})
        payload = {
            "format": "coverage.py",
            "file": _to_posix(file_path),
            "line_hits": dict(sorted(line_hits.items(), key=lambda kv: int(kv[0]))),
            "branch_hits": [],
            "contexts": contexts,
        }
        record_suffix = Path(file_path).stem
        records.append(
            _envelope(
                context,
                "coverage_slice",
                f"coverage-slice-{context['run_id']}-{context['run_attempt']}-{_slug(record_suffix)}",
                created_at,
                source_version,
                payload,
            )
        )
    return records

