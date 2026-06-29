"""Resource inventory contract tests for HATE API Read Model."""

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
# Comprehensive Resource Inventory Tests
# ============================================================================

class TestResourceInventory:
    """Verify all required resources are implemented."""

    def test_runs_resource_exists(self):
        """runs resource handler exists."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_runs(tenant)
        assert result["resource"] == "runs"

    def test_evidence_resource_exists(self):
        """evidence resource handler exists."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_evidence(tenant)
        assert result["resource"] == "evidence"

    def test_risks_resource_exists(self):
        """risks resource handler exists."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_risks(tenant)
        assert result["resource"] == "risks"

    def test_artifacts_resource_exists(self):
        """artifacts resource handler exists."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_artifacts(tenant)
        assert result["resource"] == "artifacts"

    def test_doctor_findings_resource_exists(self):
        """doctor_findings resource handler exists."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = list_doctor_findings(tenant)
        assert result["resource"] == "doctor_findings"

    def test_run_detail_resource_exists(self):
        """run_detail resource handler exists."""
        tenant = {"organization_id": "org-001", "workspace_id": "ws-001"}
        result = get_run_detail(tenant, "run-001", 1)
        assert result["resource"] == "run_detail"