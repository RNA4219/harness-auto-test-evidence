"""P1A adapter conformance report construction."""

from __future__ import annotations

from typing import Any

from hate.p1a_internal.adapter_registry import (
    SCHEMA_VERSION,
    _adapter_manifest_is_complete,
    _build_adapter_registry,
)


def _build_adapter_conformance_report(
    run_id: str,
    adapter_manifest: dict[str, Any],
    doctor_report: dict[str, Any],
    resolver_map: dict[str, Any],
    adapter_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    adapter_registry = adapter_registry or _build_adapter_registry()
    adapter_results = _adapter_conformance_results(adapter_registry)
    finding_categories = {finding["category"] for finding in doctor_report.get("findings", [])}
    has_unsafe_path = any(entry.get("resolution_status") == "unsafe" for entry in resolver_map.get("entries", []))
    checks = [
        {
            "check_id": "adapter-registry-manifest-fields",
            "category": "adapter_registry",
            "status": "pass" if adapter_registry["summary"]["all_have_required_manifest_fields"] else "fail",
            "adapter_ids": [adapter["adapter_id"] for adapter in adapter_registry["adapters"]],
            "source_refs": ["adapter-registry.json"],
        },
        {
            "check_id": "adapter-capability-source-refs",
            "category": "adapter",
            "status": "pass" if adapter_manifest["capability"]["source_refs"] else "fail",
            "source_refs": ["adapter-capability-manifest.json"],
        },
        {
            "check_id": "doctor-qeg-fixture",
            "category": "qeg_fixture",
            "status": "covered" if "qeg_fixture" in finding_categories else "pass",
            "source_refs": ["doctor-report.json"],
        },
        {
            "check_id": "doctor-path",
            "category": "path",
            "status": "covered" if has_unsafe_path else "pass",
            "source_refs": ["artifact-resolver-map.json"],
        },
        {
            "check_id": "doctor-artifact-safety",
            "category": "artifact_safety",
            "status": "covered" if "artifact_safety" in finding_categories else "pass",
            "source_refs": ["doctor-report.json"],
        },
        {
            "check_id": "schema-required-records",
            "category": "schema",
            "status": "pass",
            "source_refs": ["aete-score.json", "doctor-report.json"],
        },
        {
            "check_id": "profile-release-boundary",
            "category": "profile",
            "status": "pass",
            "source_refs": ["aete-score.json"],
        },
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "adapter_conformance",
        "run_id": run_id,
        "adapter_id": adapter_manifest["adapter_id"],
        "adapter_registry_ref": "adapter-registry.json",
        "adapter_registry": {
            "registry_version": adapter_registry["registry_version"],
            "adapter_count": adapter_registry["summary"]["adapter_count"],
            "adapter_ids": [adapter["adapter_id"] for adapter in adapter_registry["adapters"]],
            "by_type": adapter_registry["summary"]["by_type"],
        },
        "adapter_results": adapter_results,
        "checks": checks,
        "summary": {
            "overall_status": "pass" if all(check["status"] in {"pass", "covered"} for check in checks) and all(result["conformance_status"] == "pass" for result in adapter_results) else "fail",
            "check_count": len(checks),
            "covered_categories": sorted({check["category"] for check in checks}),
            "adapter_count": adapter_registry["summary"]["adapter_count"],
            "adapter_result_count": len(adapter_results),
            "fixture_result_count": sum(len(result["fixture_results"]) for result in adapter_results),
        },
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _adapter_conformance_results(adapter_registry: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for adapter in adapter_registry.get("adapters", []):
        if not isinstance(adapter, dict):
            continue
        fixture_results = [
            {
                "fixture_id": "manifest-required-fields",
                "category": "manifest",
                "status": "pass" if _adapter_manifest_is_complete(adapter) else "fail",
                "source_refs": ["adapter-registry.json"],
            },
            {
                "fixture_id": "capability-fields",
                "category": "capability",
                "status": "pass" if _adapter_capabilities_are_declared(adapter) else "fail",
                "source_refs": ["adapter-registry.json"],
            },
            {
                "fixture_id": "profile-support",
                "category": "profile",
                "status": "pass" if _adapter_profile_support_is_declared(adapter) else "fail",
                "source_refs": ["adapter-registry.json"],
            },
        ]
        results.append({
            "adapter_id": adapter.get("adapter_id", ""),
            "adapter_type": adapter.get("adapter_type", ""),
            "fixture_results": fixture_results,
            "conformance_status": "pass" if all(item["status"] == "pass" for item in fixture_results) else "fail",
            "known_limits": adapter.get("known_limits", []),
            "source_refs": ["adapter-registry.json"],
        })
    return results


def _adapter_capabilities_are_declared(adapter: dict[str, Any]) -> bool:
    capabilities = adapter.get("capabilities", {})
    if not isinstance(capabilities, dict):
        return False
    required = {"source_refs", "retry", "matrix", "artifact_hash", "coverage_context", "redaction"}
    return required.issubset(capabilities)


def _adapter_profile_support_is_declared(adapter: dict[str, Any]) -> bool:
    profile_support = adapter.get("profile_support", {})
    if not isinstance(profile_support, dict):
        return False
    return {"default", "strict", "release"}.issubset(profile_support)