"""Tests for platform policy config resolution."""

from __future__ import annotations

import json
from pathlib import Path

from hate.policy_config import build_platform_policy_report


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "platform" / "policy"
SCHEMAS = ROOT / "schemas" / "HATE" / "v1"


def test_platform_policy_fixture_paths_exist() -> None:
    for name in [
        "default-effective",
        "layered-override",
        "release-unsigned-plugin-denied",
        "regulated-unsigned-plugin-denied",
        "threshold-specificity",
        "legal-hold-retention-override",
        "scheduler-invalid-budget",
        "required-fields-missing",
    ]:
        assert (FIXTURES / name / "fixture.json").exists()


def test_default_effective_profile_resolves() -> None:
    fixture = _fixture("default-effective")

    report = build_platform_policy_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["profile"] == fixture["expected"]["profile"]
    assert report["effective_profile"]["rules"]["required_owner"] is fixture["expected"]["required_owner"]
    assert report["policy_hash"].startswith("sha256:")
    assert report["findings"] == []


def test_layered_override_explains_effective_source() -> None:
    fixture = _fixture("layered-override")

    report = build_platform_policy_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["effective_profile"]["rules"]["required_owner"] is fixture["expected"]["required_owner"]
    assert report["effective_profile"]["rule_sources"]["required_owner"] == "release"
    assert fixture["expected"]["source_ref"] in report["sourceRefs"]


def test_release_unsigned_plugin_is_denied() -> None:
    fixture = _fixture("release-unsigned-plugin-denied")

    report = build_platform_policy_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["plugin_trust_decision"]["allowed"] is fixture["expected"]["allowed"]
    assert set(fixture["expected"]["finding_codes"]) <= {finding["code"] for finding in report["findings"]}


def test_regulated_unsigned_plugin_is_denied_even_when_profile_rule_is_thin() -> None:
    fixture = _fixture("regulated-unsigned-plugin-denied")

    report = build_platform_policy_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["plugin_trust_decision"]["allowed"] is fixture["expected"]["allowed"]
    assert set(fixture["expected"]["finding_codes"]) <= {finding["code"] for finding in report["findings"]}


def test_threshold_specificity_prefers_repo_suite() -> None:
    fixture = _fixture("threshold-specificity")

    report = build_platform_policy_report(fixture["input"], fixture["fixture_id"])
    threshold = report["resolved_thresholds"][0]

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert threshold["value"] == fixture["expected"]["value"]
    assert threshold["source_layer"] == fixture["expected"]["source_layer"]
    assert threshold["reason"] == "HATE unit suite"


def test_legal_hold_overrides_full_delete() -> None:
    fixture = _fixture("legal-hold-retention-override")

    report = build_platform_policy_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["retention_decision"]["effective_deletion_mode"] == fixture["expected"]["effective_deletion_mode"]
    assert fixture["expected"]["finding_code"] in {finding["code"] for finding in report["findings"]}


def test_scheduler_invalid_budget_is_hold() -> None:
    fixture = _fixture("scheduler-invalid-budget")

    report = build_platform_policy_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["scheduler_decision"]["max_concurrent_repos"] is None
    assert report["scheduler_decision"]["max_concurrent_plugins"] == 2
    assert set(fixture["expected"]["finding_codes"]) <= {finding["code"] for finding in report["findings"]}


def test_required_top_level_fields_are_checked_before_normalization() -> None:
    fixture = _fixture("required-fields-missing")

    report = build_platform_policy_report(fixture["input"], fixture["fixture_id"])
    missing_finding = next(finding for finding in report["findings"] if finding["code"] == fixture["expected"]["finding_code"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert missing_finding["missing_fields"] == fixture["expected"]["missing_fields"]


def test_platform_policy_schema_registered() -> None:
    schema = json.loads((SCHEMAS / "platform-policy-report.schema.json").read_text(encoding="utf-8"))
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "platform-policy-report"
    assert "scheduler_decision" in schema["required"]
    assert any(record["record_type"] == "platform-policy-report" for record in registry["records"])


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))
