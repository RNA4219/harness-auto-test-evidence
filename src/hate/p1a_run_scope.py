"""現在runの証跡nodeに宣言されたrun/attempt/commitを照合する。"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .input_values import commit_identifier, positive_run_attempt, run_identifier
from .p1a_io import TrustError

CURRENT_RUN_KINDS = frozenset({
    "run", "gate_verdict", "test", "execution_evidence", "coverage",
    "contract_evidence", "mutation_evidence", "evidence_strength", "evidence_artifact",
})


def scoped_data(bundle: dict[str, Any]) -> Iterator[tuple[dict[str, Any], list[str | int]]]:
    for index, node in enumerate(bundle.get("nodes", [])):
        if node.get("kind") not in CURRENT_RUN_KINDS:
            continue
        data = node.get("data", {})
        location: list[str | int] = ["nodes", index, "data"]
        yield data, location
        if node.get("kind") == "run" and isinstance(data.get("ci"), dict):
            yield data["ci"], [*location, "ci"]


def bundle_commit_declarations(bundle: dict[str, Any]) -> Iterator[tuple[Any, list[str | int]]]:
    metadata = bundle.get("metadata", {})
    if "commitSha" in metadata:
        yield metadata["commitSha"], ["metadata", "commitSha"]
    for data, location in scoped_data(bundle):
        if "commit_sha" in data:
            yield data["commit_sha"], [*location, "commit_sha"]


def _location(path: Path, fields: list[str | int]) -> str:
    suffix = "".join(f"[{field}]" if isinstance(field, int) else f".{field}" for field in fields).lstrip(".")
    return f"{path}: {suffix}"


def validate_run_scope(
    bundle: dict[str, Any], report: dict[str, Any], bundle_path: Path, report_path: Path,
    run_id: str, run_attempt: int,
) -> None:
    for index, node in enumerate(bundle.get("nodes", [])):
        data = node.get("data", {})
        if node.get("kind") == "run" and "ci" in data and not isinstance(data["ci"], dict):
            raise TrustError(f"{bundle_path}: nodes[{index}].data.ci must be a JSON object", exit_code=1)
    for data, path in scoped_data(bundle):
        for field, expected, validator in (("run_id", run_id, run_identifier), ("run_attempt", run_attempt, positive_run_attempt)):
            if field not in data:
                continue
            location = _location(bundle_path, [*path, field])
            try:
                actual = validator(data[field])
            except ValueError as exc:
                raise TrustError(f"{location}: {exc}", exit_code=1) from exc
            if actual != expected:
                raise TrustError(f"{location} mismatch with resolved {field}: {actual!r} != {expected!r}", exit_code=1)
            if field == "run_attempt":
                data[field] = actual
    declarations = [(value, _location(bundle_path, path)) for value, path in bundle_commit_declarations(bundle)]
    if "commit_sha" in report:
        declarations.insert(0, (report["commit_sha"], f"{report_path}: commit_sha"))
    anchor: tuple[str, str] | None = None
    for value, location in declarations:
        if not isinstance(value, str):
            raise TrustError(f"{location} must be a string", exit_code=1)
        try:
            normalized = commit_identifier(value)
        except ValueError:
            # 形式不正は既存のprovenance doctor所見として記録する。
            continue
        if anchor is not None and normalized != anchor[0]:
            raise TrustError(f"commit_sha mismatch: {location} disagrees with {anchor[1]}", exit_code=1)
        anchor = anchor or (normalized, location)
