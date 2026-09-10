"""P1aの申告provenanceを検証する。hashの申告を実体検証と同一視しない。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from jsonschema import FormatChecker

from .p1a_run_scope import bundle_commit_declarations

_COMMIT = re.compile(r"[A-Fa-f0-9]{7,64}")
_SHA256 = re.compile(r"(?:sha256:)?[A-Fa-f0-9]{64}")
_FORMATS = FormatChecker()


@dataclass(frozen=True)
class ProvenanceAnalysis:
    has_run_id: bool
    has_created_at: bool
    has_commit_sha: bool
    artifact_count: int
    valid_artifact_hash_count: int
    issues: list[dict[str, Any]]

    @property
    def score(self) -> int:
        if not self.has_run_id:
            return 0
        if not self.issues and self.artifact_count > 0:
            return 3
        return 1

    def observed(self) -> dict[str, Any]:
        return {
            "has_run_id": self.has_run_id,
            "has_created_at": self.has_created_at,
            "has_commit_sha": self.has_commit_sha,
            "has_artifact_hash": self.valid_artifact_hash_count > 0,
            "artifact_count": self.artifact_count,
            "valid_artifact_hash_count": self.valid_artifact_hash_count,
            "provenance_valid": not self.issues,
            "artifact_content_verified": False,
            "tamper_resistance_verified": False,
        }


def _valid_timestamp(value: Any) -> bool:
    return isinstance(value, str) and value == value.strip() and _FORMATS.conforms(value, "date-time")


def analyze_provenance(bundle: dict[str, Any], report: dict[str, Any]) -> ProvenanceAnalysis:
    metadata = bundle.get("metadata", {})
    run_id = metadata.get("runId")
    has_run_id = isinstance(run_id, str) and bool(run_id.strip())
    has_created_at = _valid_timestamp(metadata.get("createdAt"))
    commit = report.get("commit_sha")
    has_commit_sha = isinstance(commit, str) and _COMMIT.fullmatch(commit) is not None
    issues: list[dict[str, Any]] = []

    def add(issue: str, message: str, path: list[str | int], source: str) -> None:
        issues.append({"issue": issue, "message": message, "validation_path": path, "source_refs": [source]})

    if not has_run_id:
        add("missing_run_id", "bundle metadata requires a nonblank runId", ["metadata", "runId"], "qeg-bundle.json")
    if not has_created_at:
        add("invalid_created_at", "createdAt requires an RFC 3339 date-time with timezone",
            ["metadata", "createdAt"], "qeg-bundle.json")
    if "created_at" in report and not _valid_timestamp(report["created_at"]):
        add("invalid_created_at", "created_at requires an RFC 3339 date-time with timezone",
            ["created_at"], "qeg-export-report.json")
    if not has_commit_sha:
        add("invalid_commit_sha", "commit_sha requires a 7–64 character hexadecimal commit ID",
            ["commit_sha"], "qeg-export-report.json")
    for declared_commit, path in bundle_commit_declarations(bundle):
        if not isinstance(declared_commit, str) or _COMMIT.fullmatch(declared_commit) is None:
            add("invalid_commit_sha", "declared commit requires a 7–64 character hexadecimal commit ID",
                path, "qeg-bundle.json")

    artifact_count = valid_hash_count = 0
    for index, node in enumerate(bundle.get("nodes", [])):
        if node.get("kind") != "evidence_artifact":
            continue
        artifact_count += 1
        digest = node.get("data", {}).get("sha256")
        if isinstance(digest, str) and _SHA256.fullmatch(digest) is not None:
            valid_hash_count += 1
        else:
            add("invalid_artifact_sha256", "artifact sha256 requires 64 hexadecimal characters with optional sha256: prefix",
                ["nodes", index, "data", "sha256"], "qeg-bundle.json")
    return ProvenanceAnalysis(has_run_id, has_created_at, has_commit_sha, artifact_count, valid_hash_count, issues)
