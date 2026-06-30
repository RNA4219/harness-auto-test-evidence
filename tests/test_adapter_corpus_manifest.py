"""Tests for HATE-GAP-007 adapter corpus conformance manifest."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from hate.adapters import build_adapter_conformance_report, evaluate_adapter_corpus_fixture
from hate.adapters.corpus_manifest import REQUIRED_FAMILIES


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "corpus" / "manifest"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "adapter-conformance-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"
TODAY = date(2026, 6, 30)


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _family(name: str, **overrides) -> dict:
    requirement = REQUIRED_FAMILIES[name]
    family = {
        "family": name,
        "adapter_id": f"{name}-adapter",
        "dialects": sorted(requirement["dialects"]),
        "fixture_paths": [f"fixtures/adapters/{name}/input.json"],
        "positive_count": requirement["positive_minimum"],
        "negative_count": requirement["negative_minimum"],
        "malformed_count": 1,
        "partial_count": 1,
        "path_normalization_count": 1,
        "metadata_preservation_count": 1,
        "expected_output_ref": f"fixtures/adapters/{name}/expected/HATE-output.ndjson",
        "reviewed_at": "2026-06-30",
        "review_owner": "Developer Platform",
        "stale_after_days": 30,
        "unsupported_claims": [],
        "sourceRefs": [f"fixtures/adapters/{name}"],
    }
    family.update(overrides)
    return family


def _manifest(**family_overrides) -> dict:
    families = []
    for name in REQUIRED_FAMILIES:
        families.append(_family(name, **family_overrides.get(name, {})))
    return {"manifest_id": "test-adapter-corpus", "family_manifests": families}


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "adapter-conformance-report"
    assert report["required_family_count"] == len(REQUIRED_FAMILIES)
    assert report["status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert isinstance(report["sourceRefs"], list)
    for summary in report["family_summaries"]:
        assert set(schema["properties"]["family_summaries"]["items"]["required"]) <= set(summary)
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_minimum_dialects_fixture_passes() -> None:
    result = evaluate_adapter_corpus_fixture(_fixture("minimum-dialects"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    report = result["report"]
    _assert_report_contract(report)
    assert report["observed_family_count"] == 6
    assert {family["family"] for family in report["family_summaries"]} == set(REQUIRED_FAMILIES)


def test_stale_fixture_review_is_hold() -> None:
    result = evaluate_adapter_corpus_fixture(_fixture("stale-fixture"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "adapter_corpus_stale_fixture"
    assert result["report"]["findings"][0]["severity"] == "high"


def test_missing_family_is_hold() -> None:
    manifest = _manifest()
    manifest["family_manifests"] = [
        family for family in manifest["family_manifests"] if family["family"] != "artifacts"
    ]

    report = build_adapter_conformance_report(manifest, today=TODAY)

    assert report["status"] == "hold"
    assert _codes(report) == ["adapter_corpus_family_missing"]


def test_missing_dialect_is_hold() -> None:
    report = build_adapter_conformance_report(
        _manifest(**{"test-results": {"dialects": ["junit", "pytest-json"]}}),
        today=TODAY,
    )

    assert report["status"] == "hold"
    assert "adapter_corpus_dialect_missing" in _codes(report)


def test_fixture_count_below_minimum_is_hold() -> None:
    report = build_adapter_conformance_report(
        _manifest(coverage={"positive_count": 1, "negative_count": 1}),
        today=TODAY,
    )

    assert report["status"] == "hold"
    assert "adapter_corpus_fixture_count_below_minimum" in _codes(report)


def test_unsupported_capability_claim_is_hold() -> None:
    report = build_adapter_conformance_report(
        _manifest(mutation={"unsupported_claims": ["mutation-kill-attribution-without-source"]}),
        today=TODAY,
    )

    assert report["status"] == "hold"
    assert "adapter_corpus_unsupported_claim" in _codes(report)


def test_expected_output_ref_is_required() -> None:
    report = build_adapter_conformance_report(
        _manifest(contract={"expected_output_ref": ""}),
        today=TODAY,
    )

    assert report["status"] == "hold"
    assert "adapter_corpus_expected_output_missing" in _codes(report)


def test_expired_review_date_is_stale() -> None:
    report = build_adapter_conformance_report(
        _manifest(static={"reviewed_at": "2026-01-01", "stale_after_days": 30}),
        today=TODAY,
    )

    assert report["status"] == "hold"
    assert "adapter_corpus_stale_fixture" in _codes(report)


def test_report_includes_source_refs_and_family_summaries() -> None:
    report = build_adapter_conformance_report(_manifest(), source_refs=["adapter-corpus-manifest.json"], today=TODAY)

    assert report["status"] == "pass"
    assert "adapter-corpus-manifest.json" in report["sourceRefs"]
    assert "fixtures/adapters/test-results" in report["sourceRefs"]
    assert len(report["family_summaries"]) == len(REQUIRED_FAMILIES)


def test_adapter_conformance_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["adapter-conformance-report"] == "schemas/HATE/v1/adapter-conformance-report.schema.json"


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]
