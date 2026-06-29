from __future__ import annotations

import json
from pathlib import Path

from hate.evidence_graph import build_evidence_graph
from hate.risk_matrix import build_risk_coverage_matrix


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "graph" / "risk-matrix"


def load_bundle(name: str) -> dict:
    with (FIXTURES / name / "bundle.json").open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    assert isinstance(data, dict)
    return data


def matrix(name: str, **kwargs) -> dict:
    bundle = load_bundle(name)
    graph = build_evidence_graph(bundle)
    return build_risk_coverage_matrix(graph, fixture_id=name, **kwargs)


def test_critical_risk_with_executable_oracle_is_pass() -> None:
    result = matrix("covered-critical-risk")

    assert result["record_type"] == "risk_coverage_matrix"
    assert result["summary"]["overall_status"] == "pass"
    assert result["summary"]["risk_count"] == 1
    assert result["summary"]["covered_count"] == 1
    assert result["summary"]["gap_count"] == 0

    entry = result["entries"][0]
    assert entry["risk_id"] == "RISK-CRITICAL"
    assert entry["severity"] == "critical"
    assert entry["evidence_class"] == "executable_oracle"
    assert entry["oracle_strength"] == 0.9
    assert entry["gap_class"] is None
    assert entry["readiness_effect"] == "pass"
    assert entry["requirement_refs"] == ["REQ-CRITICAL-001"]
    assert entry["required_evidence_classes"] == ["executable_oracle", "contract_check"]
    assert entry["observed_evidence_classes"] == ["executable_oracle"]
    assert "owner" in entry
    assert "due_date" in entry


def test_required_risk_matrix_fixture_names_exist() -> None:
    expected = {
        "covered-critical-risk",
        "weak-coverage",
        "manual-review-required",
        "risk-debt-accepted",
        "security-risk-blocked",
        "high-risk-no-oracle",
        "manual-review-without-owner",
        "expired-risk-debt",
        "coverage-without-evidence",
        "risk-claim-without-requirement",
    }

    assert all((FIXTURES / name / "bundle.json").exists() for name in expected)


def test_high_risk_without_oracle_is_hold() -> None:
    result = matrix("high-risk-no-oracle")

    assert result["summary"]["overall_status"] == "hold"
    assert result["summary"]["gap_count"] == 1
    assert result["summary"]["hold_count"] == 1

    entry = result["entries"][0]
    assert entry["risk_id"] == "RISK-NO-ORACLE"
    assert entry["severity"] == "high"
    assert entry["evidence_class"] is None
    assert entry["oracle_strength"] == 0.0
    assert entry["gap_class"] == "missing_execution"
    assert entry["readiness_effect"] == "hold"

    assert len(result["risk_debt"]) == 1
    debt = result["risk_debt"][0]
    assert debt["debt_type"] == "missing_execution"
    assert debt["severity"] == "high"


def test_coverage_without_assertions_is_soft_gap() -> None:
    result = matrix("coverage-no-evidence")

    assert result["summary"]["overall_status"] == "soft_gap"
    assert result["summary"]["gap_count"] == 1

    entry = result["entries"][0]
    assert entry["risk_id"] == "RISK-COVERAGE-001"
    assert entry["severity"] == "medium"
    assert entry["evidence_class"] == "coverage_only"
    assert entry["oracle_strength"] == 0.2
    assert entry["gap_class"] == "coverage_gap"
    assert entry["readiness_effect"] == "soft_gap"


def test_manual_review_provides_coverage() -> None:
    result = matrix("manual-review-supported-risk")

    assert result["summary"]["overall_status"] == "pass"
    assert result["summary"]["covered_count"] == 1

    entry = result["entries"][0]
    assert entry["risk_id"] == "RISK-MANUAL-001"
    assert entry["evidence_class"] == "manual_review"
    assert entry["oracle_strength"] == 0.5
    assert entry["gap_class"] is None
    assert entry["readiness_effect"] == "pass"


def test_contract_and_mutation_provide_coverage() -> None:
    result = matrix("contract-mutation-evidence")

    assert result["summary"]["overall_status"] == "pass"
    assert result["summary"]["covered_count"] == 1

    entry = result["entries"][0]
    assert entry["risk_id"] == "RISK-CONTRACT-001"
    assert entry["evidence_class"] == "contract_check"
    assert entry["oracle_strength"] == 0.85
    assert entry["gap_class"] is None


def test_high_risk_no_oracle_release_profile_is_blocked() -> None:
    result = matrix("high-risk-no-oracle", profile="release")

    assert result["summary"]["overall_status"] == "blocked"

    entry = result["entries"][0]
    assert entry["readiness_effect"] == "blocked"


def test_multiple_risks_mixed_coverage() -> None:
    result = matrix("multiple-risks-mixed")

    assert result["summary"]["risk_count"] == 4

    entries_by_id = {e["risk_id"]: e for e in result["entries"]}
    assert entries_by_id["RISK-CRITICAL-MIXED"]["readiness_effect"] == "pass"
    assert entries_by_id["RISK-HIGH-MIXED"]["readiness_effect"] == "soft_gap"
    assert entries_by_id["RISK-MEDIUM-MIXED"]["readiness_effect"] == "soft_gap"
    assert entries_by_id["RISK-LOW-MIXED"]["readiness_effect"] == "soft_gap"


def test_dashboard_projection_contains_summary() -> None:
    result = matrix("multiple-risks-mixed")

    projection = result["matrix_projection"]
    assert "by_severity" in projection
    assert "by_gap_class" in projection
    assert "by_evidence_class" in projection
    assert "debt_summary" in projection
    assert "rows" in projection

    assert projection["by_severity"]["critical"]["total"] == 1
    assert projection["by_severity"]["high"]["gaps"] == 1
    assert projection["debt_summary"]["total"] >= 0


def test_expired_risk_debt_is_stale() -> None:
    # Pass historical debt items with age > threshold (critical threshold = 1 day)
    historical_debt = [
        {
            "risk_debt_id": "riskdebt_RISK-EXPIRED_missing_execution",
            "debt_type": "missing_execution",
            "severity": "critical",
            "status": "open",
            "risk_id": "RISK-EXPIRED",
            "owner": None,
            "created_at": "2026-06-20T00:00:00Z",  # 9 days ago
            "last_seen_at": "2026-06-29T00:00:00Z",
            "age_days": 9,
            "source_refs": ["risks/RISK-EXPIRED.yaml"],
            "recommended_actions": ["add unit test"],
            "blocking_profile": ["default", "strict", "release", "product"],
        }
    ]
    result = matrix("expired-risk-debt", now="2026-06-29T00:00:00Z", historical_debt=historical_debt)

    assert result["summary"]["stale_count"] == 1

    findings_codes = {f["code"] for f in result["findings"]}
    assert "risk_debt_stale" in findings_codes


def test_accepted_risk_debt_with_future_expiry_is_visible_and_allowed() -> None:
    historical_debt = [
        {
            "risk_debt_id": "riskdebt_RISK-ACCEPTED_missing_execution",
            "debt_type": "missing_execution",
            "severity": "high",
            "status": "accepted",
            "risk_id": "RISK-ACCEPTED",
            "owner": "qa-lead",
            "created_at": "2026-06-20T00:00:00Z",
            "last_seen_at": "2026-06-29T00:00:00Z",
            "source_refs": ["risks/RISK-ACCEPTED.yaml"],
            "recommended_actions": ["add unit test"],
            "blocking_profile": ["release", "product"],
            "expiry_date": "2026-07-10T00:00:00Z",
            "justification": "temporary acceptance for controlled rollout",
        }
    ]
    result = matrix("risk-debt-accepted", now="2026-06-29T00:00:00Z", historical_debt=historical_debt)

    assert result["summary"]["overall_status"] == "hold"
    assert result["risk_debt"][0]["status"] == "accepted"
    assert result["risk_debt"][0]["expiry_date"] == "2026-07-10T00:00:00Z"
    assert result["risk_debt"][0]["justification"] == "temporary acceptance for controlled rollout"
    assert "accepted_debt_expired" not in {finding["code"] for finding in result["findings"]}


def test_security_risk_static_finding_blocks_not_covers() -> None:
    result = matrix("security-risk-blocked")

    entry = result["entries"][0]
    assert result["summary"]["overall_status"] == "blocked"
    assert entry["gap_class"] == "blocked_by_static_finding"
    assert entry["readiness_effect"] == "blocked"
    assert entry["observed_evidence_classes"] == []


def test_unsupported_claim_is_blocked() -> None:
    result = matrix("unsupported-claim-risk")

    assert result["summary"]["overall_status"] == "blocked"

    findings_codes = {f["code"] for f in result["findings"]}
    assert "unsupported_claim_no_evidence" in findings_codes

    assert len(result["risk_debt"]) == 1
    debt = result["risk_debt"][0]
    assert debt["debt_type"] == "traceability_gap"


def test_oracle_strength_scoring_correct() -> None:
    result = matrix("critical-risk-covered")

    entry = result["entries"][0]
    assert entry["evidence_class"] == "executable_oracle"
    assert entry["oracle_strength"] == 0.9

    result2 = matrix("contract-mutation-evidence")
    entry2 = result2["entries"][0]
    assert entry2["evidence_class"] == "contract_check"
    assert entry2["oracle_strength"] == 0.85


def test_debt_item_recommended_actions() -> None:
    result = matrix("high-risk-no-oracle")

    debt = result["risk_debt"][0]
    assert debt["debt_type"] == "missing_execution"
    assert len(debt["recommended_actions"]) > 0
    assert "add unit test" in debt["recommended_actions"]


def test_blocking_profile_for_severity() -> None:
    result = matrix("high-risk-no-oracle", profile="release")

    debt = result["risk_debt"][0]
    assert "release" in debt["blocking_profile"]
    assert "product" in debt["blocking_profile"]
