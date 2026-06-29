"""Tests for HATE-PG-005B redaction and summary/export safety filters."""

from __future__ import annotations

import json
from pathlib import Path

from hate.security.redaction import redact_artifact
from hate.security.export_filter import filter_for_export
from hate.security.summary_filter import filter_for_summary


FIXTURE_DIR = Path("fixtures/security/redaction")
CANONICAL_FIXTURES = [
    "clean-no-redaction",
    "synthetic-pii-allowed",
    "public-url-allowed",
    "allowlisted-secret-visible",
    "redacted-secret-success",
    "redacted-pii-success",
    "private-url-redacted",
    "path-traversal-redacted",
    "private-key-redacted",
    "multiple-redactions",
]
PACKET_FIXTURES = [
    "safe-summary",
    "secret-redacted",
    "path-tokenized",
    "dashboard-safe-view",
    "support-bundle-safe",
    "raw-secret-export",
    "raw-pii-summary",
    "reversible-redaction",
    "unauthorized-restricted-path",
    "diagnostic-bundle-raw-artifact",
]


def load_fixture(name: str) -> dict:
    path = FIXTURE_DIR / name / "fixture.json"
    assert path.exists(), f"missing fixture: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def assert_redaction_marker_present(content: str, marker: str) -> None:
    assert marker in content, f"expected redaction marker '{marker}' not found in content"


def assert_no_remaining_pattern(content: str, pattern_type: str) -> None:
    """Assert no sensitive pattern remains after redaction."""
    import re
    patterns = {
        "secret": [
            re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"][^'\"]{20,}['\"]"),
            re.compile(r"(?i)AKIA[0-9A-Z]{16}"),
            re.compile(r"(?i)sk-[A-Za-z0-9]{40,}"),
            re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        ],
        "pii": [
            re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        ],
        "path": [
            re.compile(r"\.\./\.\.?"),
        ],
        "url": [
            re.compile(r"x-amz-signature"),
            re.compile(r"signature="),
        ],
    }
    for pattern in patterns.get(pattern_type, []):
        assert not pattern.search(content), f"remaining {pattern_type} pattern found: {pattern.pattern}"


class TestCanonicalFixturePaths:
    def test_all_fixture_paths_exist(self) -> None:
        for name in CANONICAL_FIXTURES:
            assert (FIXTURE_DIR / name / "fixture.json").exists()

    def test_packet_fixture_paths_exist(self) -> None:
        for name in PACKET_FIXTURES:
            assert (FIXTURE_DIR / name / "fixture.json").exists()

    def test_no_pytest_skip_used(self) -> None:
        source = Path(__file__).read_text(encoding="utf-8")
        assert "pytest" + "." + "skip" not in source


class TestRedactionFilter:
    def test_clean_content_no_redaction(self) -> None:
        fixture = load_fixture("clean-no-redaction")
        report = redact_artifact(fixture)

        assert report["redaction_status"] == "not_required"
        assert report["classification"] == "public"
        assert report["readiness_effect"] == "pass"
        assert report["summary"]["redactions_count"] == 0
        assert report["redaction_log"] == []

    def test_synthetic_pii_allowed(self) -> None:
        fixture = load_fixture("synthetic-pii-allowed")
        report = redact_artifact(fixture)

        assert report["redaction_status"] == "not_required"
        assert report["readiness_effect"] == "pass"
        assert report["summary"]["pii_redacted"] == 0

    def test_public_url_allowed(self) -> None:
        fixture = load_fixture("public-url-allowed")
        report = redact_artifact(fixture)

        assert report["redaction_status"] == "not_required"
        assert report["summary"]["urls_redacted"] == 0
        # Public URLs should remain in content
        assert "docs.python.org" in report["redacted_content"]
        assert "github.com" in report["redacted_content"]

    def test_allowlisted_test_secret_visible(self) -> None:
        fixture = load_fixture("allowlisted-secret-visible")
        report = redact_artifact(fixture)

        assert report["redaction_status"] == "not_required"
        assert report["classification"] == "internal"
        # Allowlisted secrets remain visible
        assert "test_api_key" in report["redacted_content"]
        assert "fake_secret" in report["redacted_content"]

    def test_secret_redaction_with_marker(self) -> None:
        fixture = load_fixture("redacted-secret-success")
        report = redact_artifact(fixture)

        assert report["redaction_status"] == "redacted"
        assert report["classification"] == "restricted"
        assert report["readiness_effect"] == "hard_dq"
        assert report["summary"]["secrets_redacted"] >= 1

        # Redaction marker present
        assert_redaction_marker_present(report["redacted_content"], "[REDACTED_SECRET]")
        assert_no_remaining_pattern(report["redacted_content"], "secret")

        # SourceRef preserved
        assert len(report["sourceRefs"]) >= 1
        assert any("logs/runtime.log:" in ref for ref in report["sourceRefs"])

    def test_pii_redaction_with_marker(self) -> None:
        fixture = load_fixture("redacted-pii-success")
        report = redact_artifact(fixture)

        assert report["redaction_status"] == "redacted"
        assert report["classification"] == "restricted"
        assert report["summary"]["pii_redacted"] >= 1

        assert_redaction_marker_present(report["redacted_content"], "[REDACTED_PII]")
        assert_no_remaining_pattern(report["redacted_content"], "pii")

    def test_private_url_redaction(self) -> None:
        fixture = load_fixture("private-url-redacted")
        report = redact_artifact(fixture)

        assert report["redaction_status"] == "redacted"
        assert report["summary"]["urls_redacted"] >= 1

        assert_redaction_marker_present(report["redacted_content"], "[REDACTED_URL]")
        assert_no_remaining_pattern(report["redacted_content"], "url")

    def test_path_traversal_redaction(self) -> None:
        fixture = load_fixture("path-traversal-redacted")
        report = redact_artifact(fixture)

        assert report["redaction_status"] == "redacted"
        assert report["summary"]["paths_redacted"] >= 1

        assert_redaction_marker_present(report["redacted_content"], "[REDACTED_PATH]")
        assert_no_remaining_pattern(report["redacted_content"], "path")

    def test_private_key_redaction_critical(self) -> None:
        fixture = load_fixture("private-key-redacted")
        report = redact_artifact(fixture)

        assert report["redaction_status"] == "redacted"
        assert report["classification"] == "restricted"

        # Critical severity for private keys
        critical_log = [r for r in report["redaction_log"] if r.get("severity") == "critical"]
        assert len(critical_log) >= 1

        assert_redaction_marker_present(report["redacted_content"], "[REDACTED_SECRET]")
        assert "PRIVATE KEY" not in report["redacted_content"]

    def test_multiple_redactions_aggregated(self) -> None:
        fixture = load_fixture("multiple-redactions")
        report = redact_artifact(fixture)

        assert report["redaction_status"] == "redacted"
        assert report["summary"]["redactions_count"] >= 5
        assert report["summary"]["secrets_redacted"] >= 2
        assert report["summary"]["pii_redacted"] >= 1
        assert report["summary"]["paths_redacted"] >= 1
        assert report["summary"]["urls_redacted"] >= 1

        # All markers present
        assert "[REDACTED_SECRET]" in report["redacted_content"]
        assert "[REDACTED_PII]" in report["redacted_content"]
        assert "[REDACTED_PATH]" in report["redacted_content"]
        assert "[REDACTED_URL]" in report["redacted_content"]


class TestExportFilter:
    def test_quarantined_artifact_excluded(self) -> None:
        artifacts = [
            {
                "artifact_id": "clean-001",
                "classification": "public",
                "quarantine_status": "none",
                "redaction_status": "not_required",
                "safe_for_summary": True,
            },
            {
                "artifact_id": "quarantined-002",
                "classification": "restricted",
                "quarantine_status": "quarantined",
                "redaction_status": "redacted",
                "safe_for_summary": False,
            },
        ]
        report = filter_for_export(artifacts, "summary")

        assert report["export_ready"] is False
        assert len(report["allowed_artifacts"]) == 1
        assert len(report["excluded_artifacts"]) == 1
        assert report["excluded_artifacts"][0]["reason"] == "quarantined"
        assert report["summary"]["quarantined_excluded"] == 1

    def test_classification_filter_for_surface(self) -> None:
        artifacts = [
            {"artifact_id": "public-001", "classification": "public", "quarantine_status": "none", "safe_for_summary": True},
            {"artifact_id": "internal-002", "classification": "internal", "quarantine_status": "none", "safe_for_summary": True},
            {"artifact_id": "confidential-003", "classification": "confidential", "quarantine_status": "none", "safe_for_summary": True},
            {"artifact_id": "restricted-004", "classification": "restricted", "quarantine_status": "none", "safe_for_summary": True},
        ]

        # External export = only public
        ext_report = filter_for_export(artifacts, "external_export")
        assert len(ext_report["allowed_artifacts"]) == 1
        assert ext_report["allowed_artifacts"][0]["classification"] == "public"
        assert ext_report["readiness_effect"] in {"hold", "hard_dq"}

        # Dashboard = public + internal + confidential
        dash_report = filter_for_export(artifacts, "dashboard")
        assert len(dash_report["allowed_artifacts"]) == 3
        assert all(a["classification"] in {"public", "internal", "confidential"} for a in dash_report["allowed_artifacts"])

    def test_redaction_failed_blocks_export(self) -> None:
        artifacts = [
            {
                "artifact_id": "failed-001",
                "classification": "internal",
                "quarantine_status": "none",
                "redaction_status": "failed",
                "safe_for_summary": True,
            },
        ]
        report = filter_for_export(artifacts, "summary", profile="release")

        assert report["export_ready"] is False
        assert report["excluded_artifacts"][0]["reason"] == "redaction_failed"
        assert report["readiness_effect"] == "hard_dq"


class TestSummaryFilter:
    def test_quarantined_hidden_from_all_surfaces(self) -> None:
        artifacts = [
            {
                "artifact_id": "clean-001",
                "classification": "public",
                "quarantine_status": "none",
                "safe_for_summary": True,
                "readiness_effect": "pass",
            },
            {
                "artifact_id": "quarantined-002",
                "classification": "restricted",
                "quarantine_status": "quarantined",
                "safe_for_summary": False,
                "readiness_effect": "hard_dq",
            },
        ]
        report = filter_for_summary(artifacts, "dashboard")

        assert len(report["visible_artifacts"]) == 1
        assert len(report["hidden_artifacts"]) == 1
        assert report["hidden_artifacts"][0]["reason"] == "quarantined"

    def test_public_surface_only_shows_public(self) -> None:
        artifacts = [
            {"artifact_id": "public-001", "classification": "public", "quarantine_status": "none", "safe_for_summary": True, "readiness_effect": "pass"},
            {"artifact_id": "internal-002", "classification": "internal", "quarantine_status": "none", "safe_for_summary": True, "readiness_effect": "pass"},
        ]
        report = filter_for_summary(artifacts, "public")

        assert len(report["visible_artifacts"]) == 1
        assert report["visible_artifacts"][0]["classification"] == "public"
        assert len(report["hidden_artifacts"]) == 1
        assert report["hidden_artifacts"][0]["reason"] == "classification_not_visible"

    def test_readiness_effect_preserved(self) -> None:
        """CRITICAL: Summary filter NEVER changes readiness verdicts."""
        artifacts = [
            {"artifact_id": "gap-001", "classification": "internal", "quarantine_status": "none", "safe_for_summary": True, "readiness_effect": "soft_gap"},
            {"artifact_id": "dq-002", "classification": "public", "quarantine_status": "none", "safe_for_summary": True, "readiness_effect": "hard_dq"},
        ]
        report = filter_for_summary(artifacts, "dashboard")

        # Readiness should be preserved from input (worst = hard_dq)
        assert report["readiness_effect"] == "hard_dq"
        # NOT changed by summary filter
        assert all(a.get("original_readiness_effect") for a in report["visible_artifacts"])


class TestSchemaValidation:
    def test_redaction_report_schema_fields(self) -> None:
        fixture = load_fixture("redacted-secret-success")
        report = redact_artifact(fixture)

        required_fields = {
            "schema_version",
            "record_type",
            "redaction_id",
            "artifact_id",
            "artifact_path",
            "profile",
            "redacted_content",
            "redaction_log",
            "proof_hash",
            "redaction_status",
            "classification",
            "readiness_effect",
            "sourceRefs",
            "summary",
        }
        assert required_fields <= set(report)

    def test_export_filter_report_schema_fields(self) -> None:
        artifacts = [{"artifact_id": "test-001", "classification": "public", "quarantine_status": "none", "safe_for_summary": True}]
        report = filter_for_export(artifacts, "summary")

        required_fields = {
            "schema_version",
            "record_type",
            "filter_id",
            "surface",
            "profile",
            "export_ready",
            "readiness_effect",
            "allowed_artifacts",
            "excluded_artifacts",
            "hold_artifacts",
            "summary",
        }
        assert required_fields <= set(report)

    def test_summary_filter_report_schema_fields(self) -> None:
        artifacts = [{"artifact_id": "test-001", "classification": "public", "quarantine_status": "none", "safe_for_summary": True, "readiness_effect": "pass"}]
        report = filter_for_summary(artifacts, "dashboard")

        required_fields = {
            "schema_version",
            "record_type",
            "filter_id",
            "surface",
            "display_config",
            "visible_artifacts",
            "hidden_artifacts",
            "readiness_effect",
            "summary",
        }
        assert required_fields <= set(report)


class TestProfileEffects:
    def test_default_profile_secret_soft_gap_or_hard_dq(self) -> None:
        fixture = load_fixture("redacted-secret-success")
        fixture["profile"] = "default"
        report = redact_artifact(fixture)
        assert report["readiness_effect"] in {"hard_dq", "hold"}

    def test_release_profile_any_redaction_hard_dq(self) -> None:
        fixture = load_fixture("redacted-pii-success")
        report = redact_artifact(fixture)
        assert report["readiness_effect"] == "hard_dq"

    def test_strict_profile_hold_for_moderate_risks(self) -> None:
        fixture = load_fixture("private-url-redacted")
        report = redact_artifact(fixture)
        assert report["readiness_effect"] in {"hold", "hard_dq"}
