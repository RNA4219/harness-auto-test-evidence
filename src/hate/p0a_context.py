from __future__ import annotations

import hashlib
import json
import mimetypes
import posixpath
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
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
from .p0a_records import _envelope

@dataclass
class PrecheckError(Exception):
    message: str
    exit_code: int = 1
    decision: dict[str, Any] | None = None
    out_dir: Path | None = None
    def __str__(self) -> str:
        return self.message
def _read_context(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PrecheckError(f"missing required input: {path}", exit_code=1)
    with path.open("r", encoding="utf-8") as handle:
        context = json.load(handle)
    if not isinstance(context, dict):
        raise PrecheckError(f"{path.name} must be a JSON object", exit_code=1)
    required = ["repository", "workflow", "job", "run_id", "run_attempt", "started_at"]
    missing = [field for field in required if field not in context]
    if missing:
        raise PrecheckError(f"{path.name} missing fields: {', '.join(missing)}", exit_code=1)
    provider = _normalize_ci_provider(str(context.get("provider") or context.get("ci_provider") or ""))
    if not provider:
        provider = "github-actions" if path.name == "github-context.json" else "generic-ci"
    context["_context_source_name"] = path.name
    context["_ci_provider"] = provider
    return context

def _normalize_ci_provider(provider: str) -> str:
    normalized = provider.strip().lower().replace("_", "-")
    aliases = {
        "github": "github-actions",
        "github-action": "github-actions",
        "github-actions": "github-actions",
        "generic": "generic-ci",
        "generic-ci": "generic-ci",
        "genericci": "generic-ci",
    }
    return aliases.get(normalized, normalized)

def _run_record(context: dict[str, Any], created_at: str, source_version: str) -> dict[str, Any]:
    payload = {
        "repository": context["repository"],
        "workflow": context["workflow"],
        "job": context["job"],
        "event_name": context.get("event_name", "unknown"),
        "started_at": context["started_at"],
        "finished_at": context.get("finished_at"),
        "ci": {
            "provider": context.get("_ci_provider", "github-actions"),
            "run_id": str(context["run_id"]),
            "run_attempt": int(context["run_attempt"]),
            "actor": context.get("actor"),
            "ref": context.get("ref"),
        },
    }
    base_sha = str(context.get("base_sha") or "")
    if re.match(r"^[A-Fa-f0-9]{7,64}$", base_sha):
        payload["base_sha"] = base_sha
    return _envelope(context, "run", f"run-{context['run_id']}-attempt-{context['run_attempt']}", created_at, source_version, payload)

