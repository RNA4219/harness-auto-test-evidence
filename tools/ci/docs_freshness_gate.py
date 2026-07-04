from __future__ import annotations

import json
import sys
from pathlib import Path


POST_POC_ACCEPTANCE_COUNT = 16
POST_POC_SCHEMA_RECORDS = {
    "baseline-promotion-report",
    "baseline-review-packet",
    "baseline-review-packet-artifact",
    "capacity-report",
    "capacity-degradation-mode-report",
    "capacity-regression-packet",
    "capacity-regression-packet-artifact",
    "compliance-report",
    "connector-runtime-report",
    "connector-execution-manifest",
    "connector-execution-manifest-artifact",
    "connector-execution-step",
    "dashboard-interaction-report",
    "dashboard-static-html-artifact",
    "docs-freshness-ci-report",
    "history-analytics-report",
    "history-materialization-manifest",
    "history-materialization-manifest-artifact",
    "hosted-api-report",
    "hosted-api-openapi-artifact",
    "hosted-api-route-manifest",
    "hosted-scheduler-runtime-report",
    "hosted-scheduler-dispatch-manifest",
    "hosted-scheduler-dispatch-manifest-artifact",
    "human-review-workflow-report",
    "human-review-queue-packet",
    "human-review-queue-packet-artifact",
    "incident-response-packet",
    "incident-response-packet-artifact",
    "notification-delivery-report",
    "notification-routing-manifest",
    "notification-routing-manifest-artifact",
    "observability-report",
    "plugin-distribution-report",
    "plugin-install-manifest",
    "plugin-install-manifest-artifact",
    "plugin-package-manifest",
    "real-repo-roster-maintenance-report",
    "real-repo-roster-execution-manifest",
    "real-repo-roster-execution-manifest-artifact",
    "release-handoff-report",
    "slo-burn-rate-report",
    "store-dr-report",
    "post-poc-artifact-receipt",
    "store-dr-runbook",
    "store-dr-runbook-artifact",
    "store-dr-runbook-step",
}


def evaluate_docs_freshness_gate(root: Path) -> dict[str, object]:
    findings: list[dict[str, str]] = []
    _check_readme(root, findings)
    _check_post_poc_acceptance(root, findings)
    _check_post_poc_traceability_decision(root, findings)
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


def _check_readme(root: Path, findings: list[dict[str, str]]) -> None:
    readme = root / "README.md"
    text = readme.read_text(encoding="utf-8") if readme.exists() else ""
    required = [
        "POST_POC_REQUIREMENTS_GAP_AUDIT.md",
        "POST_POC_PRODUCTIZATION_DETAIL_SPEC.md",
        "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md",
        "POST_POC_IMPLEMENTATION_GAP_CHECKLIST.md",
        "product_ready=false",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        findings.append(_finding("docs_readme_state_stale", f"README missing freshness markers: {', '.join(missing)}", "README.md"))


def _check_post_poc_acceptance(root: Path, findings: list[dict[str, str]]) -> None:
    missing = []
    malformed = []
    for index in range(1, POST_POC_ACCEPTANCE_COUNT + 1):
        path = root / "docs" / "acceptance" / f"AC-20260703-postpoc-{index:03d}.md"
        if not path.exists():
            missing.append(str(path.relative_to(root)))
            continue
        text = path.read_text(encoding="utf-8")
        missing_markers = [
            marker for marker in [
                "intent_id:",
                "owner:",
                "status: accepted",
                "last_reviewed_at:",
                "next_review_due:",
                "## Evidence",
                "- Runtime:",
                "- Tests:",
                "- Registry:",
            ]
            if marker not in text
        ]
        if missing_markers:
            malformed.append(f"{path.relative_to(root)} missing {', '.join(missing_markers)}")
    if missing:
        findings.append(_finding("docs_acceptance_record_missing", f"Missing Post-PoC acceptance records: {', '.join(missing)}", "docs/acceptance"))
    if malformed:
        findings.append(_finding(
            "docs_acceptance_record_malformed",
            f"Malformed Post-PoC acceptance records: {'; '.join(malformed)}",
            "docs/acceptance",
        ))


def _check_post_poc_traceability_decision(root: Path, findings: list[dict[str, str]]) -> None:
    checklist = root / "docs" / "process" / "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md"
    if not checklist.exists():
        findings.append(_finding(
            "docs_post_poc_traceability_missing",
            "Post-PoC spec traceability checklist is missing.",
            "docs/process/POST_POC_SPEC_TRACEABILITY_CHECKLIST.md",
        ))
        return

    text = checklist.read_text(encoding="utf-8")
    gap_rows = [
        line for line in text.splitlines()
        if line.startswith("| HATE-POSTPOC-GAP-")
    ]
    accepted_rows = [
        line for line in gap_rows
        if line.startswith("| HATE-POSTPOC-GAP-") and "| accepted |" in line
    ]
    if len(gap_rows) != POST_POC_ACCEPTANCE_COUNT:
        findings.append(_finding(
            "docs_post_poc_traceability_row_count_mismatch",
            f"Post-PoC traceability checklist must contain {POST_POC_ACCEPTANCE_COUNT} gap rows; found {len(gap_rows)}.",
            "docs/process/POST_POC_SPEC_TRACEABILITY_CHECKLIST.md",
        ))
    if len(accepted_rows) != POST_POC_ACCEPTANCE_COUNT:
        findings.append(_finding(
            "docs_post_poc_traceability_acceptance_mismatch",
            f"Post-PoC traceability checklist must contain {POST_POC_ACCEPTANCE_COUNT} accepted rows; found {len(accepted_rows)}.",
            "docs/process/POST_POC_SPEC_TRACEABILITY_CHECKLIST.md",
        ))
    all_rows_accepted = len(accepted_rows) >= POST_POC_ACCEPTANCE_COUNT
    current_decision = text.split("## 4. Current Decision", 1)[-1]
    stale_not_implemented_claim = "remain not implemented" in current_decision.lower()
    accepted_decision_claim = "All 16 post-PoC gaps are `accepted`" in current_decision

    if all_rows_accepted and stale_not_implemented_claim:
        findings.append(_finding(
            "docs_post_poc_traceability_decision_stale",
            "Post-PoC traceability rows are accepted but Current Decision still claims implementation is incomplete.",
            "docs/process/POST_POC_SPEC_TRACEABILITY_CHECKLIST.md",
        ))
    if all_rows_accepted and not accepted_decision_claim:
        findings.append(_finding(
            "docs_post_poc_traceability_decision_missing",
            "Post-PoC traceability checklist must state that all 16 gaps are accepted when the matrix rows are accepted.",
            "docs/process/POST_POC_SPEC_TRACEABILITY_CHECKLIST.md",
        ))


def _check_schema_registry(root: Path, findings: list[dict[str, str]]) -> None:
    registry_path = root / "schemas" / "HATE" / "v1" / "schema-registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry_records = list(registry.get("records", []))
    records = {record["record_type"] for record in registry_records}
    missing = sorted(POST_POC_SCHEMA_RECORDS - records)
    if missing:
        findings.append(_finding(
            "docs_schema_registry_stale",
            f"Schema registry missing Post-PoC records: {', '.join(missing)}",
            "schemas/HATE/v1/schema-registry.json",
        ))
    missing_schema_paths = sorted(
        f"{record.get('record_type', '<unknown>')} => {record.get('schema', '')}"
        for record in registry_records
        if record.get("schema") and not (root / str(record["schema"])).exists()
    )
    if missing_schema_paths:
        findings.append(_finding(
            "docs_schema_registry_path_missing",
            f"Schema registry references missing schema files: {', '.join(missing_schema_paths)}",
            "schemas/HATE/v1/schema-registry.json",
        ))
    schema_type_mismatches = _schema_record_type_mismatches(root, registry_records)
    if schema_type_mismatches:
        findings.append(_finding(
            "docs_schema_record_type_mismatch",
            f"Schema registry record_type does not match schema const/enum: {', '.join(schema_type_mismatches)}",
            "schemas/HATE/v1/schema-registry.json",
        ))


def _schema_record_type_mismatches(root: Path, registry_records: list[dict[str, object]]) -> list[str]:
    mismatches = []
    for record in registry_records:
        record_type = str(record.get("record_type") or "")
        if record_type not in POST_POC_SCHEMA_RECORDS:
            continue
        schema_ref = str(record.get("schema") or "")
        if not schema_ref:
            continue
        schema_path = root / schema_ref
        if not schema_path.exists():
            continue
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            mismatches.append(f"{record_type} => invalid-json")
            continue
        record_type_schema = schema.get("properties", {}).get("record_type", {})
        const = record_type_schema.get("const")
        enum = record_type_schema.get("enum")
        if const and const != record_type:
            mismatches.append(f"{record_type} => const:{const}")
        elif enum and record_type not in enum:
            mismatches.append(f"{record_type} => enum-missing")
        elif not const and not enum:
            mismatches.append(f"{record_type} => no-const-or-enum")
    return sorted(mismatches)


def _check_birdseye_index(root: Path, findings: list[dict[str, str]]) -> None:
    index = root / "docs" / "birdseye" / "index.json"
    if not index.exists():
        findings.append(_finding("docs_codemap_stale", "Birdseye index is missing.", "docs/birdseye/index.json"))


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
