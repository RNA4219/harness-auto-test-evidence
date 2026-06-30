"""Tests for HATE-GAP-031 self-hosted installation evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.self_hosted import build_self_hosted_report, evaluate_self_hosted_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "self-hosted"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "self-hosted-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "self-hosted-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_031_fixture_paths_exist() -> None:
    assert (FIXTURES / "upgrade-compatible" / "fixture.json").is_file()
    assert (FIXTURES / "rollback-required" / "fixture.json").is_file()


def test_upgrade_compatible_fixture_passes() -> None:
    result = evaluate_self_hosted_fixture(_fixture("upgrade-compatible"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_rollback_required_fixture_holds() -> None:
    result = evaluate_self_hosted_fixture(_fixture("rollback-required"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "self_hosted_rollback_required"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_installer_contract_holds() -> None:
    report = build_self_hosted_report({
        "installer_contract_defined": False,
        "configuration_schema_defined": True,
        "upgrade_plan_defined": True,
        "rollback_supported": True,
        "backup_prerequisite_defined": True,
        "offline_verification_supported": True,
        "air_gapped_mode": False,
        "current_version": "1.0.0",
        "target_version": "1.1.0",
        "downgrade_requested": False,
    })

    assert report["overall_status"] == "hold"
    assert "self_hosted_installer_contract_missing" in _codes(report)


def test_missing_upgrade_plan_holds() -> None:
    report = build_self_hosted_report({
        "installer_contract_defined": True,
        "configuration_schema_defined": True,
        "upgrade_plan_defined": False,
        "rollback_supported": True,
        "backup_prerequisite_defined": True,
        "offline_verification_supported": True,
        "air_gapped_mode": False,
        "current_version": "1.0.0",
        "target_version": "1.1.0",
        "downgrade_requested": False,
    })

    assert report["overall_status"] == "hold"
    assert "self_hosted_upgrade_plan_missing" in _codes(report)


def test_missing_backup_prerequisite_holds() -> None:
    report = build_self_hosted_report({
        "installer_contract_defined": True,
        "configuration_schema_defined": True,
        "upgrade_plan_defined": True,
        "rollback_supported": True,
        "backup_prerequisite_defined": False,
        "offline_verification_supported": True,
        "air_gapped_mode": False,
        "current_version": "1.0.0",
        "target_version": "1.1.0",
        "downgrade_requested": False,
    })

    assert report["overall_status"] == "hold"
    assert "self_hosted_backup_prerequisite_missing" in _codes(report)


def test_self_hosted_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["self-hosted-report"] == "schemas/HATE/v1/self-hosted-report.schema.json"
