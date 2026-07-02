from __future__ import annotations

import hashlib
import json
import mimetypes
import posixpath
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .p0a_constants import REDACTION_STATUS, SCHEMA_VERSION, SOURCE_TOOL
from .p0a_io import (
    _artifact_kind,
    _dq,
    _file_sha256,
    _read_optional_json,
    _slug,
    _stable_sha256,
    _stable_source_ref,
    _to_posix,
)
def _precheck_decision(
    context: dict[str, Any],
    created_at: str,
    source_version: str,
    dq_hits: list[dict[str, str]],
    soft_gaps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    soft_gaps = soft_gaps or []
    decision = "hard_dq" if dq_hits else "conditional" if soft_gaps else "eligible"
    exit_code = 2 if decision == "hard_dq" else 0
    reasons = [
        "Minimal P0a inputs satisfy HATE/v1 schema bootstrap contracts.",
        "QEG export is allowed as optional evidence and scheduled for P0b bundling.",
    ] if not dq_hits and not soft_gaps else [hit["message"] for hit in dq_hits] + [gap.get("message", "profile soft gap") for gap in soft_gaps]
    payload = {
        "decision": decision,
        "exit_code": exit_code,
        "dq_hits": dq_hits,
        "soft_gaps": soft_gaps,
        "reasons": reasons,
        "qeg_export_allowed": not dq_hits,
        "qeg_export_ref": None,
        "qeg_export_phase": "P0b",
    }
    return _envelope(context, "precheck_decision", f"precheck-{context['run_id']}-attempt-{context['run_attempt']}", created_at, source_version, payload)
def _audit_record(
    context: dict[str, Any],
    created_at: str,
    source_version: str,
    outputs: dict[str, Any],
    input_dir: Path,
) -> dict[str, Any]:
    payload = {
        "validated_artifacts": [name for name, value in outputs.items() if value is not None],
        "validation_result": "pass",
        "source_refs": [
            _stable_source_ref(input_dir / str(context.get("_context_source_name", "github-context.json"))),
            _stable_source_ref(input_dir / "junit.xml"),
            _stable_source_ref(input_dir / "lcov.info"),
        ],
        "notes": [
            "This record is generated from local P0a inputs and does not contain a release Gate verdict.",
        ],
    }
    return _envelope(context, "audit_record", f"audit-{context['run_id']}-attempt-{context['run_attempt']}", created_at, source_version, payload)
def _summary(
    context: dict[str, Any],
    test_records: list[dict[str, Any]],
    coverage_records: list[dict[str, Any]],
    artifact_manifest: dict[str, Any],
    decision_record: dict[str, Any],
    evidence_strength_distribution: dict[str, Any] | None = None,
) -> str:
    passed = sum(1 for record in test_records if record["payload"]["status"] == "passed")
    failed = sum(1 for record in test_records if record["payload"]["status"] in {"failed", "error"})
    covered = 0
    uncovered = 0
    coverage_files: list[str] = []
    for record in coverage_records:
        coverage_files.append(record["payload"]["file"])
        for hits in record["payload"]["line_hits"].values():
            if hits > 0:
                covered += 1
            else:
                uncovered += 1
    decision = decision_record["payload"]["decision"]
    artifact_names = ", ".join(artifact["artifact_id"] for artifact in artifact_manifest["artifacts"]) or "none"
    coverage_line = "No coverage records generated"
    if coverage_files:
        coverage_line = f"Coverage sample: `{coverage_files[0]}` has {covered} covered lines and {uncovered} uncovered line"
        if uncovered != 1:
            coverage_line += "s"
    strength = evidence_strength_distribution or {}
    strength_line = (
        "Evidence strength: "
        f"{strength.get('total', 0)} tests, "
        f"flake known {strength.get('flake_known', 0)}/unknown {strength.get('flake_unknown', 0)}, "
        f"mutation known {strength.get('mutation_known', 0)}/unknown {strength.get('mutation_unknown', 0)}"
    )
    return "\n".join(
        [
            "# P0a Minimal Evidence Summary",
            "",
            f"- Run: `{context['run_id']}` attempt `{context['run_attempt']}`",
            f"- Repository: `{context['repository']}`",
            f"- Commit: `{context.get('commit_sha', '')[:40]}`",
            f"- Test result: {passed} passed, {failed} failed",
            f"- {coverage_line}",
            f"- {strength_line}",
            f"- Precheck: {decision} for optional QEG evidence export in P0b",
            f"- Generated artifacts: {artifact_names}",
            "",
            "This summary is public-safe and generated from local P0a inputs.",
            "",
        ]
    )
def _envelope(
    context: dict[str, Any],
    record_type: str,
    record_id: str,
    created_at: str,
    source_version: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    record = {
        "schema_version": SCHEMA_VERSION,
        "record_type": record_type,
        "record_id": record_id,
        "run_id": str(context["run_id"]),
        "run_attempt": int(context["run_attempt"]),
        "commit_sha": str(context.get("commit_sha", "")),
        "created_at": created_at,
        "source_tool": SOURCE_TOOL,
        "source_version": source_version,
        "sha256": "",
        "redaction_status": REDACTION_STATUS,
        "payload": payload,
    }
    record["sha256"] = f"sha256:{_stable_sha256({**record, 'sha256': ''})}"
    return record
def _dq_hits_from_control(control: dict[str, Any]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    if control.get("unresolved_flaky_over_threshold") is True:
        hits.append(_dq("HATE-DQ-005", "unresolved flakiness is over threshold", "dq-control.json"))
    if control.get("high_risk_without_execution") is True:
        hits.append(_dq("HATE-DQ-007", "high-risk changed path has no execution evidence", "dq-control.json"))
    if control.get("unresolved_high_critical_sarif") is True:
        hits.append(_dq("HATE-DQ-010", "unresolved high or critical SARIF finding on changed path", "dq-control.json"))
    return hits

