"""Stable adapter SDK contracts for HATE evidence ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence


SUPPORTED_RECORD_KINDS = frozenset(
    {
        "test_result",
        "coverage_slice",
        "static_finding",
        "contract_evidence",
        "mutation_evidence",
        "evidence_strength",
    }
)


@dataclass(frozen=True)
class AdapterDiagnostic:
    code: str
    severity: str
    message: str
    source_refs: tuple[str, ...] = ()

    def to_report(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRefs": list(self.source_refs),
        }


@dataclass(frozen=True)
class AdapterMetadata:
    adapter_id: str
    version: str
    supported_input_formats: tuple[str, ...]
    emitted_record_kinds: tuple[str, ...]
    parser_entrypoint: str
    feature_flags: tuple[str, ...] = ()
    schema_version_min: str = "HATE/v1"
    schema_version_max: str = "HATE/v1"


@dataclass(frozen=True)
class AdapterInput:
    source_ref: str
    content: str | bytes
    input_format: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedRecord:
    record_kind: str
    payload: Mapping[str, Any]
    source_ref: str
    source_hash: str | None = None

    def __post_init__(self) -> None:
        if self.record_kind not in SUPPORTED_RECORD_KINDS:
            raise ValueError(f"unknown record kind: {self.record_kind}")
        if not self.source_ref:
            raise ValueError("source_ref is required")


@dataclass(frozen=True)
class AdapterParseResult:
    adapter_id: str
    parser_version: str
    records: tuple[NormalizedRecord, ...] = ()
    diagnostics: tuple[AdapterDiagnostic, ...] = ()

    @property
    def ok(self) -> bool:
        return not any(d.severity == "error" for d in self.diagnostics)

    def produced_record_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.records:
            counts[record.record_kind] = counts.get(record.record_kind, 0) + 1
        return counts

    def source_refs(self) -> list[str]:
        refs = {record.source_ref for record in self.records}
        for diagnostic in self.diagnostics:
            refs.update(diagnostic.source_refs)
        return sorted(refs)

    def to_conformance_entry(self, fixture_id: str) -> dict[str, Any]:
        severity = "pass" if self.ok else "error"
        return {
            "adapter_id": self.adapter_id,
            "fixture_id": fixture_id,
            "result": "pass" if self.ok else "fail",
            "severity": severity,
            "sourceRefs": self.source_refs(),
            "parserVersion": self.parser_version,
            "produced_record_counts": self.produced_record_counts(),
            "diagnostics": [d.to_report() for d in self.diagnostics],
        }


class AdapterParser(Protocol):
    metadata: AdapterMetadata

    def discover_inputs(self, root: str) -> Sequence[AdapterInput]:
        ...

    def parse(self, adapter_input: AdapterInput) -> AdapterParseResult:
        ...
