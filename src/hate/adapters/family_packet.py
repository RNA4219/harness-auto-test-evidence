"""Adapter family implementation packet evaluation for HATE-GAP-014."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from .corpus_manifest import REQUIRED_FAMILIES


REQUIRED_PACKET_FIELDS = {
    "family",
    "adapter_id",
    "dialects",
    "fixture_paths",
    "positive_count",
    "negative_count",
    "malformed_count",
    "partial_count",
    "path_normalization_count",
    "metadata_preservation_count",
    "expected_output_ref",
    "reviewed_at",
    "review_owner",
    "stale_after_days",
    "sourceRefs",
}

MINIMUM_SCENARIO_FIELDS = {
    "malformed_count",
    "partial_count",
    "path_normalization_count",
    "metadata_preservation_count",
}


@dataclass(frozen=True)
class AdapterFamilyFinding:
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


def evaluate_adapter_family_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_adapter_family_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "adapter-family-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_adapter_family_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "adapter-family-report",
    source_refs: list[str] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    packets = _normalize_packets(input_data)
    findings = _findings_for(input_data, packets, today)
    source_refs = sorted(set((source_refs or []) + _packet_source_refs(packets)))
    status = "hold" if findings else "pass"

    return {
        "schema_version": "HATE/v1",
        "record_type": "adapter-family-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "required_family_count": len(REQUIRED_FAMILIES),
        "packet_count": len(packets),
        "packets": packets,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "pass": status == "pass",
            "finding_count": len(findings),
            "families": sorted({packet["family"] for packet in packets if packet["family"]}),
        },
        "sourceRefs": source_refs,
    }


def _normalize_packets(input_data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_packets = input_data.get("family_packets")
    if isinstance(raw_packets, list):
        return [_normalize_packet(packet) for packet in raw_packets if isinstance(packet, dict)]

    raw_packet = input_data.get("family_packet")
    if isinstance(raw_packet, dict):
        return [_normalize_packet(raw_packet)]

    family = str(input_data.get("adapter_family") or input_data.get("family") or "")
    dialect = str(input_data.get("dialect") or "").lower()
    requirement = REQUIRED_FAMILIES.get(family, {})
    return [_normalize_packet({
        "family": family,
        "adapter_id": f"{family}-adapter" if family else "",
        "dialects": [dialect] if dialect else [],
        "fixture_paths": [str(input_data.get("fixture_path") or f"fixtures/adapters/family/{dialect}/fixture.json")],
        "positive_count": requirement.get("positive_minimum", 1),
        "negative_count": requirement.get("negative_minimum", 1),
        "malformed_count": 1,
        "partial_count": 1,
        "path_normalization_count": 1,
        "metadata_preservation_count": 1,
        "expected_output_ref": str(input_data.get("expected_output_ref") or "fixtures/adapters/family/expected.ndjson"),
        "reviewed_at": str(input_data.get("reviewed_at") or "2026-06-30"),
        "review_owner": str(input_data.get("review_owner") or "Developer Platform"),
        "stale_after_days": int(input_data.get("stale_after_days", 3650) or 3650),
        "unsupported_claims": input_data.get("unsupported_claims", []),
        "sourceRefs": input_data.get("sourceRefs", ["fixtures/adapters/family"]),
    })]


def _normalize_packet(raw: dict[str, Any]) -> dict[str, Any]:
    family = str(raw.get("family") or raw.get("adapter_family") or "")
    return {
        "family": family,
        "adapter_id": str(raw.get("adapter_id") or ""),
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
        "missing_fields": sorted(REQUIRED_PACKET_FIELDS - set(raw)),
    }


def _findings_for(
    input_data: dict[str, Any],
    packets: list[dict[str, Any]],
    today: date,
) -> list[AdapterFamilyFinding]:
    if bool(input_data.get("malformed")):
        return [AdapterFamilyFinding(
            code="adapter_family_malformed_input",
            severity="high",
            message="Adapter family packet input is malformed.",
            sourceRef=_source_ref_for(packets, "adapter-family-packet"),
        )]

    findings: list[AdapterFamilyFinding] = []
    if not packets:
        return [AdapterFamilyFinding(
            code="adapter_family_packet_missing",
            severity="high",
            message="Adapter family packet input is missing.",
            sourceRef="adapter-family-packet",
        )]

    for packet in packets:
        source_ref = _source_ref_for([packet], packet["family"] or "adapter-family-packet")
        family = packet["family"]
        requirement = REQUIRED_FAMILIES.get(family)
        if not family:
            findings.append(AdapterFamilyFinding(
                code="adapter_family_missing",
                severity="high",
                message="Adapter family packet must name a family.",
                sourceRef=source_ref,
            ))
            continue
        if requirement is None:
            findings.append(AdapterFamilyFinding(
                code="adapter_family_unsupported_claim",
                severity="high",
                message=f"Adapter family is not in the supported family catalog: {family}",
                sourceRef=source_ref,
            ))
            continue

        findings.extend(_field_findings(packet, source_ref))
        findings.extend(_dialect_findings(packet, requirement, source_ref))
        findings.extend(_count_findings(packet, requirement, source_ref))
        findings.extend(_scenario_findings(packet, source_ref))
        if packet["unsupported_claims"]:
            findings.append(AdapterFamilyFinding(
                code="adapter_family_unsupported_claim",
                severity="high",
                message=f"{family} claims unsupported capabilities: {', '.join(packet['unsupported_claims'])}",
                sourceRef=source_ref,
            ))
        if not packet["expected_output_ref"]:
            findings.append(AdapterFamilyFinding(
                code="adapter_family_expected_output_missing",
                severity="medium",
                message=f"{family} must reference an expected output.",
                sourceRef=source_ref,
            ))
        if _is_stale(packet, today):
            findings.append(AdapterFamilyFinding(
                code="adapter_family_stale_review",
                severity="high",
                message=f"{family} review owner/date is stale or missing.",
                sourceRef=source_ref,
            ))

    return findings


def _field_findings(packet: dict[str, Any], source_ref: str) -> list[AdapterFamilyFinding]:
    if not packet["missing_fields"]:
        return []
    return [AdapterFamilyFinding(
        code="adapter_family_packet_field_missing",
        severity="high",
        message=f"Adapter family packet is missing required fields: {', '.join(packet['missing_fields'])}",
        sourceRef=source_ref,
    )]


def _dialect_findings(
    packet: dict[str, Any],
    requirement: dict[str, Any],
    source_ref: str,
) -> list[AdapterFamilyFinding]:
    observed = set(packet["dialects"])
    required = set(requirement["dialects"])
    unsupported = sorted(observed - required)
    if unsupported:
        return [AdapterFamilyFinding(
            code="adapter_family_unsupported_dialect",
            severity="high",
            message=f"{packet['family']} declares unsupported dialects: {', '.join(unsupported)}",
            sourceRef=source_ref,
        )]
    if not observed:
        return [AdapterFamilyFinding(
            code="adapter_family_dialect_missing",
            severity="high",
            message=f"{packet['family']} must declare at least one supported dialect.",
            sourceRef=source_ref,
        )]
    return []


def _count_findings(
    packet: dict[str, Any],
    requirement: dict[str, Any],
    source_ref: str,
) -> list[AdapterFamilyFinding]:
    if (
        packet["positive_count"] >= requirement["positive_minimum"]
        and packet["negative_count"] >= requirement["negative_minimum"]
    ):
        return []
    return [AdapterFamilyFinding(
        code="adapter_family_fixture_count_below_minimum",
        severity="high",
        message=f"{packet['family']} fixture counts are below the required minimum.",
        sourceRef=source_ref,
    )]


def _scenario_findings(packet: dict[str, Any], source_ref: str) -> list[AdapterFamilyFinding]:
    missing = sorted(field for field in MINIMUM_SCENARIO_FIELDS if packet[field] < 1)
    if not missing:
        return []
    return [AdapterFamilyFinding(
        code="adapter_family_required_case_missing",
        severity="high",
        message=f"{packet['family']} lacks required scenario coverage: {', '.join(missing)}",
        sourceRef=source_ref,
    )]


def _is_stale(packet: dict[str, Any], today: date) -> bool:
    if not packet["review_owner"] or not packet["reviewed_at"]:
        return True
    try:
        reviewed_at = datetime.strptime(packet["reviewed_at"], "%Y-%m-%d").date()
    except ValueError:
        return True
    return (today - reviewed_at).days > packet["stale_after_days"]


def _packet_source_refs(packets: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for packet in packets:
        refs.extend(packet["sourceRefs"])
        refs.extend(packet["fixture_paths"])
        if packet["expected_output_ref"]:
            refs.append(packet["expected_output_ref"])
    return refs


def _source_ref_for(packets: list[dict[str, Any]], fallback: str) -> str:
    for packet in packets:
        if packet["sourceRefs"]:
            return packet["sourceRefs"][0]
        if packet["fixture_paths"]:
            return packet["fixture_paths"][0]
        if packet["expected_output_ref"]:
            return packet["expected_output_ref"]
    return fallback
