"""保存manifestの各契約版を、読込・再生・比較・書込で共通判定する。"""

from __future__ import annotations

from typing import Any

from .models import StoreManifest
from .versioning import STORE_SCHEMA_VERSION, STORE_VERSION

SUPPORTED_SCHEMA_VERSIONS = {STORE_SCHEMA_VERSION}
MIGRATION_REQUIRED_VERSIONS = {"HATE/v0.9", "HATE/v0.8"}


def manifest_schema_findings(manifest: StoreManifest) -> list[dict[str, Any]]:
    """既知の各componentを独立して確認し、追加のproducer版情報は保存する。"""
    findings: list[dict[str, Any]] = []
    for component, supported in (
        ("core", SUPPORTED_SCHEMA_VERSIONS), ("store", {STORE_VERSION}), ("bundle", SUPPORTED_SCHEMA_VERSIONS),
    ):
        if component == "bundle" and component not in manifest.schema_versions:
            continue
        actual = manifest.schema_versions.get(component)
        if actual not in supported:
            findings.append({
                "issue": "store_schema_version_unsupported", "component": component,
                "field": f"schema_versions.{component}", "actual": actual, "supported": sorted(supported),
            })
    return findings
