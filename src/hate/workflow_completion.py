"""Workflow-cookbook completion governance evaluation for HATE-GAP-026."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ALLOWED_CLAIMS = {"specified", "implemented", "accepted", "product-ready"}


@dataclass(frozen=True)
class CompletionFinding:
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


def evaluate_completion_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_completion_governance_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "workflow-completion-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_completion_governance_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "workflow-completion-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["workflow-completion"])
    claim = _normalize_claim(input_data.get("completion_claim", input_data))
    findings = _findings_for(claim, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "workflow-completion-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "completion_claim": claim,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "claim": claim["claim"],
            "evidence_ref_count": len(claim["evidence_refs"]),
            "blocking_gap_count": len(claim["blocking_gaps"]),
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_claim(raw_claim: dict[str, Any]) -> dict[str, Any]:
    claim = dict(raw_claim or {})
    return {
        "claim": str(claim.get("claim") or ""),
        "scope": str(claim.get("scope") or ""),
        "evidence_refs": list(claim.get("evidence_refs") or []),
        "code_schema_fixtures_tests_docs_exist": bool(claim.get("code_schema_fixtures_tests_docs_exist", False)),
        "tests_pass": bool(claim.get("tests_pass", False)),
        "acceptance_record_approved": bool(claim.get("acceptance_record_approved", False)),
        "product_gates_pass": bool(claim.get("product_gates_pass", False)),
        "blocking_gaps": list(claim.get("blocking_gaps") or []),
        "done_task_missing_acceptance": bool(claim.get("done_task_missing_acceptance", False)),
        "stale_completion_record": bool(claim.get("stale_completion_record", False)),
        "release_evidence_matches": bool(claim.get("release_evidence_matches", True)),
        "scope_broader_than_verification": bool(claim.get("scope_broader_than_verification", False)),
        "generated_artifact_changed_without_birdseye_refresh": bool(
            claim.get("generated_artifact_changed_without_birdseye_refresh", False)
        ),
    }


def _findings_for(claim: dict[str, Any], source_ref: str) -> list[CompletionFinding]:
    findings: list[CompletionFinding] = []
    claim_kind = claim["claim"]
    if claim_kind not in ALLOWED_CLAIMS:
        findings.append(_finding(
            "completion_claim_unknown",
            "Completion claim must use the workflow-cookbook allowed taxonomy.",
            source_ref,
        ))
    if not claim["scope"] or not claim["evidence_refs"]:
        findings.append(_finding(
            "completion_claim_missing_scope_or_evidence",
            "Completion claim must name scope and evidence references.",
            source_ref,
        ))
    if claim_kind == "implemented" and not (
        claim["code_schema_fixtures_tests_docs_exist"] and claim["tests_pass"]
    ):
        findings.append(_finding(
            "completion_implemented_without_artifacts",
            "Implemented claim requires code, schema, fixtures, tests, docs, and passing verification.",
            source_ref,
        ))
    if claim_kind == "accepted" and not claim["acceptance_record_approved"]:
        findings.append(_finding(
            "completion_accepted_without_record",
            "Accepted claim requires an approved acceptance record for the stated scope.",
            source_ref,
        ))
    if claim_kind == "product-ready" and not _product_ready_supported(claim):
        findings.append(_finding(
            "completion_overclaim_detected",
            "Product-ready claim requires all product gates, accepted scope, release evidence, Birdseye freshness, and no blocking gaps.",
            source_ref,
        ))
    if claim["done_task_missing_acceptance"]:
        findings.append(_finding(
            "completion_done_task_missing_acceptance",
            "Done task cannot support completion without linked acceptance.",
            source_ref,
        ))
    if claim["stale_completion_record"]:
        findings.append(_finding(
            "completion_record_stale",
            "Completion record is stale and cannot support current scope.",
            source_ref,
        ))
    if not claim["release_evidence_matches"]:
        findings.append(_finding(
            "completion_release_evidence_mismatch",
            "Release evidence does not match the completion claim.",
            source_ref,
        ))
    if claim["scope_broader_than_verification"]:
        findings.append(_finding(
            "completion_scope_broader_than_verification",
            "Completion scope is broader than the verified evidence.",
            source_ref,
        ))
    if claim["generated_artifact_changed_without_birdseye_refresh"]:
        findings.append(_finding(
            "completion_generated_artifact_without_birdseye_refresh",
            "Generated artifact changed without Birdseye refresh.",
            source_ref,
        ))
    return findings


def _product_ready_supported(claim: dict[str, Any]) -> bool:
    return (
        claim["product_gates_pass"]
        and claim["acceptance_record_approved"]
        and claim["release_evidence_matches"]
        and not claim["blocking_gaps"]
        and not claim["scope_broader_than_verification"]
        and not claim["generated_artifact_changed_without_birdseye_refresh"]
        and not claim["stale_completion_record"]
        and not claim["done_task_missing_acceptance"]
    )


def _finding(code: str, message: str, source_ref: str) -> CompletionFinding:
    return CompletionFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
