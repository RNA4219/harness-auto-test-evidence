"""Platform operation helpers for scheduler, ownership, plugins, and scoring."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from hate.evaluation.score_model import build_real_repo_score_report
from hate.plugins.sandbox import build_plugin_sandbox_report


class PlatformOpsError(Exception):
    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def build_platform_schedule_plan(
    roster_path: Path,
    history_store: Path,
    out_path: Path | None = None,
    *,
    cache_ttl_hours: int = 24,
    retry_limit: int = 1,
    force: bool = False,
    now: str | None = None,
) -> dict[str, Any]:
    roster = _read_json(roster_path)
    history = _read_history(history_store)
    generated_at = now or _utc_now()
    generated_dt = _parse_time(generated_at) or datetime.now(UTC)
    entries = _roster_entries(roster)
    tasks = []
    for entry in entries:
        key = (entry["repo_id"], entry["suite_id"])
        last = history.get(key)
        age_hours = _age_hours(generated_dt, last)
        cached = bool(last and last.get("status") == "pass" and age_hours is not None and age_hours <= cache_ttl_hours)
        held = bool(last and last.get("status") in {"hold", "blocked"})
        retries = min(retry_limit, 1 if held else 0)
        should_run = force or not cached or held
        tasks.append({
            "repo_id": entry["repo_id"],
            "suite_id": entry["suite_id"],
            "action": "run" if should_run else "cache_hit",
            "cache": {
                "hit": cached and not force and not held,
                "ttl_hours": cache_ttl_hours,
                "age_hours": age_hours,
                "last_status": last.get("status") if last else "",
            },
            "retry": {
                "eligible": held,
                "limit": retry_limit,
                "planned_attempts": retries,
            },
            "resume_token": _resume_token(entry, last),
            "sourceRefs": [str(roster_path)],
        })
    report = {
        "schema_version": "HATE/v1",
        "record_type": "platform-schedule-plan",
        "generated_at": generated_at,
        "overall_status": "pass",
        "cache_ttl_hours": cache_ttl_hours,
        "retry_limit": retry_limit,
        "force": force,
        "tasks": tasks,
        "summary": {
            "task_count": len(tasks),
            "run_count": sum(1 for task in tasks if task["action"] == "run"),
            "cache_hit_count": sum(1 for task in tasks if task["action"] == "cache_hit"),
            "retry_count": sum(task["retry"]["planned_attempts"] for task in tasks),
        },
        "sourceRefs": [str(roster_path), str(history_store)],
    }
    if out_path is not None:
        _write_json(out_path, report)
    return report


def build_platform_assignment_report(input_path: Path, out_path: Path | None = None, *, now: str | None = None) -> dict[str, Any]:
    reports = _load_reports(input_path)
    generated_at = now or _utc_now()
    generated_dt = _parse_time(generated_at) or datetime.now(UTC)
    assignments = []
    findings = []
    for report in reports:
        for item in list(report.get("findings", []) or []):
            owner = str(item.get("owner") or report.get("owner") or "")
            due_date = str(item.get("due_date") or item.get("dueDate") or "")
            severity = str(item.get("severity") or "medium")
            code = str(item.get("code") or "finding")
            status = "assigned" if owner and due_date else "missing_owner_or_due_date"
            if status != "assigned":
                findings.append(_finding("platform_assignment_missing_owner_or_due_date", code, report, item))
            elif _is_overdue(due_date, generated_dt):
                status = "sla_breached"
                findings.append(_finding("platform_assignment_sla_breached", code, report, item))
            assignments.append({
                "finding_code": code,
                "severity": severity,
                "owner": owner,
                "due_date": due_date,
                "sla_status": status,
                "sourceRefs": _source_refs(item) or _source_refs(report),
            })
    report = {
        "schema_version": "HATE/v1",
        "record_type": "platform-assignment-report",
        "generated_at": generated_at,
        "overall_status": "hold" if findings else "pass",
        "assignments": assignments,
        "findings": findings,
        "summary": {
            "assignment_count": len(assignments),
            "missing_owner_or_due_date_count": sum(1 for item in assignments if item["sla_status"] == "missing_owner_or_due_date"),
            "sla_breach_count": sum(1 for item in assignments if item["sla_status"] == "sla_breached"),
        },
        "sourceRefs": [str(input_path)],
    }
    if out_path is not None:
        _write_json(out_path, report)
    return report


def run_platform_plugin(manifest_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    plugin = dict(manifest.get("plugin") or {})
    execution = dict(manifest.get("execution") or {})
    command = execution.get("command")
    if command is not None:
        if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
            raise PlatformOpsError("plugin execution.command must be a string list")
        timeout_ms = int((manifest.get("limits") or {}).get("timeout_ms") or 1000)
        result = subprocess.run(
            command,
            cwd=str(manifest_path.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_ms / 1000,
            check=False,
        )
        output = _json_or_empty(result.stdout)
        execution = {
            **execution,
            "exit_code": result.returncode,
            "output": output,
            "output_bytes": len(result.stdout.encode("utf-8", errors="replace")),
            "crashed": result.returncode != 0,
        }
    sandbox = build_plugin_sandbox_report({**manifest, "plugin": plugin, "execution": execution}, report_id=str(plugin.get("plugin_id") or "platform-plugin-run"))
    report = {
        "schema_version": "HATE/v1",
        "record_type": "platform-plugin-run-report",
        "overall_status": sandbox["overall_status"],
        "readiness_effect": sandbox["readiness_effect"],
        "plugin_id": sandbox["plugin_id"],
        "detector_id": sandbox["detector_id"],
        "sandbox_report": sandbox,
        "findings": sandbox["findings"],
        "sourceRefs": [str(manifest_path), *sandbox.get("sourceRefs", [])],
    }
    if out_path is not None:
        _write_json(out_path, report)
    return report


def build_platform_score_report(input_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    reports = _load_score_reports(input_path)
    scores = []
    for report in reports:
        score_input = _score_input_from_report(report)
        scores.append(build_real_repo_score_report(score_input, report_id=f"score-{score_input['repo_id']}-{score_input['suite_id']}"))
    report = {
        "schema_version": "HATE/v1",
        "record_type": "platform-score-report",
        "overall_status": "pass",
        "scores": scores,
        "summary": {
            "score_count": len(scores),
            "average_score": round(sum(item["score"] for item in scores) / len(scores), 2) if scores else 0.0,
            "blocked_count": sum(1 for item in scores if item["score_band"] == "blocked"),
        },
        "sourceRefs": [str(input_path)],
    }
    if out_path is not None:
        _write_json(out_path, report)
    return report


def _score_input_from_report(report: dict[str, Any]) -> dict[str, Any]:
    findings = list(report.get("findings", []) or [])
    regressions = list(report.get("regressions", []) or [])
    blocking_regressions = [
        item for item in regressions
        if str(item.get("regression_class") or item.get("code") or "") != "external_hold_detected"
    ]
    current = dict(report.get("current") or {})
    age_penalty = 0.0
    if _parse_time(str(report.get("finished_at") or "")) is None:
        age_penalty = 0.2
    return {
        "repo_id": str(report.get("repo_id") or report.get("report_id") or "repo"),
        "suite_id": str(report.get("suite_id") or "default"),
        "components": {
            "evidence_strength": 0.9 if report.get("overall_status") == "pass" else 0.55,
            "coverage_confidence": 0.8 if current.get("record_count") else 0.2,
            "oracle_confidence": 0.4 if current.get("runner_dialect") in {"nextjs-build", "typescript-typecheck"} else 0.8,
            "freshness_score": max(0.0, 1.0 - age_penalty),
            "stability_score": 1.0 if not blocking_regressions else 0.3,
            "ownership_clarity": 1.0 if report.get("ownership_scope") == "owned" else 0.6,
        },
        "penalties": {
            "regression_penalty": min(40.0, 15.0 * len(blocking_regressions)),
            "timeout_penalty": 20.0 if report.get("timeout_recorded") else 0.0,
            "record_collapse_penalty": 20.0 if any(item.get("code") == "real_repo_record_count_collapse" for item in findings) else 0.0,
            "manual_debt_penalty": 5.0 * len(report.get("risk_debt", []) or []),
            "expired_debt_penalty": 15.0 if any("expired" in str(item.get("code", "")) for item in findings) else 0.0,
            "unsafe_artifact_penalty": 20.0 if current.get("unsafe_artifact_findings") else 0.0,
            "subset_penalty": 12.0 if _is_subset_limited(report) else 0.0,
        },
        "sourceRefs": _source_refs(report),
    }


def _load_score_reports(input_path: Path) -> list[dict[str, Any]]:
    reports = _load_reports(input_path)
    manifests = [report for report in reports if report.get("record_type") == "real-repo-evaluation-run-report"]
    if manifests:
        return _dedupe_score_reports(
            report
            for manifest in manifests
            for report in _load_generated_reports(input_path, manifest)
        )
    expanded: list[dict[str, Any]] = []
    for report in reports:
        if report.get("record_type") == "real-repo-evaluation-report":
            expanded.append(report)
    return _dedupe_score_reports(expanded)


def _load_generated_reports(input_path: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    base_dir = input_path.parent if input_path.is_file() else input_path
    reports: list[dict[str, Any]] = []
    for name in manifest.get("generated_reports", []) or []:
        path = base_dir / str(name)
        if not path.exists():
            continue
        report = _read_json(path)
        if report.get("record_type") == "real-repo-evaluation-report":
            reports.append(report)
    return reports


def _is_subset_limited(report: dict[str, Any]) -> bool:
    subset = report.get("subset")
    if isinstance(subset, dict):
        return bool(subset.get("is_subset")) and subset.get("proves_full_suite") is not True
    return bool(subset or report.get("subset_limited"))


def _dedupe_score_reports(reports: Any) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for report in reports:
        key = (
            str(report.get("repo_id") or ""),
            str(report.get("suite_id") or "default"),
            str(report.get("run_id") or ""),
        )
        deduped[key] = report
    return list(deduped.values())


def _roster_entries(roster: dict[str, Any]) -> list[dict[str, str]]:
    entries = []
    for repo in roster.get("repositories", []) or []:
        repo_id = str(repo.get("repo_id") or "")
        suites = repo.get("suites")
        if isinstance(suites, list) and suites:
            for suite in suites:
                entries.append({"repo_id": repo_id, "suite_id": str(suite.get("suite_id") or "default")})
        else:
            entries.append({"repo_id": repo_id, "suite_id": str(repo.get("suite_id") or "default")})
    return entries


def _read_history(store_dir: Path) -> dict[tuple[str, str], dict[str, Any]]:
    path = store_dir / "run_history.jsonl" if store_dir.is_dir() else store_dir
    if not path.exists():
        return {}
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        key = (str(item.get("repo_id") or ""), str(item.get("suite_id") or "default"))
        latest[key] = item
    return latest


def _age_hours(now: datetime, item: dict[str, Any] | None) -> float | None:
    if not item:
        return None
    parsed = _parse_time(str(item.get("finished_at") or item.get("started_at") or ""))
    if parsed is None:
        return None
    return round(max(0.0, (now - parsed).total_seconds() / 3600), 2)


def _resume_token(entry: dict[str, str], last: dict[str, Any] | None) -> str:
    run_id = str(last.get("run_id") or "new") if last else "new"
    return f"{entry['repo_id']}:{entry['suite_id']}:{run_id}"


def _load_reports(input_path: Path) -> list[dict[str, Any]]:
    if not input_path.exists():
        raise PlatformOpsError(f"input not found: {input_path}")
    paths = [input_path] if input_path.is_file() else sorted(input_path.glob("*.json"))
    return [_read_json(path) for path in paths]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PlatformOpsError(f"JSON must be an object: {path}")
    return value


def _json_or_empty(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _finding(code: str, finding_code: str, report: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "high",
        "readiness_effect": "hold",
        "message": f"{code}: {finding_code}",
        "sourceRefs": _source_refs(item) or _source_refs(report),
    }


def _is_overdue(due_date: str, now: datetime) -> bool:
    parsed = _parse_time(due_date)
    return parsed is not None and parsed < now


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _source_refs(value: dict[str, Any]) -> list[str]:
    refs = value.get("sourceRefs") or value.get("source_refs") or value.get("sourceRef") or []
    if isinstance(refs, str):
        return [refs]
    return [str(item) for item in refs if isinstance(item, str)]


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
