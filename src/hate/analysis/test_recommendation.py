"""Test recommendation engine evaluation for HATE-GAP-050."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TestRecommendationFinding:
    code: str
    severity: str
    message: str
    sourceRef: str
    readiness_effect: str = "hold"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRef": self.sourceRef,
            "readiness_effect": self.readiness_effect,
        }


def evaluate_test_recommendation_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = build_test_recommendation_report(
        input_data,
        report_id=str(payload.get("fixture_id") or "test-recommendation-fixture"),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def build_test_recommendation_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "test-recommendation-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = list(source_refs or input_data.get("sourceRefs") or ["test-recommendation"])
    rec_config = _normalize_recommendation_config(input_data.get("recommendation_config", input_data))
    diagnostics = _derive_diagnostics(rec_config)
    findings = _findings_for(rec_config, diagnostics, source_refs[0])
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": "test-recommendation-report",
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        "recommendation_config": rec_config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "recommendation_count": len(rec_config["recommendations"]),
            "required_oracle_count": len(rec_config["required_oracles"]),
            "verification_command_count": len(rec_config["verification_commands"]),
            "signal_count": len(rec_config["signals"]),
            "derived_recommendation_count": len(diagnostics["derived_recommendations"]),
            "missing_command_count": len(diagnostics["recommendations_missing_command"]),
            "missing_oracle_count": len(diagnostics["recommendations_missing_oracle"]),
            "confidence": rec_config["confidence"],
            "finding_count": len(findings),
        },
        "derived_recommendations": diagnostics["derived_recommendations"],
        "test_recommendation_diagnostics": diagnostics,
        "analysis_scope": rec_config["analysis_scope"],
        "input_refs": rec_config["input_refs"],
        "confidence": rec_config["confidence"],
        "limits": rec_config["limits"],
        "sourceRefs": sorted(set(source_refs)),
    }


def _normalize_recommendation_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config or {})
    recommendations = [
        _normalize_recommendation(rec)
        for rec in config.get("recommendations", [])
        if isinstance(rec, dict)
    ]
    required_oracles = [
        _normalize_oracle(oracle)
        for oracle in config.get("required_oracles", [])
        if isinstance(oracle, dict)
    ]
    verification_commands = [
        _normalize_command(cmd)
        for cmd in config.get("verification_commands", [])
        if isinstance(cmd, dict)
    ]
    signals = [
        _normalize_signal(signal)
        for signal in config.get("signals", [])
        if isinstance(signal, dict)
    ]
    return {
        "recommendations": recommendations,
        "required_oracles": required_oracles,
        "verification_commands": verification_commands,
        "signals": signals,
        "analysis_scope": str(config.get("analysis_scope", "") or ""),
        "input_refs": [str(ref) for ref in config.get("input_refs", []) if str(ref)],
        "confidence": float(config.get("confidence", 0.0) or 0.0),
        "limits": _normalize_limits(config.get("limits", {})),
        "actionable_taxonomy_used": bool(config.get("actionable_taxonomy_used", True)),
        "oracle_validation_enabled": bool(config.get("oracle_validation_enabled", True)),
        "command_verification_enabled": bool(config.get("command_verification_enabled", True)),
    }


def _normalize_recommendation(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "recommendation_id": str(rec.get("recommendation_id", rec.get("target", "")) or ""),
        "action": str(rec.get("action", "") or ""),
        "target": str(rec.get("target", "") or ""),
        "risk_id": str(rec.get("risk_id", "") or ""),
        "required_oracle_id": str(rec.get("required_oracle_id", "") or ""),
        "confidence": float(rec.get("confidence", 0.0) or 0.0),
        "sourceRef": str(rec.get("sourceRef", "") or ""),
        "rationale": str(rec.get("rationale", "") or ""),
        "actionable": bool(rec.get("actionable", True)),
    }


def _normalize_oracle(oracle: dict[str, Any]) -> dict[str, Any]:
    return {
        "oracle_id": str(oracle.get("oracle_id", "") or ""),
        "risk_id": str(oracle.get("risk_id", "") or ""),
        "confidence": float(oracle.get("confidence", 0.0) or 0.0),
        "sourceRef": str(oracle.get("sourceRef", "") or ""),
        "rationale": str(oracle.get("rationale", "") or ""),
        "verified": bool(oracle.get("verified", True)),
    }


def _normalize_command(cmd: dict[str, Any]) -> dict[str, Any]:
    return {
        "command_id": str(cmd.get("command_id", "") or ""),
        "recommendation_id": str(cmd.get("recommendation_id", "") or ""),
        "confidence": float(cmd.get("confidence", 0.0) or 0.0),
        "sourceRef": str(cmd.get("sourceRef", "") or ""),
        "rationale": str(cmd.get("rationale", "") or ""),
        "verified": bool(cmd.get("verified", True)),
    }


def _normalize_signal(signal: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal_id": str(signal.get("signal_id", "") or ""),
        "signal_type": str(signal.get("signal_type", "") or ""),
        "risk_id": str(signal.get("risk_id", "") or ""),
        "test_id": str(signal.get("test_id", "") or ""),
        "requirement_id": str(signal.get("requirement_id", "") or ""),
        "severity": str(signal.get("severity", "") or ""),
        "readiness_effect": str(signal.get("readiness_effect", "") or ""),
        "sourceRef": str(signal.get("sourceRef", "") or ""),
    }


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_recommendations": int(limits.get("max_recommendations", 100) or 100),
        "max_oracles": int(limits.get("max_oracles", 50) or 50),
        "max_commands": int(limits.get("max_commands", 100) or 100),
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
    }


def _derive_diagnostics(config: dict[str, Any]) -> dict[str, Any]:
    derived = [_recommendation_from_signal(signal) for signal in config["signals"]]
    derived = [item for item in derived if item]
    recommendation_ids = {rec["recommendation_id"] for rec in config["recommendations"] if rec["recommendation_id"]}
    command_rec_ids = {cmd["recommendation_id"] for cmd in config["verification_commands"] if cmd["recommendation_id"]}
    oracle_ids = {oracle["oracle_id"] for oracle in config["required_oracles"] if oracle["oracle_id"]}
    missing_command = sorted(
        rec["recommendation_id"] or rec["target"]
        for rec in config["recommendations"]
        if (rec["recommendation_id"] or rec["target"]) not in command_rec_ids
    )
    missing_oracle = sorted(
        rec["recommendation_id"] or rec["target"]
        for rec in config["recommendations"]
        if rec["required_oracle_id"] and rec["required_oracle_id"] not in oracle_ids
    )
    missing_source_refs = sorted(
        [
            *[rec["recommendation_id"] or rec["target"] for rec in config["recommendations"] if not rec["sourceRef"]],
            *[oracle["oracle_id"] for oracle in config["required_oracles"] if oracle["oracle_id"] and not oracle["sourceRef"]],
            *[cmd["command_id"] for cmd in config["verification_commands"] if cmd["command_id"] and not cmd["sourceRef"]],
            *[signal["signal_id"] for signal in config["signals"] if signal["signal_id"] and not signal["sourceRef"]],
        ]
    )
    stale_derived = sorted(
        item["recommendation_id"]
        for item in derived
        if item["recommendation_id"] in recommendation_ids and item["action"] == "generic"
    )
    return {
        "derived_recommendations": derived,
        "recommendations_missing_command": missing_command,
        "recommendations_missing_oracle": missing_oracle,
        "missing_source_ref_ids": missing_source_refs,
        "stale_or_generic_recommendation_ids": stale_derived,
    }


def _recommendation_from_signal(signal: dict[str, Any]) -> dict[str, Any] | None:
    signal_type = signal["signal_type"]
    target = signal["test_id"] or signal["risk_id"] or signal["requirement_id"]
    if not target:
        return None
    action = "generic"
    required_oracle = ""
    command = ""
    if signal_type in {"no_oracle", "missing_oracle", "oracle_weak"}:
        action = "add_or_modify_test"
        required_oracle = "executable_oracle"
        command = "run targeted test with oracle"
    elif signal_type in {"flaky", "mixed_outcome", "environment_flake"}:
        action = "rerun_test"
        command = "rerun affected test with retry/environment capture"
    elif signal_type in {"impact", "affected_test"}:
        action = "rerun_test"
        command = "rerun impacted test"
    elif signal_type in {"blocked", "manual_review_required", "unsupported_claim"}:
        action = "manual_review"
        command = "open manual review packet"
    elif signal_type in {"coverage_gap", "mutation_survived"}:
        action = "add_test"
        required_oracle = "mutation_backed_oracle"
        command = "run coverage and mutation check"
    return {
        "recommendation_id": signal["signal_id"] or f"rec:{target}",
        "action": action,
        "target": target,
        "risk_id": signal["risk_id"],
        "required_oracle": required_oracle,
        "verification_command": command,
        "confidence": 0.85 if action != "generic" else 0.4,
        "sourceRef": signal["sourceRef"],
    }


def _findings_for(
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    source_ref: str,
) -> list[TestRecommendationFinding]:
    findings: list[TestRecommendationFinding] = []

    # HATE-GAP-050 primary negative: generic advice denied
    if not config["actionable_taxonomy_used"]:
        findings.append(_finding(
            "test_recommendation_generic_advice_denied",
            "Test recommendation engine requires actionable taxonomy for recommendations.",
            source_ref,
        ))

    # Additional finding codes from vocabulary
    for cmd in config["verification_commands"]:
        if not cmd.get("verified"):
            findings.append(_finding(
                "test_recommendation_missing_verification_command",
                f"Verification command '{cmd.get('command_id')}' not verified.",
                source_ref,
            ))

    for oracle in config["required_oracles"]:
        if not oracle.get("verified"):
            findings.append(_finding(
                "test_recommendation_missing_required_oracle",
                f"Required oracle '{oracle.get('oracle_id')}' not verified.",
                source_ref,
            ))

    for rec in config["recommendations"]:
        if not rec.get("actionable"):
            findings.append(_finding(
                "test_recommendation_generic_advice_denied",
                f"Recommendation '{rec.get('action')}' not actionable.",
                source_ref,
            ))

    if diagnostics["recommendations_missing_command"]:
        findings.append(_finding(
            "test_recommendation_missing_verification_command",
            f"Recommendations missing verification commands: {', '.join(diagnostics['recommendations_missing_command'])}.",
            source_ref,
        ))

    if diagnostics["recommendations_missing_oracle"]:
        findings.append(_finding(
            "test_recommendation_missing_required_oracle",
            f"Recommendations reference missing required oracles: {', '.join(diagnostics['recommendations_missing_oracle'])}.",
            source_ref,
        ))

    generic_derived = [rec["recommendation_id"] for rec in diagnostics["derived_recommendations"] if rec["action"] == "generic"]
    if generic_derived:
        findings.append(_finding(
            "test_recommendation_generic_advice_denied",
            f"Signals produced generic recommendations: {', '.join(generic_derived)}.",
            source_ref,
        ))

    if diagnostics["missing_source_ref_ids"]:
        findings.append(_finding(
            "test_recommendation_source_ref_missing",
            f"Recommendation inputs missing sourceRef: {', '.join(diagnostics['missing_source_ref_ids'])}.",
            source_ref,
        ))

    if not config["oracle_validation_enabled"]:
        findings.append(_finding(
            "test_recommendation_missing_required_oracle",
            "Test recommendation engine requires oracle validation.",
            source_ref,
        ))

    if not config["command_verification_enabled"]:
        findings.append(_finding(
            "test_recommendation_missing_verification_command",
            "Test recommendation engine requires command verification.",
            source_ref,
        ))

    if config["confidence"] < config["limits"]["confidence_threshold"]:
        findings.append(_finding(
            "test_recommendation_generic_advice_denied",
            f"Test recommendation confidence {config['confidence']} below threshold {config['limits']['confidence_threshold']}.",
            source_ref,
        ))

    if len(config["recommendations"]) > config["limits"]["max_recommendations"]:
        findings.append(_finding(
            "test_recommendation_budget_exceeded",
            f"Recommendation count {len(config['recommendations'])} exceeds limit {config['limits']['max_recommendations']}.",
            source_ref,
        ))

    if len(config["required_oracles"]) > config["limits"]["max_oracles"]:
        findings.append(_finding(
            "test_recommendation_oracle_budget_exceeded",
            f"Required oracle count {len(config['required_oracles'])} exceeds limit {config['limits']['max_oracles']}.",
            source_ref,
        ))

    if len(config["verification_commands"]) > config["limits"]["max_commands"]:
        findings.append(_finding(
            "test_recommendation_command_budget_exceeded",
            f"Verification command count {len(config['verification_commands'])} exceeds limit {config['limits']['max_commands']}.",
            source_ref,
        ))

    return findings


def _finding(code: str, message: str, source_ref: str) -> TestRecommendationFinding:
    return TestRecommendationFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )
