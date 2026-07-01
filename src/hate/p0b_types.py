"""Shared P0b export types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "HATE/v1"


@dataclass
class ExportError(Exception):
    message: str
    exit_code: int = 1
    report: dict[str, Any] | None = None
    out_dir: Path | None = None

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class P0bInputBundle:
    fixture_dir: Path
    p0a_dir: Path
    diff_risk_path: Path
    risk_debt_lifecycle_path: Path
    run_record: dict[str, Any]
    test_records: list[dict[str, Any]]
    coverage_records: list[dict[str, Any]]
    contract_records: list[dict[str, Any]]
    mutation_records: list[dict[str, Any]]
    artifact_manifest: dict[str, Any]
    precheck_decision: dict[str, Any]
    audit_record: dict[str, Any]
    sarif_record: dict[str, Any]
    diff_risk_test: dict[str, Any]
    risk_debt_lifecycle: dict[str, Any]
