"""P1aで使用するbundleとreportのrun情報を照合する。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .input_values import positive_run_attempt, run_identifier
from .p1a_io import TrustError, _read_json
from .p1a_precheck import validate_precheck_inputs
from .p1a_retry_inputs import validate_retry_inputs
from .p1a_run_scope import validate_run_scope
from .p1a_schema import validate_trust_structure


@dataclass(frozen=True)
class TrustInputs:
    bundle: dict[str, Any]
    report: dict[str, Any]
    run_id: str
    run_attempt: int


def read_trust_inputs(bundle_path: Path, report_path: Path) -> TrustInputs:
    bundle = _read_json(bundle_path, exact_run_numbers=True)
    report = _read_json(report_path, exact_run_numbers=True)
    metadata = bundle.get("metadata", {})
    if not isinstance(metadata, dict):
        raise TrustError(f"{bundle_path}: metadata must be a JSON object", exit_code=1)

    bundle_id, bundle_attempt = _identity(metadata, "runId", "runAttempt", f"{bundle_path}: metadata")
    report_id, report_attempt = _identity(report, "run_id", "run_attempt", str(report_path))
    for label, left, right in [("run_id", bundle_id, report_id), ("run_attempt", bundle_attempt, report_attempt)]:
        if left is not None and right is not None and left != right:
            raise TrustError(
                f"{label} mismatch: {bundle_path} declares {left!r}; {report_path} declares {right!r}",
                exit_code=1,
            )

    run_id = bundle_id if bundle_id is not None else report_id
    run_attempt = bundle_attempt if bundle_attempt is not None else report_attempt
    if run_id is None:
        raise TrustError(f"run_id is missing from both {bundle_path} and {report_path}", exit_code=1)
    if run_attempt is None:
        raise TrustError(f"run_attempt is missing from both {bundle_path} and {report_path}", exit_code=1)

    for data, fields, location in [
        (metadata, ("createdAt", "profile"), f"{bundle_path}: metadata"),
        (report, ("created_at", "commit_sha"), str(report_path)),
    ]:
        for field in fields:
            if field in data and not isinstance(data[field], str):
                raise TrustError(f"{location}.{field} must be a string", exit_code=1)
    if bundle_attempt is not None:
        metadata["runAttempt"] = bundle_attempt
    if report_attempt is not None:
        report["run_attempt"] = report_attempt
    validate_trust_structure(bundle, report, bundle_path, report_path)
    validate_precheck_inputs(bundle, bundle_path)
    validate_run_scope(bundle, report, bundle_path, report_path, run_id, run_attempt)
    validate_retry_inputs(bundle, bundle_path)
    return TrustInputs(bundle, report, run_id, run_attempt)


def _identity(data: dict[str, Any], id_field: str, attempt_field: str, location: str) -> tuple[str | None, int | None]:
    run_id = None
    run_attempt = None
    if id_field in data:
        try:
            run_id = run_identifier(data[id_field])
        except ValueError as exc:
            raise TrustError(f"{location}.{id_field}: {exc}", exit_code=1) from exc
    if attempt_field in data:
        try:
            run_attempt = positive_run_attempt(data[attempt_field])
        except ValueError as exc:
            raise TrustError(f"{location}.{attempt_field}: {exc}", exit_code=1) from exc
    return run_id, run_attempt
