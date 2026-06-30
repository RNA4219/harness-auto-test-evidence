from __future__ import annotations

from pathlib import Path
from typing import Any


def check_acceptance_index(repo_root: Path, gap_reports: list[dict[str, Any]]) -> dict[str, Any]:
    index_path = repo_root / "docs" / "acceptance" / "INDEX.md"
    findings: list[dict[str, str]] = []
    text = index_path.read_text(encoding="utf-8") if index_path.is_file() else ""

    if not index_path.is_file():
        findings.append(_finding("acceptance_index_missing", "global", "docs/acceptance/INDEX.md is missing."))
    for gap in gap_reports:
        if gap["acceptance_id"] not in text:
            findings.append(_finding(
                "acceptance_index_entry_missing",
                gap["gap_id"],
                f"{gap['acceptance_id']} is missing from docs/acceptance/INDEX.md.",
            ))
    if "AC-20260630-01.md" not in text:
        findings.append(_finding(
            "acceptance_index_record_link_missing",
            "global",
            "Acceptance index must link the human-readable AC record.",
        ))

    return {
        "check_id": "workflow_acceptance_index",
        "status": "pass" if not findings else "hold",
        "findings": findings,
    }


def check_priority_score_policy(repo_root: Path) -> dict[str, Any]:
    contract_path = repo_root / "docs" / "process" / "WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md"
    acceptance_path = repo_root / "docs" / "acceptance" / "AC-20260630-01.md"
    text = _read_existing_text(contract_path, acceptance_path)
    findings: list[dict[str, str]] = []

    for term in ["Priority Score", "priority_score", "rationale"]:
        if term not in text:
            findings.append(_finding(
                "priority_score_policy_missing",
                "global",
                f"Workflow contract must preserve workflow-cookbook PR Priority Score policy: missing {term}.",
            ))

    return {
        "check_id": "workflow_priority_score_policy",
        "status": "pass" if not findings else "hold",
        "findings": findings,
    }


def check_metrics_kpi_policy(repo_root: Path) -> dict[str, Any]:
    contract_path = repo_root / "docs" / "process" / "WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md"
    text = _read_existing_text(contract_path)
    findings: list[dict[str, str]] = []

    for term in [
        ".ga/qa-metrics.json",
        "spec_completeness",
        "birdseye_refresh_delay_minutes",
        "review_latency",
        "check_metrics_thresholds.py",
    ]:
        if term not in text:
            findings.append(_finding("metrics_kpi_policy_missing", "global", f"Workflow KPI policy is missing {term}."))

    return {
        "check_id": "workflow_metrics_kpi_policy",
        "status": "pass" if not findings else "hold",
        "findings": findings,
    }


def check_feature_detection_policy(repo_root: Path) -> dict[str, Any]:
    contract_path = repo_root / "docs" / "process" / "WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md"
    text = _read_existing_text(contract_path)
    findings: list[dict[str, str]] = []

    for term in ["feature detection", "governance/predictor.yaml", ".ga/qa-metrics.json"]:
        if term not in text:
            findings.append(_finding(
                "feature_detection_policy_missing",
                "global",
                f"Workflow feature detection policy is missing {term}.",
            ))

    return {
        "check_id": "workflow_feature_detection_policy",
        "status": "pass" if not findings else "hold",
        "findings": findings,
    }


def check_security_release_evidence_policy(repo_root: Path) -> dict[str, Any]:
    contract_path = repo_root / "docs" / "process" / "WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md"
    text = _read_existing_text(contract_path)
    findings: list[dict[str, str]] = []

    for term in [
        "check_security_posture.py",
        "check_release_evidence.py",
        "security posture",
        "release evidence",
        "branch protection",
    ]:
        if term not in text:
            findings.append(_finding(
                "security_release_evidence_policy_missing",
                "global",
                f"Workflow security/release evidence policy is missing {term}.",
            ))

    return {
        "check_id": "workflow_security_release_evidence_policy",
        "status": "pass" if not findings else "hold",
        "findings": findings,
    }


def _read_existing_text(*paths: Path) -> str:
    parts = []
    for path in paths:
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _finding(code: str, gap_id: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "gap_id": gap_id,
        "severity": "high",
        "message": message,
    }
