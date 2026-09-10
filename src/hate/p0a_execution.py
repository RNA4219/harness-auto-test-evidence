"""テストadapterの実行座標、宣言値、record識別を共通化する。"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .execution_metadata import EXECUTION_FIELDS, normalize_execution_metadata
from .input_values import ParsedFloat


def _parse_float(value: str) -> ParsedFloat:
    parsed = ParsedFloat(value)
    if not math.isfinite(parsed):
        raise ValueError("JSON number exceeds the supported finite range")
    return parsed


def _invalid_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def read_test_report(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, parse_float=_parse_float, parse_constant=_invalid_constant)


def json_execution_metadata(item: dict[str, Any], location: str, *, native_count: str | None = None) -> dict[str, Any]:
    metadata = {field: item[field] for field in EXECUTION_FIELDS if field in item}
    normalize_execution_metadata(metadata, location)
    if native_count and native_count in item:
        declared = {"retry_count": item[native_count]}
        normalize_execution_metadata(declared, f"{location}.{native_count}")
        if "retry_count" in metadata and metadata["retry_count"] != declared["retry_count"]:
            raise ValueError(f"{location}: conflicting retry_count and {native_count}")
        metadata.update(declared)
    return metadata


def merge_execution_metadata(first: dict[str, Any], second: dict[str, Any], location: str) -> dict[str, Any]:
    """同一観測内の二つの宣言は、矛盾を隠して上書きしない。"""
    for field in first.keys() & second.keys():
        if first[field] != second[field]:
            raise ValueError(f"{location}: conflicting {field} declarations")
    merged = {**first, **second}
    normalize_execution_metadata(merged, location)
    return merged


def xml_execution_metadata(attributes: Mapping[str, str], properties: Mapping[str, str], location: str) -> dict[str, Any]:
    converted = []
    for source in (properties, attributes):
        metadata: dict[str, Any] = {}
        for field in (*EXECUTION_FIELDS, "retry"):
            if field not in source:
                continue
            value = source[field].strip()
            target = "retry_index" if field == "retry" else field
            if field in {"matrix", "matrix_values"}:
                parsed = json.loads(value, parse_float=_parse_float, parse_constant=_invalid_constant)
            elif field == "flaky":
                if value.lower() not in {"true", "false", "1", "0", "yes", "no", "on", "off", "y", "n"}:
                    raise ValueError(f"{location}.flaky must be a boolean declaration")
                parsed = value.lower() in {"true", "1", "yes", "on", "y"}
            else:
                try:
                    # XMLの番号は文字列。ASCIIの十進表記だけを整数として受理する。
                    if not value.isascii() or "_" in value:
                        raise ValueError("invalid decimal integer")
                    parsed = (int(value) if value.lstrip("+-").isdecimal()
                              else json.loads(value, parse_float=_parse_float, parse_constant=_invalid_constant))
                except ValueError as exc:
                    raise ValueError(f"{location}.{field} must be an integer declaration") from exc
            if target in metadata and metadata[target] != parsed:
                raise ValueError(f"{location}: conflicting retry and retry_index")
            metadata[target] = parsed
        normalize_execution_metadata(metadata, location)
        converted.append(metadata)
    return merge_execution_metadata(converted[0], converted[1], location)


def execution_record_id(payload: dict[str, Any], context: dict[str, Any], occurrences: dict[str, int]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    occurrences[digest] = occurrences.get(digest, 0) + 1
    return f"test-result-{context['run_id']}-{context['run_attempt']}-{payload['framework']}-{digest}-{occurrences[digest]}"


def mark_duplicate_observations(tests: list[dict[str, Any]]) -> list[str]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for test in tests:
        key = json.dumps([test["canonical_test_id"], test.get("matrix", {}), test.get("retry_index", 0),
                          test.get("shard_index")], sort_keys=True, ensure_ascii=False)
        groups.setdefault(key, []).append(test)
    duplicates = set()
    for group in groups.values():
        if len(group) > 1:
            duplicates.add(group[0]["canonical_test_id"])
            for test in group:
                test.setdefault("parser_diagnostics", []).append({"code": "duplicate_testcase_id", "severity": "error"})
    return sorted(duplicates)
