"""Output serialization for P0b QEG export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .p0b_support import (
    _build_evidence_map,
    _build_manual_bridge_requests,
    _build_risk_debt_register,
    _calculate_completeness,
    _dedupe_gap_dicts,
    _validate_qeg_bundle_schema,
    _write_json,
)
from .p0b_types import SCHEMA_VERSION


def write_export_outputs(
    *,
    out_dir: Path,
    run_id: str,
    run_attempt: int,
    created_at: str,
    commit_sha: str,
    decision: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    test_node_ids: dict[str, str],
    coverage_node_ids: dict[str, str],
    missing_executions: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    unsupported_claims: list[dict[str, Any]],
    unsafe_artifacts: list[dict[str, Any]],
    excluded_artifacts: list[dict[str, Any]],
    diff_risk_test: dict[str, Any],
    risk_debt_lifecycle: dict[str, Any],
    p0a_dir: Path,
    diff_risk_path: Path,
    sarif_record: dict[str, Any],
    contract_records: list[dict[str, Any]],
    mutation_records: list[dict[str, Any]],
    source_ref: Callable[[Path], str],
) -> dict[str, Any]:
    evidence_map = _build_evidence_map(
        run_id=run_id,
        run_attempt=run_attempt,
        nodes=nodes,
        edges=edges,
        test_node_ids=test_node_ids,
        coverage_node_ids=coverage_node_ids,
        missing_executions=missing_executions,
        risks=risks,
        unsupported_claims=unsupported_claims,
        unsafe_artifacts=_dedupe_gap_dicts(unsafe_artifacts),
    )
    completeness = _calculate_completeness(
        nodes=nodes,
        edges=edges,
        missing_artifacts=[],
        missing_executions=missing_executions,
        risks=risks,
        parser_failures=[],
        unsupported_claims=evidence_map["gaps"]["unsupported_claims"],
        unsafe_artifacts=evidence_map["gaps"]["unsafe_artifacts"],
        excluded_artifacts=_dedupe_gap_dicts(excluded_artifacts),
    )
    qeg_bundle = {
        "metadata": {
            "qegVersion": "HATE/v1",
            "runId": run_id,
            "runAttempt": run_attempt,
            "createdAt": created_at,
            "profile": "lean",
            "inputArtifacts": [
                {"kind": "HATE-run", "path": source_ref(p0a_dir / "HATE-run.json")},
                {"kind": "HATE-test-results", "path": source_ref(p0a_dir / "HATE-test-results.ndjson")},
                {"kind": "HATE-coverage", "path": source_ref(p0a_dir / "HATE-coverage.ndjson")},
                {"kind": "precheck-decision", "path": source_ref(p0a_dir / "precheck-decision.json")},
                *([{"kind": "HATE-static", "path": source_ref(p0a_dir / "HATE-static.sarif")}] if sarif_record else []),
                *([{"kind": "HATE-contract", "path": source_ref(p0a_dir / "HATE-contract.ndjson")}] if contract_records else []),
                *([{"kind": "HATE-mutation", "path": source_ref(p0a_dir / "HATE-mutation.ndjson")}] if mutation_records else []),
            ],
            "debugOnly": decision == "hard_dq",
        },
        "nodes": nodes,
        "edges": edges,
        "completeness": completeness,
    }
    qeg_schema_compatibility = _validate_qeg_bundle_schema(qeg_bundle)
    export_report = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "commit_sha": commit_sha,
        "created_at": created_at,
        "export_status": "partial" if completeness["partial"] else "success",
        "completeness": completeness,
        "qeg_schema_compatibility": qeg_schema_compatibility,
        "unsupportedClaims": completeness["unsupportedClaims"],
        "contract_failures": [
            claim for claim in completeness["unsupportedClaims"]
            if claim.get("reason") in {"required contract failed", "required contract evidence missing"}
        ],
        "mutation_gaps": [
            claim for claim in completeness["unsupportedClaims"]
            if claim.get("reason") in {"required mutation survived", "required mutation evidence missing"}
        ],
        "missing_execution": missing_executions,
        "excludedArtifacts": completeness["excludedArtifacts"],
        "source_refs": [
            source_ref(p0a_dir / "precheck-decision.json"),
            source_ref(diff_risk_path) if diff_risk_path.exists() else "none",
        ],
        "publish_gate_override": False,
    }
    summary_content = "\n".join([
        "# P0b QEG Export Summary",
        "",
        f"- Run: `{run_id}` attempt `{run_attempt}`",
        f"- Commit: `{commit_sha[:12]}`",
        f"- Precheck: `{decision}`",
        f"- Nodes: {len(nodes)}",
        f"- Edges: {len(edges)}",
        f"- Completeness: `{completeness['score']:.2f}`",
        f"- Missing execution gaps: {len(missing_executions)}",
        "",
        "Generated artifacts:",
        f"- `qeg-bundle.json` ({len(nodes)} nodes, {len(edges)} edges)",
        "- `evidence-map.json`",
        "- `qeg-export-report.json`",
        "",
        "This export is advisory optional evidence for QEG.",
        "HATE does not approve release. `publish_gate_override=false`.",
        "",
    ])
    _write_json(out_dir / "qeg-bundle.json", qeg_bundle)
    _write_json(out_dir / "evidence-map.json", evidence_map)
    _write_json(out_dir / "qeg-export-report.json", export_report)
    _write_json(
        out_dir / "diff-risk-test.json",
        diff_risk_test if diff_risk_test else {"schema_version": SCHEMA_VERSION, "changed_entities": [], "risks": [], "test_obligations": []},
    )
    generated = [
        "qeg-bundle.json",
        "evidence-map.json",
        "diff-risk-test.json",
        "qeg-export-report.json",
        "qeg-export-summary.md",
    ]
    if missing_executions:
        _write_json(
            out_dir / "risk-debt-register.json",
            _build_risk_debt_register(
                run_id,
                run_attempt,
                missing_executions,
                risks=risks,
                lifecycle=risk_debt_lifecycle,
                created_at=created_at,
            ),
        )
        (out_dir / "manual-bb-bridge-requests.jsonl").write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in _build_manual_bridge_requests(run_id, run_attempt, missing_executions)) + "\n",
            encoding="utf-8",
        )
        generated.extend(["risk-debt-register.json", "manual-bb-bridge-requests.jsonl"])
    (out_dir / "qeg-export-summary.md").write_text(summary_content, encoding="utf-8")
    return {
        "export_status": "partial" if completeness["partial"] else "success",
        "exit_code": 0 if completeness["score"] >= 0.8 else 0,
        "generated": generated,
        "completeness": completeness,
        "missing_executions": len(missing_executions),
        "out_dir": str(out_dir),
        "publish_gate_override": False,
    }
