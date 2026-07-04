from __future__ import annotations

import json
from pathlib import Path

from hate.post_poc.release_handoff import build_release_handoff_report, evaluate_release_handoff_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc" / "handoff"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "release-handoff-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "release-handoff-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert report["handoff_request"]["record_type"] == "external-release-handoff-request"
    assert report["handoff_result"]["record_type"] == "external-release-handoff-result"
    assert report["external_approval_reference"]["record_type"] == "external-approval-reference"
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_task_postpoc_010_canonical_fixture_paths_exist() -> None:
    for name in [
        "qeg-approved-reference",
        "qeg-denied-reference",
        "shipyard-publish-denied",
        "hate-overclaim-denied",
        "missing-external-reference",
    ]:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_qeg_approved_reference_passes_without_hate_final_approval_claim() -> None:
    result = evaluate_release_handoff_fixture(_fixture("qeg-approved-reference"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["report"]["summary"]["external_reference_present"] is True
    assert result["report"]["summary"]["hate_claimed_final_approval"] is False
    _assert_report_contract(result["report"])


def test_qeg_denied_reference_is_preserved_as_hold() -> None:
    result = evaluate_release_handoff_fixture(_fixture("qeg-denied-reference"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "handoff_external_denied"
    assert result["report"]["handoff_result"]["external_status"] == "denied"


def test_shipyard_publish_denied_is_preserved() -> None:
    result = evaluate_release_handoff_fixture(_fixture("shipyard-publish-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "handoff_external_denied"
    assert result["report"]["handoff_request"]["handoff_target"] == "shipyard"


def test_hate_overclaim_and_verdict_overwrite_are_denied() -> None:
    result = evaluate_release_handoff_fixture(_fixture("hate-overclaim-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "handoff_hate_claimed_final_approval"
    assert "handoff_verdict_overwrite_attempted" in _codes(result["report"])


def test_missing_external_reference_holds_even_when_status_says_approved() -> None:
    result = evaluate_release_handoff_fixture(_fixture("missing-external-reference"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "handoff_external_reference_missing"
    assert result["report"]["summary"]["external_status"] == "approved"


def test_unavailable_target_holds() -> None:
    report = build_release_handoff_report({
        "request": {
            "handoff_id": "handoff-unavailable",
            "handoff_target": "unknown_gate",
            "handoff_mode": "live_reference",
            "external_run_ref": "external://run",
            "external_decision_ref": "external://decision",
            "external_status": "approved",
            "target_available": False,
        }
    })

    assert report["overall_status"] == "hold"
    assert "handoff_target_unavailable" in _codes(report)


def test_invalid_handoff_mode_holds() -> None:
    report = build_release_handoff_report({
        "request": {
            "handoff_id": "handoff-mode",
            "handoff_target": "qeg",
            "handoff_mode": "self_approve",
            "external_run_ref": "qeg://run",
            "external_decision_ref": "qeg://decision",
            "external_status": "approved",
        }
    })

    assert report["overall_status"] == "hold"
    assert "handoff_target_unavailable" in _codes(report)


def test_release_handoff_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["release-handoff-report"] == "schemas/HATE/v1/release-handoff-report.schema.json"
