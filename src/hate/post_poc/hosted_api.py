from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .common import apply_productization_contract_tree, productization_envelope


AUTH_METHODS = {"oidc", "api_token", "service_account"}
HOSTED_API_ROUTES = [
    {
        "operation_id": "platformRun",
        "method": "POST",
        "path": "/v1/platform/runs",
        "resource": "platform_run",
        "action": "write",
        "required_scope": "platform:run",
        "tenant_scoped": True,
        "audit_required": True,
        "rate_limited": True,
    },
    {
        "operation_id": "platformHistory",
        "method": "GET",
        "path": "/v1/platform/history",
        "resource": "platform_history",
        "action": "read",
        "required_scope": "platform:history:read",
        "tenant_scoped": True,
        "audit_required": True,
        "rate_limited": True,
    },
    {
        "operation_id": "platformFindings",
        "method": "GET",
        "path": "/v1/platform/findings",
        "resource": "finding_read_model",
        "action": "read",
        "required_scope": "platform:findings:read",
        "tenant_scoped": True,
        "audit_required": True,
        "rate_limited": True,
    },
    {
        "operation_id": "platformDebt",
        "method": "GET",
        "path": "/v1/platform/debt",
        "resource": "risk_debt_read_model",
        "action": "read",
        "required_scope": "platform:debt:read",
        "tenant_scoped": True,
        "audit_required": True,
        "rate_limited": True,
    },
    {
        "operation_id": "platformReviewDecision",
        "method": "POST",
        "path": "/v1/platform/review/decisions",
        "resource": "manual_review_decision",
        "action": "write",
        "required_scope": "platform:review:write",
        "tenant_scoped": True,
        "audit_required": True,
        "rate_limited": True,
    },
    {
        "operation_id": "platformPolicySimulation",
        "method": "POST",
        "path": "/v1/platform/policy/simulations",
        "resource": "policy_simulation",
        "action": "write",
        "required_scope": "platform:policy:simulate",
        "tenant_scoped": True,
        "audit_required": True,
        "rate_limited": True,
    },
    {
        "operation_id": "platformReport",
        "method": "GET",
        "path": "/v1/platform/reports/{report_id}",
        "resource": "safe_report_artifact",
        "action": "read",
        "required_scope": "platform:report:read",
        "tenant_scoped": True,
        "audit_required": True,
        "rate_limited": True,
    },
]


@dataclass(frozen=True)
class HostedApiFinding:
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


def evaluate_hosted_api_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    report = build_hosted_api_report(
        payload.get("input", {}),
        report_id=str(payload.get("fixture_id") or "hosted-api-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_hosted_api_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "hosted-api-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["hosted-api"])
    request = _normalize_request(input_data.get("request", input_data))
    authz = _authz_decision(request)
    rate_limit = _rate_limit_event(request)
    findings = _findings_for(request, authz, rate_limit, source_refs[0])
    status = "hold" if findings else "pass"
    report = {
        "schema_version": "HATE/v1",
        "record_type": "hosted-api-report",
        "report_id": report_id,
        **productization_envelope(input_data, report_id=report_id, source_refs=source_refs),
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "request_record": request,
        "authz_decision": authz,
        "rate_limit_event": rate_limit,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "decision": authz["decision"],
            "denial_reason": authz["denial_reason"],
            "rate_limit_status": rate_limit["rate_limit_status"],
            "audit_event_present": request["audit_event_present"],
            "restricted_data_leaked": request["restricted_data_leaked"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(report, source_refs=source_refs)


def build_hosted_api_route_manifest(
    *,
    manifest_id: str = "hosted-api-route-manifest",
    base_path: str = "/v1",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or ["hosted-api-route-manifest"])
    envelope_input = {"system_actor": "hate-local", "decision_basis": source_refs}
    routes = [_route_contract(route) for route in HOSTED_API_ROUTES]
    manifest = {
        "schema_version": "HATE/v1",
        "record_type": "hosted-api-route-manifest",
        "manifest_id": manifest_id,
        **productization_envelope(envelope_input, report_id=manifest_id, source_refs=source_refs),
        "readiness_effect": "none",
        "base_path": base_path,
        "routes": routes,
        "summary": {
            "route_count": len(routes),
            "tenant_scoped_count": sum(1 for route in routes if route["tenant_scoped"]),
            "audit_required_count": sum(1 for route in routes if route["audit_required"]),
            "rate_limited_count": sum(1 for route in routes if route["rate_limited"]),
            "write_route_count": sum(1 for route in routes if route["action"] == "write"),
        },
        "sourceRefs": source_refs,
    }
    return apply_productization_contract_tree(manifest, source_refs=source_refs)


def build_hosted_api_openapi_document(
    *,
    title: str = "HATE Hosted Platform API",
    version: str = "0.1.0",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    manifest = build_hosted_api_route_manifest(source_refs=source_refs)
    paths: dict[str, Any] = {}
    for route in manifest["routes"]:
        method = route["method"].lower()
        paths.setdefault(route["path"], {})[method] = {
            "operationId": route["operation_id"],
            "summary": route["description"],
            "x-hate-resource": route["resource"],
            "x-hate-action": route["action"],
            "x-hate-tenant-scoped": route["tenant_scoped"],
            "x-hate-audit-required": route["audit_required"],
            "x-hate-rate-limited": route["rate_limited"],
            "security": [{"hateAuth": [route["required_scope"]]}],
            "responses": {
                "200": {"description": "Accepted canonical HATE response envelope."},
                "401": {"description": "Authentication required or expired."},
                "403": {"description": "Tenant, role, or scope denied without restricted data leakage."},
                "429": {"description": "Rate limit exceeded."},
            },
        }
    return {
        "openapi": "3.1.0",
        "info": {"title": title, "version": version},
        "paths": paths,
        "components": {
            "securitySchemes": {
                "hateAuth": {
                    "type": "oauth2",
                    "flows": {
                        "clientCredentials": {
                            "tokenUrl": "/oauth/token",
                            "scopes": {route["required_scope"]: route["description"] for route in manifest["routes"]},
                        }
                    },
                }
            }
        },
        "x-hate-sourceRefs": manifest["sourceRefs"],
        "x-hate-route-summary": manifest["summary"],
    }


def write_hosted_api_openapi_document(document: dict[str, Any], out_path: str | Path) -> dict[str, Any]:
    import json

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {
        "schema_version": "HATE/v1",
        "record_type": "hosted-api-openapi-artifact",
        **productization_envelope(document, report_id="hosted-api-openapi:artifact", source_refs=list(document.get("x-hate-sourceRefs", []))),
        "readiness_effect": "none",
        "artifact_path": str(path),
        "path_count": len(document.get("paths", {})),
        "sourceRefs": list(document.get("x-hate-sourceRefs", [])),
    }


def _route_contract(route: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "hosted-api-route-contract",
        "operation_id": str(route["operation_id"]),
        "method": str(route["method"]),
        "path": str(route["path"]),
        "resource": str(route["resource"]),
        "action": str(route["action"]),
        "required_scope": str(route["required_scope"]),
        "tenant_scoped": bool(route["tenant_scoped"]),
        "audit_required": bool(route["audit_required"]),
        "rate_limited": bool(route["rate_limited"]),
        "description": f"{route['method']} {route['path']} requires tenant isolation, audit, and rate-limit evidence.",
    }


def _normalize_request(raw: dict[str, Any]) -> dict[str, Any]:
    request = dict(raw or {})
    return {
        "record_type": "hosted-api-request-record",
        "request_id": str(request.get("request_id") or ""),
        "tenant_id": str(request.get("tenant_id") or ""),
        "resource_tenant_id": str(request.get("resource_tenant_id") or request.get("tenant_id") or ""),
        "subject_id": str(request.get("subject_id") or ""),
        "role": str(request.get("role") or "viewer"),
        "auth_method": str(request.get("auth_method") or ""),
        "resource": str(request.get("resource") or ""),
        "action": str(request.get("action") or "read"),
        "token_ref": str(request.get("token_ref") or ""),
        "raw_token": str(request.get("raw_token") or ""),
        "token_expiry": str(request.get("token_expiry") or ""),
        "service_account_scopes": [str(item) for item in request.get("service_account_scopes", [])],
        "required_scope": str(request.get("required_scope") or ""),
        "rate_limit_bucket": str(request.get("rate_limit_bucket") or ""),
        "rate_limit_status": str(request.get("rate_limit_status") or "ok"),
        "audit_event_present": bool(request.get("audit_event_present", False)),
        "restricted_data_leaked": bool(request.get("restricted_data_leaked", False)),
        "safe_denial_response": bool(request.get("safe_denial_response", True)),
    }


def _authz_decision(request: dict[str, Any]) -> dict[str, Any]:
    decision = "allowed"
    denial_reason = ""
    if request["tenant_id"] != request["resource_tenant_id"]:
        decision = "denied"
        denial_reason = "cross_tenant"
    elif request["auth_method"] == "service_account" and request["required_scope"] and request["required_scope"] not in request["service_account_scopes"]:
        decision = "denied"
        denial_reason = "service_account_scope"
    elif _token_expired(request["token_expiry"]):
        decision = "denied"
        denial_reason = "token_expired"
    return {
        "record_type": "hosted-authz-decision-record",
        "request_id": request["request_id"],
        "tenant_id": request["tenant_id"],
        "subject_id": request["subject_id"],
        "role": request["role"],
        "auth_method": request["auth_method"],
        "resource": request["resource"],
        "action": request["action"],
        "decision": decision,
        "denial_reason": denial_reason,
        "token_ref": request["token_ref"],
        "token_expiry": request["token_expiry"],
    }


def _rate_limit_event(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "hosted-rate-limit-event",
        "request_id": request["request_id"],
        "tenant_id": request["tenant_id"],
        "rate_limit_bucket": request["rate_limit_bucket"],
        "rate_limit_status": request["rate_limit_status"],
    }


def _findings_for(
    request: dict[str, Any],
    authz: dict[str, Any],
    rate_limit: dict[str, Any],
    source_ref: str,
) -> list[HostedApiFinding]:
    findings: list[HostedApiFinding] = []
    if authz["denial_reason"] == "cross_tenant":
        findings.append(_finding("api_cross_tenant_denied", "Cross-tenant access denied.", source_ref))
        if not request["safe_denial_response"]:
            findings.append(_finding("api_restricted_data_leaked", "Cross-tenant denial leaked restricted data.", source_ref))
    if authz["denial_reason"] == "token_expired":
        findings.append(_finding("api_token_expired", "Expired token denied.", source_ref))
    if authz["denial_reason"] == "service_account_scope":
        findings.append(_finding("api_service_account_scope_denied", "Service account scope denied.", source_ref))
    if rate_limit["rate_limit_status"] in {"exceeded", "blocked"}:
        findings.append(_finding("api_rate_limit_exceeded", "Hosted API rate limit exceeded.", source_ref))
    if not request["audit_event_present"]:
        findings.append(_finding("api_audit_event_missing", "Every hosted API request requires an audit event.", source_ref))
    if request["restricted_data_leaked"] or request["raw_token"] or (request["token_ref"] and not request["token_ref"].startswith(("token-ref://", "secret-ref://"))):
        findings.append(_finding("api_restricted_data_leaked", "Hosted API response or request contains restricted data.", source_ref))
    if request["auth_method"] not in AUTH_METHODS:
        findings.append(_finding("api_service_account_scope_denied", "Unsupported hosted API auth_method.", source_ref))
    return findings


def _token_expired(token_expiry: str) -> bool:
    if not token_expiry:
        return False
    try:
        expiry = datetime.fromisoformat(token_expiry.replace("Z", "+00:00"))
    except ValueError:
        return True
    now = datetime.fromisoformat("2026-07-03T00:00:00+00:00")
    return expiry <= now


def _finding(code: str, message: str, source_ref: str) -> HostedApiFinding:
    return HostedApiFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
        readiness_effect="hold",
    )
