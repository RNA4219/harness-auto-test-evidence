from __future__ import annotations

import json
from pathlib import Path

from hate.p0a_schema import _validate_schema_value
from hate.p2p3_readiness import _build_product_readiness_report

ROOT = Path(__file__).resolve().parents[1]


def _report(input_gaps: list[dict[str, str]] | None = None) -> dict:
    return _build_product_readiness_report(
        run_id="run-contract",
        version="test",
        source_refs=["workflow-task-seed.json"],
        aete={"weighted_score": 0.82, "calibration_status": "calibrated", "score_confidence": "high"},
        doctor={"summary": {"finding_count": 0}, "sourceRefs": ["doctor-report.json"]},
        alignment={
            "summary": {
                "claim_count": 3,
                "requirement_count": 2,
                "acceptance_count": 3,
                "unverified_acceptance_count": 0,
            },
            "sourceRefs": ["requirement-evidence-alignment.json"],
        },
        workflow_acceptance={"verdict": "accepted"},
        product_metrics={"metrics": [{"metric_id": "m1"}]},
        generated_refs=["dashboard-report.html", "enterprise-metrics-report.json"],
        input_gaps=input_gaps or [],
    )


def test_p2p3_product_readiness_emits_schema_required_sections() -> None:
    report = _report()

    for field in ("graph_summary", "unsupported_claims", "contradictions", "hard_dqs", "soft_gaps", "sourceRefs"):
        assert field in report
    assert report["summary"]["claim_count"] == 3
    assert report["summary"]["unsupported_claim_count"] == 0
    assert report["summary"]["contradiction_count"] == 0
    assert report["summary"]["hard_dq_count"] == 0
    assert "requirement-evidence-alignment.json" in report["sourceRefs"]
    assert "workflow-task-seed.json" in report["sourceRefs"]


def test_p2p3_product_readiness_matches_artifact_schema() -> None:
    schema = json.loads((ROOT / "schemas/HATE/v1/product-readiness-report.schema.json").read_text(encoding="utf-8"))
    errors = _validate_schema_value(_report(), schema, "$")

    assert errors == []


def test_p2p3_missing_input_artifacts_are_visible_soft_gaps() -> None:
    report = _report([{"root": "workflow", "artifact_ref": "workflow-evidence.jsonl", "reason": "expected input artifact missing"}])

    assert report["summary"]["overall_status"] == "hold"
    assert report["summary"]["soft_gap_count"] == 1
    assert report["soft_gaps"][0]["code"] == "missing_input_artifact"
    assert report["soft_gaps"][0]["readiness_effect"] == "hold"
    assert "workflow-evidence.jsonl" in report["sourceRefs"]
