from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .input_values import ParsedFloat
from .json_input import unique_json_object
from .p0a_errors import PrecheckError


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json_object(path)


def _read_json_object(path: Path, *, exact_run_numbers: bool = False) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle, parse_float=ParsedFloat if exact_run_numbers else float,
                             object_pairs_hook=unique_json_object if exact_run_numbers else None)
    except (OSError, UnicodeError, ValueError) as exc:
        raise PrecheckError(f"cannot read JSON input {path}: {exc}", exit_code=1) from exc
    if not isinstance(data, dict):
        raise PrecheckError(f"{path.name} must contain a JSON object", exit_code=1)
    return data

def _stable_sha256(value: Any) -> str:
    blob = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()

def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def _write_ndjson(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in records), encoding="utf-8")

def _dq(code: str, message: str, source_ref: str) -> dict[str, str]:
    return {"code": code, "message": message, "source_ref": source_ref}

def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "item"

def _to_posix(value: str) -> str:
    return value.replace("\\", "/")

def _stable_source_ref(path: Path) -> str:
    value = path.resolve().as_posix()
    marker = "/fixtures/golden/"
    if marker in value:
        return "fixture:/" + value.split(marker, 1)[1]
    try:
        return "workspace:/" + path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return "path:/" + path.name

def _artifact_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".zip", ".trace"} or "trace" in path.name.lower():
        return "trace"
    if suffix in {".log", ".txt"}:
        return "other"
    if suffix in {".html", ".md"}:
        return "report"
    if suffix in {".png", ".jpg", ".jpeg"}:
        return "screenshot"
    if suffix in {".webm", ".mp4"}:
        return "video"
    return "other"
