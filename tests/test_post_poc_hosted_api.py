from __future__ import annotations

import json
from pathlib import Path

from hate.post_poc.hosted_api import (
    build_hosted_api_openapi_document,
    build_hosted_api_report,
    build_hosted_api_route_manifest,
    evaluate_hosted_api_fixture,
    write_hosted_api_openapi_document,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc" / "hosted-api"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "hosted-api-report.schema.json"
ROUTE_MANIFEST_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "hosted-api-route-manifest.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "hosted-api-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert report["request_record"]["record_type"] == "hosted-api-request-record"
    assert report["authz_decision"]["record_type"] == "hosted-authz-decision-record"
    assert report["rate_limit_event"]["record_type"] == "hosted-rate-limit-event"
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def _assert_route_manifest_contract(manifest: dict) -> None:
    schema = json.loads(ROUTE_MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(manifest)
    assert manifest["schema_version"] == "HATE/v1"
    assert manifest["record_type"] == "hosted-api-route-manifest"
    assert manifest["summary"]["route_count"] == len(manifest["routes"])
    assert manifest["summary"]["tenant_scoped_count"] == sum(1 for route in manifest["routes"] if route["tenant_scoped"])
    assert manifest["summary"]["audit_required_count"] == sum(1 for route in manifest["routes"] if route["audit_required"])
    assert manifest["summary"]["rate_limited_count"] == sum(1 for route in manifest["routes"] if route["rate_limited"])
    for route in manifest["routes"]:
        assert set(schema["properties"]["routes"]["items"]["required"]) <= set(route)
        assert route["record_type"] == "hosted-api-route-contract"
        assert route["required_scope"].startswith("platform:")


def test_task_postpoc_011_canonical_fixture_paths_exist() -> None:
    for name in [
        "tenant-allowed",
        "cross-tenant-denied",
        "expired-token-denied",
        "service-account-scope-denied",
        "rate-limit-exceeded",
    ]:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_tenant_allowed_passes_with_authz_and_audit() -> None:
    result = evaluate_hosted_api_fixture(_fixture("tenant-allowed"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["report"]["authz_decision"]["decision"] == "allowed"
    assert result["report"]["summary"]["audit_event_present"] is True
    _assert_report_contract(result["report"])


def test_cross_tenant_denied_is_deterministic_and_non_leaky() -> None:
    result = evaluate_hosted_api_fixture(_fixture("cross-tenant-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "api_cross_tenant_denied"
    assert result["report"]["authz_decision"]["decision"] == "denied"
    assert result["report"]["authz_decision"]["denial_reason"] == "cross_tenant"
    assert "api_restricted_data_leaked" not in _codes(result["report"])


def test_expired_token_denied() -> None:
    result = evaluate_hosted_api_fixture(_fixture("expired-token-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "api_token_expired"
    assert result["report"]["authz_decision"]["denial_reason"] == "token_expired"


def test_service_account_scope_denied() -> None:
    result = evaluate_hosted_api_fixture(_fixture("service-account-scope-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "api_service_account_scope_denied"
    assert result["report"]["authz_decision"]["denial_reason"] == "service_account_scope"


def test_rate_limit_exceeded_holds() -> None:
    result = evaluate_hosted_api_fixture(_fixture("rate-limit-exceeded"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "api_rate_limit_exceeded"
    assert result["report"]["rate_limit_event"]["rate_limit_status"] == "exceeded"


def test_audit_event_missing_holds() -> None:
    report = build_hosted_api_report({
        "request": {
            "request_id": "req-no-audit",
            "tenant_id": "tenant-a",
            "resource_tenant_id": "tenant-a",
            "subject_id": "user",
            "auth_method": "oidc",
            "resource": "read-model://portfolio",
            "token_ref": "token-ref://oidc/session",
            "token_expiry": "2026-08-03T00:00:00Z",
            "rate_limit_bucket": "tenant-a:read",
        }
    })

    assert report["overall_status"] == "hold"
    assert "api_audit_event_missing" in _codes(report)


def test_raw_token_or_bad_token_ref_is_restricted_data_leak() -> None:
    report = build_hosted_api_report({
        "request": {
            "request_id": "req-token-leak",
            "tenant_id": "tenant-a",
            "resource_tenant_id": "tenant-a",
            "subject_id": "user",
            "auth_method": "api_token",
            "resource": "read-model://portfolio",
            "token_ref": "plain-token",
            "raw_token": "secret-token",
            "token_expiry": "2026-08-03T00:00:00Z",
            "rate_limit_bucket": "tenant-a:read",
            "audit_event_present": True,
        }
    })

    assert report["overall_status"] == "hold"
    assert "api_restricted_data_leaked" in _codes(report)


def test_cross_tenant_leaky_denial_is_restricted_data_leak() -> None:
    report = build_hosted_api_report({
        "request": {
            "request_id": "req-cross-leak",
            "tenant_id": "tenant-a",
            "resource_tenant_id": "tenant-b",
            "subject_id": "user",
            "auth_method": "oidc",
            "resource": "read-model://portfolio/tenant-b",
            "token_ref": "token-ref://oidc/session",
            "token_expiry": "2026-08-03T00:00:00Z",
            "rate_limit_bucket": "tenant-a:read",
            "audit_event_present": True,
            "safe_denial_response": False,
        }
    })

    assert report["overall_status"] == "hold"
    assert "api_cross_tenant_denied" in _codes(report)
    assert "api_restricted_data_leaked" in _codes(report)


def test_hosted_api_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["hosted-api-report"] == "schemas/HATE/v1/hosted-api-report.schema.json"
    assert records["hosted-api-route-manifest"] == "schemas/HATE/v1/hosted-api-route-manifest.schema.json"


def test_hosted_api_route_manifest_covers_platform_operations() -> None:
    manifest = build_hosted_api_route_manifest(source_refs=["spec://hosted-api"])
    operations = {route["operation_id"]: route for route in manifest["routes"]}

    assert {
        "platformRun",
        "platformHistory",
        "platformFindings",
        "platformDebt",
        "platformReviewDecision",
        "platformPolicySimulation",
        "platformReport",
    } <= set(operations)
    assert manifest["summary"]["route_count"] == 7
    assert manifest["summary"]["tenant_scoped_count"] == 7
    assert manifest["summary"]["audit_required_count"] == 7
    assert manifest["summary"]["rate_limited_count"] == 7
    assert manifest["sourceRefs"] == ["spec://hosted-api"]
    _assert_route_manifest_contract(manifest)


def test_hosted_api_route_contracts_require_scope_audit_and_tenant_boundary() -> None:
    manifest = build_hosted_api_route_manifest()

    for route in manifest["routes"]:
        assert route["record_type"] == "hosted-api-route-contract"
        assert route["required_scope"].startswith("platform:")
        assert route["tenant_scoped"] is True
        assert route["audit_required"] is True
        assert route["rate_limited"] is True
        assert route["description"]


def test_hosted_api_openapi_document_exposes_safe_contract_extensions() -> None:
    document = build_hosted_api_openapi_document(version="2026.07.03", source_refs=["spec://openapi"])

    assert document["openapi"] == "3.1.0"
    assert document["info"]["version"] == "2026.07.03"
    run_operation = document["paths"]["/v1/platform/runs"]["post"]
    assert run_operation["operationId"] == "platformRun"
    assert run_operation["x-hate-tenant-scoped"] is True
    assert run_operation["x-hate-audit-required"] is True
    assert run_operation["x-hate-rate-limited"] is True
    assert run_operation["security"] == [{"hateAuth": ["platform:run"]}]
    assert "403" in run_operation["responses"]
    assert document["x-hate-sourceRefs"] == ["spec://openapi"]


def test_hosted_api_openapi_artifact_write_contract(tmp_path: Path) -> None:
    document = build_hosted_api_openapi_document(source_refs=["spec://openapi"])
    out_path = tmp_path / "openapi.json"

    artifact = write_hosted_api_openapi_document(document, out_path)

    assert artifact["record_type"] == "hosted-api-openapi-artifact"
    assert artifact["path_count"] == 7
    assert artifact["sourceRefs"] == ["spec://openapi"]
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["paths"]["/v1/platform/review/decisions"]["post"]["operationId"] == "platformReviewDecision"
