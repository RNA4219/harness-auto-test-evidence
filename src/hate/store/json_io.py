"""JSONの項目を失わず、保存形式で表現できる値だけを読み込む。"""

from __future__ import annotations

import json
import math
from typing import Any, NoReturn


def _invalid_number(value: str) -> NoReturn:
    raise ValueError(f"JSON number must be finite: {value}")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        _invalid_number(value)
    if number == 0 and any(character in "123456789" for character in value.lower().split("e")[0]):
        raise ValueError(f"JSON number underflows the supported float range: {value}")
    return number


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def strict_json_loads(content: str) -> Any:
    """重複項目、非有限数、UTF-8へ戻せない文字列を拒否する。"""
    try:
        data = json.loads(content, object_pairs_hook=_unique_object, parse_float=_finite_float, parse_constant=_invalid_number)
    except RecursionError as exc:
        raise ValueError("JSON nesting exceeds parser capacity") from exc
    pending = [data]
    while pending:
        value = pending.pop()
        if isinstance(value, str):
            value.encode("utf-8")
        elif isinstance(value, dict):
            pending.extend(value.keys())
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    return data
