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
    findings = _findings_for(rec_config, source_refs[0])
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
            "confidence": rec_config["confidence"],
            "finding_count": len(findings),
        },
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
    return {
        "recommendations": recommendations,
        "required_oracles": required_oracles,
        "verification_commands": verification_commands,
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
        "action": str(rec.get("action", "") or ""),
        "target": str(rec.get("target", "") or ""),
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


def _normalize_limits(limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_recommendations": int(limits.get("max_recommendations", 100) or 100),
        "max_oracles": int(limits.get("max_oracles", 50) or 50),
        "confidence_threshold": float(limits.get("confidence_threshold", 0.7) or 0.7),
    }


def _findings_for(config: dict[str, Any], source_ref: str) -> list[TestRecommendationFinding]:
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

    return findings


def _finding(code: str, message: str, source_ref: str) -> TestRecommendationFinding:
    return TestRecommendationFinding(
        code=code,
        severity="high",
        message=message,
        sourceRef=source_ref,
    )