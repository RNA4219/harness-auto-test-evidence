from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import __version__
from .p0a_support import (
    PrecheckError,
    _artifact_manifest,
    _audit_record,
    _dq,
    _dq_hits_from_control,
    _parse_cobertura,
    _parse_jacoco,
    _parse_jest_json,
    _parse_junit,
    _parse_lcov,
    _parse_pytest_json,
    _parse_vitest_json,
    _parse_coveragepy_json,
    _read_sarif,
    _precheck_decision,
    _quarantine_report,
    _read_context,
    _read_optional_json,
    _run_record,
    _sarif_dq_hits,
    _schema_validation_hits,
    _summary,
    _write_json,
    _write_ndjson,
)
from .profile import evaluate_profile, resolve_profile

def generate_p0a(
    input_dir: Path,
    out_dir: Path,
    source_version: str | None = None,
    fixture_path_prefix: str | None = None,
    profile: str = "default",
) -> dict[str, Any]:
    input_dir = input_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    version = source_version or __version__
    resolve_profile(profile)

    context_path = _first_existing(input_dir, ["github-context.json", "ci-context.json", "generic-ci-context.json"])
    if context_path is None:
        raise PrecheckError(
            "missing required input: github-context.json, ci-context.json, or generic-ci-context.json",
            exit_code=1,
        )
    junit_path = input_dir / "junit.xml"
    pytest_path = input_dir / "pytest-report.json"
    vitest_path = input_dir / "vitest-report.json"
    jest_path = input_dir / "jest-report.json"
    lcov_path = input_dir / "lcov.info"
    cobertura_path = input_dir / "cobertura.xml"
    jacoco_path = input_dir / "jacoco.xml"
    coveragepy_path = input_dir / "coverage.json"
    sarif_path = _first_existing(input_dir, ["results.sarif", "sarif.json", "HATE-static.sarif"])
    artifacts_dir = input_dir / "artifacts"
    artifact_refs_path = input_dir / "artifact-refs.json"
    record_control_path = input_dir / "record-control.json"
    dq_control_path = input_dir / "dq-control.json"

    context = _read_context(context_path)
    created_at = str(context.get("finished_at") or context.get("started_at") or "")
    context_source = str(context.get("_context_source_name", context_path.name))
    if not created_at:
        raise PrecheckError(f"{context_source} requires finished_at or started_at", exit_code=1)

    dq_hits: list[dict[str, str]] = []
    commit_sha = str(context.get("commit_sha", ""))
    if not commit_sha:
        dq_hits.append(_dq("HATE-DQ-001", "commit_sha is missing", context_source))
    elif not re.match(r"^[A-Fa-f0-9]{7,64}$", commit_sha):
        dq_hits.append(_dq("HATE-DQ-001", "commit_sha is not a hex sha", context_source))

    test_records: list[dict[str, Any]] = []
    coverage_records: list[dict[str, Any]] = []
    test_adapter_errors: list[dict[str, str]] = []
    coverage_adapter_errors: list[dict[str, str]] = []

    try:
        test_records = _parse_junit(junit_path, context, created_at, version)
    except Exception as exc:  # noqa: BLE001 - adapter boundary converts parser failures to DQ.
        test_adapter_errors.append(_dq("HATE-DQ-002", f"junit parse failure: {exc}", "junit.xml"))

    # Test result adapters: pytest, vitest, jest
    try:
        test_records.extend(_parse_pytest_json(pytest_path, context, created_at, version))
    except Exception as exc:  # noqa: BLE001
        test_adapter_errors.append(_dq("HATE-DQ-002", f"pytest parse failure: {exc}", "pytest-report.json"))
    try:
        test_records.extend(_parse_vitest_json(vitest_path, context, created_at, version))
    except Exception as exc:  # noqa: BLE001
        test_adapter_errors.append(_dq("HATE-DQ-002", f"vitest parse failure: {exc}", "vitest-report.json"))
    try:
        test_records.extend(_parse_jest_json(jest_path, context, created_at, version))
    except Exception as exc:  # noqa: BLE001
        test_adapter_errors.append(_dq("HATE-DQ-002", f"jest parse failure: {exc}", "jest-report.json"))

    # Coverage adapters: lcov, cobertura, jacoco, coverage.py
    try:
        coverage_records = _parse_lcov(lcov_path, context, created_at, version, test_records)
    except Exception as exc:  # noqa: BLE001
        coverage_adapter_errors.append(_dq("HATE-DQ-002", f"lcov parse failure: {exc}", "lcov.info"))
    try:
        coverage_records.extend(_parse_cobertura(cobertura_path, context, created_at, version, test_records))
    except Exception as exc:  # noqa: BLE001
        coverage_adapter_errors.append(_dq("HATE-DQ-002", f"cobertura parse failure: {exc}", "cobertura.xml"))
    try:
        coverage_records.extend(_parse_jacoco(jacoco_path, context, created_at, version, test_records))
    except Exception as exc:  # noqa: BLE001
        coverage_adapter_errors.append(_dq("HATE-DQ-002", f"jacoco parse failure: {exc}", "jacoco.xml"))
    try:
        coverage_records.extend(_parse_coveragepy_json(coveragepy_path, context, created_at, version))
    except Exception as exc:  # noqa: BLE001
        coverage_adapter_errors.append(_dq("HATE-DQ-002", f"coverage.py parse failure: {exc}", "coverage.json"))

    sarif_record: dict[str, Any] | None = None
    sarif_error: dict[str, str] | None = None
    if sarif_path is not None:
        try:
            sarif_record = _read_sarif(sarif_path)
            dq_hits.extend(_sarif_dq_hits(sarif_record))
        except Exception as exc:  # noqa: BLE001
            sarif_error = _dq("HATE-DQ-002", f"sarif parse failure: {exc}", sarif_path.name)

    # Only add test adapter errors if no test records were produced
    # (junit.xml absence is OK if pytest/vitest/jest produces results)
    if not test_records and test_adapter_errors:
        dq_hits.extend(test_adapter_errors)
    # Coverage adapter errors always count (malformed coverage is serious)
    dq_hits.extend(coverage_adapter_errors)
    if sarif_error:
        dq_hits.append(sarif_error)
    if coverage_records and not test_records:
        dq_hits.append(_dq("HATE-DQ-008", "coverage exists but no test execution result exists", "lcov.info"))

    run_record = _run_record(context, created_at, version)
    artifact_manifest = _artifact_manifest(context, created_at, artifacts_dir, artifact_refs_path, fixture_path_prefix)
    missing_artifacts = [
        artifact for artifact in artifact_manifest["artifacts"]
        if artifact.get("security_checks", {}).get("path_exists") == "fail"
    ]
    if missing_artifacts:
        dq_hits.append(_dq("HATE-DQ-003", "artifact manifest references missing files", "artifact-refs.json"))

    record_control = _read_optional_json(record_control_path)
    if record_control.get("force_record_missing") is True:
        dq_hits.append(_dq("HATE-DQ-015", "record generation was forced to fail by fixture control", "record-control.json"))

    dq_control = _read_optional_json(dq_control_path)
    dq_hits.extend(_dq_hits_from_control(dq_control))

    profile_report, profile_dq_hits, profile_soft_gaps = evaluate_profile(
        profile_name=profile,
        run_id=str(context["run_id"]),
        run_attempt=int(context["run_attempt"]),
        commit_sha=str(context.get("commit_sha", "")),
        created_at=created_at,
        test_records=test_records,
        coverage_records=coverage_records,
        artifact_manifest=artifact_manifest,
    )
    dq_hits.extend(profile_dq_hits)

    decision_record = _precheck_decision(context, created_at, version, dq_hits, profile_soft_gaps)
    outputs = {
        "HATE-run.json": run_record,
        "HATE-test-results.ndjson": test_records,
        "HATE-coverage.ndjson": coverage_records,
        "artifact-manifest.json": artifact_manifest,
        "quarantine-report.json": _quarantine_report(context, created_at, version, artifact_manifest),
        "profile-report.json": profile_report,
        "precheck-decision.json": decision_record,
    }
    if sarif_record is not None:
        outputs["HATE-static.sarif"] = sarif_record

    _write_json(out_dir / "HATE-run.json", run_record)
    _write_ndjson(out_dir / "HATE-test-results.ndjson", test_records)
    _write_ndjson(out_dir / "HATE-coverage.ndjson", coverage_records)
    if sarif_record is not None:
        _write_json(out_dir / "HATE-static.sarif", sarif_record)
    _write_json(out_dir / "artifact-manifest.json", artifact_manifest)
    _write_json(out_dir / "quarantine-report.json", outputs["quarantine-report.json"])
    _write_json(out_dir / "profile-report.json", profile_report)
    _write_json(out_dir / "precheck-decision.json", decision_record)

    record = _audit_record(context, created_at, version, outputs, input_dir)
    schema_hits = _schema_validation_hits([*outputs.values(), record])
    if schema_hits:
        dq_hits.extend(schema_hits)
        decision_record = _precheck_decision(context, created_at, version, dq_hits, profile_soft_gaps)
        outputs["precheck-decision.json"] = decision_record
        _write_json(out_dir / "precheck-decision.json", decision_record)
        record = _audit_record(context, created_at, version, outputs, input_dir)
    _write_json(out_dir / "record.json", record)
    summary = _summary(context, test_records, coverage_records, artifact_manifest, decision_record)
    (out_dir / "summary.md").write_text(summary, encoding="utf-8")

    result = {
        "decision": decision_record["payload"]["decision"],
        "exit_code": decision_record["payload"]["exit_code"],
        "generated": sorted([*outputs.keys(), "record.json", "summary.md"]),
        "out_dir": str(out_dir),
    }
    if decision_record["payload"]["exit_code"] != 0:
        raise PrecheckError("P0a precheck did not pass", decision_record["payload"]["exit_code"], decision_record, out_dir)
    return result


def _first_existing(input_dir: Path, names: list[str]) -> Path | None:
    for name in names:
        path = input_dir / name
        if path.exists():
            return path
    return None

