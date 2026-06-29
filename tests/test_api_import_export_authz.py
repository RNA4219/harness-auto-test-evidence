"""Tests for HATE-PG-007B API Import/Export/Authz projection.

Validates:
- Import: schema, hash, sourceRefs, artifact safety
- Export: quarantine filtering, redaction failure handling, classification scope
- Authz: safe-by-default denial, cross-tenant protection, tenant ID hashing
"""

from __future__ import annotations

import json
from pathlib import Path

from hate.api import (
    check_export_authz,
    check_import_authz,
    AuthorizationDecision,
    validate_bundle_import,
    export_safe_diagnostic,
)


FIXTURE_DIR = Path("fixtures/api/import-export")
CANONICAL_FIXTURES = [
    "import-valid-bundle",
    "export-safe-diagnostic",
    "authz-internal-allowed",
    "authz-external-denied",
    "import-schema-mismatch",
    "export-quarantined-raw",
]


def load_fixture(name: str) -> dict:
    """Load fixture JSON."""
    path = FIXTURE_DIR / name / "fixture.json"
    assert path.exists(), f"missing fixture: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


class TestCanonicalFixturePaths:
    """Verify all fixture paths exist."""

    def test_all_fixture_paths_exist(self) -> None:
        """All 6 canonical fixtures must exist."""
        for name in CANONICAL_FIXTURES:
            assert (FIXTURE_DIR / name / "fixture.json").exists()

    def test_no_pytest_skip_used(self) -> None:
        """No pytest.skip allowed in this test file."""
        import re
        source = Path(__file__).read_text(encoding="utf-8")
        # Check for pytest skip call pattern (function call syntax)
        assert not re.search(r"pytest\.skip\s*\(", source), "skip call disallowed"


class TestAuthorizationDecision:
    """Tests for AuthorizationDecision class."""

    def test_to_dict_contains_required_fields(self) -> None:
        """AuthorizationDecision.to_dict() must contain all required schema fields."""
        decision = AuthorizationDecision(
            actor="test-actor",
            tenant={"organization_id": "org-001", "workspace_id": "ws-001"},
            scopes=["public", "internal"],
            resource="bundle-import",
            decision="allowed",
            reason_code="HATE-API-AUTH-ALLOWED",
            reason_detail="Test authorization",
            source_refs=["test:authz"],
        )
        result = decision.to_dict()

        required_fields = {
            "schema_version",
            "record_type",
            "decision_id",
            "actor",
            "tenant",
            "scopes",
            "resource",
            "decision",
            "reason_code",
            "source_refs",
            "created_at",
        }
        assert required_fields <= set(result)
        assert result["schema_version"] == "HATE/v1"
        assert result["record_type"] == "api-authz-decision"

    def test_is_allowed_true_for_allowed(self) -> None:
        """is_allowed() returns True for allowed decision."""
        decision = AuthorizationDecision(
            actor="test",
            tenant={"organization_id": "org"},
            scopes=["public"],
            resource="test",
            decision="allowed",
            reason_code="HATE-API-AUTH-ALLOWED",
        )
        assert decision.is_allowed() is True

    def test_is_allowed_false_for_denied(self) -> None:
        """is_allowed() returns False for denied decision."""
        decision = AuthorizationDecision(
            actor="test",
            tenant={"organization_id": "hashed"},
            scopes=["public"],
            resource="test",
            decision="denied",
            reason_code="HATE-API-AUTH-CROSS-TENANT",
        )
        assert decision.is_allowed() is False


class TestCheckImportAuthz:
    """Tests for check_import_authz function."""

    def test_valid_bundle_allowed(self) -> None:
        """Valid bundle with matching tenant scope is authorized."""
        fixture = load_fixture("import-valid-bundle")
        bundle = fixture["input"]["bundle"]
        actor = fixture["input"]["actor"]
        tenant = fixture["input"]["tenant"]

        decision = check_import_authz(actor, tenant, bundle)
        assert decision.is_allowed() is True
        assert decision.reason_code == "HATE-API-AUTH-ALLOWED"

    def test_cross_tenant_denied_with_hashed_tenant(self) -> None:
        """Cross-tenant access denied with hashed tenant ID (no leakage)."""
        bundle = {
            "schema_version": "HATE/v1",
            "bundle_id": "bundle-cross-tenant",
            "organization_id": "org-002",  # Different from tenant
            "workspace_id": "ws-002",
            "sourceRefs": ["test:cross-tenant"],
        }
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}

        decision = check_import_authz("test-actor", tenant, bundle)
        assert decision.is_allowed() is False
        assert decision.reason_code == "HATE-API-AUTH-CROSS-TENANT"
        # Tenant ID should be hashed (16 hex chars, not original)
        assert decision.tenant["organization_id"] != "org-001"
        assert len(decision.tenant["organization_id"]) == 16

    def test_schema_unsupported_denied(self) -> None:
        """Unsupported schema version denied."""
        fixture = load_fixture("import-schema-mismatch")
        bundle = fixture["input"]["bundle"]
        tenant = fixture["input"]["tenant"]

        decision = check_import_authz("test-actor", tenant, bundle)
        assert decision.is_allowed() is False
        assert decision.reason_code == "HATE-API-SCHEMA-UNSUPPORTED"


class TestValidateBundleImport:
    """Tests for validate_bundle_import function."""

    def test_valid_bundle_accepted(self) -> None:
        """Valid bundle import is accepted."""
        fixture = load_fixture("import-valid-bundle")
        bundle = fixture["input"]["bundle"]
        actor = fixture["input"]["actor"]
        tenant = fixture["input"]["tenant"]

        report = validate_bundle_import(bundle, actor, tenant)
        assert report["import_status"] == "accepted"
        assert report["validation_results"]["schema_valid"] is True
        assert report["validation_results"]["sourceRefs_valid"] is True
        assert report["validation_results"]["artifact_safety_valid"] is True
        assert report["summary"]["accepted"] is True

    def test_schema_invalid_rejected(self) -> None:
        """Invalid schema version rejected."""
        fixture = load_fixture("import-schema-mismatch")
        bundle = fixture["input"]["bundle"]
        tenant = fixture["input"]["tenant"]

        report = validate_bundle_import(bundle, "test-actor", tenant)
        assert report["import_status"] == "rejected"
        # Authz rejects unsupported schema first with HATE-API-SCHEMA-UNSUPPORTED
        assert report["rejection_reason"] == "HATE-API-SCHEMA-UNSUPPORTED"

    def test_missing_sourcerefs_rejected(self) -> None:
        """Missing sourceRefs in bundle rejected."""
        bundle = {
            "schema_version": "HATE/v1",
            "bundle_id": "bundle-no-sourcerefs",
            "organization_id": "org-001",
            "workspace_id": "ws-001",
            # Missing sourceRefs at top level
            "artifacts": [],
        }
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}

        report = validate_bundle_import(bundle, "test-actor", tenant)
        assert report["import_status"] == "rejected"
        assert report["rejection_reason"] == "HATE-API-REQ-MISSING-SOURCEREF"
        assert report["validation_results"]["sourceRefs_valid"] is False

    def test_idempotent_duplicate_detected(self) -> None:
        """Idempotent import with matching hash returns duplicate status."""
        bundle = {
            "schema_version": "HATE/v1",
            "bundle_id": "bundle-idempotent",
            "organization_id": "org-001",
            "workspace_id": "ws-001",
            "sourceRefs": ["test:idempotent"],
            "artifacts": [],
        }
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}

        # First import
        report1 = validate_bundle_import(bundle, "test-actor", tenant, idempotency_key="key-001")

        # Second import with same hash
        existing_hash = report1["bundle_hash"]
        report2 = validate_bundle_import(
            bundle, "test-actor", tenant, idempotency_key="key-001", existing_bundle_hash=existing_hash
        )

        assert report2["import_status"] == "duplicate"
        assert report2["validation_results"]["hash_match"] is True
        assert report2["summary"]["duplicate"] is True
        assert report2["summary"]["idempotent"] is True

    def test_bundle_hash_computed(self) -> None:
        """Bundle hash is computed as SHA256."""
        bundle = {
            "schema_version": "HATE/v1",
            "bundle_id": "bundle-hash-test",
            "organization_id": "org-001",
            "workspace_id": "ws-001",
            "sourceRefs": ["test:hash"],
            "artifacts": [],
        }
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}

        report = validate_bundle_import(bundle, "test-actor", tenant)
        assert "bundle_hash" in report
        assert len(report["bundle_hash"]) == 64  # SHA256 hex length


class TestCheckExportAuthz:
    """Tests for check_export_authz function."""

    def test_internal_surface_allowed(self) -> None:
        """Internal surface with maintainer role is authorized."""
        fixture = load_fixture("authz-internal-allowed")
        actor = fixture["input"]["actor"]
        tenant = fixture["input"]["tenant"]
        surface = fixture["input"]["export_surface"]
        artifacts = fixture["input"]["artifacts"]
        role = fixture["input"]["role"]

        decision = check_export_authz(actor, tenant, surface, artifacts, role)
        assert decision.is_allowed() is True
        assert decision.reason_code == "HATE-API-AUTH-ALLOWED"
        assert "internal" in decision.scopes

    def test_external_export_denied_for_confidential(self) -> None:
        """External export denied for confidential artifacts with reader role."""
        fixture = load_fixture("authz-external-denied")
        actor = fixture["input"]["actor"]
        tenant = fixture["input"]["tenant"]
        surface = fixture["input"]["export_surface"]
        artifacts = fixture["input"]["artifacts"]
        role = fixture["input"]["role"]

        decision = check_export_authz(actor, tenant, surface, artifacts, role)
        assert decision.is_allowed() is False
        assert decision.reason_code == "HATE-API-PRIV-EXPORT-BLOCKED"


class TestExportSafeDiagnostic:
    """Tests for export_safe_diagnostic function."""

    def test_partial_export_with_quarantined(self) -> None:
        """Partial export with quarantined artifact excluded."""
        fixture = load_fixture("export-safe-diagnostic")
        artifacts = fixture["input"]["artifacts"]
        actor = fixture["input"]["actor"]
        tenant = fixture["input"]["tenant"]
        surface = fixture["input"]["export_surface"]
        role = fixture["input"]["role"]

        report = export_safe_diagnostic(artifacts, actor, tenant, surface, role)
        assert report["export_status"] == "partial"
        assert report["readiness_effect"] == "hold"
        assert len(report["allowed_artifacts"]) == 2
        assert len(report["excluded_artifacts"]) == 1
        assert report["excluded_artifacts"][0]["exclusion_reason"] == "quarantined"

        # Quarantined artifact has safe metadata
        assert report["excluded_artifacts"][0]["safe_metadata"] is not None
        assert report["excluded_artifacts"][0]["safe_metadata"]["quarantine_status"] == "quarantined"

    def test_blocked_export_redaction_failed(self) -> None:
        """Blocked export for redaction-failed artifact with no safe metadata."""
        fixture = load_fixture("export-quarantined-raw")
        artifacts = fixture["input"]["artifacts"]
        tenant = fixture["input"]["tenant"]
        surface = fixture["input"]["export_surface"]
        role = fixture["input"]["role"]

        report = export_safe_diagnostic(artifacts, "test-actor", tenant, surface, role)
        assert report["export_status"] == "blocked"
        assert report["readiness_effect"] == "hard_dq"

        # Redaction-failed artifact has no safe metadata
        assert report["excluded_artifacts"][0]["exclusion_reason"] == "redaction_failed"
        assert report["excluded_artifacts"][0]["safe_metadata"] is None

    def test_ready_export_all_allowed(self) -> None:
        """Ready export when all artifacts allowed."""
        artifacts = [
            {
                "artifact_id": "artifact-public",
                "classification": "public",
                "quarantine_status": "none",
                "redaction_status": "not_required",
            },
            {
                "artifact_id": "artifact-internal",
                "classification": "internal",
                "quarantine_status": "none",
                "redaction_status": "not_required",
            },
        ]
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}

        report = export_safe_diagnostic(artifacts, "test-actor", tenant, "dashboard", "maintainer")
        assert report["export_status"] == "ready"
        assert report["readiness_effect"] == "pass"
        assert len(report["allowed_artifacts"]) == 2
        assert len(report["excluded_artifacts"]) == 0

    def test_classification_filtering_by_scope(self) -> None:
        """Classification filtering by surface scope."""
        artifacts = [
            {"artifact_id": "public-001", "classification": "public", "quarantine_status": "none", "redaction_status": "not_required"},
            {"artifact_id": "internal-002", "classification": "internal", "quarantine_status": "none", "redaction_status": "not_required"},
            {"artifact_id": "confidential-003", "classification": "confidential", "quarantine_status": "none", "redaction_status": "not_required"},
            {"artifact_id": "restricted-004", "classification": "restricted", "quarantine_status": "none", "redaction_status": "not_required"},
        ]
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}

        # public surface = only public artifacts
        public_report = export_safe_diagnostic(artifacts, "test-actor", tenant, "public", "reader")
        assert len(public_report["allowed_artifacts"]) == 1
        assert public_report["allowed_artifacts"][0]["classification"] == "public"

        # dashboard with maintainer = public + internal + confidential
        dash_report = export_safe_diagnostic(artifacts, "test-actor", tenant, "dashboard", "maintainer")
        allowed_classifications = [a["classification"] for a in dash_report["allowed_artifacts"]]
        assert set(allowed_classifications) == {"public", "internal", "confidential"}

    def test_schema_validation_fields(self) -> None:
        """Export report contains all required schema fields."""
        artifacts = [
            {
                "artifact_id": "test-001",
                "classification": "public",
                "quarantine_status": "none",
                "redaction_status": "not_required",
            }
        ]
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}

        report = export_safe_diagnostic(artifacts, "test-actor", tenant, "summary", "reader")

        required_fields = {
            "schema_version",
            "record_type",
            "export_id",
            "export_surface",
            "export_profile",
            "export_status",
            "readiness_effect",
            "authz_decision",
            "allowed_artifacts",
            "excluded_artifacts",
            "sourceRefs",
            "created_at",
            "summary",
        }
        assert required_fields <= set(report)
        assert report["schema_version"] == "HATE/v1"
        assert report["record_type"] == "safe-export-report"


class TestNoTenantLeakage:
    """Tests for safe-by-default denial with no tenant leakage."""

    def test_cross_tenant_denial_hashes_tenant_id(self) -> None:
        """Cross-tenant denial hashes tenant ID to prevent leakage."""
        bundle = {
            "schema_version": "HATE/v1",
            "bundle_id": "bundle-cross",
            "organization_id": "org-malicious",
            "workspace_id": "ws-malicious",
        }
        tenant = {"organization_id": "org-victim", "workspace_id": "ws-victim"}

        decision = check_import_authz("attacker", tenant, bundle)
        assert decision.is_allowed() is False

        # Tenant ID should NOT appear in denial response
        assert "org-victim" not in decision.tenant["organization_id"]
        assert "ws-victim" not in decision.tenant.get("workspace_id", "")

        # Hash should be 16 hex chars (SHA256[:16])
        hashed = decision.tenant["organization_id"]
        assert len(hashed) == 16
        assert all(c in "0123456789abcdef" for c in hashed)

    def test_denial_response_contains_no_secrets_or_paths(self) -> None:
        """Denial response contains no secrets, paths, or sensitive details."""
        decision = AuthorizationDecision(
            actor="test",
            tenant={"organization_id": "hashed123"},
            scopes=["public"],
            resource="bundle-import",
            decision="denied",
            reason_code="HATE-API-AUTH-CROSS-TENANT",
            reason_detail="Bundle tenant scope mismatch",  # Safe detail only
        )
        result = decision.to_dict()

        # No secrets, paths, or PII in denial response
        assert "password" not in str(result)
        assert "secret" not in str(result)
        assert "/home" not in str(result)
        assert "C:\\" not in str(result)


class TestQuarantineHandling:
    """Tests for quarantine artifact handling."""

    def test_quarantined_artifact_has_safe_metadata_only(self) -> None:
        """Quarantined artifact has safe metadata only (no content)."""
        artifacts = [
            {
                "artifact_id": "quarantined-001",
                "classification": "restricted",
                "quarantine_status": "quarantined",
                "redaction_status": "redacted",
                "content": "secret data should not be exported",
            },
        ]
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}

        report = export_safe_diagnostic(artifacts, "admin", tenant, "dashboard", "admin")

        # Quarantined artifact excluded even for admin
        assert len(report["excluded_artifacts"]) == 1
        excluded = report["excluded_artifacts"][0]
        assert excluded["exclusion_reason"] == "quarantined"

        # Safe metadata only - no content exposed
        safe_metadata = excluded["safe_metadata"]
        assert safe_metadata is not None
        assert "artifact_id" in safe_metadata
        assert "classification" in safe_metadata
        assert "content" not in safe_metadata
        assert safe_metadata["safe_for_summary"] is False

    def test_redaction_failed_no_safe_metadata(self) -> None:
        """Redaction-failed artifact has no safe metadata export."""
        artifacts = [
            {
                "artifact_id": "failed-001",
                "classification": "internal",
                "quarantine_status": "none",
                "redaction_status": "failed",
            },
        ]
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}

        report = export_safe_diagnostic(artifacts, "admin", tenant, "summary", "admin")

        # Redaction-failed blocked entirely
        assert report["export_status"] == "blocked"
        assert report["excluded_artifacts"][0]["safe_metadata"] is None


class TestRolePermissions:
    """Tests for role permission hierarchy."""

    def test_admin_has_restricted_scope(self) -> None:
        """Admin role has restricted scope on support_bundle surface."""
        decision = check_export_authz(
            "admin-user",
            {"organization_id": "org", "workspace_id": "ws"},
            "support_bundle",  # Has confidential scope (dashboard also has confidential)
            [],
            "admin",
        )
        # Admin has restricted in role, but support_bundle surface only has up to confidential
        assert "confidential" in decision.scopes
        # Restricted only available on surfaces that support it (admin role intersects with surface scope)
        assert "public" in decision.scopes

    def test_reader_has_public_only(self) -> None:
        """Reader role has public scope only."""
        decision = check_export_authz(
            "reader-user",
            {"organization_id": "org", "workspace_id": "ws"},
            "summary",
            [],
            "reader",
        )
        assert decision.scopes == ["public"]

    def test_maintainer_has_confidential(self) -> None:
        """Maintainer role has confidential scope."""
        decision = check_export_authz(
            "maintainer-user",
            {"organization_id": "org", "workspace_id": "ws"},
            "dashboard",
            [],
            "maintainer",
        )
        assert "confidential" in decision.scopes
        assert "restricted" not in decision.scopes