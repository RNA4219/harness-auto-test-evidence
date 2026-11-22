"""書込前にbundleの構造・宣言したQEG契約・artifact一覧を検証する。"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from hate.schema_resources import read_schema

from .atomic_write import compute_json_hash, compute_json_hash_for_write
from .models import STORED_ARTIFACT_KINDS, LocalStoreError


@cache
def _qeg_validator() -> Draft202012Validator:
    return Draft202012Validator(read_schema("qeg-bundle.schema.json"))


def _nonblank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _structure_errors(data: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    nodes = data.get("nodes", [])
    seen: dict[str, int] = {}
    if not isinstance(nodes, list):
        errors.append({"issue": "invalid_bundle_nodes", "field": "nodes", "error": "nodes must be an array"})
    else:
        for position, node in enumerate(nodes):
            field = f"nodes.{position}"
            if not isinstance(node, dict):
                errors.append({"issue": "invalid_bundle_node", "field": field, "error": "node must be an object"})
                continue
            if not _nonblank(node.get("kind")):
                errors.append({"issue": "invalid_bundle_node", "field": field + ".kind", "error": "kind must be a non-blank string"})
            if "id" in node:
                identifier = node["id"]
                if not _nonblank(identifier):
                    errors.append({"issue": "invalid_bundle_node", "field": field + ".id", "error": "id must be a non-blank string"})
                elif identifier in seen:
                    errors.append({"issue": "duplicate_node_id", "field": field + ".id", "first_node": seen[identifier]})
                else:
                    seen[identifier] = position
            for name in ("data", "payload"):
                if name in node and not isinstance(node[name], dict):
                    errors.append({"issue": "invalid_bundle_node", "field": field + "." + name, "error": "payload must be an object"})
    if "metadata" in data and not isinstance(data["metadata"], dict):
        errors.append({"issue": "invalid_bundle_metadata", "field": "metadata", "error": "metadata must be an object"})
    edges = data.get("edges", [])
    if not isinstance(edges, list):
        errors.append({"issue": "invalid_bundle_edges", "field": "edges", "error": "edges must be an array"})
    else:
        for position, edge in enumerate(edges):
            relation = "kind" if isinstance(edge, dict) and "kind" in edge else "relationship"
            if not isinstance(edge, dict) or any(not _nonblank(edge.get(name)) for name in (relation, "from", "to")):
                errors.append({"issue": "invalid_bundle_edge", "field": f"edges.{position}", "error": "edge requires a relation, from and to strings"})
    metadata = data.get("metadata")
    if "completeness" in data or (isinstance(metadata, dict) and "qegVersion" in metadata):
        errors.extend(
            {"issue": "invalid_qeg_bundle", "field": ".".join(map(str, error.absolute_path)), "error": error.message}
            for error in _qeg_validator().iter_errors(data)
        )
    return errors


@dataclass
class PreparedBundle:
    bundle_id: str
    artifacts: dict[str, dict[str, Any]]
    content_hashes: dict[str, str]
    canonical_hash: str = ""


def prepare_bundle(data: dict[str, Any], source: Path) -> PreparedBundle:
    errors = _structure_errors(data)
    if errors:
        raise LocalStoreError("Invalid bundle input", "validate_bundle", source, errors)
    artifacts: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    try:
        canonical_hash = compute_json_hash(data)
        bundle_id = "bundle-" + canonical_hash.split(":")[1][:16]
        for position, node in enumerate(data.get("nodes", [])):
            if node["kind"] not in STORED_ARTIFACT_KINDS:
                continue
            digest = compute_json_hash_for_write(node)
            identifier = "artifact-" + digest.split(":")[1][:16]
            if identifier in artifacts:
                raise LocalStoreError(
                    "Duplicate artifact in bundle", "validate_bundle", source,
                    [{"issue": "duplicate_artifact_id", "field": f"nodes.{position}", "artifact_id": identifier}],
                )
            artifacts[identifier], hashes[identifier] = node, digest
    except (ValueError, TypeError, RecursionError) as exc:
        raise LocalStoreError(
            f"Bundle cannot be serialized: {exc}", "validate_bundle", source,
            [{"issue": "invalid_bundle_json", "error": str(exc)}],
        ) from exc
    return PreparedBundle(bundle_id, artifacts, hashes, canonical_hash)
