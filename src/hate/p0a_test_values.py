"""テスト識別値と実行時間を、型変換で意味を変えずに正規化する。"""

from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from typing import Any

from .input_values import ParsedFloat


def identity_text(value: Any, location: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{location} must be a {'string' if allow_empty else 'non-empty string'}")
    return value


def assertion_identity(assertion: dict[str, Any], location: str) -> tuple[str, str, list[str]]:
    full_name = identity_text(assertion.get("fullName", assertion.get("title")), f"{location}.fullName")
    title = identity_text(assertion.get("title", full_name), f"{location}.title", allow_empty=True)
    ancestors = assertion.get("ancestorTitles", [])
    if not isinstance(ancestors, list):
        raise ValueError(f"{location}.ancestorTitles must be an array of strings")
    return full_name, title, [identity_text(item, f"{location}.ancestorTitles[{index}]", allow_empty=True)
                              for index, item in enumerate(ancestors)]


def _duration_number(value: Any, location: str, *, xml: bool = False) -> Decimal:
    if xml and isinstance(value, str):
        if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value.strip()):
            raise ValueError(f"{location} must be a finite non-negative duration")
        try:
            number = Decimal(value.strip())
        except InvalidOperation as exc:
            raise ValueError(f"{location} exceeds the supported numeric range for duration") from exc
    elif type(value) is int:
        number = Decimal(value)
    elif isinstance(value, float):
        number = Decimal(value.lexeme) if isinstance(value, ParsedFloat) else Decimal(str(value))
    else:
        raise ValueError(f"{location} must be a finite non-negative number; booleans and strings are invalid")
    if not number.is_finite() or number < 0:
        raise ValueError(f"{location} must be a finite non-negative duration")
    approximate = float(number)
    if not math.isfinite(approximate) or (number != 0 and approximate == 0):
        raise ValueError(f"{location} exceeds the supported numeric range for duration")
    return number if number else Decimal(0)


def _milliseconds(number: Decimal, *, seconds: bool = False) -> int:
    if seconds:
        sign, digits, exponent = number.as_tuple()
        assert isinstance(exponent, int)
        number = Decimal((sign, digits, exponent + 3))
    return int(number.to_integral_value(rounding=ROUND_HALF_EVEN))


def junit_duration(value: str | None, location: str) -> tuple[float, int]:
    number = _duration_number(value if value is not None else 0, location, xml=True)
    return float(number), _milliseconds(number, seconds=True)


def pytest_duration(test: dict[str, Any], location: str) -> int:
    stages = []
    for name in ("setup", "call", "teardown"):
        if name not in test:
            continue
        stage = test[name]
        if not isinstance(stage, dict):
            raise ValueError(f"{location}.{name} must be an object")
        if "duration" in stage:
            stages.append(_duration_number(stage["duration"], f"{location}.{name}.duration"))
    if "duration" in test:
        # 既存のtest単位の時間を優先し、stage時間を二重加算しない。
        return _milliseconds(_duration_number(test["duration"], f"{location}.duration"), seconds=True)
    if not stages:
        return 0
    # stageごとにmsへ丸めず、十進表記の合計を一度だけ丸める。
    exponents = [stage.as_tuple().exponent for stage in stages]
    assert all(isinstance(exponent, int) for exponent in exponents)
    minimum_exponent = min(int(exponent) for exponent in exponents)
    with localcontext() as context:
        context.prec = max(28, max(stage.adjusted() for stage in stages) - minimum_exponent + 3)
        total = sum(stages, Decimal(0))
    return _milliseconds(total, seconds=True)


def assertion_duration(assertion: dict[str, Any], location: str) -> dict[str, Any]:
    value = assertion.get("duration", 0)
    if value is None:
        return {
            "duration_ms": 0,
            "parser_diagnostics": [{"code": "duration_not_reported", "severity": "warning", "sourceRef": f"{location}.duration",
                                    "message": "Duration was not reported; duration_ms=0 is a compatibility placeholder."}],
        }
    return {"duration_ms": _milliseconds(_duration_number(value, f"{location}.duration"))}
