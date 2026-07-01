"""QEG graph construction phases for P0b export."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .p0b_sarif import (
    _contract_status,
    _line_ranges_overlap,
    _mutation_status,
    _sarif_findings,
)
from .p0b_support import (
    _artifact_is_unsafe,
    _artifact_refs_from_test,
    _hash_path,
    _hash_test_id,
    _playwright_artifact_role,
)


def append_contract_nodes(
    *,
    contract_records: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
    p0a_dir: Path,
    source_ref: Callable[[Path], str],
) -> dict[str, dict[str, Any]]:
    contract_by_id: dict[str, dict[str, Any]] = {}
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
    return contract_by_id


def append_mutation_nodes(
    *,
    mutation_records: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
    p0a_dir: Path,
    source_ref: Callable[[Path], str],
) -> dict[str, dict[str, Any]]:
    mutation_by_id: dict[str, dict[str, Any]] = {}
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
    return mutation_by_id


def append_sarif_finding_nodes(
    *,
    sarif_record: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    changed_node_by_path: dict[str, list[str]],
    changed_node_ranges: dict[str, dict[str, int]],
    p0a_dir: Path,
    source_ref: Callable[[Path], str],
) -> None:
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


def build_artifact_index(artifact_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(artifact.get("artifact_id", "")): artifact
        for artifact in artifact_manifest.get("artifacts", [])
        if artifact.get("artifact_id")
    }


def append_artifact_nodes(
    *,
    artifact_by_id: dict[str, dict[str, Any]],
    nodes: list[dict[str, Any]],
    unsafe_artifacts: list[dict[str, Any]],
    excluded_artifacts: list[dict[str, Any]],
    p0a_dir: Path,
    source_ref: Callable[[Path], str],
) -> None:
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


def append_test_execution_nodes(
    *,
    test_records: list[dict[str, Any]],
    artifact_by_id: dict[str, dict[str, Any]],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    unsupported_claims: list[dict[str, Any]],
    unsafe_artifacts: list[dict[str, Any]],
    excluded_artifacts: list[dict[str, Any]],
    run_id: str,
    run_attempt: int,
    p0a_dir: Path,
    source_ref: Callable[[Path], str],
) -> dict[str, str]:
    test_node_ids: dict[str, str] = {}
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
    return test_node_ids


def append_coverage_nodes(
    *,
    coverage_records: list[dict[str, Any]],
    test_node_ids: dict[str, str],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    p0a_dir: Path,
    source_ref: Callable[[Path], str],
) -> dict[str, str]:
    coverage_node_ids: dict[str, str] = {}
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
    return coverage_node_ids


def append_test_obligation_edges(
    *,
    diff_risk_test: dict[str, Any],
    risk_by_id: dict[str, dict[str, Any]],
    changed_entities_by_risk: dict[str, list[dict[str, Any]]],
    test_node_ids: dict[str, str],
    artifact_by_id: dict[str, dict[str, Any]],
    contract_by_id: dict[str, dict[str, Any]],
    mutation_by_id: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    unsupported_claims: list[dict[str, Any]],
    unsafe_artifacts: list[dict[str, Any]],
    excluded_artifacts: list[dict[str, Any]],
    p0a_dir: Path,
    diff_risk_path: Path,
    source_ref: Callable[[Path], str],
) -> list[dict[str, Any]]:
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
    return missing_executions
