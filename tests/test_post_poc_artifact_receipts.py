from __future__ import annotations

import json
from pathlib import Path

from hate.post_poc.baseline import write_baseline_review_packet
from hate.post_poc.capacity import write_capacity_regression_packet
from hate.post_poc.connectors import write_connector_execution_manifest
from hate.post_poc.dashboard import write_dashboard_static_html
from hate.post_poc.history_analytics import write_history_materialization_manifest
from hate.post_poc.hosted_api import build_hosted_api_openapi_document, write_hosted_api_openapi_document
from hate.post_poc.human_review import write_human_review_queue_packet
from hate.post_poc.notifications import write_notification_routing_manifest
from hate.post_poc.observability import write_incident_response_packet
from hate.post_poc.plugin_distribution import write_plugin_install_manifest
from hate.post_poc.roster import write_roster_execution_manifest
from hate.post_poc.scheduler import write_scheduler_dispatch_manifest
from hate.post_poc.store_dr import write_store_dr_runbook


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "post-poc-artifact-receipt.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


ARTIFACT_RECORD_TYPES = {
    "baseline-review-packet-artifact",
    "capacity-regression-packet-artifact",
    "connector-execution-manifest-artifact",
    "dashboard-static-html-artifact",
    "history-materialization-manifest-artifact",
    "hosted-api-openapi-artifact",
    "hosted-scheduler-dispatch-manifest-artifact",
    "human-review-queue-packet-artifact",
    "incident-response-packet-artifact",
    "notification-routing-manifest-artifact",
    "plugin-install-manifest-artifact",
    "real-repo-roster-execution-manifest-artifact",
    "store-dr-runbook-artifact",
}


def _assert_receipt_contract(receipt: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(receipt)
    assert receipt["schema_version"] == "HATE/v1"
    assert receipt["record_type"] in schema["properties"]["record_type"]["enum"]
    assert receipt["artifact_path"]
    assert isinstance(receipt["sourceRefs"], list)
    assert receipt["record_id"]
    assert receipt["created_at"]
    assert receipt["decision_basis"]
    assert receipt["readiness_effect"] in {"none", "hold"}
    assert receipt["unsafe_output_policy"] == "redact_unsafe_outputs"
    assert receipt.get("actor") or receipt.get("system_actor")


def test_post_poc_artifact_receipt_schema_registers_all_artifact_record_types() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert set(schema["properties"]["record_type"]["enum"]) == ARTIFACT_RECORD_TYPES | {"post-poc-artifact-receipt"}
    assert records["post-poc-artifact-receipt"] == "schemas/HATE/v1/post-poc-artifact-receipt.schema.json"
    for record_type in ARTIFACT_RECORD_TYPES:
        assert records[record_type] == "schemas/HATE/v1/post-poc-artifact-receipt.schema.json"


def test_post_poc_artifact_writers_emit_receipts(tmp_path: Path) -> None:
    source_refs = ["fixture://post-poc/artifact-receipt"]
    receipts = [
        write_baseline_review_packet({"baseline_id": "baseline", "review_items": [], "sourceRefs": source_refs}, tmp_path / "baseline.json"),
        write_capacity_regression_packet({"comparisons": [], "sourceRefs": source_refs}, tmp_path / "capacity.json"),
        write_connector_execution_manifest({"steps": [], "sourceRefs": source_refs}, tmp_path / "connector.json"),
        write_dashboard_static_html(
            {
                "report_id": "dashboard",
                "overall_status": "pass",
                "session_view": {},
                "route_states": [],
                "action_intents": [],
                "findings": [],
                "summary": {},
                "sourceRefs": source_refs,
            },
            tmp_path / "dashboard.html",
        ),
        write_history_materialization_manifest({"entries": [], "sourceRefs": source_refs}, tmp_path / "history.json"),
        write_hosted_api_openapi_document(build_hosted_api_openapi_document(source_refs=source_refs), tmp_path / "openapi.json"),
        write_scheduler_dispatch_manifest({"dispatch_entries": [], "sourceRefs": source_refs}, tmp_path / "scheduler.json"),
        write_human_review_queue_packet({"allowed_actions": [], "sourceRefs": source_refs}, tmp_path / "human-review.json"),
        write_incident_response_packet({"actions": [], "sourceRefs": source_refs}, tmp_path / "incident.json"),
        write_notification_routing_manifest({"routing_entries": [], "sourceRefs": source_refs}, tmp_path / "notifications.json"),
        write_plugin_install_manifest({"entries": [], "sourceRefs": source_refs}, tmp_path / "plugin.json"),
        write_roster_execution_manifest({"entries": [], "sourceRefs": source_refs}, tmp_path / "roster.json"),
        write_store_dr_runbook({"steps": [], "sourceRefs": source_refs}, tmp_path / "store-dr.json"),
    ]

    assert {receipt["record_type"] for receipt in receipts} == ARTIFACT_RECORD_TYPES
    for receipt in receipts:
        _assert_receipt_contract(receipt)
        assert Path(receipt["artifact_path"]).is_file()
