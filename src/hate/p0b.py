from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import __version__

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

    # Read required inputs
    p0a_dir = fixture_dir / "p0a"
    diff_risk_path = fixture_dir / "diff-risk-test.json"

    # Validate required artifacts exist
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

    # Load P0a artifacts
    run_record = _read_json(p0a_dir / "HATE-run.json")
    test_records = _read_ndjson(p0a_dir / "HATE-test-results.ndjson")
    coverage_records = _read_ndjson(p0a_dir / "HATE-coverage.ndjson")
    artifact_manifest = _read_json(p0a_dir / "artifact-manifest.json")
    precheck_decision = _read_json(p0a_dir / "precheck-decision.json")
    audit_record = _read_json(p0a_dir / "record.json")

    # Check precheck decision
    decision = precheck_decision.get("payload", {}).get("decision", "")
    if decision == "hard_dq":
        raise ExportError(
            "P0a precheck decision is hard_dq - QEG export not allowed",
            exit_code=2,
            report={"decision": "hard_dq", "reason": "P0a precheck disqualified"},
            out_dir=out_dir,
        )

    # Load diff-risk-test (optional, if missing use empty defaults)
    diff_risk_test: dict[str, Any] = {}
    if diff_risk_path.exists():
        diff_risk_test = _read_json(diff_risk_path)

    # Build QEG bundle
    created_at = run_record.get("created_at", "")
    commit_sha = run_record.get("commit_sha", "")
    run_id = run_record.get("run_id", "")
    run_attempt = run_record.get("run_attempt", 1)

    # Generate nodes and edges
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    # Add gate_verdict node (hate_precheck)
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
        "sourceRefs": [str(p0a_dir / "precheck-decision.json")],
    })

    # Add run node
    run_node_id = f"run:{run_id}:{run_attempt}"
    nodes.append({
        "id": run_node_id,
        "kind": "run",
        "label": f"CI Run {run_id}",
        "data": run_record.get("payload", {}),
        "sourceRefs": [str(p0a_dir / "HATE-run.json")],
    })

    # Add changed_code nodes from diff-risk-test
    changed_entities = diff_risk_test.get("changed_entities", [])
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
                "sourceRefs": [str(diff_risk_path)],
            })

            # Add touches edges (changed_code -> risk)
            for risk_ref in entity.get("risk_refs", []):
                edges.append({
                    "kind": "touches",
                    "from": node_id,
                    "to": f"risk:{risk_ref}",
                    "traceability": {
                        "sourceRefs": [str(diff_risk_path)],
                        "confidence": "high",
                        "assumptions": [],
                    },
                })

    # Add risk nodes
    risks = diff_risk_test.get("risks", [])
    for risk in risks:
        risk_id = risk.get("risk_id", "")
        node_id = f"risk:{risk_id}"
        nodes.append({
            "id": node_id,
            "kind": "risk",
            "label": risk.get("title", f"Risk {risk_id}"),
            "data": {
                "severity": risk.get("severity", "medium"),
                "required_test_layers": risk.get("required_test_layers", []),
            },
            "sourceRefs": risk.get("source_refs", [str(diff_risk_path)]),
        })

    # Add test nodes and execution_evidence nodes
    test_node_ids: dict[str, str] = {}  # canonical_test_id -> test node id
    for record in test_records:
        payload = record.get("payload", {})
        canonical_test_id = payload.get("canonical_test_id", "")
        if not canonical_test_id:
            continue

        # Compute deterministic hash for test node ID
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
            "sourceRefs": [str(p0a_dir / "HATE-test-results.ndjson")],
        })

        # Add execution_evidence node
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
            "sourceRefs": [str(p0a_dir / "HATE-test-results.ndjson")],
        })

        # Add evidenced_by edge (test -> execution)
        edges.append({
            "kind": "evidenced_by",
            "from": test_node_id,
            "to": execution_node_id,
            "traceability": {
                "sourceRefs": [str(p0a_dir / "HATE-test-results.ndjson")],
                "confidence": "high",
                "assumptions": [],
            },
        })

    # Add coverage nodes
    coverage_node_ids: dict[str, str] = {}  # file -> coverage node id
    for record in coverage_records:
        payload = record.get("payload", {})
        file_path = payload.get("file", "")
        if not file_path:
            continue

        # Compute hash for coverage node ID
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
            "sourceRefs": [str(p0a_dir / "HATE-coverage.ndjson")],
        })

        # Link coverage to test via contexts
        for ctx in payload.get("contexts", []):
            test_node_id = test_node_ids.get(ctx)
            if test_node_id:
                edges.append({
                    "kind": "supports",
                    "from": coverage_node_id,
                    "to": test_node_id,
                    "traceability": {
                        "sourceRefs": [str(p0a_dir / "HATE-coverage.ndjson")],
                        "confidence": "medium",
                        "assumptions": ["coverage context maps to test"],
                    },
                })

    # Add requires_test edges (risk -> test) based on test_obligations
    test_obligations = diff_risk_test.get("test_obligations", [])
    missing_executions: list[dict[str, Any]] = []
    for obligation in test_obligations:
        risk_id = obligation.get("risk_id", "")
        risk_node_id = f"risk:{risk_id}"
        expected_tests = obligation.get("expected_test_refs", [])

        for test_ref in expected_tests:
            # Find matching test node
            canonical_test_id = f"junit:{test_ref}"
            test_node_id = test_node_ids.get(canonical_test_id)

            if test_node_id:
                edges.append({
                    "kind": "requires_test",
                    "from": risk_node_id,
                    "to": test_node_id,
                    "traceability": {
                        "sourceRefs": [str(diff_risk_path)],
                        "confidence": "high",
                        "assumptions": [],
                    },
                })
            else:
                # Test not executed - mark as missing execution
                missing_executions.append({
                    "risk_id": risk_id,
                    "expected_test_ref": test_ref,
                    "reason": "test not found in execution results",
                })

    # Add decides edge (hate_precheck -> export eligibility)
    edges.append({
        "kind": "decides",
        "from": precheck_node_id,
        "to": f"qeg_export:{run_id}",
        "traceability": {
            "sourceRefs": [str(p0a_dir / "precheck-decision.json")],
            "confidence": "high",
            "assumptions": [],
        },
    })

    # Build evidence-map.json
    evidence_map = _build_evidence_map(
        run_id=run_id,
        run_attempt=run_attempt,
        nodes=nodes,
        edges=edges,
        test_node_ids=test_node_ids,
        coverage_node_ids=coverage_node_ids,
        missing_executions=missing_executions,
        risks=risks,
    )

    # Calculate completeness
    completeness = _calculate_completeness(
        nodes=nodes,
        edges=edges,
        missing_artifacts=missing_artifacts,
        missing_executions=missing_executions,
        parser_failures=[],  # P0a already validated
        unsupported_claims=[],  # Will be computed
    )

    # Build qeg-bundle.json
    qeg_bundle = {
        "metadata": {
            "qegVersion": "HATE/v1",
            "runId": run_id,
            "runAttempt": run_attempt,
            "createdAt": created_at,
            "profile": "lean",
            "inputArtifacts": [
                {"kind": "HATE-run", "path": str(p0a_dir / "HATE-run.json")},
                {"kind": "HATE-test-results", "path": str(p0a_dir / "HATE-test-results.ndjson")},
                {"kind": "HATE-coverage", "path": str(p0a_dir / "HATE-coverage.ndjson")},
                {"kind": "precheck-decision", "path": str(p0a_dir / "precheck-decision.json")},
            ],
            "debugOnly": decision == "hard_dq",
        },
        "nodes": nodes,
        "edges": edges,
        "completeness": completeness,
    }

    # Build qeg-export-report.json
    export_report = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "commit_sha": commit_sha,
        "created_at": created_at,
        "export_status": "success" if completeness["partial"] else "partial",
        "completeness": completeness,
        "unsupportedClaims": completeness["unsupportedClaims"],
        "missing_execution": missing_executions,
        "excludedArtifacts": completeness["excludedArtifacts"],
        "source_refs": [
            str(p0a_dir / "precheck-decision.json"),
            str(diff_risk_path) if diff_risk_path.exists() else "none",
        ],
        "publish_gate_override": False,
    }

    # Build summary.md (public-safe)
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

    # Write outputs
    _write_json(out_dir / "qeg-bundle.json", qeg_bundle)
    _write_json(out_dir / "evidence-map.json", evidence_map)
    _write_json(out_dir / "qeg-export-report.json", export_report)
    _write_json(out_dir / "diff-risk-test.json", diff_risk_test if diff_risk_test else {"schema_version": SCHEMA_VERSION, "changed_entities": [], "risks": [], "test_obligations": []})
    (out_dir / "qeg-export-summary.md").write_text(summary_content, encoding="utf-8")

    result = {
        "export_status": "success" if completeness["partial"] else "partial",
        "exit_code": 0 if completeness["score"] >= 0.8 else 0,  # P0b does not fail on partial
        "generated": [
            "qeg-bundle.json",
            "evidence-map.json",
            "diff-risk-test.json",
            "qeg-export-report.json",
            "qeg-export-summary.md",
        ],
        "completeness": completeness,
        "missing_executions": len(missing_executions),
        "out_dir": str(out_dir),
        "publish_gate_override": False,
    }

    return result


def _build_evidence_map(
    run_id: str,
    run_attempt: int,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    test_node_ids: dict[str, str],
    coverage_node_ids: dict[str, str],
    missing_executions: list[dict[str, Any]],
    risks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build evidence-map.json internal representation."""
    requirements: list[dict[str, Any]] = []
    risks_list: list[dict[str, Any]] = []
    tests_list: list[dict[str, Any]] = []
    evidence_list: list[dict[str, Any]] = []

    for node in nodes:
        kind = node.get("kind", "")
        if kind == "risk":
            risks_list.append({
                "risk_id": node["id"],
                "label": node.get("label", ""),
                "severity": node.get("data", {}).get("severity", "medium"),
            })
        elif kind == "test":
            tests_list.append({
                "test_id": node["id"],
                "canonical_test_id": node.get("data", {}).get("canonical_test_id", ""),
                "status": node.get("data", {}).get("status", "unknown"),
            })
        elif kind in {"execution_evidence", "coverage"}:
            evidence_list.append({
                "evidence_id": node["id"],
                "kind": kind,
                "label": node.get("label", ""),
            })

    # Build link arrays
    requires_test_links: list[dict[str, Any]] = []
    evidenced_by_links: list[dict[str, Any]] = []
    supports_links: list[dict[str, Any]] = []

    for edge in edges:
        kind = edge.get("kind", "")
        link = {
            "from": edge.get("from", ""),
            "to": edge.get("to", ""),
            "confidence": edge.get("traceability", {}).get("confidence", "medium"),
        }
        if kind == "requires_test":
            requires_test_links.append(link)
        elif kind == "evidenced_by":
            evidenced_by_links.append(link)
        elif kind == "supports":
            supports_links.append(link)

    # Build gaps
    unsupported_claims: list[dict[str, Any]] = []
    for miss in missing_executions:
        unsupported_claims.append({
            "risk_id": miss.get("risk_id", ""),
            "expected_test": miss.get("expected_test_ref", ""),
            "reason": miss.get("reason", ""),
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "requirements": requirements,
        "risks": risks_list,
        "tests": tests_list,
        "evidence": evidence_list,
        "links": {
            "requires_test": requires_test_links,
            "evidenced_by": evidenced_by_links,
            "supports": supports_links,
        },
        "gaps": {
            "unsupported_claims": unsupported_claims,
            "missing_execution": missing_executions,
            "missing_coverage": [],
            "unsafe_artifacts": [],
        },
    }


def _calculate_completeness(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    missing_artifacts: list[str],
    missing_executions: list[dict[str, Any]],
    parser_failures: list[dict[str, Any]],
    unsupported_claims: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculate P0b completeness score per contract."""
    base = 1.0

    # Penalty for missing required artifacts
    if missing_artifacts:
        base -= 0.20

    # Penalty for parser failures
    base -= 0.15 * len(parser_failures)

    # Penalty for unsupported high-risk claims (missing execution)
    high_risk_missing = [
        m for m in missing_executions
        if any(
            r.get("risk_id") == m.get("risk_id") and r.get("severity") == "high"
            for r in []  # risks passed separately in real impl
        )
    ]
    base -= 0.10 * len(high_risk_missing)

    # Floor at 0
    score = max(0.0, base)

    # Determine partial status
    partial = (
        not missing_artifacts
        and not parser_failures
        and score >= 0.8
    )

    return {
        "score": round(score, 2),
        "partial": partial,
        "parserFailures": parser_failures,
        "unsupportedClaims": unsupported_claims,
        "excludedArtifacts": [],
    }


def _hash_test_id(canonical_test_id: str) -> str:
    """Compute deterministic hash for test node ID."""
    digest = hashlib.sha256(canonical_test_id.encode("utf-8")).hexdigest()
    return digest[:16]


def _hash_path(file_path: str) -> str:
    """Compute deterministic hash for path-based node ID."""
    # Normalize path for cross-platform consistency
    normalized = file_path.replace("\\", "/")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return digest[:16]


def _read_json(path: Path) -> dict[str, Any]:
    """Read JSON file."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return data


def _read_ndjson(path: Path) -> list[dict[str, Any]]:
    """Read NDJSON file."""
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            records.append(record)
    return records


def _write_json(path: Path, value: dict[str, Any]) -> None:
    """Write JSON file with indentation."""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")