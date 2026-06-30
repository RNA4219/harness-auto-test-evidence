"""API rate limit and abuse-prevention evaluator for HATE-GAP-003."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import ceil
from typing import Any
import uuid


MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
DEFAULT_QUOTA = 100
DEFAULT_WINDOW_SECONDS = 60
DEFAULT_ABUSE_MULTIPLIER = 2.0


@dataclass(frozen=True)
class TenantScope:
    organization_id: str
    workspace_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "organization_id": self.organization_id,
            "workspace_id": self.workspace_id,
        }

    def is_complete(self) -> bool:
        return bool(self.organization_id and self.workspace_id)


@dataclass
class RateLimitFinding:
    code: str
    severity: str
    message: str
    source_refs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "source_refs": self.source_refs,
        }


@dataclass
class RateLimitDecision:
    request_id: str
    tenant: TenantScope
    actor_id: str
    route: str
    method: str
    requests: int
    quota: int
    window_seconds: int
    status: str
    readiness_effect: str
    remaining: int
    retry_after_seconds: int | None
    reset_after_seconds: int
    findings: list[RateLimitFinding]
    audit_event: dict[str, Any]

    def as_report(self, *, source_version: str, source_refs: list[str]) -> dict[str, Any]:
        finding_code = self.findings[0].code if self.findings else ""
        report = {
            "schema_version": "HATE/v1",
            "record_type": "api-rate-limit-report",
            "source_version": source_version,
            "status": self.status,
            "readiness_effect": self.readiness_effect,
            "request_id": self.request_id,
            "tenant": self.tenant.as_dict(),
            "actor_id": self.actor_id,
            "route": self.route,
            "method": self.method,
            "quota": {
                "limit": self.quota,
                "window_seconds": self.window_seconds,
                "used": self.requests,
                "remaining": self.remaining,
                "reset_after_seconds": self.reset_after_seconds,
                "retry_after_seconds": self.retry_after_seconds,
            },
            "response_headers": _rate_limit_headers(
                limit=self.quota,
                remaining=self.remaining,
                reset_after_seconds=self.reset_after_seconds,
                retry_after_seconds=self.retry_after_seconds,
            ),
            "audit_events": [self.audit_event],
            "findings": [finding.as_dict() for finding in self.findings],
            "sourceRefs": source_refs,
        }
        if finding_code:
            report["finding_code"] = finding_code
        return report


def evaluate_api_rate_limit_fixture(payload: dict[str, Any], *, source_version: str = "unknown") -> dict[str, Any]:
    """Evaluate a product-gap fixture for API rate limiting."""

    data = payload.get("input", {})
    decision = evaluate_rate_limit_request(data, fixture_id=str(payload.get("fixture_id") or "api-rate-limit-fixture"))
    return decision.as_report(source_version=source_version, source_refs=[str(payload.get("fixture_id") or "api-rate-limit")])


def evaluate_rate_limit_request(data: dict[str, Any], *, fixture_id: str = "api-rate-limit") -> RateLimitDecision:
    """Evaluate one deterministic rate-limit request envelope.

    The evaluator is intentionally local and replayable. It models the hosted API
    contract without depending on an external gateway or billing meter.
    """

    request_id = str(data.get("request_id") or f"req-{uuid.uuid5(uuid.NAMESPACE_URL, fixture_id).hex[:12]}")
    tenant = _tenant_from_input(data)
    actor_id = str(data.get("actor_id") or "actor-local")
    route = str(data.get("route") or "/v1/runs")
    method = str(data.get("method") or "GET").upper()
    requests = _non_negative_int(data.get("requests"), default=0)
    quota = _positive_int(data.get("quota"), default=DEFAULT_QUOTA)
    window_seconds = _positive_int(data.get("window_seconds"), default=DEFAULT_WINDOW_SECONDS)
    abuse_multiplier = float(data.get("abuse_multiplier") or DEFAULT_ABUSE_MULTIPLIER)
    require_tenant_scope = bool(data.get("require_tenant_scope"))
    mutating = bool(data.get("mutating")) or method in MUTATING_METHODS

    findings: list[RateLimitFinding] = []
    if require_tenant_scope and not tenant.is_complete():
        findings.append(_finding(
            "api_tenant_scope_missing",
            "high",
            "hosted API rate limiting requires organization_id and workspace_id scope",
        ))
    if mutating and not data.get("idempotency_key"):
        findings.append(_finding(
            "api_idempotency_key_missing",
            "high",
            "mutating API requests require an idempotency key before rate-limit accounting",
        ))
    if requests > ceil(quota * abuse_multiplier):
        findings.append(_finding(
            "api_abuse_burst_detected",
            "critical",
            "request burst exceeded abuse-prevention threshold",
        ))
    elif requests > quota:
        findings.append(_finding(
            "api_quota_exceeded",
            "high",
            "request count exceeded quota for the current window",
        ))

    status = "hold" if findings else "pass"
    retry_after_seconds = window_seconds if any(item.code in {"api_quota_exceeded", "api_abuse_burst_detected"} for item in findings) else None
    remaining = max(quota - requests, 0)
    readiness_effect = "hold" if findings else "none"
    audit_event = _audit_event(
        request_id=request_id,
        tenant=tenant,
        actor_id=actor_id,
        route=route,
        method=method,
        status=status,
        finding_code=findings[0].code if findings else "",
        requests=requests,
        quota=quota,
        window_seconds=window_seconds,
    )
    return RateLimitDecision(
        request_id=request_id,
        tenant=tenant,
        actor_id=actor_id,
        route=route,
        method=method,
        requests=requests,
        quota=quota,
        window_seconds=window_seconds,
        status=status,
        readiness_effect=readiness_effect,
        remaining=remaining,
        retry_after_seconds=retry_after_seconds,
        reset_after_seconds=window_seconds,
        findings=findings,
        audit_event=audit_event,
    )


def _tenant_from_input(data: dict[str, Any]) -> TenantScope:
    tenant = data.get("tenant") if isinstance(data.get("tenant"), dict) else {}
    organization_id = str(tenant.get("organization_id") or data.get("organization_id") or "org-local")
    workspace_id = str(tenant.get("workspace_id") or data.get("workspace_id") or "ws-local")
    if data.get("tenant") is None and data.get("require_tenant_scope"):
        organization_id = str(data.get("organization_id") or "")
        workspace_id = str(data.get("workspace_id") or "")
    return TenantScope(organization_id=organization_id, workspace_id=workspace_id)


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _non_negative_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 0)


def _finding(code: str, severity: str, message: str) -> RateLimitFinding:
    return RateLimitFinding(
        code=code,
        severity=severity,
        message=message,
        source_refs=["docs/process/API_REQUIREMENTS.md", "docs/process/PRODUCT_REQUIREMENTS_GAP_CLOSURE_PACKETS.md"],
    )


def _audit_event(
    *,
    request_id: str,
    tenant: TenantScope,
    actor_id: str,
    route: str,
    method: str,
    status: str,
    finding_code: str,
    requests: int,
    quota: int,
    window_seconds: int,
) -> dict[str, Any]:
    return {
        "event_type": "api_rate_limit_decision",
        "request_id": request_id,
        "tenant": tenant.as_dict(),
        "actor_id": actor_id,
        "route": route,
        "method": method,
        "decision": "allow" if status == "pass" else "deny",
        "finding_code": finding_code,
        "usage": {
            "requests": requests,
            "quota": quota,
            "window_seconds": window_seconds,
        },
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def _rate_limit_headers(
    *,
    limit: int,
    remaining: int,
    reset_after_seconds: int,
    retry_after_seconds: int | None,
) -> dict[str, str]:
    headers = {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset-After": str(reset_after_seconds),
    }
    if retry_after_seconds is not None:
        headers["Retry-After"] = str(retry_after_seconds)
    return headers
