"""P0bのJSON/NDJSONを、数値の原表記と位置付き診断を保持して読む。"""

from __future__ import annotations

import json
import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .input_values import ParsedFloat
from .json_input import unique_json_object
from .p0b_types import ExportError


def _parse_float(value: str) -> ParsedFloat:
    number = ParsedFloat(value)
    if not math.isfinite(number):
        raise ValueError("JSON number exceeds the supported finite range")
    return number


def _invalid_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle, parse_float=_parse_float, parse_constant=_invalid_constant, object_pairs_hook=unique_json_object)
        if not isinstance(data, dict):
            raise ValueError("must contain a JSON object")
    except (OSError, UnicodeError, ValueError) as exc:
        raise ExportError(f"{path}: {exc}", exit_code=1) from exc
    return data


def iter_ndjson(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    location = str(path)
    try:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                location = f"{path}:{line_number}"
                record = json.loads(line, parse_float=_parse_float, parse_constant=_invalid_constant, object_pairs_hook=unique_json_object)
                if not isinstance(record, dict):
                    raise ValueError("record must be a JSON object")
                yield line_number, record
    except (OSError, UnicodeError, ValueError) as exc:
        raise ExportError(f"{location}: {exc}", exit_code=1) from exc


def read_ndjson(path: Path) -> list[dict[str, Any]]:
    return [record for _, record in iter_ndjson(path)]
