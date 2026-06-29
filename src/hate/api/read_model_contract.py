"""Read-model response envelope and request validation contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .errors import APIError, error_list_to_dict, req_invalid_filter, req_invalid_pagination, req_invalid_sort


STALENESS_FRESH = "fresh"
STALENESS_STALE = "stale"
STALENESS_REBUILDING = "rebuilding"
STALENESS_UNKNOWN = "unknown"

MIN_LIMIT = 1
MAX_LIMIT = 1000
DEFAULT_LIMIT = 50


@dataclass
class PaginationInfo:
    """Pagination metadata."""

    limit: int
    cursor: str | None = None
    next_cursor: str | None = None
    total_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "limit": self.limit,
            "cursor": self.cursor,
            "next_cursor": self.next_cursor,
            "total_count": self.total_count,
        }


@dataclass
class StalenessInfo:
    """Staleness metadata."""

    status: str
    reason: str | None = None
    last_rebuild_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "last_rebuild_at": self.last_rebuild_at,
        }


@dataclass
class SourceInfo:
    """Source bundle reference."""

    bundle_hash: str | None = None
    run_id: str | None = None
    attempt: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_hash": self.bundle_hash,
            "run_id": self.run_id,
            "attempt": self.attempt,
        }


@dataclass
class APIResponseEnvelope:
    """Standard API response envelope."""

    request_id: str
    tenant: dict[str, str]
    resource: str
    schema_version: str = "HATE/v1"
    api_version: str = "v1"
    generated_at: str = ""
    source: SourceInfo = field(default_factory=SourceInfo)
    staleness: StalenessInfo = field(default_factory=lambda: StalenessInfo(status=STALENESS_FRESH))
    pagination: PaginationInfo | None = None
    data: Any = None
    errors: list[APIError] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.generated_at:
            self.generated_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        result = {
            "request_id": self.request_id,
            "tenant": self.tenant,
            "resource": self.resource,
            "schema_version": self.schema_version,
            "api_version": self.api_version,
            "generated_at": self.generated_at,
            "source": self.source.to_dict(),
            "staleness": self.staleness.to_dict(),
            "data": self.data,
            "errors": error_list_to_dict(self.errors),
        }
        if self.pagination:
            result["pagination"] = self.pagination.to_dict()
        return result


RESOURCE_FILTERS = {
    "runs": ["repo", "branch", "commit", "profile", "decision", "date_from", "date_to", "actor"],
    "run_detail": ["include"],
    "evidence": ["run_id", "risk_id", "test_id", "kind", "status", "trust_score", "source_tool"],
    "risks": ["severity", "owner", "layer", "oracle_status", "manual_required", "debt_status"],
    "artifacts": ["run_id", "artifact_id", "classification", "quarantine_status", "redaction_status"],
    "doctor_findings": ["severity", "category", "artifact_id", "bundle_id"],
    "risk_debt": ["status", "owner", "risk_id"],
    "profiles": ["name", "version", "status"],
}

RESOURCE_SORT_FIELDS = {
    "runs": ["created_at", "run_id", "decision", "commit"],
    "evidence": ["created_at", "trust_score", "status"],
    "risks": ["severity", "created_at", "owner"],
    "artifacts": ["created_at", "classification"],
    "doctor_findings": ["severity", "created_at"],
}


def validate_filters(resource: str, filters: dict[str, Any]) -> list[APIError]:
    """Validate filter parameters for a resource."""

    errors: list[APIError] = []
    allowed_filters = RESOURCE_FILTERS.get(resource, [])

    for filter_name in filters:
        if filter_name not in allowed_filters:
            errors.append(req_invalid_filter(filter_name, f"not allowed for {resource}"))

    return errors


def validate_pagination(limit: int, cursor: str | None) -> list[APIError]:
    """Validate pagination parameters."""

    errors: list[APIError] = []

    if limit < MIN_LIMIT:
        errors.append(req_invalid_pagination(f"limit {limit} below minimum {MIN_LIMIT}"))
    if limit > MAX_LIMIT:
        errors.append(req_invalid_pagination(f"limit {limit} above maximum {MAX_LIMIT}"))

    if cursor:
        if not (
            all(c in "0123456789abcdef" for c in cursor.lower())
            or all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for c in cursor)
        ):
            errors.append(req_invalid_pagination("invalid cursor format"))

    return errors


def validate_sort(resource: str, sort_field: str | None) -> list[APIError]:
    """Validate sort field for a resource."""

    errors: list[APIError] = []

    if sort_field:
        allowed_sorts = RESOURCE_SORT_FIELDS.get(resource, [])
        if sort_field not in allowed_sorts:
            errors.append(req_invalid_sort(sort_field))

    return errors
