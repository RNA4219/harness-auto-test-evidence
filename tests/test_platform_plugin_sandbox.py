"""Tests for platform plugin sandbox decisions."""

from __future__ import annotations

import json
from pathlib import Path

from hate.plugins.sandbox import build_plugin_sandbox_report


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "platform" / "plugin-sandbox"
SCHEMAS = ROOT / "schemas" / "HATE" / "v1"


def test_plugin_sandbox_fixture_paths_exist() -> None:
    for name in [
        "builtin-pass",
        "workspace-unsigned-release-denied",
        "output-budget-exceeded",
        "network-denied",
        "crash-isolated",
    ]:
        assert (FIXTURES / name / "fixture.json").exists()


def test_builtin_plugin_passes_in_release() -> None:
    fixture = _fixture("builtin-pass")

    report = build_plugin_sandbox_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["mode_decision"]["allowed"] is fixture["expected"]["allowed"]
    assert report["findings"] == []


def test_workspace_unsigned_plugin_is_denied_in_release() -> None:
    fixture = _fixture("workspace-unsigned-release-denied")

    report = build_plugin_sandbox_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["mode_decision"]["allowed"] is fixture["expected"]["allowed"]
    assert fixture["expected"]["finding_code"] in _codes(report)


def test_output_budget_exceeded_is_finding() -> None:
    fixture = _fixture("output-budget-exceeded")

    report = build_plugin_sandbox_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["output_decision"]["output_bytes"] > report["output_decision"]["max_output_bytes"]
    assert fixture["expected"]["finding_code"] in _codes(report)


def test_network_access_is_denied_by_default() -> None:
    fixture = _fixture("network-denied")

    report = build_plugin_sandbox_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["isolation_decision"]["network_access_attempted"] is True
    assert fixture["expected"]["finding_code"] in _codes(report)


def test_crash_isolated_allows_platform_to_continue() -> None:
    fixture = _fixture("crash-isolated")

    report = build_plugin_sandbox_report(fixture["input"], fixture["fixture_id"])

    assert report["overall_status"] == fixture["expected"]["overall_status"]
    assert report["summary"]["platform_continues"] is fixture["expected"]["platform_continues"]
    assert fixture["expected"]["finding_code"] in _codes(report)


def test_plugin_sandbox_schema_registered() -> None:
    schema = json.loads((SCHEMAS / "platform-plugin-sandbox-report.schema.json").read_text(encoding="utf-8"))
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "platform-plugin-sandbox-report"
    assert any(record["record_type"] == "platform-plugin-sandbox-report" for record in registry["records"])


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> set[str]:
    return {finding["code"] for finding in report["findings"]}
