from __future__ import annotations

import hashlib
import json
import mimetypes
import posixpath
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .p0a_constants import REDACTION_STATUS, SCHEMA_VERSION, SOURCE_TOOL
from .p0a_io import (
    _artifact_kind,
    _dq,
    _file_sha256,
    _read_optional_json,
    _slug,
    _stable_sha256,
    _stable_source_ref,
    _to_posix,
)
def _read_sarif(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("SARIF root must be an object")
    if data.get("version") is None or not isinstance(data.get("runs"), list):
        raise ValueError("SARIF requires version and runs")
    return data

def _sarif_dq_hits(sarif: dict[str, Any]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for run in sarif.get("runs", []):
        if not isinstance(run, dict):
            continue
        for result in run.get("results", []):
            if not isinstance(result, dict):
                continue
            level = str(result.get("level", "")).lower()
            properties = result.get("properties", {}) if isinstance(result.get("properties"), dict) else {}
            severity = str(properties.get("security-severity") or properties.get("severity") or "").lower()
            if level in {"error"} or severity in {"high", "critical"}:
                hits.append(_dq("HATE-DQ-010", "unresolved high or critical SARIF finding", "results.sarif"))
    return hits

