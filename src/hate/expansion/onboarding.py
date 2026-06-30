"""Guided onboarding evaluation for HATE-GAP-027."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OnboardingFinding:
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


def evaluate_onboarding_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_onboarding_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "onboarding-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_onboarding_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "onboarding-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["onboarding"])
    onboarding_config = _normalize_onboarding_config(input_data.get("onboarding_config", input_data))
    findings = _findings_for(onboarding_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "onboarding-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "onboarding_config": onboarding_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "sample_repo_count": len(onboarding_config["sample_repos"]),
            "walkthrough_step_count": onboarding_config["walkthrough_step_count"],
            "tutorial_failure_contract": onboarding_config["tutorial_failure_contract"],
            "support_handoff_contract": onboarding_config["support_handoff_contract"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_onboarding_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    sample_repos = [str(repo) for repo in config.get("sample_repos", []) if str(repo)]
    return {
        "sample_repos": sample_repos,
        "walkthrough_step_count": int(config.get("walkthrough_step_count", 0) or 0),
        "tutorial_failure_contract": bool(config.get("tutorial_failure_contract", False)),
        "support_handoff_contract": bool(config.get("support_handoff_contract", False)),
        "expected_output_defined": bool(config.get("expected_output_defined", False)),
        "five_minute_path_valid": bool(config.get("five_minute_path_valid", False)),
        "versioned_sample_repo": bool(config.get("versioned_sample_repo", False)),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[OnboardingFinding]:
    findings: list[OnboardingFinding] = []
    if not config["sample_repos"]:
        findings.append(_finding(
            "onboarding_sample_repo_missing",
            "Guided onboarding requires at least one versioned sample repository.",
            source_ref,
        ))
    if config["walkthrough_step_count"] < 5:
        findings.append(_finding(
            "onboarding_walkthrough_insufficient",
            "Guided onboarding walkthrough must have at least five documented steps.",
            source_ref,
        ))
    if not config["tutorial_failure_contract"]:
        findings.append(_finding(
            "onboarding_parser_failure_tutorial_missing",
            "Guided onboarding requires a failure tutorial contract for parser failures.",
            source_ref,
        ))
    if not config["support_handoff_contract"]:
        findings.append(_finding(
            "onboarding_support_handoff_missing",
            "Guided onboarding requires a support handoff evidence contract.",
            source_ref,
        ))
    if not config["expected_output_defined"]:
        findings.append(_finding(
            "onboarding_expected_output_missing",
            "Guided onboarding requires defined expected output for sample walkthrough.",
            source_ref,
        ))
    if not config["five_minute_path_valid"]:
        findings.append(_finding(
            "onboarding_five_minute_path_invalid",
            "Five-minute onboarding path must be validated and documented.",
            source_ref,
        ))
    if config["sample_repos"] and not config["versioned_sample_repo"]:
        findings.append(_finding(
            "onboarding_sample_repo_not_versioned",
            "Sample repositories must be versioned and tracked.",
            source_ref,
        ))
    return findings


def _finding(code: str, message: str, source_ref: str) -> OnboardingFinding:
    return OnboardingFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )