"""runの識別値を、意味を変える型変換なしで検証する。"""

from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Self


class ParsedFloat(float):
    """JSON数値の元の十進表記を、通常のfloat動作とともに保持する。"""

    lexeme: str

    def __new__(cls, value: str) -> Self:
        number = super().__new__(cls, value)
        number.lexeme = value
        return number


def positive_run_attempt(value: object, *, allow_decimal_string: bool = False) -> int:
    attempt: int | None = None
    if type(value) is int:
        attempt = value
    elif isinstance(value, float) and math.isfinite(value) and value > 0:
        if isinstance(value, ParsedFloat):
            exact = Decimal(value.lexeme)
            if exact == exact.to_integral_value():
                attempt = int(exact)
        elif value.is_integer():
            attempt = int(value)
    elif allow_decimal_string and isinstance(value, str):
        decimal = value.strip()
        if decimal.isascii() and decimal.isdecimal():
            attempt = int(decimal)
    if attempt is None or attempt < 1:
        raise ValueError("must be a positive integer; booleans and fractional values are invalid")
    return attempt


def run_identifier(value: object, *, allow_integer: bool = False) -> str:
    if isinstance(value, str) and value.strip():
        return value
    if allow_integer and type(value) is int:
        return str(value)
    raise ValueError("must be a non-empty run identifier")


def commit_identifier(value: object) -> str:
    """検証済みcommit IDを比較用の小文字へ揃える。短縮IDの同一性は推測しない。"""
    if isinstance(value, str) and re.fullmatch(r"[A-Fa-f0-9]{7,64}", value):
        return value.lower()
    raise ValueError("must be a 7–64 character hexadecimal commit ID")
