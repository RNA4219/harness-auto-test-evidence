"""export時の用途制限・状態・スキーマ検証結果をP1aの評価根拠へ接続する。"""

from __future__ import annotations

from typing import Any


def export_metadata_issues(bundle: dict[str, Any], report: dict[str, Any]) -> list[dict[str, Any]]:
    """独立した否定的な宣言を、別の成功宣言で打ち消さず保持する。"""
    issues: list[dict[str, Any]] = []
    if bundle.get("metadata", {}).get("debugOnly") is True:
        issues.append({
            "issue": "diagnostic_only_bundle", "severity": "high",
            "message": "The bundle is marked debugOnly and is not formal QEG evidence.",
            "reported_value": True, "validation_path": ["metadata", "debugOnly"],
            "source_refs": ["qeg-bundle.json"],
        })
    if "export_status" in report:
        status = report["export_status"]
        if status != "success":
            partial = status == "partial"
            issues.append({
                "issue": "partial_export" if partial else "invalid_export_status",
                "severity": "medium" if partial else "high",
                "message": "The export report declares partial evidence." if partial
                           else "The export report does not declare a recognized export status.",
                "reported_value": status, "validation_path": ["export_status"],
                "source_refs": ["qeg-export-report.json"],
            })
    if "qeg_schema_compatibility" in report:
        compatibility = report["qeg_schema_compatibility"]
        conditions: list[str] = []
        paths: list[list[str]] = []
        if "valid" not in compatibility:
            conditions.append("schema validity is missing")
            paths.append(["qeg_schema_compatibility", "valid"])
        elif compatibility["valid"] is False:
            conditions.append("schema validity is false")
            paths.append(["qeg_schema_compatibility", "valid"])
        if compatibility.get("errors"):
            conditions.append("schema errors are reported")
            paths.append(["qeg_schema_compatibility", "errors"])
        if conditions:
            issues.append({
                "issue": "export_schema_validation_failed", "severity": "high",
                "message": "The export report does not establish successful QEG schema validation: " + "; ".join(conditions),
                "reported_validation": compatibility, "conditions": conditions,
                "validation_path": ["qeg_schema_compatibility"], "validation_paths": paths,
                "source_refs": ["qeg-export-report.json"],
            })
    return issues
