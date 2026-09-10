"""Risk debt履歴の構造と経過日数を、出力の生成前に検証する。"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from .input_values import ParsedFloat
from .p0b_io import read_json
from .p0b_types import ExportError


def load_risk_debt_lifecycle(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    record = read_json(path)
    items = record.get("items", [])
    if not isinstance(items, list):
        raise ExportError(f"{path}: $.items must be an array of objects", exit_code=1)
    normalized = []
    for index, item in enumerate(items):
        location = f"{path}: $.items[{index}]"
        if not isinstance(item, dict):
            raise ExportError(f"{location} must be an object", exit_code=1)
        copied = dict(item)
        if "age_days" in item:
            copied["age_days"] = _age_days(item["age_days"], f"{location}.age_days")
        normalized.append(copied)
    return {**record, "items": normalized}


def _age_days(value: Any, location: str) -> int:
    age: int | None = None
    if type(value) is int:
        age = value
    elif isinstance(value, float):
        exact = Decimal(value.lexeme) if isinstance(value, ParsedFloat) else Decimal(str(value))
        if exact.is_finite() and exact == exact.to_integral_value():
            age = int(exact)
    if age is None or age < 0:
        raise ExportError(f"{location} must be a non-negative integer; booleans and fractional values are invalid", exit_code=1)
    return age
