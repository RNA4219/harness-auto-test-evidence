"""Tests for HATE-GAP-017 deployment topology and residency."""

from __future__ import annotations

import json
from pathlib import Path

from hate.deployment import build_deployment_topology_report, evaluate_deployment_topology_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "deployment" / "topology"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "deployment-topology-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "deployment-topology-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert set(schema["properties"]["profile"]["required"]) <= set(report["profile"])
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_017_fixture_paths_exist() -> None:
    assert (FIXTURES / "local-single-node" / "fixture.json").is_file()
    assert (FIXTURES / "region-violation" / "fixture.json").is_file()


def test_local_single_node_fixture_passes() -> None:
    result = evaluate_deployment_topology_fixture(_fixture("local-single-node"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])
    assert result["report"]["profile"]["offline_mode"] is True
    assert result["report"]["summary"]["local_first_preserved"] is True


def test_region_violation_fixture_holds() -> None:
    result = evaluate_deployment_topology_fixture(_fixture("region-violation"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "deployment_region_violation"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_allowed_region_matrix_is_enforced() -> None:
    report = build_deployment_topology_report({
        "topology": "hosted_read_model",
        "actual_region": "eu",
        "allowed_regions": ["jp", "us"],
    })

    assert report["overall_status"] == "hold"
    assert "deployment_region_not_allowed" in _codes(report)


def test_raw_customer_data_is_not_hosted_by_default() -> None:
    report = build_deployment_topology_report({
        "topology": "hosted_read_model",
        "region": "jp",
        "data_classes": {
            "canonical_bundle": "customer_controlled",
            "read_model": "hosted_allowed",
            "artifact_content": "hosted",
            "telemetry": "aggregate_only",
        },
    })

    assert report["overall_status"] == "hold"
    assert "deployment_raw_data_hosted_upload_denied" in _codes(report)


def test_hosted_read_model_must_be_rebuildable() -> None:
    report = build_deployment_topology_report({
        "topology": "hosted_read_model",
        "region": "jp",
        "canonical_bundle_rebuildable": False,
    })

    assert report["overall_status"] == "hold"
    assert "deployment_read_model_not_rebuildable" in _codes(report)


def test_private_tenant_requires_private_networking() -> None:
    report = build_deployment_topology_report({
        "topology": "private_tenant",
        "region": "jp",
        "network": {"private_link": False, "public_ingress": False, "ip_allowlist": True},
    })

    assert report["overall_status"] == "hold"
    assert "deployment_private_network_missing" in _codes(report)


def test_air_gapped_export_requires_offline_mode() -> None:
    report = build_deployment_topology_report({
        "topology": "air_gapped_export",
        "offline_mode": False,
    })

    assert report["overall_status"] == "hold"
    assert "deployment_airgap_offline_mode_required" in _codes(report)


def test_backup_cannot_rewrite_record_ids() -> None:
    report = build_deployment_topology_report({
        "topology": "hosted_read_model",
        "region": "jp",
        "backup": {"strategy": "restore", "rewrites_record_ids": True},
    })

    assert report["overall_status"] == "hold"
    assert "deployment_backup_rewrites_records" in _codes(report)


def test_deployment_topology_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["deployment-topology-report"] == "schemas/HATE/v1/deployment-topology-report.schema.json"
