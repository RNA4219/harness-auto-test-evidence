"""P1aの処理可能な構造と、doctorへ渡す公開スキーマ違反。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .p1a_io import TrustError
from .schema_resources import read_schema

_FINDING_SHAPE = {
    "type": "object",
    "properties": {name: {"type": "string"} for name in ("reason", "risk_id", "expected_test_ref", "artifact_id")},
}
_REPORT_SHAPE = {
    "type": "object",
    "properties": {
        **{name: {"type": "array", "items": _FINDING_SHAPE}
           for name in ("unsupportedClaims", "excludedArtifacts", "missing_execution")},
        "completeness": {"type": "object"},
        "export_status": {"type": "string"},
        "qeg_schema_compatibility": {
            "type": "object",
            "properties": {
                "schema": {"type": "string"},
                "valid": {"type": "boolean"},
                "errors": {"type": "array"},
            },
        },
        "source_refs": {"type": "array", "items": {"type": "string"}},
    },
}


@lru_cache(maxsize=1)
def _bundle_validator() -> Draft202012Validator:
    return Draft202012Validator(read_schema("qeg-bundle.schema.json"))


def bundle_schema_errors(bundle: dict[str, Any]) -> list[ValidationError]:
    return sorted(_bundle_validator().iter_errors(bundle), key=lambda error: (error.json_path, str(error.validator)))


def schema_error_message(error: ValidationError) -> str:
    detail = error.message if error.validator == "required" else f"expected {error.validator}={error.validator_value!r}"
    return f"{error.json_path}: {detail}"


def bundle_schema_issues(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """現在のbundleの検証結果を、doctor・信頼度・説明で共通利用する。"""
    return [{
        "issue": "bundle_schema_violation", "severity": "high",
        "message": schema_error_message(error), "validation_path": list(error.absolute_path),
        "source_refs": ["qeg-bundle.json"],
    } for error in bundle_schema_errors(bundle)]


def validate_trust_structure(
    bundle: dict[str, Any], report: dict[str, Any], bundle_path: Path, report_path: Path,
) -> None:
    errors = [(bundle_path, error) for error in bundle_schema_errors(bundle) if error.validator == "type"]
    errors.extend((report_path, error) for error in Draft202012Validator(_REPORT_SHAPE).iter_errors(report))
    if errors:
        diagnostics = [f"{path}: {schema_error_message(error)}" for path, error in errors[:8]]
        if len(errors) > 8:
            diagnostics.append(f"{len(errors) - 8} more structural errors")
        raise TrustError("invalid input structure: " + "; ".join(diagnostics), exit_code=1)
