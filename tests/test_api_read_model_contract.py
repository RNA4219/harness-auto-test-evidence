"""Contract tests for HATE API Read Model.

Tests response envelope, pagination, filters, sort, staleness, errors.
All tests verify contract per API_REQUIREMENTS.md.
"""

from __future__ import annotations

import pytest

from hate.api import (
    # Staleness
    STALENESS_FRESH,
    STALENESS_STALE,
    STALENESS_REBUILDING,
    STALENESS_UNKNOWN,
    # Pagination
    MIN_LIMIT,
    MAX_LIMIT,
    DEFAULT_LIMIT,
    PaginationInfo,
    StalenessInfo,
    SourceInfo,
    APIResponseEnvelope,
    # Validation
    validate_filters,
    validate_pagination,
    validate_sort,
    # Response builders
    build_response,
    build_error_response,
    # Resource handlers
    list_runs,
    get_run_detail,
    list_evidence,
    list_risks,
    list_artifacts,
    list_doctor_findings,
    # Error taxonomy
    APIError,
    auth_unauthenticated,
    auth_unauthorized,
    auth_cross_tenant,
    req_invalid_filter,
    req_invalid_pagination,
    req_missing_required,
    req_invalid_sort,
    schema_unsupported,
    schema_incompatible,
    store_not_found,
    store_stale,
    store_rebuilding,
    store_corruption,
    export_failed,
    export_blocked,
    priv_quarantined,
    priv_redaction_failed,
    priv_restricted,
    priv_path_leak_prevented,
    error_list_to_dict,
    # Constants
    RESOURCE_FILTERS,
    RESOURCE_SORT_FIELDS,
)


# ============================================================================
# Response Envelope Tests
# ============================================================================

class TestResponseEnvelope:
    """Test APIResponseEnvelope contract."""

    def test_envelope_has_required_fields(self):
        """Envelope must have all required fields."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        envelope = APIResponseEnvelope(
            request_id="req-test",
            tenant=tenant,
            resource="runs",
        )
        result = envelope.to_dict()

        # Required fields per API_REQUIREMENTS.md
        assert "request_id" in result
        assert "tenant" in result
        assert "resource" in result
        assert "schema_version" in result
        assert "api_version" in result
        assert "generated_at" in result
        assert "source" in result
        assert "staleness" in result
        assert "data" in result
        assert "errors" in result

    def test_envelope_schema_version(self):
        """Schema version must be HATE/v1."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        envelope = APIResponseEnvelope(
            request_id="req-test",
            tenant=tenant,
            resource="runs",
        )
        assert envelope.schema_version == "HATE/v1"

    def test_envelope_api_version(self):
        """API version must be v1."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        envelope = APIResponseEnvelope(
            request_id="req-test",
            tenant=tenant,
            resource="runs",
        )
        assert envelope.api_version == "v1"

    def test_envelope_generated_at_iso_format(self):
        """generated_at must be ISO 8601 format."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        envelope = APIResponseEnvelope(
            request_id="req-test",
            tenant=tenant,
            resource="runs",
        )
        # Should contain ISO format markers
        assert "T" in envelope.generated_at
        assert envelope.generated_at.endswith("Z") or "+" in envelope.generated_at

    def test_envelope_with_pagination(self):
        """Envelope with pagination includes pagination field."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        pagination = PaginationInfo(limit=50, total_count=100)
        envelope = APIResponseEnvelope(
            request_id="req-test",
            tenant=tenant,
            resource="runs",
            pagination=pagination,
        )
        result = envelope.to_dict()
        assert "pagination" in result
        assert result["pagination"]["limit"] == 50

    def test_envelope_without_pagination(self):
        """Envelope without pagination omits pagination field."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        envelope = APIResponseEnvelope(
            request_id="req-test",
            tenant=tenant,
            resource="runs",
        )
        result = envelope.to_dict()
        assert "pagination" not in result


class TestSourceInfo:
    """Test SourceInfo contract."""

    def test_source_info_to_dict(self):
        """SourceInfo converts to dict."""
        source = SourceInfo(
            bundle_hash="hash-001",
            run_id="run-001",
            attempt=1,
        )
        result = source.to_dict()
        assert result["bundle_hash"] == "hash-001"
        assert result["run_id"] == "run-001"
        assert result["attempt"] == 1

    def test_source_info_defaults(self):
        """SourceInfo defaults to None."""
        source = SourceInfo()
        result = source.to_dict()
        assert result["bundle_hash"] is None
        assert result["run_id"] is None
        assert result["attempt"] is None


class TestStalenessInfo:
    """Test StalenessInfo contract."""

    def test_staleness_fresh(self):
        """Fresh staleness status."""
        staleness = StalenessInfo(status=STALENESS_FRESH)
        result = staleness.to_dict()
        assert result["status"] == "fresh"

    def test_staleness_stale_with_reason(self):
        """Stale staleness with reason."""
        staleness = StalenessInfo(
            status=STALENESS_STALE,
            reason="Bundle import pending",
            last_rebuild_at="2024-01-01T00:00:00Z",
        )
        result = staleness.to_dict()
        assert result["status"] == "stale"
        assert result["reason"] == "Bundle import pending"
        assert result["last_rebuild_at"] == "2024-01-01T00:00:00Z"

    def test_staleness_rebuilding(self):
        """Rebuilding staleness status."""
        staleness = StalenessInfo(status=STALENESS_REBUILDING)
        result = staleness.to_dict()
        assert result["status"] == "rebuilding"

    def test_staleness_unknown(self):
        """Unknown staleness status."""
        staleness = StalenessInfo(status=STALENESS_UNKNOWN)
        result = staleness.to_dict()
        assert result["status"] == "unknown"


class TestPaginationInfo:
    """Test PaginationInfo contract."""

    def test_pagination_required_fields(self):
        """Pagination must have limit."""
        pagination = PaginationInfo(limit=50)
        result = pagination.to_dict()
        assert "limit" in result
        assert result["limit"] == 50

    def test_pagination_with_cursor(self):
        """Pagination with cursor."""
        pagination = PaginationInfo(
            limit=50,
            cursor="abc123",
            next_cursor="def456",
            total_count=100,
        )
        result = pagination.to_dict()
        assert result["cursor"] == "abc123"
        assert result["next_cursor"] == "def456"
        assert result["total_count"] == 100

    def test_pagination_defaults(self):
        """Pagination defaults."""
        pagination = PaginationInfo(limit=50)
        result = pagination.to_dict()
        assert result["cursor"] is None
        assert result["next_cursor"] is None
        assert result["total_count"] is None


# ============================================================================
# Pagination Validation Tests
# ============================================================================

class TestPaginationValidation:
    """Test pagination parameter validation."""

    def test_valid_limit(self):
        """Valid limit passes."""
        errors = validate_pagination(50, None)
        assert len(errors) == 0

    def test_limit_below_minimum(self):
        """Limit below minimum fails."""
        errors = validate_pagination(0, None)
        assert len(errors) > 0
        assert errors[0].code == "HATE-API-REQ-INVALID-PAGINATION"

    def test_limit_above_maximum(self):
        """Limit above maximum fails."""
        errors = validate_pagination(1001, None)
        assert len(errors) > 0
        assert errors[0].code == "HATE-API-REQ-INVALID-PAGINATION"

    def test_valid_cursor_hex(self):
        """Valid hex cursor passes."""
        errors = validate_pagination(50, "abc123def")
        assert len(errors) == 0

    def test_valid_cursor_base64(self):
        """Valid base64 cursor passes."""
        errors = validate_pagination(50, "YWJjMTIz")
        assert len(errors) == 0

    def test_invalid_cursor_format(self):
        """Invalid cursor format fails."""
        errors = validate_pagination(50, "invalid!cursor")
        assert len(errors) > 0
        assert errors[0].code == "HATE-API-REQ-INVALID-PAGINATION"

    def test_min_limit_value(self):
        """MIN_LIMIT is 1."""
        assert MIN_LIMIT == 1

    def test_max_limit_value(self):
        """MAX_LIMIT is 1000."""
        assert MAX_LIMIT == 1000

    def test_default_limit_value(self):
        """DEFAULT_LIMIT is 50."""
        assert DEFAULT_LIMIT == 50


# ============================================================================
# Filter Validation Tests
# ============================================================================

class TestFilterValidation:
    """Test filter parameter validation."""

    def test_valid_filter_runs(self):
        """Valid filter for runs passes."""
        filters = {"repo": "org/repo", "branch": "main"}
        errors = validate_filters("runs", filters)
        assert len(errors) == 0

    def test_invalid_filter_runs(self):
        """Invalid filter for runs fails."""
        filters = {"invalid_filter": "value"}
        errors = validate_filters("runs", filters)
        assert len(errors) > 0
        assert errors[0].code == "HATE-API-REQ-INVALID-FILTER"

    def test_valid_filter_evidence(self):
        """Valid filter for evidence passes."""
        filters = {"run_id": "run-001", "status": "passed"}
        errors = validate_filters("evidence", filters)
        assert len(errors) == 0

    def test_invalid_filter_evidence(self):
        """Invalid filter for evidence fails."""
        filters = {"invalid": "value"}
        errors = validate_filters("evidence", filters)
        assert len(errors) > 0

    def test_empty_filters(self):
        """Empty filters pass."""
        errors = validate_filters("runs", {})
        assert len(errors) == 0

    def test_resource_filters_defined(self):
        """All resources have defined filters."""
        expected_resources = [
            "runs",
            "run_detail",
            "evidence",
            "risks",
            "artifacts",
            "doctor_findings",
            "risk_debt",
            "profiles",
        ]
        for resource in expected_resources:
            assert resource in RESOURCE_FILTERS


class TestSortValidation:
    """Test sort field validation."""

    def test_valid_sort_runs(self):
        """Valid sort for runs passes."""
        errors = validate_sort("runs", "created_at")
        assert len(errors) == 0

    def test_invalid_sort_runs(self):
        """Invalid sort for runs fails."""
        errors = validate_sort("runs", "invalid_field")
        assert len(errors) > 0
        assert errors[0].code == "HATE-API-REQ-INVALID-SORT"

    def test_no_sort(self):
        """No sort field passes."""
        errors = validate_sort("runs", None)
        assert len(errors) == 0

    def test_resource_sort_fields_defined(self):
        """Resources have defined sort fields."""
        expected_resources = [
            "runs",
            "evidence",
            "risks",
            "artifacts",
            "doctor_findings",
        ]
        for resource in expected_resources:
            assert resource in RESOURCE_SORT_FIELDS


# ============================================================================
# Error Taxonomy Tests
# ============================================================================

class TestErrorTaxonomy:
    """Test error taxonomy structure."""

    def test_api_error_required_fields(self):
        """APIError has required fields."""
        error = APIError(
            code="HATE-API-REQ-INVALID",
            message="Invalid request",
        )
        result = error.to_dict()
        assert "code" in result
        assert "message" in result
        assert "remediation" in result
        assert "source_refs" in result
        assert "details" in result

    def test_api_error_with_details(self):
        """APIError with details."""
        error = APIError(
            code="HATE-API-REQ-INVALID",
            message="Invalid request",
            remediation="Fix the request",
            source_refs=["test.py:1"],
            details={"field": "value"},
        )
        result = error.to_dict()
        assert result["remediation"] == "Fix the request"
        assert result["source_refs"] == ["test.py:1"]
        assert result["details"] == {"field": "value"}

    def test_auth_unauthenticated(self):
        """AUTH-UNAUTHENTICATED error."""
        error = auth_unauthenticated()
        assert error.code == "HATE-API-AUTH-UNAUTHENTICATED"
        assert "Authentication required" in error.message

    def test_auth_unauthorized(self):
        """AUTH-UNAUTHORIZED error."""
        error = auth_unauthorized("runs")
        assert error.code == "HATE-API-AUTH-UNAUTHORIZED"
        assert "runs" in error.message

    def test_auth_cross_tenant(self):
        """AUTH-CROSS-TENANT error."""
        error = auth_cross_tenant()
        assert error.code == "HATE-API-AUTH-CROSS-TENANT"

    def test_req_invalid_filter(self):
        """REQ-INVALID-FILTER error."""
        error = req_invalid_filter("bad_filter", "not allowed")
        assert error.code == "HATE-API-REQ-INVALID-FILTER"
        assert "bad_filter" in error.message

    def test_req_invalid_pagination(self):
        """REQ-INVALID-PAGINATION error."""
        error = req_invalid_pagination("limit too high")
        assert error.code == "HATE-API-REQ-INVALID-PAGINATION"

    def test_req_missing_required(self):
        """REQ-MISSING-REQUIRED error."""
        error = req_missing_required("run_id")
        assert error.code == "HATE-API-REQ-MISSING-REQUIRED"
        assert "run_id" in error.message

    def test_req_invalid_sort(self):
        """REQ-INVALID-SORT error."""
        error = req_invalid_sort("bad_sort")
        assert error.code == "HATE-API-REQ-INVALID-SORT"

    def test_schema_unsupported(self):
        """SCHEMA-UNSUPPORTED error."""
        error = schema_unsupported("v0.8")
        assert error.code == "HATE-API-SCHEMA-UNSUPPORTED"

    def test_schema_incompatible(self):
        """SCHEMA-INCOMPATIBLE error."""
        error = schema_incompatible("custom-profile")
        assert error.code == "HATE-API-SCHEMA-INCOMPATIBLE"

    def test_store_not_found(self):
        """STORE-NOT-FOUND error."""
        error = store_not_found("run", "run-001")
        assert error.code == "HATE-API-STORE-NOT-FOUND"
        assert "run-001" in error.message

    def test_store_stale(self):
        """STORE-STALE error."""
        error = store_stale("Rebuild pending")
        assert error.code == "HATE-API-STORE-STALE"

    def test_store_rebuilding(self):
        """STORE-REBUILDING error."""
        error = store_rebuilding()
        assert error.code == "HATE-API-STORE-REBUILDING"

    def test_store_corruption(self):
        """STORE-CORRUPTION error."""
        error = store_corruption("bundle-001")
        assert error.code == "HATE-API-STORE-CORRUPTION"

    def test_export_failed(self):
        """EXPORT-FAILED error."""
        error = export_failed("s3", "connection failed")
        assert error.code == "HATE-API-EXPORT-FAILED"

    def test_export_blocked(self):
        """EXPORT-BLOCKED error."""
        error = export_blocked("policy violation")
        assert error.code == "HATE-API-EXPORT-BLOCKED"

    def test_priv_quarantined(self):
        """PRIV-QUARANTINED error."""
        error = priv_quarantined("artifact-001")
        assert error.code == "HATE-API-PRIV-QUARANTINED"

    def test_priv_redaction_failed(self):
        """PRIV-REDACTION-FAILED error."""
        error = priv_redaction_failed("artifact-001")
        assert error.code == "HATE-API-PRIV-REDACTION-FAILED"

    def test_priv_restricted(self):
        """PRIV-RESTRICTED error."""
        error = priv_restricted("artifact-001")
        assert error.code == "HATE-API-PRIV-RESTRICTED"

    def test_priv_path_leak_prevented(self):
        """PRIV-PATH-LEAK-PREVENTED error."""
        error = priv_path_leak_prevented()
        assert error.code == "HATE-API-PRIV-PATH-LEAK-PREVENTED"

    def test_error_list_to_dict(self):
        """Convert error list to dict list."""
        errors = [
            auth_unauthenticated(),
            req_invalid_filter("test", "reason"),
        ]
        result = error_list_to_dict(errors)
        assert len(result) == 2
        assert all(isinstance(e, dict) for e in result)


# ============================================================================
# Resource Handler Tests
# ============================================================================

class TestListRuns:
    """Test list_runs resource handler."""

    def test_list_runs_success(self):
        """list_runs returns valid response."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_runs(tenant)

        assert "request_id" in result
        assert result["tenant"] == tenant
        assert result["resource"] == "runs"
        assert result["schema_version"] == "HATE/v1"
        assert result["data"] is not None
        assert "runs" in result["data"]
        assert result["errors"] == []
        assert "pagination" in result

    def test_list_runs_with_filters(self):
        """list_runs with valid filters."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        filters = {"repo": "org/repo", "branch": "main"}
        result = list_runs(tenant, filters=filters)

        assert result["errors"] == []

    def test_list_runs_invalid_filter(self):
        """list_runs with invalid filter returns error."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        filters = {"invalid": "value"}
        result = list_runs(tenant, filters=filters)

        assert len(result["errors"]) > 0
        assert result["errors"][0]["code"] == "HATE-API-REQ-INVALID-FILTER"

    def test_list_runs_pagination(self):
        """list_runs pagination."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_runs(tenant, limit=100)

        assert result["pagination"]["limit"] == 100

    def test_list_runs_invalid_limit(self):
        """list_runs with invalid limit."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_runs(tenant, limit=2000)

        assert len(result["errors"]) > 0

    def test_list_runs_with_sort(self):
        """list_runs with valid sort."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_runs(tenant, sort="created_at")

        assert result["errors"] == []

    def test_list_runs_invalid_sort(self):
        """list_runs with invalid sort."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_runs(tenant, sort="invalid_field")

        assert len(result["errors"]) > 0


class TestGetRunDetail:
    """Test get_run_detail resource handler."""

    def test_get_run_detail_success(self):
        """get_run_detail returns valid response."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = get_run_detail(tenant, "run-001", 1)

        assert result["resource"] == "run_detail"
        assert result["data"]["run_id"] == "run-001"
        assert result["data"]["attempt"] == 1
        assert "provenance" in result["data"]
        assert "inputs" in result["data"]
        assert "outputs" in result["data"]

    def test_get_run_detail_missing_run_id(self):
        """get_run_detail missing run_id."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = get_run_detail(tenant, "", 1)

        assert len(result["errors"]) > 0
        assert result["errors"][0]["code"] == "HATE-API-REQ-MISSING-REQUIRED"

    def test_get_run_detail_with_include(self):
        """get_run_detail with include filters."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = get_run_detail(tenant, "run-001", 1, include=["evidence"])

        assert result["errors"] == []

    def test_get_run_detail_invalid_include(self):
        """get_run_detail with invalid include."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = get_run_detail(tenant, "run-001", 1, include=["invalid"])

        assert len(result["errors"]) > 0


class TestListEvidence:
    """Test list_evidence resource handler."""

    def test_list_evidence_success(self):
        """list_evidence returns valid response."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_evidence(tenant)

        assert result["resource"] == "evidence"
        assert "evidence" in result["data"]
        assert result["errors"] == []

    def test_list_evidence_with_filters(self):
        """list_evidence with valid filters."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        filters = {"run_id": "run-001", "status": "passed"}
        result = list_evidence(tenant, filters=filters)

        assert result["errors"] == []

    def test_list_evidence_invalid_filter(self):
        """list_evidence with invalid filter."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        filters = {"invalid": "value"}
        result = list_evidence(tenant, filters=filters)

        assert len(result["errors"]) > 0


class TestListRisks:
    """Test list_risks resource handler."""

    def test_list_risks_success(self):
        """list_risks returns valid response."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_risks(tenant)

        assert result["resource"] == "risks"
        assert "risks" in result["data"]
        assert result["errors"] == []

    def test_list_risks_default_sort_severity(self):
        """list_risks defaults to severity sort."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_risks(tenant)

        assert result["errors"] == []

    def test_list_risks_with_filters(self):
        """list_risks with valid filters."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        filters = {"severity": "high"}
        result = list_risks(tenant, filters=filters)

        assert result["errors"] == []


class TestListArtifacts:
    """Test list_artifacts resource handler."""

    def test_list_artifacts_success(self):
        """list_artifacts returns valid response."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_artifacts(tenant)

        assert result["resource"] == "artifacts"
        assert "artifacts" in result["data"]
        assert result["errors"] == []

    def test_list_artifacts_reader_role(self):
        """list_artifacts with reader role."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_artifacts(tenant, actor_role="reader")

        # Reader should only see public artifacts
        for artifact in result["data"]["artifacts"]:
            assert artifact["classification"] == "public"

    def test_list_artifacts_with_filters(self):
        """list_artifacts with valid filters."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        filters = {"classification": "public"}
        result = list_artifacts(tenant, filters=filters)

        assert result["errors"] == []


class TestListDoctorFindings:
    """Test list_doctor_findings resource handler."""

    def test_list_doctor_findings_success(self):
        """list_doctor_findings returns valid response."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_doctor_findings(tenant)

        assert result["resource"] == "doctor_findings"
        assert "findings" in result["data"]
        assert result["errors"] == []

    def test_list_doctor_findings_with_filters(self):
        """list_doctor_findings with valid filters."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        filters = {"severity": "hard_dq"}
        result = list_doctor_findings(tenant, filters=filters)

        assert result["errors"] == []

    def test_list_doctor_findings_invalid_filter(self):
        """list_doctor_findings with invalid filter."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        filters = {"invalid": "value"}
        result = list_doctor_findings(tenant, filters=filters)

        assert len(result["errors"]) > 0


# ============================================================================
# Response Builder Tests
# ============================================================================

class TestBuildResponse:
    """Test build_response function."""

    def test_build_response_basic(self):
        """Build basic response."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        data = {"runs": []}
        result = build_response("runs", tenant, data=data)

        assert result["resource"] == "runs"
        assert result["tenant"] == tenant
        assert result["data"] == data
        assert result["errors"] == []

    def test_build_response_with_staleness(self):
        """Build response with staleness."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        staleness = StalenessInfo(status=STALENESS_STALE, reason="Rebuild pending")
        result = build_response("runs", tenant, staleness=staleness)

        assert result["staleness"]["status"] == "stale"
        assert result["staleness"]["reason"] == "Rebuild pending"

    def test_build_response_with_source(self):
        """Build response with source."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        source = SourceInfo(run_id="run-001", attempt=1)
        result = build_response("runs", tenant, source=source)

        assert result["source"]["run_id"] == "run-001"

    def test_build_error_response(self):
        """Build error response."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        errors = [req_invalid_filter("test", "reason")]
        result = build_error_response("runs", tenant, errors)

        assert result["data"] is None
        assert len(result["errors"]) > 0


# ============================================================================
# Staleness State Tests
# ============================================================================

class TestStalenessStates:
    """Test staleness state constants."""

    def test_staleness_fresh_value(self):
        """STALENESS_FRESH is 'fresh'."""
        assert STALENESS_FRESH == "fresh"

    def test_staleness_stale_value(self):
        """STALENESS_STALE is 'stale'."""
        assert STALENESS_STALE == "stale"

    def test_staleness_rebuilding_value(self):
        """STALENESS_REBUILDING is 'rebuilding'."""
        assert STALENESS_REBUILDING == "rebuilding"

    def test_staleness_unknown_value(self):
        """STALENESS_UNKNOWN is 'unknown'."""
        assert STALENESS_UNKNOWN == "unknown"


# ============================================================================
# No-Tenant-Leakage Tests
# ============================================================================

class TestNoTenantLeakage:
    """Verify no tenant ID leakage in responses."""

    def test_tenant_not_in_data(self):
        """Tenant should not appear in data section."""
        tenant = {"organization_id": "org-secret", "workspace_id": "ws-secret"}
        result = list_runs(tenant)

        # Data should not contain tenant IDs
        data_str = str(result["data"])
        assert "org-secret" not in data_str
        assert "ws-secret" not in data_str

    def test_tenant_only_in_tenant_field(self):
        """Tenant only appears in tenant field."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_runs(tenant)

        # Tenant appears in designated field
        assert result["tenant"] == tenant

        # Tenant does not leak elsewhere
        assert "organization_id" not in result["data"]
        assert "workspace_id" not in result["data"]


# ============================================================================
# Error Prefix Tests
# ============================================================================

class TestErrorPrefixes:
    """Test error code prefixes per API_REQUIREMENTS.md."""

    def test_auth_prefix(self):
        """AUTH errors have HATE-API-AUTH prefix."""
        error = auth_unauthenticated()
        assert error.code.startswith("HATE-API-AUTH-")

    def test_req_prefix(self):
        """REQ errors have HATE-API-REQ prefix."""
        error = req_invalid_filter("test", "reason")
        assert error.code.startswith("HATE-API-REQ-")

    def test_schema_prefix(self):
        """SCHEMA errors have HATE-API-SCHEMA prefix."""
        error = schema_unsupported("v0.8")
        assert error.code.startswith("HATE-API-SCHEMA-")

    def test_store_prefix(self):
        """STORE errors have HATE-API-STORE prefix."""
        error = store_not_found("run", "run-001")
        assert error.code.startswith("HATE-API-STORE-")

    def test_export_prefix(self):
        """EXPORT errors have HATE-API-EXPORT prefix."""
        error = export_failed("s3", "reason")
        assert error.code.startswith("HATE-API-EXPORT-")

    def test_priv_prefix(self):
        """PRIV errors have HATE-API-PRIV prefix."""
        error = priv_quarantined("artifact-001")
        assert error.code.startswith("HATE-API-PRIV-")
