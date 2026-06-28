from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

class TrustError(Exception):
    message: str
    exit_code: int = 1
    def __str__(self) -> str:
        return self.message

def _collect_source_refs(bundle: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for artifact in bundle.get("metadata", {}).get("inputArtifacts", []):
        if artifact.get("path"):
            refs.append(str(artifact["path"]))
    for node in bundle.get("nodes", []):
        refs.extend(str(ref) for ref in node.get("sourceRefs", []))
    for edge in bundle.get("edges", []):
        refs.extend(str(ref) for ref in edge.get("traceability", {}).get("sourceRefs", []))
    return sorted(set(refs))

def _normalize_source_ref(source_ref: str) -> str:
    if source_ref.startswith("fixture:/"):
        return source_ref
    return source_ref.replace("\\", "/")

def _root_kind(source_ref: str) -> str:
    if source_ref.startswith("fixture:/"):
        return "workspace"
    if source_ref.startswith("http://") or source_ref.startswith("https://"):
        return "url"
    if ":" in source_ref[:3]:
        return "windows"
    return "package"

def _stable_ref(path: Path) -> str:
    value = path.resolve().as_posix()
    marker = "/fixtures/golden/"
    if marker in value:
        return "fixture:/" + value.split(marker, 1)[1]
    try:
        return "workspace:/" + path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return "path:/" + path.name

def _stable_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise TrustError(f"{path.name} must contain a JSON object", exit_code=1)
    return data

def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
