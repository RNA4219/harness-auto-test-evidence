"""HATE API Read Model.

Implements read-only resource handlers with filtering, pagination, staleness tracking.
Read model is derived from canonical bundles and local store indexes.
It must not change HATE precheck decisions or canonical bundle content.
"""

from __future__ import annotations

import uuid
from typing import Any

from .errors import (
    APIError,
    req_invalid_filter,
    req_missing_required,
    store_not_found,
    store_stale,
    store_rebuilding,
    auth_unauthorized,
)
from .read_model_contract import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    MIN_LIMIT,
    RESOURCE_FILTERS,
    RESOURCE_SORT_FIELDS,
    STALENESS_FRESH,
    STALENESS_REBUILDING,
    STALENESS_STALE,
    STALENESS_UNKNOWN,
    APIResponseEnvelope,
    PaginationInfo,
    SourceInfo,
    StalenessInfo,
    validate_filters,
    validate_pagination,
    validate_sort,
)
from .read_model_projection import build_read_model, default_read_model


def build_response(
    resource: str,
    tenant: dict[str, str],
    data: Any = None,
    errors: list[APIError] = None,
    source: SourceInfo | None = None,
    staleness: StalenessInfo | None = None,
    pagination: PaginationInfo | None = None,
) -> dict[str, Any]:
    """Build standard API response envelope."""
    envelope = APIResponseEnvelope(
        request_id=f"req-{uuid.uuid4().hex[:12]}",
        tenant=tenant,
        resource=resource,
        data=data,
        errors=errors or [],
        source=source or SourceInfo(),
        staleness=staleness or StalenessInfo(status=STALENESS_FRESH),
        pagination=pagination,
    )
    return envelope.to_dict()


def build_error_response(
    resource: str,
    tenant: dict[str, str],
    errors: list[APIError],
    source: SourceInfo | None = None,
) -> dict[str, Any]:
    """Build error-only response envelope."""
    return build_response(
        resource=resource,
        tenant=tenant,
        data=None,
        errors=errors,
        source=source,
    )


def _source_from_model(read_model: dict[str, Any]) -> SourceInfo:
    source = read_model.get("source", {})
    return SourceInfo(
        bundle_hash=source.get("bundle_hash"),
        run_id=source.get("run_id"),
        attempt=source.get("attempt"),
    )


def _staleness_from_model(read_model: dict[str, Any]) -> StalenessInfo:
    staleness = read_model.get("staleness", {})
    return StalenessInfo(
        status=staleness.get("status", STALENESS_FRESH),
        reason=staleness.get("reason"),
        last_rebuild_at=staleness.get("last_rebuild_at"),
    )


def _apply_filters(items: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    result = items
    for key, expected in filters.items():
        result = [item for item in result if item.get(key) == expected]
    return result


def _apply_sort(items: list[dict[str, Any]], sort: str | None) -> list[dict[str, Any]]:
    if not sort:
        return items
    return sorted(items, key=lambda item: str(item.get(sort, "")))


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return int(cursor, 16)
    except ValueError:
        return 0


def _paginate(items: list[dict[str, Any]], limit: int, cursor: str | None) -> tuple[list[dict[str, Any]], PaginationInfo]:
    offset = _decode_cursor(cursor)
    page = items[offset:offset + limit]
    next_offset = offset + limit
    next_cursor = format(next_offset, "x") if next_offset < len(items) else None
    return page, PaginationInfo(
        limit=limit,
        cursor=cursor,
        next_cursor=next_cursor,
        total_count=len(items),
    )


def list_runs(
    tenant: dict[str, str],
    filters: dict[str, Any] = None,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
    sort: str | None = None,
    read_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List runs with filtering, sorting, pagination.

    Required filters (optional): repo, branch, commit, profile, decision, date range, actor
    Required fields: run_id, attempt, commit, profile, decision, dq_count, gap_count
    """
    filters = filters or {}
    errors: list[APIError] = []

    # Validate filters
    filter_errors = validate_filters("runs", filters)
    errors.extend(filter_errors)

    # Validate pagination
    pagination_errors = validate_pagination(limit, cursor)
    errors.extend(pagination_errors)

    # Validate sort
    sort_errors = validate_sort("runs", sort)
    errors.extend(sort_errors)

    if errors:
        return build_error_response("runs", tenant, errors)

    model = read_model or default_read_model()
    runs = _apply_sort(_apply_filters(model.get("runs", []), filters), sort)
    page, pagination = _paginate(runs, limit, cursor)
    data = {"runs": page}

    return build_response(
        resource="runs",
        tenant=tenant,
        data=data,
        pagination=pagination,
        source=_source_from_model(model),
        staleness=_staleness_from_model(model),
    )


def get_run_detail(
    tenant: dict[str, str],
    run_id: str,
    attempt: int,
    include: list[str] | None = None,
    read_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get run detail with provenance, profile, decision.

    Required filters (optional): include=evidence,doctor,release
    Required fields: provenance, inputs, outputs, decision reasons, sourceRefs
    """
    errors: list[APIError] = []

    if not run_id:
        errors.append(req_missing_required("run_id"))

    if errors:
        return build_error_response("run_detail", tenant, errors)

    # Validate include filters
    if include:
        allowed_include = ["evidence", "doctor", "release", "artifacts"]
        for inc in include:
            if inc not in allowed_include:
                errors.append(req_invalid_filter(f"include.{inc}", "not allowed"))

    if errors:
        return build_error_response("run_detail", tenant, errors)

    model = read_model or default_read_model()
    data = model.get("run_details", {}).get(run_id)
    if data is None:
        return build_error_response("run_detail", tenant, [store_not_found("run", run_id)], _source_from_model(model))

    return build_response(
        resource="run_detail",
        tenant=tenant,
        data=data,
        source=SourceInfo(run_id=run_id, attempt=attempt),
        staleness=_staleness_from_model(model),
    )


def list_evidence(
    tenant: dict[str, str],
    filters: dict[str, Any] = None,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
    sort: str | None = None,
    read_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List evidence by run/risk/test/kind/trust.

    Required filters: run_id, risk_id, test_id, kind, status, trust_score, source_tool
    Required fields: evidence_id, kind, status, sourceRefs, artifact refs
    """
    filters = filters or {}
    errors: list[APIError] = []

    filter_errors = validate_filters("evidence", filters)
    errors.extend(filter_errors)

    pagination_errors = validate_pagination(limit, cursor)
    errors.extend(pagination_errors)

    sort_errors = validate_sort("evidence", sort)
    errors.extend(sort_errors)

    if errors:
        return build_error_response("evidence", tenant, errors)

    model = read_model or default_read_model()
    evidence = _apply_sort(_apply_filters(model.get("evidence", []), filters), sort)
    page, pagination = _paginate(evidence, limit, cursor)
    data = {"evidence": page}

    return build_response(
        resource="evidence",
        tenant=tenant,
        data=data,
        pagination=pagination,
        source=_source_from_model(model),
        staleness=_staleness_from_model(model),
    )


def list_risks(
    tenant: dict[str, str],
    filters: dict[str, Any] = None,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
    sort: str | None = None,
    read_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List risks by severity, owner, layer, oracle status, debt.

    Required filters: severity, owner, layer, oracle_status, manual_required, debt_status
    Required fields: risk_id, changed_entity, required_evidence, current_evidence, gap
    """
    filters = filters or {}
    errors: list[APIError] = []

    filter_errors = validate_filters("risks", filters)
    errors.extend(filter_errors)

    pagination_errors = validate_pagination(limit, cursor)
    errors.extend(pagination_errors)

    # Default sort by severity (high/critical first)
    if not sort:
        sort = "severity"

    sort_errors = validate_sort("risks", sort)
    errors.extend(sort_errors)

    if errors:
        return build_error_response("risks", tenant, errors)

    model = read_model or default_read_model()
    risks = _apply_sort(_apply_filters(model.get("risks", []), filters), sort)
    page, pagination = _paginate(risks, limit, cursor)
    data = {"risks": page}

    return build_response(
        resource="risks",
        tenant=tenant,
        data=data,
        pagination=pagination,
        source=_source_from_model(model),
        staleness=_staleness_from_model(model),
    )


def list_artifacts(
    tenant: dict[str, str],
    filters: dict[str, Any] = None,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
    sort: str | None = None,
    actor_role: str = "reader",
    read_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List artifact metadata only (content requires authz + safe status).

    Required filters: run_id, artifact_id, classification, quarantine_status, redaction_status
    Required fields: artifact_id, classification, quarantine_status, redaction_status, safe_metadata

    Artifact states: safe, quarantined, redaction_pending, redaction_failed, restricted, missing, external_blocked
    """
    filters = filters or {}
    errors: list[APIError] = []

    filter_errors = validate_filters("artifacts", filters)
    errors.extend(filter_errors)

    pagination_errors = validate_pagination(limit, cursor)
    errors.extend(pagination_errors)

    sort_errors = validate_sort("artifacts", sort)
    errors.extend(sort_errors)

    if errors:
        return build_error_response("artifacts", tenant, errors)

    model = read_model or default_read_model()
    artifacts = _apply_sort(_apply_filters(model.get("artifacts", []), filters), sort)

    if actor_role == "reader":
        artifacts = [a for a in artifacts if a["classification"] == "public"]
    page, pagination = _paginate(artifacts, limit, cursor)
    data = {"artifacts": page}

    return build_response(
        resource="artifacts",
        tenant=tenant,
        data=data,
        pagination=pagination,
        source=_source_from_model(model),
        staleness=_staleness_from_model(model),
    )


def list_doctor_findings(
    tenant: dict[str, str],
    filters: dict[str, Any] = None,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
    sort: str | None = None,
    read_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List doctor findings with severity, category, remediation.

    Required filters: severity, category, artifact_id, bundle_id
    Required fields: finding_id, severity, category, message, remediation
    """
    filters = filters or {}
    errors: list[APIError] = []

    filter_errors = validate_filters("doctor_findings", filters)
    errors.extend(filter_errors)

    pagination_errors = validate_pagination(limit, cursor)
    errors.extend(pagination_errors)

    sort_errors = validate_sort("doctor_findings", sort)
    errors.extend(sort_errors)

    if errors:
        return build_error_response("doctor_findings", tenant, errors)

    model = read_model or default_read_model()
    findings = _apply_sort(_apply_filters(model.get("findings", []), filters), sort)
    page, pagination = _paginate(findings, limit, cursor)
    data = {"findings": page}

    return build_response(
        resource="doctor_findings",
        tenant=tenant,
        data=data,
        pagination=pagination,
        source=_source_from_model(model),
        staleness=_staleness_from_model(model),
    )
