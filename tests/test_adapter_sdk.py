"""Tests for the public adapter SDK contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from hate.adapter_sdk import (
    AdapterDiagnostic,
    AdapterInput,
    AdapterMetadata,
    AdapterParseResult,
    NormalizedRecord,
)


def test_normalized_record_accepts_known_record_kind() -> None:
    record = NormalizedRecord(
        record_kind="test_result",
        payload={"nodeid": "tests/test_example.py::test_ok", "outcome": "passed"},
        source_ref="fixtures/adapters/sdk/valid-manifest/manifest.json",
        source_hash="sha256:abc123",
    )

    assert record.record_kind == "test_result"
    assert record.payload["outcome"] == "passed"
    assert record.source_hash == "sha256:abc123"


def test_normalized_record_rejects_unknown_record_kind() -> None:
    with pytest.raises(ValueError, match="unknown record kind"):
        NormalizedRecord(
            record_kind="invented_record",
            payload={},
            source_ref="fixtures/adapters/sdk/valid-manifest/manifest.json",
        )


def test_normalized_record_requires_source_ref() -> None:
    with pytest.raises(ValueError, match="source_ref is required"):
        NormalizedRecord(record_kind="test_result", payload={}, source_ref="")


def test_parse_result_reports_counts_source_refs_and_warning_diagnostics() -> None:
    record = NormalizedRecord(
        record_kind="coverage_slice",
        payload={"file": "src/hate/p0a.py", "covered": 20, "missing": 2},
        source_ref="coverage.json#/files/src/hate/p0a.py",
    )
    warning = AdapterDiagnostic(
        code="partial_contexts",
        severity="warning",
        message="coverage contexts are present for only some lines",
        source_refs=("coverage.json#/meta",),
    )
    result = AdapterParseResult(
        adapter_id="coveragepy-json",
        parser_version="coveragepy-json/1.0.0",
        records=(record,),
        diagnostics=(warning,),
    )

    assert result.ok is True
    assert result.produced_record_counts() == {"coverage_slice": 1}
    assert result.source_refs() == [
        "coverage.json#/files/src/hate/p0a.py",
        "coverage.json#/meta",
    ]

    entry = result.to_conformance_entry("partial-contexts")
    assert entry["result"] == "pass"
    assert entry["severity"] == "pass"
    assert entry["parserVersion"] == "coveragepy-json/1.0.0"
    assert entry["produced_record_counts"] == {"coverage_slice": 1}
    assert entry["diagnostics"][0]["sourceRefs"] == ["coverage.json#/meta"]


def test_parse_result_error_diagnostic_fails_conformance_entry() -> None:
    error = AdapterDiagnostic(
        code="malformed_input",
        severity="error",
        message="input JSON could not be parsed",
        source_refs=("pytest-report.json",),
    )
    result = AdapterParseResult(
        adapter_id="pytest-json",
        parser_version="pytest-json/1.0.0",
        diagnostics=(error,),
    )

    entry = result.to_conformance_entry("malformed")
    assert result.ok is False
    assert entry["result"] == "fail"
    assert entry["severity"] == "error"
    assert entry["sourceRefs"] == ["pytest-report.json"]


def test_minimal_parser_contract_can_discover_and_parse_inputs(tmp_path: Path) -> None:
    class DummyParser:
        metadata = AdapterMetadata(
            adapter_id="dummy",
            version="0.1.0",
            supported_input_formats=("dummy-json",),
            emitted_record_kinds=("test_result",),
            parser_entrypoint="tests.test_adapter_sdk:DummyParser",
        )

        def discover_inputs(self, root: str) -> list[AdapterInput]:
            return [
                AdapterInput(
                    source_ref=str(Path(root) / "dummy.json"),
                    content='{"ok": true}',
                    input_format="dummy-json",
                )
            ]

        def parse(self, adapter_input: AdapterInput) -> AdapterParseResult:
            assert adapter_input.input_format in self.metadata.supported_input_formats
            record = NormalizedRecord(
                record_kind="test_result",
                payload={"outcome": "passed"},
                source_ref=adapter_input.source_ref,
            )
            return AdapterParseResult(
                adapter_id=self.metadata.adapter_id,
                parser_version=self.metadata.version,
                records=(record,),
            )

    parser = DummyParser()
    [adapter_input] = parser.discover_inputs(str(tmp_path))
    result = parser.parse(adapter_input)

    assert result.adapter_id == "dummy"
    assert result.produced_record_counts() == {"test_result": 1}
