"""Tests for HATE-GAP-035 adapter marketplace evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.adapter_marketplace import build_adapter_marketplace_report, evaluate_adapter_marketplace_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "adapter-marketplace"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "adapter-marketplace-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "adapter-marketplace-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_035_fixture_paths_exist() -> None:
    assert (FIXTURES / "signed-compatible-plugin" / "fixture.json").is_file()
    assert (FIXTURES / "revoked-plugin-denied" / "fixture.json").is_file()


def test_signed_compatible_plugin_fixture_passes() -> None:
    result = evaluate_adapter_marketplace_fixture(_fixture("signed-compatible-plugin"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_revoked_plugin_denied_fixture_holds() -> None:
    result = evaluate_adapter_marketplace_fixture(_fixture("revoked-plugin-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "adapter_marketplace_revoked_plugin_denied"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_manifest_holds() -> None:
    report = build_adapter_marketplace_report({
        "plugin_manifest_present": False,
        "plugin_id": "com.example.plugin",
        "publisher_id": "com.example",
        "signature_present": True,
        "signature_verified": True,
        "compatibility_range": ">=1.0.0,<2.0.0",
        "host_version": "1.6.0",
        "conformance_evidence_present": True,
        "deprecation_status": "active",
        "revocation_record_present": False,
        "requested_install": True,
    })

    assert report["overall_status"] == "hold"
    assert "adapter_marketplace_manifest_missing" in _codes(report)


def test_missing_signature_holds() -> None:
    report = build_adapter_marketplace_report({
        "plugin_manifest_present": True,
        "plugin_id": "com.example.plugin",
        "publisher_id": "com.example",
        "signature_present": False,
        "signature_verified": False,
        "compatibility_range": ">=1.0.0,<2.0.0",
        "host_version": "1.6.0",
        "conformance_evidence_present": True,
        "deprecation_status": "active",
        "revocation_record_present": False,
        "requested_install": True,
    })

    assert report["overall_status"] == "hold"
    assert "adapter_marketplace_signature_missing" in _codes(report)


def test_invalid_signature_holds() -> None:
    report = build_adapter_marketplace_report({
        "plugin_manifest_present": True,
        "plugin_id": "com.example.plugin",
        "publisher_id": "com.example",
        "signature_present": True,
        "signature_verified": False,
        "compatibility_range": ">=1.0.0,<2.0.0",
        "host_version": "1.6.0",
        "conformance_evidence_present": True,
        "deprecation_status": "active",
        "revocation_record_present": False,
        "requested_install": True,
    })

    assert report["overall_status"] == "hold"
    assert "adapter_marketplace_signature_invalid" in _codes(report)


def test_incompatible_host_version_holds() -> None:
    report = build_adapter_marketplace_report({
        "plugin_manifest_present": True,
        "plugin_id": "com.example.plugin",
        "publisher_id": "com.example",
        "signature_present": True,
        "signature_verified": True,
        "compatibility_range": ">=2.0.0,<3.0.0",
        "host_version": "1.0.0",
        "conformance_evidence_present": True,
        "deprecation_status": "active",
        "revocation_record_present": False,
        "requested_install": True,
    })

    assert report["overall_status"] == "hold"
    assert "adapter_marketplace_incompatible_host" in _codes(report)


def test_missing_publisher_id_holds() -> None:
    report = build_adapter_marketplace_report({
        "plugin_manifest_present": True,
        "plugin_id": "com.example.plugin",
        "publisher_id": "",
        "signature_present": True,
        "signature_verified": True,
        "compatibility_range": ">=1.0.0,<2.0.0",
        "host_version": "1.6.0",
        "conformance_evidence_present": True,
        "deprecation_status": "active",
        "revocation_record_present": False,
        "requested_install": True,
    })

    assert report["overall_status"] == "hold"
    assert "adapter_marketplace_publisher_missing" in _codes(report)


def test_adapter_marketplace_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["adapter-marketplace-report"] == "schemas/HATE/v1/adapter-marketplace-report.schema.json"


def test_adapter_marketplace_no_report_json_alias_schema() -> None:
    alias_path = ROOT / "schemas" / "HATE" / "v1" / "adapter-marketplace-report.json"
    assert not alias_path.exists()