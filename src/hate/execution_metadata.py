"""実行座標の型・範囲・aliasを、入力経路に依存せず検証する。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from .input_values import ParsedFloat, positive_run_attempt

EXECUTION_FIELDS = (
    "retry_index", "attempt_index", "retry_count", "matrix", "matrix_values",
    "shard_index", "shard_total", "shard_count", "flaky",
)


def _nonnegative_index(value: Any) -> int:
    if type(value) is int and value == 0:
        return 0
    if isinstance(value, float) and value == 0:
        exact = Decimal(value.lexeme) if isinstance(value, ParsedFloat) else Decimal(str(value))
        if exact == 0:
            return 0
    return positive_run_attempt(value)


def normalize_execution_metadata(data: dict[str, Any], location: str, *, execution: bool = True) -> None:
    """所有済み入力を正規化し、不正値には位置付きValueErrorを返す。"""
    for field in ("matrix", "matrix_values"):
        if field in data and not isinstance(data[field], dict):
            raise ValueError(f"{location}.{field} must be a JSON object")
    _alias(data, "matrix", "matrix_values", location)
    if "flaky" in data and type(data["flaky"]) is not bool:
        raise ValueError(f"{location}.flaky must be a boolean")
    if not execution:
        return
    if "status" in data and not isinstance(data["status"], str):
        raise ValueError(f"{location}.status must be a string")
    for field in ("retry_index", "attempt_index", "retry_count", "shard_index", "shard_total", "shard_count"):
        if field not in data:
            continue
        positive = field in {"shard_total", "shard_count"}
        try:
            data[field] = positive_run_attempt(data[field]) if positive else _nonnegative_index(data[field])
        except (ValueError, InvalidOperation) as exc:
            raise ValueError(f"{location}.{field} must be a JSON integer >= {1 if positive else 0}") from exc
    _alias(data, "retry_index", "attempt_index", location)
    _alias(data, "shard_total", "shard_count", location)


def _alias(data: dict[str, Any], canonical: str, alias: str, location: str) -> None:
    if canonical in data and alias in data and data[canonical] != data[alias]:
        raise ValueError(f"{location}: conflicting {canonical} and {alias} declarations")
    if canonical not in data and alias in data:
        data[canonical] = data[alias]
