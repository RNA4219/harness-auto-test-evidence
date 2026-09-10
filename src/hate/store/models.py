"""ローカルストアの公開データ型。保存・検証処理から独立させる。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .manifest_validation import manifest_errors

ARTIFACT_KIND_ALIASES = {"test": "test_result", "coverage": "coverage_slice", "finding": "static_finding"}
STORED_ARTIFACT_KINDS = frozenset({
    "test_result", "coverage_slice", "static_finding", "contract_evidence", "mutation_evidence", *ARTIFACT_KIND_ALIASES,
})


@dataclass
class LocalStoreError(Exception):
    message: str
    operation: str
    path: Path | None = None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        return f"LocalStoreError({self.operation}): {self.message}"


@dataclass
class StoreManifest:
    run_id: str
    bundle_id: str
    source_version: str
    schema_versions: dict[str, str]
    artifact_ids: list[str]
    content_hashes: dict[str, str]
    index_hashes: dict[str, str]  # 取り込み時点の索引スナップショット。
    legal_hold: dict[str, Any]
    retention_policy_id: str
    created_at: str
    producer_version: str
    completed: bool
    sourceRefs: list[str]
    import_status: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoreManifest:
        errors = manifest_errors(data)
        if errors:
            fields = ", ".join(sorted({item["field"] or "manifest" for item in errors}))
            raise LocalStoreError(f"Invalid manifest fields: {fields}", "validate_manifest", diagnostics=errors)
        return cls(
            run_id=data["run_id"],
            bundle_id=data["bundle_id"],
            source_version=data["source_version"],
            schema_versions=data["schema_versions"],
            artifact_ids=data["artifact_ids"],
            content_hashes=data["content_hashes"],
            index_hashes=data["index_hashes"],
            legal_hold=data["legal_hold"],
            retention_policy_id=data["retention_policy_id"],
            created_at=data["created_at"],
            producer_version=data["producer_version"],
            completed=data["completed"],
            sourceRefs=data["sourceRefs"],
            import_status=data.get("import_status"),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": "HATE/v1",
            "record_type": "store_manifest",
            "run_id": self.run_id,
            "bundle_id": self.bundle_id,
            "source_version": self.source_version,
            "schema_versions": self.schema_versions,
            "artifact_ids": self.artifact_ids,
            "content_hashes": self.content_hashes,
            "index_hashes": self.index_hashes,
            "legal_hold": self.legal_hold,
            "retention_policy_id": self.retention_policy_id,
            "created_at": self.created_at,
            "producer_version": self.producer_version,
            "completed": self.completed,
            "sourceRefs": self.sourceRefs,
        }
        if self.import_status is not None:
            data["import_status"] = self.import_status
        return data


@dataclass
class ImportBundleResult:
    success: bool
    run_id: str
    bundle_id: str
    manifest_path: Path | None
    index_hashes: dict[str, str] | None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "HATE/v1",
            "record_type": "import_bundle_result",
            "success": self.success,
            "run_id": self.run_id,
            "bundle_id": self.bundle_id,
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "index_hashes": self.index_hashes,
            "diagnostics": self.diagnostics,
        }
