from __future__ import annotations

import json
from pathlib import Path

from hate.post_poc.connectors import (
    build_connector_execution_plan,
    build_connector_runtime_report,
    evaluate_connector_runtime_fixture,
    write_connector_execution_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc" / "connectors"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "connector-runtime-report.schema.json"
MANIFEST_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "connector-execution-manifest.schema.json"
STEP_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "connector-execution-step.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "connector-runtime-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert report["runtime_plan"]["record_type"] == "connector-runtime-plan"
    for attempt in report["runtime_attempts"]:
        assert attempt["record_type"] == "connector-runtime-attempt"
        assert attempt["sourceRefs"]
    for record in report["idempotency_records"]:
        assert record["record_type"] == "connector-idempotency-record"
        assert record["sourceRefs"]
    for record in report["rollback_visibility_records"]:
        assert record["record_type"] == "connector-rollback-visibility-record"
        assert record["sourceRefs"]
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def _assert_manifest_contract(manifest: dict) -> None:
    schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    step_schema = json.loads(STEP_SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(manifest)
    assert manifest["schema_version"] == "HATE/v1"
    assert manifest["record_type"] == "connector-execution-manifest"
    assert manifest["mode"] in {"dry_run", "live", "replay", "rollback_preview"}
    for step in manifest["steps"]:
        assert set(schema["properties"]["steps"]["items"]["required"]) <= set(step)
        assert set(step_schema["required"]) <= set(step)
        assert step["record_type"] == "connector-execution-step"
        assert step["status"] in {"ready", "blocked", "skipped"}


def test_task_postpoc_007_canonical_fixture_paths_exist() -> None:
    for name in [
        "fake-ticket-live-success",
        "dry-run-no-side-effect",
        "idempotent-retry",
        "token-exposure-denied",
        "rollback-visibility-missing",
    ]:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_fake_ticket_live_success_passes_with_fake_endpoint() -> None:
    result = evaluate_connector_runtime_fixture(_fixture("fake-ticket-live-success"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["report"]["runtime_plan"]["mode"] == "live"
    assert result["report"]["summary"]["side_effect_performed"] is True
    assert result["report"]["runtime_attempts"][0]["external_ref"] == "fake-ticket://TICKET-001"
    _assert_report_contract(result["report"])


def test_dry_run_has_no_side_effect_and_distinct_source_ref() -> None:
    result = evaluate_connector_runtime_fixture(_fixture("dry-run-no-side-effect"))

    assert result["status"] == "pass"
    assert result["report"]["runtime_plan"]["mode"] == "dry_run"
    assert result["report"]["summary"]["side_effect_performed"] is False
    assert "dry-run-no-side-effect" in result["report"]["runtime_attempts"][0]["sourceRefs"][0]


def test_idempotent_retry_passes_after_successful_retry() -> None:
    result = evaluate_connector_runtime_fixture(_fixture("idempotent-retry"))

    assert result["status"] == "pass"
    assert result["report"]["summary"]["attempt_count"] == 2
    assert {record["idempotency_key"] for record in result["report"]["idempotency_records"]} == {"ticket-retry-001"}
    assert result["report"]["runtime_plan"]["sync_status"] == "succeeded"


def test_token_exposure_is_denied() -> None:
    result = evaluate_connector_runtime_fixture(_fixture("token-exposure-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "connector_token_exposed"
    assert "connector_payload_rejected" in _codes(result["report"])


def test_rollback_visibility_missing_holds() -> None:
    result = evaluate_connector_runtime_fixture(_fixture("rollback-visibility-missing"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "connector_rollback_visibility_missing"
    assert result["report"]["rollback_visibility_records"][0]["rollback_available"] is False


def test_live_mode_requires_explicit_allowance() -> None:
    report = build_connector_runtime_report({
        "plan": {
            "connector_id": "real-ticket",
            "connector_type": "ticket",
            "mode": "live",
            "endpoint_ref": "fake-endpoint://ticket-system",
            "endpoint_available": True,
            "live_mode_allowed": False,
            "idempotency_key": "k",
            "payload_hash": "sha256:p",
            "redaction_report_ref": "artifact://redaction/report.json",
            "token_ref": "secret-ref://connectors/real-ticket",
            "rollback_available": True,
        }
    })

    assert report["overall_status"] == "hold"
    assert "connector_live_mode_not_allowed" in _codes(report)


def test_idempotency_key_missing_holds() -> None:
    report = build_connector_runtime_report({
        "plan": {
            "connector_id": "fake-ticket",
            "connector_type": "ticket",
            "mode": "dry_run",
            "endpoint_ref": "fake-endpoint://ticket-system",
            "endpoint_available": True,
            "redaction_report_ref": "artifact://redaction/report.json",
            "token_ref": "secret-ref://connectors/fake-ticket",
            "rollback_available": True,
        }
    })

    assert report["overall_status"] == "hold"
    assert "connector_idempotency_key_missing" in _codes(report)


def test_endpoint_unavailable_holds() -> None:
    report = build_connector_runtime_report({
        "plan": {
            "connector_id": "fake-ticket",
            "connector_type": "ticket",
            "mode": "dry_run",
            "endpoint_ref": "",
            "endpoint_available": False,
            "idempotency_key": "k",
            "payload_hash": "sha256:p",
            "redaction_report_ref": "artifact://redaction/report.json",
            "token_ref": "secret-ref://connectors/fake-ticket",
            "rollback_available": True,
        }
    })

    assert report["overall_status"] == "hold"
    assert "connector_endpoint_unavailable" in _codes(report)


def test_connector_runtime_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["connector-runtime-report"] == "schemas/HATE/v1/connector-runtime-report.schema.json"
    assert records["connector-execution-manifest"] == "schemas/HATE/v1/connector-execution-manifest.schema.json"
    assert records["connector-execution-step"] == "schemas/HATE/v1/connector-execution-step.schema.json"


def test_connector_execution_plan_for_dry_run_skips_side_effect_step() -> None:
    plan = build_connector_execution_plan(_fixture("dry-run-no-side-effect")["input"], source_refs=["fixture://connectors/dry-run"])
    steps = {step["step_type"]: step for step in plan["steps"]}

    assert plan["record_type"] == "connector-execution-plan"
    assert plan["mode"] == "dry_run"
    assert plan["approval_required"] is False
    assert plan["summary"]["side_effect_possible"] is False
    assert plan["summary"]["execution_allowed"] is False
    assert steps["execute"]["status"] == "skipped"
    assert steps["rollback_preview"]["status"] == "ready"
    assert plan["sourceRefs"] == ["fixture://connectors/dry-run"]


def test_connector_execution_plan_for_live_requires_approval_and_rollback() -> None:
    input_data = _fixture("rollback-visibility-missing")["input"]

    plan = build_connector_execution_plan(input_data)
    codes = _codes(plan)

    assert plan["mode"] == "live"
    assert plan["approval_required"] is True
    assert plan["rollback_required"] is True
    assert plan["summary"]["execution_allowed"] is False
    assert "connector_execution_step_blocked" in codes
    assert "connector_rollback_visibility_missing" in codes


def test_connector_execution_plan_for_approved_live_can_execute() -> None:
    plan = build_connector_execution_plan(_fixture("fake-ticket-live-success")["input"])
    steps = {step["step_type"]: step for step in plan["steps"]}

    assert plan["summary"]["execution_allowed"] is True
    assert steps["approval_gate"]["status"] == "ready"
    assert steps["execute"]["status"] == "ready"
    assert steps["rollback_preview"]["status"] == "ready"
    assert plan["findings"] == []


def test_connector_execution_plan_blocks_raw_token_before_provider_handoff() -> None:
    plan = build_connector_execution_plan(_fixture("token-exposure-denied")["input"])

    assert "connector_token_exposed" in _codes(plan)
    assert plan["summary"]["execution_allowed"] is False


def test_connector_execution_manifest_write_contract(tmp_path: Path) -> None:
    plan = build_connector_execution_plan(_fixture("fake-ticket-live-success")["input"], source_refs=["fixture://connectors/live"])
    out_path = tmp_path / "connector-execution.json"

    artifact = write_connector_execution_manifest(plan, out_path)

    assert artifact["record_type"] == "connector-execution-manifest-artifact"
    assert artifact["step_count"] == 7
    assert artifact["sourceRefs"] == ["fixture://connectors/live"]
    manifest = json.loads(out_path.read_text(encoding="utf-8"))
    assert manifest["record_type"] == "connector-execution-manifest"
    _assert_manifest_contract(manifest)
    assert manifest["steps"][4]["step_type"] == "execute"
