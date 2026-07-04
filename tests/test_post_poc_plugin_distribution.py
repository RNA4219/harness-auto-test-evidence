from __future__ import annotations

import json
from pathlib import Path

from hate.post_poc.plugin_distribution import (
    build_plugin_distribution_report,
    build_plugin_install_manifest,
    evaluate_plugin_distribution_fixture,
    write_plugin_install_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc" / "plugin-distribution"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "plugin-distribution-report.schema.json"
INSTALL_MANIFEST_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "plugin-install-manifest.schema.json"
PACKAGE_MANIFEST_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "plugin-package-manifest.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    package_schema = json.loads(PACKAGE_MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "plugin-distribution-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert report["package_manifest"]["record_type"] == "plugin-package-manifest"
    assert set(package_schema["required"]) <= set(report["package_manifest"])
    assert isinstance(report["package_manifest"]["signature_valid"], bool)
    assert isinstance(report["package_manifest"]["capabilities"], list)
    assert report["signature_verification"]["record_type"] == "plugin-signature-verification"
    assert report["revocation_event"]["record_type"] == "plugin-revocation-event"
    assert report["distribution_index"]["record_type"] == "plugin-distribution-index"
    if report["sandbox_execution_report"] is not None:
        assert report["sandbox_execution_report"]["record_type"] == "platform-plugin-sandbox-report"
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def _assert_install_manifest_contract(manifest: dict) -> None:
    schema = json.loads(INSTALL_MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(manifest)
    assert manifest["schema_version"] == "HATE/v1"
    assert manifest["record_type"] == "plugin-install-manifest"
    assert manifest["summary"]["entry_count"] == len(manifest["entries"])
    assert manifest["summary"]["finding_count"] == len(manifest["findings"])
    for entry in manifest["entries"]:
        assert set(schema["properties"]["entries"]["items"]["required"]) <= set(entry)
        assert entry["record_type"] == "plugin-install-entry"
        assert isinstance(entry["installable"], bool)
        assert isinstance(entry["install_block_reasons"], list)
    for finding in manifest["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_task_postpoc_006_canonical_fixture_paths_exist() -> None:
    for name in [
        "signed-allowed",
        "unsigned-release-denied",
        "revoked-plugin-denied",
        "api-migration-required",
        "stale-index-holds",
    ]:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_signed_allowed_release_plugin_passes() -> None:
    result = evaluate_plugin_distribution_fixture(_fixture("signed-allowed"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["report"]["summary"]["trusted"] is True
    _assert_report_contract(result["report"])


def test_unsigned_release_plugin_is_denied() -> None:
    result = evaluate_plugin_distribution_fixture(_fixture("unsigned-release-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "plugin_signature_invalid"
    assert "plugin_allowlist_missing" in _codes(result["report"])


def test_revoked_plugin_is_denied() -> None:
    result = evaluate_plugin_distribution_fixture(_fixture("revoked-plugin-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "plugin_revoked"
    assert result["report"]["revocation_event"]["revoked"] is True


def test_api_migration_required_holds() -> None:
    result = evaluate_plugin_distribution_fixture(_fixture("api-migration-required"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "plugin_api_migration_required"
    assert result["report"]["package_manifest"]["compatibility_status"] == "migration_required"


def test_stale_distribution_index_holds() -> None:
    result = evaluate_plugin_distribution_fixture(_fixture("stale-index-holds"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "plugin_distribution_index_stale"
    assert result["report"]["summary"]["index_stale"] is True


def test_package_hash_mismatch_holds() -> None:
    report = build_plugin_distribution_report({
        "profile": "release",
        "manifest": {
            "plugin_id": "detector.hash",
            "plugin_version": "1.0.0",
            "api_version": "HATE-plugin/v1",
            "package_hash": "sha256:expected",
            "observed_package_hash": "sha256:actual",
            "signature_ref": "signature://detector.hash",
            "signature_valid": True,
            "allowlist_ref": "allowlist://detector.hash",
            "compatibility_status": "compatible",
        },
        "distribution_index": {"indexed_package_hash": "sha256:expected"},
    })

    assert report["overall_status"] == "hold"
    assert "plugin_package_hash_mismatch" in _codes(report)


def test_regulated_unallowlisted_plugin_is_denied() -> None:
    report = build_plugin_distribution_report({
        "profile": "regulated",
        "manifest": {
            "plugin_id": "detector.unallowlisted",
            "plugin_version": "1.0.0",
            "api_version": "HATE-plugin/v1",
            "package_hash": "sha256:p",
            "observed_package_hash": "sha256:p",
            "signature_ref": "signature://detector.unallowlisted",
            "signature_valid": True,
            "compatibility_status": "compatible",
        },
        "distribution_index": {"indexed_package_hash": "sha256:p"},
    })

    assert report["overall_status"] == "hold"
    assert "plugin_allowlist_missing" in _codes(report)


def test_default_profile_can_report_unsigned_without_release_denial() -> None:
    report = build_plugin_distribution_report({
        "profile": "default",
        "manifest": {
            "plugin_id": "detector.local",
            "plugin_version": "0.1.0",
            "api_version": "HATE-plugin/v1",
            "package_hash": "sha256:p",
            "observed_package_hash": "sha256:p",
            "compatibility_status": "compatible",
        },
        "distribution_index": {"indexed_package_hash": "sha256:p"},
    })

    assert report["overall_status"] == "pass"
    assert "plugin_signature_invalid" not in _codes(report)


def test_distribution_report_accepts_passing_sandbox_execution_evidence() -> None:
    report = build_plugin_distribution_report({
        "profile": "release",
        "manifest": {
            "plugin_id": "detector.sandboxed",
            "plugin_version": "1.0.0",
            "api_version": "HATE-plugin/v1",
            "package_hash": "sha256:p",
            "observed_package_hash": "sha256:p",
            "signature_ref": "signature://detector.sandboxed",
            "signature_valid": True,
            "allowlist_ref": "allowlist://detector.sandboxed",
            "compatibility_status": "compatible",
        },
        "distribution_index": {"indexed_package_hash": "sha256:p"},
        "sandbox": {
            "limits": {"timeout_ms": 1000, "max_output_bytes": 4096, "max_input_bytes": 4096, "max_memory_mb": 256},
            "input_bundle": {"redacted_canonical_input": True, "read_only_artifact_metadata": True},
            "execution": {
                "output_bytes": 128,
                "output": {
                    "schema_version": "HATE/plugin-output/v1",
                    "detector_id": "detector.sandboxed",
                    "sourceRefs": ["fixture://sandbox/pass"],
                },
            },
        },
    })

    assert report["overall_status"] == "pass"
    assert report["summary"]["sandbox_status"] == "pass"
    assert report["sandbox_execution_report"]["summary"]["platform_continues"] is True


def test_distribution_report_holds_when_sandbox_execution_is_unsafe() -> None:
    report = build_plugin_distribution_report({
        "profile": "release",
        "manifest": {
            "plugin_id": "detector.unsafe",
            "plugin_version": "1.0.0",
            "api_version": "HATE-plugin/v1",
            "package_hash": "sha256:p",
            "observed_package_hash": "sha256:p",
            "signature_ref": "signature://detector.unsafe",
            "signature_valid": True,
            "allowlist_ref": "allowlist://detector.unsafe",
            "compatibility_status": "compatible",
        },
        "distribution_index": {"indexed_package_hash": "sha256:p"},
        "sandbox": {
            "limits": {"timeout_ms": 1000, "max_output_bytes": 4096, "max_input_bytes": 4096},
            "input_bundle": {"secrets": True},
            "execution": {"network_access_attempted": True, "network_mode": "none"},
        },
    })

    assert report["overall_status"] == "hold"
    assert "plugin_sandbox_execution_hold" in _codes(report)
    sandbox_codes = [finding["code"] for finding in report["sandbox_execution_report"]["findings"]]
    assert "plugin_forbidden_filesystem_access" in sandbox_codes
    assert "plugin_forbidden_network_access" in sandbox_codes


def test_plugin_distribution_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["plugin-distribution-report"] == "schemas/HATE/v1/plugin-distribution-report.schema.json"
    assert records["plugin-package-manifest"] == "schemas/HATE/v1/plugin-package-manifest.schema.json"
    assert records["plugin-install-manifest"] == "schemas/HATE/v1/plugin-install-manifest.schema.json"


def test_plugin_install_manifest_marks_signed_allowed_plugin_installable() -> None:
    input_data = json.loads(json.dumps(_fixture("signed-allowed")["input"]))
    input_data["distribution_index"]["index_ref"] = "plugin-index://detector.signed/1.0.0"

    manifest = build_plugin_install_manifest(input_data, source_refs=["fixture://plugin/installable"])

    assert manifest["record_type"] == "plugin-install-manifest"
    assert manifest["summary"]["installable_count"] == 1
    assert manifest["summary"]["blocked_count"] == 0
    assert manifest["findings"] == []
    entry = manifest["entries"][0]
    assert entry["installable"] is True
    assert entry["plugin_id"]
    assert entry["index_ref"] == "plugin-index://detector.signed/1.0.0"
    assert manifest["sourceRefs"] == ["fixture://plugin/installable"]
    _assert_install_manifest_contract(manifest)


def test_plugin_install_manifest_blocks_revoked_plugin() -> None:
    manifest = build_plugin_install_manifest(_fixture("revoked-plugin-denied")["input"])

    assert manifest["summary"]["installable_count"] == 0
    assert manifest["entries"][0]["installable"] is False
    assert "plugin_revoked" in manifest["entries"][0]["install_block_reasons"]
    assert "plugin_install_blocked" in _codes(manifest)


def test_plugin_install_manifest_blocks_migration_required_plugin() -> None:
    manifest = build_plugin_install_manifest(_fixture("api-migration-required")["input"])

    assert manifest["entries"][0]["installable"] is False
    assert "plugin_api_migration_required" in manifest["entries"][0]["install_block_reasons"]


def test_plugin_install_manifest_blocks_unsafe_sandbox_report() -> None:
    report = build_plugin_distribution_report({
        "profile": "release",
        "manifest": {
            "plugin_id": "detector.unsafe",
            "plugin_version": "1.0.0",
            "api_version": "HATE-plugin/v1",
            "package_hash": "sha256:p",
            "observed_package_hash": "sha256:p",
            "signature_ref": "signature://detector.unsafe",
            "signature_valid": True,
            "allowlist_ref": "allowlist://detector.unsafe",
            "compatibility_status": "compatible",
        },
        "distribution_index": {"index_ref": "plugin-index://unsafe", "indexed_package_hash": "sha256:p"},
        "sandbox": {
            "limits": {"timeout_ms": 1000, "max_output_bytes": 4096, "max_input_bytes": 4096},
            "input_bundle": {"secrets": True},
            "execution": {"network_access_attempted": True, "network_mode": "none"},
        },
    })

    manifest = build_plugin_install_manifest(report)

    assert manifest["entries"][0]["installable"] is False
    assert "plugin_sandbox_execution_hold" in manifest["entries"][0]["install_block_reasons"]


def test_plugin_install_manifest_write_contract(tmp_path: Path) -> None:
    input_data = json.loads(json.dumps(_fixture("signed-allowed")["input"]))
    input_data["distribution_index"]["index_ref"] = "plugin-index://detector.signed/1.0.0"
    manifest = build_plugin_install_manifest(input_data, source_refs=["fixture://plugin/manifest"])
    out_path = tmp_path / "plugin-install.json"

    artifact = write_plugin_install_manifest(manifest, out_path)

    assert artifact["record_type"] == "plugin-install-manifest-artifact"
    assert artifact["entry_count"] == 1
    assert artifact["sourceRefs"] == ["fixture://plugin/manifest"]
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["record_type"] == "plugin-install-manifest"
    assert written["entries"][0]["installable"] is True
    _assert_install_manifest_contract(written)
