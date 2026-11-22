"""Multi-dimensional Store Indexes for HATE Local Store.

Implements JSONL-based indexes for fast lookup across multiple dimensions:
- run_id: Lookup by run identifier
- requirement_ref: Lookup by requirement reference
- risk_ref: Lookup by risk reference
- sourceRef: Lookup by source reference
- artifact_id: Lookup by artifact identifier

No-Go conditions:
- Index can reference missing records (hard DQ)
- Index rebuild changes canonical bundle hash
- Missing index is ignored for high-volume query
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .atomic_write import atomic_write_bytes
from .json_io import strict_json_loads


def _display_text(value: object) -> str:
    return str(value).encode("utf-8", errors="backslashreplace").decode("utf-8")


@dataclass
class HardDQFinding(Exception):
    """Hard DQ finding when index references missing record.

    This is a data quality finding that blocks store operations.
    Index references must always resolve to valid records.
    """
    message: str
    index_type: str
    referenced_key: str
    missing_path: str
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        return _display_text(f"HardDQ({self.index_type}): {self.message} - missing {self.missing_path}")

    def to_record(self) -> dict[str, Any]:
        """Convert finding to HATE record format."""
        return {
            "schema_version": "HATE/v1",
            "record_type": "hard_dq_finding",
            "finding_id": f"dq-{hashlib.sha256(_display_text(self.message).encode()).hexdigest()[:16]}",
            "severity": "hard_block",
            "index_type": self.index_type,
            "referenced_key": _display_text(self.referenced_key),
            "missing_path": _display_text(self.missing_path),
            "diagnostics": self.diagnostics,
            "created_at": datetime.now(UTC).isoformat(),
        }


@dataclass
class IndexLookupError(Exception):
    """Error during index lookup operation."""
    message: str
    index_type: str
    key: str
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class IndexEntry:
    """Single entry in a store index."""
    key: str
    value: str  # Path to record (relative to store root)
    hash: str  # SHA256 hash of referenced record
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_jsonl(self) -> str:
        """Serialize entry to JSONL format."""
        self.validate()
        return json.dumps({
            "key": self.key,
            "value": self.value,
            "hash": self.hash,
            "metadata": self.metadata,
        }, ensure_ascii=False, sort_keys=True, allow_nan=False)

    def validate(self) -> None:
        for name in ("key", "value", "hash"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"index entry requires a non-blank string: {name}")
            value.encode("utf-8")
        if re.fullmatch(r"sha256:[a-fA-F0-9]{64}", self.hash) is None:
            raise ValueError("index hash must be a SHA256 digest")
        if not isinstance(self.metadata, dict):
            raise ValueError("index metadata must be an object")
        json.dumps(self.metadata, ensure_ascii=False, allow_nan=False).encode("utf-8")

    @classmethod
    def from_jsonl(cls, line: str) -> IndexEntry:
        """Deserialize entry from JSONL format."""
        data = strict_json_loads(line)
        if not isinstance(data, dict):
            raise ValueError("index entry must be an object")
        for name in ("key", "value", "hash"):
            if not isinstance(data.get(name), str) or not data[name]:
                raise ValueError(f"index entry requires a non-empty string: {name}")
        if not isinstance(data.get("metadata", {}), dict):
            raise ValueError("index metadata must be an object")
        entry = cls(
            key=data["key"],
            value=data["value"],
            hash=data["hash"],
            metadata=data.get("metadata", {}),
        )
        entry.validate()
        return entry


@dataclass
class StoreIndex:
    """Multi-dimensional index for store lookup.

    Each index is a JSONL file with entries for one lookup dimension.
    Index files are unique-key snapshots. Completed bundle files remain append-only;
    run and bundle keys may point to newer copies after a successful import.
    """
    index_type: str  # "runs", "bundles", "evidence", "risks", "artifacts"
    index_path: Path
    store_root: Path
    entries: dict[str, IndexEntry] = field(default_factory=dict)

    def load(self) -> None:
        """Load existing index entries from JSONL file."""
        loaded: dict[str, IndexEntry] = {}
        first_lines: dict[str, int] = {}
        line_number = 0
        try:
            with self.index_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line_number += 1
                    line = line.strip()
                    if line:
                        entry = IndexEntry.from_jsonl(line)
                        self._entry_path(entry.key, entry)
                        if entry.key in loaded:
                            raise IndexLookupError(
                                "Duplicate key in index snapshot", self.index_type, entry.key,
                                [{"issue": "duplicate_index_key", "first_line": first_lines[entry.key], "line_number": line_number}],
                            )
                        loaded[entry.key] = entry
                        first_lines[entry.key] = line_number
        except FileNotFoundError:
            loaded = {}
        except (OSError, ValueError, TypeError, KeyError, HardDQFinding) as e:
            raise IndexLookupError(
                message=f"Index file corrupted: {e}",
                index_type=self.index_type,
                key="",
                diagnostics=[{"error": str(e), "line_number": line_number}],
            ) from e
        self.entries = loaded

    def save(self) -> str:
        """Save index entries to JSONL file atomically.

        Returns:
            SHA256 hash of the saved index file.
        """
        # Sort entries by key for deterministic output
        sorted_entries = sorted(self.entries.items(), key=lambda x: x[0])

        # Write JSONL content
        lines = []
        for key, entry in sorted_entries:
            if key != entry.key:
                raise IndexLookupError("Index mapping key differs from entry key", self.index_type, key)
            try:
                self._entry_path(key, entry)
                lines.append(entry.to_jsonl())
            except (ValueError, TypeError, HardDQFinding) as exc:
                raise IndexLookupError("Invalid index entry", self.index_type, key, [{"error": str(exc)}]) from exc
        content = "\n".join(lines) + "\n" if lines else ""

        # Atomic write
        atomic_write_bytes(self.index_path, content.encode("utf-8"), self.store_root)

        # Compute hash
        sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return f"sha256:{sha256}"

    def add_entry(
        self,
        key: str,
        value: str,
        record_hash: str,
        metadata: dict[str, Any] | None = None,
    ) -> IndexEntry:
        """Add entry to index.

        Args:
            key: Lookup key (run_id, requirement_ref, etc.)
            value: Path to record (relative to store root)
            record_hash: SHA256 hash of the referenced record
            metadata: Additional metadata for the entry

        Returns:
            The added entry

        Raises:
            HardDQFinding: If key is invalid or value contains path traversal
        """
        # Validate key format
        if not key or not isinstance(key, str):
            raise HardDQFinding(
                message="Index key must be non-empty string",
                index_type=self.index_type,
                referenced_key=key,
                missing_path=value,
                diagnostics=[{"issue": "invalid_key", "key": str(key)}],
            )

        entry = IndexEntry(key, value, record_hash, {} if metadata is None else metadata)
        try:
            entry.validate()
        except (ValueError, TypeError) as exc:
            raise HardDQFinding("Invalid index entry", self.index_type, key, value, [{"error": str(exc)}]) from exc

        # Validate path traversal
        resolved_value = (self.store_root / value).resolve()
        try:
            resolved_value.relative_to(self.store_root.resolve())
        except ValueError as exc:
            raise HardDQFinding(
                message="Path traversal in index value rejected",
                index_type=self.index_type,
                referenced_key=key,
                missing_path=value,
                diagnostics=[
                    {
                        "issue": "path_traversal",
                        "resolved_path": str(resolved_value),
                        "store_root": str(self.store_root.resolve()),
                    }
                ],
            ) from exc

        self._entry_path(key, entry)
        self.entries[key] = entry
        return entry

    def lookup(self, key: str, verify_record: bool = True) -> IndexEntry:
        """Lookup entry by key.

        Args:
            key: Lookup key
            verify_record: If True, verify referenced record exists and hash matches

        Returns:
            The found entry

        Raises:
            IndexLookupError: If key not found
            HardDQFinding: If record missing or hash mismatch (when verify_record=True)
        """
        if not isinstance(key, str) or not key.strip() or key not in self.entries:
            raise IndexLookupError(
                message=f"Key not found in index: {key}",
                index_type=self.index_type,
                key=key,
            )

        entry = self.entries[key]
        record_path = self._entry_path(key, entry)

        if verify_record:
            try:
                if not stat.S_ISREG(record_path.stat().st_mode):
                    raise HardDQFinding(
                        "Index record is not a file", self.index_type, key, str(record_path),
                        [{"issue": "record_not_file", "expected_path": str(record_path)}],
                    )
                actual_hash = self._compute_record_hash(record_path)
            except OSError as exc:
                issue = "missing_record" if isinstance(exc, FileNotFoundError) else "record_unreadable"
                raise HardDQFinding(
                    "Index record is missing or unreadable", self.index_type, key, str(record_path),
                    [{"issue": issue, "expected_path": str(record_path), "error": str(exc)}],
                ) from exc
            if actual_hash.lower() != entry.hash.lower():
                raise HardDQFinding(
                    "Index hash mismatch with record", self.index_type, key, str(record_path),
                    [{"issue": "hash_mismatch", "expected_hash": entry.hash, "actual_hash": actual_hash}],
                )

        return entry

    def _entry_path(self, key: str, entry: IndexEntry) -> Path:
        try:
            entry.validate()
            if entry.key != key:
                raise ValueError("index mapping key does not match entry key")
            root = self.store_root.resolve()
            path = (root / entry.value).resolve()
            if path == root or not path.is_relative_to(root):
                raise ValueError("index record path must stay within store")
        except (ValueError, TypeError, OSError, RuntimeError) as exc:
            raise HardDQFinding(
                "Invalid index reference", self.index_type, key, str(entry.value),
                [{"issue": "invalid_index_reference", "error": str(exc)}],
            ) from exc
        return path

    def _compute_record_hash(self, record_path: Path) -> str:
        """拡張子によらず、参照先ファイルの実バイトからSHA256を計算する。"""
        # Read raw file content and compute hash directly
        # This matches atomic_write_json format (indent=2)
        sha256 = hashlib.sha256()
        with record_path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return f"sha256:{sha256.hexdigest()}"

    def iter_entries(self) -> Iterator[IndexEntry]:
        """Iterate over all entries."""
        return iter(self.entries.values())

    def count(self) -> int:
        """Return number of entries."""
        return len(self.entries)


class MultiIndexManager:
    """Manager for multiple store indexes."""

    def __init__(self, store_root: Path) -> None:
        self.store_root = store_root
        self.index_dir = store_root / "indexes"

        # Create index instances
        self.runs_index = StoreIndex(
            index_type="runs",
            index_path=self.index_dir / "runs.jsonl",
            store_root=store_root,
        )
        self.bundles_index = StoreIndex(
            index_type="bundles",
            index_path=self.index_dir / "bundles.jsonl",
            store_root=store_root,
        )
        self.evidence_index = StoreIndex(
            index_type="evidence",
            index_path=self.index_dir / "evidence.jsonl",
            store_root=store_root,
        )
        self.risks_index = StoreIndex(
            index_type="risks",
            index_path=self.index_dir / "risks.jsonl",
            store_root=store_root,
        )
        self.artifacts_index = StoreIndex(
            index_type="artifacts",
            index_path=self.index_dir / "artifacts.jsonl",
            store_root=store_root,
        )

        # Requirement and sourceRef indexes
        self.requirements_index = StoreIndex(
            index_type="requirements",
            index_path=self.index_dir / "requirements.jsonl",
            store_root=store_root,
        )
        self.source_refs_index = StoreIndex(
            index_type="source_refs",
            index_path=self.index_dir / "source-refs.jsonl",
            store_root=store_root,
        )

    def load_all(self) -> None:
        """Load all indexes."""
        for index in self._all_indexes():
            index.load()

    def save_all(self) -> dict[str, str]:
        """Save all indexes.

        Returns:
            Dict mapping index type to hash.
        """
        hashes = {}
        for index in self._all_indexes():
            hashes[index.index_type] = index.save()
        return hashes

    def _all_indexes(self) -> list[StoreIndex]:
        """List all managed indexes."""
        return [
            self.runs_index,
            self.bundles_index,
            self.evidence_index,
            self.risks_index,
            self.artifacts_index,
            self.requirements_index,
            self.source_refs_index,
        ]

    def lookup_by_run_id(self, run_id: str, verify: bool = True) -> IndexEntry:
        """Lookup by run_id."""
        return self.runs_index.lookup(run_id, verify_record=verify)

    def lookup_by_requirement_ref(self, ref: str, verify: bool = True) -> IndexEntry:
        """Lookup by requirement_ref."""
        return self.requirements_index.lookup(ref, verify_record=verify)

    def lookup_by_risk_ref(self, ref: str, verify: bool = True) -> IndexEntry:
        """Lookup by risk_ref."""
        return self.risks_index.lookup(ref, verify_record=verify)

    def lookup_by_source_ref(self, ref: str, verify: bool = True) -> IndexEntry:
        """Lookup by sourceRef."""
        return self.source_refs_index.lookup(ref, verify_record=verify)

    def lookup_by_artifact_id(self, artifact_id: str, verify: bool = True) -> IndexEntry:
        """Lookup by artifact_id."""
        return self.artifacts_index.lookup(artifact_id, verify_record=verify)


def build_indexes_for_bundle(
    store_root: Path,
    bundle_dir: Path,
    manifest: dict[str, Any],
) -> dict[str, str]:
    """保存済みbundleの索引を検証・補完する。公開import経路を維持する。"""
    from .indexing import build_indexes_for_bundle as build

    return build(store_root, bundle_dir, manifest)
