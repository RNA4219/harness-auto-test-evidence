from __future__ import annotations
from pathlib import Path
from typing import Any
from . import __version__
from .p0b_graph import append_gate_changed_and_risk_nodes
from .p0b_inputs import load_input_bundle, source_ref as fixture_source_ref
from .p0b_outputs import write_export_outputs
from .p0b_phases import (
    append_artifact_nodes,
    append_contract_nodes,
    append_coverage_nodes,
    append_mutation_nodes,
    append_sarif_finding_nodes,
    append_test_execution_nodes,
    append_test_obligation_edges,
    build_artifact_index,
)
from .p0b_types import ExportError


def export_qeg(
    fixture_dir: Path,
    out_dir: Path,
    source_version: str | None = None,
) -> dict[str, Any]:
    """P0b QEG optional evidence export.
    Args:
        fixture_dir: Input directory containing p0a/ subfolder and diff-risk-test.json
        out_dir: Output directory for QEG bundle
        source_version: Source version for generated records
    Returns:
        Export result with generated artifacts and completeness
    Raises:
        ExportError: If export fails or precheck decision is hard_dq
    """
    inputs = load_input_bundle(fixture_dir)
    fixture_dir = inputs.fixture_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    version = source_version or __version__
    p0a_dir = inputs.p0a_dir
    diff_risk_path = inputs.diff_risk_path
    run_record = inputs.run_record
    test_records = inputs.test_records
    coverage_records = inputs.coverage_records
    contract_records = inputs.contract_records
    mutation_records = inputs.mutation_records
    artifact_manifest = inputs.artifact_manifest
    precheck_decision = inputs.precheck_decision
    audit_record = inputs.audit_record
    sarif_record = inputs.sarif_record
    source_ref = lambda path: fixture_source_ref(fixture_dir, path)
    decision = precheck_decision.get("payload", {}).get("decision", "")
    if decision == "hard_dq":
        raise ExportError(
            "P0a precheck decision is hard_dq - QEG export not allowed",
            exit_code=2,
            report={"decision": "hard_dq", "reason": "P0a precheck disqualified"},
            out_dir=out_dir,
        )
    diff_risk_test = inputs.diff_risk_test
    risk_debt_lifecycle = inputs.risk_debt_lifecycle
    created_at = run_record.get("created_at", "")
    commit_sha = run_record.get("commit_sha", "")
    run_id = run_record.get("run_id", "")
    run_attempt = run_record.get("run_attempt", 1)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    unsupported_claims: list[dict[str, Any]] = []
    unsafe_artifacts: list[dict[str, Any]] = []
    excluded_artifacts: list[dict[str, Any]] = []
    artifact_by_id = build_artifact_index(artifact_manifest)
    (
        precheck_node_id,
        risks,
        risk_by_id,
        changed_entities_by_risk,
        changed_node_by_path,
        changed_node_ranges,
    ) = append_gate_changed_and_risk_nodes(
        nodes=nodes,
        edges=edges,
        unsupported_claims=unsupported_claims,
        run_id=run_id,
        run_attempt=run_attempt,
        decision=decision,
        precheck_decision=precheck_decision,
        run_record=run_record,
        diff_risk_test=diff_risk_test,
        p0a_dir=p0a_dir,
        diff_risk_path=diff_risk_path,
        source_ref=source_ref,
    )
    contract_by_id = append_contract_nodes(
        contract_records=contract_records,
        nodes=nodes,
        p0a_dir=p0a_dir,
        source_ref=source_ref,
    )
    mutation_by_id = append_mutation_nodes(
        mutation_records=mutation_records,
        nodes=nodes,
        p0a_dir=p0a_dir,
        source_ref=source_ref,
    )
    append_sarif_finding_nodes(
        sarif_record=sarif_record,
        nodes=nodes,
        edges=edges,
        changed_node_by_path=changed_node_by_path,
        changed_node_ranges=changed_node_ranges,
        p0a_dir=p0a_dir,
        source_ref=source_ref,
    )
    append_artifact_nodes(
        artifact_by_id=artifact_by_id,
        nodes=nodes,
        unsafe_artifacts=unsafe_artifacts,
        excluded_artifacts=excluded_artifacts,
        p0a_dir=p0a_dir,
        source_ref=source_ref,
    )
    test_node_ids = append_test_execution_nodes(
        test_records=test_records,
        artifact_by_id=artifact_by_id,
        nodes=nodes,
        edges=edges,
        unsupported_claims=unsupported_claims,
        unsafe_artifacts=unsafe_artifacts,
        excluded_artifacts=excluded_artifacts,
        run_id=run_id,
        run_attempt=run_attempt,
        p0a_dir=p0a_dir,
        source_ref=source_ref,
    )
    coverage_node_ids = append_coverage_nodes(
        coverage_records=coverage_records,
        test_node_ids=test_node_ids,
        nodes=nodes,
        edges=edges,
        p0a_dir=p0a_dir,
        source_ref=source_ref,
    )
    missing_executions = append_test_obligation_edges(
        diff_risk_test=diff_risk_test,
        risk_by_id=risk_by_id,
        changed_entities_by_risk=changed_entities_by_risk,
        test_node_ids=test_node_ids,
        artifact_by_id=artifact_by_id,
        contract_by_id=contract_by_id,
        mutation_by_id=mutation_by_id,
        edges=edges,
        unsupported_claims=unsupported_claims,
        unsafe_artifacts=unsafe_artifacts,
        excluded_artifacts=excluded_artifacts,
        p0a_dir=p0a_dir,
        diff_risk_path=diff_risk_path,
        source_ref=source_ref,
    )
    edges.append({
        "kind": "decides",
        "from": precheck_node_id,
        "to": f"qeg_export:{run_id}",
        "traceability": {
            "sourceRefs": [source_ref(p0a_dir / "precheck-decision.json")],
            "confidence": "high",
            "assumptions": [],
        },
    })
    return write_export_outputs(
        out_dir=out_dir,
        run_id=run_id,
        run_attempt=run_attempt,
        created_at=created_at,
        commit_sha=commit_sha,
        decision=decision,
        nodes=nodes,
        edges=edges,
        test_node_ids=test_node_ids,
        coverage_node_ids=coverage_node_ids,
        missing_executions=missing_executions,
        risks=risks,
        unsupported_claims=unsupported_claims,
        unsafe_artifacts=unsafe_artifacts,
        excluded_artifacts=excluded_artifacts,
        diff_risk_test=diff_risk_test,
        risk_debt_lifecycle=risk_debt_lifecycle,
        p0a_dir=p0a_dir,
        diff_risk_path=diff_risk_path,
        sarif_record=sarif_record,
        contract_records=contract_records,
        mutation_records=mutation_records,
        source_ref=source_ref,
    )
