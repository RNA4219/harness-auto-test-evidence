"""Tests for HATE-GAP-009 API contract report."""

from __future__ import annotations

import json
from pathlib import Path

from hate.api import build_api_contract_report, evaluate_api_contract_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "api" / "contract"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "api-contract-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "api-contract-report"
    assert report["status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert set(schema["properties"]["request_contract"]["required"]) <= set(report["request_contract"])
    assert set(schema["properties"]["response_contract"]["required"]) <= set(report["response_contract"])
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_paginated_evidence_fixture_passes() -> None:
    result = evaluate_api_contract_fixture(_fixture("paginated-evidence"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    report = result["report"]
    _assert_report_contract(report)
    assert report["endpoint"] == "/v1/evidence"
    assert report["resource"] == "evidence"
    assert report["request_contract"]["pagination"]["limit"] == 50
    assert report["response_contract"]["pagination_required"] is True


def test_authz_leak_denied_fixture_is_hold() -> None:
    result = evaluate_api_contract_fixture(_fixture("authz-leak-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "api_authz_leak_denied"
    finding = result["report"]["findings"][0]
    assert finding["severity"] == "critical"


def test_unknown_endpoint_is_hold() -> None:
    report = build_api_contract_report({"endpoint": "/v1/unknown", "authz": "allowed"})

    assert report["status"] == "hold"
    assert "api_endpoint_unknown" in _codes(report)


def test_missing_pagination_is_hold_when_required() -> None:
    report = build_api_contract_report({
        "endpoint": "/v1/evidence",
        "requires_pagination": True,
        "authz": "allowed",
    })

    assert report["status"] == "hold"
    assert "api_pagination_missing" in _codes(report)


def test_invalid_pagination_limit_is_hold() -> None:
    report = build_api_contract_report({
        "endpoint": "/v1/evidence",
        "pagination": {"limit": 5001, "cursor": "cur_1"},
        "authz": "allowed",
    })

    assert report["status"] == "hold"
    assert "api_pagination_invalid" in _codes(report)


def test_denied_response_cannot_leak_tenant_existence() -> None:
    report = build_api_contract_report({
        "endpoint": "/v1/artifacts",
        "authz": "denied",
        "tenant_existence_visible": True,
    })

    assert report["status"] == "hold"
    assert "api_authz_tenant_leak_denied" in _codes(report)


def test_stale_read_model_cannot_be_marked_fresh() -> None:
    report = build_api_contract_report({
        "endpoint": "/v1/runs",
        "authz": "allowed",
        "staleness": "fresh",
        "source_bundle_stale": True,
    })

    assert report["status"] == "hold"
    assert "api_stale_read_model_marked_fresh" in _codes(report)


def test_response_envelope_is_required() -> None:
    report = build_api_contract_report({
        "endpoint": "/v1/runs",
        "authz": "allowed",
        "envelope": "missing",
    })

    assert report["status"] == "hold"
    assert "api_response_envelope_missing" in _codes(report)


def test_report_includes_source_refs_and_redacted_denial_contract() -> None:
    report = build_api_contract_report(
        {"endpoint": "/v1/artifacts", "authz": "denied"},
        source_refs=["HOSTED_READ_MODEL_API.md"],
    )

    _assert_report_contract(report)
    assert "HOSTED_READ_MODEL_API.md" in report["sourceRefs"]
    assert report["response_contract"]["redacted_denial_required"] is True


def test_api_contract_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["api-contract-report"] == "schemas/HATE/v1/api-contract-report.schema.json"
