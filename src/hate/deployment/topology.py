"""Deployment topology and residency evaluation for HATE-GAP-017."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEPLOYMENT_MODES = {
    "local_only",
    "local_single_node",
    "ci_attached",
    "hosted",
    "hosted_read_model",
    "private_tenant",
    "customer_managed",
    "air_gapped_export",
}

HOSTED_MODES = {"hosted", "hosted_read_model", "private_tenant"}
RAW_DATA_CLASSES = {"customer_source_code", "unsafe_artifact", "raw_path", "artifact_content"}


@dataclass(frozen=True)
class DeploymentTopologyFinding:
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


def evaluate_deployment_topology_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_deployment_topology_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "deployment-topology-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_deployment_topology_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "deployment-topology-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["deployment-topology"])
    profile = _normalize_profile(input_data)
    findings = _findings_for(profile, source_refs[0])
    status = "hold" if findings else "pass"

    return {
        "schema_version": "HATE/v1",
        "record_type": "deployment-topology-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "profile": profile,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "deployment_mode": profile["deployment_mode"],
            "region": profile["actual_region"],
            "offline_mode": profile["offline_mode"],
            "finding_count": len(findings),
            "local_first_preserved": profile["local_first_preserved"],
            "hosted_upload_blocked_count": len(profile["blocked_hosted_upload_classes"]),
        },
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_profile(input_data: dict[str, Any]) -> dict[str, Any]:
    topology = str(input_data.get("topology") or input_data.get("deployment_mode") or "local_only")
    required_region = str(input_data.get("required_region") or "")
    actual_region = str(input_data.get("actual_region") or input_data.get("region") or "")
    allowed_regions = [str(item) for item in input_data.get("allowed_regions", [])]
    if required_region and not allowed_regions:
        allowed_regions = [required_region]
    data_classes = dict(input_data.get("data_classes") or _default_data_classes(topology))
    network = dict(input_data.get("network") or _default_network(topology))
    backup = dict(input_data.get("backup") or _default_backup(topology))
    blocked_uploads = sorted(
        data_class
        for data_class, route in data_classes.items()
        if data_class in RAW_DATA_CLASSES and str(route) in {"hosted", "hosted_allowed", "uploaded"}
    )
    return {
        "deployment_mode": topology,
        "required_region": required_region,
        "actual_region": actual_region,
        "allowed_regions": allowed_regions,
        "offline_mode": bool(input_data.get("offline_mode", topology in {"local_only", "local_single_node", "air_gapped_export"})),
        "data_classes": data_classes,
        "network": network,
        "backup": backup,
        "local_first_preserved": bool(input_data.get("local_first_preserved", True)),
        "canonical_bundle_rebuildable": bool(input_data.get("canonical_bundle_rebuildable", True)),
        "blocked_hosted_upload_classes": blocked_uploads,
    }


def _findings_for(profile: dict[str, Any], source_ref: str) -> list[DeploymentTopologyFinding]:
    findings: list[DeploymentTopologyFinding] = []
    mode = profile["deployment_mode"]
    if mode not in DEPLOYMENT_MODES:
        findings.append(DeploymentTopologyFinding(
            code="deployment_topology_unknown_mode",
            severity="high",
            message=f"Unknown deployment topology: {mode}",
            sourceRef=source_ref,
        ))

    if profile["required_region"] and profile["actual_region"] and profile["required_region"] != profile["actual_region"]:
        findings.append(DeploymentTopologyFinding(
            code="deployment_region_violation",
            severity="high",
            message=f"Actual region {profile['actual_region']} violates required region {profile['required_region']}.",
            sourceRef=source_ref,
        ))
    if profile["allowed_regions"] and profile["actual_region"] and profile["actual_region"] not in profile["allowed_regions"]:
        findings.append(DeploymentTopologyFinding(
            code="deployment_region_not_allowed",
            severity="high",
            message=f"Actual region {profile['actual_region']} is not in allowed regions.",
            sourceRef=source_ref,
        ))
    if profile["blocked_hosted_upload_classes"]:
        findings.append(DeploymentTopologyFinding(
            code="deployment_raw_data_hosted_upload_denied",
            severity="high",
            message="Raw customer data classes must not be hosted by default.",
            sourceRef=source_ref,
        ))
    if mode in HOSTED_MODES and not profile["canonical_bundle_rebuildable"]:
        findings.append(DeploymentTopologyFinding(
            code="deployment_read_model_not_rebuildable",
            severity="high",
            message="Hosted read model must be rebuildable from canonical bundle.",
            sourceRef=source_ref,
        ))
    if mode in {"private_tenant", "customer_managed"} and not profile["network"].get("private_link", False):
        findings.append(DeploymentTopologyFinding(
            code="deployment_private_network_missing",
            severity="medium",
            message="Private tenant/customer managed deployment requires private networking.",
            sourceRef=source_ref,
        ))
    if mode == "air_gapped_export" and not profile["offline_mode"]:
        findings.append(DeploymentTopologyFinding(
            code="deployment_airgap_offline_mode_required",
            severity="high",
            message="Air-gapped export requires offline mode.",
            sourceRef=source_ref,
        ))
    if not profile["local_first_preserved"]:
        findings.append(DeploymentTopologyFinding(
            code="deployment_local_first_broken",
            severity="high",
            message="Deployment topology must not break local-first precheck and frozen bundle replay.",
            sourceRef=source_ref,
        ))
    if profile["backup"].get("rewrites_record_ids", False):
        findings.append(DeploymentTopologyFinding(
            code="deployment_backup_rewrites_records",
            severity="high",
            message="Backup/recovery must not rewrite evidence record IDs.",
            sourceRef=source_ref,
        ))
    return findings


def _default_data_classes(mode: str) -> dict[str, str]:
    if mode in {"hosted", "hosted_read_model", "private_tenant"}:
        return {
            "canonical_bundle": "customer_controlled",
            "read_model": "hosted_allowed",
            "artifact_content": "not_uploaded",
            "artifact_metadata": "hosted_allowed",
            "telemetry": "aggregate_only",
        }
    return {
        "canonical_bundle": "customer_controlled",
        "read_model": "local",
        "artifact_content": "local",
        "artifact_metadata": "local",
        "telemetry": "off",
    }


def _default_network(mode: str) -> dict[str, bool]:
    return {
        "public_ingress": mode in {"hosted", "hosted_read_model"},
        "private_link": mode in {"private_tenant", "customer_managed"},
        "ip_allowlist": mode not in {"local_only", "local_single_node"},
    }


def _default_backup(mode: str) -> dict[str, bool | str]:
    return {
        "strategy": "rebuild_from_canonical_bundle" if mode in HOSTED_MODES else "customer_rerun",
        "audit_event_required": mode not in {"local_only", "local_single_node"},
        "rewrites_record_ids": False,
    }
