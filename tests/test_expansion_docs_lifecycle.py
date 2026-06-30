"""Tests for HATE-GAP-033 documentation lifecycle evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.expansion.docs_lifecycle import build_docs_lifecycle_report, evaluate_docs_lifecycle_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "docs-lifecycle"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "docs-lifecycle-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "docs-lifecycle-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_033_fixture_paths_exist() -> None:
    assert (FIXTURES / "version-bound-docs" / "fixture.json").is_file()
    assert (FIXTURES / "stale-claim-denied" / "fixture.json").is_file()


def test_version_bound_docs_fixture_passes() -> None:
    result = evaluate_docs_lifecycle_fixture(_fixture("version-bound-docs"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_stale_claim_denied_fixture_holds() -> None:
    result = evaluate_docs_lifecycle_fixture(_fixture("stale-claim-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "docs_lifecycle_stale_claim_denied"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_required_docs_definition_holds() -> None:
    report = build_docs_lifecycle_report({
        "required_docs_defined": False,
        "version_binding_enforced": True,
        "broken_ref_detection_enabled": True,
        "stale_doc_max_age_days": 90,
        "required_docs": ["getting-started.md"],
        "doc_claim_stale": False,
        "doc_age_days": 30,
        "broken_refs": [],
        "version_bound": True,
    })

    assert report["overall_status"] == "hold"
    assert "docs_lifecycle_required_docs_missing" in _codes(report)


def test_missing_version_binding_holds() -> None:
    report = build_docs_lifecycle_report({
        "required_docs_defined": True,
        "version_binding_enforced": False,
        "broken_ref_detection_enabled": True,
        "stale_doc_max_age_days": 90,
        "required_docs": ["getting-started.md"],
        "doc_claim_stale": False,
        "doc_age_days": 30,
        "broken_refs": [],
        "version_bound": True,
    })

    assert report["overall_status"] == "hold"
    assert "docs_lifecycle_version_binding_missing" in _codes(report)


def test_broken_refs_found_holds() -> None:
    report = build_docs_lifecycle_report({
        "required_docs_defined": True,
        "version_binding_enforced": True,
        "broken_ref_detection_enabled": True,
        "stale_doc_max_age_days": 90,
        "required_docs": ["getting-started.md"],
        "doc_claim_stale": False,
        "doc_age_days": 30,
        "broken_refs": ["api-reference.md"],
        "version_bound": True,
    })

    assert report["overall_status"] == "hold"
    assert "docs_lifecycle_broken_refs_found" in _codes(report)


def test_doc_age_exceeds_max_age_holds() -> None:
    report = build_docs_lifecycle_report({
        "required_docs_defined": True,
        "version_binding_enforced": True,
        "broken_ref_detection_enabled": True,
        "stale_doc_max_age_days": 90,
        "required_docs": ["getting-started.md"],
        "doc_claim_stale": False,
        "doc_age_days": 120,
        "broken_refs": [],
        "version_bound": True,
    })

    assert report["overall_status"] == "hold"
    assert "docs_lifecycle_doc_exceeded_max_age" in _codes(report)


def test_docs_lifecycle_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["docs-lifecycle-report"] == "schemas/HATE/v1/docs-lifecycle-report.schema.json"
