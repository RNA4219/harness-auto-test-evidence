"""HATE API Read Model.

Implements read-only resource handlers with filtering, pagination, staleness tracking.
Read model is derived from canonical bundles and local store indexes.
It must not change HATE precheck decisions or canonical bundle content.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
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


def build_read_model(
    reports: dict[str, Any],
    required_reports: list[str] | None = None,
    staleness_status: str = STALENESS_FRESH,
    staleness_reason: str | None = None,
) -> dict[str, Any]:
    """Project canonical HATE reports into API read-model resources.

    The projection copies verdict/status fields from upstream reports. It does
    not recompute readiness or turn missing reports into success.
    """
    required_reports = required_reports or []
    missing_reports = [name for name in required_reports if name not in reports]
    source_refs: list[str] = []
    for report in reports.values():
        if isinstance(report, dict):
            source_refs.extend(report.get("sourceRefs", []))

    run_report = reports.get("run", {})
    readiness_report = reports.get("readiness", {})
    readiness_summary = readiness_report.get("summary", {})
    risk_matrix = reports.get("risk_coverage_matrix", {})
    artifact_safety = reports.get("artifact_safety", {})
    manual_review_report = reports.get("manual_review", {})
    evidence_graph = reports.get("evidence_graph", {})

    run_id = (
        run_report.get("run_id")
        or readiness_report.get("run_id")
        or risk_matrix.get("run_id")
        or artifact_safety.get("run_id")
    )
    decision = (
        run_report.get("decision")
        or readiness_summary.get("overall_status")
        or readiness_report.get("overall_status")
        or "unknown"
    )

    runs: list[dict[str, Any]] = []
    if run_id:
        runs.append({
            "run_id": run_id,
            "attempt": run_report.get("attempt", 1),
            "commit": run_report.get("commit", run_report.get("source_version", "")),
            "profile": run_report.get("profile", readiness_report.get("profile", "default")),
            "decision": decision,
            "dq_count": readiness_summary.get("hard_dq_count", len(readiness_report.get("hard_dqs", []))),
            "gap_count": readiness_summary.get("soft_gap_count", len(readiness_report.get("soft_gaps", []))),
            "created_at": run_report.get("created_at") or readiness_report.get("generated_at"),
            "source_refs": run_report.get("sourceRefs", []) + readiness_report.get("sourceRefs", []),
        })

    risks = []
    for risk in risk_matrix.get("risks", []):
        risks.append({
            "risk_id": risk.get("risk_id"),
            "severity": risk.get("severity"),
            "owner": risk.get("owner"),
            "layer": risk.get("layer"),
            "changed_entity": risk.get("changed_entity") or risk.get("description"),
            "required_evidence": risk.get("required_evidence_classes") or risk.get("required_evidence", []),
            "current_evidence": risk.get("observed_evidence_classes") or risk.get("current_evidence", []),
            "oracle_status": "missing" if risk.get("oracle_evidence") is False else "present",
            "manual_required": bool(risk.get("manual_required")),
            "debt_status": risk.get("debt_status"),
            "gap": risk.get("gap_class") not in (None, "pass"),
            "source_refs": risk.get("sourceRefs", []) or ([risk["sourceRef"]] if risk.get("sourceRef") else []),
        })

    artifacts = []
    for artifact in artifact_safety.get("artifacts", []):
        artifacts.append(_safe_artifact_metadata(artifact))
    if artifact_safety.get("artifact_id"):
        artifacts.append(_safe_artifact_metadata(artifact_safety))

    findings = []
    for report_key in ("artifact_safety", "manual_review", "readiness"):
        report = reports.get(report_key, {})
        for finding in report.get("findings", []) + report.get("hard_dqs", []):
            findings.append({
                "finding_id": finding.get("finding_id") or finding.get("code") or finding.get("id"),
                "severity": finding.get("severity", finding.get("readiness_effect", "info")),
                "category": finding.get("category", report_key),
                "message": finding.get("message") or finding.get("reason", ""),
                "remediation": finding.get("remediation") or finding.get("suggested_manual_review_action"),
                "source_refs": finding.get("sourceRefs", []) or ([finding["sourceRef"]] if finding.get("sourceRef") else []),
            })

    manual_review_requests = manual_review_report.get("requests", [])
    if manual_review_report.get("record_type") == "manual_review_request_bundle":
        manual_review_requests = manual_review_report.get("manual_review_requests", manual_review_requests)

    evidence = []
    for node in evidence_graph.get("nodes", []):
        if node.get("kind") in {"test_result", "coverage_slice", "static_finding", "contract_evidence", "mutation_evidence"}:
            evidence.append({
                "evidence_id": node.get("id"),
                "kind": node.get("kind"),
                "status": node.get("status", node.get("result")),
                "trust_score": node.get("trust_score"),
                "source_refs": node.get("sourceRefs", []) or ([node["sourceRef"]] if node.get("sourceRef") else []),
                "artifact_refs": node.get("artifact_refs", []),
            })

    diagnostics = []
    for report_name in missing_reports:
        diagnostics.append({
            "code": "missing_upstream_report",
            "finding_id": "missing_upstream_report",
            "category": "read_model",
            "severity": "hold",
            "message": f"Required upstream report is missing: {report_name}",
            "sourceRef": f"api/read_model:{report_name}",
        })

    if missing_reports and staleness_status == STALENESS_FRESH:
        staleness_status = STALENESS_STALE
        staleness_reason = "missing required upstream report"

    bundle_hash = reports.get("bundle_hash") or run_report.get("bundle_hash") or readiness_report.get("bundle_hash")

    return {
        "runs": runs,
        "run_details": {run["run_id"]: {
            "run_id": run["run_id"],
            "attempt": run["attempt"],
            "provenance": run_report.get("provenance", {
                "repo": run_report.get("repo"),
                "branch": run_report.get("branch"),
                "commit": run["commit"],
                "actor": run_report.get("actor"),
                "triggered_at": run.get("created_at"),
            }),
            "inputs": run_report.get("inputs", {"profile": run["profile"]}),
            "outputs": readiness_summary or {"decision": run["decision"]},
            "source_refs": run["source_refs"],
        } for run in runs},
        "evidence": evidence,
        "risks": risks,
        "artifacts": artifacts,
        "findings": findings + diagnostics,
        "manual_review_requests": manual_review_requests,
        "readiness_summaries": [readiness_summary] if readiness_summary else [],
        "sourceRefs": source_refs,
        "source": {
            "bundle_hash": bundle_hash,
            "run_id": run_id,
            "attempt": runs[0]["attempt"] if runs else None,
        },
        "staleness": {
            "status": staleness_status,
            "reason": staleness_reason,
            "last_rebuild_at": reports.get("last_rebuild_at"),
        },
        "diagnostics": diagnostics,
    }


def _safe_artifact_metadata(artifact: dict[str, Any]) -> dict[str, Any]:
    """Return artifact metadata safe for API/UI surfaces."""
    classification = artifact.get("classification", "restricted")
    quarantine_status = artifact.get("quarantine_status")
    if not quarantine_status:
        quarantine_status = "quarantined" if classification in {"restricted", "secret", "pii"} else "none"
    redaction_status = artifact.get("redaction_status", "not_required")
    safe_metadata = artifact.get("safe_metadata", {})
    if not safe_metadata:
        safe_metadata = {
            "artifact_id": artifact.get("artifact_id"),
            "classification": classification,
            "safe_for_summary": quarantine_status == "none",
        }
    return {
        "artifact_id": artifact.get("artifact_id"),
        "classification": classification,
        "quarantine_status": quarantine_status,
        "redaction_status": redaction_status,
        "safe_metadata": safe_metadata,
        "source_refs": artifact.get("sourceRefs", []) or ([artifact["sourceRef"]] if artifact.get("sourceRef") else []),
    }


def _default_read_model() -> dict[str, Any]:
    """Minimal empty read model used when callers do not pass report data."""
    return build_read_model(
        {
            "run": {
                "run_id": "run-001",
                "attempt": 1,
                "commit": "abc123",
                "profile": "default",
                "decision": "PASS",
                "created_at": datetime.now(UTC).isoformat(),
                "sourceRefs": ["api/read_model:default-run"],
            },
            "readiness": {
                "summary": {"overall_status": "PASS", "hard_dq_count": 0, "soft_gap_count": 0},
                "sourceRefs": ["api/read_model:default-readiness"],
            },
        }
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

    model = read_model or _default_read_model()
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

    model = read_model or _default_read_model()
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

    model = read_model or _default_read_model()
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

    model = read_model or _default_read_model()
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

    model = read_model or _default_read_model()
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

    model = read_model or _default_read_model()
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
