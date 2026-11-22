"""retry/shard/matrixの宣言値を出力前に検証し、数値aliasを正規化する。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .execution_metadata import normalize_execution_metadata
from .execution_status import validate_execution_status
from .p1a_io import TrustError


def validate_retry_inputs(bundle: dict[str, Any], path: Path) -> None:
    for index, node in enumerate(bundle.get("nodes", [])):
        if node.get("kind") not in {"test", "execution_evidence"}:
            continue
        data = node.get("data", {})
        location = f"{path}: nodes[{index}].data"
        try:
            normalize_execution_metadata(data, location, execution=node.get("kind") == "execution_evidence")
            validate_execution_status(data, location)
        except ValueError as exc:
            raise TrustError(str(exc), exit_code=1) from exc
