from __future__ import annotations

import json
from pathlib import Path

from hate.security.artifact_safety import scan_artifact_safety
from hate.security.quarantine_report import build_security_quarantine_report


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "HATE" / "v1" / "security-quarantine-report.schema.json"
REGISTRY_PATH = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _scan(fixture: dict) -> dict:
    return scan_artifact_safety(fixture)


def _codes(report: dict) -> set[str]:
    return {finding["code"] for finding in report["findings"]}


class TestSecurityQuarantineReport:
    def test_clean_artifact_passes_schema_and_status(self) -> None:
        safety_report = _scan(
            {
                "artifact_id": "clean-log",
                "artifact_path": "logs/clean.log",
                "profile": "product",
                "content": "tests passed without sensitive data",
            }
        )

        report = build_security_quarantine_report({"artifact_safety_reports": [safety_report]})

        assert report["record_type"] == "security-quarantine-report"
        assert report["status"] == "pass"
        assert report["readiness_effect"] == "pass"
        assert report["findings"] == []
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        for field in schema["required"]:
            assert field in report
        assert schema["properties"]["record_type"]["const"] == "security-quarantine-report"

    def test_required_quarantine_missing_decision_is_hard_dq(self) -> None:
        safety_report = _scan(
            {
                "artifact_id": "secret-log",
                "artifact_path": "logs/runtime.log",
                "profile": "product",
                "content": "api_key='abcdefghijklmnopqrstuvwxyz123456'",
            }
        )

        report = build_security_quarantine_report(
            {
                "artifact_safety_reports": [safety_report],
                "artifacts": [
                    {
                        "artifact_id": "secret-log",
                        "classification": "restricted",
                        "quarantine_status": "none",
                        "redaction_status": "pending",
                        "safe_for_summary": False,
                        "readiness_effect": "hard_dq",
                    }
                ],
                "surfaces": ["summary", "external_export"],
            }
        )

        assert report["status"] == "hold"
        assert report["readiness_effect"] == "hard_dq"
        assert "security_quarantine_decision_missing" in _codes(report)
        assert "security_quarantine_redaction_not_complete" in _codes(report)

    def test_unsafe_artifact_exported_is_detected(self) -> None:
        safety_report = _scan(
            {
                "artifact_id": "pending-secret",
                "artifact_path": "logs/pending.log",
                "profile": "product",
                "content": "api_key='abcdefghijklmnopqrstuvwxyz123456'",
            }
        )

        report = build_security_quarantine_report(
            {
                "artifact_safety_reports": [safety_report],
                "artifacts": [
                    {
                        "artifact_id": "pending-secret",
                        "classification": "public",
                        "quarantine_status": "none",
                        "redaction_status": "pending",
                        "safe_for_summary": True,
                        "readiness_effect": "hold",
                    }
                ],
                "surfaces": ["summary"],
            }
        )

        assert "security_quarantine_unsafe_artifact_visible" in _codes(report)
        assert "security_quarantine_unsafe_artifact_exported" in _codes(report)
        assert report["readiness_effect"] == "hard_dq"

    def test_quarantined_artifact_is_hidden_and_excluded(self) -> None:
        safety_report = _scan(
            {
                "artifact_id": "quarantined-secret",
                "artifact_path": "logs/quarantined.log",
                "profile": "product",
                "content": "api_key='abcdefghijklmnopqrstuvwxyz123456'",
            }
        )

        report = build_security_quarantine_report(
            {
                "artifact_safety_reports": [safety_report],
                "artifacts": [
                    {
                        "artifact_id": "quarantined-secret",
                        "classification": "restricted",
                        "quarantine_status": "quarantined",
                        "redaction_status": "redacted",
                        "safe_for_summary": False,
                        "readiness_effect": "hard_dq",
                    }
                ],
                "surfaces": ["summary", "external_export"],
            }
        )

        assert "security_quarantine_unsafe_artifact_visible" not in _codes(report)
        assert "security_quarantine_unsafe_artifact_exported" not in _codes(report)
        assert "security_quarantine_artifact_hard_dq" in _codes(report)
        for check in report["surface_checks"]:
            assert "quarantined-secret" not in check["summary_visible_artifact_ids"]
            assert "quarantined-secret" in check["export_excluded_artifact_ids"]

    def test_schema_registry_registers_security_quarantine_report(self) -> None:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        records = {item["record_type"]: item for item in registry["records"]}

        assert records["security-quarantine-report"]["schema"] == (
            "schemas/HATE/v1/security-quarantine-report.schema.json"
        )
        assert records["security-quarantine-report"]["unknown_field_policy"] == "preserve_without_summary"
