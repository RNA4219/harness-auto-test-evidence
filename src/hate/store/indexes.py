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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


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
        return f"HardDQ({self.index_type}): {self.message} - missing {self.missing_path}"

    def to_record(self) -> dict[str, Any]:
        """Convert finding to HATE record format."""
        return {
            "schema_version": "HATE/v1",
            "record_type": "hard_dq_finding",
            "finding_id": f"dq-{hashlib.sha256(self.message.encode()).hexdigest()[:16]}",
            "severity": "hard_block",
            "index_type": self.index_type,
            "referenced_key": self.referenced_key,
            "missing_path": self.missing_path,
            "diagnostics": self.diagnostics,
            "created_at": datetime.now(timezone.utc).isoformat(),
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
        return json.dumps({
            "key": self.key,
            "value": self.value,
            "hash": self.hash,
            "metadata": self.metadata,
        }, ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_jsonl(cls, line: str) -> "IndexEntry":
        """Deserialize entry from JSONL format."""
        data = json.loads(line)
        return cls(
            key=data["key"],
            value=data["value"],
            hash=data["hash"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class StoreIndex:
    """Multi-dimensional index for store lookup.

    Each index is a JSONL file with entries for one lookup dimension.
    Indexes are append-only for completed bundles.
    """
    index_type: str  # "runs", "bundles", "evidence", "risks", "artifacts"
    index_path: Path
    store_root: Path
    entries: dict[str, IndexEntry] = field(default_factory=dict)

    def load(self) -> None:
        """Load existing index entries from JSONL file."""
        if not self.index_path.exists():
            self.entries = {}
            return

        try:
            with self.index_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entry = IndexEntry.from_jsonl(line)
                        self.entries[entry.key] = entry
        except json.JSONDecodeError as e:
            raise IndexLookupError(
                message=f"Index file corrupted: {e}",
                index_type=self.index_type,
                key="",
                diagnostics=[{"error": str(e), "line": line if line else "EOF"}],
            )

    def save(self) -> str:
        """Save index entries to JSONL file atomically.

        Returns:
            SHA256 hash of the saved index file.
        """
        # Sort entries by key for deterministic output
        sorted_entries = sorted(self.entries.items(), key=lambda x: x[0])

        # Write JSONL content
        lines = [entry.to_jsonl() for _, entry in sorted_entries]
        content = "\n".join(lines) + "\n" if lines else ""

        # Atomic write
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.index_path.with_suffix(".tmp")
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(self.index_path)

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

        # Validate path traversal
        resolved_value = (self.store_root / value).resolve()
        try:
            resolved_value.relative_to(self.store_root.resolve())
        except ValueError:
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
            )

        entry = IndexEntry(
            key=key,
            value=value,
            hash=record_hash,
            metadata=metadata or {},
        )
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
        if key not in self.entries:
            raise IndexLookupError(
                message=f"Key not found in index: {key}",
                index_type=self.index_type,
                key=key,
            )

        entry = self.entries[key]

        if verify_record:
            record_path = self.store_root / entry.value

            # Check record exists
            if not record_path.exists():
                raise HardDQFinding(
                    message="Index references missing record",
                    index_type=self.index_type,
                    referenced_key=key,
                    missing_path=str(record_path),
                    diagnostics=[
                        {
                            "issue": "missing_record",
                            "index_entry": entry.to_jsonl(),
                            "expected_path": str(record_path),
                        }
                    ],
                )

            # Verify hash
            if record_path.suffix == ".json":
                actual_hash = self._compute_record_hash(record_path)
                if actual_hash != entry.hash:
                    raise HardDQFinding(
                        message="Index hash mismatch with record",
                        index_type=self.index_type,
                        referenced_key=key,
                        missing_path=str(record_path),
                        diagnostics=[
                            {
                                "issue": "hash_mismatch",
                                "expected_hash": entry.hash,
                                "actual_hash": actual_hash,
                            }
                        ],
                    )

        return entry

    def _compute_record_hash(self, record_path: Path) -> str:
        """Compute SHA256 hash of JSON record in write format."""
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
    """Build indexes for a newly imported bundle.

    Args:
        store_root: Root of store
        bundle_dir: Directory containing bundle files
        manifest: Store manifest for the bundle

    Returns:
        Dict mapping index type to hash.

    Raises:
        HardDQFinding: If index references missing record
    """
    manager = MultiIndexManager(store_root)
    manager.load_all()

    run_id = manifest["run_id"]
    bundle_id = manifest["bundle_id"]

    # Relative path to bundle directory
    rel_bundle_dir = bundle_dir.relative_to(store_root)

    # Add run index entry
    run_path = rel_bundle_dir / "run.json"
    if (store_root / run_path).exists():
        run_hash = manager.runs_index._compute_record_hash(store_root / run_path)
        manager.runs_index.add_entry(
            key=run_id,
            value=str(run_path),
            record_hash=run_hash,
            metadata={"bundle_id": bundle_id},
        )

    # Add bundle index entry
    bundle_path = rel_bundle_dir / "qeg-bundle.json"
    if (store_root / bundle_path).exists():
        bundle_hash = manager.bundles_index._compute_record_hash(store_root / bundle_path)
        manager.bundles_index.add_entry(
            key=bundle_id,
            value=str(bundle_path),
            record_hash=bundle_hash,
            metadata={"run_id": run_id},
        )

    # Add artifact entries
    for artifact_id in manifest.get("artifact_ids", []):
        artifact_path = rel_bundle_dir / f"{artifact_id}.json"
        if (store_root / artifact_path).exists():
            artifact_hash = manifest.get("content_hashes", {}).get(
                artifact_id, manager.bundles_index._compute_record_hash(store_root / artifact_path)
            )
            manager.artifacts_index.add_entry(
                key=artifact_id,
                value=str(artifact_path),
                record_hash=artifact_hash,
                metadata={"run_id": run_id, "bundle_id": bundle_id},
            )

    # Save all indexes
    return manager.save_all()