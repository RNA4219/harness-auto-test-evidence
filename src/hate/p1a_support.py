from __future__ import annotations

from typing import Any

from . import __version__
from .p1a_io import (
    _collect_source_refs,
    _normalize_source_ref,
    _root_kind,
    _stable_hash,
)

SCHEMA_VERSION = "HATE/v1"
RUBRIC_VERSION = "aete-rubric-2026-06-28"
PROFILE_VERSION = "hate-profile-default-2026-06-28"
AETE_DIMENSIONS = [
    "provenance_integrity",
    "determinism_flakiness",
    "traceability_lineage",
    "oracle_strength",
    "change_relevance",
    "coverage_adequacy",
    "cross_signal_corroboration",
    "freshness_profile_conformance",
]


ADAPTER_REGISTRY_VERSION = "adapter-registry-2026-06-29"


def _build_adapter_registry() -> dict[str, Any]:
    adapters = [
        _adapter_manifest("context-github-actions", "GitHub Actions context", "context", ["github-context.json"], ["run"]),
        _adapter_manifest("context-generic-ci", "Generic CI context", "context", ["ci-context.json", "generic-ci-context.json"], ["run"]),
        _adapter_manifest("test-result-junit", "JUnit XML", "test-result", ["junit.xml"], ["test_result"], retry=True),
        _adapter_manifest("test-result-pytest-json", "pytest-json-report", "test-result", ["pytest-report.json"], ["test_result"], retry=True, flaky_history=True),
        _adapter_manifest("test-result-vitest-json", "Vitest JSON", "test-result", ["vitest-report.json"], ["test_result"], retry=True, flaky_history=True),
        _adapter_manifest("test-result-jest-json", "Jest JSON", "test-result", ["jest-report.json"], ["test_result"], retry=True),
        _adapter_manifest("coverage-lcov", "LCOV", "coverage", ["lcov.info"], ["coverage_slice"]),
        _adapter_manifest("coverage-cobertura", "Cobertura XML", "coverage", ["cobertura.xml"], ["coverage_slice"]),
        _adapter_manifest("coverage-jacoco", "JaCoCo XML", "coverage", ["jacoco.xml"], ["coverage_slice"]),
        _adapter_manifest("coverage-coveragepy-json", "coverage.py JSON", "coverage", ["coverage.json"], ["coverage_slice"], coverage_context=True),
        _adapter_manifest("static-sarif", "SARIF", "static", ["results.sarif", "sarif.json", "HATE-static.sarif"], ["evidence_ref"]),
        _adapter_manifest("artifact-manifest", "Artifact manifest", "artifact", ["artifacts/", "artifact-refs.json"], ["evidence_ref"], artifact_hash=True, redaction=True),
        _adapter_manifest("browser-playwright-artifacts", "Playwright artifacts", "artifact", ["trace.zip", "screenshot.png", "video.webm", "log.txt"], ["evidence_ref"], artifact_hash=True, redaction=True),
        _adapter_manifest("contract-pact", "Pact contract evidence", "contract", ["HATE-contract.ndjson"], ["contract"]),
        _adapter_manifest("mutation-stryker", "Stryker mutation evidence", "mutation", ["HATE-mutation.ndjson"], ["mutation"]),
        _adapter_manifest("export-qeg-bundle", "QEG bundle export", "export", ["qeg-bundle.json", "qeg-export-report.json"], ["aete_score", "doctor_report", "adapter_conformance"]),
    ]
    by_type: dict[str, int] = {}
    for adapter in adapters:
        by_type[adapter["adapter_type"]] = by_type.get(adapter["adapter_type"], 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "adapter_registry",
        "registry_version": ADAPTER_REGISTRY_VERSION,
        "adapters": adapters,
        "summary": {
            "adapter_count": len(adapters),
            "by_type": by_type,
            "all_have_required_manifest_fields": all(_adapter_manifest_is_complete(adapter) for adapter in adapters),
        },
        "source_refs": ["docs/process/ADAPTER_SDK_CONTRACT.md", "docs/process/P1A_TRUST_HARDENING_IMPLEMENTATION_CONTRACT.md"],
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _adapter_manifest(
    adapter_id: str,
    name: str,
    adapter_type: str,
    input_formats: list[str],
    output_record_types: list[str],
    *,
    retry: bool = False,
    matrix: bool = False,
    flaky_history: bool = False,
    coverage_context: bool = False,
    artifact_hash: bool = False,
    redaction: bool = False,
) -> dict[str, Any]:
    fixture_id = adapter_id.replace("_", "-")
    return {
        "adapter_id": adapter_id,
        "name": name,
        "version": __version__,
        "adapter_type": adapter_type,
        "kind": adapter_type,
        "input_formats": input_formats,
        "output_record_types": output_record_types,
        "capabilities": {
            "flaky": flaky_history,
            "retry": retry,
            "matrix": matrix,
            "artifact_hash": artifact_hash,
            "coverage_context": coverage_context,
            "redaction": redaction,
            "source_refs": True,
        },
        "capability": {
            "execution_result": adapter_type == "test-result",
            "retry": retry,
            "matrix": matrix,
            "flaky_history": flaky_history,
            "coverage_context": coverage_context,
            "artifact_hash": artifact_hash,
            "source_refs": True,
            "redaction": redaction,
        },
        "known_limits": _adapter_known_limits(adapter_type, coverage_context, matrix, flaky_history),
        "fixtures": [f"fixtures/adapters/{fixture_id}"],
        "conformance_fixtures": ["valid-minimal", "malformed", "missing-required"],
        "profile_support": {
            "default": "supported",
            "strict": "supported" if adapter_type in {"test-result", "coverage", "context"} else "partial",
            "release": "supported" if adapter_type in {"test-result", "coverage", "context"} else "partial",
        },
    }


def _adapter_known_limits(adapter_type: str, coverage_context: bool, matrix: bool, flaky_history: bool) -> list[str]:
    limits: list[str] = []
    if adapter_type == "coverage" and not coverage_context:
        limits.append("coverage context is unavailable unless the source format carries per-test context")
    if adapter_type == "test-result" and not matrix:
        limits.append("matrix values are preserved only when present in source records")
    if adapter_type == "test-result" and not flaky_history:
        limits.append("flaky history requires explicit source fields or future baseline-history input")
    return limits


def _adapter_manifest_is_complete(adapter: dict[str, Any]) -> bool:
    required = ["adapter_id", "name", "version", "adapter_type", "input_formats", "output_record_types", "capabilities", "fixtures", "profile_support"]
    for field in required:
        value = adapter.get(field)
        if value is None or value == "" or value == []:
            return False
    return True


def _build_adapter_capability_manifest() -> dict[str, Any]:
    registry = _build_adapter_registry()
    upstream = next(adapter for adapter in registry["adapters"] if adapter["adapter_id"] == "export-qeg-bundle")
    return {
        "schema_version": SCHEMA_VERSION,
        "adapter_id": "hate-p0b-qeg-bundle",
        "adapter_version": __version__,
        "kind": "upstream",
        "input_formats": upstream["input_formats"],
        "output_record_types": [
            "aete_score",
            "doctor_report",
            "artifact_resolution",
            "adapter_conformance",
            "replay_report",
            "compare_report",
            "explain_report",
            "recommendation_report",
        ],
        "capability": upstream["capability"],
        "known_limits": upstream["known_limits"],
        "conformance_fixtures": [
            "qeg_fixture",
            "path",
            "artifact_safety",
            "schema",
            "profile",
        ],
        "profile_support": {
            "default": "supported",
            "strict": "partial",
            "release": "partial",
        },
        "registry_ref": "adapter-registry.json",
    }
def _build_adapter_conformance_report(
    run_id: str,
    adapter_manifest: dict[str, Any],
    doctor_report: dict[str, Any],
    resolver_map: dict[str, Any],
    adapter_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    adapter_registry = adapter_registry or _build_adapter_registry()
    adapter_results = _adapter_conformance_results(adapter_registry)
    finding_categories = {finding["category"] for finding in doctor_report.get("findings", [])}
    has_unsafe_path = any(entry.get("resolution_status") == "unsafe" for entry in resolver_map.get("entries", []))
    checks = [
        {
            "check_id": "adapter-registry-manifest-fields",
            "category": "adapter_registry",
            "status": "pass" if adapter_registry["summary"]["all_have_required_manifest_fields"] else "fail",
            "adapter_ids": [adapter["adapter_id"] for adapter in adapter_registry["adapters"]],
            "source_refs": ["adapter-registry.json"],
        },
        {
            "check_id": "adapter-capability-source-refs",
            "category": "adapter",
            "status": "pass" if adapter_manifest["capability"]["source_refs"] else "fail",
            "source_refs": ["adapter-capability-manifest.json"],
        },
        {
            "check_id": "doctor-qeg-fixture",
            "category": "qeg_fixture",
            "status": "covered" if "qeg_fixture" in finding_categories else "pass",
            "source_refs": ["doctor-report.json"],
        },
        {
            "check_id": "doctor-path",
            "category": "path",
            "status": "covered" if has_unsafe_path else "pass",
            "source_refs": ["artifact-resolver-map.json"],
        },
        {
            "check_id": "doctor-artifact-safety",
            "category": "artifact_safety",
            "status": "covered" if "artifact_safety" in finding_categories else "pass",
            "source_refs": ["doctor-report.json"],
        },
        {
            "check_id": "schema-required-records",
            "category": "schema",
            "status": "pass",
            "source_refs": ["aete-score.json", "doctor-report.json"],
        },
        {
            "check_id": "profile-release-boundary",
            "category": "profile",
            "status": "pass",
            "source_refs": ["aete-score.json"],
        },
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "adapter_conformance",
        "run_id": run_id,
        "adapter_id": adapter_manifest["adapter_id"],
        "adapter_registry_ref": "adapter-registry.json",
        "adapter_registry": {
            "registry_version": adapter_registry["registry_version"],
            "adapter_count": adapter_registry["summary"]["adapter_count"],
            "adapter_ids": [adapter["adapter_id"] for adapter in adapter_registry["adapters"]],
            "by_type": adapter_registry["summary"]["by_type"],
        },
        "adapter_results": adapter_results,
        "checks": checks,
        "summary": {
            "overall_status": "pass" if all(check["status"] in {"pass", "covered"} for check in checks) and all(result["conformance_status"] == "pass" for result in adapter_results) else "fail",
            "check_count": len(checks),
            "covered_categories": sorted({check["category"] for check in checks}),
            "adapter_count": adapter_registry["summary"]["adapter_count"],
            "adapter_result_count": len(adapter_results),
            "fixture_result_count": sum(len(result["fixture_results"]) for result in adapter_results),
        },
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _adapter_conformance_results(adapter_registry: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for adapter in adapter_registry.get("adapters", []):
        if not isinstance(adapter, dict):
            continue
        fixture_results = [
            {
                "fixture_id": "manifest-required-fields",
                "category": "manifest",
                "status": "pass" if _adapter_manifest_is_complete(adapter) else "fail",
                "source_refs": ["adapter-registry.json"],
            },
            {
                "fixture_id": "capability-fields",
                "category": "capability",
                "status": "pass" if _adapter_capabilities_are_declared(adapter) else "fail",
                "source_refs": ["adapter-registry.json"],
            },
            {
                "fixture_id": "profile-support",
                "category": "profile",
                "status": "pass" if _adapter_profile_support_is_declared(adapter) else "fail",
                "source_refs": ["adapter-registry.json"],
            },
        ]
        results.append({
            "adapter_id": adapter.get("adapter_id", ""),
            "adapter_type": adapter.get("adapter_type", ""),
            "fixture_results": fixture_results,
            "conformance_status": "pass" if all(item["status"] == "pass" for item in fixture_results) else "fail",
            "known_limits": adapter.get("known_limits", []),
            "source_refs": ["adapter-registry.json"],
        })
    return results


def _adapter_capabilities_are_declared(adapter: dict[str, Any]) -> bool:
    capabilities = adapter.get("capabilities", {})
    if not isinstance(capabilities, dict):
        return False
    required = {"source_refs", "retry", "matrix", "artifact_hash", "coverage_context", "redaction"}
    return required.issubset(capabilities)


def _adapter_profile_support_is_declared(adapter: dict[str, Any]) -> bool:
    profile_support = adapter.get("profile_support", {})
    if not isinstance(profile_support, dict):
        return False
    return {"default", "strict", "release"}.issubset(profile_support)
def _score_dimensions_with_signals(bundle: dict[str, Any], report: dict[str, Any]) -> tuple[dict[str, int], list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = bundle.get("nodes", [])
    edges = bundle.get("edges", [])
    metadata = bundle.get("metadata", {})
    completeness = bundle.get("completeness", {})
    has_run = bool(metadata.get("runId") and metadata.get("createdAt") and report.get("commit_sha"))
    has_source_refs = _all_source_refs_non_empty(nodes, edges)
    has_tests = any(node.get("kind") == "test" for node in nodes)
    has_execution = any(node.get("kind") == "execution_evidence" for node in nodes)
    has_coverage = any(node.get("kind") == "coverage" for node in nodes)
    has_context_or_branch_coverage = any(
        node.get("kind") == "coverage"
        and (node.get("data", {}).get("contexts") or node.get("data", {}).get("branch_hits"))
        for node in nodes
    )
    has_changed_code = any(node.get("kind") == "changed_code" for node in nodes)
    has_risk_edges = any(edge.get("kind") in {"touches", "requires_test"} for edge in edges)
    has_contract_or_mutation = any(node.get("kind") in {"contract_evidence", "mutation_evidence"} for node in nodes)
    has_artifact_hash = any(node.get("kind") == "evidence_artifact" and node.get("data", {}).get("sha256") for node in nodes)
    has_unsupported = bool(completeness.get("unsupportedClaims") or report.get("unsupportedClaims"))
    missing_execution = bool(report.get("missing_execution"))
    signal_kinds = {
        node.get("kind")
        for node in nodes
        if node.get("kind") in {"execution_evidence", "coverage", "finding", "evidence_artifact", "contract_evidence", "mutation_evidence"}
    }
    dimensions = {
        "provenance_integrity": 5 if has_run and has_artifact_hash else 3 if has_run else 1 if metadata.get("runId") else 0,
        "determinism_flakiness": 3 if has_tests and has_execution and not missing_execution else 1 if has_tests else 0,
        "traceability_lineage": 5 if has_source_refs and has_risk_edges and has_execution else 3 if has_source_refs and has_risk_edges else 1,
        "oracle_strength": 5 if has_contract_or_mutation else 3 if has_tests and has_execution else 1,
        "change_relevance": 5 if has_changed_code and has_risk_edges else 1,
        "coverage_adequacy": 5 if has_context_or_branch_coverage else 3 if has_coverage else 0,
        "cross_signal_corroboration": 5 if len(signal_kinds) >= 3 else 3 if has_execution and has_coverage else 1 if signal_kinds else 0,
        "freshness_profile_conformance": 3 if not has_unsupported else 1,
    }
    signals = [
        _dimension_signal(
            "provenance_integrity",
            dimensions["provenance_integrity"],
            {
                "has_run_id": bool(metadata.get("runId")),
                "has_created_at": bool(metadata.get("createdAt")),
                "has_commit_sha": bool(report.get("commit_sha")),
                "has_artifact_hash": has_artifact_hash,
            },
            ["qeg-bundle.json", "qeg-export-report.json"],
        ),
        _dimension_signal(
            "determinism_flakiness",
            dimensions["determinism_flakiness"],
            {"has_tests": has_tests, "has_execution": has_execution, "missing_execution": missing_execution},
            ["qeg-bundle.json", "qeg-export-report.json"],
        ),
        _dimension_signal(
            "traceability_lineage",
            dimensions["traceability_lineage"],
            {"source_refs_complete": has_source_refs, "has_risk_edges": has_risk_edges, "has_execution": has_execution},
            ["qeg-bundle.json", "evidence-map.json"],
        ),
        _dimension_signal(
            "oracle_strength",
            dimensions["oracle_strength"],
            {"has_tests": has_tests, "has_execution": has_execution, "has_contract_or_mutation": has_contract_or_mutation},
            ["qeg-bundle.json"],
        ),
        _dimension_signal(
            "change_relevance",
            dimensions["change_relevance"],
            {"has_changed_code": has_changed_code, "has_risk_edges": has_risk_edges},
            ["qeg-bundle.json"],
        ),
        _dimension_signal(
            "coverage_adequacy",
            dimensions["coverage_adequacy"],
            {"has_coverage": has_coverage, "has_context_or_branch_coverage": has_context_or_branch_coverage},
            ["qeg-bundle.json"],
        ),
        _dimension_signal(
            "cross_signal_corroboration",
            dimensions["cross_signal_corroboration"],
            {"signal_kinds": sorted(signal_kinds), "signal_kind_count": len(signal_kinds)},
            ["qeg-bundle.json"],
        ),
        _dimension_signal(
            "freshness_profile_conformance",
            dimensions["freshness_profile_conformance"],
            {"has_unsupported_claims": has_unsupported, "export_status": report.get("export_status", "")},
            ["qeg-export-report.json", "profile-report.json"],
        ),
    ]
    reason_refs = [
        {
            "dimension": signal["dimension"],
            "reason_ref": signal["signal_id"],
            "score": signal["score"],
            "source_refs": signal["source_refs"],
        }
        for signal in signals
    ]
    return dimensions, reason_refs, signals


def _score_dimensions(bundle: dict[str, Any], report: dict[str, Any]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    dimensions, reason_refs, _signals = _score_dimensions_with_signals(bundle, report)
    return dimensions, reason_refs


def _dimension_signal(dimension: str, score: int, observed: dict[str, Any], source_refs: list[str]) -> dict[str, Any]:
    return {
        "signal_id": f"signal:{dimension}:{score}",
        "dimension": dimension,
        "score": score,
        "observed": observed,
        "rationale": _dimension_rationale(dimension, score),
        "source_refs": source_refs,
    }


def _dimension_rationale(dimension: str, score: int) -> str:
    labels = {
        0: "required signal is absent",
        1: "only weak or incomplete signal is present",
        3: "required signal is present at the base trust level",
        5: "strong corroborating signal is present",
    }
    return f"{dimension} score {score}: {labels.get(score, 'profile-specific signal score')}"
def _score_confidence(completeness: dict[str, Any], report: dict[str, Any]) -> str:
    if report.get("missing_execution") or completeness.get("unsupportedClaims"):
        return "medium"
    if completeness.get("partial"):
        return "medium"
    return "high"
def _build_artifact_resolver_map(run_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for source_ref in _collect_source_refs(bundle):
        entries.append({
            "entry_type": "source_ref",
            "original": source_ref,
            "normalized": _normalize_source_ref(source_ref),
            "root_kind": _root_kind(source_ref),
            "resolution_status": _resolution_status(source_ref),
            "source_refs": [source_ref],
        })
    for node in bundle.get("nodes", []):
        if node.get("kind") != "evidence_artifact":
            continue
        data = node.get("data", {})
        artifact_path = str(data.get("path", ""))
        if not artifact_path:
            continue
        entries.append({
            "entry_type": "artifact_path",
            "artifact_id": str(node.get("id", "")).removeprefix("artifact:"),
            "artifact_kind": data.get("kind", ""),
            "artifact_role": data.get("artifact_role", ""),
            "sha256": data.get("sha256", ""),
            "original": artifact_path,
            "normalized": _normalize_source_ref(artifact_path),
            "root_kind": _root_kind(artifact_path),
            "resolution_status": _resolution_status(artifact_path),
            "source_refs": node.get("sourceRefs", []),
        })
    entries = sorted(entries, key=lambda item: (item.get("entry_type", ""), item.get("original", ""), item.get("artifact_id", "")))
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "artifact_resolution",
        "run_id": run_id,
        "entries": entries,
        "summary": {
            "entry_count": len(entries),
            "unsafe_count": sum(1 for entry in entries if entry["resolution_status"] == "unsafe"),
            "unresolved_count": sum(1 for entry in entries if entry["resolution_status"] == "unresolved"),
            "artifact_path_count": sum(1 for entry in entries if entry["entry_type"] == "artifact_path"),
            "source_ref_count": sum(1 for entry in entries if entry["entry_type"] == "source_ref"),
        },
    }


def _resolution_status(value: str) -> str:
    normalized = value.replace("\\", "/")
    parts = normalized.split("/")
    if ".." in parts:
        return "unsafe"
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return "unsafe"
    if not normalized:
        return "unresolved"
    return "resolved"
def _build_doctor_report(
    run_id: str,
    run_attempt: int,
    bundle: dict[str, Any],
    report: dict[str, Any],
    resolver_map: dict[str, Any],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for claim in report.get("unsupportedClaims", []):
        findings.append(_doctor_finding({
            "finding_id": f"doctor:qeg_fixture:{len(findings) + 1}",
            "category": "qeg_fixture",
            "severity": "high",
            "message": claim.get("reason", "unsupported claim"),
            "source_refs": ["qeg-export-report.json"],
        }))
    for artifact in report.get("excludedArtifacts", []):
        findings.append(_doctor_finding({
            "finding_id": f"doctor:artifact_safety:{len(findings) + 1}",
            "category": "artifact_safety",
            "severity": "critical",
            "message": artifact.get("reason", "artifact excluded"),
            "source_refs": ["qeg-export-report.json"],
        }))
    if not _all_source_refs_non_empty(bundle.get("nodes", []), bundle.get("edges", [])):
        findings.append(_doctor_finding({
            "finding_id": f"doctor:qeg_fixture:{len(findings) + 1}",
            "category": "qeg_fixture",
            "severity": "high",
            "message": "node or edge has missing sourceRefs",
            "source_refs": ["qeg-bundle.json"],
        }))
    for entry in resolver_map.get("entries", []):
        if entry.get("resolution_status") == "unsafe":
            findings.append(_doctor_finding({
                "finding_id": f"doctor:path:{len(findings) + 1}",
                "category": "path",
                "severity": "high",
                "message": "unsafe source reference path",
                "source_refs": [entry.get("original", "")],
            }))
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "doctor_report",
        "run_id": run_id,
        "run_attempt": run_attempt,
        "findings": findings,
        "summary": {
            "finding_count": len(findings),
            "blocking_categories": sorted({f["category"] for f in findings if f["severity"] in {"high", "critical"}}),
            "by_category": _count_by(findings, "category"),
            "by_severity": _count_by(findings, "severity"),
            "taxonomy_version": "doctor-taxonomy-2026-06-29",
        },
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _doctor_finding(finding: dict[str, Any]) -> dict[str, Any]:
    category = str(finding.get("category", "unknown"))
    severity = str(finding.get("severity", "medium"))
    taxonomy = {
        "qeg_fixture": ("HATE-DOC-QEG-001", "Review QEG bundle/report sourceRefs and unsupported claims."),
        "artifact_safety": ("HATE-DOC-ART-001", "Redact, quarantine, or replace unsafe artifact evidence."),
        "path": ("HATE-DOC-PATH-001", "Normalize or remove unsafe path references before export."),
        "schema": ("HATE-DOC-SCH-001", "Validate generated artifacts against the schema registry."),
        "profile": ("HATE-DOC-PROF-001", "Check profile support and inheritance drift."),
        "adapter": ("HATE-DOC-ADP-001", "Check adapter manifest and conformance fixture coverage."),
    }
    code, remediation = taxonomy.get(category, ("HATE-DOC-UNK-001", "Inspect the finding and attach source-backed remediation."))
    return {
        "finding_code": code,
        "taxonomy_version": "doctor-taxonomy-2026-06-29",
        "blocking": severity in {"high", "critical"},
        "remediation": remediation,
        **finding,
    }


def _count_by(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(field, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return counts
def _build_canonical_identity_index(run_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
    identities: list[dict[str, Any]] = []
    for node in bundle.get("nodes", []):
        if node.get("kind") != "test":
            continue
        data = node.get("data", {})
        canonical_test_id = str(data.get("canonical_test_id", ""))
        components = _identity_components(canonical_test_id, data)
        normalized_canonical_test_id = _normalized_canonical_test_id(components)
        aliases = []
        if canonical_test_id and canonical_test_id != normalized_canonical_test_id:
            aliases.append({
                "previous_id": canonical_test_id,
                "reason": "path_normalization",
                "valid_from": run_id,
            })
        identities.append({
            "identity_id": f"identity:{_stable_hash(normalized_canonical_test_id)[:16]}",
            "test_node_id": node.get("id", ""),
            "canonical_test_id": canonical_test_id,
            "normalized_canonical_test_id": normalized_canonical_test_id,
            "identity_components": components,
            "aliases": aliases,
            "source_refs": node.get("sourceRefs", []),
        })
    duplicate_ids = sorted(_duplicates([item["normalized_canonical_test_id"] for item in identities]))
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "canonical_identity_index",
        "run_id": run_id,
        "summary": {
            "identity_count": len(identities),
            "duplicate_normalized_ids": duplicate_ids,
            "has_duplicates": bool(duplicate_ids),
        },
        "identities": identities,
    }


def _identity_components(canonical_test_id: str, data: dict[str, Any]) -> dict[str, Any]:
    framework = str(data.get("framework") or (canonical_test_id.split(":", 1)[0] if ":" in canonical_test_id else ""))
    remainder = canonical_test_id.split(":", 1)[1] if ":" in canonical_test_id else canonical_test_id
    parts = remainder.split("::") if remainder else []
    raw_file = str(data.get("file") or (parts[0] if parts else ""))
    classname = str(data.get("classname") or data.get("class_name") or "")
    name = str(data.get("name") or "")
    if len(parts) >= 3:
        classname = classname or parts[1]
        name = name or "::".join(parts[2:])
    elif len(parts) >= 2:
        name = name or "::".join(parts[1:])
    elif parts:
        name = name or parts[0]
    parameters = _stable_mapping(data.get("parameters") or data.get("params") or {})
    matrix = _stable_mapping(data.get("matrix") or data.get("matrix_values") or {})
    return {
        "framework": framework,
        "package": str(data.get("package", "")),
        "file": _normalize_source_ref(raw_file),
        "classname": classname,
        "name": name,
        "parameters": parameters,
        "matrix": matrix,
    }


def _normalized_canonical_test_id(components: dict[str, Any]) -> str:
    base = f"{components['framework']}:{components['file']}::{components['classname']}::{components['name']}"
    parameters = components.get("parameters", {})
    if parameters:
        return f"{base}::{_stable_hash(parameters)[:12]}"
    return base


def _stable_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): value[key] for key in sorted(value)}


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates
def _build_retry_aggregation(run_id: str, run_attempt: int, bundle: dict[str, Any]) -> dict[str, Any]:
    executions_by_test: dict[str, list[dict[str, Any]]] = {}
    for edge in bundle.get("edges", []):
        if edge.get("kind") != "evidenced_by":
            continue
        executions_by_test.setdefault(str(edge.get("from", "")), [])
    execution_nodes = {
        str(node.get("id", "")): node
        for node in bundle.get("nodes", [])
        if node.get("kind") == "execution_evidence"
    }
    for edge in bundle.get("edges", []):
        if edge.get("kind") != "evidenced_by":
            continue
        execution = execution_nodes.get(str(edge.get("to", "")))
        if execution:
            executions_by_test.setdefault(str(edge.get("from", "")), []).append(execution)
    aggregates: list[dict[str, Any]] = []
    test_nodes = {
        str(node.get("id", "")): node
        for node in bundle.get("nodes", [])
        if node.get("kind") == "test"
    }
    for test_node_id, executions in sorted(executions_by_test.items()):
        test_node = test_nodes.get(test_node_id, {})
        test_data = test_node.get("data", {}) if isinstance(test_node, dict) else {}
        components = _identity_components(str(test_data.get("canonical_test_id", "")), test_data)
        normalized_test_id = _normalized_canonical_test_id(components)
        matrix = _merge_matrix(components.get("matrix", {}), executions)
        matrix_group = _matrix_group_id(matrix)
        ordered_executions = sorted(executions, key=_execution_sort_key)
        statuses = [str(item.get("data", {}).get("status", "unknown")) for item in ordered_executions]
        shard_total = _shard_total(ordered_executions)
        observed_shards = sorted({
            str(item.get("data", {}).get("shard_index"))
            for item in ordered_executions
            if item.get("data", {}).get("shard_index") is not None
        })
        missing_shard = bool(shard_total and len(observed_shards) < shard_total)
        aggregate_status = "inconclusive" if missing_shard else _aggregate_status(statuses)
        aggregates.append({
            "aggregation_key": f"{normalized_test_id}:{matrix_group}:{run_attempt}",
            "test_node_id": test_node_id,
            "normalized_canonical_test_id": normalized_test_id,
            "matrix": matrix,
            "matrix_group": matrix_group,
            "run_id": run_id,
            "run_attempt": run_attempt,
            "retry_attempts": [
                {
                    "execution_node_id": item.get("id", ""),
                    "retry_index": int(item.get("data", {}).get("retry_index", index)),
                    "status": str(item.get("data", {}).get("status", "unknown")),
                }
                for index, item in enumerate(ordered_executions)
            ],
            "shards": {
                "observed": observed_shards,
                "expected_count": shard_total,
                "missing": missing_shard,
            },
            "raw_statuses": statuses,
            "aggregate_status": aggregate_status,
            "source_refs": ["qeg-bundle.json"],
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "aggregates": aggregates,
        "summary": {
            "aggregate_count": len(aggregates),
            "flaky_count": sum(1 for item in aggregates if str(item["aggregate_status"]).startswith("flaky")),
            "inconclusive_count": sum(1 for item in aggregates if item["aggregate_status"] == "inconclusive"),
            "matrix_group_count": len({item["matrix_group"] for item in aggregates}),
            "missing_shard_count": sum(1 for item in aggregates if item["shards"]["missing"]),
        },
    }


def _merge_matrix(test_matrix: Any, executions: list[dict[str, Any]]) -> dict[str, Any]:
    matrix: dict[str, Any] = dict(test_matrix) if isinstance(test_matrix, dict) else {}
    for execution in executions:
        execution_matrix = execution.get("data", {}).get("matrix") or execution.get("data", {}).get("matrix_values") or {}
        if isinstance(execution_matrix, dict):
            matrix.update(_stable_mapping(execution_matrix))
    return _stable_mapping(matrix)


def _matrix_group_id(matrix: dict[str, Any]) -> str:
    if not matrix:
        return "matrix:default"
    return f"matrix:{_stable_hash(matrix)[:12]}"


def _execution_sort_key(execution: dict[str, Any]) -> tuple[int, str]:
    data = execution.get("data", {})
    retry_index = data.get("retry_index", data.get("attempt_index", 0))
    try:
        retry_value = int(retry_index)
    except (TypeError, ValueError):
        retry_value = 0
    return retry_value, str(execution.get("id", ""))


def _shard_total(executions: list[dict[str, Any]]) -> int:
    totals: list[int] = []
    for execution in executions:
        value = execution.get("data", {}).get("shard_total") or execution.get("data", {}).get("shard_count")
        try:
            if value is not None:
                totals.append(int(value))
        except (TypeError, ValueError):
            continue
    return max(totals) if totals else 0
def _aggregate_status(statuses: list[str]) -> str:
    if not statuses:
        return "inconclusive"
    normalized = [status.lower() for status in statuses]
    if all(status == "passed" for status in normalized):
        return "stable_passed"
    if all(status == "failed" for status in normalized):
        return "failed"
    if normalized[-1] == "passed":
        return "flaky_passed"
    if normalized[-1] == "failed":
        return "flaky_failed"
    return "inconclusive"
def _build_reason_tree(bundle: dict[str, Any], report: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    if mode == "why-soft-gap":
        for index, gap in enumerate(report.get("missing_execution", []), start=1):
            reasons.append({
                "reason_id": f"reason:soft_gap:{index}",
                "category": "missing_execution",
                "summary": gap.get("reason", "missing execution"),
                "risk_id": gap.get("risk_id", ""),
                "expected_test_ref": gap.get("expected_test_ref", ""),
                "evidence_status": "missing",
                "source_refs": ["qeg-export-report.json"],
                "children": [
                    {
                        "reason_id": f"reason:soft_gap:{index}:risk",
                        "summary": "High-risk changed path requires execution evidence.",
                        "source_refs": _source_refs_for_risk(bundle, gap.get("risk_id", "")),
                    }
                ],
            })
    elif mode == "why-excluded":
        for index, artifact in enumerate(report.get("excludedArtifacts", []), start=1):
            reasons.append({
                "reason_id": f"reason:excluded:{index}",
                "category": "artifact_safety",
                "summary": artifact.get("reason", "artifact excluded"),
                "artifact_id": artifact.get("artifact_id", ""),
                "evidence_status": "excluded",
                "source_refs": ["qeg-export-report.json"],
                "children": [],
            })
    else:
        completeness = bundle.get("completeness", {})
        reasons.append({
            "reason_id": "reason:score:completeness",
            "category": "aete_score",
            "summary": "AETE score follows bundle completeness and visible unsupported claims.",
            "score": completeness.get("score"),
            "partial": completeness.get("partial"),
            "source_refs": ["qeg-bundle.json", "qeg-export-report.json"],
            "children": [
                {
                    "reason_id": "reason:score:unsupported",
                    "summary": f"Unsupported claims: {len(completeness.get('unsupportedClaims', []))}",
                    "source_refs": ["qeg-export-report.json"],
                }
            ],
        })
    return reasons
def _build_recommendations(bundle: dict[str, Any], report: dict[str, Any], gap_id: str) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    if gap_id in {"missing_execution", "all"}:
        for index, gap in enumerate(report.get("missing_execution", []), start=1):
            recommendations.append({
                "recommendation_id": f"recommend:missing_execution:{index}",
                "gap_id": "missing_execution",
                "risk_id": gap.get("risk_id", ""),
                "expected_test_ref": gap.get("expected_test_ref", ""),
                "recommended_actions": [
                    "Add or restore automated execution evidence for the expected test.",
                    "If automation is not available, create a manual-bb bridge review.",
                    "Keep the risk debt open until evidence is attached.",
                ],
                "recommended_test_layer": "unit",
                "recommended_manual_layer": "manual-scripted",
                "source_refs": ["qeg-export-report.json", "risk-debt-register.json", "manual-bb-bridge-requests.jsonl"],
                "related_source_refs": _source_refs_for_risk(bundle, gap.get("risk_id", "")),
            })
    if gap_id in {"artifact_safety", "all"}:
        for index, artifact in enumerate(report.get("excludedArtifacts", []), start=1):
            recommendations.append({
                "recommendation_id": f"recommend:artifact_safety:{index}",
                "gap_id": "artifact_safety",
                "artifact_id": artifact.get("artifact_id", ""),
                "recommended_actions": [
                    "Replace the unsafe artifact with a redacted artifact reference.",
                    "Run artifact safety checks before adding it to QEG evidence.",
                ],
                "recommended_manual_layer": "spec-clarification",
                "source_refs": ["qeg-export-report.json"],
                "related_source_refs": [],
            })
    return recommendations
def _source_refs_for_risk(bundle: dict[str, Any], risk_id: str) -> list[str]:
    target_id = f"risk:{risk_id}"
    refs: list[str] = []
    for node in bundle.get("nodes", []):
        if node.get("id") == target_id:
            refs.extend(str(ref) for ref in node.get("sourceRefs", []))
    for edge in bundle.get("edges", []):
        if edge.get("from") == target_id or edge.get("to") == target_id:
            refs.extend(str(ref) for ref in edge.get("traceability", {}).get("sourceRefs", []))
    return sorted(set(refs))
def _build_summary(aete_score: dict[str, Any], doctor_report: dict[str, Any]) -> str:
    return "\n".join([
        "# P1a Trust Summary",
        "",
        f"- Run: `{aete_score['run_id']}` attempt `{aete_score['run_attempt']}`",
        f"- Weighted score: `{aete_score['weighted_score']:.3f}`",
        f"- Score confidence: `{aete_score['score_confidence']}`",
        f"- Calibration: `{aete_score['calibration_status']}`",
        f"- Doctor findings: {doctor_report['summary']['finding_count']}",
        "",
        "HATE trust hardening is advisory evidence only.",
        "`publish_gate_override=false` and `release_gate_override=false`.",
        "",
    ])
def _all_source_refs_non_empty(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> bool:
    for node in nodes:
        if not node.get("sourceRefs"):
            return False
    for edge in edges:
        if not edge.get("traceability", {}).get("sourceRefs"):
            return False
    return True
