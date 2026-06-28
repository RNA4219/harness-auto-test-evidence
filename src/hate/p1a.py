from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import __version__
from .p1a_io import TrustError, _read_json, _stable_hash, _stable_ref, _write_json
from .p1a_support import (
    AETE_DIMENSIONS,
    PROFILE_VERSION,
    RUBRIC_VERSION,
    SCHEMA_VERSION,
    _build_adapter_capability_manifest,
    _build_adapter_conformance_report,
    _build_adapter_registry,
    _build_artifact_resolver_map,
    _build_canonical_identity_index,
    _build_doctor_report,
    _build_reason_tree,
    _build_recommendations,
    _build_retry_aggregation,
    _build_summary,
    _score_confidence,
    _score_dimensions_with_signals,
)
from .profile import build_profile_report

def evaluate_trust(
    bundle_path: Path,
    report_path: Path,
    out_dir: Path,
    profile: str = "default",
    source_version: str | None = None,
) -> dict[str, Any]:
    """Generate P1a trust-hardening artifacts from a frozen P0b bundle."""
    if not bundle_path.exists():
        raise TrustError(f"QEG bundle not found: {bundle_path}", exit_code=2)
    if not report_path.exists():
        raise TrustError(f"QEG export report not found: {report_path}", exit_code=2)

    out_dir.mkdir(parents=True, exist_ok=True)
    version = source_version or __version__
    bundle = _read_json(bundle_path)
    report = _read_json(report_path)

    metadata = bundle.get("metadata", {})
    nodes = bundle.get("nodes", [])
    edges = bundle.get("edges", [])
    completeness = bundle.get("completeness", {})
    run_id = str(metadata.get("runId", report.get("run_id", "")))
    run_attempt = int(metadata.get("runAttempt", report.get("run_attempt", 1)))
    commit_sha = str(report.get("commit_sha", ""))
    created_at = str(metadata.get("createdAt", report.get("created_at", "")))
    profile_report = build_profile_report(profile, run_id, run_attempt, commit_sha, created_at)

    dimensions, reason_refs, dimension_signals = _score_dimensions_with_signals(bundle, report)
    weighted_score = round(sum(dimensions.values()) / (len(AETE_DIMENSIONS) * 5), 3)
    score_confidence = _score_confidence(completeness, report)

    aete_score = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "aete_score",
        "run_id": run_id,
        "run_attempt": run_attempt,
        "commit_sha": commit_sha,
        "source_tool": "harness-auto-test-evidence",
        "source_version": version,
        "rubric_version": RUBRIC_VERSION,
        "profile_version": profile_report["profile_version"],
        "profile": profile,
        "calibration_status": "uncalibrated",
        "score_confidence": score_confidence,
        "subject": {
            "subject_type": "run",
            "subject_id": f"run:{run_id}:{run_attempt}",
        },
        "dimensions": dimensions,
        "dimension_signals": dimension_signals,
        "weighted_score": weighted_score,
        "reason_refs": reason_refs,
        "source_refs": [
            _stable_ref(bundle_path),
            _stable_ref(report_path),
        ],
        "release_gate_override": False,
        "publish_gate_override": False,
    }
    aete_signal_report = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "aete_signal_report",
        "run_id": run_id,
        "run_attempt": run_attempt,
        "profile": profile,
        "rubric_version": RUBRIC_VERSION,
        "profile_version": profile_report["profile_version"],
        "dimensions": dimensions,
        "signals": dimension_signals,
        "reason_refs": reason_refs,
        "deterministic": True,
        "source_refs": ["qeg-bundle.json", "qeg-export-report.json", "profile-report.json"],
        "release_gate_override": False,
        "publish_gate_override": False,
    }

    resolver_map = _build_artifact_resolver_map(run_id, bundle)
    doctor_report = _build_doctor_report(run_id, run_attempt, bundle, report, resolver_map)
    adapter_registry = _build_adapter_registry()
    adapter_manifest = _build_adapter_capability_manifest()
    adapter_conformance = _build_adapter_conformance_report(run_id, adapter_manifest, doctor_report, resolver_map, adapter_registry)
    identity_index = _build_canonical_identity_index(run_id, bundle)
    retry_aggregation = _build_retry_aggregation(run_id, run_attempt, bundle)
    summary = _build_summary(aete_score, doctor_report)

    _write_json(out_dir / "aete-score.json", aete_score)
    _write_json(out_dir / "aete-signal-report.json", aete_signal_report)
    _write_json(out_dir / "profile-report.json", profile_report)
    _write_json(out_dir / "artifact-resolver-map.json", resolver_map)
    _write_json(out_dir / "doctor-report.json", doctor_report)
    _write_json(out_dir / "adapter-registry.json", adapter_registry)
    _write_json(out_dir / "adapter-capability-manifest.json", adapter_manifest)
    _write_json(out_dir / "adapter-conformance-report.json", adapter_conformance)
    _write_json(out_dir / "canonical-identity-index.json", identity_index)
    _write_json(out_dir / "retry-aggregation.json", retry_aggregation)
    (out_dir / "trust-summary.md").write_text(summary, encoding="utf-8")

    return {
        "trust_status": "partial" if doctor_report["findings"] else "success",
        "exit_code": 0,
        "generated": [
            "aete-score.json",
            "aete-signal-report.json",
            "profile-report.json",
            "artifact-resolver-map.json",
            "doctor-report.json",
            "adapter-registry.json",
            "adapter-capability-manifest.json",
            "adapter-conformance-report.json",
            "canonical-identity-index.json",
            "retry-aggregation.json",
            "trust-summary.md",
        ],
        "weighted_score": weighted_score,
        "score_confidence": score_confidence,
        "doctor_findings": len(doctor_report["findings"]),
        "publish_gate_override": False,
    }


def replay_trust(
    bundle_path: Path,
    report_path: Path,
    out_dir: Path,
    profile: str = "default",
) -> dict[str, Any]:
    """Replay trust evaluation and emit a deterministic recalculation report."""
    trust_result = evaluate_trust(
        bundle_path=bundle_path,
        report_path=report_path,
        out_dir=out_dir,
        profile=profile,
    )
    aete_score = _read_json(out_dir / "aete-score.json")
    aete_signal = _read_json(out_dir / "aete-signal-report.json")
    profile_report = _read_json(out_dir / "profile-report.json")
    resolver_map = _read_json(out_dir / "artifact-resolver-map.json")
    doctor_report = _read_json(out_dir / "doctor-report.json")
    conformance = _read_json(out_dir / "adapter-conformance-report.json")
    identity_index = _read_json(out_dir / "canonical-identity-index.json")
    retry_aggregation = _read_json(out_dir / "retry-aggregation.json")
    replay_payload = {
        "aete_score": aete_score,
        "aete_signal_report": aete_signal,
        "profile_report": profile_report,
        "resolver_summary": resolver_map.get("summary", {}),
        "doctor_summary": doctor_report.get("summary", {}),
        "conformance_summary": conformance.get("summary", {}),
        "identity_summary": identity_index.get("summary", {}),
        "retry_summary": retry_aggregation.get("summary", {}),
    }
    recalculation_hash = _stable_hash(replay_payload)
    replay_report = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "replay_report",
        "profile": profile,
        "bundle_ref": _stable_ref(bundle_path),
        "report_ref": _stable_ref(report_path),
        "recalculation_hash": recalculation_hash,
        "deterministic_inputs": {
            "aete_score": _stable_hash(aete_score),
            "aete_signal_report": _stable_hash(aete_signal),
            "profile_report": _stable_hash(profile_report),
            "artifact_resolver_map": _stable_hash(resolver_map),
            "doctor_report": _stable_hash(doctor_report),
            "adapter_conformance_report": _stable_hash(conformance),
            "canonical_identity_index": _stable_hash(identity_index),
            "retry_aggregation": _stable_hash(retry_aggregation),
        },
        "weighted_score": aete_score["weighted_score"],
        "doctor_findings": doctor_report["summary"]["finding_count"],
        "retry_aggregate_count": retry_aggregation["summary"]["aggregate_count"],
        "deterministic": True,
        "release_gate_override": False,
        "publish_gate_override": False,
    }
    _write_json(out_dir / "replay-report.json", replay_report)
    trust_result["generated"].append("replay-report.json")
    trust_result["recalculation_hash"] = recalculation_hash
    return trust_result


def compare_trust(
    base_dir: Path,
    head_dir: Path,
    out_dir: Path,
) -> dict[str, Any]:
    """Compare two P1a trust artifact directories."""
    base_aete = _read_json(base_dir / "aete-score.json")
    head_aete = _read_json(head_dir / "aete-score.json")
    base_doctor = _read_json(base_dir / "doctor-report.json")
    head_doctor = _read_json(head_dir / "doctor-report.json")
    base_retry = _read_json(base_dir / "retry-aggregation.json")
    head_retry = _read_json(head_dir / "retry-aggregation.json")
    base_profile = _read_json(base_dir / "profile-report.json")
    head_profile = _read_json(head_dir / "profile-report.json")
    base_resolver = _read_json(base_dir / "artifact-resolver-map.json")
    head_resolver = _read_json(head_dir / "artifact-resolver-map.json")
    base_identity = _read_json(base_dir / "canonical-identity-index.json")
    head_identity = _read_json(head_dir / "canonical-identity-index.json")
    base_signal = _read_json(base_dir / "aete-signal-report.json")
    head_signal = _read_json(head_dir / "aete-signal-report.json")

    out_dir.mkdir(parents=True, exist_ok=True)
    trust_delta = round(head_aete["weighted_score"] - base_aete["weighted_score"], 3)
    doctor_delta = head_doctor["summary"]["finding_count"] - base_doctor["summary"]["finding_count"]
    retry_delta = head_retry["summary"]["aggregate_count"] - base_retry["summary"]["aggregate_count"]
    resolver_unsafe_delta = head_resolver.get("summary", {}).get("unsafe_count", 0) - base_resolver.get("summary", {}).get("unsafe_count", 0)
    identity_duplicate_delta = int(head_identity.get("summary", {}).get("has_duplicates", False)) - int(base_identity.get("summary", {}).get("has_duplicates", False))
    dimension_delta = {
        name: head_aete["dimensions"].get(name, 0) - base_aete["dimensions"].get(name, 0)
        for name in AETE_DIMENSIONS
    }
    signal_delta = {
        name: _signal_score(head_signal, name) - _signal_score(base_signal, name)
        for name in AETE_DIMENSIONS
    }
    compare_report = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "compare_report",
        "base_ref": _stable_ref(base_dir),
        "head_ref": _stable_ref(head_dir),
        "trust_delta": trust_delta,
        "doctor_finding_delta": doctor_delta,
        "retry_aggregate_delta": retry_delta,
        "resolver_unsafe_delta": resolver_unsafe_delta,
        "identity_duplicate_delta": identity_duplicate_delta,
        "profile_hash_changed": base_profile.get("profile_hash") != head_profile.get("profile_hash"),
        "dimension_delta": dimension_delta,
        "signal_delta": signal_delta,
        "regression": trust_delta < 0 or doctor_delta > 0 or resolver_unsafe_delta > 0 or identity_duplicate_delta > 0,
        "release_gate_override": False,
        "publish_gate_override": False,
    }
    _write_json(out_dir / "compare-report.json", compare_report)
    return {
        "compare_status": "regression" if compare_report["regression"] else "stable",
        "exit_code": 0,
        "generated": ["compare-report.json"],
        "trust_delta": trust_delta,
        "doctor_finding_delta": doctor_delta,
        "resolver_unsafe_delta": resolver_unsafe_delta,
        "publish_gate_override": False,
    }


def _signal_score(signal_report: dict[str, Any], dimension: str) -> int:
    for signal in signal_report.get("signals", []):
        if signal.get("dimension") == dimension:
            return int(signal.get("score", 0))
    return 0


def doctor_trust(
    bundle_path: Path,
    report_path: Path,
    out_dir: Path,
) -> dict[str, Any]:
    """Run the P1a doctor and adapter conformance matrix."""
    bundle = _read_json(bundle_path)
    report = _read_json(report_path)
    metadata = bundle.get("metadata", {})
    run_id = str(metadata.get("runId", report.get("run_id", "")))
    run_attempt = int(metadata.get("runAttempt", report.get("run_attempt", 1)))
    commit_sha = str(report.get("commit_sha", ""))
    created_at = str(metadata.get("createdAt", report.get("created_at", "")))
    out_dir.mkdir(parents=True, exist_ok=True)

    profile_report = build_profile_report("default", run_id, run_attempt, commit_sha, created_at)
    resolver_map = _build_artifact_resolver_map(run_id, bundle)
    doctor_report = _build_doctor_report(run_id, run_attempt, bundle, report, resolver_map)
    adapter_registry = _build_adapter_registry()
    adapter_manifest = _build_adapter_capability_manifest()
    adapter_conformance = _build_adapter_conformance_report(run_id, adapter_manifest, doctor_report, resolver_map, adapter_registry)
    _write_json(out_dir / "profile-report.json", profile_report)
    _write_json(out_dir / "doctor-report.json", doctor_report)
    _write_json(out_dir / "adapter-registry.json", adapter_registry)
    _write_json(out_dir / "adapter-capability-manifest.json", adapter_manifest)
    _write_json(out_dir / "adapter-conformance-report.json", adapter_conformance)
    return {
        "doctor_status": "partial" if doctor_report["findings"] else "success",
        "exit_code": 0,
        "generated": [
            "doctor-report.json",
            "profile-report.json",
            "adapter-registry.json",
            "adapter-capability-manifest.json",
            "adapter-conformance-report.json",
        ],
        "doctor_findings": doctor_report["summary"]["finding_count"],
        "conformance_status": adapter_conformance["summary"]["overall_status"],
        "publish_gate_override": False,
    }


def explain_trust(
    bundle_path: Path,
    report_path: Path,
    out_dir: Path,
    mode: str = "why-soft-gap",
) -> dict[str, Any]:
    """Explain soft gaps, exclusions, or score changes with source-backed reasons."""
    if mode not in {"why-soft-gap", "why-excluded", "why-score-changed"}:
        raise TrustError(f"unsupported explain mode: {mode}", exit_code=1)
    bundle = _read_json(bundle_path)
    report = _read_json(report_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    reason_tree = _build_reason_tree(bundle, report, mode)
    explain_report = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "explain_report",
        "mode": mode,
        "bundle_ref": _stable_ref(bundle_path),
        "report_ref": _stable_ref(report_path),
        "reason_tree": reason_tree,
        "summary": {
            "reason_count": len(reason_tree),
            "traceability_complete": _tree_has_source_refs(reason_tree),
        },
        "source_refs": [_stable_ref(bundle_path), _stable_ref(report_path)],
        "release_gate_override": False,
        "publish_gate_override": False,
    }
    _write_json(out_dir / "explain-report.json", explain_report)
    return {
        "explain_status": "success",
        "exit_code": 0,
        "generated": ["explain-report.json"],
        "reason_count": len(reason_tree),
        "publish_gate_override": False,
    }


def recommend_trust(
    bundle_path: Path,
    report_path: Path,
    out_dir: Path,
    gap_id: str = "missing_execution",
) -> dict[str, Any]:
    """Recommend next evidence/test/manual actions for a visible trust gap."""
    bundle = _read_json(bundle_path)
    report = _read_json(report_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    recommendations = _build_recommendations(bundle, report, gap_id)
    recommendation_report = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "recommendation_report",
        "gap_id": gap_id,
        "bundle_ref": _stable_ref(bundle_path),
        "report_ref": _stable_ref(report_path),
        "recommendations": recommendations,
        "summary": {
            "recommendation_count": len(recommendations),
            "traceability_complete": all(item.get("source_refs") for item in recommendations),
            "manual_bridge_recommendation_count": sum(1 for item in recommendations if item.get("recommended_manual_layer")),
        },
        "source_refs": [_stable_ref(bundle_path), _stable_ref(report_path)],
        "release_gate_override": False,
        "publish_gate_override": False,
    }
    _write_json(out_dir / "recommendation-report.json", recommendation_report)
    return {
        "recommend_status": "success",
        "exit_code": 0,
        "generated": ["recommendation-report.json"],
        "recommendation_count": len(recommendations),
        "publish_gate_override": False,
    }


def _tree_has_source_refs(items: list[dict[str, Any]]) -> bool:
    for item in items:
        if not item.get("source_refs"):
            return False
        if not _tree_has_source_refs(item.get("children", [])):
            return False
    return True

