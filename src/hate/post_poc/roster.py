from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .common import apply_productization_contract_tree, productization_envelope


DISCOVERY_MARKERS: tuple[tuple[str, str, list[str], list[str]], ...] = (
    ("pyproject.toml", "python", ["uv", "run", "pytest"], ["python-tests"]),
    ("package.json", "node", ["npm", "test"], ["node-tests"]),
    ("Cargo.toml", "rust", ["cargo", "test"], ["rust-tests"]),
    ("go.mod", "go", ["go", "test", "./..."], ["go-tests"]),
)


@dataclass(frozen=True)
class RosterFinding:
    code: str
    severity: str
    message: str
    sourceRef: str
    readiness_effect: str = "hold"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRef": self.sourceRef,
            "readiness_effect": self.readiness_effect,
        }


def evaluate_roster_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_roster_maintenance_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "roster-maintenance-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_roster_maintenance_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "roster-maintenance-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["roster-maintenance"])
    now = str(input_data.get("now") or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"))
    now_dt = _parse_time(now) or datetime.now(UTC)
    repos = [_normalize_repo(repo) for repo in input_data.get("repositories", [])]
    plans: list[dict[str, Any]] = []
    recipes: list[dict[str, Any]] = []
    quarantine_events: list[dict[str, Any]] = []
    findings: list[RosterFinding] = []

    for index, repo in enumerate(repos):
        source_ref = f"{source_refs[0]}#/repositories/{index}"
        repo_findings = _findings_for_repo(repo, now_dt, source_ref)
        findings.extend(repo_findings)
        action = "quarantine" if any(item.code in {"roster_repo_stale", "roster_dependency_bootstrap_failed"} for item in repo_findings) else "maintain"
        if any(item.code == "roster_external_repo_repair_denied" for item in repo_findings):
            action = "external_hold"
        plan = {
            "record_type": "real-repo-roster-maintenance-plan",
            "repo_id": repo["repo_id"],
            "ownership_scope": repo["ownership_scope"],
            "repo_class": repo["repo_class"],
            "suite_ids": [suite["suite_id"] for suite in repo["suites"]],
            "discovery_source": repo["discovery_source"],
            "last_seen_at": repo["last_seen_at"],
            "stale_after": repo["stale_after"],
            "retry_isolation_group": repo["retry_isolation_group"],
            "external_repair_allowed": repo["external_repair_allowed"],
            "action": action,
            "sourceRefs": [source_ref],
        }
        plans.append(plan)
        recipes.append({
            "record_type": "real-repo-environment-recipe",
            "repo_id": repo["repo_id"],
            "environment_recipe_ref": repo["environment_recipe_ref"],
            "dependency_bootstrap_command": repo["dependency_bootstrap_command"],
            "bootstrap_status": repo["dependency_bootstrap_status"],
            "sourceRefs": [source_ref],
        })
        if action in {"quarantine", "external_hold"}:
            quarantine_events.append({
                "record_type": "real-repo-quarantine-event",
                "repo_id": repo["repo_id"],
                "quarantine_reason": ",".join(sorted({finding.code for finding in repo_findings})),
                "retry_isolation_group": repo["retry_isolation_group"],
                "external_repair_allowed": repo["external_repair_allowed"],
                "sourceRefs": [source_ref],
            })

    status = "hold" if findings else "pass"
    report = {
        "schema_version": "HATE/v1",
        "record_type": "real-repo-roster-maintenance-report",
        "report_id": report_id,
        **productization_envelope(input_data, report_id=report_id, source_refs=source_refs),
        "generated_at": now,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "maintenance_plans": plans,
        "environment_recipes": recipes,
        "quarantine_events": quarantine_events,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "repo_count": len(repos),
            "suite_count": sum(len(repo["suites"]) for repo in repos),
            "quarantine_count": len(quarantine_events),
            "finding_count": len(findings),
            "external_hold_count": sum(1 for item in plans if item["action"] == "external_hold"),
            "large_roster": len(repos) >= 100,
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(report, source_refs=source_refs)


def build_roster_execution_manifest(
    input_data: dict[str, Any],
    *,
    manifest_id: str = "real-repo-roster-execution-manifest",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["roster-execution-manifest"])
    report = (
        input_data
        if input_data.get("record_type") == "real-repo-roster-maintenance-report"
        else build_roster_maintenance_report(input_data, report_id=f"{manifest_id}:maintenance", source_refs=source_refs)
    )
    recipes = {recipe["repo_id"]: recipe for recipe in report.get("environment_recipes", [])}
    entries = [
        _execution_entry_for(plan, recipes.get(plan["repo_id"], {}), index)
        for index, plan in enumerate(report.get("maintenance_plans", []))
    ]
    findings = _execution_manifest_findings(report, entries, source_refs[0])
    manifest = {
        "schema_version": "HATE/v1",
        "record_type": "real-repo-roster-execution-manifest",
        "manifest_id": manifest_id,
        **productization_envelope(input_data, report_id=manifest_id, source_refs=source_refs),
        "readiness_effect": "hold" if findings else "none",
        "generated_at": str(report.get("generated_at") or ""),
        "entries": entries,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "entry_count": len(entries),
            "maintain_count": sum(1 for entry in entries if entry["execution_action"] == "run"),
            "quarantine_count": sum(1 for entry in entries if entry["execution_action"] == "quarantine"),
            "external_hold_count": sum(1 for entry in entries if entry["execution_action"] == "external_hold"),
            "bootstrap_required_count": sum(1 for entry in entries if entry["bootstrap_required"]),
            "finding_count": len(findings),
            "ready_for_scheduler": not findings,
        },
        "sourceRefs": sorted(set(source_refs + list(report.get("sourceRefs", [])))),
    }
    return apply_productization_contract_tree(manifest, source_refs=source_refs)


def write_roster_execution_manifest(manifest: dict[str, Any], out_path: str | Path) -> dict[str, Any]:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {
        "schema_version": "HATE/v1",
        "record_type": "real-repo-roster-execution-manifest-artifact",
        **productization_envelope(manifest, report_id=f"{manifest.get('manifest_id') or 'real-repo-roster-execution-manifest'}:artifact", source_refs=list(manifest.get("sourceRefs", []))),
        "readiness_effect": str(manifest.get("readiness_effect") or "none"),
        "artifact_path": str(path),
        "entry_count": len(manifest.get("entries", [])),
        "sourceRefs": list(manifest.get("sourceRefs", [])),
    }


def _execution_entry_for(plan: dict[str, Any], recipe: dict[str, Any], index: int) -> dict[str, Any]:
    action = str(plan.get("action") or "")
    execution_action = "run"
    if action == "quarantine":
        execution_action = "quarantine"
    elif action == "external_hold":
        execution_action = "external_hold"
    bootstrap_status = str(recipe.get("bootstrap_status") or "not_run")
    return {
        "record_type": "real-repo-roster-execution-entry",
        "sequence": index + 1,
        "repo_id": str(plan.get("repo_id") or ""),
        "ownership_scope": str(plan.get("ownership_scope") or ""),
        "repo_class": str(plan.get("repo_class") or ""),
        "suite_ids": list(plan.get("suite_ids", [])),
        "execution_action": execution_action,
        "retry_isolation_group": str(plan.get("retry_isolation_group") or ""),
        "bootstrap_required": bootstrap_status in {"not_run", "failed"},
        "bootstrap_status": bootstrap_status,
        "dependency_bootstrap_command": list(recipe.get("dependency_bootstrap_command", [])),
        "scheduler_job_id": f"roster:{plan.get('repo_id', '')}:{index + 1}",
        "sourceRefs": list(plan.get("sourceRefs", [])) + list(recipe.get("sourceRefs", [])),
    }


def _execution_manifest_findings(
    report: dict[str, Any],
    entries: list[dict[str, Any]],
    source_ref: str,
) -> list[RosterFinding]:
    findings: list[RosterFinding] = []
    if report.get("findings"):
        findings.append(_finding("roster_execution_blocked_by_maintenance_findings", "Execution manifest is not scheduler-ready while maintenance findings remain.", source_ref))
    if not entries:
        findings.append(_finding("roster_execution_entries_missing", "Execution manifest requires at least one roster entry.", source_ref))
    for entry in entries:
        if not entry["retry_isolation_group"]:
            findings.append(_finding("roster_retry_isolation_missing", f"Execution entry {entry['repo_id']} lacks retry isolation group.", source_ref))
        if entry["execution_action"] == "external_hold" and entry["ownership_scope"] != "external":
            findings.append(_finding("roster_external_repo_repair_denied", f"Execution entry {entry['repo_id']} has invalid external hold scope.", source_ref))
        if entry["bootstrap_required"] and not entry["dependency_bootstrap_command"]:
            findings.append(_finding("roster_environment_recipe_missing", f"Execution entry {entry['repo_id']} requires bootstrap command.", source_ref))
    return findings


def discover_repositories_from_filesystem(
    root: str | Path,
    *,
    now: str = "2026-07-03T00:00:00Z",
    stale_after: str = "2026-07-17T00:00:00Z",
    ownership_scope: str = "owned",
    max_depth: int = 3,
) -> dict[str, Any]:
    """Discover local repository roster entries without executing commands."""

    root_path = Path(root)
    repositories: list[dict[str, Any]] = []
    seen: set[Path] = set()
    if not root_path.exists() or not root_path.is_dir():
        return {
            "now": now,
            "repositories": [],
            "sourceRefs": [f"filesystem-discovery:{root_path}"],
        }

    for marker, repo_class, command, suite_ids in DISCOVERY_MARKERS:
        for marker_path in sorted(root_path.rglob(marker)):
            repo_path = marker_path.parent
            if repo_path in seen or not _within_depth(root_path, repo_path, max_depth):
                continue
            seen.add(repo_path)
            repo_id = _repo_id(root_path, repo_path)
            repositories.append({
                "repo_id": repo_id,
                "ownership_scope": ownership_scope,
                "repo_class": repo_class,
                "discovery_source": f"filesystem:{marker}",
                "last_seen_at": now,
                "stale_after": stale_after,
                "environment_recipe_ref": f"discovered://{repo_id}/{marker}",
                "dependency_bootstrap_command": command,
                "dependency_bootstrap_status": "not_run",
                "retry_isolation_group": f"{repo_id}:{repo_class}",
                "expected_record_floor": 1,
                "suites": [{"suite_id": suite_id} for suite_id in suite_ids],
            })

    return {
        "now": now,
        "repositories": sorted(repositories, key=lambda item: item["repo_id"]),
        "sourceRefs": [f"filesystem-discovery:{root_path}"],
    }


def _normalize_repo(raw: dict[str, Any]) -> dict[str, Any]:
    repo = dict(raw or {})
    suites = repo.get("suites") or [{"suite_id": repo.get("suite_id") or "default"}]
    return {
        "repo_id": str(repo.get("repo_id") or ""),
        "ownership_scope": str(repo.get("ownership_scope") or "owned"),
        "repo_class": str(repo.get("repo_class") or "small"),
        "discovery_source": str(repo.get("discovery_source") or ""),
        "last_seen_at": str(repo.get("last_seen_at") or ""),
        "stale_after": str(repo.get("stale_after") or ""),
        "environment_recipe_ref": str(repo.get("environment_recipe_ref") or ""),
        "dependency_bootstrap_command": [str(item) for item in repo.get("dependency_bootstrap_command", [])],
        "dependency_bootstrap_status": str(repo.get("dependency_bootstrap_status") or "not_run"),
        "quarantine_reason": str(repo.get("quarantine_reason") or ""),
        "retry_isolation_group": str(repo.get("retry_isolation_group") or ""),
        "external_repair_allowed": bool(repo.get("external_repair_allowed", False)),
        "repair_requested": bool(repo.get("repair_requested", False)),
        "expected_record_floor": repo.get("expected_record_floor"),
        "suites": [{"suite_id": str(suite.get("suite_id") or "default")} for suite in suites],
    }


def _findings_for_repo(repo: dict[str, Any], now: datetime, source_ref: str) -> list[RosterFinding]:
    findings: list[RosterFinding] = []
    last_seen = _parse_time(repo["last_seen_at"])
    stale_after = _parse_time(repo["stale_after"])
    if last_seen and stale_after and now > stale_after:
        findings.append(_finding("roster_repo_stale", f"Repository {repo['repo_id']} is stale.", source_ref))
    if not repo["environment_recipe_ref"]:
        findings.append(_finding("roster_environment_recipe_missing", f"Repository {repo['repo_id']} lacks environment recipe.", source_ref))
    if repo["dependency_bootstrap_status"] == "failed":
        findings.append(_finding("roster_dependency_bootstrap_failed", f"Repository {repo['repo_id']} dependency bootstrap failed.", source_ref))
    if repo["ownership_scope"] == "external" and repo["repair_requested"] and not repo["external_repair_allowed"]:
        findings.append(_finding("roster_external_repo_repair_denied", f"External repository {repo['repo_id']} cannot be repaired by HATE.", source_ref))
    if not repo["retry_isolation_group"]:
        findings.append(_finding("roster_retry_isolation_missing", f"Repository {repo['repo_id']} lacks retry isolation group.", source_ref))
    if repo["expected_record_floor"] is None:
        findings.append(_finding("roster_expected_record_floor_missing", f"Repository {repo['repo_id']} lacks expected record floor.", source_ref))
    return findings


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _finding(code: str, message: str, source_ref: str) -> RosterFinding:
    return RosterFinding(code=code, severity="high", message=message, sourceRef=source_ref)


def _within_depth(root: Path, path: Path, max_depth: int) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    if rel == Path("."):
        return True
    return len(rel.parts) <= max_depth


def _repo_id(root: Path, path: Path) -> str:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return path.name
    if rel == Path("."):
        return root.name
    return "-".join(rel.parts)
