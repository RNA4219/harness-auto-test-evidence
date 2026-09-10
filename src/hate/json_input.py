"""入力JSONの重複keyを、後勝ちの上書きにせず診断する。"""

from __future__ import annotations

from typing import Any


def unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result
