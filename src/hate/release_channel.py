"""Release channel and migration policy evaluation for HATE-GAP-019."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


RELEASE_CHANNELS = {"experimental", "preview", "stable", "long-term"}
CHANGE_TYPES = {"patch", "minor", "major", "breaking"}
RELEASE_GATES = [f"RG-{index}" for index in range(1, 9)]


@dataclass(frozen=True)
class ReleaseChannelFinding:
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


def evaluate_release_channel_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_release_channel_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "release-channel-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_release_channel_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "release-channel-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["release-channel"])
    matrix = _normalize_matrix(input_data)
    findings = _findings_for(matrix, source_refs[0])
    status = "hold" if findings else "pass"

    return {
        "schema_version": "HATE/v1",
        "record_type": "release-channel-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "channel_matrix": matrix,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "channel": matrix["channel"],
            "change_type": matrix["change_type"],
            "migration_required": matrix["migration_required"],
            "release_gate_count": len(matrix["release_gates"]),
            "finding_count": len(findings),
            "rollback_ready": matrix["rollback_plan"],
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_matrix(input_data: dict[str, Any]) -> dict[str, Any]:
    change_type = str(input_data.get("change_type") or "patch")
    channel = str(input_data.get("channel") or _default_channel(change_type))
    migration_required = bool(input_data.get("migration_required", change_type in {"major", "breaking"}))
    migration_artifacts = dict(input_data.get("migration_artifacts") or {})
    release_gates = list(input_data.get("release_gates") or RELEASE_GATES)
    compatibility_matrix = dict(input_data.get("compatibility_matrix") or _default_compatibility_matrix(channel))
    release_notes = dict(input_data.get("release_notes") or _default_release_notes(change_type, migration_required))
    return {
        "channel": channel,
        "change_type": change_type,
        "migration_required": migration_required,
        "migration_plan": bool(input_data.get("migration_plan", not migration_required)),
        "rollback_plan": bool(input_data.get("rollback_plan", False)),
        "deprecation_notice": bool(input_data.get("deprecation_notice", change_type not in {"major", "breaking"})),
        "migration_artifacts": migration_artifacts,
        "release_gates": sorted(str(gate) for gate in release_gates),
        "compatibility_matrix": compatibility_matrix,
        "release_notes": release_notes,
        "previous_stable_safe_reject": bool(input_data.get("previous_stable_safe_reject", True)),
        "qeg_compatibility": bool(input_data.get("qeg_compatibility", True)),
    }


def _findings_for(matrix: dict[str, Any], source_ref: str) -> list[ReleaseChannelFinding]:
    findings: list[ReleaseChannelFinding] = []
    if matrix["channel"] not in RELEASE_CHANNELS:
        findings.append(_finding("release_unknown_channel", f"Unknown release channel: {matrix['channel']}", source_ref))
    if matrix["change_type"] not in CHANGE_TYPES:
        findings.append(_finding("release_unknown_change_type", f"Unknown release change type: {matrix['change_type']}", source_ref))
    if matrix["change_type"] == "breaking" and matrix["migration_required"] and not matrix["migration_plan"]:
        findings.append(_finding(
            "release_breaking_without_migration",
            "Breaking release requires migration plan.",
            source_ref,
        ))
    if matrix["migration_required"] and not _has_required_migration_artifacts(matrix):
        findings.append(_finding(
            "release_migration_artifact_missing",
            "Migration-required release must include migration guide, diff, replay impact, and compatibility matrix.",
            source_ref,
        ))
    if matrix["change_type"] in {"major", "breaking"} and not matrix["deprecation_notice"]:
        findings.append(_finding(
            "release_deprecation_notice_missing",
            "Major/breaking release requires deprecation/removal notice.",
            source_ref,
        ))
    if not matrix["rollback_plan"]:
        findings.append(_finding(
            "release_rollback_plan_missing",
            "Release channel policy requires rollback instructions.",
            source_ref,
        ))
    missing_gates = sorted(set(RELEASE_GATES) - set(matrix["release_gates"]))
    if missing_gates:
        findings.append(_finding(
            "release_gate_evidence_missing",
            f"Release gate evidence missing: {', '.join(missing_gates)}",
            source_ref,
        ))
    if not matrix["previous_stable_safe_reject"]:
        findings.append(_finding(
            "release_previous_stable_safe_reject_missing",
            "Previous stable must read or safely reject unsupported future schema.",
            source_ref,
        ))
    if not matrix["qeg_compatibility"]:
        findings.append(_finding(
            "release_qeg_compatibility_missing",
            "Release requires QEG compatibility matrix evidence.",
            source_ref,
        ))
    if not _release_notes_complete(matrix["release_notes"]):
        findings.append(_finding(
            "release_notes_incomplete",
            "Release notes must include compatibility matrix and rollback instructions.",
            source_ref,
        ))
    return findings


def _has_required_migration_artifacts(matrix: dict[str, Any]) -> bool:
    artifacts = matrix["migration_artifacts"]
    if not matrix["migration_required"]:
        return True
    required = {
        "migration_guide",
        "schema_diff",
        "replay_impact",
        "compatibility_matrix",
    }
    return all(bool(artifacts.get(key)) for key in required)


def _release_notes_complete(notes: dict[str, Any]) -> bool:
    required = {
        "summary",
        "breaking_changes",
        "deprecated_fields",
        "migration_steps",
        "compatibility_matrix",
        "known_issues",
        "security_notes",
        "artifact_safety_changes",
        "qeg_compatibility",
        "rollback_instructions",
    }
    return required <= set(notes)


def _default_channel(change_type: str) -> str:
    if change_type == "breaking":
        return "preview"
    return "stable"


def _default_compatibility_matrix(channel: str) -> dict[str, Any]:
    return {
        "channel": channel,
        "cli_version": "0.1.0-fixture",
        "schema_versions": ["HATE/v1"],
        "adapter_sdk_versions": ["1.x"],
        "qeg_export_versions": ["QEG/v1"],
        "profile_versions": ["default/v1", "release/v1"],
        "supported_until": "2026-12-31",
    }


def _default_release_notes(change_type: str, migration_required: bool) -> dict[str, Any]:
    return {
        "summary": "Release channel fixture",
        "breaking_changes": ["requires migration"] if change_type == "breaking" else [],
        "deprecated_fields": [],
        "migration_steps": ["follow migration-guide.md"] if migration_required else [],
        "compatibility_matrix": "compatibility-matrix.json",
        "known_issues": [],
        "security_notes": [],
        "artifact_safety_changes": [],
        "qeg_compatibility": "QEG/v1",
        "rollback_instructions": "Rollback to previous stable without mutating canonical bundles.",
    }


def _finding(code: str, message: str, source_ref: str) -> ReleaseChannelFinding:
    return ReleaseChannelFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
