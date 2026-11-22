"""保存日時を、小数秒の精度を失わずUTCの時系列キーへ変換する。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .models import LocalStoreError

_TIMESTAMP = re.compile(
    r"(?P<seconds>[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2})"
    r"(?:\.(?P<fraction>[0-9]+))?(?P<zone>[Zz]|[+-][0-9]{2}:[0-9]{2})"
)


def timestamp_key(value: str, *, operation: str, path: Path, field: str = "created_at") -> tuple[int, str]:
    """整数秒と末尾ゼロを除いた小数部で比較し、floatやmicrosecondへ丸めない。"""
    try:
        matched = _TIMESTAMP.fullmatch(value)
        if matched is None:
            raise ValueError("date-time with timezone required")
        stamp = datetime.fromisoformat(matched["seconds"].upper() + matched["zone"].upper().replace("Z", "+00:00"))
        offset = stamp.utcoffset()
        if offset is None:
            raise ValueError("timezone required")
        seconds = (stamp.toordinal() - 1) * 86400 + stamp.hour * 3600 + stamp.minute * 60 + stamp.second
        seconds -= offset.days * 86400 + offset.seconds
        # 桁数の異なる小数も、末尾ゼロ除去後の辞書順が実際の大小関係に一致する。
        return seconds, (matched["fraction"] or "").rstrip("0")
    except (TypeError, ValueError) as exc:
        raise LocalStoreError(
            "Invalid timestamp for history selection", operation, path,
            [{"issue": "invalid_store_timestamp", "field": field, "value": value, "error": str(exc)}],
        ) from exc
