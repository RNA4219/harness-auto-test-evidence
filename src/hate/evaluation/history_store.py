"""Local real-repo run history store and query helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STORE_VERSION = "real-repo-history-store/v1"
RUN_HISTORY_FILENAME = "run_history.jsonl"
HISTORY_INDEX_FILENAME = "history-index.json"


class RealRepoHistoryStoreError(Exception):
    """Raised when the real-repo history store cannot be read or written."""


def ingest_real_repo_history(history_path: Path, store_dir: Path) -> dict[str, Any]:
    """Append real-repo run history entries to a local JSONL store."""
    if not history_path.exists():
        raise RealRepoHistoryStoreError(f"history file not found: {history_path}")

    entries = _read_history_entries(history_path)
    store_dir.mkdir(parents=True, exist_ok=True)

    store_path = store_dir / RUN_HISTORY_FILENAME
    source_hash = _hash_file(history_path)
    started_sequence = _last_sequence(store_path)
    ingested_at = _utc_now()
    stored_entries = [
        _stored_entry(entry, sequence=started_sequence + index + 1, ingested_at=ingested_at, source_hash=source_hash)
        for index, entry in enumerate(entries)
    ]

    with store_path.open("a", encoding="utf-8", newline="\n") as handle:
        for entry in stored_entries:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

    index = _write_history_index(store_dir, _read_store_entries(store_path))
    return {
        "schema_version": "HATE/v1",
        "record_type": "real-repo-history-ingest-report",
        "report_id": "real-repo-history-ingest",
        "store_version": STORE_VERSION,
        "history_path": str(history_path),
        "store_path": str(store_path),
        "source_history_hash": source_hash,
        "ingested_count": len(stored_entries),
        "stored_count": index["summary"]["stored_count"],
        "repo_count": index["summary"]["repo_count"],
        "sourceRefs": [str(history_path), str(store_path), str(store_dir / HISTORY_INDEX_FILENAME)],
    }


def query_real_repo_history(
    store_dir: Path,
    *,
    repo_id: str | None = None,
    suite_id: str | None = None,
    source_version: str | None = None,
    status: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Query stored real-repo run history entries."""
    store_path = store_dir / RUN_HISTORY_FILENAME
    if not store_path.exists():
        raise RealRepoHistoryStoreError(f"history store not found: {store_path}")
    if limit < 1:
        raise RealRepoHistoryStoreError("limit must be greater than zero")

    entries = _read_store_entries(store_path)
    filters = {
        "repo_id": repo_id,
        "suite_id": suite_id,
        "source_version": source_version,
        "status": status,
        "since": since,
        "until": until,
    }
    filtered = [_public_entry(entry) for entry in entries if _matches(entry, filters)]
    filtered.sort(key=lambda item: (str(item.get("started_at", "")), str(item.get("run_id", "")), str(item.get("suite_id", ""))))
    limited = filtered[:limit]

    return {
        "schema_version": "HATE/v1",
        "record_type": "real-repo-history-query-report",
        "report_id": "real-repo-history-query",
        "store_version": STORE_VERSION,
        "store_path": str(store_path),
        "filters": {key: value for key, value in filters.items() if value is not None},
        "matched_count": len(filtered),
        "returned_count": len(limited),
        "entries": limited,
        "sourceRefs": [str(store_path)],
    }


def _read_history_entries(history_path: Path) -> list[dict[str, Any]]:
    entries = []
    for line_number, line in enumerate(history_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RealRepoHistoryStoreError(f"invalid history JSONL at line {line_number}: {exc}") from exc
        if not isinstance(entry, dict) or entry.get("record_type") != "real-repo-run-history-entry":
            raise RealRepoHistoryStoreError(f"invalid history entry at line {line_number}")
        entries.append(entry)
    return entries


def _read_store_entries(store_path: Path) -> list[dict[str, Any]]:
    if not store_path.exists():
        return []
    entries = []
    for line_number, line in enumerate(store_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RealRepoHistoryStoreError(f"invalid store JSONL at line {line_number}: {exc}") from exc
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _last_sequence(store_path: Path) -> int:
    sequences = [int(entry.get("store_sequence") or 0) for entry in _read_store_entries(store_path)]
    return max(sequences, default=0)


def _stored_entry(entry: dict[str, Any], *, sequence: int, ingested_at: str, source_hash: str) -> dict[str, Any]:
    stored = dict(entry)
    stored["store_version"] = STORE_VERSION
    stored["store_sequence"] = sequence
    stored["ingested_at"] = ingested_at
    stored["source_history_hash"] = source_hash
    return stored


def _public_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": entry.get("run_id", ""),
        "repo_id": entry.get("repo_id", ""),
        "suite_id": entry.get("suite_id", "default"),
        "ownership_scope": entry.get("ownership_scope", ""),
        "source_version": entry.get("source_version", ""),
        "roster_hash": entry.get("roster_hash", ""),
        "policy_hash": entry.get("policy_hash", ""),
        "started_at": entry.get("started_at", ""),
        "finished_at": entry.get("finished_at", ""),
        "status": entry.get("status", ""),
        "record_count": entry.get("record_count"),
        "duration_ms": entry.get("duration_ms"),
        "failure_kind": entry.get("failure_kind", ""),
        "timeout_recorded": bool(entry.get("timeout_recorded", False)),
        "store_sequence": entry.get("store_sequence"),
        "sourceRefs": list(entry.get("sourceRefs") or []),
    }


def _matches(entry: dict[str, Any], filters: dict[str, str | None]) -> bool:
    for key in ("repo_id", "suite_id", "source_version", "status"):
        value = filters.get(key)
        if value is not None and str(entry.get(key, "")) != value:
            return False
    started_at = str(entry.get("started_at") or "")
    if filters.get("since") is not None and started_at < str(filters["since"]):
        return False
    if filters.get("until") is not None and started_at > str(filters["until"]):
        return False
    return True


def _write_history_index(store_dir: Path, entries: list[dict[str, Any]]) -> dict[str, Any]:
    repos = sorted({str(entry.get("repo_id") or "") for entry in entries if entry.get("repo_id")})
    statuses = sorted({str(entry.get("status") or "") for entry in entries if entry.get("status")})
    index = {
        "schema_version": "HATE/v1",
        "record_type": "real-repo-history-index",
        "store_version": STORE_VERSION,
        "updated_at": _utc_now(),
        "summary": {
            "stored_count": len(entries),
            "repo_count": len(repos),
            "status_count": len(statuses),
            "latest_started_at": max((str(entry.get("started_at") or "") for entry in entries), default=""),
        },
        "indexes": ["idx_run_repo_time", "idx_run_source_version", "idx_suite_status"],
        "repos": repos,
        "statuses": statuses,
    }
    (store_dir / HISTORY_INDEX_FILENAME).write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return index


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
