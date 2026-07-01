"""Adapter manifest validation and conformance reporting."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .adapter_sdk import SUPPORTED_RECORD_KINDS

SUPPORTED_MANIFEST_SCHEMA = "HATE.adapter-manifest/v1"
SUPPORTED_HATE_SCHEMA = "HATE/v1"
REQUIRED_FIELDS = (
    "adapter_id",
    "version",
    "supported_input_formats",
    "emitted_record_kinds",
    "schema_version_range",
    "parser_entrypoint",
    "feature_flags",
    "conformance_fixtures",
)
ENTRYPOINT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class ManifestFinding:
    code: str
    severity: str
    message: str
    source_ref: str

    def to_report(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRef": self.source_ref,
        }


def load_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        raise ValueError(f"manifest must be a JSON object: {manifest_path}")
    return manifest


def validate_manifest(
    manifest: Mapping[str, Any],
    *,
    source_ref: str = "manifest.json",
) -> list[ManifestFinding]:
    findings: list[ManifestFinding] = []
    for field in REQUIRED_FIELDS:
        if field not in manifest:
            findings.append(_finding("missing_required", f"missing required field: {field}", source_ref, field))
    if findings:
        return findings

    if manifest.get("manifest_schema_version") not in (None, SUPPORTED_MANIFEST_SCHEMA):
        findings.append(
            _finding(
                "unsupported_manifest_schema",
                f"unsupported manifest schema: {manifest.get('manifest_schema_version')}",
                source_ref,
                "manifest_schema_version",
            )
        )

    adapter_id = manifest.get("adapter_id")
    if not isinstance(adapter_id, str) or not adapter_id:
        findings.append(_finding("invalid_adapter_id", "adapter_id must be a non-empty string", source_ref, "adapter_id"))

    if not _is_str_list(manifest.get("supported_input_formats")):
        findings.append(
            _finding(
                "invalid_input_formats",
                "supported_input_formats must be a non-empty string array",
                source_ref,
                "supported_input_formats",
            )
        )

    emitted = manifest.get("emitted_record_kinds")
    if not _is_str_list(emitted):
        findings.append(
            _finding(
                "invalid_emitted_records",
                "emitted_record_kinds must be a non-empty string array",
                source_ref,
                "emitted_record_kinds",
            )
        )
    else:
        for record_kind in emitted:
            if record_kind not in SUPPORTED_RECORD_KINDS:
                findings.append(
                    _finding(
                        "unknown_output_record",
                        f"unknown output record kind: {record_kind}",
                        source_ref,
                        f"emitted_record_kinds.{record_kind}",
                    )
                )

    schema_range = manifest.get("schema_version_range")
    if not isinstance(schema_range, Mapping):
        findings.append(
            _finding("invalid_schema_range", "schema_version_range must be an object", source_ref, "schema_version_range")
        )
    elif schema_range.get("min") != SUPPORTED_HATE_SCHEMA or schema_range.get("max") != SUPPORTED_HATE_SCHEMA:
        findings.append(
            _finding(
                "unsupported_schema_version",
                "schema_version_range must include HATE/v1",
                source_ref,
                "schema_version_range",
            )
        )

    entrypoint = manifest.get("parser_entrypoint")
    if not isinstance(entrypoint, str) or not ENTRYPOINT_RE.match(entrypoint):
        findings.append(
            _finding(
                "invalid_parser_entrypoint",
                "parser_entrypoint must use module.path:function syntax",
                source_ref,
                "parser_entrypoint",
            )
        )

    if not _is_str_list(manifest.get("feature_flags"), allow_empty=True):
        findings.append(_finding("invalid_feature_flags", "feature_flags must be a string array", source_ref, "feature_flags"))

    findings.extend(_validate_fixture_map(manifest, source_ref))
    return findings


def load_manifests(paths: Iterable[str | Path]) -> tuple[list[dict[str, Any]], list[ManifestFinding]]:
    manifests: list[dict[str, Any]] = []
    findings: list[ManifestFinding] = []
    seen: dict[str, str] = {}
    for manifest_path in paths:
        path = Path(manifest_path)
        try:
            manifest = load_manifest(path)
        except Exception as exc:  # noqa: BLE001 - surfaced as deterministic finding
            findings.append(_finding("manifest_parse_error", str(exc), str(path), "$"))
            continue
        source_ref = str(path)
        findings.extend(validate_manifest(manifest, source_ref=source_ref))
        adapter_id = manifest.get("adapter_id")
        if isinstance(adapter_id, str):
            if adapter_id in seen:
                findings.append(
                    _finding(
                        "duplicate_adapter_id",
                        f"duplicate adapter_id {adapter_id}: {seen[adapter_id]} and {source_ref}",
                        source_ref,
                        "adapter_id",
                    )
                )
            seen[adapter_id] = source_ref
        manifests.append(manifest)
    return manifests, findings


def build_conformance_report(
    manifests: Iterable[Mapping[str, Any]],
    *,
    manifest_findings: Iterable[ManifestFinding] = (),
    parser_version: str = "adapter-registry/1.0.0",
) -> dict[str, Any]:
    manifest_list = list(manifests)
    entries: list[dict[str, Any]] = []
    all_findings = list(manifest_findings)
    for manifest in manifest_list:
        adapter_id = str(manifest.get("adapter_id", "unknown"))
        fixture_map = manifest.get("conformance_fixtures", {})
        if isinstance(fixture_map, Mapping):
            for fixture_id in sorted(fixture_map):
                entries.append(
                    {
                        "adapter_id": adapter_id,
                        "fixture_id": fixture_id,
                        "result": "pass",
                        "severity": "pass",
                        "sourceRefs": [f"manifest:{adapter_id}:conformance_fixtures.{fixture_id}"],
                        "parserVersion": parser_version,
                        "produced_record_counts": {
                            record_kind: 0 for record_kind in manifest.get("emitted_record_kinds", [])
                        },
                    }
                )
    return {
        "schema_version": "HATE/v1",
        "record_type": "adapter-conformance-report",
        "manifest_id": "adapter-sdk-manifest-set",
        "parserVersion": parser_version,
        "result": "fail" if all_findings else "pass",
        "required_family_count": len(manifest_list),
        "observed_family_count": len({entry["adapter_id"] for entry in entries}),
        "family_summaries": [],
        "entries": entries,
        "findings": [
            {
                **finding.to_report(),
                "readiness_effect": "hold",
            }
            for finding in all_findings
        ],
        "status": "hold" if all_findings else "pass",
        "readiness_effect": "hold" if all_findings else "none",
        "sourceRefs": sorted({ref for entry in entries for ref in entry["sourceRefs"]} | {finding.source_ref for finding in all_findings}),
    }


def _validate_fixture_map(manifest: Mapping[str, Any], source_ref: str) -> list[ManifestFinding]:
    findings: list[ManifestFinding] = []
    fixture_map = manifest.get("conformance_fixtures")
    emitted = set(manifest.get("emitted_record_kinds", []))
    if not isinstance(fixture_map, Mapping) or not fixture_map:
        return [_finding("missing_conformance_fixtures", "conformance_fixtures must be a non-empty object", source_ref, "conformance_fixtures")]
    for fixture_id, fixture in fixture_map.items():
        if not isinstance(fixture, Mapping):
            findings.append(_finding("invalid_fixture", f"fixture {fixture_id} must be an object", source_ref, f"conformance_fixtures.{fixture_id}"))
            continue
        expected = fixture.get("expected_record_kinds", [])
        if not _is_str_list(expected, allow_empty=True):
            findings.append(_finding("invalid_fixture_records", f"fixture {fixture_id} expected_record_kinds must be a string array", source_ref, f"conformance_fixtures.{fixture_id}.expected_record_kinds"))
            continue
        for record_kind in expected:
            if record_kind not in emitted:
                findings.append(
                    _finding(
                        "capability_mismatch",
                        f"fixture {fixture_id} expects undeclared record kind: {record_kind}",
                        source_ref,
                        f"conformance_fixtures.{fixture_id}.expected_record_kinds",
                    )
                )
    return findings


def _is_str_list(value: Any, *, allow_empty: bool = False) -> bool:
    return isinstance(value, list) and (allow_empty or bool(value)) and all(isinstance(item, str) and item for item in value)


def _finding(code: str, message: str, source_ref: str, pointer: str) -> ManifestFinding:
    return ManifestFinding(code=code, severity="error", message=message, source_ref=f"{source_ref}#{pointer}")
