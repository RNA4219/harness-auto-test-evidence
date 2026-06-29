from __future__ import annotations

import json
from pathlib import Path

from hate.cross_record_validator import build_cross_record_report, validate_cross_record_bundle
from hate.source_ref import deterministic_record_id, normalize_path, parse_source_ref


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "schema" / "cross-record"


def load_bundle(name: str) -> dict:
    with (FIXTURES / name / "bundle.json").open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    assert isinstance(data, dict)
    return data


def codes(bundle_name: str) -> set[str]:
    return {violation.code for violation in validate_cross_record_bundle(load_bundle(bundle_name))}


def test_matching_test_coverage_source_is_accepted() -> None:
    assert validate_cross_record_bundle(load_bundle("matching-test-coverage-source")) == []


def test_matching_static_finding_file_is_accepted() -> None:
    assert validate_cross_record_bundle(load_bundle("matching-finding-changed-file")) == []


def test_container_and_windows_paths_normalize_to_bundle_paths() -> None:
    assert normalize_path("/workspace/repo/src/app.py") == "src/app.py"
    assert normalize_path(r"C:\repo\tests\test_sample.py") == "tests/test_sample.py"
    assert validate_cross_record_bundle(load_bundle("container-path-normalized")) == []
    assert validate_cross_record_bundle(load_bundle("windows-path-normalized")) == []


def test_replayed_bundle_has_stable_record_id() -> None:
    bundle = load_bundle("replayed-bundle-stable")
    record = bundle["records"][0]

    assert record["record_id"] == deterministic_record_id(record, ["tests/test_sample.py#L1"])
    assert validate_cross_record_bundle(bundle) == []


def test_hash_mismatch_is_hard_violation() -> None:
    assert codes("hash-mismatch") == {"hash_mismatch"}


def test_missing_source_artifact_is_hard_violation() -> None:
    assert codes("missing-source-artifact") == {"missing_source_artifact"}


def test_path_traversal_source_ref_is_rejected() -> None:
    ref = parse_source_ref("../secrets.env#L1")

    assert ref.has_traversal is True
    assert codes("path-traversal-source-ref") == {"path_traversal_source_ref", "finding_refers_unknown_file"}


def test_coverage_refers_unknown_test_is_rejected() -> None:
    assert codes("coverage-refers-unknown-test") == {"coverage_refers_unknown_test"}


def test_finding_refers_unknown_file_is_rejected() -> None:
    assert codes("finding-refers-unknown-file") == {"finding_refers_unknown_file"}


def test_non_deterministic_record_id_is_rejected() -> None:
    assert codes("non-deterministic-record-id") == {"non_deterministic_record_id"}


def test_cross_record_report_has_stable_violation_order_and_source_refs() -> None:
    report = build_cross_record_report(load_bundle("hash-mismatch"), fixture_id="HATE-PG-002B")

    assert report["record_type"] == "schema_validation_report"
    assert report["summary"]["accepted"] == 0
    assert report["summary"]["rejected"] == 1
    assert report["summary"]["rejection_classes"] == {"hash_mismatch": 1}
    assert report["cross_record"]["violation_count"] == 1
    assert report["cross_record"]["violations"][0]["severity"] == "hard"
    assert report["cross_record"]["violations"][0]["affected_record_ids"] == ["hash-mismatch-1"]
    assert report["cross_record"]["violations"][0]["sourceRef"] == "src/app.py#L1"
