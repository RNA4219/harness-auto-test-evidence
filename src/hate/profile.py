from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

from .p0a_io import _dq


PROFILE_VERSION = "hate-profile-inheritance-2026-06-29"


PROFILES: dict[str, dict[str, Any]] = {
    "default": {
        "inherits": None,
        "rules": {
            "require_tests": False,
            "require_coverage": False,
            "unsafe_artifact_policy": "quarantine",
        },
    },
    "strict": {
        "inherits": "default",
        "rules": {
            "require_tests": True,
            "require_coverage": True,
            "unsafe_artifact_policy": "soft_gap",
        },
    },
    "release": {
        "inherits": "strict",
        "rules": {
            "require_tests": True,
            "require_coverage": True,
            "unsafe_artifact_policy": "hard_dq",
        },
    },
    "experimental": {
        "inherits": "default",
        "rules": {
            "require_tests": False,
            "require_coverage": False,
            "unsafe_artifact_policy": "observe",
        },
    },
}


PROFILE_POLICIES: dict[str, dict[str, str]] = {
    "default": {
        "dq_policy": "p0a_hard_dq_only",
        "soft_gap_policy": "p1a_p1b_gaps_visible",
        "aete_policy": "uncalibrated_allowed",
        "manual_policy": "high_risk_gap_recommended",
        "export_policy": "qeg_partial_allowed",
    },
    "strict": {
        "dq_policy": "high_risk_missing_execution_and_unsafe_required_artifact_hard",
        "soft_gap_policy": "weak_oracle_and_missing_context_conditional",
        "aete_policy": "medium_confidence_recommended",
        "manual_policy": "manual_supplement_required",
        "export_policy": "qeg_partial_allowed_with_warning",
    },
    "release": {
        "dq_policy": "strict_plus_unresolved_high_critical_static_and_open_manual_required_hard",
        "soft_gap_policy": "uncalibrated_score_conditional",
        "aete_policy": "calibration_status_explicit_required",
        "manual_policy": "unresolved_manual_request_blocks_eligibility",
        "export_policy": "qeg_export_only_without_hard_dq",
    },
    "experimental": {
        "dq_policy": "required_input_failures_only",
        "soft_gap_policy": "adapter_development_gaps_softened",
        "aete_policy": "reference_score_only",
        "manual_policy": "manual_supplement_recommendation",
        "export_policy": "debug_non_release_export",
    },
}


def resolve_profile(profile_name: str) -> dict[str, Any]:
    if profile_name not in PROFILES:
        raise ValueError(f"unknown profile: {profile_name}")

    chain: list[str] = []
    current: str | None = profile_name
    while current:
        chain.append(current)
        inherited = PROFILES[current].get("inherits")
        current = str(inherited) if inherited else None

    rules: dict[str, Any] = {}
    for name in reversed(chain):
        rules.update(PROFILES[name].get("rules", {}))

    return {
        "profile": profile_name,
        "inherits": list(reversed(chain)),
        "rules": rules,
        "policies": deepcopy(PROFILE_POLICIES[profile_name]),
    }


def build_profile_report(
    profile_name: str,
    run_id: str = "",
    run_attempt: int = 1,
    commit_sha: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build a machine-readable profile inheritance and drift report."""
    profile = resolve_profile(profile_name)
    chain = profile["inherits"]
    rule_sources: dict[str, str] = {}
    rule_diffs: list[dict[str, Any]] = []
    effective_rules: dict[str, Any] = {}
    for name in chain:
        declared_rules = deepcopy(PROFILES[name].get("rules", {}))
        added: dict[str, Any] = {}
        overridden: dict[str, dict[str, Any]] = {}
        for rule_name, value in declared_rules.items():
            if rule_name in effective_rules and effective_rules[rule_name] != value:
                overridden[rule_name] = {
                    "from": effective_rules[rule_name],
                    "to": value,
                    "previous_source": rule_sources.get(rule_name, ""),
                }
            elif rule_name not in effective_rules:
                added[rule_name] = value
            effective_rules[rule_name] = value
            rule_sources[rule_name] = name
        rule_diffs.append({
            "profile": name,
            "inherits": PROFILES[name].get("inherits"),
            "declared_rules": declared_rules,
            "added": added,
            "overridden": overridden,
            "effective_rules_after": deepcopy(effective_rules),
        })
    inheritance_graph = [
        {"profile": name, "inherits": PROFILES[name].get("inherits")}
        for name in PROFILES
    ]
    effective_policies = deepcopy(PROFILE_POLICIES[profile_name])
    drift_checks = _profile_drift_checks(profile_name, chain, effective_rules, effective_policies)
    hash_payload = {
        "profile": profile_name,
        "chain": chain,
        "rules": effective_rules,
        "policies": effective_policies,
        "rule_sources": rule_sources,
        "profile_version": PROFILE_VERSION,
    }
    profile_hash = hashlib.sha256(json.dumps(hash_payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": "HATE/v1",
        "record_type": "profile_report",
        "profile_version": PROFILE_VERSION,
        "run_id": str(run_id),
        "run_attempt": int(run_attempt),
        "commit_sha": str(commit_sha),
        "created_at": created_at,
        "profile": profile_name,
        "inherits": chain,
        "effective_chain": chain,
        "inheritance_graph": inheritance_graph,
        "rules": deepcopy(effective_rules),
        "effective_rules": deepcopy(effective_rules),
        "effective_policies": effective_policies,
        "policy_table": deepcopy(PROFILE_POLICIES),
        "rule_sources": rule_sources,
        "rule_diffs": rule_diffs,
        "drift_checks": drift_checks,
        "profile_hash": profile_hash,
        "qeg_gate_policy": False,
        "release_gate_override": False,
        "publish_gate_override": False,
        "note": "HATE profile controls evidence eligibility and AETE interpretation only; it is not QEG release Gate policy.",
    }


def _profile_drift_checks(
    profile_name: str,
    chain: list[str],
    rules: dict[str, Any],
    policies: dict[str, str],
) -> list[dict[str, Any]]:
    expected_chain = {
        "default": ["default"],
        "strict": ["default", "strict"],
        "release": ["default", "strict", "release"],
        "experimental": ["default", "experimental"],
    }
    checks = [
        {
            "check_id": "profile-chain-known",
            "status": "pass" if chain == expected_chain.get(profile_name, chain) else "fail",
            "expected": expected_chain.get(profile_name, chain),
            "actual": chain,
        },
        {
            "check_id": "effective-rules-complete",
            "status": "pass" if {"require_tests", "require_coverage", "unsafe_artifact_policy"}.issubset(rules) else "fail",
            "required_rules": ["require_tests", "require_coverage", "unsafe_artifact_policy"],
        },
        {
            "check_id": "effective-policies-complete",
            "status": "pass" if {
                "dq_policy",
                "soft_gap_policy",
                "aete_policy",
                "manual_policy",
                "export_policy",
            }.issubset(policies) else "fail",
            "required_policies": [
                "dq_policy",
                "soft_gap_policy",
                "aete_policy",
                "manual_policy",
                "export_policy",
            ],
        },
        {
            "check_id": "qeg-gate-boundary",
            "status": "pass",
            "message": "profile inheritance does not grant release approval or QEG Gate override",
        },
    ]
    if profile_name == "release":
        checks.append({
            "check_id": "release-extends-strict",
            "status": "pass" if chain[-2:] == ["strict", "release"] else "fail",
            "expected_suffix": ["strict", "release"],
            "actual": chain,
        })
    return checks


def evaluate_profile(
    profile_name: str,
    run_id: str,
    run_attempt: int,
    commit_sha: str,
    created_at: str,
    test_records: list[dict[str, Any]],
    coverage_records: list[dict[str, Any]],
    artifact_manifest: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, Any]]]:
    profile = resolve_profile(profile_name)
    rules = profile["rules"]
    hard_dq_hits: list[dict[str, str]] = []
    soft_gaps: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    def add_check(check_id: str, status: str, message: str) -> None:
        checks.append({"check_id": check_id, "status": status, "message": message})

    if rules.get("require_tests") and not test_records:
        hard_dq_hits.append(_dq("HATE-DQ-016", "profile requires test execution evidence", "profile-report.json"))
        add_check("require_tests", "fail", "profile requires at least one test_result record")
    else:
        add_check("require_tests", "pass", "test evidence requirement satisfied or not required")

    if rules.get("require_coverage") and not coverage_records:
        hard_dq_hits.append(_dq("HATE-DQ-017", "profile requires coverage evidence", "profile-report.json"))
        add_check("require_coverage", "fail", "profile requires at least one coverage_slice record")
    else:
        add_check("require_coverage", "pass", "coverage requirement satisfied or not required")

    unsafe_artifacts = [
        artifact for artifact in artifact_manifest.get("artifacts", [])
        if artifact.get("safe_for_summary") is False
    ]
    artifact_policy = str(rules.get("unsafe_artifact_policy", "quarantine"))
    if unsafe_artifacts and artifact_policy == "hard_dq":
        hard_dq_hits.append(_dq("HATE-DQ-018", "release profile rejects unsafe artifacts", "artifact-manifest.json"))
        add_check("unsafe_artifact_policy", "fail", "unsafe artifacts are not allowed in release profile")
    elif unsafe_artifacts and artifact_policy == "soft_gap":
        soft_gaps.append({
            "gap_id": "unsafe_artifact_profile_gap",
            "profile": profile_name,
            "artifact_ids": [artifact.get("artifact_id", "") for artifact in unsafe_artifacts],
            "message": "strict profile keeps unsafe artifact quarantine visible as a soft gap",
        })
        add_check("unsafe_artifact_policy", "warn", "unsafe artifacts are quarantined and visible")
    else:
        add_check("unsafe_artifact_policy", "pass", "unsafe artifact policy satisfied")

    report = {
        **build_profile_report(profile_name, run_id, run_attempt, commit_sha, created_at),
        "checks": checks,
        "decision_impact": {
            "hard_dq_codes": [hit["code"] for hit in hard_dq_hits],
            "soft_gap_count": len(soft_gaps),
        },
    }
    return report, hard_dq_hits, soft_gaps
