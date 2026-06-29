"""Tests for HATE-PG-005A artifact safety scanner."""

from __future__ import annotations

import json
import base64
from pathlib import Path

from hate.security.artifact_safety import scan_artifact_safety


FIXTURE_DIR = Path("fixtures/security/artifact-safety")
CANONICAL_FIXTURES = [
    "clean-metadata",
    "synthetic-pii-allowed",
    "public-doc-url-allowed",
    "fake-secret-allowlisted",
    "api-key-secret",
    "private-key-block",
    "unredacted-pii",
    "windows-user-path",
    "path-traversal",
    "signed-url",
    "base64-opaque-payload",
    "archive-without-manifest",
]


def load_fixture(name: str) -> dict:
    path = FIXTURE_DIR / name / "fixture.json"
    assert path.exists(), f"missing canonical fixture: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def load_flat_fixture(name: str) -> dict:
    path = FIXTURE_DIR / f"{name}.json"
    assert path.exists(), f"missing flat fixture: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def finding_types(report: dict) -> set[str]:
    return {finding["finding_type"] for finding in report["findings"]}


def first_finding(report: dict, finding_type: str) -> dict:
    for finding in report["findings"]:
        if finding["finding_type"] == finding_type:
            return finding
    raise AssertionError(f"missing finding_type={finding_type}: {report}")


def finding_with_reason(report: dict, reason_fragment: str) -> dict:
    for finding in report["findings"]:
        if reason_fragment in finding["reason"]:
            return finding
    raise AssertionError(f"missing reason fragment={reason_fragment}: {report}")


class TestCanonicalFixtures:
    def test_all_canonical_fixture_paths_exist(self) -> None:
        for name in CANONICAL_FIXTURES:
            assert (FIXTURE_DIR / name / "fixture.json").exists()

    def test_no_pytest_skip_used_for_missing_fixtures(self) -> None:
        source = Path(__file__).read_text(encoding="utf-8")
        assert "pytest" + "." + "skip" not in source


class TestArtifactSafetyScanner:
    def test_clean_metadata_passes(self) -> None:
        report = scan_artifact_safety(load_fixture("clean-metadata"))

        assert report["findings"] == []
        assert report["readiness_effect"] == "pass"
        assert report["quarantine_required"] is False
        assert report["redaction_required"] is False

    def test_fake_secret_with_allowlist_is_visible_soft_gap(self) -> None:
        report = scan_artifact_safety(load_fixture("fake-secret-allowlisted"))

        finding = first_finding(report, "secret_detected")
        assert finding["readiness_effect"] == "soft_gap"
        assert finding["quarantine_action"] == "none"
        assert finding["allowlist_ref"] == "ALLOWED-TEST-SECRET-001"
        assert report["quarantine_required"] is False

    def test_realistic_api_key_is_hard_dq_and_quarantined(self) -> None:
        report = scan_artifact_safety(load_fixture("api-key-secret"))

        finding = first_finding(report, "secret_detected")
        assert finding["readiness_effect"] == "hard_dq"
        assert finding["quarantine_action"] == "quarantine"
        assert report["quarantine_required"] is True
        assert report["readiness_effect"] == "hard_dq"

    def test_private_key_is_hard_dq(self) -> None:
        report = scan_artifact_safety(load_fixture("private-key-block"))

        finding = first_finding(report, "secret_detected")
        assert finding["severity"] == "critical"
        assert finding["readiness_effect"] == "hard_dq"
        assert report["quarantine_required"] is True

    def test_synthetic_pii_allowed_only_with_marker(self) -> None:
        allowed = scan_artifact_safety(load_fixture("synthetic-pii-allowed"))
        unallowed = scan_artifact_safety(
            {
                "artifact_id": "raw-pii",
                "artifact_path": "logs/pii.log",
                "profile": "release",
                "content": "email jane@example.com phone +1 415-555-7777",
            }
        )

        assert first_finding(allowed, "pii_detected")["readiness_effect"] == "soft_gap"
        assert allowed["quarantine_required"] is False
        assert first_finding(unallowed, "pii_detected")["readiness_effect"] == "hard_dq"
        assert unallowed["redaction_required"] is True

    def test_unredacted_pii_hard_dq_in_release_profile(self) -> None:
        report = scan_artifact_safety(load_fixture("unredacted-pii"))

        assert "pii_detected" in finding_types(report)
        assert report["readiness_effect"] == "hard_dq"
        assert report["redaction_required"] is True

    def test_windows_user_path_detected(self) -> None:
        report = scan_artifact_safety(load_fixture("windows-user-path"))

        finding = first_finding(report, "unsafe_path_detected")
        assert "Windows" in finding["reason"]
        assert finding["readiness_effect"] in {"hold", "hard_dq"}
        assert report["quarantine_required"] is True

    def test_path_traversal_hard_dq(self) -> None:
        report = scan_artifact_safety(load_fixture("path-traversal"))

        finding = first_finding(report, "unsafe_path_detected")
        assert "traversal" in finding["reason"]
        assert finding["readiness_effect"] == "hard_dq"
        assert report["quarantine_required"] is True

    def test_public_url_allowlist_passes(self) -> None:
        report = scan_artifact_safety(load_fixture("public-doc-url-allowed"))

        finding = first_finding(report, "external_url_detected")
        assert finding["readiness_effect"] == "pass"
        assert finding["quarantine_action"] == "none"
        assert report["readiness_effect"] == "pass"

    def test_signed_private_url_quarantined(self) -> None:
        report = scan_artifact_safety(load_fixture("signed-url"))

        finding = first_finding(report, "external_url_detected")
        assert finding["readiness_effect"] == "hard_dq"
        assert finding["quarantine_action"] == "quarantine"
        assert report["quarantine_required"] is True

    def test_base64_opaque_payload_quarantined(self) -> None:
        encoded = base64.b64encode(b"A" * 4097).decode("ascii")
        report = scan_artifact_safety(
            {
                "artifact_id": "base64-over-4kb",
                "artifact_path": "logs/blob.txt",
                "profile": "product",
                "content": f"payload={encoded}",
            }
        )

        finding = first_finding(report, "archive_or_binary_risk")
        assert "4KB" in finding["reason"]
        assert finding["quarantine_action"] == "quarantine"
        assert report["readiness_effect"] == "hard_dq"

    def test_base64_under_4kb_does_not_trigger(self) -> None:
        report = scan_artifact_safety(load_fixture("base64-opaque-payload"))

        assert "archive_or_binary_risk" not in finding_types(report)

    def test_archive_without_manifest_quarantined(self) -> None:
        report = scan_artifact_safety(load_fixture("archive-without-manifest"))

        finding = first_finding(report, "archive_or_binary_risk")
        assert "without manifest" in finding["reason"]
        assert report["quarantine_required"] is True

    def test_flat_archive_size_fixture_is_quarantined(self) -> None:
        report = scan_artifact_safety(load_flat_fixture("quarantine-archive-size"))

        finding = finding_with_reason(report, "50MB")
        assert "50MB" in finding["reason"]
        assert finding["quarantine_action"] == "quarantine"
        assert report["readiness_effect"] == "hard_dq"

    def test_flat_nested_archive_fixture_is_quarantined(self) -> None:
        report = scan_artifact_safety(load_flat_fixture("quarantine-nested-archive"))

        finding = finding_with_reason(report, "nested archive")
        assert "nested archive" in finding["reason"]
        assert report["quarantine_required"] is True

    def test_flat_secret_fixture_is_scanned_from_nested_json(self) -> None:
        report = scan_artifact_safety(load_flat_fixture("hard-dq-secret-exposed"))

        finding = first_finding(report, "secret_detected")
        assert finding["readiness_effect"] in {"soft_gap", "hold", "hard_dq"}
        assert report["quarantine_required"] is True

    def test_profile_effects_for_external_url_risk(self) -> None:
        effects = {}
        for profile in ["default", "strict", "release"]:
            report = scan_artifact_safety(
                {
                    "artifact_id": f"url-{profile}",
                    "artifact_path": "logs/url.txt",
                    "profile": profile,
                    "content": "callback=https://example.invalid/webhook",
                }
            )
            effects[profile] = first_finding(report, "external_url_detected")["readiness_effect"]

        assert effects == {"default": "soft_gap", "strict": "hold", "release": "hard_dq"}

    def test_source_refs_are_aggregated(self) -> None:
        report = scan_artifact_safety(load_fixture("api-key-secret"))

        assert "logs/runtime.log" in report["sourceRefs"]
        assert any(ref.startswith("logs/runtime.log:") for ref in report["sourceRefs"])

    def test_report_shape_contains_required_fields(self) -> None:
        report = scan_artifact_safety(load_fixture("api-key-secret"))
        required_report_fields = {
            "schema_version",
            "record_type",
            "artifact_id",
            "profile",
            "findings",
            "quarantine_required",
            "redaction_required",
            "readiness_effect",
            "sourceRefs",
            "summary",
        }
        required_finding_fields = {
            "finding_id",
            "detector_id",
            "finding_type",
            "severity",
            "confidence",
            "reason",
            "sourceRef",
            "location",
            "span",
            "redaction_hint",
            "quarantine_action",
            "readiness_effect",
            "allowlist_ref",
            "policy_refs",
        }

        assert required_report_fields <= set(report)
        assert required_finding_fields <= set(report["findings"][0])


class TestArtifactSafetySchema:
    def test_schema_accepts_generated_report(self) -> None:
        schema = json.loads(
            Path("schemas/HATE/v1/artifact-safety-report.schema.json").read_text(
                encoding="utf-8"
            )
        )
        report = scan_artifact_safety(load_fixture("api-key-secret"))

        assert set(schema["required"]) <= set(report)
        finding_schema = schema["properties"]["findings"]["items"]
        assert set(finding_schema["required"]) <= set(report["findings"][0])
        assert report["record_type"] in schema["properties"]["record_type"]["enum"]
        assert report["readiness_effect"] in schema["properties"]["readiness_effect"]["enum"]
        assert report["findings"][0]["finding_type"] in finding_schema["properties"]["finding_type"]["enum"]
