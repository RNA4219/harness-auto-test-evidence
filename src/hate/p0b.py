from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from . import __version__
from .p0b_support import (
    _artifact_is_unsafe,
    _artifact_refs_from_test,
    _build_evidence_map,
    _build_manual_bridge_requests,
    _build_risk_debt_register,
    _calculate_completeness,
    _dedupe_gap_dicts,
    _hash_path,
    _hash_test_id,
    _playwright_artifact_role,
    _read_json,
    _read_ndjson,
    _validate_qeg_bundle_schema,
    _write_json,
)
SCHEMA_VERSION = "HATE/v1"
SOURCE_TOOL = "harness-auto-test-evidence"
@dataclass
class ExportError(Exception):
    message: str
    exit_code: int = 1
    report: dict[str, Any] | None = None
    out_dir: Path | None = None
    def __str__(self) -> str:
        return self.message
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
    fixture_dir = fixture_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    version = source_version or __version__
    p0a_dir = fixture_dir / "p0a"
    diff_risk_path = fixture_dir / "diff-risk-test.json"
    risk_debt_lifecycle_path = fixture_dir / "risk-debt-lifecycle.json"
    def source_ref(path: Path) -> str:
        """Return a stable fixture-relative source reference."""
        try:
            return f"fixture:/{path.resolve().relative_to(fixture_dir).as_posix()}"
        except ValueError:
            return path.as_posix()
    required_p0a_files = [
        "HATE-run.json",
        "HATE-test-results.ndjson",
        "HATE-coverage.ndjson",
        "artifact-manifest.json",
        "precheck-decision.json",
        "record.json",
    ]
    missing_artifacts: list[str] = []
    for name in required_p0a_files:
        if not (p0a_dir / name).exists():
            missing_artifacts.append(name)
    if missing_artifacts:
        raise ExportError(
            f"Missing required P0a artifacts: {', '.join(missing_artifacts)}",
            exit_code=2,
        )
    run_record = _read_json(p0a_dir / "HATE-run.json")
    test_records = _read_ndjson(p0a_dir / "HATE-test-results.ndjson")
    coverage_records = _read_ndjson(p0a_dir / "HATE-coverage.ndjson")
    contract_records = _read_ndjson(p0a_dir / "HATE-contract.ndjson") if (p0a_dir / "HATE-contract.ndjson").exists() else []
    mutation_records = _read_ndjson(p0a_dir / "HATE-mutation.ndjson") if (p0a_dir / "HATE-mutation.ndjson").exists() else []
    artifact_manifest = _read_json(p0a_dir / "artifact-manifest.json")
    precheck_decision = _read_json(p0a_dir / "precheck-decision.json")
    audit_record = _read_json(p0a_dir / "record.json")
    sarif_record = _read_json(p0a_dir / "HATE-static.sarif") if (p0a_dir / "HATE-static.sarif").exists() else {}
    decision = precheck_decision.get("payload", {}).get("decision", "")
    if decision == "hard_dq":
        raise ExportError(
            "P0a precheck decision is hard_dq - QEG export not allowed",
            exit_code=2,
            report={"decision": "hard_dq", "reason": "P0a precheck disqualified"},
            out_dir=out_dir,
        )
    diff_risk_test: dict[str, Any] = {}
    if diff_risk_path.exists():
        diff_risk_test = _read_json(diff_risk_path)
    risk_debt_lifecycle: dict[str, Any] = {}
    if risk_debt_lifecycle_path.exists():
        risk_debt_lifecycle = _read_json(risk_debt_lifecycle_path)
    created_at = run_record.get("created_at", "")
    commit_sha = run_record.get("commit_sha", "")
    run_id = run_record.get("run_id", "")
    run_attempt = run_record.get("run_attempt", 1)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    unsupported_claims: list[dict[str, Any]] = []
    unsafe_artifacts: list[dict[str, Any]] = []
    excluded_artifacts: list[dict[str, Any]] = []
    artifact_by_id = {
        str(artifact.get("artifact_id", "")): artifact
        for artifact in artifact_manifest.get("artifacts", [])
        if artifact.get("artifact_id")
    }
    contract_by_id: dict[str, dict[str, Any]] = {}
    mutation_by_id: dict[str, dict[str, Any]] = {}
    precheck_node_id = f"hate_precheck:{run_id}:{run_attempt}"
    nodes.append({
        "id": precheck_node_id,
        "kind": "gate_verdict",
        "label": f"HATE P0a Precheck {run_id}",
        "data": {
            "decision": decision,
            "exit_code": precheck_decision.get("payload", {}).get("exit_code", 0),
            "qeg_export_allowed": precheck_decision.get("payload", {}).get("qeg_export_allowed", False),
            "qeg_export_phase": precheck_decision.get("payload", {}).get("qeg_export_phase", "P0b"),
        },
        "sourceRefs": [source_ref(p0a_dir / "precheck-decision.json")],
    })
    run_node_id = f"run:{run_id}:{run_attempt}"
    nodes.append({
        "id": run_node_id,
        "kind": "run",
        "label": f"CI Run {run_id}",
        "data": run_record.get("payload", {}),
        "sourceRefs": [source_ref(p0a_dir / "HATE-run.json")],
    })
    changed_entities = diff_risk_test.get("changed_entities", [])
    changed_entities_by_risk: dict[str, list[dict[str, Any]]] = {}
    for entity in changed_entities:
        if not isinstance(entity, dict):
            continue
        for risk_ref in entity.get("risk_refs", []):
            changed_entities_by_risk.setdefault(str(risk_ref), []).append(entity)
    changed_node_by_path: dict[str, list[str]] = {}
    changed_node_ranges: dict[str, dict[str, int]] = {}
    for entity in changed_entities:
        entity_id = entity.get("entity_id", "")
        path = entity.get("path", "")
        ranges = entity.get("ranges", [])
        for rng in ranges:
            start = rng.get("start_line", 0)
            end = rng.get("end_line", 0)
            node_id = f"changed_code:{path}#L{start}-L{end}"
            nodes.append({
                "id": node_id,
                "kind": "changed_code",
                "label": f"Changed: {path} L{start}-L{end}",
                "data": {
                    "path": path,
                    "start_line": start,
                    "end_line": end,
                },
                "sourceRefs": [source_ref(diff_risk_path)],
            })
            changed_node_by_path.setdefault(path.replace("\\", "/"), []).append(node_id)
            changed_node_ranges[node_id] = {"start_line": int(start), "end_line": int(end)}
            for risk_ref in entity.get("risk_refs", []):
                edges.append({
                    "kind": "touches",
                    "from": node_id,
                    "to": f"risk:{risk_ref}",
                    "traceability": {
                        "sourceRefs": [source_ref(diff_risk_path)],
                        "confidence": "high",
                        "assumptions": [],
                    },
                })
    risks = diff_risk_test.get("risks", [])
    risk_by_id = {str(risk.get("risk_id", "")): risk for risk in risks if isinstance(risk, dict)}
    for risk in risks:
        risk_id = risk.get("risk_id", "")
        node_id = f"risk:{risk_id}"
        risk_source_refs = risk.get("source_refs", [])
        if not risk_source_refs:
            unsupported_claims.append({
                "risk_id": risk_id,
                "reason": "risk source_refs missing",
            })
        nodes.append({
            "id": node_id,
            "kind": "risk",
            "label": risk.get("title", f"Risk {risk_id}"),
            "data": {
                "severity": risk.get("severity", "medium"),
                "required_test_layers": risk.get("required_test_layers", []),
            },
            "sourceRefs": risk_source_refs,
        })
    for record in contract_records:
        payload = record.get("payload", {})
        contract_id = str(payload.get("contract_id") or payload.get("pact_id") or payload.get("verification_id") or "")
        if not contract_id:
            continue
        status = _contract_status(payload)
        node_id = f"contract:{contract_id}"
        contract_by_id[contract_id] = {"node_id": node_id, "record": record, "payload": payload, "status": status}
        nodes.append({
            "id": node_id,
            "kind": "contract_evidence",
            "label": payload.get("name") or f"{payload.get('consumer', 'consumer')} -> {payload.get('provider', 'provider')}",
            "data": {
                "contract_id": contract_id,
                "provider": payload.get("provider", ""),
                "consumer": payload.get("consumer", ""),
                "interaction": payload.get("interaction", ""),
                "status": status,
                "required": bool(payload.get("required", False)),
                "verification_id": payload.get("verification_id", ""),
                "pact_url": payload.get("pact_url", ""),
                "message": payload.get("message", ""),
            },
            "sourceRefs": [source_ref(p0a_dir / "HATE-contract.ndjson")],
        })
    for record in mutation_records:
        payload = record.get("payload", {})
        mutation_id = str(payload.get("mutation_id") or payload.get("mutant_id") or payload.get("id") or "")
        if not mutation_id:
            continue
        status = _mutation_status(payload)
        node_id = f"mutation:{mutation_id}"
        mutation_by_id[mutation_id] = {"node_id": node_id, "record": record, "payload": payload, "status": status}
        nodes.append({
            "id": node_id,
            "kind": "mutation_evidence",
            "label": payload.get("name") or f"{payload.get('mutator', 'mutant')} {mutation_id}",
            "data": {
                "mutation_id": mutation_id,
                "status": status,
                "mutator": payload.get("mutator", ""),
                "file": str(payload.get("file") or payload.get("source_file") or "").replace("\\", "/"),
                "start_line": int(payload.get("start_line") or payload.get("line") or 0),
                "end_line": int(payload.get("end_line") or payload.get("line") or 0),
                "covered_by": payload.get("covered_by") or payload.get("covered_by_tests") or [],
                "killed_by": payload.get("killed_by") or payload.get("killed_by_tests") or [],
                "message": payload.get("message", ""),
            },
            "sourceRefs": [source_ref(p0a_dir / "HATE-mutation.ndjson")],
        })
    for finding in _sarif_findings(sarif_record):
        finding_node_id = f"finding:{finding['finding_id']}"
        nodes.append({
            "id": finding_node_id,
            "kind": "finding",
            "label": finding["title"],
            "data": {
                "rule_id": finding["rule_id"],
                "rule_name": finding["rule_name"],
                "rule_short_description": finding["rule_short_description"],
                "rule_full_description": finding["rule_full_description"],
                "help_uri": finding["help_uri"],
                "level": finding["level"],
                "severity": finding["severity"],
                "path": finding["path"],
                "start_line": finding["start_line"],
                "end_line": finding["end_line"],
                "start_column": finding["start_column"],
                "end_column": finding["end_column"],
                "location": finding["location"],
                "fingerprints": finding["fingerprints"],
                "message": finding["message"],
            },
            "sourceRefs": [source_ref(p0a_dir / "HATE-static.sarif")],
        })
        for changed_node_id in changed_node_by_path.get(finding["path"], []):
            changed_range = changed_node_ranges.get(changed_node_id, {})
            if not _line_ranges_overlap(
                int(changed_range.get("start_line", 0)),
                int(changed_range.get("end_line", 0)),
                int(finding["start_line"]),
                int(finding["end_line"]),
            ):
                continue
            edges.append({
                "kind": "touches",
                "from": changed_node_id,
                "to": finding_node_id,
                "traceability": {
                    "sourceRefs": [source_ref(p0a_dir / "HATE-static.sarif")],
                    "confidence": "high",
                    "assumptions": [],
                },
            })
    for artifact_id, artifact in artifact_by_id.items():
        if _artifact_is_unsafe(artifact):
            unsafe_gap = {
                "artifact_id": artifact_id,
                "path": artifact.get("path", ""),
                "reason": "artifact is not safe for QEG export",
            }
            unsafe_artifacts.append(unsafe_gap)
            excluded_artifacts.append(unsafe_gap)
            continue
        playwright_role = _playwright_artifact_role(artifact)
        nodes.append({
            "id": f"artifact:{artifact_id}",
            "kind": "evidence_artifact",
            "label": artifact_id,
            "data": {
                "kind": artifact.get("kind", "artifact"),
                "adapter": "playwright" if playwright_role else artifact.get("adapter", ""),
                "artifact_role": playwright_role,
                "path": artifact.get("path", ""),
                "sha256": artifact.get("sha256", ""),
            },
            "sourceRefs": [source_ref(p0a_dir / "artifact-manifest.json")],
        })
    test_node_ids: dict[str, str] = {}  # canonical_test_id -> test node id
    for record in test_records:
        payload = record.get("payload", {})
        canonical_test_id = payload.get("canonical_test_id", "")
        if not canonical_test_id:
            continue
        test_hash = _hash_test_id(canonical_test_id)
        test_node_id = f"test:{test_hash}"
        test_node_ids[canonical_test_id] = test_node_id
        nodes.append({
            "id": test_node_id,
            "kind": "test",
            "label": payload.get("name", canonical_test_id),
            "data": {
                "canonical_test_id": canonical_test_id,
                "framework": payload.get("framework", "unknown"),
                "status": payload.get("status", "unknown"),
                "file": payload.get("file", ""),
                "duration_ms": payload.get("duration_ms", 0),
            },
            "sourceRefs": [source_ref(p0a_dir / "HATE-test-results.ndjson")],
        })
        execution_node_id = f"execution:{run_id}:{test_hash}"
        nodes.append({
            "id": execution_node_id,
            "kind": "execution_evidence",
            "label": f"Execution: {canonical_test_id}",
            "data": {
                "run_id": run_id,
                "run_attempt": run_attempt,
                "status": payload.get("status", "unknown"),
                "duration_ms": payload.get("duration_ms", 0),
            },
            "sourceRefs": [source_ref(p0a_dir / "HATE-test-results.ndjson")],
        })
        edges.append({
            "kind": "evidenced_by",
            "from": test_node_id,
            "to": execution_node_id,
            "traceability": {
                "sourceRefs": [source_ref(p0a_dir / "HATE-test-results.ndjson")],
                "confidence": "high",
                "assumptions": [],
            },
        })
        for artifact_ref in _artifact_refs_from_test(payload):
            artifact = artifact_by_id.get(artifact_ref)
            if artifact is None:
                unsupported_claims.append({
                    "test_id": canonical_test_id,
                    "artifact_id": artifact_ref,
                    "reason": "test artifact reference not found in artifact manifest",
                })
                continue
            if _artifact_is_unsafe(artifact):
                unsafe_gap = {
                    "test_id": canonical_test_id,
                    "artifact_id": artifact_ref,
                    "path": artifact.get("path", ""),
                    "reason": "test requires unsafe artifact",
                }
                unsafe_artifacts.append(unsafe_gap)
                excluded_artifacts.append(unsafe_gap)
                continue
            playwright_role = _playwright_artifact_role(artifact)
            edge_source_refs = [
                source_ref(p0a_dir / "HATE-test-results.ndjson"),
                source_ref(p0a_dir / "artifact-manifest.json"),
            ]
            if playwright_role:
                edges.append({
                    "kind": "evidenced_by",
                    "from": test_node_id,
                    "to": f"artifact:{artifact_ref}",
                    "traceability": {
                        "sourceRefs": edge_source_refs,
                        "confidence": "medium",
                        "assumptions": ["Playwright artifact is attached to this test result"],
                        "adapter": "playwright",
                        "artifact_role": playwright_role,
                    },
                })
            edges.append({
                "kind": "evidenced_by",
                "from": execution_node_id,
                "to": f"artifact:{artifact_ref}",
                "traceability": {
                    "sourceRefs": edge_source_refs,
                    "confidence": "high",
                    "assumptions": [],
                    **({"adapter": "playwright", "artifact_role": playwright_role} if playwright_role else {}),
                },
            })
    coverage_node_ids: dict[str, str] = {}  # file -> coverage node id
    for record in coverage_records:
        payload = record.get("payload", {})
        file_path = payload.get("file", "")
        if not file_path:
            continue
        path_hash = _hash_path(file_path)
        coverage_node_id = f"coverage:{path_hash}"
        coverage_node_ids[file_path] = coverage_node_id
        nodes.append({
            "id": coverage_node_id,
            "kind": "coverage",
            "label": f"Coverage: {file_path}",
            "data": {
                "file": file_path,
                "format": payload.get("format", "lcov"),
                "line_hits": payload.get("line_hits", {}),
                "branch_hits": payload.get("branch_hits", []),
                "contexts": payload.get("contexts", []),
            },
            "sourceRefs": [source_ref(p0a_dir / "HATE-coverage.ndjson")],
        })
        for ctx in payload.get("contexts", []):
            # Contexts can be either string (legacy) or object with test_id
            test_id = ctx if isinstance(ctx, str) else ctx.get("test_id") if isinstance(ctx, dict) else None
            if test_id:
                test_node_id = test_node_ids.get(test_id)
                if test_node_id:
                    edges.append({
                        "kind": "supports",
                        "from": coverage_node_id,
                        "to": test_node_id,
                        "traceability": {
                            "sourceRefs": [source_ref(p0a_dir / "HATE-coverage.ndjson")],
                            "confidence": "medium",
                            "assumptions": ["coverage context maps to test"],
                        },
                    })
    test_obligations = diff_risk_test.get("test_obligations", [])
    missing_executions: list[dict[str, Any]] = []
    for obligation in test_obligations:
        risk_id = obligation.get("risk_id", "")
        risk_node_id = f"risk:{risk_id}"
        risk = risk_by_id.get(str(risk_id), {})
        related_entities = changed_entities_by_risk.get(str(risk_id), [])
        expected_tests = obligation.get("expected_test_refs", [])
        for test_ref in expected_tests:
            canonical_test_id = f"junit:{test_ref}"
            test_node_id = test_node_ids.get(canonical_test_id)
            if test_node_id:
                edges.append({
                    "kind": "requires_test",
                    "from": risk_node_id,
                    "to": test_node_id,
                    "traceability": {
                        "sourceRefs": [source_ref(diff_risk_path)],
                        "confidence": "high",
                        "assumptions": [],
                    },
                })
            else:
                missing_executions.append({
                    "risk_id": risk_id,
                    "risk_title": risk.get("title", ""),
                    "severity": risk.get("severity", "high"),
                    "obligation_id": obligation.get("obligation_id", ""),
                    "expected_test_ref": test_ref,
                    "required_evidence_kinds": obligation.get("required_evidence_kinds", []),
                    "required_test_layers": risk.get("required_test_layers", []),
                    "risk_source_refs": risk.get("source_refs", []),
                    "changed_entity_ids": [entity.get("entity_id", "") for entity in related_entities],
                    "changed_entities": [
                        {
                            "entity_id": entity.get("entity_id", ""),
                            "path": entity.get("path", ""),
                            "ranges": entity.get("ranges", []),
                        }
                        for entity in related_entities
                    ],
                    "reason": "test not found in execution results",
                })
        if "artifact" in obligation.get("required_evidence_kinds", []):
            for artifact_ref in obligation.get("required_artifact_refs", []):
                artifact = artifact_by_id.get(artifact_ref)
                if artifact is None:
                    unsupported_claims.append({
                        "risk_id": risk_id,
                        "artifact_id": artifact_ref,
                        "reason": "required artifact not found in artifact manifest",
                    })
                elif _artifact_is_unsafe(artifact):
                    unsafe_gap = {
                        "risk_id": risk_id,
                        "artifact_id": artifact_ref,
                        "path": artifact.get("path", ""),
                        "reason": "required artifact is unsafe for export",
                    }
                    unsafe_artifacts.append(unsafe_gap)
                    excluded_artifacts.append(unsafe_gap)
        if "contract" in obligation.get("required_evidence_kinds", []):
            for contract_ref in obligation.get("required_contract_refs", []):
                contract = contract_by_id.get(str(contract_ref))
                if contract is None:
                    unsupported_claims.append({
                        "risk_id": risk_id,
                        "contract_id": str(contract_ref),
                        "reason": "required contract evidence missing",
                    })
                    continue
                status = contract["status"]
                contract_node_id = str(contract["node_id"])
                if status in {"passed", "success", "verified"}:
                    edges.append({
                        "kind": "supports",
                        "from": contract_node_id,
                        "to": risk_node_id,
                        "traceability": {
                            "sourceRefs": [source_ref(p0a_dir / "HATE-contract.ndjson"), source_ref(diff_risk_path)],
                            "confidence": "high",
                            "assumptions": [],
                            "adapter": "pact",
                        },
                    })
                else:
                    unsupported_claims.append({
                        "risk_id": risk_id,
                        "contract_id": str(contract_ref),
                        "reason": "required contract failed",
                        "status": status,
                    })
                    edges.append({
                        "kind": "contradicts",
                        "from": contract_node_id,
                        "to": risk_node_id,
                        "traceability": {
                            "sourceRefs": [source_ref(p0a_dir / "HATE-contract.ndjson"), source_ref(diff_risk_path)],
                            "confidence": "high",
                            "assumptions": [],
                            "adapter": "pact",
                        },
                    })
        if "mutation" in obligation.get("required_evidence_kinds", []):
            for mutation_ref in obligation.get("required_mutation_refs", []):
                mutation = mutation_by_id.get(str(mutation_ref))
                if mutation is None:
                    unsupported_claims.append({
                        "risk_id": risk_id,
                        "mutation_id": str(mutation_ref),
                        "reason": "required mutation evidence missing",
                    })
                    continue
                status = mutation["status"]
                mutation_node_id = str(mutation["node_id"])
                if status in {"killed", "timeout", "covered"}:
                    edges.append({
                        "kind": "supports",
                        "from": mutation_node_id,
                        "to": risk_node_id,
                        "traceability": {
                            "sourceRefs": [source_ref(p0a_dir / "HATE-mutation.ndjson"), source_ref(diff_risk_path)],
                            "confidence": "medium",
                            "assumptions": ["mutation evidence strengthens oracle adequacy"],
                            "adapter": "stryker",
                        },
                    })
                else:
                    unsupported_claims.append({
                        "risk_id": risk_id,
                        "mutation_id": str(mutation_ref),
                        "reason": "required mutation survived",
                        "status": status,
                    })
                    edges.append({
                        "kind": "contradicts",
                        "from": mutation_node_id,
                        "to": risk_node_id,
                        "traceability": {
                            "sourceRefs": [source_ref(p0a_dir / "HATE-mutation.ndjson"), source_ref(diff_risk_path)],
                            "confidence": "high",
                            "assumptions": ["survived or uncovered mutant weakens oracle adequacy"],
                            "adapter": "stryker",
                        },
                    })
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
        missing_artifacts=missing_artifacts,
        missing_executions=missing_executions,
        risks=risks,
        parser_failures=[],  # P0a already validated
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
    summary_lines = [
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
        f"- `evidence-map.json`",
        f"- `qeg-export-report.json`",
        "",
        "This export is advisory optional evidence for QEG.",
        "HATE does not approve release. `publish_gate_override=false`.",
        "",
    ]
    summary_content = "\n".join(summary_lines)
    _write_json(out_dir / "qeg-bundle.json", qeg_bundle)
    _write_json(out_dir / "evidence-map.json", evidence_map)
    _write_json(out_dir / "qeg-export-report.json", export_report)
    _write_json(out_dir / "diff-risk-test.json", diff_risk_test if diff_risk_test else {"schema_version": SCHEMA_VERSION, "changed_entities": [], "risks": [], "test_obligations": []})
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
    result = {
        "export_status": "partial" if completeness["partial"] else "success",
        "exit_code": 0 if completeness["score"] >= 0.8 else 0,  # P0b does not fail on partial
        "generated": generated,
        "completeness": completeness,
        "missing_executions": len(missing_executions),
        "out_dir": str(out_dir),
        "publish_gate_override": False,
    }
    return result


def _sarif_findings(sarif: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for run_index, run in enumerate(sarif.get("runs", [])):
        if not isinstance(run, dict):
            continue
        rules = {
            str(rule.get("id", "")): rule
            for tool in [run.get("tool", {})]
            for driver in [tool.get("driver", {})] if isinstance(driver, dict)
            for rule in driver.get("rules", []) if isinstance(rule, dict)
        }
        for result_index, result in enumerate(run.get("results", [])):
            if not isinstance(result, dict):
                continue
            rule_id = str(result.get("ruleId", "unknown-rule"))
            rule = rules.get(rule_id, {})
            location = _first_sarif_location(result)
            path = location.get("path", "")
            start_line = location.get("start_line", 0)
            end_line = location.get("end_line", start_line)
            message = result.get("message", {})
            message_text = str(message.get("text", "")) if isinstance(message, dict) else str(message)
            properties = result.get("properties", {}) if isinstance(result.get("properties"), dict) else {}
            fingerprints = result.get("fingerprints", {}) if isinstance(result.get("fingerprints"), dict) else {}
            partial_fingerprints = result.get("partialFingerprints", {}) if isinstance(result.get("partialFingerprints"), dict) else {}
            merged_fingerprints = {**partial_fingerprints, **fingerprints}
            findings.append({
                "finding_id": hashlib.sha256(f"{run_index}:{result_index}:{rule_id}:{path}:{start_line}".encode("utf-8")).hexdigest()[:16],
                "rule_id": rule_id,
                "rule_name": str(rule.get("name") or rule_id),
                "rule_short_description": _sarif_multiformat_text(rule.get("shortDescription")),
                "rule_full_description": _sarif_multiformat_text(rule.get("fullDescription")),
                "help_uri": str(rule.get("helpUri", "")),
                "title": str(rule.get("name") or rule_id),
                "level": str(result.get("level", "warning")),
                "severity": str(properties.get("security-severity") or properties.get("severity") or result.get("level", "warning")),
                "path": path.replace("\\", "/"),
                "start_line": start_line,
                "end_line": end_line,
                "start_column": location.get("start_column", 0),
                "end_column": location.get("end_column", 0),
                "location": location,
                "fingerprints": merged_fingerprints,
                "message": message_text,
            })
    return findings


def _contract_status(payload: dict[str, Any]) -> str:
    raw = str(payload.get("status") or payload.get("result") or payload.get("verification_status") or "").strip().lower()
    aliases = {
        "pass": "passed",
        "passed": "passed",
        "success": "passed",
        "verified": "passed",
        "ok": "passed",
        "fail": "failed",
        "failed": "failed",
        "failure": "failed",
        "error": "failed",
    }
    return aliases.get(raw, raw or "unknown")


def _mutation_status(payload: dict[str, Any]) -> str:
    raw = str(payload.get("status") or payload.get("result") or payload.get("mutant_status") or "").strip().lower()
    normalized = raw.replace(" ", "_").replace("-", "_")
    aliases = {
        "killed": "killed",
        "killed_by_timeout": "timeout",
        "timeout": "timeout",
        "survived": "survived",
        "no_coverage": "no_coverage",
        "nocoverage": "no_coverage",
        "not_covered": "no_coverage",
        "covered": "covered",
        "ignored": "ignored",
    }
    return aliases.get(normalized, normalized or "unknown")


def _first_sarif_location(result: dict[str, Any]) -> dict[str, Any]:
    locations = result.get("locations", [])
    if not locations or not isinstance(locations, list) or not isinstance(locations[0], dict):
        return {"path": "", "start_line": 0}
    physical = locations[0].get("physicalLocation", {})
    if not isinstance(physical, dict):
        return {"path": "", "start_line": 0}
    artifact = physical.get("artifactLocation", {})
    region = physical.get("region", {})
    path = str(artifact.get("uri", "")) if isinstance(artifact, dict) else ""
    start_line = int(region.get("startLine", 0)) if isinstance(region, dict) else 0
    end_line = int(region.get("endLine", start_line)) if isinstance(region, dict) else start_line
    start_column = int(region.get("startColumn", 0)) if isinstance(region, dict) else 0
    end_column = int(region.get("endColumn", 0)) if isinstance(region, dict) else 0
    return {
        "path": path.replace("\\", "/"),
        "start_line": start_line,
        "end_line": end_line,
        "start_column": start_column,
        "end_column": end_column,
        "uri_base_id": str(artifact.get("uriBaseId", "")) if isinstance(artifact, dict) else "",
    }


def _line_ranges_overlap(left_start: int, left_end: int, right_start: int, right_end: int) -> bool:
    if left_start <= 0 or right_start <= 0:
        return True
    left_end = left_end or left_start
    right_end = right_end or right_start
    return left_start <= right_end and right_start <= left_end


def _sarif_multiformat_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or value.get("markdown") or "")
    return ""
