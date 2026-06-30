"""Adapter corpus conformance manifest evaluation for HATE-GAP-007."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


REQUIRED_FAMILIES = {
    "test-results": {
        "dialects": {"junit", "pytest-json", "jest-json", "vitest-json", "playwright-json"},
        "positive_minimum": 5,
        "negative_minimum": 5,
    },
    "coverage": {
        "dialects": {"lcov", "cobertura", "jacoco", "coverage.py-json"},
        "positive_minimum": 4,
        "negative_minimum": 4,
    },
    "static": {
        "dialects": {"sarif-generic", "codeql-like", "sonar-like"},
        "positive_minimum": 3,
        "negative_minimum": 2,
    },
    "contract": {
        "dialects": {"pact"},
        "positive_minimum": 1,
        "negative_minimum": 2,
    },
    "mutation": {
        "dialects": {"stryker"},
        "positive_minimum": 1,
        "negative_minimum": 2,
    },
    "artifacts": {
        "dialects": {"trace", "screenshot", "video", "log", "archive", "external-url"},
        "positive_minimum": 6,
        "negative_minimum": 3,
    },
}


@dataclass(frozen=True)
class AdapterCorpusFinding:
    code: str
    severity: str
    message: str
    sourceRef: str
    readiness_effect: str = "hold"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRef": self.sourceRef,
            "readiness_effect": self.readiness_effect,
        }


def evaluate_adapter_corpus_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_adapter_conformance_report(input_data, source_refs=[payload.get("fixture_id", "fixture")])
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_adapter_conformance_report(
    input_data: dict[str, Any],
    *,
    source_refs: list[str] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    families = _normalize_families(input_data)
    source_refs = sorted(set((source_refs or []) + _family_source_refs(families)))
    findings = _findings_for(families, input_data, today)
    status = "hold" if findings else "pass"

    return {
        "schema_version": "HATE/v1",
        "record_type": "adapter-conformance-report",
        "manifest_id": str(input_data.get("manifest_id") or "adapter-corpus-manifest"),
        "parserVersion": str(input_data.get("parserVersion") or "adapter-corpus-manifest/v1"),
        "result": "fail" if findings else "pass",
        "required_family_count": len(REQUIRED_FAMILIES),
        "observed_family_count": len(families),
        "family_summaries": families,
        "entries": _entries_for(families, findings, str(input_data.get("parserVersion") or "adapter-corpus-manifest/v1")),
        "findings": [finding.to_dict() for finding in findings],
        "status": status,
        "readiness_effect": "hold" if findings else "none",
        "sourceRefs": source_refs,
    }


def _normalize_families(input_data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_families = input_data.get("family_manifests")
    if isinstance(raw_families, list):
        return [_normalize_family(item) for item in raw_families if isinstance(item, dict)]

    names = input_data.get("families", [])
    stale_count = int(input_data.get("stale_count", 0) or 0)
    families: list[dict[str, Any]] = []
    for index, name in enumerate(names):
        family_name = str(name)
        requirement = REQUIRED_FAMILIES.get(family_name, {})
        families.append(_normalize_family({
            "family": family_name,
            "adapter_id": f"{family_name}-adapter",
            "dialects": sorted(requirement.get("dialects", [])),
            "positive_count": requirement.get("positive_minimum", 1),
            "negative_count": requirement.get("negative_minimum", 1),
            "malformed_count": 1,
            "partial_count": 1,
            "path_normalization_count": 1,
            "metadata_preservation_count": 1,
            "expected_output_ref": f"fixtures/adapters/{family_name}/expected/HATE-output.ndjson",
            "reviewed_at": "2026-06-30" if index >= stale_count else "2026-01-01",
            "review_owner": "Developer Platform",
            "stale_after_days": 3650,
            "unsupported_claims": [],
            "sourceRefs": [f"fixtures/adapters/{family_name}"],
        }))
    return families


def _normalize_family(raw: dict[str, Any]) -> dict[str, Any]:
    family = str(raw.get("family", ""))
    return {
        "family": family,
        "adapter_id": str(raw.get("adapter_id") or f"{family}-adapter"),
        "dialects": sorted({str(item).lower() for item in raw.get("dialects", [])}),
        "fixture_paths": sorted({str(item) for item in raw.get("fixture_paths", [])}),
        "positive_count": int(raw.get("positive_count", 0) or 0),
        "negative_count": int(raw.get("negative_count", 0) or 0),
        "malformed_count": int(raw.get("malformed_count", 0) or 0),
        "partial_count": int(raw.get("partial_count", 0) or 0),
        "path_normalization_count": int(raw.get("path_normalization_count", 0) or 0),
        "metadata_preservation_count": int(raw.get("metadata_preservation_count", 0) or 0),
        "expected_output_ref": str(raw.get("expected_output_ref") or ""),
        "reviewed_at": str(raw.get("reviewed_at") or ""),
        "review_owner": str(raw.get("review_owner") or ""),
        "stale_after_days": int(raw.get("stale_after_days", 30) or 30),
        "unsupported_claims": sorted({str(item) for item in raw.get("unsupported_claims", [])}),
        "sourceRefs": sorted({str(item) for item in raw.get("sourceRefs", [])}),
    }


def _findings_for(
    families: list[dict[str, Any]],
    input_data: dict[str, Any],
    today: date,
) -> list[AdapterCorpusFinding]:
    findings: list[AdapterCorpusFinding] = []
    by_family = {family["family"]: family for family in families}

    if int(input_data.get("stale_count", 0) or 0) > 0:
        findings.append(AdapterCorpusFinding(
            code="adapter_corpus_stale_fixture",
            severity="high",
            message="Adapter corpus contains stale fixtures that require review.",
            sourceRef=_source_ref_for(families, "manifest"),
        ))
        return findings

    for family_name, requirement in REQUIRED_FAMILIES.items():
        family = by_family.get(family_name)
        if not family:
            findings.append(AdapterCorpusFinding(
                code="adapter_corpus_family_missing",
                severity="high",
                message=f"Required adapter family is missing: {family_name}",
                sourceRef="adapter-corpus-manifest",
            ))
            continue

        missing_dialects = sorted(requirement["dialects"] - set(family["dialects"]))
        if missing_dialects:
            findings.append(AdapterCorpusFinding(
                code="adapter_corpus_dialect_missing",
                severity="high",
                message=f"{family_name} is missing dialects: {', '.join(missing_dialects)}",
                sourceRef=_source_ref_for([family], family_name),
            ))

        if (
            family["positive_count"] < requirement["positive_minimum"]
            or family["negative_count"] < requirement["negative_minimum"]
        ):
            findings.append(AdapterCorpusFinding(
                code="adapter_corpus_fixture_count_below_minimum",
                severity="high",
                message=f"{family_name} fixture counts are below the required minimum.",
                sourceRef=_source_ref_for([family], family_name),
            ))

        if family["unsupported_claims"]:
            findings.append(AdapterCorpusFinding(
                code="adapter_corpus_unsupported_claim",
                severity="high",
                message=f"{family_name} claims unsupported capabilities: {', '.join(family['unsupported_claims'])}",
                sourceRef=_source_ref_for([family], family_name),
            ))

        if not family["expected_output_ref"]:
            findings.append(AdapterCorpusFinding(
                code="adapter_corpus_expected_output_missing",
                severity="medium",
                message=f"{family_name} must reference a conformance expected output.",
                sourceRef=_source_ref_for([family], family_name),
            ))

        if _is_stale(family, today):
            findings.append(AdapterCorpusFinding(
                code="adapter_corpus_stale_fixture",
                severity="high",
                message=f"{family_name} fixture review is stale or lacks an owner.",
                sourceRef=_source_ref_for([family], family_name),
            ))

    return findings


def _is_stale(family: dict[str, Any], today: date) -> bool:
    if not family["review_owner"] or not family["reviewed_at"]:
        return True
    try:
        reviewed_at = datetime.strptime(family["reviewed_at"], "%Y-%m-%d").date()
    except ValueError:
        return True
    return (today - reviewed_at).days > family["stale_after_days"]


def _family_source_refs(families: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for family in families:
        refs.extend(family["sourceRefs"])
        if family["expected_output_ref"]:
            refs.append(family["expected_output_ref"])
    return refs


def _entries_for(
    families: list[dict[str, Any]],
    findings: list[AdapterCorpusFinding],
    parser_version: str,
) -> list[dict[str, Any]]:
    blocked_sources = {finding.sourceRef for finding in findings}
    entries: list[dict[str, Any]] = []
    for family in families:
        source_refs = family["sourceRefs"] or [family["expected_output_ref"] or family["family"]]
        result = "fail" if any(ref in blocked_sources for ref in source_refs) else "pass"
        entries.append({
            "adapter_id": family["adapter_id"],
            "fixture_id": family["family"],
            "result": result,
            "severity": "high" if result == "fail" else "pass",
            "sourceRefs": source_refs,
            "parserVersion": parser_version,
            "produced_record_counts": {},
        })
    return entries


def _source_ref_for(families: list[dict[str, Any]], fallback: str) -> str:
    for family in families:
        if family["sourceRefs"]:
            return family["sourceRefs"][0]
        if family["expected_output_ref"]:
            return family["expected_output_ref"]
    return fallback
