"""Tests for HATE-GAP-058 audience report pack evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.analysis.audience_report_pack import (
    build_audience_report_pack,
    evaluate_audience_report_pack_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "expansion" / "audience-report-pack"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "audience-report-pack.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "audience-report-pack"
    assert report["overall_status"] in {"pass", "hold", "blocked"}
    assert report["readiness_effect"] in {"none", "hold", "blocked"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_058_fixture_paths_exist() -> None:
    assert (FIXTURES / "shared-sourcerefs-pass" / "fixture.json").is_file()
    assert (FIXTURES / "verdict-recomputed-denied" / "fixture.json").is_file()


def test_shared_sourcerefs_fixture_passes() -> None:
    result = evaluate_audience_report_pack_fixture(_fixture("shared-sourcerefs-pass"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])


def test_verdict_recomputed_fixture_holds() -> None:
    result = evaluate_audience_report_pack_fixture(_fixture("verdict-recomputed-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "audience_report_pack_verdict_recomputed_denied"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_source_ref_drift_detected_holds() -> None:
    report = build_audience_report_pack({
        "audience_views": [{"audience_id": "a1", "view_type": "technical", "verdict": "pass", "sourceRef": "v:1", "rationale": ""}],
        "shared_sourceRefs": ["e:1"],
        "verdict_recomputed": False,
        "source_ref_drift_detected": True,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_views": 10, "max_sourceRefs": 50},
    })

    assert report["overall_status"] == "hold"
    assert "audience_report_pack_source_ref_drift" in _codes(report)


def test_view_without_source_ref_holds() -> None:
    report = build_audience_report_pack({
        "audience_views": [{"audience_id": "a1", "view_type": "technical", "verdict": "pass", "sourceRef": "", "rationale": ""}],
        "shared_sourceRefs": ["e:1"],
        "verdict_recomputed": False,
        "source_ref_drift_detected": False,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_views": 10, "max_sourceRefs": 50},
    })

    assert report["overall_status"] == "hold"
    assert "audience_report_pack_view_missing" in _codes(report)


def test_view_without_verdict_holds() -> None:
    report = build_audience_report_pack({
        "audience_views": [{"audience_id": "a1", "view_type": "technical", "verdict": "", "sourceRef": "v:1", "rationale": ""}],
        "shared_sourceRefs": ["e:1"],
        "verdict_recomputed": False,
        "source_ref_drift_detected": False,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_views": 10, "max_sourceRefs": 50},
    })

    assert report["overall_status"] == "hold"
    assert "audience_report_pack_view_missing" in _codes(report)


def test_empty_shared_sourceRefs_holds() -> None:
    report = build_audience_report_pack({
        "audience_views": [{"audience_id": "a1", "view_type": "technical", "verdict": "pass", "sourceRef": "v:1", "rationale": ""}],
        "shared_sourceRefs": [],
        "verdict_recomputed": False,
        "source_ref_drift_detected": False,
        "confidence": 0.95,
        "limits": {"confidence_threshold": 0.7, "max_views": 10, "max_sourceRefs": 50},
    })

    assert report["overall_status"] == "hold"
    assert "audience_report_pack_view_missing" in _codes(report)


def test_confidence_below_threshold_holds() -> None:
    report = build_audience_report_pack({
        "audience_views": [{"audience_id": "a1", "view_type": "technical", "verdict": "pass", "sourceRef": "v:1", "rationale": ""}],
        "shared_sourceRefs": ["e:1"],
        "verdict_recomputed": False,
        "source_ref_drift_detected": False,
        "confidence": 0.5,
        "limits": {"confidence_threshold": 0.7, "max_views": 10, "max_sourceRefs": 50},
    })

    assert report["overall_status"] == "hold"
    assert "audience_report_pack_verdict_recomputed_denied" in _codes(report)


def test_audience_report_pack_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["audience-report-pack"] == "schemas/HATE/v1/audience-report-pack.schema.json"