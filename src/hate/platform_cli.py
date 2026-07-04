"""Platform CLI orchestration helpers.

The platform command is a user-facing wrapper over canonical HATE reports. It
does not recompute release verdicts; it projects existing evidence for operators.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from hate.evaluation import query_real_repo_history, run_real_repo_roster
from hate.post_poc.baseline import build_baseline_promotion_report
from hate.platform_ops import (
    build_platform_assignment_report,
    build_platform_schedule_plan,
    build_platform_score_report,
    build_platform_triage_report,
    build_platform_verdict_report,
    run_platform_plugin,
)
from hate.policy_config import build_platform_policy_report
from hate.p2p3 import serve_product_read_model


class PlatformCliError(Exception):
    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


SELF_GENERATED_PLATFORM_RECORD_TYPES = {
    "platform-assignment-report",
    "platform-debt-report",
    "platform-findings-report",
    "platform-html-report",
    "platform-review-report",
    "platform-score-report",
    "platform-triage-report",
    "platform-verdict-evaluation-report",
}


def platform_run(roster_path: Path, out_dir: Path, source_version: str | None = None) -> dict[str, Any]:
    return run_real_repo_roster(roster_path=roster_path, out_dir=out_dir, source_version=source_version)


def platform_history(
    store_dir: Path,
    *,
    repo_id: str | None = None,
    suite_id: str | None = None,
    source_version: str | None = None,
    status: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    return query_real_repo_history(
        store_dir,
        repo_id=repo_id,
        suite_id=suite_id,
        source_version=source_version,
        status=status,
        since=since,
        until=until,
        limit=limit,
    )


def platform_compare(base_path: Path, head_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    base = _read_json(base_path)
    head = _read_json(head_path)
    base_reports = _report_map(base, base_path.parent)
    head_reports = _report_map(head, head_path.parent)
    findings: list[dict[str, Any]] = []
    deltas: list[dict[str, Any]] = []

    for key in sorted(set(base_reports) | set(head_reports)):
        before = base_reports.get(key)
        after = head_reports.get(key)
        delta = _comparison_delta(key, before, after)
        if delta["changes"]:
            deltas.append(delta)
        if before and after and before.get("overall_status") == "pass" and after.get("overall_status") != "pass":
            findings.append(_finding("platform_compare_status_regression", key, after))
        if before and after and _int(after.get("current", {}).get("record_count")) < _int(before.get("current", {}).get("record_count")):
            findings.append(_finding("platform_compare_record_count_drop", key, after))

    report = {
        "schema_version": "HATE/v1",
        "record_type": "platform-comparison-report",
        "overall_status": "hold" if findings else "pass",
        "readiness_effect": "hold" if findings else "none",
        "base": str(base_path),
        "head": str(head_path),
        "deltas": deltas,
        "findings": findings,
        "summary": {
            "delta_count": len(deltas),
            "finding_count": len(findings),
        },
        "sourceRefs": [str(base_path), str(head_path)],
    }
    if out_path is not None:
        _write_json(out_path, report)
    return report


def platform_findings(input_path: Path) -> dict[str, Any]:
    reports = _load_reports(input_path)
    findings = []
    for report in reports:
        report_ref = _report_ref(report)
        for finding in report.get("findings", []) or []:
            item = dict(finding)
            item.setdefault("sourceRefs", _source_refs(finding) or _source_refs(report) or [report_ref])
            item["report_id"] = report.get("report_id", report_ref)
            item["record_type"] = report.get("record_type", "")
            findings.append(item)
    return _projection_report("platform-findings-report", input_path, findings, "finding_count")


def platform_debt(input_path: Path) -> dict[str, Any]:
    reports = _load_reports(input_path)
    debts = []
    for report in reports:
        for key in ("risk_debt", "risk_debts", "debt", "debts"):
            values = report.get(key, []) or []
            if isinstance(values, dict):
                values = [values]
            for item in values:
                if isinstance(item, dict):
                    debt = dict(item)
                    debt.setdefault("sourceRefs", _source_refs(item) or _source_refs(report))
                    debts.append(debt)
    return _projection_report("platform-debt-report", input_path, debts, "debt_count")


def platform_review(input_path: Path) -> dict[str, Any]:
    reports = _load_reports(input_path)
    reviews = []
    for report in reports:
        for key in ("manual_review_requests", "manual_reviews", "review_requests", "requiredHumanReview"):
            values = report.get(key, []) or []
            if isinstance(values, dict):
                values = [values]
            for item in values:
                if isinstance(item, dict):
                    review = dict(item)
                    review.setdefault("sourceRefs", _source_refs(item) or _source_refs(report))
                    reviews.append(review)
    return _projection_report("platform-review-report", input_path, reviews, "review_count")


def platform_policy_explain(policy_path: Path, out_path: Path | None = None, profile: str = "default") -> dict[str, Any]:
    data = _read_json(policy_path)
    if "base_policy" not in data and "policy" not in data:
        data = {"base_policy": data, "profile": profile}
    else:
        data = {**data, "profile": data.get("profile", profile)}
    report = build_platform_policy_report(data, report_id="platform-policy-explain")
    if out_path is not None:
        _write_json(out_path, report)
    return report


def platform_report_html(input_path: Path, out_path: Path) -> dict[str, Any]:
    reports = _load_reports(input_path)
    findings = platform_findings(input_path)["items"]
    debts = platform_debt(input_path)["items"]
    reviews = platform_review(input_path)["items"]
    critical = [item for item in findings if str(item.get("severity", "")).lower() in {"critical", "high"}]
    overall_status = "hold" if critical or any(_report_holds(report) for report in reports) else "pass"
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(report.get('record_type', '')))}</td>"
        f"<td>{html.escape(str(report.get('report_id', '')))}</td>"
        f"<td>{html.escape(str(report.get('overall_status', report.get('status', 'unknown'))))}</td>"
        f"<td>{html.escape(str(len(report.get('findings', []) or [])))}</td>"
        "</tr>"
        for report in reports
    )
    finding_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('code', '')))}</td>"
        f"<td>{html.escape(str(item.get('severity', '')))}</td>"
        f"<td>{html.escape(str(item.get('readiness_effect', '')))}</td>"
        f"<td>{html.escape(', '.join(_source_refs(item)))}</td>"
        "</tr>"
        for item in findings
    )
    document = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>HATE Platform Report</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
th, td {{ border: 1px solid #ccc; padding: 0.4rem; text-align: left; }}
</style>
<h1>HATE Platform Daily Report</h1>
<p>Reports: {len(reports)} / Findings: {len(findings)} / Critical queue: {len(critical)} / Debt: {len(debts)} / Reviews: {len(reviews)}</p>
<h2>Reports</h2>
<table><thead><tr><th>Type</th><th>ID</th><th>Status</th><th>Findings</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Operator Queue</h2>
<table><thead><tr><th>Code</th><th>Severity</th><th>Owner</th><th>Due</th><th>Source refs</th></tr></thead><tbody>{_queue_rows(critical)}</tbody></table>
<h2>Findings</h2>
<table><thead><tr><th>Code</th><th>Severity</th><th>Effect</th><th>Source refs</th></tr></thead><tbody>{finding_rows}</tbody></table>
<h2>Risk Debt</h2>
<table><thead><tr><th>ID</th><th>Owner</th><th>Expiry</th><th>Status</th></tr></thead><tbody>{_debt_rows(debts)}</tbody></table>
<h2>Manual Review</h2>
<table><thead><tr><th>ID</th><th>Owner</th><th>Blocking</th><th>Decision</th></tr></thead><tbody>{_review_rows(reviews)}</tbody></table>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(document, encoding="utf-8")
    return {
        "schema_version": "HATE/v1",
        "record_type": "platform-html-report",
        "overall_status": overall_status,
        "html_path": str(out_path),
        "report_count": len(reports),
        "finding_count": len(findings),
        "debt_count": len(debts),
        "review_count": len(reviews),
        "critical_queue_count": len(critical),
        "sourceRefs": [str(input_path)],
    }


def platform_serve(readiness_dir: Path, host: str, port: int) -> None:
    serve_product_read_model(readiness_dir=readiness_dir, host=host, port=port)


def platform_schedule(
    roster_path: Path,
    history_store: Path,
    out_path: Path | None = None,
    cache_ttl_hours: int = 24,
    retry_limit: int = 1,
    force: bool = False,
) -> dict[str, Any]:
    return build_platform_schedule_plan(
        roster_path,
        history_store,
        out_path,
        cache_ttl_hours=cache_ttl_hours,
        retry_limit=retry_limit,
        force=force,
    )


def platform_assign(input_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    return build_platform_assignment_report(input_path, out_path)


def platform_plugin_run(manifest_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    return run_platform_plugin(manifest_path, out_path)


def platform_score(input_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    return build_platform_score_report(input_path, out_path)


def platform_verdict(input_path: Path, corpus_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    return build_platform_verdict_report(input_path, corpus_path, out_path)


def platform_triage(input_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    return build_platform_triage_report(input_path, out_path)


def platform_baseline_promote(input_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    data = _read_json(input_path)
    report = build_baseline_promotion_report(
        data.get("input", data),
        report_id=str(data.get("fixture_id") or data.get("report_id") or "platform-baseline-promotion"),
        source_refs=[str(input_path)],
    )
    if out_path is not None:
        _write_json(out_path, report)
    return report


def _projection_report(record_type: str, input_path: Path, items: list[dict[str, Any]], count_key: str) -> dict[str, Any]:
    overall_status = "hold" if any(_projection_item_holds(item) for item in items) else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": record_type,
        "overall_status": overall_status,
        "items": items,
        "summary": {count_key: len(items)},
        "sourceRefs": [str(input_path)],
    }


def _projection_item_holds(item: dict[str, Any]) -> bool:
    effect = str(item.get("readiness_effect") or item.get("effect") or "").lower()
    severity = str(item.get("severity") or "").lower()
    return effect in {"hold", "blocked", "hard_dq"} or severity in {"critical", "high"}


def _report_holds(report: dict[str, Any]) -> bool:
    status = str(report.get("overall_status") or report.get("status") or "").lower()
    return status in {"hold", "blocked", "hard_dq", "no_go"}


def _load_reports(input_path: Path) -> list[dict[str, Any]]:
    if not input_path.exists():
        raise PlatformCliError(f"platform input not found: {input_path}")
    directory_input = input_path.is_dir()
    paths = [input_path] if input_path.is_file() else sorted(input_path.glob("*.json"))
    reports = []
    for path in paths:
        try:
            value = _read_json(path)
        except json.JSONDecodeError as exc:
            raise PlatformCliError(f"invalid JSON report: {path}") from exc
        if isinstance(value, dict):
            if directory_input and value.get("record_type") in SELF_GENERATED_PLATFORM_RECORD_TYPES:
                continue
            reports.append(value)
    return reports


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PlatformCliError(f"JSON file not found: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PlatformCliError(f"JSON file must contain an object: {path}")
    return value


def _report_map(report: dict[str, Any], report_dir: Path) -> dict[str, dict[str, Any]]:
    if report.get("record_type") == "real-repo-evaluation-run-report":
        generated = report.get("generated_reports", []) or []
        mapped = {}
        for name in generated:
            path = report_dir / str(name)
            if path.exists():
                loaded = _read_json(path)
                mapped[_report_key(loaded)] = loaded
        if mapped:
            return mapped
    return {_report_key(report): report}


def _comparison_delta(key: str, before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    changes = []
    if before is None:
        changes.append("added")
    elif after is None:
        changes.append("removed")
    else:
        fields = [
            ("overall_status", before.get("overall_status"), after.get("overall_status")),
            ("record_count", before.get("current", {}).get("record_count"), after.get("current", {}).get("record_count")),
            ("runtime_ms", before.get("current", {}).get("runtime_ms"), after.get("current", {}).get("runtime_ms")),
            ("runner_dialect", before.get("current", {}).get("runner_dialect"), after.get("current", {}).get("runner_dialect")),
        ]
        changes = [name for name, left, right in fields if left != right]
    return {"key": key, "changes": changes}


def _finding(code: str, key: str, report: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "high",
        "readiness_effect": "hold",
        "message": f"{code}: {key}",
        "sourceRefs": _source_refs(report or {}),
    }


def _report_key(report: dict[str, Any]) -> str:
    return f"{report.get('repo_id', report.get('report_id', 'report'))}:{report.get('suite_id', 'default')}"


def _report_ref(report: dict[str, Any]) -> str:
    return str(report.get("report_id") or report.get("record_type") or "report")


def _source_refs(value: dict[str, Any]) -> list[str]:
    refs = value.get("sourceRefs") or value.get("source_refs") or []
    if isinstance(refs, str):
        return [refs]
    return [str(item) for item in refs if isinstance(item, str)]


def _queue_rows(items: list[dict[str, Any]]) -> str:
    return "\n".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('code', '')))}</td>"
        f"<td>{html.escape(str(item.get('severity', '')))}</td>"
        f"<td>{html.escape(str(item.get('owner', '')))}</td>"
        f"<td>{html.escape(str(item.get('due_date', item.get('dueDate', ''))))}</td>"
        f"<td>{html.escape(', '.join(_source_refs(item)))}</td>"
        "</tr>"
        for item in items
    )


def _debt_rows(items: list[dict[str, Any]]) -> str:
    return "\n".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('debt_id', item.get('id', ''))))}</td>"
        f"<td>{html.escape(str(item.get('owner', '')))}</td>"
        f"<td>{html.escape(str(item.get('expiry', item.get('expiry_date', ''))))}</td>"
        f"<td>{html.escape(str(item.get('status', '')))}</td>"
        "</tr>"
        for item in items
    )


def _review_rows(items: list[dict[str, Any]]) -> str:
    return "\n".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('request_id', item.get('id', ''))))}</td>"
        f"<td>{html.escape(str(item.get('owner', '')))}</td>"
        f"<td>{html.escape(str(item.get('blocking', '')))}</td>"
        f"<td>{html.escape(str(item.get('required_decision', item.get('decision', ''))))}</td>"
        "</tr>"
        for item in items
    )


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
