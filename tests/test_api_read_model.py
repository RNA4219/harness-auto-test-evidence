"""UAT tests for API read-model projection over HATE reports."""

from __future__ import annotations

import json
from pathlib import Path

from hate.api import (
    build_read_model,
    get_run_detail,
    list_artifacts,
    list_doctor_findings,
    list_risks,
    list_runs,
)


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "api" / "read-model"
TENANT = {"organization_id": "org-001", "workspace_id": "ws-001"}


def load_fixture(name: str) -> dict:
    with (FIXTURE_ROOT / name / "fixture.json").open(encoding="utf-8") as f:
        return json.load(f)


def model_from_fixture(name: str) -> tuple[dict, dict]:
    fixture = load_fixture(name)
    input_data = fixture["input"]
    return build_read_model(
        input_data["reports"],
        required_reports=input_data.get("required_reports", []),
    ), fixture["expected"]


def test_packet_fixture_paths_exist() -> None:
    for name in [
        "minimal-run",
        "risk-readiness",
        "quarantined-artifact",
        "manual-review-pending",
        "missing-upstream-report",
    ]:
        assert (FIXTURE_ROOT / name / "fixture.json").exists()


def test_minimal_run_projects_run_and_source_bundle() -> None:
    read_model, expected = model_from_fixture("minimal-run")

    response = list_runs(TENANT, read_model=read_model)

    assert response["errors"] == []
    assert response["source"]["bundle_hash"] == expected["bundle_hash"]
    assert response["staleness"]["status"] == expected["staleness"]
    assert response["data"]["runs"][0]["run_id"] == expected["run_id"]
    assert response["data"]["runs"][0]["decision"] == expected["decision"]
    assert "reports/product-readiness-report.json" in response["data"]["runs"][0]["source_refs"]


def test_run_detail_is_projected_from_reports() -> None:
    read_model, expected = model_from_fixture("minimal-run")

    response = get_run_detail(TENANT, expected["run_id"], 2, read_model=read_model)

    assert response["errors"] == []
    assert response["data"]["run_id"] == expected["run_id"]
    assert response["data"]["provenance"]["commit"] == "abc123"
    assert response["data"]["outputs"]["overall_status"] == expected["decision"]


def test_risk_readiness_does_not_recompute_verdict() -> None:
    read_model, expected = model_from_fixture("risk-readiness")

    runs = list_runs(TENANT, read_model=read_model)
    risks = list_risks(TENANT, filters={"severity": "high"}, read_model=read_model)

    assert runs["data"]["runs"][0]["decision"] == expected["decision"]
    assert risks["errors"] == []
    assert risks["data"]["risks"][0]["risk_id"] == expected["risk_id"]
    assert risks["data"]["risks"][0]["oracle_status"] == expected["oracle_status"]
    assert risks["data"]["risks"][0]["manual_required"] is expected["manual_required"]


def test_quarantined_artifact_exposes_only_safe_metadata() -> None:
    read_model, expected = model_from_fixture("quarantined-artifact")

    reader_response = list_artifacts(TENANT, actor_role="reader", read_model=read_model)
    maintainer_response = list_artifacts(TENANT, actor_role="maintainer", read_model=read_model)

    assert len(reader_response["data"]["artifacts"]) == expected["reader_visible_count"]
    assert len(maintainer_response["data"]["artifacts"]) == expected["maintainer_visible_count"]
    serialized = json.dumps(maintainer_response["data"], sort_keys=True)
    assert "SECRET_SHOULD_NOT_APPEAR" not in serialized
    assert "raw_content" not in serialized
    restricted = [
        item for item in maintainer_response["data"]["artifacts"]
        if item["artifact_id"] == expected["restricted_artifact_id"]
    ][0]
    assert restricted["quarantine_status"] == "quarantined"
    assert "safe_metadata" in restricted


def test_manual_review_pending_is_visible_in_read_model() -> None:
    read_model, expected = model_from_fixture("manual-review-pending")

    requests = read_model["manual_review_requests"]

    assert requests[0]["request_id"] == expected["request_id"]
    assert requests[0]["status"] == expected["status"]
    assert requests[0]["owner"] == expected["owner"]
    assert requests[0]["sourceRef"] == "reports/manual-review-request.json#/0"


def test_missing_upstream_report_is_stale_diagnostic_not_fake_success() -> None:
    read_model, expected = model_from_fixture("missing-upstream-report")

    runs = list_runs(TENANT, read_model=read_model)
    findings = list_doctor_findings(TENANT, filters={"severity": "hold"}, read_model=read_model)

    assert runs["staleness"]["status"] == expected["staleness"]
    assert runs["data"]["runs"][0]["decision"] == "unknown"
    assert len(read_model["diagnostics"]) == expected["missing_count"]
    assert findings["data"]["findings"][0]["finding_id"] == expected["diagnostic_code"]
