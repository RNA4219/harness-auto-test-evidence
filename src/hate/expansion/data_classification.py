"""Data classification evaluation for HATE-GAP-032."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ALLOWED_SINKS = {"canonical_bundle", "api_response", "audit_log", "public_summary"}
ALLOWED_SINK_TYPES = {"telemetry", "audit_log", "public_summary", "canonical_bundle"}


@dataclass(frozen=True)
class DataClassificationFinding:
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


def evaluate_data_classification_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_data_classification_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "data-classification-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_data_classification_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "data-classification-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["data-classification"])
    classification_config = _normalize_classification_config(
        input_data.get("classification_config", input_data)
    )
    findings = _findings_for(classification_config, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "data-classification-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "classification_config": classification_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "field_taxonomy_defined": classification_config["field_taxonomy_defined"],
            "sink_allowlist_defined": classification_config["sink_allowlist_defined"],
            "sink_type": classification_config["sink_type"],
            "telemetry_allowed": classification_config["telemetry_allowed"],
            "prohibited_field_exposed": classification_config["prohibited_field_exposed"],
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_classification_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    classified_fields = [
        str(field) for field in config.get("classified_fields", []) if str(field)
    ]
    allowed_sinks = [
        str(sink) for sink in config.get("allowed_sinks", []) if str(sink)
    ]
    taxonomy_defined = bool(
        config.get("field_taxonomy_defined", config.get("taxonomy_defined", False))
    )
    sink_allowlist_defined = bool(
        config.get("sink_allowlist_defined", bool(allowed_sinks))
    )
    redaction_policy_defined = bool(
        config.get("redaction_policy_defined", config.get("redaction_rules_defined", False))
    )
    telemetry_allowed = bool(config.get("telemetry_allowed", False))
    telemetry_sink_requested = bool(config.get("telemetry_sink_allowed", False))
    return {
        "field_taxonomy_defined": taxonomy_defined,
        "sink_allowlist_defined": sink_allowlist_defined,
        "sink_allowlist_missing_code": (
            "data_classification_allowed_sinks_missing"
            if "allowed_sinks" in config
            else "data_classification_sink_allowlist_missing"
        ),
        "redaction_policy_defined": redaction_policy_defined,
        "telemetry_allowed": telemetry_allowed,
        "telemetry_sink_requested": telemetry_sink_requested,
        "telemetry_destination": str(config.get("telemetry_destination") or ""),
        "public_summary_safe": bool(config.get("public_summary_safe", False)),
        "classified_fields": classified_fields,
        "allowed_sinks": allowed_sinks,
        "prohibited_field_exposed": bool(config.get("prohibited_field_exposed", False)),
        "sink_type": str(config.get("sink_type") or ""),
    }


def _findings_for(
    config: dict[str, Any], source_ref: str
) -> list[DataClassificationFinding]:
    findings: list[DataClassificationFinding] = []
    if not config["field_taxonomy_defined"]:
        findings.append(_finding(
            "data_classification_taxonomy_missing",
            "Data classification requires field taxonomy definition.",
            source_ref,
        ))
    if not config["sink_allowlist_defined"]:
        findings.append(_finding(
            config["sink_allowlist_missing_code"],
            "Data classification requires sink allowlist definition.",
            source_ref,
        ))
    if not config["redaction_policy_defined"]:
        findings.append(_finding(
            "data_classification_redaction_missing",
            "Data classification requires redaction policy for sensitive fields.",
            source_ref,
        ))
    invalid_sinks = sorted(set(config["allowed_sinks"]) - ALLOWED_SINKS)
    if invalid_sinks:
        findings.append(_finding(
            "data_classification_invalid_sink",
            f"Data classification sink is not allowed: {', '.join(invalid_sinks)}.",
            source_ref,
        ))
    if config["sink_type"] == "prohibited" or config["telemetry_sink_requested"]:
        findings.append(_finding(
            "data_classification_prohibited_telemetry",
            "Telemetry sink is prohibited by classification policy.",
            source_ref,
        ))
    if config["prohibited_field_exposed"]:
        findings.append(_finding(
            "data_classification_prohibited_field_exposed",
            "Prohibited field exposed violates classification policy.",
            source_ref,
        ))
    return findings


def _finding(code: str, message: str, source_ref: str) -> DataClassificationFinding:
    return DataClassificationFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
