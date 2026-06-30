"""API contract report evaluation for HATE-GAP-009."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


RESOURCE_BY_ENDPOINT = {
    "/v1/evidence": "evidence",
    "/v1/artifacts": "artifacts",
    "/v1/runs": "runs",
    "/v1/risks": "risks",
    "/v1/doctor-findings": "doctor_findings",
    "/v1/risk-debt": "risk_debt",
}


@dataclass(frozen=True)
class APIContractFinding:
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


def evaluate_api_contract_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_api_contract_report(input_data, source_refs=[payload.get("fixture_id", "fixture")])
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_api_contract_report(
    input_data: dict[str, Any],
    *,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    endpoint = str(input_data.get("endpoint") or "")
    resource = RESOURCE_BY_ENDPOINT.get(endpoint, "unknown")
    pagination = _normalize_pagination(input_data.get("pagination"))
    authz = str(input_data.get("authz") or "allowed")
    findings = _findings_for(input_data, endpoint, resource, pagination, authz)
    status = "hold" if findings else "pass"

    return {
        "schema_version": "HATE/v1",
        "record_type": "api-contract-report",
        "report_id": str(input_data.get("report_id") or "api-contract-report"),
        "endpoint": endpoint,
        "resource": resource,
        "request_contract": {
            "pagination": pagination,
            "filters": input_data.get("filters", {}),
            "sort": input_data.get("sort"),
            "authz": authz,
        },
        "response_contract": {
            "envelope_required": True,
            "source_required": True,
            "staleness_required": True,
            "pagination_required": bool(pagination),
            "redacted_denial_required": authz == "denied",
        },
        "findings": [finding.to_dict() for finding in findings],
        "status": status,
        "readiness_effect": "hold" if findings else "none",
        "sourceRefs": sorted(set((source_refs or []) + [f"api-contract:{endpoint or 'unknown'}"])),
    }


def _findings_for(
    input_data: dict[str, Any],
    endpoint: str,
    resource: str,
    pagination: dict[str, Any] | None,
    authz: str,
) -> list[APIContractFinding]:
    findings: list[APIContractFinding] = []
    source_ref = f"api-contract:{endpoint or 'unknown'}"

    if resource == "unknown":
        findings.append(APIContractFinding(
            code="api_endpoint_unknown",
            severity="high",
            message=f"Endpoint is not part of the supported read model contract: {endpoint}",
            sourceRef=source_ref,
        ))

    if input_data.get("requires_pagination", bool(pagination)) and not pagination:
        findings.append(APIContractFinding(
            code="api_pagination_missing",
            severity="high",
            message="List endpoint must expose cursor pagination metadata.",
            sourceRef=source_ref,
        ))

    if pagination:
        limit = pagination.get("limit")
        cursor = str(pagination.get("cursor") or "")
        if not isinstance(limit, int) or limit < 1 or limit > 1000:
            findings.append(APIContractFinding(
                code="api_pagination_invalid",
                severity="high",
                message="Pagination limit must be between 1 and 1000.",
                sourceRef=source_ref,
            ))
        if cursor and not _valid_cursor(cursor):
            findings.append(APIContractFinding(
                code="api_pagination_invalid",
                severity="high",
                message="Pagination cursor must be opaque and stable.",
                sourceRef=source_ref,
            ))

    if authz == "denied" and input_data.get("raw_path_requested"):
        findings.append(APIContractFinding(
            code="api_authz_leak_denied",
            severity="critical",
            message="Unauthorized API response must not expose raw artifact paths or restricted details.",
            sourceRef=source_ref,
        ))

    if authz == "denied" and input_data.get("tenant_existence_visible"):
        findings.append(APIContractFinding(
            code="api_authz_tenant_leak_denied",
            severity="critical",
            message="Unauthorized API response must not reveal tenant existence.",
            sourceRef=source_ref,
        ))

    if input_data.get("staleness") == "fresh" and input_data.get("source_bundle_stale"):
        findings.append(APIContractFinding(
            code="api_stale_read_model_marked_fresh",
            severity="high",
            message="Stale read model cannot be returned as fresh.",
            sourceRef=source_ref,
        ))

    if input_data.get("envelope_required", True) and input_data.get("envelope") == "missing":
        findings.append(APIContractFinding(
            code="api_response_envelope_missing",
            severity="high",
            message="API response must use the canonical response envelope.",
            sourceRef=source_ref,
        ))

    return findings


def _normalize_pagination(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    return {
        "limit": raw.get("limit"),
        "cursor": raw.get("cursor"),
        "next_cursor": raw.get("next_cursor"),
    }


def _valid_cursor(cursor: str) -> bool:
    if cursor.startswith("cur_"):
        return True
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=-_"
    return all(char in allowed for char in cursor)
