from __future__ import annotations

import copy
import json
from pathlib import Path

from hate.schema_validator import build_schema_validation_report, validate_record, validate_records
from hate.cross_record_validator import validate_cross_record_bundle


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


def test_registry_entries_define_unknown_and_deprecated_field_policy() -> None:
    registry = json.loads((ROOT / "schemas/HATE/v1/schema-registry.json").read_text(encoding="utf-8"))

    for entry in registry["records"]:
        assert entry["unknown_field_policy"] in {"preserve_without_summary", "warn", "reject"}
        assert isinstance(entry["deprecated_fields"], list)


def test_unknown_field_warn_policy_preserves_record_with_warning(tmp_path: Path) -> None:
    record = copy.deepcopy(load_fixture("valid-test-result"))
    record["unexpected_vendor_field"] = "kept for forward compatibility"
    _write_registry_fixture(tmp_path, unknown_field_policy="warn")

    result = validate_record(record, schema_root=tmp_path)

    assert result.accepted is True
    assert "unknown_field_preserved" in finding_codes(result)
    assert {finding.severity for finding in result.findings if finding.code == "unknown_field_preserved"} == {"warn"}


def test_unknown_field_reject_policy_blocks_record(tmp_path: Path) -> None:
    record = copy.deepcopy(load_fixture("valid-test-result"))
    record["unexpected_vendor_field"] = "blocked by registry policy"
    _write_registry_fixture(tmp_path, unknown_field_policy="reject")

    result = validate_record(record, schema_root=tmp_path)

    assert result.accepted is False
    assert "unknown_field_rejected" in finding_codes(result)


def test_deprecated_field_policy_warns_without_rejecting(tmp_path: Path) -> None:
    record = copy.deepcopy(load_fixture("valid-test-result"))
    record["legacy_status"] = "old"
    _write_registry_fixture(
        tmp_path,
        unknown_field_policy="preserve_without_summary",
        deprecated_fields=[{
            "field": "legacy_status",
            "deprecated_since": "HATE/v1",
            "remove_after": "HATE/v2",
            "replacement": "payload.status",
        }],
    )

    result = validate_record(record, schema_root=tmp_path)

    assert result.accepted is True
    assert "deprecated_field_used" in finding_codes(result)
    warning = next(finding for finding in result.findings if finding.code == "deprecated_field_used")
    assert warning.severity == "warn"
    assert "payload.status" in warning.message


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
    assert report["summary"]["warnings"] == 0
    assert report["summary"]["rejection_classes"] == {
        "invalid_timestamp": 1,
        "missing_source_ref": 1,
        "unredacted_secret": 1,
    }
    assert report["summary"]["warning_classes"] == {}
    assert report["summary"]["schema_versions"] == ["HATE/v1"]
    assert report["results"][0]["sourceRefs"] == ["pytest-report.json#/tests/0"]
    assert report["cross_record"] == {"violation_count": 0, "violations": []}


def test_schema_validation_report_embeds_cross_record_violations() -> None:
    bundle = _read_cross_record_bundle("hash-mismatch")
    results = validate_records(bundle["records"])
    report = build_schema_validation_report(
        results,
        fixture_id="HATE-PG-002B",
        cross_record_violations=validate_cross_record_bundle(bundle),
    )

    assert report["summary"]["accepted"] == 0
    assert report["summary"]["rejected"] == 1
    assert report["summary"]["cross_record_violation_count"] == 1
    assert report["summary"]["rejection_classes"]["hash_mismatch"] == 1
    assert report["cross_record"]["violations"][0]["affected_record_ids"] == ["hash-mismatch-1"]
    assert report["cross_record"]["violations"][0]["severity"] == "hard"


def _write_registry_fixture(
    schema_root: Path,
    *,
    unknown_field_policy: str,
    deprecated_fields: list[dict] | None = None,
) -> None:
    (schema_root / "schema-registry.json").write_text(
        json.dumps({
            "schema_version": "HATE/v1",
            "registry_version": "test",
            "records": [{
                "record_type": "test_result",
                "schema": "schemas/HATE/v1/test-result.schema.json",
                "phase": "P1a",
                "unknown_field_policy": unknown_field_policy,
                "deprecated_fields": deprecated_fields or [],
            }],
        }),
        encoding="utf-8",
    )
    (schema_root / "test-result.schema.json").write_text(
        json.dumps({"type": "object", "additionalProperties": True}),
        encoding="utf-8",
    )


def _read_cross_record_bundle(name: str) -> dict:
    with (ROOT / "fixtures/schema/cross-record" / name / "bundle.json").open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    assert isinstance(data, dict)
    return data
