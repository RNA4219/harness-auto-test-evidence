"""P0aの入力診断とprecheck判定に共通の例外。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PrecheckError(Exception):
    message: str
    exit_code: int = 1
    decision: dict[str, Any] | None = None
    out_dir: Path | None = None

    def __str__(self) -> str:
        return self.message
