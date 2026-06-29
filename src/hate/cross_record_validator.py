from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_envelope import source_refs
from .source_ref import deterministic_record_id, normalize_path, parse_source_ref, sha256_text


@dataclass(frozen=True)
class CrossRecordViolation:
    violation_id: str
    code: str
    severity: str
    affected_record_ids: list[str]
    relation_kind: str
    expected: str
    observed: str
    sourceRef: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "violation_id": self.violation_id,
            "code": self.code,
            "severity": self.severity,
            "affected_record_ids": self.affected_record_ids,
            "relation_kind": self.relation_kind,
            "expected": self.expected,
            "observed": self.observed,
            "sourceRef": self.sourceRef,
        }


def validate_cross_record_bundle(bundle: dict[str, Any]) -> list[CrossRecordViolation]:
    artifacts = _artifact_index(bundle.get("artifacts", []))
    records = [record for record in bundle.get("records", []) if isinstance(record, dict)]
    violations: list[CrossRecordViolation] = []
    test_ids = _known_test_ids(records)

    for record in records:
        record_id = str(record.get("record_id") or "<missing>")
        refs = source_refs(record)
        parsed_refs = [parse_source_ref(ref) for ref in refs]
        for parsed in parsed_refs:
            if parsed.has_traversal:
                violations.append(_violation("path_traversal_source_ref", record_id, "source_ref_path", "workspace-relative path", parsed.path, parsed.raw))
                continue
            artifact = _find_artifact(parsed, artifacts)
            if artifact is None:
                violations.append(_violation("missing_source_artifact", record_id, "source_ref_artifact", "artifact in bundle", parsed.normalized_path, parsed.raw))
                continue
            expected_hash = str(artifact.get("sha256") or "")
            observed_hash = str(record.get("source_hash") or record.get("payload", {}).get("source_hash") or expected_hash)
            if expected_hash and observed_hash and expected_hash != observed_hash:
                violations.append(_violation("hash_mismatch", record_id, "source_hash", expected_hash, observed_hash, parsed.raw))

        if record.get("deterministic_id_required") is True:
            expected_id = deterministic_record_id(record, refs)
            if record_id != expected_id:
                violations.append(_violation("non_deterministic_record_id", record_id, "record_id", expected_id, record_id, refs[0] if refs else record_id))

        kind = str(record.get("record_kind") or record.get("record_type") or "")
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        if kind == "coverage_slice":
            for context in payload.get("contexts", []):
                if not isinstance(context, dict):
                    continue
                for test_id in context.get("contexts", []):
                    if str(test_id) not in test_ids:
                        violations.append(_violation("coverage_refers_unknown_test", record_id, "coverage_test_context", "known test id", str(test_id), refs[0] if refs else record_id))
        if kind == "static_finding":
            file_path = normalize_path(str(payload.get("file", "")))
            if file_path and file_path not in artifacts["by_path"]:
                violations.append(_violation("finding_refers_unknown_file", record_id, "finding_file", "artifact path in bundle", file_path, refs[0] if refs else record_id))

    return sorted(violations, key=lambda item: (item.code, item.sourceRef, item.violation_id))


def build_cross_record_report(bundle: dict[str, Any], *, fixture_id: str = "cross-record") -> dict[str, Any]:
    violations = validate_cross_record_bundle(bundle)
    return {
        "schema_version": "HATE/schema-validation-report/v1",
        "record_type": "schema_validation_report",
        "fixture_id": fixture_id,
        "summary": {
            "accepted": 0 if violations else len([record for record in bundle.get("records", []) if isinstance(record, dict)]),
            "rejected": len({record_id for violation in violations for record_id in violation.affected_record_ids}),
            "rejection_classes": _violation_counts(violations),
        },
        "cross_record": {
            "violation_count": len(violations),
            "violations": [violation.as_dict() for violation in violations],
        },
    }


def _artifact_index(items: Any) -> dict[str, dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_path: dict[str, dict[str, Any]] = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        artifact = dict(item)
        path = normalize_path(str(artifact.get("normalized_path") or artifact.get("path") or ""))
        artifact["normalized_path"] = path
        if "content" in artifact:
            observed = sha256_text(str(artifact["content"]))
            artifact["observed_sha256"] = observed
        artifact_id = str(artifact.get("artifact_id") or "")
        if artifact_id:
            by_id[artifact_id] = artifact
        if path and path != ".":
            by_path[path] = artifact
    return {"by_id": by_id, "by_path": by_path}


def _find_artifact(parsed, artifacts: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any] | None:
    if parsed.artifact_id and parsed.artifact_id in artifacts["by_id"]:
        return artifacts["by_id"][parsed.artifact_id]
    return artifacts["by_path"].get(parsed.normalized_path)


def _known_test_ids(records: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for record in records:
        kind = str(record.get("record_kind") or record.get("record_type") or "")
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        if kind == "test_result" and payload.get("canonical_test_id"):
            ids.add(str(payload["canonical_test_id"]))
    return ids


def _violation(code: str, record_id: str, relation_kind: str, expected: str, observed: str, source_ref: str) -> CrossRecordViolation:
    return CrossRecordViolation(
        violation_id=f"{code}:{record_id}",
        code=code,
        severity="hard",
        affected_record_ids=[record_id],
        relation_kind=relation_kind,
        expected=expected,
        observed=observed,
        sourceRef=source_ref,
    )


def _violation_counts(violations: list[CrossRecordViolation]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for violation in violations:
        counts[violation.code] = counts.get(violation.code, 0) + 1
    return dict(sorted(counts.items()))
