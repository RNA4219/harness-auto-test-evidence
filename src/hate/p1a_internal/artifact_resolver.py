"""P1A artifact path resolution and safety checks."""

from __future__ import annotations

from typing import Any

from hate.p1a_io import _normalize_source_ref, _root_kind, _collect_source_refs

SCHEMA_VERSION = "HATE/v1"


def _build_artifact_resolver_map(run_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for source_ref in _collect_source_refs(bundle):
        entries.append({
            "entry_type": "source_ref",
            "original": source_ref,
            "normalized": _normalize_source_ref(source_ref),
            "root_kind": _root_kind(source_ref),
            "resolution_status": _resolution_status(source_ref),
            "source_refs": [source_ref],
        })
    for node in bundle.get("nodes", []):
        if node.get("kind") != "evidence_artifact":
            continue
        data = node.get("data", {})
        artifact_path = str(data.get("path", ""))
        if not artifact_path:
            continue
        entries.append({
            "entry_type": "artifact_path",
            "artifact_id": str(node.get("id", "")).removeprefix("artifact:"),
            "artifact_kind": data.get("kind", ""),
            "artifact_role": data.get("artifact_role", ""),
            "sha256": data.get("sha256", ""),
            "original": artifact_path,
            "normalized": _normalize_source_ref(artifact_path),
            "root_kind": _root_kind(artifact_path),
            "resolution_status": _resolution_status(artifact_path),
            "source_refs": node.get("sourceRefs", []),
        })
    entries = sorted(entries, key=lambda item: (item.get("entry_type", ""), item.get("original", ""), item.get("artifact_id", "")))
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "artifact_resolution",
        "run_id": run_id,
        "entries": entries,
        "summary": {
            "entry_count": len(entries),
            "unsafe_count": sum(1 for entry in entries if entry["resolution_status"] == "unsafe"),
            "unresolved_count": sum(1 for entry in entries if entry["resolution_status"] == "unresolved"),
            "artifact_path_count": sum(1 for entry in entries if entry["entry_type"] == "artifact_path"),
            "source_ref_count": sum(1 for entry in entries if entry["entry_type"] == "source_ref"),
        },
    }


def _resolution_status(value: str) -> str:
    normalized = value.replace("\\", "/")
    parts = normalized.split("/")
    if ".." in parts:
        return "unsafe"
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return "unsafe"
    if not normalized:
        return "unresolved"
    return "resolved"