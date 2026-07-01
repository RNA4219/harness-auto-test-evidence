"""Agent implementation quality evaluation reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_REVIEWER_DECISIONS = {"pass", "needs_review", "reject"}
DEFAULT_RETENTION_DAYS = 30


@dataclass(frozen=True)
class AgentQualityFinding:
    code: str
    severity: str
    readiness_effect: str
    message: str
    sourceRef: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "readiness_effect": self.readiness_effect,
            "message": self.message,
            "sourceRef": self.sourceRef,
        }


def evaluate_agent_quality_fixture(payload: dict[str, Any]) -> dict[str, str]:
    report = build_agent_quality_report(
        payload.get("input", {}),
        report_id=payload.get("fixture_id", "agent-quality"),
        source_refs=[_fixture_source_ref(payload)],
    )
    finding_code = report["findings"][0]["code"] if report["findings"] else ""
    return {
        "status": report["overall_status"],
        "finding_code": finding_code,
        "readiness_effect": "hold" if report["overall_status"] == "hold" else "none",
    }


def build_agent_quality_report(
    data: dict[str, Any],
    report_id: str = "agent-quality",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = source_refs or [f"fixtures/evaluation/agent-quality/{report_id}/fixture.json"]
    output = dict(data.get("agent_output") or {})
    oracle_refs = list(output.get("oracle_refs") or [])
    avoidance_signals = list(output.get("avoidance_signals") or [])
    reviewer_decision = str(output.get("reviewer_decision") or "")
    retained = bool(output.get("retained", True))
    retention_days = int(output.get("retention_days") or DEFAULT_RETENTION_DAYS)
    reviewer_record_ref = str(output.get("reviewer_record_ref") or "")

    findings: list[AgentQualityFinding] = []
    if avoidance_signals:
        findings.append(_finding(
            "agent_quality_avoidance_detected",
            "hold",
            "Agent output contains suspicious implementation avoidance signals.",
            source_refs[0],
        ))
    if not oracle_refs:
        findings.append(_finding(
            "agent_quality_oracle_missing",
            "hold",
            "Agent output has no oracle-backed evidence reference.",
            source_refs[0],
        ))
    if reviewer_decision and reviewer_decision not in REQUIRED_REVIEWER_DECISIONS:
        findings.append(_finding(
            "agent_quality_reviewer_decision_invalid",
            "hold",
            "Reviewer decision is outside the controlled decision set.",
            source_refs[0],
        ))
    if reviewer_decision in {"needs_review", "reject"} and not reviewer_record_ref:
        findings.append(_finding(
            "agent_quality_reviewer_record_missing",
            "hold",
            "Reviewer workflow requires a retained reviewer record.",
            source_refs[0],
        ))
    if not retained or retention_days <= 0:
        findings.append(_finding(
            "agent_quality_retention_missing",
            "hold",
            "Agent quality evidence must be retained with a positive retention window.",
            source_refs[0],
        ))

    score_result = _score(
        oracle_refs,
        avoidance_signals,
        reviewer_decision,
        reviewer_record_ref,
        retained,
        retention_days,
    )
    return {
        "schema_version": "HATE/v1",
        "record_type": "agent-quality-report",
        "report_id": report_id,
        "overall_status": "hold" if findings else "pass",
        "score": score_result["score"],
        "raw_score": score_result["raw_score"],
        "cap_score": score_result["cap_score"],
        "caps": score_result["caps"],
        "dimensions": {
            "oracle_backing": 1.0 if oracle_refs else 0.0,
            "avoidance_penalty": min(1.0, len(avoidance_signals) * 0.4),
            "reviewer_workflow": 1.0 if reviewer_decision in {"pass", ""} or reviewer_record_ref else 0.0,
            "retention": 1.0 if retained and retention_days > 0 else 0.0,
        },
        "oracle_refs": oracle_refs,
        "avoidance_signals": avoidance_signals,
        "reviewer": {
            "decision": reviewer_decision,
            "record_ref": reviewer_record_ref,
            "controlled_decision": reviewer_decision in REQUIRED_REVIEWER_DECISIONS or reviewer_decision == "",
        },
        "retention": {
            "retained": retained,
            "retention_days": retention_days,
        },
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "finding_count": len(findings),
            "manual_review_required": bool(findings),
            "oracle_count": len(oracle_refs),
            "avoidance_signal_count": len(avoidance_signals),
        },
        "sourceRefs": source_refs,
    }


def _score(
    oracle_refs: list[Any],
    avoidance_signals: list[Any],
    reviewer_decision: str,
    reviewer_record_ref: str,
    retained: bool,
    retention_days: int,
) -> dict[str, Any]:
    score = 1.0
    if not oracle_refs:
        score -= 0.35
    score -= min(0.45, len(avoidance_signals) * 0.25)
    if reviewer_decision in {"needs_review", "reject"}:
        score -= 0.2
    if not retained or retention_days <= 0:
        score -= 0.2
    raw_score = max(0.0, round(score, 2))
    caps = _score_caps(
        oracle_refs=oracle_refs,
        avoidance_signals=avoidance_signals,
        reviewer_decision=reviewer_decision,
        reviewer_record_ref=reviewer_record_ref,
        retained=retained,
        retention_days=retention_days,
    )
    cap_score = min((cap["max_score"] for cap in caps), default=1.0)
    return {
        "score": round(min(raw_score, cap_score), 2),
        "raw_score": raw_score,
        "cap_score": cap_score,
        "caps": caps,
    }


def _score_caps(
    *,
    oracle_refs: list[Any],
    avoidance_signals: list[Any],
    reviewer_decision: str,
    reviewer_record_ref: str,
    retained: bool,
    retention_days: int,
) -> list[dict[str, Any]]:
    caps: list[dict[str, Any]] = []
    if not oracle_refs:
        caps.append(_score_cap(
            "oracle_missing",
            0.4,
            "Agent quality cannot score above weak evidence without oracle-backed references.",
        ))
    if avoidance_signals:
        caps.append(_score_cap(
            "avoidance_detected",
            0.35,
            "Suspicious avoidance signals cap agent quality below acceptable evidence.",
        ))
    if reviewer_decision and reviewer_decision not in REQUIRED_REVIEWER_DECISIONS:
        caps.append(_score_cap(
            "reviewer_decision_invalid",
            0.6,
            "Invalid reviewer decision prevents high-confidence quality scoring.",
        ))
    if reviewer_decision in {"needs_review", "reject"} and not reviewer_record_ref:
        caps.append(_score_cap(
            "reviewer_record_missing",
            0.55,
            "Reviewer workflow cannot score highly without a retained reviewer record.",
        ))
    if not retained or retention_days <= 0:
        caps.append(_score_cap(
            "retention_missing",
            0.5,
            "Evidence without retention cannot carry high agent quality score.",
        ))
    return caps


def _score_cap(cap_id: str, max_score: float, reason: str) -> dict[str, Any]:
    return {
        "cap_id": cap_id,
        "max_score": max_score,
        "reason": reason,
    }


def _finding(
    code: str,
    readiness_effect: str,
    message: str,
    source_ref: str,
) -> AgentQualityFinding:
    return AgentQualityFinding(
        code=code,
        severity="high",
        readiness_effect=readiness_effect,
        message=message,
        sourceRef=source_ref,
    )


def _fixture_source_ref(payload: dict[str, Any]) -> str:
    fixture_id = str(payload.get("fixture_id") or "fixture")
    return f"fixtures/evaluation/agent-quality/{fixture_id}/fixture.json"
