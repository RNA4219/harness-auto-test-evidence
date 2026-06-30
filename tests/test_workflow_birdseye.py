"""Tests for HATE-GAP-024 workflow Birdseye freshness evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.workflow_birdseye import build_birdseye_freshness_report, evaluate_birdseye_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "workflow" / "birdseye"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "workflow-birdseye-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "workflow-birdseye-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_024_fixture_paths_exist() -> None:
    assert (FIXTURES / "fresh-index" / "fixture.json").is_file()
    assert (FIXTURES / "stale-capsule" / "fixture.json").is_file()


def test_fresh_index_fixture_passes() -> None:
    result = evaluate_birdseye_fixture(_fixture("fresh-index"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_stale_capsule_fixture_holds() -> None:
    result = evaluate_birdseye_fixture(_fixture("stale-capsule"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "birdseye_stale_or_incomplete"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_index_holds() -> None:
    report = build_birdseye_freshness_report({"birdseye": {"index_exists": False}})

    assert report["overall_status"] == "hold"
    assert "birdseye_stale_or_incomplete" in _codes(report)


def test_node_count_mismatch_holds() -> None:
    report = build_birdseye_freshness_report({"birdseye": {"node_count_matches_caps": False}})

    assert report["overall_status"] == "hold"
    assert "birdseye_stale_or_incomplete" in _codes(report)


def test_generated_at_mismatch_holds() -> None:
    report = build_birdseye_freshness_report({"birdseye": {"generated_at_matches": False}})

    assert report["overall_status"] == "hold"
    assert "birdseye_stale_or_incomplete" in _codes(report)


def test_product_ready_claim_with_stale_map_holds() -> None:
    report = build_birdseye_freshness_report({
        "birdseye": {
            "product_ready_claim": True,
            "docs_schema_fixture_map_fresh": False,
        }
    })

    assert report["overall_status"] == "hold"
    assert "birdseye_product_ready_claim_stale" in _codes(report)


def test_emergency_patch_stale_requires_exception_record() -> None:
    report = build_birdseye_freshness_report({
        "birdseye": {
            "context": "emergency_patch",
            "readme_matches_index": False,
            "explicit_exception_record": False,
        }
    })

    assert report["overall_status"] == "hold"
    assert "birdseye_emergency_exception_missing" in _codes(report)


def test_emergency_patch_with_exception_keeps_stale_hold_but_no_exception_finding() -> None:
    report = build_birdseye_freshness_report({
        "birdseye": {
            "context": "emergency_patch",
            "readme_matches_index": False,
            "explicit_exception_record": True,
        }
    })

    assert report["overall_status"] == "hold"
    assert "birdseye_stale_or_incomplete" in _codes(report)
    assert "birdseye_emergency_exception_missing" not in _codes(report)


def test_workflow_birdseye_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["workflow-birdseye-report"] == "schemas/HATE/v1/workflow-birdseye-report.schema.json"
