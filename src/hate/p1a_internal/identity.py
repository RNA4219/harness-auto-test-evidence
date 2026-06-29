"""P1A canonical identity index with normalization."""

from __future__ import annotations

from typing import Any

from hate.p1a_io import _stable_hash, _normalize_source_ref

SCHEMA_VERSION = "HATE/v1"


def _build_canonical_identity_index(run_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
    identities: list[dict[str, Any]] = []
    for node in bundle.get("nodes", []):
        if node.get("kind") != "test":
            continue
        data = node.get("data", {})
        canonical_test_id = str(data.get("canonical_test_id", ""))
        components = _identity_components(canonical_test_id, data)
        normalized_canonical_test_id = _normalized_canonical_test_id(components)
        aliases = []
        if canonical_test_id and canonical_test_id != normalized_canonical_test_id:
            aliases.append({
                "previous_id": canonical_test_id,
                "reason": "path_normalization",
                "valid_from": run_id,
            })
        identities.append({
            "identity_id": f"identity:{_stable_hash(normalized_canonical_test_id)[:16]}",
            "test_node_id": node.get("id", ""),
            "canonical_test_id": canonical_test_id,
            "normalized_canonical_test_id": normalized_canonical_test_id,
            "identity_components": components,
            "aliases": aliases,
            "source_refs": node.get("sourceRefs", []),
        })
    duplicate_ids = sorted(_duplicates([item["normalized_canonical_test_id"] for item in identities]))
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "canonical_identity_index",
        "run_id": run_id,
        "summary": {
            "identity_count": len(identities),
            "duplicate_normalized_ids": duplicate_ids,
            "has_duplicates": bool(duplicate_ids),
        },
        "identities": identities,
    }


def _identity_components(canonical_test_id: str, data: dict[str, Any]) -> dict[str, Any]:
    framework = str(data.get("framework") or (canonical_test_id.split(":", 1)[0] if ":" in canonical_test_id else ""))
    remainder = canonical_test_id.split(":", 1)[1] if ":" in canonical_test_id else canonical_test_id
    parts = remainder.split("::") if remainder else []
    raw_file = str(data.get("file") or (parts[0] if parts else ""))
    classname = str(data.get("classname") or data.get("class_name") or "")
    name = str(data.get("name") or "")
    if len(parts) >= 3:
        classname = classname or parts[1]
        name = name or "::".join(parts[2:])
    elif len(parts) >= 2:
        name = name or "::".join(parts[1:])
    elif parts:
        name = name or parts[0]
    parameters = _stable_mapping(data.get("parameters") or data.get("params") or {})
    matrix = _stable_mapping(data.get("matrix") or data.get("matrix_values") or {})
    return {
        "framework": framework,
        "package": str(data.get("package", "")),
        "file": _normalize_source_ref(raw_file),
        "classname": classname,
        "name": name,
        "parameters": parameters,
        "matrix": matrix,
    }


def _normalized_canonical_test_id(components: dict[str, Any]) -> str:
    base = f"{components['framework']}:{components['file']}::{components['classname']}::{components['name']}"
    parameters = components.get("parameters", {})
    if parameters:
        return f"{base}::{_stable_hash(parameters)[:12]}"
    return base


def _stable_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): value[key] for key in sorted(value)}


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates