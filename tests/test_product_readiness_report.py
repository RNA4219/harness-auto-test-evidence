from __future__ import annotations

import json
from pathlib import Path

from hate.evidence_graph import build_evidence_graph
from hate.readiness_model import build_product_readiness_from_graph


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "graph" / "model"


def readiness(name: str) -> dict:
    with (FIXTURES / name / "bundle.json").open("r", encoding="utf-8") as handle:
        bundle = json.load(handle)
    return build_product_readiness_from_graph(build_evidence_graph(bundle), fixture_id=name)


def test_supported_requirement_claim_is_go() -> None:
    report = readiness("requirement-test-coverage")

    assert report["record_type"] == "product_readiness_report"
    assert report["summary"]["overall_status"] == "go"
    assert report["summary"]["unsupported_claim_count"] == 0


def test_manual_review_can_support_requirement_when_explicit() -> None:
    report = readiness("manual-review-supported")

    assert report["summary"]["overall_status"] == "go"
    assert report["summary"]["unsupported_claim_count"] == 0


def test_contradictory_evidence_blocks_readiness() -> None:
    report = readiness("contradictory-evidence")

    assert report["summary"]["overall_status"] == "block"
    assert report["summary"]["contradiction_count"] == 1
    assert report["unsupported_claims"][0]["claim_id"] == "CLAIM-CONTRACT-READY"


def test_missing_requirement_ref_blocks_claim_path() -> None:
    report = readiness("missing-requirement-ref")

    assert report["summary"]["overall_status"] == "block"
    assert {finding["code"] for finding in report["hard_dqs"]} == {"missing_requirement_ref"}


def test_unsupported_claim_marked_ready_is_hard_dq() -> None:
    report = readiness("unsupported-claim-marked-ready")

    assert report["summary"]["overall_status"] == "block"
    assert report["summary"]["unsupported_claim_count"] == 1
    assert "unsupported_claim_marked_ready" in {finding["code"] for finding in report["hard_dqs"]}
