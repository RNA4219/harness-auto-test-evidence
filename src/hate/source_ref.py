from __future__ import annotations

import hashlib
import posixpath
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs


SAFE_ROOT_MARKERS = ("/workspace/", "/workspaces/", "/repo/", "/project/")
KNOWN_TOP_LEVELS = ("src/", "tests/", "fixtures/", "schemas/", "docs/")


@dataclass(frozen=True)
class SourceRef:
    raw: str
    artifact_id: str | None
    path: str
    normalized_path: str
    line: int | None
    column: int | None
    context_id: str | None
    source_family: str
    has_traversal: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "artifact_id": self.artifact_id,
            "path": self.path,
            "normalized_path": self.normalized_path,
            "line": self.line,
            "column": self.column,
            "context_id": self.context_id,
            "source_family": self.source_family,
            "has_traversal": self.has_traversal,
        }


def parse_source_ref(value: str) -> SourceRef:
    raw = str(value)
    artifact_id: str | None = None
    path_part = raw
    fragment = ""
    if raw.startswith("artifact:"):
        body = raw.removeprefix("artifact:")
        artifact_id, _, remainder = body.partition("#")
        path_part = artifact_id
        fragment = remainder
    elif "#" in raw:
        path_part, fragment = raw.split("#", 1)

    query = parse_qs(fragment.replace(";", "&"), keep_blank_values=True)
    query_path = _first(query, "path")
    if query_path:
        path_part = query_path
    line = _int_or_none(_first(query, "line") or _line_from_fragment(fragment))
    column = _int_or_none(_first(query, "column") or _first(query, "col"))
    context_id = _first(query, "context") or _first(query, "context_id")
    normalized = normalize_path(path_part)
    return SourceRef(
        raw=raw,
        artifact_id=artifact_id if artifact_id else None,
        path=path_part,
        normalized_path=normalized,
        line=line,
        column=column,
        context_id=context_id,
        source_family=source_family(path_part),
        has_traversal=is_path_traversal(path_part),
    )


def normalize_path(value: str) -> str:
    path = str(value).replace("\\", "/").strip()
    path = re.sub(r"^[A-Za-z]:/", "", path)
    for marker in SAFE_ROOT_MARKERS:
        index = path.find(marker)
        if index >= 0:
            path = path[index + len(marker) :]
    path = path.lstrip("/")
    for marker in KNOWN_TOP_LEVELS:
        index = path.find(marker)
        if index > 0:
            path = path[index:]
            break
    return posixpath.normpath(path)


def source_family(value: str) -> str:
    path = normalize_path(value)
    if path.startswith("tests/"):
        return "test"
    if path.startswith("src/"):
        return "source"
    if path.startswith("fixtures/"):
        return "fixture"
    if path.startswith("schemas/"):
        return "schema"
    if path.startswith("docs/"):
        return "doc"
    return "artifact"


def is_path_traversal(value: str) -> bool:
    raw = str(value).replace("\\", "/").strip()
    if re.match(r"(?i)^https?://", raw):
        return True
    if raw.startswith("/") and not any(marker in raw for marker in SAFE_ROOT_MARKERS):
        return True
    parts = [part for part in raw.split("/") if part]
    return ".." in parts


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def deterministic_record_id(record: dict[str, Any], source_refs: list[str]) -> str:
    kind = str(record.get("record_kind") or record.get("record_type") or "record")
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    key_parts = [
        kind,
        *sorted(source_refs),
        str(payload.get("canonical_test_id") or ""),
        str(payload.get("file") or ""),
        str(payload.get("line") or ""),
        str(payload.get("mutation_id") or ""),
        str(payload.get("contract_id") or ""),
    ]
    digest = hashlib.sha256("\0".join(key_parts).encode("utf-8")).hexdigest()[:16]
    return f"{kind}-{digest}"


def _first(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    return values[0] or None


def _line_from_fragment(fragment: str) -> str | None:
    match = re.search(r"(?:^|[^\w])L?line[=:](\d+)|(?:^|[^\w])L(\d+)", fragment, re.IGNORECASE)
    if not match:
        return None
    return match.group(1) or match.group(2)


def _int_or_none(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None
