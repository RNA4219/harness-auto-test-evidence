from __future__ import annotations

import copy
import json
from pathlib import Path

from hate.schema_validator import build_schema_validation_report, validate_record, validate_records


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "schema" / "envelope"


def load_fixture(name: str) -> dict:
    with (FIXTURES / name / "record.json").open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    assert isinstance(data, dict)
    return data


def finding_codes(result) -> set[str]:
    return {finding.code for finding in result.findings}


def test_valid_envelope_fixtures_are_accepted() -> None:
    fixture_names = [
        "valid-test-result",
        "valid-coverage-slice",
        "valid-static-finding",
        "valid-contract-evidence",
        "valid-mutation-evidence",
    ]

    results = validate_records([load_fixture(name) for name in fixture_names], source_ref="fixtures/schema/envelope")

    assert [result.record_kind for result in results] == [
        "test_result",
        "coverage_slice",
        "static_finding",
        "contract_evidence",
        "mutation_evidence",
    ]
    assert all(result.accepted for result in results)
    assert all(result.sourceRefs for result in results)


def test_record_kind_schema_dispatch_rejects_mismatched_payload() -> None:
    result = validate_record(load_fixture("record-kind-schema-mismatch"))

    assert result.accepted is False
    assert "record_kind_schema_mismatch" in finding_codes(result)
    assert result.schema_ref == "coverage-slice.schema.json"


def test_unknown_schema_version_is_rejected() -> None:
    result = validate_record(load_fixture("unknown-schema-version"))

    assert result.accepted is False
    assert "unknown_schema_version" in finding_codes(result)


def test_missing_record_kind_is_rejected() -> None:
    result = validate_record(load_fixture("missing-record-kind"))

    assert result.accepted is False
    assert "missing_record_kind" in finding_codes(result)


def test_missing_source_ref_is_rejected() -> None:
    result = validate_record(load_fixture("missing-source-ref"))

    assert result.accepted is False
    assert "missing_source_ref" in finding_codes(result)


def test_invalid_timestamp_is_rejected() -> None:
    result = validate_record(load_fixture("invalid-timestamp"))

    assert result.accepted is False
    assert "invalid_timestamp" in finding_codes(result)


def test_secret_like_values_are_rejected() -> None:
    result = validate_record(load_fixture("unredacted-secret"))

    assert result.accepted is False
    assert "unredacted_secret" in finding_codes(result)


def test_unknown_record_kind_is_rejected() -> None:
    record = copy.deepcopy(load_fixture("valid-static-finding"))
    record["record_kind"] = "unknown_evidence"
    record["record_type"] = "unknown_evidence"

    result = validate_record(record)

    assert result.accepted is False
    assert "unknown_record_kind" in finding_codes(result)


def test_missing_registry_schema_file_is_rejected(tmp_path: Path) -> None:
    result = validate_record(load_fixture("valid-test-result"), schema_root=tmp_path)

    assert result.accepted is False
    assert "schema_registry_missing_file" in finding_codes(result)


def test_schema_validation_report_counts_rejections_and_source_refs() -> None:
    records = [
        load_fixture("valid-test-result"),
        load_fixture("valid-coverage-slice"),
        load_fixture("missing-source-ref"),
        load_fixture("invalid-timestamp"),
        load_fixture("unredacted-secret"),
    ]

    report = build_schema_validation_report(validate_records(records), fixture_id="HATE-PG-002A")

    assert report["record_type"] == "schema_validation_report"
    assert report["summary"]["accepted"] == 2
    assert report["summary"]["rejected"] == 3
    assert report["summary"]["rejection_classes"] == {
        "invalid_timestamp": 1,
        "missing_source_ref": 1,
        "unredacted_secret": 1,
    }
    assert report["summary"]["schema_versions"] == ["HATE/v1"]
    assert report["results"][0]["sourceRefs"] == ["pytest-report.json#/tests/0"]
