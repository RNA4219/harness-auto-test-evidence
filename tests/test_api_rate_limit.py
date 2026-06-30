"""Tests for HATE-GAP-003 API rate-limit contract."""

from __future__ import annotations

import json
from pathlib import Path

from hate.api.rate_limit import evaluate_api_rate_limit_fixture, evaluate_rate_limit_request


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "api" / "rate-limit"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "api-rate-limit-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def test_burst_within_quota_passes_with_headers_and_audit() -> None:
    report = evaluate_api_rate_limit_fixture(_fixture("burst-within-quota"), source_version="test")

    assert report["record_type"] == "api-rate-limit-report"
    assert report["status"] == "pass"
    assert report["readiness_effect"] == "none"
    assert report["quota"]["limit"] == 100
    assert report["quota"]["used"] == 10
    assert report["quota"]["remaining"] == 90
    assert "Retry-After" not in report["response_headers"]
    assert report["audit_events"][0]["decision"] == "allow"
    assert report["findings"] == []


def test_quota_exceeded_holds_with_retry_after() -> None:
    report = evaluate_api_rate_limit_fixture(_fixture("quota-exceeded"), source_version="test")

    assert report["status"] == "hold"
    assert report["finding_code"] == "api_quota_exceeded"
    assert report["quota"]["remaining"] == 0
    assert report["quota"]["retry_after_seconds"] == 60
    assert report["response_headers"]["Retry-After"] == "60"
    assert report["audit_events"][0]["decision"] == "deny"


def test_missing_tenant_scope_is_hard_gap_for_hosted_requests() -> None:
    report = evaluate_api_rate_limit_fixture(_fixture("missing-tenant-scope"), source_version="test")

    assert report["status"] == "hold"
    assert report["finding_code"] == "api_tenant_scope_missing"
    assert report["tenant"] == {"organization_id": "", "workspace_id": ""}


def test_mutating_request_requires_idempotency_before_accounting() -> None:
    report = evaluate_api_rate_limit_fixture(_fixture("mutating-without-idempotency"), source_version="test")

    assert report["status"] == "hold"
    assert report["finding_code"] == "api_idempotency_key_missing"
    assert report["method"] == "POST"
    assert report["audit_events"][0]["route"] == "/v1/bundles/import"


def test_abuse_burst_takes_priority_over_quota_exceeded() -> None:
    report = evaluate_api_rate_limit_fixture(_fixture("abuse-burst-denied"), source_version="test")

    assert report["status"] == "hold"
    assert report["finding_code"] == "api_abuse_burst_detected"
    assert report["findings"][0]["severity"] == "critical"


def test_mutating_request_with_idempotency_and_tenant_passes() -> None:
    decision = evaluate_rate_limit_request(
        {
            "tenant": {"organization_id": "org-001", "workspace_id": "ws-001"},
            "actor_id": "user-001",
            "route": "/v1/exports/github",
            "method": "POST",
            "idempotency_key": "idem-001",
            "requests": 4,
            "quota": 10,
            "window_seconds": 30,
            "require_tenant_scope": True,
        },
        fixture_id="mutating-pass",
    )

    assert decision.status == "pass"
    assert decision.remaining == 6
    assert decision.audit_event["decision"] == "allow"


def test_schema_registered_for_api_rate_limit_report() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "api-rate-limit-report"
    assert "audit_events" in schema["required"]
    assert "response_headers" in schema["required"]
    assert {
        "record_type": "api-rate-limit-report",
        "schema": "schemas/HATE/v1/api-rate-limit-report.schema.json",
        "phase": "P3",
    } in registry["records"]
