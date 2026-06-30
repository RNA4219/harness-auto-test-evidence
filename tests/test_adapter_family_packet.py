"""Tests for HATE-GAP-014 adapter family implementation packets."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from hate.adapters import build_adapter_family_report, evaluate_adapter_family_fixture
from hate.adapters.corpus_manifest import REQUIRED_FAMILIES


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "adapters" / "family"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "adapter-family-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"
TODAY = date(2026, 6, 30)


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _packet(family: str = "test-results", **overrides) -> dict:
    requirement = REQUIRED_FAMILIES[family]
    packet = {
        "family": family,
        "adapter_id": f"{family}-adapter",
        "dialects": sorted(requirement["dialects"]),
        "fixture_paths": [f"fixtures/adapters/{family}/input.json"],
        "positive_count": requirement["positive_minimum"],
        "negative_count": requirement["negative_minimum"],
        "malformed_count": 1,
        "partial_count": 1,
        "path_normalization_count": 1,
        "metadata_preservation_count": 1,
        "expected_output_ref": f"fixtures/adapters/{family}/expected/HATE-output.ndjson",
        "reviewed_at": "2026-06-30",
        "review_owner": "Developer Platform",
        "stale_after_days": 30,
        "unsupported_claims": [],
        "sourceRefs": [f"fixtures/adapters/{family}"],
    }
    packet.update(overrides)
    return packet


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "adapter-family-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for packet in report["packets"]:
        required = schema["properties"]["packets"]["items"]["required"]
        assert set(required) <= set(packet)
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_014_fixture_paths_exist() -> None:
    assert (FIXTURES / "junit-pass" / "fixture.json").is_file()
    assert (FIXTURES / "malformed-input" / "fixture.json").is_file()


def test_junit_family_fixture_passes() -> None:
    result = evaluate_adapter_family_fixture(_fixture("junit-pass"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])
    assert result["report"]["packets"][0]["family"] == "test-results"
    assert result["report"]["packets"][0]["dialects"] == ["junit"]


def test_malformed_family_fixture_holds() -> None:
    result = evaluate_adapter_family_fixture(_fixture("malformed-input"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "adapter_family_malformed_input"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_explicit_packet_passes_with_all_required_fields() -> None:
    report = build_adapter_family_report({"family_packet": _packet()}, today=TODAY)

    assert report["overall_status"] == "pass"
    assert report["findings"] == []
    assert report["summary"]["families"] == ["test-results"]


def test_missing_packet_fields_hold() -> None:
    report = build_adapter_family_report({"family_packet": {"family": "coverage", "dialects": ["lcov"]}}, today=TODAY)

    assert report["overall_status"] == "hold"
    assert "adapter_family_packet_field_missing" in _codes(report)


def test_fixture_counts_below_minimum_hold() -> None:
    report = build_adapter_family_report(
        {"family_packet": _packet("coverage", positive_count=1, negative_count=1)},
        today=TODAY,
    )

    assert report["overall_status"] == "hold"
    assert "adapter_family_fixture_count_below_minimum" in _codes(report)


def test_required_case_coverage_is_required() -> None:
    report = build_adapter_family_report(
        {"family_packet": _packet("static", malformed_count=0, metadata_preservation_count=0)},
        today=TODAY,
    )

    assert report["overall_status"] == "hold"
    assert "adapter_family_required_case_missing" in _codes(report)


def test_unsupported_dialect_holds() -> None:
    report = build_adapter_family_report({"family_packet": _packet(dialects=["junit", "tap"])} , today=TODAY)

    assert report["overall_status"] == "hold"
    assert "adapter_family_unsupported_dialect" in _codes(report)


def test_unsupported_family_claim_holds() -> None:
    report = build_adapter_family_report(
        {
            "family_packet": {
                **_packet(),
                "family": "mobile-device-farm",
                "unsupported_claims": ["native-ios-device-grid"],
            }
        },
        today=TODAY,
    )

    assert report["overall_status"] == "hold"
    assert "adapter_family_unsupported_claim" in _codes(report)


def test_expected_output_ref_is_required() -> None:
    report = build_adapter_family_report({"family_packet": _packet("contract", expected_output_ref="")}, today=TODAY)

    assert report["overall_status"] == "hold"
    assert "adapter_family_expected_output_missing" in _codes(report)


def test_stale_review_owner_or_date_holds() -> None:
    report = build_adapter_family_report(
        {"family_packet": _packet("mutation", reviewed_at="2026-01-01", stale_after_days=30)},
        today=TODAY,
    )

    assert report["overall_status"] == "hold"
    assert "adapter_family_stale_review" in _codes(report)


def test_adapter_family_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["adapter-family-report"] == "schemas/HATE/v1/adapter-family-report.schema.json"
