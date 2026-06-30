from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters.corpus_manifest import evaluate_adapter_corpus_fixture
from .adapters.family_packet import evaluate_adapter_family_fixture
from .api.contract_report import evaluate_api_contract_fixture
from .api.rate_limit import evaluate_api_rate_limit_fixture
from .dashboard.state_report import evaluate_dashboard_state_fixture
from .deployment.topology import evaluate_deployment_topology_fixture
from .entitlement import evaluate_entitlement_fixture
from .enterprise.control_packet import evaluate_enterprise_control_fixture
from .evaluation.agent_quality import evaluate_agent_quality_fixture
from .evaluation.real_repo import evaluate_real_repo_fixture
from .gap_closure_evidence import IMPLEMENTED_GAP_EVIDENCE
from .github_integration import evaluate_github_integration_fixture
from .product_e2e import evaluate_product_e2e_fixture
from .release_channel import evaluate_release_channel_fixture
from .runtime_worker import evaluate_worker_runtime_fixture
from .security.artifact_lifecycle import evaluate_artifact_lifecycle_fixture
from .scale.benchmark_catalog import evaluate_benchmark_catalog_fixture
from .support_ops.diagnostics import evaluate_support_diagnostics_fixture
from .support_ops.observability import evaluate_observability_fixture
from .store.migration_rebuild import evaluate_store_migration_fixture
from .tenant_isolation import evaluate_tenant_isolation_fixture
from .workflow_acceptance import evaluate_acceptance_fixture
from .workflow_birdseye import evaluate_birdseye_fixture
from .workflow_completion import evaluate_completion_fixture
from .workflow_evidence import evaluate_evidence_fixture
from .workflow_plugin import evaluate_workflow_plugin_fixture
from .workflow_task_seed import evaluate_task_seed_fixture
from .workflow_alignment_extra import (
    check_acceptance_index,
    check_feature_detection_policy,
    check_metrics_kpi_policy,
    check_priority_score_policy,
    check_security_release_evidence_policy,
)


class GapClosureError(Exception):
    def __init__(self, message: str, exit_code: int = 2, report: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.report = report


@dataclass(frozen=True)
class GapFixtureRef:
    gap_id: str
    path: str
    case_kind: str


GAP_IDS = [f"HATE-GAP-{index:03d}" for index in range(1, 27)]
REQUIRED_DOCS = [
    "PRODUCT_REQUIREMENTS_GAP_BACKLOG.md",
    "PRODUCT_REQUIREMENTS_GAP_CLOSURE_PACKETS.md",
    "WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md",
    "HOSTED_WORKER_RUNTIME_CONTRACT.md",
    "TENANT_ISOLATION_CONTRACT.md",
    "GITHUB_INTEGRATION_CONTRACT.md",
    "STORE_MIGRATION_INDEX_REBUILD_CONTRACT.md",
    "REAL_REPO_EVALUATION_CONTRACT.md",
    "ADAPTER_CORPUS_MANIFEST.md",
    "PRODUCT_E2E_UAT_CONTRACT.md",
]
def generate_gap_closure_report(
    repo_root: Path,
    out_dir: Path,
    source_version: str | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    process_dir = repo_root / "docs" / "process"
    tasks_path = repo_root / "docs" / "tasks" / "HATE_GAP_CLOSURE_TASK_SEEDS.md"
    acceptance_path = repo_root / "docs" / "acceptance" / "HATE_GAP_CLOSURE_ACCEPTANCE.md"
    packet_path = process_dir / "PRODUCT_REQUIREMENTS_GAP_CLOSURE_PACKETS.md"

    missing_required_docs = [name for name in REQUIRED_DOCS if not (process_dir / name).is_file()]
    missing_ledgers = [
        str(path.relative_to(repo_root))
        for path in [tasks_path, acceptance_path, packet_path]
        if not path.is_file()
    ]

    if not packet_path.is_file():
        report = _empty_report(source_version, missing_required_docs, missing_ledgers)
        _write_report(out_dir, report)
        raise GapClosureError("gap closure packet ledger not found", exit_code=2, report=report)

    packet_text = packet_path.read_text(encoding="utf-8")
    task_text = tasks_path.read_text(encoding="utf-8") if tasks_path.is_file() else ""
    acceptance_text = acceptance_path.read_text(encoding="utf-8") if acceptance_path.is_file() else ""
    fixture_refs = _extract_fixture_refs(packet_text, repo_root)

    gap_reports: list[dict[str, Any]] = []
    for gap_id in GAP_IDS:
        task_id = gap_id.replace("HATE-GAP", "TASK-HATE-GAP")
        acceptance_id = gap_id.replace("HATE-GAP", "AC-HATE-GAP")
        refs = [ref for ref in fixture_refs if ref.gap_id == gap_id]
        positive = [ref for ref in refs if ref.case_kind == "positive"]
        negative = [ref for ref in refs if ref.case_kind == "negative"]
        missing_fixtures = [
            ref.path
            for ref in refs
            if not (repo_root / ref.path).is_file()
        ]
        invalid_fixtures = _invalid_fixture_payloads(repo_root, refs, gap_id, task_id, acceptance_id)
        behavior_results = _evaluate_fixture_behaviors(repo_root, refs)
        uat_reports = sorted({
            item["uat_report"]
            for item in behavior_results
            if item.get("uat_report")
        })

        status = "fixture_ready"
        readiness_effect = "none"
        findings: list[dict[str, Any]] = []
        if gap_id not in packet_text:
            findings.append(_finding("gap_missing_from_packet", gap_id, "Gap is missing from packet ledger."))
        if task_id not in task_text:
            findings.append(_finding("task_seed_missing", gap_id, "Task Seed reference is missing."))
        if acceptance_id not in acceptance_text:
            findings.append(_finding("acceptance_missing", gap_id, "Acceptance reference is missing."))
        if not positive:
            findings.append(_finding("positive_fixture_missing", gap_id, "Positive fixture reference is missing."))
        if not negative:
            findings.append(_finding("negative_fixture_missing", gap_id, "Negative fixture reference is missing."))
        for path in missing_fixtures:
            findings.append(_finding("fixture_file_missing", gap_id, f"Fixture file missing: {path}"))
        for invalid in invalid_fixtures:
            findings.append(_finding("fixture_invalid", gap_id, invalid))
        for behavior in behavior_results:
            if not behavior["matches_expected"]:
                findings.append(
                    _finding(
                        "fixture_behavior_mismatch",
                        gap_id,
                        f"{behavior['fixture_path']}: expected {behavior['expected_status']} "
                        f"but evaluated {behavior['actual_status']}",
                    )
                )

        if findings:
            status = "hold"
            readiness_effect = "hold"
        else:
            implementation_evidence = _implementation_evidence_for(repo_root, gap_id)
            status = "implemented" if implementation_evidence else "checker_ready"

        gap_reports.append({
            "gap_id": gap_id,
            "task_seed_id": task_id,
            "acceptance_id": acceptance_id,
            "status": status,
            "readiness_effect": readiness_effect,
            "fixture_refs": [ref.path for ref in refs],
            "positive_fixture_count": len(positive),
            "negative_fixture_count": len(negative),
            "behavior_checked_count": len(behavior_results),
            "uat_reports": uat_reports,
            "implementation_evidence": _implementation_evidence_for(repo_root, gap_id) or {},
            "findings": findings,
        })

    hard_findings = [
        _finding("required_contract_missing", "global", f"Required contract missing: {name}")
        for name in missing_required_docs
    ] + [
        _finding("required_ledger_missing", "global", f"Required ledger missing: {path}")
        for path in missing_ledgers
    ]

    hold_count = sum(1 for item in gap_reports if item["status"] == "hold")
    checker_ready_count = sum(1 for item in gap_reports if item["status"] == "checker_ready")
    implemented_count = sum(1 for item in gap_reports if item["status"] == "implemented")
    overall_status = "checker_ready" if hold_count == 0 and not hard_findings else "hold"
    workflow_alignment = _check_workflow_alignment(repo_root, gap_reports)
    uat_report_refs = _write_uat_reports(out_dir, gap_reports, source_version)
    if workflow_alignment["findings"]:
        overall_status = "hold"

    report = {
        "schema_version": "HATE/v1",
        "record_type": "gap-closure-report",
        "source_version": source_version or "unknown",
        "overall_status": overall_status,
        "summary": {
            "gap_count": len(GAP_IDS),
            "checker_ready_count": checker_ready_count,
            "implemented_count": implemented_count,
            "hold_count": hold_count,
            "fixture_ref_count": len(fixture_refs),
            "behavior_checked_count": sum(item["behavior_checked_count"] for item in gap_reports),
            "uat_report_count": len(uat_report_refs),
            "missing_required_doc_count": len(missing_required_docs),
            "workflow_alignment_status": workflow_alignment["status"],
        },
        "findings": hard_findings,
        "workflow_alignment": workflow_alignment,
        "uat_reports": uat_report_refs,
        "gaps": gap_reports,
    }
    _write_report(out_dir, report)
    return report


def _implementation_evidence_for(repo_root: Path, gap_id: str) -> dict[str, Any] | None:
    evidence = IMPLEMENTED_GAP_EVIDENCE.get(gap_id)
    if not evidence:
        return None
    paths = [str(evidence["runtime_module"]), str(evidence["contract"])]
    paths.extend(str(path) for path in evidence["tests"])
    paths.extend(str(path) for path in evidence["fixtures"])
    if all((repo_root / path).is_file() for path in paths):
        return evidence
    return None


def _empty_report(
    source_version: str | None,
    missing_required_docs: list[str],
    missing_ledgers: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": "HATE/v1",
        "record_type": "gap-closure-report",
        "source_version": source_version or "unknown",
        "overall_status": "hold",
        "summary": {
            "gap_count": len(GAP_IDS),
            "checker_ready_count": 0,
            "implemented_count": 0,
            "hold_count": len(GAP_IDS),
            "fixture_ref_count": 0,
            "behavior_checked_count": 0,
            "uat_report_count": 0,
            "missing_required_doc_count": len(missing_required_docs),
            "workflow_alignment_status": "hold",
        },
        "findings": [
            _finding("required_contract_missing", "global", f"Required contract missing: {name}")
            for name in missing_required_docs
        ] + [
            _finding("required_ledger_missing", "global", f"Required ledger missing: {path}")
            for path in missing_ledgers
        ],
        "gaps": [],
        "workflow_alignment": {
            "status": "hold",
            "findings": [
                _finding("gap_closure_packet_ledger_missing", "global", "Packet ledger is required before workflow alignment.")
            ],
        },
        "uat_reports": [],
    }


def _extract_fixture_refs(packet_text: str, repo_root: Path) -> list[GapFixtureRef]:
    refs: list[GapFixtureRef] = []
    for line in packet_text.splitlines():
        gap_match = re.search(r"\|\s*(HATE-GAP-\d{3})\s*\|", line)
        if not gap_match:
            continue
        gap_id = gap_match.group(1)
        paths = re.findall(r"`(fixtures/[^`]+/fixture\.json)`", line)
        for path in paths:
            case_kind = "unknown"
            full_path = repo_root / path
            if full_path.is_file():
                try:
                    case_kind = json.loads(full_path.read_text(encoding="utf-8")).get("case_kind", "unknown")
                except json.JSONDecodeError:
                    case_kind = "invalid_json"
            refs.append(GapFixtureRef(gap_id=gap_id, path=path, case_kind=case_kind))
    return refs


def _invalid_fixture_payloads(
    repo_root: Path,
    refs: list[GapFixtureRef],
    gap_id: str,
    task_id: str,
    acceptance_id: str,
) -> list[str]:
    invalid: list[str] = []
    for ref in refs:
        path = repo_root / ref.path
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            invalid.append(f"{ref.path}: invalid JSON: {exc}")
            continue

        if payload.get("gap_id") != gap_id:
            invalid.append(f"{ref.path}: gap_id mismatch")
        if payload.get("task_seed_id") != task_id:
            invalid.append(f"{ref.path}: task_seed_id mismatch")
        if payload.get("acceptance_id") != acceptance_id:
            invalid.append(f"{ref.path}: acceptance_id mismatch")
        if payload.get("case_kind") not in {"positive", "negative"}:
            invalid.append(f"{ref.path}: invalid case_kind")
        expected = payload.get("expected", {})
        if expected.get("status") not in {"pass", "hold"}:
            invalid.append(f"{ref.path}: invalid expected.status")
        if not str(expected.get("uat_report", "")).endswith(".json"):
            invalid.append(f"{ref.path}: missing expected.uat_report")
        if payload.get("case_kind") == "negative" and not expected.get("finding_code"):
            invalid.append(f"{ref.path}: negative fixture missing finding_code")
    return invalid


def _evaluate_fixture_behaviors(repo_root: Path, refs: list[GapFixtureRef]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for ref in refs:
        path = repo_root / ref.path
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        expected = payload.get("expected", {})
        actual = _evaluate_fixture(payload)
        expected_code = expected.get("finding_code")
        actual_code = actual.get("finding_code")
        matches = actual.get("status") == expected.get("status")
        if expected.get("status") == "hold":
            matches = matches and actual_code == expected_code

        results.append({
            "fixture_path": ref.path,
            "expected_status": expected.get("status"),
            "actual_status": actual.get("status"),
            "expected_finding_code": expected_code,
            "actual_finding_code": actual_code,
            "matches_expected": matches,
            "uat_report": expected.get("uat_report"),
            "acceptance_id": payload.get("acceptance_id"),
            "task_seed_id": payload.get("task_seed_id"),
            "packet_id": payload.get("packet_id"),
        })
    return results


def _write_uat_reports(
    out_dir: Path,
    gap_reports: list[dict[str, Any]],
    source_version: str | None,
) -> list[str]:
    report_dir = out_dir / "uat-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    uat_reports: dict[str, dict[str, Any]] = {}

    for gap in gap_reports:
        for report_name in gap["uat_reports"]:
            uat = uat_reports.setdefault(
                report_name,
                {
                    "schema_version": "HATE/v1",
                    "record_type": "gap-closure-uat-report",
                    "report_id": Path(report_name).stem,
                    "source_version": source_version or "unknown",
                    "status": "uat_ready",
                    "decision": "hold_until_implemented",
                    "readiness_effect": "hold",
                    "gap_ids": [],
                    "task_seed_ids": [],
                    "acceptance_ids": [],
                    "fixture_refs": [],
                    "behavior_checked_count": 0,
                    "findings": [],
                    "sourceRefs": [],
                },
            )
            uat["gap_ids"].append(gap["gap_id"])
            uat["task_seed_ids"].append(gap["task_seed_id"])
            uat["acceptance_ids"].append(gap["acceptance_id"])
            uat["fixture_refs"].extend(gap["fixture_refs"])
            uat["behavior_checked_count"] += gap["behavior_checked_count"]
            uat["findings"].extend(gap["findings"])
            if gap["status"] == "implemented":
                uat["status"] = "implemented"
                uat["decision"] = "awaiting_acceptance"
                uat["readiness_effect"] = "none"

    written: list[str] = []
    for report_name, report in sorted(uat_reports.items()):
        report["gap_ids"] = sorted(set(report["gap_ids"]))
        report["task_seed_ids"] = sorted(set(report["task_seed_ids"]))
        report["acceptance_ids"] = sorted(set(report["acceptance_ids"]))
        report["fixture_refs"] = sorted(set(report["fixture_refs"]))
        report["sourceRefs"] = report["fixture_refs"]
        if report["findings"]:
            report["status"] = "hold"
            report["decision"] = "fix_findings_before_implementation"
            report["readiness_effect"] = "hold"
        path = report_dir / report_name
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(str(path.relative_to(out_dir)).replace("\\", "/"))

    return written


def _check_workflow_alignment(repo_root: Path, gap_reports: list[dict[str, Any]]) -> dict[str, Any]:
    checks = [
        _check_task_seed_sync(repo_root, gap_reports),
        _check_acceptance_records(repo_root, gap_reports),
        check_acceptance_index(repo_root, gap_reports),
        _check_completion_trace(repo_root, gap_reports),
        _check_birdseye_index(repo_root),
        _check_evidence_fixture_fields(repo_root),
        _check_coverage_policy(repo_root),
        check_priority_score_policy(repo_root),
        check_metrics_kpi_policy(repo_root),
        check_feature_detection_policy(repo_root),
        check_security_release_evidence_policy(repo_root),
    ]
    findings = [finding for check in checks for finding in check["findings"]]
    return {
        "status": "uat_ready" if not findings else "hold",
        "checks": checks,
        "findings": findings,
    }


def _check_task_seed_sync(repo_root: Path, gap_reports: list[dict[str, Any]]) -> dict[str, Any]:
    task_seed_path = repo_root / "docs" / "tasks" / "HATE_GAP_CLOSURE_TASK_SEEDS.md"
    findings: list[dict[str, str]] = []
    rows: dict[str, dict[str, str]] = {}

    if not task_seed_path.is_file():
        return {
            "check_id": "workflow_task_seed_sync",
            "status": "hold",
            "task_seed_count": 0,
            "findings": [_finding("task_seed_ledger_missing", "global", "Task Seed ledger is missing.")],
        }

    for line in task_seed_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| TASK-HATE-GAP-"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 7:
            findings.append(_finding("task_seed_row_malformed", "global", f"Malformed Task Seed row: {line}"))
            continue
        task_id, gap_id, packet_id, objective, scope_in, scope_out, acceptance_id = cells
        rows[gap_id] = {
            "task_id": task_id,
            "packet_id": packet_id,
            "objective": objective,
            "scope_in": scope_in,
            "scope_out": scope_out,
            "acceptance_id": acceptance_id,
        }

    for gap in gap_reports:
        row = rows.get(gap["gap_id"])
        if not row:
            findings.append(_finding("task_seed_row_missing", gap["gap_id"], "Gap has no Task Seed ledger row."))
            continue
        if row["task_id"] != gap["task_seed_id"]:
            findings.append(_finding("task_seed_id_mismatch", gap["gap_id"], "Task Seed ID does not match gap report."))
        if row["acceptance_id"] != gap["acceptance_id"]:
            findings.append(_finding("task_seed_acceptance_mismatch", gap["gap_id"], "Acceptance ID does not match gap report."))
        if not row["packet_id"].startswith("HATE-PKT-"):
            findings.append(_finding("task_seed_packet_missing", gap["gap_id"], "Packet ID is not canonical."))
        for field in ("objective", "scope_in", "scope_out"):
            if not row[field]:
                findings.append(_finding("task_seed_scope_field_missing", gap["gap_id"], f"Task Seed {field} is empty."))

    return {
        "check_id": "workflow_task_seed_sync",
        "status": "pass" if not findings else "hold",
        "task_seed_count": len(rows),
        "findings": findings,
    }


def _check_acceptance_records(repo_root: Path, gap_reports: list[dict[str, Any]]) -> dict[str, Any]:
    acceptance_dir = repo_root / "docs" / "acceptance"
    acceptance_files = sorted(acceptance_dir.glob("AC-*.md")) if acceptance_dir.is_dir() else []
    text_by_file = {
        path.name: path.read_text(encoding="utf-8")
        for path in acceptance_files
    }
    all_text = "\n".join(text_by_file.values())
    required_headings = [
        "## Scope",
        "## Acceptance Criteria",
        "## Evidence",
        "## Verification Result",
    ]
    findings: list[dict[str, str]] = []

    for gap in gap_reports:
        if gap["acceptance_id"] not in all_text:
            findings.append(_finding(
                "acceptance_record_missing",
                gap["gap_id"],
                f"{gap['acceptance_id']} is not referenced by an AC-YYYYMMDD-xx.md record.",
            ))

    for name, text in text_by_file.items():
        if not text.startswith("---"):
            findings.append(_finding("acceptance_front_matter_missing", "global", f"{name} lacks front matter."))
        for heading in required_headings:
            if heading not in text:
                findings.append(_finding("acceptance_heading_missing", "global", f"{name} lacks {heading}."))

    return {
        "check_id": "workflow_acceptance_records",
        "status": "pass" if not findings else "hold",
        "record_count": len(acceptance_files),
        "findings": findings,
    }


def _check_completion_trace(repo_root: Path, gap_reports: list[dict[str, Any]]) -> dict[str, Any]:
    acceptance_path = repo_root / "docs" / "acceptance" / "HATE_GAP_CLOSURE_ACCEPTANCE.md"
    text = acceptance_path.read_text(encoding="utf-8") if acceptance_path.is_file() else ""
    findings: list[dict[str, str]] = []

    for gap in gap_reports:
        expected_state = "implemented" if gap["implementation_evidence"] else "uat_ready"
        decision = "awaiting acceptance" if expected_state == "implemented" else "hold until implemented"
        row_pattern = re.compile(
            rf"\|\s*{re.escape(gap['acceptance_id'])}\s*\|\s*{re.escape(gap['gap_id'])}\s*\|"
            rf".*?\|\s*{expected_state}\s*\|\s*{decision}\s*\|"
        )
        if not row_pattern.search(text):
            findings.append(_finding(
                "completion_trace_state_mismatch",
                gap["gap_id"],
                f"{gap['acceptance_id']} must be {expected_state} with decision '{decision}'.",
            ))
        if gap["status"] == "implemented" and not gap["implementation_evidence"]:
            findings.append(_finding(
                "implemented_without_evidence",
                gap["gap_id"],
                "Implemented status requires runtime module, tests, fixtures, and contract evidence.",
            ))
        if gap["status"] != "implemented" and re.search(
            rf"\|\s*{re.escape(gap['acceptance_id'])}\s*\|\s*{re.escape(gap['gap_id'])}\s*\|.*?\|\s*accepted\s*\|",
            text,
        ):
            findings.append(_finding(
                "acceptance_overclaim_detected",
                gap["gap_id"],
                "Acceptance ledger must not mark an unimplemented gap as accepted.",
            ))

    return {
        "check_id": "workflow_completion_trace",
        "status": "pass" if not findings else "hold",
        "implemented_trace_count": sum(1 for gap in gap_reports if gap["implementation_evidence"]),
        "findings": findings,
    }


def _check_birdseye_index(repo_root: Path) -> dict[str, Any]:
    index_path = repo_root / "docs" / "birdseye" / "index.json"
    findings: list[dict[str, str]] = []
    node_count = 0
    if not index_path.is_file():
        findings.append(_finding("birdseye_index_missing", "global", "docs/birdseye/index.json is missing."))
    else:
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            findings.append(_finding("birdseye_index_malformed", "global", f"index.json is malformed: {exc}"))
            index = {}
        nodes = index.get("nodes", {})
        node_count = len(nodes)
        for node_id, node in nodes.items():
            caps = node.get("caps")
            if caps and not (repo_root / caps).is_file():
                findings.append(_finding("birdseye_caps_missing", "global", f"{node_id} caps missing: {caps}"))

    return {
        "check_id": "workflow_birdseye_invariants",
        "status": "pass" if not findings else "hold",
        "node_count": node_count,
        "findings": findings,
    }


def _check_evidence_fixture_fields(repo_root: Path) -> dict[str, Any]:
    fixture_dir = repo_root / "fixtures" / "workflow" / "evidence"
    findings: list[dict[str, str]] = []
    required = {
        "evidence_id",
        "source_tool",
        "command_or_action",
        "artifact_refs",
        "hashes",
        "decision_or_status",
        "timestamp",
        "sourceRefs",
    }
    for path in sorted(fixture_dir.glob("*/fixture.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        evidence = payload.get("input", {}).get("evidence", {})
        missing = sorted(required - set(evidence))
        if missing and payload.get("case_kind") == "positive":
            findings.append(_finding(
                "evidence_minimum_fields_missing",
                payload.get("gap_id", "global"),
                f"{path.relative_to(repo_root)} missing {', '.join(missing)}",
            ))

    return {
        "check_id": "workflow_evidence_minimum_fields",
        "status": "pass" if not findings else "hold",
        "findings": findings,
    }


def _check_coverage_policy(repo_root: Path) -> dict[str, Any]:
    task_seed_path = repo_root / "docs" / "tasks" / "HATE_GAP_CLOSURE_TASK_SEEDS.md"
    findings: list[dict[str, str]] = []
    text = task_seed_path.read_text(encoding="utf-8") if task_seed_path.is_file() else ""
    if "--cov-fail-under=80" not in text:
        findings.append(_finding(
            "coverage_gate_missing",
            "global",
            "Task Seed verification commands must include pytest coverage fail-under 80.",
        ))
    return {
        "check_id": "workflow_coverage_policy",
        "status": "pass" if not findings else "hold",
        "findings": findings,
    }


def _evaluate_fixture(payload: dict[str, Any]) -> dict[str, str]:
    gap_id = payload.get("gap_id")
    data = payload.get("input", {})
    status = "pass"
    finding_code = ""

    if gap_id == "HATE-GAP-001":
        worker_report = evaluate_worker_runtime_fixture(payload)
        status = worker_report["status"]
        finding_code = worker_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-002":
        tenant_report = evaluate_tenant_isolation_fixture(payload)
        status = tenant_report["status"]
        finding_code = tenant_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-003":
        rate_limit_report = evaluate_api_rate_limit_fixture(payload)
        status = rate_limit_report["status"]
        finding_code = rate_limit_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-004":
        entitlement_report = evaluate_entitlement_fixture(payload)
        status = entitlement_report["status"]
        finding_code = entitlement_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-005":
        github_report = evaluate_github_integration_fixture(payload)
        status = github_report["status"]
        finding_code = github_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-006":
        store_report = evaluate_store_migration_fixture(payload)
        status = store_report["status"]
        finding_code = store_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-007":
        corpus_report = evaluate_adapter_corpus_fixture(payload)
        status = corpus_report["status"]
        finding_code = corpus_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-008":
        dashboard_report = evaluate_dashboard_state_fixture(payload)
        status = dashboard_report["status"]
        finding_code = dashboard_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-009":
        api_report = evaluate_api_contract_fixture(payload)
        status = api_report["status"]
        finding_code = api_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-010":
        observability_report = evaluate_observability_fixture(payload)
        status = observability_report["status"]
        finding_code = observability_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-011":
        diagnostics_report = evaluate_support_diagnostics_fixture(payload)
        status = diagnostics_report["status"]
        finding_code = diagnostics_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-012":
        real_repo_report = evaluate_real_repo_fixture(payload)
        status = real_repo_report["status"]
        finding_code = real_repo_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-013":
        agent_quality_report = evaluate_agent_quality_fixture(payload)
        status = agent_quality_report["status"]
        finding_code = agent_quality_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-014":
        adapter_family_report = evaluate_adapter_family_fixture(payload)
        status = adapter_family_report["status"]
        finding_code = adapter_family_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-015":
        enterprise_control_report = evaluate_enterprise_control_fixture(payload)
        status = enterprise_control_report["status"]
        finding_code = enterprise_control_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-016":
        artifact_lifecycle_report = evaluate_artifact_lifecycle_fixture(payload)
        status = artifact_lifecycle_report["status"]
        finding_code = artifact_lifecycle_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-017":
        deployment_topology_report = evaluate_deployment_topology_fixture(payload)
        status = deployment_topology_report["status"]
        finding_code = deployment_topology_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-018":
        benchmark_report = evaluate_benchmark_catalog_fixture(payload)
        status = benchmark_report["status"]
        finding_code = benchmark_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-019":
        release_channel_report = evaluate_release_channel_fixture(payload)
        status = release_channel_report["status"]
        finding_code = release_channel_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-020":
        product_e2e_report = evaluate_product_e2e_fixture(payload)
        status = product_e2e_report["status"]
        finding_code = product_e2e_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-021":
        task_seed_report = evaluate_task_seed_fixture(payload)
        status = task_seed_report["status"]
        finding_code = task_seed_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-022":
        acceptance_report = evaluate_acceptance_fixture(payload)
        status = acceptance_report["status"]
        finding_code = acceptance_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-023":
        evidence_report = evaluate_evidence_fixture(payload)
        status = evidence_report["status"]
        finding_code = evidence_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-024":
        birdseye_report = evaluate_birdseye_fixture(payload)
        status = birdseye_report["status"]
        finding_code = birdseye_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-025":
        plugin_report = evaluate_workflow_plugin_fixture(payload)
        status = plugin_report["status"]
        finding_code = plugin_report.get("finding_code", "")
    elif gap_id == "HATE-GAP-026":
        completion_report = evaluate_completion_fixture(payload)
        status = completion_report["status"]
        finding_code = completion_report.get("finding_code", "")

    result = {"status": status, "readiness_effect": "none" if status == "pass" else "hold"}
    if finding_code:
        result["finding_code"] = finding_code
    return result


def _finding(code: str, gap_id: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "gap_id": gap_id,
        "severity": "high",
        "message": message,
    }


def _write_report(out_dir: Path, report: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "gap-closure-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
