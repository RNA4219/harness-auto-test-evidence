"""Filesystem input loading for P0b QEG export."""

from __future__ import annotations

from pathlib import Path

from .p0b_support import _read_json, _read_ndjson
from .p0b_types import ExportError, P0bInputBundle


def source_ref(fixture_dir: Path, path: Path) -> str:
    """Return a stable fixture-relative source reference."""
    try:
        return f"fixture:/{path.resolve().relative_to(fixture_dir).as_posix()}"
    except ValueError:
        return path.as_posix()


def load_input_bundle(fixture_dir: Path) -> P0bInputBundle:
    fixture_dir = fixture_dir.resolve()
    p0a_dir = fixture_dir / "p0a"
    diff_risk_path = fixture_dir / "diff-risk-test.json"
    risk_debt_lifecycle_path = fixture_dir / "risk-debt-lifecycle.json"
    required_p0a_files = [
        "HATE-run.json",
        "HATE-test-results.ndjson",
        "HATE-coverage.ndjson",
        "artifact-manifest.json",
        "precheck-decision.json",
        "record.json",
    ]
    missing_artifacts = [name for name in required_p0a_files if not (p0a_dir / name).exists()]
    if missing_artifacts:
        raise ExportError(
            f"Missing required P0a artifacts: {', '.join(missing_artifacts)}",
            exit_code=2,
        )
    return P0bInputBundle(
        fixture_dir=fixture_dir,
        p0a_dir=p0a_dir,
        diff_risk_path=diff_risk_path,
        risk_debt_lifecycle_path=risk_debt_lifecycle_path,
        run_record=_read_json(p0a_dir / "HATE-run.json"),
        test_records=_read_ndjson(p0a_dir / "HATE-test-results.ndjson"),
        coverage_records=_read_ndjson(p0a_dir / "HATE-coverage.ndjson"),
        contract_records=_read_ndjson(p0a_dir / "HATE-contract.ndjson")
        if (p0a_dir / "HATE-contract.ndjson").exists()
        else [],
        mutation_records=_read_ndjson(p0a_dir / "HATE-mutation.ndjson")
        if (p0a_dir / "HATE-mutation.ndjson").exists()
        else [],
        artifact_manifest=_read_json(p0a_dir / "artifact-manifest.json"),
        precheck_decision=_read_json(p0a_dir / "precheck-decision.json"),
        audit_record=_read_json(p0a_dir / "record.json"),
        sarif_record=_read_json(p0a_dir / "HATE-static.sarif") if (p0a_dir / "HATE-static.sarif").exists() else {},
        diff_risk_test=_read_json(diff_risk_path) if diff_risk_path.exists() else {},
        risk_debt_lifecycle=_read_json(risk_debt_lifecycle_path) if risk_debt_lifecycle_path.exists() else {},
    )
