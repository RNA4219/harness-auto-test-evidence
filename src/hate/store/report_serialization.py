"""保存証跡の決定的なJSON表現と、実行観測値を除いたハッシュ。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .atomic_write import compute_json_hash


def _ordered(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _ordered(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_ordered(item) for item in value]
    return value


def report_data(
    data: dict[str, Any], *, observation_field: str, include_observation: bool = False,
) -> dict[str, Any]:
    return {
        key: _ordered(data[key]) for key in sorted(data)
        if include_observation or key != observation_field
    }


def report_hash(data: dict[str, Any], *, hash_field: str, observation_field: str) -> str:
    """キー順・実行時刻・既に埋めた自身のhashに依存せず、内容から再計算する。"""
    return compute_json_hash({key: value for key, value in data.items() if key not in {hash_field, observation_field}})


def relative_diagnostics(diagnostics: list[dict[str, Any]], root: Path) -> list[dict[str, Any]]:
    """現在のストア配置を診断の内容IDに混ぜず、相対パスで対象を示す。"""
    root_path = str(root.resolve())
    escaped_root = root_path.replace("\\", "\\\\")
    prefixes = (escaped_root + "\\\\", root_path + "/", root_path + "\\")

    def relative(value: Any) -> Any:
        if isinstance(value, str):
            if value in {root_path, escaped_root}:
                return "<store>"
            for prefix in prefixes:
                value = value.replace(prefix, "<store>/")
            if "<store>/" in value:
                value = value.replace("\\\\", "/").replace("\\", "/")
            return value
        if isinstance(value, dict):
            return {key: relative(item) for key, item in value.items()}
        if isinstance(value, list):
            return [relative(item) for item in value]
        return value

    return [dict(relative(item)) for item in diagnostics]
