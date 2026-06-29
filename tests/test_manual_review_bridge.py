from __future__ import annotations

import json
from pathlib import Path

from hate.evidence_graph import build_evidence_graph
from hate.risk_matrix import build_risk_coverage_matrix
from hate.manual_review_bridge import (
    accept_risk_debt,
    build_manual_review_requests,
    validate_manual_review_request,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "graph" / "risk-matrix"


def load_bundle(name: str) -> dict:
    with (FIXTURES / name / "bundle.json").open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    assert isinstance(data, dict)
    return data


def bridge(name: str, **kwargs) -> dict:
    bundle = load_bundle(name)
    graph = build_evidence_graph(bundle)

    # Split kwargs between matrix and bridge
    matrix_kwargs = {}
    bridge_kwargs = {}

    matrix_keys = {"profile", "now", "historical_debt"}
    bridge_keys = {"owner_override", "expiry_days"}

    for key, value in kwargs.items():
        if key in matrix_keys:
            matrix_kwargs[key] = value
        elif key in bridge_keys:
            bridge_kwargs[key] = value
        else:
            # Unknown key - pass to bridge (more permissive)
            bridge_kwargs[key] = value

    matrix = build_risk_coverage_matrix(graph, fixture_id=name, **matrix_kwargs)
    return build_manual_review_requests(matrix, fixture_id=f"{name}-bridge", **bridge_kwargs)


def test_manual_review_request_generated_for_gap() -> None:
    result = bridge("high-risk-no-oracle", owner_override="reviewer@example.com")

    assert result["record_type"] == "manual_review_request_bundle"
    assert result["summary"]["request_count"] == 1
    assert result["summary"]["pending_count"] == 1

    request = result["requests"][0]
    assert request["risk_id"] == "RISK-NO-ORACLE"
    assert request["owner"] == "reviewer@example.com"
    assert request["status"] == "pending"
    assert request["expiry_date"] is not None
    assert request["expiry"] == request["expiry_date"]
    assert request["reason"]
    assert request["blocking"] is True
    assert request["required_decision"] == "verify_coverage_or_accept_risk"


def test_manual_review_required_fixture_generates_request() -> None:
    result = bridge("manual-review-required", owner_override="reviewer@example.com")

    assert result["summary"]["request_count"] == 1
    assert result["requests"][0]["risk_id"] == "RISK-MANUAL-001"
    assert result["requests"][0]["owner"] == "reviewer@example.com"
    assert result["requests"][0]["required_decision"]


def test_missing_manual_owner_is_hard_dq() -> None:
    result = bridge("high-risk-no-oracle")

    assert result["summary"]["overall_status"] == "blocked"
    assert result["summary"]["hard_dq_count"] == 1
    assert result["summary"]["missing_owner_count"] == 1

    findings_codes = {f["code"] for f in result["findings"]}
    assert "manual_review_missing_owner" in findings_codes


def test_manual_review_request_validation() -> None:
    request = {
        "request_id": "manual_review_RISK-001",
        "risk_id": "RISK-001",
        "owner": None,
        "expiry_date": "2027-06-29T00:00:00Z",
        "source_refs": [],
        "status": "pending",
    }

    findings = validate_manual_review_request(request)

    assert len(findings) >= 1
    assert any(f.code == "manual_review_missing_owner" for f in findings)


def test_manual_review_request_with_valid_owner() -> None:
    request = {
        "request_id": "manual_review_RISK-001",
        "risk_id": "RISK-001",
        "owner": "reviewer@example.com",
        "expiry_date": "2027-06-29T00:00:00Z",
        "source_refs": ["risks/RISK-001.yaml"],
        "status": "pending",
    }

    findings = validate_manual_review_request(request)

    hard_findings = [f for f in findings if f.severity == "hard"]
    assert len(hard_findings) == 0


def test_accept_risk_debt_requires_owner() -> None:
    debt_item = {
        "risk_debt_id": "riskdebt_RISK-001_missing_execution",
        "debt_type": "missing_execution",
        "severity": "high",
        "risk_id": "RISK-001",
        "source_refs": ["risks/RISK-001.yaml"],
    }

    try:
        accept_risk_debt(debt_item, owner=None, justification="test")
        assert False, "should have raised"
    except ValueError as e:
        assert "owner" in str(e)


def test_accept_risk_debt_requires_justification() -> None:
    debt_item = {
        "risk_debt_id": "riskdebt_RISK-001_missing_execution",
        "debt_type": "missing_execution",
        "severity": "high",
        "risk_id": "RISK-001",
        "source_refs": ["risks/RISK-001.yaml"],
    }

    try:
        accept_risk_debt(debt_item, owner="reviewer@example.com", justification="")
        assert False, "should have raised"
    except ValueError as e:
        assert "justification" in str(e)


def test_accept_risk_debt_produces_accepted_status() -> None:
    debt_item = {
        "risk_debt_id": "riskdebt_RISK-001_missing_execution",
        "debt_type": "missing_execution",
        "severity": "high",
        "risk_id": "RISK-001",
        "source_refs": ["risks/RISK-001.yaml"],
        "created_at": "2026-06-29T00:00:00Z",
        "age_days": 5,
    }

    accepted = accept_risk_debt(
        debt_item,
        owner="reviewer@example.com",
        justification="Manual verification performed, risk mitigated.",
        expiry_days=14,
    )

    assert accepted["status"] == "accepted"
    assert accepted["owner"] == "reviewer@example.com"
    assert accepted["justification"] == "Manual verification performed, risk mitigated."
    assert accepted["expiry_date"] is not None


def test_expired_accepted_debt_is_hard_dq() -> None:
    # Create a scenario where accepted debt has expired
    historical_debt = [
        {
            "risk_debt_id": "riskdebt_RISK-EXPIRED_missing_execution",
            "debt_type": "missing_execution",
            "severity": "critical",
            "status": "accepted",
            "risk_id": "RISK-EXPIRED",
            "owner": "reviewer@example.com",
            "created_at": "2026-06-20T00:00:00Z",
            "last_seen_at": "2026-06-29T00:00:00Z",
            "age_days": 9,
            "source_refs": ["risks/RISK-EXPIRED.yaml"],
            "recommended_actions": ["add unit test"],
            "blocking_profile": ["default", "strict", "release", "product"],
            "expiry_date": "2026-06-25T00:00:00Z",  # Already expired
        }
    ]

    result = bridge("expired-risk-debt", historical_debt=historical_debt, now="2026-06-29T00:00:00Z")

    # Expired accepted debt should be treated as hard DQ
    assert result["summary"]["overall_status"] == "blocked"
    assert result["summary"]["hard_dq_count"] >= 1

    findings_codes = {f["code"] for f in result["findings"]}
    assert "accepted_debt_expired" in findings_codes


def test_bridge_status_blocked_on_hard_findings() -> None:
    result = bridge("high-risk-no-oracle")

    assert result["summary"]["overall_status"] == "blocked"


def test_bridge_status_pending_on_requests() -> None:
    result = bridge("high-risk-no-oracle", owner_override="reviewer@example.com")

    assert result["summary"]["overall_status"] == "pending"


def test_expiry_days_override() -> None:
    result = bridge("high-risk-no-oracle", owner_override="reviewer@example.com", expiry_days=7)

    request = result["requests"][0]
    assert request["expiry_date"] is not None
    # The expiry should be 7 days from now


def test_source_refs_preserved_in_request() -> None:
    result = bridge("high-risk-no-oracle", owner_override="reviewer@example.com")

    request = result["requests"][0]
    assert len(request["source_refs"]) > 0


def test_no_gap_entries_no_requests() -> None:
    result = bridge("critical-risk-covered", owner_override="reviewer@example.com")

    assert result["summary"]["request_count"] == 0
    assert result["summary"]["overall_status"] == "ready"
