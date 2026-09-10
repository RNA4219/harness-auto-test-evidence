"""橋渡し入力の指紋と、自身が生成するファイルの除外記録。"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .protocol import PathRole

TEMPORARY_PREFIX = ".hate-bridge-"
LOCAL_OUTPUT_ARGUMENTS = frozenset({"out", "manifest_out"})
Exclusion = tuple[Path, str]


def collect_inputs(
    arguments: Mapping[str, object],
    roles: tuple[tuple[str, PathRole], ...],
    base: Path | None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    declared = dict(roles)
    for name, value in sorted(arguments.items()):
        if isinstance(value, Path) and name not in declared and name not in LOCAL_OUTPUT_ARGUMENTS:
            raise ValueError(f"unregistered bridge path argument: {name}")
    handoff_root = (Path.cwd() / ".hate" / "bridge" if base is None else base).resolve()
    artifacts: list[Exclusion] = (
        [(handoff_root, "directory")] if base is None else [
            (handoff_root / "bridge-request.json", "file"),
            (handoff_root, "temporary-files"),
        ]
    )
    refs: list[dict[str, Any]] = []
    paths: dict[str, dict[str, Any]] = {}
    for name, role in sorted(declared.items()):
        value = arguments.get(name)
        if value is None:
            continue
        if not isinstance(value, Path):
            raise ValueError(f"bridge path argument must be a Path: {name}")
        path = value.resolve()
        try:
            path.stat()
        except FileNotFoundError:
            exists = False
        else:
            exists = True
        if role == "input" and not exists:
            raise ValueError(f"bridge input not found: {name}: {path}")
        if _excluded(path, artifacts):
            raise ValueError(f"bridge input overlaps generated handoff artifacts: {name}")
        if not exists and handoff_root.is_relative_to(path):
            raise ValueError(f"handoff output would create missing path argument: {name}")
        if role == "destination" and exists and not path.is_dir():
            raise ValueError(f"bridge destination must be a directory: {name}: {path}")
        paths[name] = {"path": str(path), "role": role, "exists": exists}
        if exists:
            refs.append(input_reference(name, path, artifacts))
    return refs, paths


def _excluded(path: Path, exclusions: list[Exclusion]) -> bool:
    return any(
        (kind == "file" and path == excluded)
        or (kind == "directory" and path.is_relative_to(excluded))
        or (
            kind == "temporary-files" and path.parent == excluded
            and path.name.startswith(TEMPORARY_PREFIX) and path.name.endswith(".tmp")
        )
        for excluded, kind in exclusions
    )


def input_reference(argument: str, path: Path, exclusions: list[Exclusion]) -> dict[str, Any]:
    path = path.resolve()
    if _excluded(path, exclusions):
        raise ValueError(f"bridge input overlaps generated handoff artifacts: {argument}")
    applicable = [(excluded, kind) for excluded, kind in exclusions if excluded.is_relative_to(path)]
    reference: dict[str, Any] = {"argument": argument, "path": str(path)}
    if path.is_file():
        with path.open("rb") as stream:
            sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
        reference.update(sha256=sha256, kind="file")
        return reference
    if not path.is_dir():
        raise ValueError(f"bridge input is not a file or directory: {argument}")
    digest = hashlib.sha256()
    for child in sorted(path.rglob("*")):
        if _excluded(child, applicable) or not child.is_file():
            continue
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with child.open("rb") as stream:
            digest.update(hashlib.file_digest(stream, "sha256").digest())
    reference.update(sha256=digest.hexdigest(), kind="directory")
    if applicable:
        reference["excluded_paths"] = [
            {"path": excluded.relative_to(path).as_posix(), "kind": kind}
            for excluded, kind in applicable
        ]
    return reference
