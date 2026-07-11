from __future__ import annotations

import json
from collections.abc import Iterable
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable

DEVELOPMENT_SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "schemas" / "HATE" / "v1"


def read_schema(name: str, *, schema_root: Path | None = None) -> dict[str, Any]:
    """Read a HATE schema from an explicit root, a source checkout, or package data."""
    if schema_root is not None:
        return _read_path(schema_root / name)
    if DEVELOPMENT_SCHEMA_ROOT.exists():
        return _read_path(DEVELOPMENT_SCHEMA_ROOT / name)

    resource = resources.files("hate").joinpath("_schemas", "HATE", "v1", name)
    data = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return data


def iter_schemas(*, schema_root: Path | None = None) -> Iterable[tuple[str, dict[str, Any]]]:
    if schema_root is not None or DEVELOPMENT_SCHEMA_ROOT.exists():
        root: Path = schema_root or DEVELOPMENT_SCHEMA_ROOT
        for path in sorted(root.glob("*.json")):
            yield path.name, _read_path(path)
        return

    package_root = resources.files("hate").joinpath("_schemas", "HATE", "v1")
    for item in sorted(package_root.iterdir(), key=lambda candidate: candidate.name):
        if item.name.endswith(".json"):
            data = json.loads(item.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError(f"{item.name} must contain a JSON object")
            yield item.name, data


def build_schema_registry(*, schema_root: Path | None = None) -> Registry:
    registry = Registry()
    for name, schema in iter_schemas(schema_root=schema_root):
        if "$schema" not in schema:
            continue
        uri = str(schema.get("$id") or f"https://hate.local/schemas/HATE/v1/{name}")
        registry = registry.with_resource(uri, Resource.from_contents(schema))
    return registry


def validate_schema_instance(
    value: Any,
    schema: dict[str, Any],
    *,
    schema_root: Path | None = None,
) -> list[Any]:
    validator = Draft202012Validator(
        schema,
        registry=build_schema_registry(schema_root=schema_root),
        format_checker=FormatChecker(),
    )
    try:
        errors = list(validator.iter_errors(value))
    except Unresolvable as exc:
        errors = [ValidationError(f"unresolved schema reference: {exc}")]
    return sorted(errors, key=lambda error: (list(error.absolute_path), error.message))


def validate_all_schema_documents(*, schema_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    for name, schema in iter_schemas(schema_root=schema_root):
        if "$schema" not in schema:
            continue
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    return errors


def _read_path(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data
