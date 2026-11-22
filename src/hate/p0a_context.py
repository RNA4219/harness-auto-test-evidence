from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .input_values import positive_run_attempt, run_identifier
from .p0a_errors import PrecheckError as PrecheckError
from .p0a_io import _read_json_object
from .p0a_records import _envelope


def _read_context(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PrecheckError(f"missing required input: {path}", exit_code=1)
    context = _read_json_object(path, exact_run_numbers=True)
    required = ["repository", "workflow", "job", "run_id", "run_attempt", "started_at"]
    missing = [field for field in required if field not in context]
    if missing:
        raise PrecheckError(f"{path.name} missing fields: {', '.join(missing)}", exit_code=1)
    try:
        context["run_id"] = run_identifier(context["run_id"], allow_integer=True)
    except ValueError as exc:
        raise PrecheckError(f"{path.name}.run_id: {exc}", exit_code=1) from exc
    try:
        context["run_attempt"] = positive_run_attempt(context["run_attempt"], allow_decimal_string=True)
    except ValueError as exc:
        raise PrecheckError(f"{path.name}.run_attempt: {exc}", exit_code=1) from exc
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

