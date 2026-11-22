"""P0aの許可宣言を検証し、正式なQEG exportの可否を判定する。"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from .input_values import ParsedFloat
from .p0b_types import ExportError

_DECISIONS = {"eligible", "conditional", "ineligible", "hard_dq"}


def authorize_precheck(record: dict[str, Any], path: Path, out_dir: Path) -> str:
    """不正形式は終了コード1、明示的な不許可は2とし、出力には触れない。"""
    location = f"{path}: payload"
    payload = record.get("payload")
    if not isinstance(payload, dict):
        raise ExportError(f"{location}: must be an object")
    for field in ("decision", "exit_code", "dq_hits", "soft_gaps", "reasons", "qeg_export_allowed"):
        if field not in payload:
            raise ExportError(f"{location}.{field}: required field is missing")

    decision = payload["decision"]
    if not isinstance(decision, str) or decision not in _DECISIONS:
        raise ExportError(f"{location}.decision: must be eligible, conditional, ineligible or hard_dq")
    exit_code = payload["exit_code"]
    exact_code = Decimal(exit_code.lexeme) if isinstance(exit_code, ParsedFloat) else exit_code
    if isinstance(exit_code, bool) or not isinstance(exit_code, (int, float)) or exact_code not in (0, 2):
        raise ExportError(f"{location}.exit_code: must be the JSON integer 0 or 2")
    if type(payload["qeg_export_allowed"]) is not bool:
        raise ExportError(f"{location}.qeg_export_allowed: must be a boolean")
    for field, item_type in (("dq_hits", dict), ("soft_gaps", dict), ("reasons", str)):
        values = payload[field]
        if not isinstance(values, list):
            raise ExportError(f"{location}.{field}: must be an array")
        for index, value in enumerate(values):
            if not isinstance(value, item_type):
                expected = "an object" if item_type is dict else "a string"
                raise ExportError(f"{location}.{field}[{index}]: must be {expected}")

    denials = []
    if decision in {"ineligible", "hard_dq"}:
        denials.append(f"decision is {decision}")
    if not payload["qeg_export_allowed"]:
        denials.append("qeg_export_allowed is false")
    if exact_code == 2:
        denials.append("exit_code is 2")
    if payload["dq_hits"]:
        denials.append("dq_hits is not empty")
    if denials:
        reason = "; ".join(denials)
        # 従来のhard DQ診断JSONを維持する。矛盾する許可宣言があっても拒否する。
        report = {
            "decision": decision,
            "reason": "P0a precheck disqualified" if decision == "hard_dq" else reason,
        }
        raise ExportError(
            f"P0a precheck: {reason} - QEG export not allowed",
            exit_code=2,
            report=report,
            out_dir=out_dir,
        )
    return decision
