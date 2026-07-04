from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .common import productization_envelope


@dataclass(frozen=True)
class DocsFreshnessFinding:
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


def evaluate_docs_freshness_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_docs_freshness_ci_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "docs-freshness-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_docs_freshness_ci_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "docs-freshness-ci-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["docs-freshness"])
    freshness = _normalize_freshness(input_data.get("freshness", input_data))
    exceptions = _normalize_exceptions(input_data.get("exceptions", []))
    findings = _findings_for(freshness, exceptions, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "docs-freshness-ci-report",
        "report_id": report_id,
        **productization_envelope(input_data, report_id=report_id, source_refs=source_refs),
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "freshness": freshness,
        "exceptions": exceptions,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "required_check_count": 5,
            "finding_count": len(findings),
            "exception_count": len(exceptions),
            "stale_readme": not freshness["readme_state_current"],
            "missing_acceptance_count": len(freshness["missing_acceptance_refs"]),
            "schema_registry_stale": not freshness["schema_registry_current"],
            "codemap_stale": not freshness["codemap_current"],
            "product_ready_overclaim": freshness["product_ready_claim"] and not freshness["product_ready_evidence_present"],
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_freshness(raw: dict[str, Any]) -> dict[str, Any]:
    data = dict(raw or {})
    return {
        "readme_state_current": bool(data.get("readme_state_current", True)),
        "readme_expected_test_count": int(data.get("readme_expected_test_count", 0) or 0),
        "readme_observed_test_count": int(data.get("readme_observed_test_count", 0) or 0),
        "acceptance_refs": [str(item) for item in data.get("acceptance_refs", [])],
        "missing_acceptance_refs": [str(item) for item in data.get("missing_acceptance_refs", [])],
        "codemap_current": bool(data.get("codemap_current", True)),
        "codemap_caps_missing": [str(item) for item in data.get("codemap_caps_missing", [])],
        "schema_registry_current": bool(data.get("schema_registry_current", True)),
        "missing_schema_refs": [str(item) for item in data.get("missing_schema_refs", [])],
        "product_ready_claim": bool(data.get("product_ready_claim", False)),
        "product_ready_evidence_present": bool(data.get("product_ready_evidence_present", False)),
        "emergency_exception": bool(data.get("emergency_exception", False)),
    }


def _normalize_exceptions(raw: list[dict[str, Any]]) -> list[dict[str, str]]:
    exceptions = []
    for item in raw or []:
        exception = dict(item)
        exceptions.append({
            "owner": str(exception.get("owner") or ""),
            "reason": str(exception.get("reason") or ""),
            "expiry": str(exception.get("expiry") or ""),
            "acceptance_ref": str(exception.get("acceptance_ref") or ""),
        })
    return exceptions


def _findings_for(
    freshness: dict[str, Any],
    exceptions: list[dict[str, str]],
    source_ref: str,
) -> list[DocsFreshnessFinding]:
    findings: list[DocsFreshnessFinding] = []
    if not freshness["readme_state_current"] or _readme_count_mismatch(freshness):
        findings.append(_finding(
            "docs_readme_state_stale",
            "README state or test-count claim is stale.",
            source_ref,
        ))
    if freshness["missing_acceptance_refs"]:
        findings.append(_finding(
            "docs_acceptance_record_missing",
            "Product-grade or checklist references missing acceptance records.",
            source_ref,
        ))
    if not freshness["codemap_current"] or freshness["codemap_caps_missing"]:
        findings.append(_finding(
            "docs_codemap_stale",
            "Codemap or Birdseye caps are stale or incomplete.",
            source_ref,
        ))
    if not freshness["schema_registry_current"] or freshness["missing_schema_refs"]:
        findings.append(_finding(
            "docs_schema_registry_stale",
            "Schema registry references are stale or missing.",
            source_ref,
        ))
    if freshness["product_ready_claim"] and not freshness["product_ready_evidence_present"]:
        findings.append(_finding(
            "docs_product_ready_overclaim",
            "Product-ready claim lacks release authority and evidence.",
            source_ref,
        ))
    if freshness["emergency_exception"] and not _has_valid_exception(exceptions):
        findings.append(_finding(
            "docs_freshness_exception_invalid",
            "Emergency freshness exception requires owner, reason, expiry, and acceptance_ref.",
            source_ref,
        ))
    return findings


def _readme_count_mismatch(freshness: dict[str, Any]) -> bool:
    expected = freshness["readme_expected_test_count"]
    observed = freshness["readme_observed_test_count"]
    return expected > 0 and observed > 0 and expected != observed


def _has_valid_exception(exceptions: list[dict[str, str]]) -> bool:
    return any(all(item.get(field) for field in ("owner", "reason", "expiry", "acceptance_ref")) for item in exceptions)


def _finding(code: str, message: str, source_ref: str) -> DocsFreshnessFinding:
    return DocsFreshnessFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
