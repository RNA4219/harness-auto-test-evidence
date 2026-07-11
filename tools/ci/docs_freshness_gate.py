from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _discover_post_poc_record_types(root: Path) -> set[str]:
    emitted: set[str] = set()
    source_root = root / "src" / "hate" / "post_poc"
    for path in source_root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r'"record_type"\s*:\s*"([^"]+)"', text):
            record_type = match.group(1)
            if re.search(r"(report|manifest|packet|runbook|artifact|step)$", record_type):
                emitted.add(record_type)
    return emitted


POST_POC_SCHEMA_RECORDS = _discover_post_poc_record_types(ROOT)


def evaluate_docs_freshness_gate(root: Path) -> dict[str, object]:
    findings: list[dict[str, str]] = []
    registry = _load_gap_registry(root, findings)
    _check_readme(root, findings)
    _check_post_poc_acceptance(root, registry, findings)
    _check_generated_post_poc_status(root, registry, findings)
    _check_schema_registry(root, findings)
    _check_birdseye_index(root, findings)
    return {
        "schema_version": "HATE/ci-docs-freshness/v1",
        "record_type": "ci-docs-freshness-gate",
        "overall_status": "hold" if findings else "pass",
        "findings": findings,
        "summary": {"finding_count": len(findings)},
    }


def main(argv: list[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    root = Path(args[0]) if args else Path.cwd()
    report = evaluate_docs_freshness_gate(root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["overall_status"] != "pass" else 0


def _load_gap_registry(root: Path, findings: list[dict[str, str]]) -> dict[str, Any] | None:
    path = root / "docs" / "process" / "post-poc-gap-registry.json"
    if not path.exists():
        findings.append(_finding("docs_post_poc_registry_missing", "Canonical Post-PoC gap registry is missing.", str(path.relative_to(root))))
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        findings.append(_finding("docs_post_poc_registry_invalid", f"Cannot read Post-PoC registry: {exc}", str(path.relative_to(root))))
        return None
    gaps = data.get("gaps")
    if not isinstance(gaps, list) or not gaps:
        findings.append(_finding("docs_post_poc_registry_invalid", "Post-PoC registry requires a non-empty gaps array.", str(path.relative_to(root))))
        return None
    ids = [str(item.get("gap_id") or "") for item in gaps if isinstance(item, dict)]
    if not all(ids) or len(ids) != len(set(ids)):
        findings.append(_finding("docs_post_poc_registry_invalid", "Post-PoC gap IDs must be present and unique.", str(path.relative_to(root))))
    if data.get("product_ready") is not False or data.get("release_authority") != "external":
        findings.append(_finding("docs_product_ready_overclaim", "Post-PoC registry must preserve product_ready=false and external release authority.", str(path.relative_to(root))))
    return data


def _check_readme(root: Path, findings: list[dict[str, str]]) -> None:
    path = root / "README.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    required = [
        "POST_POC_REQUIREMENTS_GAP_AUDIT.md",
        "POST_POC_PRODUCTIZATION_DETAIL_SPEC.md",
        "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md",
        "POST_POC_IMPLEMENTATION_GAP_CHECKLIST.md",
        "post-poc-gap-registry.json",
        "product_ready=false",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        findings.append(_finding("docs_readme_state_stale", f"README missing freshness markers: {', '.join(missing)}", "README.md"))


def _acceptance_paths(root: Path, registry: dict[str, Any] | None) -> list[Path]:
    if registry is not None:
        return [
            root / str(gap.get("acceptance_ref"))
            for gap in registry.get("gaps", [])
            if isinstance(gap, dict) and gap.get("acceptance_ref")
        ]
    return sorted((root / "docs" / "acceptance").glob("AC-*-postpoc-*.md"))


def _check_post_poc_acceptance(
    root: Path,
    registry: dict[str, Any] | None,
    findings: list[dict[str, str]],
) -> None:
    paths = _acceptance_paths(root, registry)
    if not paths:
        findings.append(_finding("docs_acceptance_record_missing", "No Post-PoC acceptance records were discovered.", "docs/acceptance"))
        return
    missing = [str(path.relative_to(root)) for path in paths if not path.exists()]
    malformed = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        required = [
            "intent_id:",
            "owner:",
            "status: accepted",
            "last_reviewed_at:",
            "next_review_due:",
            "verification_executed_at:",
            "verification_commit:",
            "## Verification",
            "## Evidence",
            "## Open Risks",
            "## Decision",
        ]
        absent = [marker for marker in required if marker not in text]
        if absent:
            malformed.append(f"{path.relative_to(root)} missing {', '.join(absent)}")
    if missing:
        findings.append(_finding("docs_acceptance_record_missing", f"Missing Post-PoC acceptance records: {', '.join(missing)}", "docs/acceptance"))
    if malformed:
        findings.append(_finding("docs_acceptance_record_malformed", f"Malformed Post-PoC acceptance records: {'; '.join(malformed)}", "docs/acceptance"))


def _check_generated_post_poc_status(
    root: Path,
    registry: dict[str, Any] | None,
    findings: list[dict[str, str]],
) -> None:
    if registry is None:
        return
    targets = {
        "POST_POC_REQUIREMENTS_GAP_AUDIT.md": "POST_POC_REQUIREMENTS",
        "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md": "POST_POC_TRACEABILITY",
        "POST_POC_IMPLEMENTATION_GAP_CHECKLIST.md": "POST_POC_IMPLEMENTATION",
    }
    for name, marker in targets.items():
        path = root / "docs" / "process" / name
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        if f"BEGIN GENERATED:{marker}" not in text or f"END GENERATED:{marker}" not in text:
            findings.append(_finding("docs_post_poc_generated_status_stale", f"{name} lacks generated status markers.", str(path.relative_to(root))))
            continue
        for gap in registry["gaps"]:
            required = [
                str(gap["gap_id"]),
                str(gap["local_slice_status"]),
                str(gap["product_status"]),
            ]
            if any(item not in text for item in required):
                findings.append(_finding("docs_post_poc_generated_status_stale", f"{name} is missing canonical state for {gap['gap_id']}.", str(path.relative_to(root))))
                break
    decision_path = root / "docs" / "process" / "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md"
    decision = decision_path.read_text(encoding="utf-8") if decision_path.exists() else ""
    if "local evidence slices are accepted" not in decision.lower() or "product gaps remain open" not in decision.lower():
        findings.append(_finding("docs_post_poc_traceability_decision_stale", "Current Decision must distinguish accepted local slices from open product gaps.", str(decision_path.relative_to(root))))


def _check_schema_registry(root: Path, findings: list[dict[str, str]]) -> None:
    registry_path = root / "schemas" / "HATE" / "v1" / "schema-registry.json"
    if not registry_path.exists():
        findings.append(_finding("docs_schema_registry_stale", "Schema registry is missing.", str(registry_path.relative_to(root))))
        return
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    records = list(registry.get("records", []))
    by_type = {str(record.get("record_type")): record for record in records if isinstance(record, dict)}
    expected = _discover_post_poc_record_types(root) or POST_POC_SCHEMA_RECORDS
    missing = sorted(expected.difference(by_type))
    if missing:
        findings.append(_finding("docs_schema_registry_stale", f"Schema registry missing Post-PoC records: {', '.join(missing)}", str(registry_path.relative_to(root))))
    missing_paths = sorted(
        f"{record.get('record_type', '<unknown>')} => {record.get('schema', '')}"
        for record in records
        if record.get("schema") and not (root / str(record["schema"])).exists()
    )
    if missing_paths:
        findings.append(_finding("docs_schema_registry_path_missing", f"Schema registry references missing schema files: {', '.join(missing_paths)}", str(registry_path.relative_to(root))))
    mismatches = _schema_record_type_mismatches(root, records, expected)
    if mismatches:
        findings.append(_finding("docs_schema_record_type_mismatch", f"Schema registry record_type does not match schema const/enum: {', '.join(mismatches)}", str(registry_path.relative_to(root))))


def _schema_record_type_mismatches(root: Path, records: list[dict[str, Any]], expected: set[str]) -> list[str]:
    mismatches = []
    for record in records:
        record_type = str(record.get("record_type") or "")
        if record_type not in expected:
            continue
        path = root / str(record.get("schema") or "")
        if not path.is_file():
            continue
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            mismatches.append(f"{record_type} => invalid-json")
            continue
        contract = schema.get("properties", {}).get("record_type", {})
        if contract.get("const") and contract["const"] != record_type:
            mismatches.append(f"{record_type} => const:{contract['const']}")
        elif contract.get("enum") and record_type not in contract["enum"]:
            mismatches.append(f"{record_type} => enum-missing")
        elif not contract.get("const") and not contract.get("enum"):
            mismatches.append(f"{record_type} => no-const-or-enum")
    return sorted(mismatches)


def _check_birdseye_index(root: Path, findings: list[dict[str, str]]) -> None:
    path = root / "docs" / "birdseye" / "index.json"
    if not path.exists():
        findings.append(_finding("docs_codemap_stale", "Birdseye index is missing.", str(path.relative_to(root))))


def _finding(code: str, message: str, source_ref: str) -> dict[str, str]:
    return {
        "code": code,
        "severity": "high",
        "message": message,
        "sourceRef": source_ref,
        "readiness_effect": "hold",
    }


if __name__ == "__main__":
    raise SystemExit(main())
