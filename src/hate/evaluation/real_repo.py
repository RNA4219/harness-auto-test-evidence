"""Recurring real repository evaluation reports.

Real repository trials are product evidence only when they preserve baseline
comparison, timeout visibility, and subset limitations.
"""

from __future__ import annotations

import json
import os
import hashlib
import platform
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hate.evaluation.output_safety import safe_command_output
from hate.evaluation.regression_engine import classify_real_repo_regressions
from hate.evaluation.runner_dialects import parse_runner_summary
from hate.evaluation.real_repo_runtime import (
    merge_counts as _merge_counts,
    no_split_execution as _no_split_execution,
    no_timeout_cleanup as _no_timeout_cleanup,
    normalize_command as _normalize_command,
    run_bootstrap_if_configured as _run_bootstrap_if_configured,
    run_command as _run_command,
    split_plan_for_entry as _split_plan_for_entry,
)


DEFAULT_TIMEOUT_MS = 900_000
REPO_CLASS_TIMEOUT_MS = {
    "small": 900_000,
    "medium": 1_800_000,
    "large": 2_700_000,
    "xlarge": 3_600_000,
    "monorepo": 3_600_000,
}
VALID_OWNERSHIP_SCOPES = {"owned", "external", "third_party_sample"}
VALID_REPO_CLASSES = set(REPO_CLASS_TIMEOUT_MS)
VALID_SUITE_KINDS = {
    "unit",
    "integration",
    "e2e",
    "build",
    "typecheck",
    "lint",
    "security",
    "smoke",
    "package-split",
}
DEFAULT_POLICY_HASH = "sha256:default"


@dataclass(frozen=True)
class RealRepoEvaluationFinding:
    code: str
    severity: str
    readiness_effect: str
    message: str
    sourceRef: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "readiness_effect": self.readiness_effect,
            "message": self.message,
            "sourceRef": self.sourceRef,
        }

def evaluate_real_repo_fixture(payload: dict[str, Any]) -> dict[str, str]:
    """Evaluate a product gap real-repo fixture."""
    report = build_real_repo_evaluation_report(
        payload.get("input", {}),
        report_id=payload.get("fixture_id", "real-repo-evaluation"),
        source_refs=[_fixture_source_ref(payload)],
    )
    finding_code = report["findings"][0]["code"] if report["findings"] else ""
    return {
        "status": report["overall_status"],
        "finding_code": finding_code,
        "readiness_effect": "hold" if report["overall_status"] == "hold" else "none",
    }


def build_real_repo_evaluation_report(
    data: dict[str, Any],
    report_id: str = "real-repo-evaluation",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Build a recurring real repository baseline comparison report."""
    source_refs = source_refs or [f"fixtures/evaluation/real-repo/{report_id}/fixture.json"]
    repo_id = str(data.get("repo_id") or "")
    suite_id = str(data.get("suite_id") or "default")
    repo_class = str(data.get("repo_class") or "small")
    ownership_scope = str(data.get("ownership_scope") or "owned")
    run_id = str(data.get("run_id") or "")
    source_version = str(data.get("source_version") or "")
    roster_hash = str(data.get("roster_hash") or "")
    policy_hash = str(data.get("policy_hash") or "")
    environment_fingerprint = dict(data.get("environment_fingerprint") or {})
    started_at = str(data.get("started_at") or "")
    finished_at = str(data.get("finished_at") or "")
    baseline_decision = str(data.get("baseline_decision") or "")
    current_decision = str(data.get("current_decision") or "")
    timeout_ms = int(data.get("timeout_ms") or DEFAULT_TIMEOUT_MS)
    runtime_ms = int(data.get("runtime_ms") or 0)
    runtime_budget_ms = int(data.get("runtime_budget_ms") or timeout_ms)
    baseline_record_count = _optional_int(data.get("baseline_record_count"))
    current_record_count = _optional_int(data.get("current_record_count"))
    parser_status = str(data.get("parser_status") or "passed")
    unsafe_artifact_findings = int(data.get("unsafe_artifact_findings") or 0)
    command_exit_code = data.get("command_exit_code")
    failure_kind = str(data.get("failure_kind") or "")
    command_summary = dict(data.get("command_summary") or {})
    runner_dialect = str(data.get("runner_dialect") or "unknown")
    runner_parser = dict(data.get("runner_parser") or {"parser_status": "unparsed", "ignored_noise": []})
    bootstrap = dict(data.get("bootstrap") or {})
    split_execution = dict(data.get("split_execution") or {})
    command_excerpt = str(data.get("command_excerpt") or "")
    output_safety = dict(data.get("output_safety") or {})
    timeout_cleanup = dict(data.get("timeout_cleanup") or {
        "timeout_reason": "none",
        "cleanup_attempted": False,
        "cleanup_method": "none",
        "cleanup_completed": None,
        "fallback_kill_used": False,
    })
    subset = bool(data.get("subset") or data.get("subset_command"))
    subset_label = str(data.get("subset_label") or "")

    findings: list[RealRepoEvaluationFinding] = []
    regressions = classify_real_repo_regressions(data)
    if not repo_id:
        findings.append(_finding(
            "real_repo_repo_id_missing",
            "hold",
            "Repository roster entry is missing repo_id.",
            source_refs[0],
        ))
    for regression in regressions:
        findings.append(_finding(regression["code"], regression["readiness_effect"], regression["message"], source_refs[0]))
    if parser_status == "failed":
        findings.append(_finding(
            "real_repo_parser_failure",
            "hold",
            "Real repository evaluation parser failed.",
            source_refs[0],
        ))
    if bootstrap.get("status") == "hold":
        findings.append(_finding(
            "real_repo_bootstrap_failed",
            "hold",
            "Dependency bootstrap command failed before the real repository suite could run.",
            source_refs[0],
        ))
    if split_execution.get("status") == "hold":
        findings.append(_finding(
            "real_repo_split_execution_failed",
            "hold",
            "Split or resumed execution failed and cannot prove the full suite.",
            source_refs[0],
        ))
    if split_execution.get("resume_required") and not split_execution.get("resume_token"):
        findings.append(_finding(
            "real_repo_resume_token_missing",
            "hold",
            "Split execution with skipped or partial shards requires a resume token.",
            source_refs[0],
        ))
    if runtime_ms and runtime_ms > runtime_budget_ms:
        findings.append(_finding(
            "real_repo_runtime_budget_exceeded",
            "hold",
            "Real repository evaluation exceeded runtime budget.",
            source_refs[0],
        ))
    if data.get("timeout_recorded") or data.get("timed_out"):
        findings.append(_finding(
            "real_repo_timeout_recorded",
            "hold",
            "Timeout is retained as evidence and cannot be silent.",
            source_refs[0],
        ))
    if runner_parser.get("parser_status") == "partial":
        findings.append(_finding(
            "real_repo_runner_partial_progress_observed",
            "hold",
            "Runner output contained partial progress evidence without a complete summary.",
            source_refs[0],
        ))
    if command_exit_code is not None and int(command_exit_code) != 0:
        findings.append(_finding(
            "real_repo_command_failed",
            "hold",
            "Real repository evaluation command returned a non-zero exit code.",
            source_refs[0],
        ))
    if failure_kind == "dependency_network_blocked":
        findings.append(_finding(
            "real_repo_dependency_network_blocked",
            "hold",
            "Real repository command could not resolve build dependencies because network access was blocked.",
            source_refs[0],
        ))
    elif failure_kind == "missing_test_dependency":
        findings.append(_finding(
            "real_repo_missing_test_dependency",
            "hold",
            "Real repository command could not find a declared test runner or runtime dependency.",
            source_refs[0],
        ))
    elif failure_kind == "runner_config_mismatch":
        findings.append(_finding(
            "real_repo_runner_config_mismatch",
            "hold",
            "Real repository command failed because the selected runner did not satisfy repository configuration.",
            source_refs[0],
        ))
    elif failure_kind == "test_failure":
        findings.append(_finding(
            "real_repo_test_failure",
            "hold",
            "Real repository tests executed and reported failures.",
            source_refs[0],
        ))
    elif failure_kind == "command_launch_failed":
        findings.append(_finding(
            "real_repo_command_launch_failed",
            "hold",
            "Real repository command could not be launched.",
            source_refs[0],
        ))
    if unsafe_artifact_findings > 0:
        findings.append(_finding(
            "real_repo_unsafe_artifact_finding",
            "hold",
            "New unsafe artifact finding appeared in real repository trial.",
            source_refs[0],
        ))
    if subset and not subset_label:
        findings.append(_finding(
            "real_repo_subset_unlabeled",
            "hold",
            "Subset evaluation must be labeled and cannot prove full-suite readiness.",
            source_refs[0],
        ))

    status = "hold" if findings else "pass"
    external_hold_regressions = [
        regression for regression in regressions if regression["regression_class"] == "external_hold_detected"
    ]
    return {
        "schema_version": "HATE/v1",
        "record_type": "real-repo-evaluation-report",
        "report_id": report_id,
        "overall_status": status,
        "repo_id": repo_id,
        "suite_id": suite_id,
        "repo_class": repo_class,
        "ownership_scope": ownership_scope,
        "run_id": run_id,
        "source_version": source_version,
        "roster_hash": roster_hash,
        "policy_hash": policy_hash,
        "environment_fingerprint": environment_fingerprint,
        "started_at": started_at,
        "finished_at": finished_at,
        "baseline": {
            "decision": baseline_decision,
            "record_count": baseline_record_count,
            "runtime_ms": _optional_int(data.get("baseline_runtime_ms")),
            "failure_kind": str(data.get("baseline_failure_kind") or ""),
        },
        "current": {
            "decision": current_decision,
            "record_count": current_record_count,
            "parser_status": parser_status,
            "runtime_ms": runtime_ms,
            "unsafe_artifact_findings": unsafe_artifact_findings,
            "command_exit_code": command_exit_code,
            "failure_kind": failure_kind,
            "command_summary": command_summary,
            "runner_dialect": runner_dialect,
            "runner_parser": runner_parser,
            "bootstrap": bootstrap,
            "split_execution": split_execution,
            "command_excerpt": command_excerpt,
            "output_safety": output_safety,
            "timeout_cleanup": timeout_cleanup,
        },
        "regressions": regressions,
        "external_hold": {
            "detected": bool(external_hold_regressions),
            "ownership_scope": ownership_scope,
            "implementation_failure": False if external_hold_regressions else None,
            "records": external_hold_regressions,
        },
        "timeout_ms": timeout_ms,
        "runtime_budget_ms": runtime_budget_ms,
        "timeout_recorded": bool(data.get("timeout_recorded") or data.get("timed_out")),
        "subset": {
            "is_subset": subset,
            "label": subset_label,
            "limitation_visible": (not subset) or bool(subset_label),
            "proves_full_suite": False if subset else True,
        },
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "finding_count": len(findings),
            "regression_detected": any(
                finding.code.startswith("real_repo_regression") for finding in findings
            ) or bool(regressions),
            "regression_classes": [regression["regression_class"] for regression in regressions],
            "timeout_recorded": bool(data.get("timeout_recorded") or data.get("timed_out")),
            "subset_limited": subset,
            "executed_record_count": current_record_count,
            "bootstrap_status": bootstrap.get("status", "not_configured"),
            "split_status": split_execution.get("status", "not_configured"),
        },
        "sourceRefs": source_refs,
    }


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _finding(
    code: str,
    readiness_effect: str,
    message: str,
    source_ref: str,
) -> RealRepoEvaluationFinding:
    return RealRepoEvaluationFinding(
        code=code,
        severity="high",
        readiness_effect=readiness_effect,
        message=message,
        sourceRef=source_ref,
    )


def _fixture_source_ref(payload: dict[str, Any]) -> str:
    fixture_id = str(payload.get("fixture_id") or "fixture")
    return f"fixtures/evaluation/real-repo/{fixture_id}/fixture.json"


def run_real_repo_roster(
    roster_path: Path,
    out_dir: Path,
    source_version: str | None = None,
) -> dict[str, Any]:
    """Run real repository evaluation commands from a JSON roster."""
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    entries = _normalize_roster_entries(roster)
    roster_hash = _stable_hash(roster)
    policy_hash = _policy_hash(roster)
    environment_fingerprint = _environment_fingerprint()

    out_dir.mkdir(parents=True, exist_ok=True)

    generated: list[str] = []
    reports: list[dict[str, Any]] = []
    history_entries: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        result = _run_roster_entry(
            entry,
            roster_path,
            roster_hash=roster_hash,
            policy_hash=policy_hash,
            environment_fingerprint=environment_fingerprint,
            source_version=source_version or roster.get("source_version") or "unknown",
        )
        report_stem = _report_stem(result)
        report = build_real_repo_evaluation_report(
            result,
            report_id=report_stem,
            source_refs=[f"file:{roster_path.name}#{result['repo_id']}:{result.get('suite_id', 'default')}"],
        )
        report_path = out_dir / f"{report_stem}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        generated.append(report_path.name)
        reports.append(report)
        history_entries.append(_run_history_entry(result, report, roster_path, report_stem))

    held_reports = [report for report in reports if report["overall_status"] == "hold"]
    hold_count = len(held_reports)
    manifest = {
        "schema_version": "HATE/v1",
        "record_type": "real-repo-evaluation-run-report",
        "report_id": "real-repo-evaluation-run",
        "source_version": source_version or roster.get("source_version") or "unknown",
        "run_id": _stable_id("run", roster_hash, source_version or roster.get("source_version") or "unknown"),
        "roster_hash": roster_hash,
        "policy_hash": policy_hash,
        "environment_fingerprint": environment_fingerprint,
        "overall_status": "hold" if hold_count else "pass",
        "roster_path": str(roster_path),
        "repo_count": len(reports),
        "hold_count": hold_count,
        "generated_reports": generated,
        "history_path": "real-repo-run-history.jsonl",
        "summary": {
            "passed": len(reports) - hold_count,
            "held": hold_count,
            "timeout_count": sum(1 for report in reports if report["timeout_recorded"]),
            "executed_record_count": sum(int(report["current"]["record_count"] or 0) for report in reports),
            "held_repos": [report["repo_id"] for report in held_reports],
        },
        "sourceRefs": [f"file:{roster_path.name}"],
    }
    manifest_path = out_dir / "real-repo-evaluation-run-report.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    history_path = out_dir / "real-repo-run-history.jsonl"
    history_path.write_text(
        "".join(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n" for entry in history_entries),
        encoding="utf-8",
    )
    return manifest


def _report_stem(result: dict[str, Any]) -> str:
    repo_id = str(result.get("repo_id") or "repo")
    suite_id = str(result.get("suite_id") or "default")
    if suite_id == "default":
        return f"real-repo-{repo_id}"
    return f"real-repo-{repo_id}-{suite_id}"


def _run_history_entry(result: dict[str, Any], report: dict[str, Any], roster_path: Path, report_stem: str) -> dict[str, Any]:
    return {
        "schema_version": "HATE/v1",
        "record_type": "real-repo-run-history-entry",
        "run_id": str(result.get("run_id") or ""),
        "repo_id": str(result.get("repo_id") or ""),
        "suite_id": str(result.get("suite_id") or "default"),
        "ownership_scope": str(result.get("ownership_scope") or "owned"),
        "source_version": str(result.get("source_version") or ""),
        "roster_hash": str(result.get("roster_hash") or ""),
        "policy_hash": str(result.get("policy_hash") or ""),
        "environment_fingerprint": dict(result.get("environment_fingerprint") or {}),
        "started_at": str(result.get("started_at") or ""),
        "finished_at": str(result.get("finished_at") or ""),
        "duration_ms": int(result.get("runtime_ms") or 0),
        "command_exit_code": int(result.get("command_exit_code") or 0),
        "status": report["overall_status"],
        "record_count": report["current"]["record_count"],
        "command_summary": report["current"]["command_summary"],
        "failure_kind": report["current"]["failure_kind"],
        "timeout_recorded": bool(report["timeout_recorded"]),
        "subset": report["subset"],
        "command_excerpt_ref": f"{report_stem}.json#/current/command_excerpt",
        "sourceRefs": [f"file:{roster_path.name}#{result.get('repo_id')}:{result.get('suite_id', 'default')}"],
    }


def _normalize_roster_entries(roster: dict[str, Any]) -> list[dict[str, Any]]:
    entries = roster.get("repositories")
    if not isinstance(entries, list):
        raise ValueError("real repo roster must contain repositories[]")
    if roster.get("record_type") != "real-repo-roster-v2":
        return [entry for entry in entries if isinstance(entry, dict)]

    normalized: list[dict[str, Any]] = []
    for repo in entries:
        if not isinstance(repo, dict):
            continue
        repo_id = str(repo.get("repo_id") or "")
        ownership_scope = str(repo.get("ownership_scope") or "")
        repo_class = str(repo.get("repo_class") or "")
        suites = repo.get("suites")
        if not repo_id:
            raise ValueError("real-repo-roster-v2 repository requires repo_id")
        if ownership_scope not in VALID_OWNERSHIP_SCOPES:
            raise ValueError(f"invalid ownership_scope for {repo_id}: {ownership_scope}")
        if repo_class not in VALID_REPO_CLASSES:
            raise ValueError(f"invalid repo_class for {repo_id}: {repo_class}")
        if not isinstance(suites, list) or not suites:
            raise ValueError(f"real-repo-roster-v2 repository requires suites[]: {repo_id}")
        for suite in suites:
            if not isinstance(suite, dict):
                continue
            suite_id = str(suite.get("suite_id") or "")
            suite_kind = str(suite.get("suite_kind") or "")
            command = suite.get("command")
            if not suite_id:
                raise ValueError(f"real-repo-roster-v2 suite requires suite_id: {repo_id}")
            if suite_kind not in VALID_SUITE_KINDS:
                raise ValueError(f"invalid suite_kind for {repo_id}/{suite_id}: {suite_kind}")
            if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
                raise ValueError(f"real-repo-roster-v2 suite requires string command[]: {repo_id}/{suite_id}")
            normalized.append({
                **repo,
                **suite,
                "repo_id": repo_id,
                "suite_id": suite_id,
                "suite_kind": suite_kind,
                "ownership_scope": ownership_scope,
                "repo_class": repo_class,
                "path": repo.get("path"),
                "env": {**(repo.get("env") or {}), **(suite.get("env") or {})},
            })
    return normalized


def _run_roster_entry(
    entry: dict[str, Any],
    roster_path: Path,
    roster_hash: str = "",
    policy_hash: str = DEFAULT_POLICY_HASH,
    environment_fingerprint: dict[str, str] | None = None,
    source_version: str = "unknown",
) -> dict[str, Any]:
    repo_id = _safe_repo_id(str(entry.get("repo_id") or entry.get("name") or "repo"))
    suite_id = _safe_repo_id(str(entry.get("suite_id") or "default"))
    repo_path = Path(str(entry.get("path") or "."))
    if not repo_path.is_absolute():
        repo_path = (roster_path.parent / repo_path).resolve()
    timeout_ms = _timeout_ms_for_entry(entry)
    command = entry.get("command")
    identity = _run_identity(repo_id, suite_id, command if isinstance(command, list) else [], roster_hash, source_version)
    started_at = _utc_now()
    if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
        return {
            **entry,
            "repo_id": repo_id,
            "suite_id": suite_id,
            "run_id": identity,
            "source_version": source_version,
            "roster_hash": roster_hash,
            "policy_hash": policy_hash,
            "environment_fingerprint": environment_fingerprint or _environment_fingerprint(),
            "started_at": started_at,
            "finished_at": _utc_now(),
            "baseline_decision": _baseline_decision_for_entry(entry),
            "current_decision": "hold",
            "parser_status": "failed",
            "runtime_ms": 0,
            "runtime_budget_ms": timeout_ms,
            "timeout_ms": timeout_ms,
            "command_exit_code": 127,
            "timeout_cleanup": _no_timeout_cleanup(),
            "subset": bool(entry.get("subset") or entry.get("subset_command")),
        }
    command = _normalize_command(command)
    command_env = _isolated_command_env(entry.get("env"))
    bootstrap = _run_bootstrap_if_configured(entry, repo_path, command_env)
    if bootstrap["status"] == "hold":
        return {
            **entry,
            "repo_id": repo_id,
            "suite_id": suite_id,
            "run_id": identity,
            "source_version": source_version,
            "roster_hash": roster_hash,
            "policy_hash": policy_hash,
            "environment_fingerprint": environment_fingerprint or _environment_fingerprint(),
            "started_at": started_at,
            "finished_at": _utc_now(),
            "baseline_decision": _baseline_decision_for_entry(entry),
            "current_decision": "hold",
            "baseline_record_count": entry.get("baseline_record_count"),
            "current_record_count": 0,
            "parser_status": "passed",
            "runtime_ms": int(bootstrap.get("runtime_ms") or 0),
            "runtime_budget_ms": int(entry.get("runtime_budget_ms") or timeout_ms),
            "timeout_ms": timeout_ms,
            "timed_out": bool(bootstrap.get("timeout_recorded")),
            "timeout_recorded": bool(bootstrap.get("timeout_recorded")),
            "timeout_cleanup": bootstrap.get("timeout_cleanup", _no_timeout_cleanup()),
            "command_exit_code": int(bootstrap.get("exit_code") or 1),
            "failure_kind": "bootstrap_failed",
            "command_summary": {},
            "runner_dialect": "unknown",
            "runner_parser": {"parser_status": "unparsed", "ignored_noise": []},
            "bootstrap": bootstrap,
            "split_execution": _no_split_execution(),
            "command_excerpt": str(bootstrap.get("command_excerpt") or ""),
            "output_safety": dict(bootstrap.get("output_safety") or {}),
            "subset": bool(entry.get("subset") or entry.get("subset_command")),
            "subset_label": str(entry.get("subset_label") or ""),
        }

    split_plan = _split_plan_for_entry(entry)
    if split_plan["configured"]:
        return _run_split_roster_entry(
            entry,
            repo_id=repo_id,
            suite_id=suite_id,
            repo_path=repo_path,
            timeout_ms=timeout_ms,
            command=command,
            identity=identity,
            started_at=started_at,
            roster_hash=roster_hash,
            policy_hash=policy_hash,
            environment_fingerprint=environment_fingerprint,
            source_version=source_version,
            bootstrap=bootstrap,
            split_plan=split_plan,
        )

    started = time.perf_counter()
    command_result = _run_command(command, repo_path, command_env, timeout_ms)
    timed_out = command_result.timed_out
    exit_code = command_result.exit_code
    parser_status = command_result.parser_status
    stdout = command_result.stdout
    stderr = command_result.stderr

    runtime_ms = int((time.perf_counter() - started) * 1000)
    current_decision = "hold" if timed_out or exit_code != 0 or parser_status == "failed" else "pass"
    failure_kind = ""
    if timed_out or exit_code != 0 or parser_status == "failed":
        failure_kind = _classify_command_failure(stdout, stderr, timed_out, parser_status)
    runner_parse = parse_runner_summary(stdout, stderr)
    command_summary = runner_parse["summary"]
    safe_output = safe_command_output(stdout, stderr)
    fallback_record_count = 1 if exit_code == 0 else 0
    inferred_record_count = command_summary.get("total_tests") or fallback_record_count
    return {
        **entry,
        "repo_id": repo_id,
        "suite_id": suite_id,
        "run_id": identity,
        "source_version": source_version,
        "roster_hash": roster_hash,
        "policy_hash": policy_hash,
        "environment_fingerprint": environment_fingerprint or _environment_fingerprint(),
        "started_at": started_at,
        "finished_at": _utc_now(),
        "baseline_decision": _baseline_decision_for_entry(entry),
        "current_decision": current_decision,
        "baseline_record_count": entry.get("baseline_record_count"),
        "current_record_count": entry.get("current_record_count", inferred_record_count),
        "parser_status": parser_status,
        "runtime_ms": runtime_ms,
        "runtime_budget_ms": int(entry.get("runtime_budget_ms") or timeout_ms),
        "timeout_ms": timeout_ms,
        "timed_out": timed_out,
        "timeout_recorded": timed_out,
        "timeout_cleanup": command_result.timeout_cleanup,
        "command_exit_code": exit_code,
        "failure_kind": failure_kind,
        "command_summary": command_summary,
        "runner_dialect": runner_parse["dialect"],
        "runner_parser": {
            "parser_status": runner_parse["parser_status"],
            "ignored_noise": runner_parse["ignored_noise"],
        },
        "bootstrap": bootstrap,
        "split_execution": _no_split_execution(),
        "command_excerpt": safe_output["excerpt"],
        "output_safety": safe_output["metadata"],
        "subset": bool(entry.get("subset") or entry.get("subset_command")),
        "subset_label": str(entry.get("subset_label") or ""),
    }


def _run_split_roster_entry(
    entry: dict[str, Any],
    *,
    repo_id: str,
    suite_id: str,
    repo_path: Path,
    timeout_ms: int,
    command: list[str],
    identity: str,
    started_at: str,
    roster_hash: str,
    policy_hash: str,
    environment_fingerprint: dict[str, str] | None,
    source_version: str,
    bootstrap: dict[str, Any],
    split_plan: dict[str, Any],
) -> dict[str, Any]:
    started = time.perf_counter()
    split_results: list[dict[str, Any]] = []
    aggregate_summary: dict[str, int] = {}
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    any_timeout = False
    any_failed = False
    skipped_count = 0
    for index, split_command in enumerate(split_plan["commands"], start=1):
        split_id = str(index)
        if split_id in split_plan["completed_splits"]:
            skipped_count += 1
            split_results.append({
                "split_id": split_id,
                "status": "skipped_completed",
                "exit_code": 0,
                "record_count": 0,
                "timeout_recorded": False,
            })
            continue
        result = _run_command(_normalize_command(split_command), repo_path, _isolated_command_env(entry.get("env")), timeout_ms)
        any_timeout = any_timeout or result.timed_out
        any_failed = any_failed or result.exit_code != 0 or result.parser_status == "failed"
        parsed = parse_runner_summary(result.stdout, result.stderr)
        summary = parsed["summary"]
        _merge_counts(aggregate_summary, summary)
        stdout_parts.append(result.stdout)
        stderr_parts.append(result.stderr)
        split_results.append({
            "split_id": split_id,
            "status": "hold" if result.timed_out or result.exit_code != 0 or result.parser_status == "failed" else "pass",
            "exit_code": result.exit_code,
            "record_count": int(summary.get("total_tests") or (1 if result.exit_code == 0 else 0)),
            "timeout_recorded": result.timed_out,
            "runner_dialect": parsed["dialect"],
            "runner_parser": {
                "parser_status": parsed["parser_status"],
                "ignored_noise": parsed["ignored_noise"],
            },
            "timeout_cleanup": result.timeout_cleanup,
        })
    if "total_tests" not in aggregate_summary:
        aggregate_summary["total_tests"] = sum(int(item.get("record_count") or 0) for item in split_results)
    runtime_ms = int((time.perf_counter() - started) * 1000)
    combined_stdout = "\n".join(stdout_parts)
    combined_stderr = "\n".join(stderr_parts)
    safe_output = safe_command_output(combined_stdout, combined_stderr)
    split_status = "hold" if any_timeout or any_failed else "pass"
    resume_required = skipped_count > 0 or any_timeout
    return {
        **entry,
        "repo_id": repo_id,
        "suite_id": suite_id,
        "run_id": identity,
        "source_version": source_version,
        "roster_hash": roster_hash,
        "policy_hash": policy_hash,
        "environment_fingerprint": environment_fingerprint or _environment_fingerprint(),
        "started_at": started_at,
        "finished_at": _utc_now(),
        "baseline_decision": _baseline_decision_for_entry(entry),
        "current_decision": "hold" if split_status == "hold" else "pass",
        "baseline_record_count": entry.get("baseline_record_count"),
        "current_record_count": entry.get("current_record_count", aggregate_summary.get("total_tests", 0)),
        "parser_status": "passed",
        "runtime_ms": runtime_ms + int(bootstrap.get("runtime_ms") or 0),
        "runtime_budget_ms": int(entry.get("runtime_budget_ms") or timeout_ms * max(1, len(split_plan["commands"]))),
        "timeout_ms": timeout_ms,
        "timed_out": any_timeout,
        "timeout_recorded": any_timeout,
        "timeout_cleanup": _no_timeout_cleanup() if not any_timeout else {"timeout_reason": "split_timeout_recorded", "cleanup_attempted": True, "cleanup_method": "per_split", "cleanup_completed": True, "fallback_kill_used": False},
        "command_exit_code": 1 if any_failed or any_timeout else 0,
        "failure_kind": "timeout" if any_timeout else "test_failure" if any_failed else "",
        "command_summary": aggregate_summary,
        "runner_dialect": "split",
        "runner_parser": {"parser_status": "parsed" if aggregate_summary.get("total_tests") else "unparsed", "ignored_noise": []},
        "bootstrap": bootstrap,
        "split_execution": {
            "status": split_status,
            "mode": "split",
            "configured": True,
            "split_count": len(split_plan["commands"]),
            "completed_count": sum(1 for item in split_results if item["status"] == "pass"),
            "skipped_count": skipped_count,
            "resume_required": resume_required,
            "resume_token": split_plan["resume_token"],
            "splits": split_results,
            "original_command": command,
        },
        "command_excerpt": safe_output["excerpt"],
        "output_safety": safe_output["metadata"],
        "subset": bool(entry.get("subset") or entry.get("subset_command")),
        "subset_label": str(entry.get("subset_label") or ""),
    }


def _timeout_ms_for_entry(entry: dict[str, Any]) -> int:
    if entry.get("timeout_ms") is not None:
        return int(entry["timeout_ms"])
    timeout_profile = str(entry.get("timeout_profile") or "")
    if timeout_profile in REPO_CLASS_TIMEOUT_MS:
        return REPO_CLASS_TIMEOUT_MS[timeout_profile]
    repo_class = str(entry.get("repo_class") or "small").lower()
    return REPO_CLASS_TIMEOUT_MS.get(repo_class, DEFAULT_TIMEOUT_MS)


def _baseline_decision_for_entry(entry: dict[str, Any]) -> str:
    if entry.get("baseline_decision"):
        return str(entry["baseline_decision"])
    if str(entry.get("ownership_scope") or "").lower() == "external":
        return ""
    return "pass"


def _policy_hash(roster: dict[str, Any]) -> str:
    policy_ref = roster.get("default_policy_ref") or roster.get("policy_ref") or "default"
    return _stable_id("policy", str(policy_ref))


def _run_identity(repo_id: str, suite_id: str, command: list[str], roster_hash: str, source_version: str) -> str:
    return _stable_id("real-repo-run", repo_id, suite_id, " ".join(command), roster_hash, source_version)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _stable_hash(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(data.encode("utf-8")).hexdigest()


def _environment_fingerprint() -> dict[str, str]:
    return {
        "os": platform.system() or os.name,
        "os_release": platform.release(),
        "python": platform.python_version(),
        "shell": Path(os.environ.get("SHELL") or os.environ.get("COMSPEC") or "").name,
    }


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _isolated_command_env(extra_env: Any | None = None) -> dict[str, str]:
    env = dict(os.environ)
    for key in [
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTEST_CURRENT_TEST",
        "UV_PROJECT_ENVIRONMENT",
        "VIRTUAL_ENV",
    ]:
        env.pop(key, None)
    if isinstance(extra_env, dict):
        for key, value in extra_env.items():
            if isinstance(key, str) and isinstance(value, str):
                env[key] = value
    return env


def _safe_repo_id(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.strip())
    return safe.strip("-") or "repo"


def _classify_command_failure(stdout: str, stderr: str, timed_out: bool, parser_status: str) -> str:
    if timed_out:
        return "timeout"
    if parser_status == "failed":
        return "command_launch_failed"
    text = f"{stdout}\n{stderr}".lower()
    if (
        "is not recognized as an internal or external command" in text
        or "cannot find module" in text
        or "modulenotfounderror: no module named" in text
        or "no module named " in text
    ):
        return "missing_test_dependency"
    if "minversion" in text and "requires pytest" in text and "actual pytest" in text:
        return "runner_config_mismatch"
    if (
        "failed to fetch" in text
        or "pypi.org/simple" in text
        or "tcp connect error" in text
        or "network" in text
        or "dns" in text
        or "socket" in text
    ) and (
        "failed to resolve requirements" in text
        or "failed to build" in text
        or "no solution found" in text
        or "build-system.requires" in text
    ):
        return "dependency_network_blocked"
    if " failures " in text or " failed" in text or " errors " in text or " error collecting " in text:
        return "test_failure"
    return ""


def _command_excerpt(stdout: str, stderr: str, limit: int = 2000) -> str:
    return safe_command_output(stdout, stderr, limit=limit)["excerpt"]


def _parse_command_summary(stdout: str, stderr: str) -> dict[str, int]:
    """Extract safe aggregate test counts from common runner output."""
    return parse_runner_summary(stdout, stderr)["summary"]
