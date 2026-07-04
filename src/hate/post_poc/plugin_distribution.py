from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from hate.plugins.sandbox import build_plugin_sandbox_report

from .common import apply_productization_contract_tree, productization_envelope


STRICT_PROFILES = {"release", "regulated"}


@dataclass(frozen=True)
class PluginDistributionFinding:
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


def evaluate_plugin_distribution_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_plugin_distribution_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "plugin-distribution-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_plugin_distribution_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "plugin-distribution-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["plugin-distribution"])
    profile = str(input_data.get("profile") or "default")
    manifest = _normalize_manifest(input_data.get("manifest", input_data))
    signature = _signature_verification(manifest)
    index = _distribution_index(input_data.get("distribution_index", {}), manifest)
    revocation = _revocation_event(input_data.get("revocation", {}), manifest)
    sandbox_report = _sandbox_report(input_data, profile, manifest)
    findings = _findings_for(profile, manifest, signature, index, revocation, sandbox_report, source_refs[0])
    status = "hold" if findings else "pass"
    report = {
        "schema_version": "HATE/v1",
        "record_type": "plugin-distribution-report",
        "report_id": report_id,
        **productization_envelope(input_data, report_id=report_id, source_refs=source_refs),
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "profile": profile,
        "package_manifest": manifest,
        "signature_verification": signature,
        "revocation_event": revocation,
        "distribution_index": index,
        "sandbox_execution_report": sandbox_report,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "trusted": not findings,
            "profile": profile,
            "compatibility_status": manifest["compatibility_status"],
            "signature_valid": signature["signature_valid"],
            "allowlisted": bool(manifest["allowlist_ref"]),
            "revoked": revocation["revoked"],
            "index_stale": index["index_stale"],
            "sandbox_status": sandbox_report["overall_status"] if sandbox_report else "not_provided",
            "finding_count": len(findings),
        },
        "sourceRefs": sorted(set(source_refs)),
    }
    return apply_productization_contract_tree(report, source_refs=source_refs)


def build_plugin_install_manifest(
    input_data: dict[str, Any],
    *,
    manifest_id: str = "plugin-install-manifest",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["plugin-install-manifest"])
    report = (
        input_data
        if input_data.get("record_type") == "plugin-distribution-report"
        else build_plugin_distribution_report(input_data, report_id=f"{manifest_id}:distribution", source_refs=source_refs)
    )
    package = dict(report.get("package_manifest", {}))
    index = dict(report.get("distribution_index", {}))
    installable = _plugin_installable(report)
    entry = {
        "record_type": "plugin-install-entry",
        "plugin_id": package.get("plugin_id", ""),
        "plugin_version": package.get("plugin_version", ""),
        "api_version": package.get("api_version", ""),
        "package_hash": package.get("package_hash", ""),
        "index_ref": index.get("index_ref", ""),
        "signature_ref": package.get("signature_ref", ""),
        "allowlist_ref": package.get("allowlist_ref", ""),
        "compatibility_status": package.get("compatibility_status", ""),
        "capabilities": list(package.get("capabilities", [])),
        "resource_limits": dict(package.get("resource_limits", {})),
        "migration_note_ref": package.get("migration_note_ref", ""),
        "installable": installable,
        "install_block_reasons": _install_block_reasons(report),
    }
    findings = _install_manifest_findings(report, entry, source_refs[0])
    manifest = {
        "schema_version": "HATE/v1",
        "record_type": "plugin-install-manifest",
        "manifest_id": manifest_id,
        **productization_envelope(input_data, report_id=manifest_id, source_refs=source_refs),
        "readiness_effect": "hold" if findings else "none",
        "profile": report.get("profile", "default"),
        "entries": [entry],
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "entry_count": 1,
            "installable_count": 1 if installable else 0,
            "blocked_count": 0 if installable else 1,
            "finding_count": len(findings),
            "trusted": bool(report.get("summary", {}).get("trusted", False)),
        },
        "sourceRefs": sorted(set(source_refs + list(report.get("sourceRefs", [])))),
    }
    return apply_productization_contract_tree(manifest, source_refs=source_refs)


def write_plugin_install_manifest(manifest: dict[str, Any], out_path: str | Path) -> dict[str, Any]:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    apply_productization_contract_tree(manifest, source_refs=list(manifest.get("sourceRefs", [])))
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {
        "schema_version": "HATE/v1",
        "record_type": "plugin-install-manifest-artifact",
        **productization_envelope(manifest, report_id=f"{manifest.get('manifest_id') or 'plugin-install-manifest'}:artifact", source_refs=list(manifest.get("sourceRefs", []))),
        "readiness_effect": str(manifest.get("readiness_effect") or "none"),
        "artifact_path": str(path),
        "entry_count": len(manifest.get("entries", [])),
        "sourceRefs": list(manifest.get("sourceRefs", [])),
    }


def _plugin_installable(report: dict[str, Any]) -> bool:
    summary = report.get("summary", {})
    package = report.get("package_manifest", {})
    return (
        bool(summary.get("trusted", False))
        and package.get("compatibility_status") == "compatible"
        and not report.get("findings")
    )


def _install_block_reasons(report: dict[str, Any]) -> list[str]:
    reasons = [finding.get("code", "plugin_distribution_hold") for finding in report.get("findings", [])]
    package = report.get("package_manifest", {})
    if package.get("compatibility_status") != "compatible" and "plugin_api_migration_required" not in reasons:
        reasons.append("plugin_api_migration_required")
    if not report.get("summary", {}).get("trusted", False) and not reasons:
        reasons.append("plugin_distribution_untrusted")
    return sorted(set(reasons))


def _install_manifest_findings(
    report: dict[str, Any],
    entry: dict[str, Any],
    source_ref: str,
) -> list[PluginDistributionFinding]:
    findings: list[PluginDistributionFinding] = []
    if not entry["plugin_id"] or not entry["plugin_version"] or not entry["package_hash"]:
        findings.append(_finding("plugin_install_manifest_incomplete", "Install manifest requires plugin id, version, and package hash.", source_ref))
    if not entry["installable"]:
        findings.append(_finding("plugin_install_blocked", "Plugin install manifest is blocked by distribution trust findings.", source_ref))
    if entry["installable"] and not entry["index_ref"]:
        findings.append(_finding("plugin_distribution_index_stale", "Installable plugin requires distribution index_ref.", source_ref))
    return findings


def _normalize_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    manifest = dict(raw or {})
    return {
        "record_type": "plugin-package-manifest",
        "plugin_id": str(manifest.get("plugin_id") or ""),
        "plugin_version": str(manifest.get("plugin_version") or ""),
        "api_version": str(manifest.get("api_version") or ""),
        "package_hash": str(manifest.get("package_hash") or ""),
        "observed_package_hash": str(manifest.get("observed_package_hash") or manifest.get("package_hash") or ""),
        "signature_algorithm": str(manifest.get("signature_algorithm") or ""),
        "signature_ref": str(manifest.get("signature_ref") or ""),
        "signature_valid": bool(manifest.get("signature_valid", False)),
        "trust_source": str(manifest.get("trust_source") or ""),
        "allowlist_ref": str(manifest.get("allowlist_ref") or ""),
        "revocation_ref": str(manifest.get("revocation_ref") or ""),
        "compatibility_status": str(manifest.get("compatibility_status") or "compatible"),
        "capabilities": [str(item) for item in manifest.get("capabilities", [])],
        "resource_limits": dict(manifest.get("resource_limits") or {}),
        "migration_note_ref": str(manifest.get("migration_note_ref") or ""),
    }


def _signature_verification(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "plugin-signature-verification",
        "plugin_id": manifest["plugin_id"],
        "plugin_version": manifest["plugin_version"],
        "signature_algorithm": manifest["signature_algorithm"],
        "signature_ref": manifest["signature_ref"],
        "trust_source": manifest["trust_source"],
        "signature_valid": manifest["signature_valid"],
    }


def _distribution_index(raw: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    index = dict(raw or {})
    return {
        "record_type": "plugin-distribution-index",
        "plugin_id": manifest["plugin_id"],
        "plugin_version": manifest["plugin_version"],
        "index_ref": str(index.get("index_ref") or ""),
        "index_hash": str(index.get("index_hash") or ""),
        "indexed_package_hash": str(index.get("indexed_package_hash") or manifest["package_hash"]),
        "index_stale": bool(index.get("index_stale", False)),
        "generated_at": str(index.get("generated_at") or ""),
    }


def _revocation_event(raw: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    revocation = dict(raw or {})
    return {
        "record_type": "plugin-revocation-event",
        "plugin_id": manifest["plugin_id"],
        "plugin_version": manifest["plugin_version"],
        "revoked": bool(revocation.get("revoked", False)),
        "revocation_ref": str(revocation.get("revocation_ref") or manifest["revocation_ref"]),
        "reason": str(revocation.get("reason") or ""),
    }


def _sandbox_report(input_data: dict[str, Any], profile: str, manifest: dict[str, Any]) -> dict[str, Any] | None:
    raw = input_data.get("sandbox")
    if not isinstance(raw, dict):
        return None
    sandbox_input = dict(raw)
    plugin = dict(sandbox_input.get("plugin") or {})
    plugin.setdefault("plugin_id", manifest["plugin_id"])
    plugin.setdefault("detector_id", manifest["plugin_id"])
    plugin.setdefault("execution_mode", "containerized")
    plugin.setdefault("signed", manifest["signature_valid"])
    plugin.setdefault("trusted", bool(manifest["allowlist_ref"]))
    sandbox_input["plugin"] = plugin
    sandbox_input.setdefault("profile", profile)
    return build_plugin_sandbox_report(sandbox_input, report_id=f"plugin-sandbox:{manifest['plugin_id']}")


def _findings_for(
    profile: str,
    manifest: dict[str, Any],
    signature: dict[str, Any],
    index: dict[str, Any],
    revocation: dict[str, Any],
    sandbox_report: dict[str, Any] | None,
    source_ref: str,
) -> list[PluginDistributionFinding]:
    findings: list[PluginDistributionFinding] = []
    strict = profile in STRICT_PROFILES

    if manifest["package_hash"] != manifest["observed_package_hash"]:
        findings.append(_finding("plugin_package_hash_mismatch", "Plugin package hash does not match observed package hash.", source_ref))
    if strict and (not signature["signature_ref"] or not signature["signature_valid"]):
        findings.append(_finding("plugin_signature_invalid", "Release and regulated profiles require a valid plugin signature.", source_ref))
    if revocation["revoked"]:
        findings.append(_finding("plugin_revoked", "Revoked plugins cannot be distributed or executed.", source_ref))
    if strict and not manifest["allowlist_ref"]:
        findings.append(_finding("plugin_allowlist_missing", "Release and regulated profiles require plugin allowlist_ref.", source_ref))
    if manifest["compatibility_status"] != "compatible":
        findings.append(_finding("plugin_api_migration_required", "Plugin API compatibility requires migration before distribution.", source_ref))
    if manifest["compatibility_status"] == "migration_required" and not manifest["migration_note_ref"]:
        findings.append(_finding("plugin_api_migration_required", "Migration-required plugins require migration_note_ref.", source_ref))
    if index["index_stale"] or index["indexed_package_hash"] != manifest["package_hash"]:
        findings.append(_finding("plugin_distribution_index_stale", "Plugin distribution index is stale or points at a different package hash.", source_ref))
    if sandbox_report and sandbox_report["overall_status"] != "pass":
        findings.append(_finding("plugin_sandbox_execution_hold", "Plugin sandbox execution evidence is not pass.", source_ref))
    return findings


def _finding(code: str, message: str, source_ref: str) -> PluginDistributionFinding:
    return PluginDistributionFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
        readiness_effect="hold",
    )
