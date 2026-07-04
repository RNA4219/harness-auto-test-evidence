from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from hate.post_poc.baseline import build_baseline_review_packet, evaluate_baseline_fixture
from hate.post_poc.capacity import build_capacity_regression_packet, evaluate_capacity_fixture
from hate.post_poc.compliance import evaluate_compliance_fixture
from hate.post_poc.connectors import build_connector_execution_plan, evaluate_connector_runtime_fixture
from hate.post_poc.dashboard import evaluate_dashboard_fixture
from hate.post_poc.docs_freshness import evaluate_docs_freshness_fixture
from hate.post_poc.history_analytics import build_history_materialization_plan, evaluate_history_analytics_fixture
from hate.post_poc.hosted_api import build_hosted_api_route_manifest, evaluate_hosted_api_fixture
from hate.post_poc.human_review import build_human_review_queue_packet, evaluate_human_review_fixture
from hate.post_poc.notifications import build_notification_routing_plan, evaluate_notification_delivery_fixture
from hate.post_poc.observability import build_incident_response_packet, evaluate_observability_fixture
from hate.post_poc.plugin_distribution import build_plugin_install_manifest, evaluate_plugin_distribution_fixture
from hate.post_poc.release_handoff import evaluate_release_handoff_fixture
from hate.post_poc.roster import build_roster_execution_manifest, evaluate_roster_fixture
from hate.post_poc.scheduler import build_scheduler_dispatch_plan, evaluate_scheduler_fixture
from hate.post_poc.store_dr import build_store_dr_runbook, evaluate_store_dr_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc"
SCHEMAS = ROOT / "schemas" / "HATE" / "v1"

CASE_MATRIX: list[tuple[str, str, Callable[[dict[str, Any]], dict[str, Any]], bool]] = [
    ("scheduler", "lease-acquire-heartbeat", evaluate_scheduler_fixture, False),
    ("dashboard", "portfolio-loaded", evaluate_dashboard_fixture, True),
    ("notifications", "slack-delivered", evaluate_notification_delivery_fixture, False),
    ("baseline", "propose-approve-freeze", evaluate_baseline_fixture, False),
    ("roster", "owned-repo-bootstrap", evaluate_roster_fixture, False),
    ("plugin-distribution", "signed-allowed", evaluate_plugin_distribution_fixture, False),
    ("connectors", "dry-run-no-side-effect", evaluate_connector_runtime_fixture, False),
    ("history", "flake-rate-trend", evaluate_history_analytics_fixture, False),
    ("docs-freshness", "readme-current", evaluate_docs_freshness_fixture, False),
    ("handoff", "qeg-approved-reference", evaluate_release_handoff_fixture, False),
    ("hosted-api", "tenant-allowed", evaluate_hosted_api_fixture, True),
    ("dr", "backup-restore-success", evaluate_store_dr_fixture, False),
    ("capacity", "100-repo-baseline", evaluate_capacity_fixture, False),
    ("compliance", "procurement-pack-valid", evaluate_compliance_fixture, False),
    ("observability", "telemetry-valid", evaluate_observability_fixture, True),
    ("human-review", "approve-with-evidence", evaluate_human_review_fixture, False),
]


def _fixture(area: str, case: str) -> dict[str, Any]:
    return json.loads((FIXTURES / area / case / "fixture.json").read_text(encoding="utf-8"))


def test_post_poc_reports_emit_shared_productization_envelope() -> None:
    for area, case, evaluator, requires_tenant in CASE_MATRIX:
        result = evaluator(_fixture(area, case))
        report = result["report"]

        assert report["record_id"], area
        assert report["created_at"], area
        assert report["unsafe_output_policy"] == "redact_unsafe_outputs", area
        assert report["decision_basis"], area
        assert report.get("actor") or report.get("system_actor"), area
        if requires_tenant:
            assert report["tenant_id"], area


def test_post_poc_report_schemas_require_shared_productization_envelope() -> None:
    for area, case, evaluator, _requires_tenant in CASE_MATRIX:
        report = evaluator(_fixture(area, case))["report"]
        schema_path = SCHEMAS / f"{report['record_type']}.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "unsafe_output_policy"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "unsafe_output_policy"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_manifest_packet_and_runbook_records_emit_shared_envelope() -> None:
    capacity_input = _fixture("capacity", "100-repo-baseline")["input"]
    records = [
        build_scheduler_dispatch_plan(_fixture("scheduler", "lease-acquire-heartbeat")["input"]),
        build_roster_execution_manifest(_fixture("roster", "owned-repo-bootstrap")["input"]),
        build_baseline_review_packet(_fixture("baseline", "propose-approve-freeze")["input"]),
        build_plugin_install_manifest(_fixture("plugin-distribution", "signed-allowed")["input"]),
        build_connector_execution_plan(_fixture("connectors", "dry-run-no-side-effect")["input"]),
        build_history_materialization_plan(_fixture("history", "flake-rate-trend")["input"]),
        build_notification_routing_plan(_fixture("notifications", "slack-delivered")["input"]),
        build_human_review_queue_packet(_fixture("human-review", "approve-with-evidence")["input"]),
        build_incident_response_packet(_fixture("observability", "telemetry-valid")["input"]),
        build_hosted_api_route_manifest(),
        build_store_dr_runbook(_fixture("dr", "backup-restore-success")["input"]),
        build_capacity_regression_packet(capacity_input, capacity_input),
    ]

    for record in records:
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_manifest_packet_and_runbook_schemas_require_shared_envelope() -> None:
    schema_names = [
        "hosted-scheduler-dispatch-manifest.schema.json",
        "real-repo-roster-execution-manifest.schema.json",
        "baseline-review-packet.schema.json",
        "history-materialization-manifest.schema.json",
        "human-review-queue-packet.schema.json",
        "notification-routing-manifest.schema.json",
        "incident-response-packet.schema.json",
        "plugin-install-manifest.schema.json",
        "connector-execution-manifest.schema.json",
        "hosted-api-route-manifest.schema.json",
        "store-dr-runbook.schema.json",
        "capacity-regression-packet.schema.json",
    ]

    for schema_name in schema_names:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_registered_nested_step_records_emit_shared_envelope() -> None:
    connector_plan = build_connector_execution_plan(_fixture("connectors", "dry-run-no-side-effect")["input"])
    runbook = build_store_dr_runbook(_fixture("dr", "backup-restore-success")["input"])
    records = connector_plan["steps"] + runbook["steps"]

    for record in records:
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["sourceRefs"], record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_registered_nested_step_schemas_require_shared_envelope() -> None:
    for schema_name in ["connector-execution-step.schema.json", "store-dr-runbook-step.schema.json"]:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_scheduler_runtime_nested_records_are_registered_and_enveloped() -> None:
    report = evaluate_scheduler_fixture(_fixture("scheduler", "lease-acquire-heartbeat"))["report"]
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    registered = {record["record_type"] for record in registry["records"]}
    records = [report["worker_state"], *report["lease_events"], *report["job_results"]]

    assert {"hosted-scheduler-worker-state", "hosted-scheduler-lease-event", "hosted-scheduler-job-result"} <= registered
    for record in records:
        assert record["record_type"] in registered
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["sourceRefs"], record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_scheduler_runtime_nested_schemas_require_shared_envelope() -> None:
    for schema_name in [
        "hosted-scheduler-worker-state.schema.json",
        "hosted-scheduler-lease-event.schema.json",
        "hosted-scheduler-job-result.schema.json",
    ]:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_notification_delivery_nested_records_are_registered_and_enveloped() -> None:
    report = evaluate_notification_delivery_fixture(_fixture("notifications", "dead-lettered"))["report"]
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    registered = {record["record_type"] for record in registry["records"]}
    records = [report["delivery_plan"], *report["delivery_attempts"], *report["dead_letter_events"]]

    assert {"notification-delivery-plan", "notification-delivery-attempt", "notification-dead-letter-event"} <= registered
    for record in records:
        assert record["record_type"] in registered
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["sourceRefs"], record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_notification_delivery_nested_schemas_require_shared_envelope() -> None:
    for schema_name in [
        "notification-delivery-plan.schema.json",
        "notification-delivery-attempt.schema.json",
        "notification-dead-letter-event.schema.json",
    ]:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_baseline_promotion_nested_records_are_registered_and_enveloped() -> None:
    report = evaluate_baseline_fixture(_fixture("baseline", "propose-approve-freeze"))["report"]
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    registered = {record["record_type"] for record in registry["records"]}
    records = [report["baseline_state"], *report["promotion_requests"], *report["promotion_decisions"], *report["immutability_events"]]

    assert {"baseline-state", "baseline-promotion-request", "baseline-promotion-decision", "baseline-immutability-event"} <= registered
    for record in records:
        assert record["record_type"] in registered
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["sourceRefs"], record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_baseline_promotion_nested_schemas_require_shared_envelope() -> None:
    for schema_name in [
        "baseline-state.schema.json",
        "baseline-promotion-request.schema.json",
        "baseline-promotion-decision.schema.json",
        "baseline-immutability-event.schema.json",
    ]:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_baseline_review_nested_records_are_registered_and_enveloped() -> None:
    input_data = json.loads(json.dumps(_fixture("baseline", "propose-approve-freeze")["input"]))
    input_data["comparison"] = {
        "previous_baseline_ref": "baseline://base-1000",
        "previous_score": 0.92,
        "candidate_score": 0.95,
        "previous_regression_count": 1,
        "candidate_regression_count": 0,
        "comparison_artifact_ref": "artifact://baseline/base-1001/comparison.json",
    }
    packet = build_baseline_review_packet(input_data, source_refs=["fixture://baseline/review-ready"])
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    registered = {record["record_type"] for record in registry["records"]}
    records = [packet["comparison"], *packet["review_items"]]

    assert {"baseline-review-comparison", "baseline-review-item"} <= registered
    for record in records:
        assert record["record_type"] in registered
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["sourceRefs"], record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_baseline_review_nested_schemas_require_shared_envelope() -> None:
    for schema_name in [
        "baseline-review-comparison.schema.json",
        "baseline-review-item.schema.json",
    ]:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_roster_maintenance_nested_records_are_registered_and_enveloped() -> None:
    report = evaluate_roster_fixture(_fixture("roster", "stale-repo-quarantined"))["report"]
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    registered = {record["record_type"] for record in registry["records"]}
    records = [*report["maintenance_plans"], *report["environment_recipes"], *report["quarantine_events"]]

    assert {"real-repo-roster-maintenance-plan", "real-repo-environment-recipe", "real-repo-quarantine-event"} <= registered
    for record in records:
        assert record["record_type"] in registered
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["sourceRefs"], record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_roster_maintenance_nested_schemas_require_shared_envelope() -> None:
    for schema_name in [
        "real-repo-roster-maintenance-plan.schema.json",
        "real-repo-environment-recipe.schema.json",
        "real-repo-quarantine-event.schema.json",
    ]:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_history_nested_records_are_registered_and_enveloped() -> None:
    fixture = _fixture("history", "flake-rate-trend")
    report = evaluate_history_analytics_fixture(fixture)["report"]
    plan = build_history_materialization_plan(fixture["input"])
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    registered = {record["record_type"] for record in registry["records"]}
    records = [report["query"], report["trend_window"], report["result"], plan["incremental"], *plan["entries"]]

    assert {
        "history-analytics-query",
        "history-trend-window",
        "history-analytics-result",
        "history-incremental-materialization",
        "history-materialization-entry",
    } <= registered
    for record in records:
        assert record["record_type"] in registered
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["sourceRefs"], record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_history_nested_schemas_require_shared_envelope() -> None:
    for schema_name in [
        "history-analytics-query.schema.json",
        "history-trend-window.schema.json",
        "history-analytics-result.schema.json",
        "history-incremental-materialization.schema.json",
        "history-materialization-entry.schema.json",
    ]:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_notification_routing_nested_records_are_registered_and_enveloped() -> None:
    delivery_report = evaluate_notification_delivery_fixture(_fixture("notifications", "duplicate-suppressed"))["report"]
    routing_plan = build_notification_routing_plan({
        "operating_record": {
            "operating_record_id": "finding:OPEN-1",
            "owner": "alice@example.com",
            "team": "quality",
            "payload_hash": "sha256:payload",
            "redaction_report_ref": "artifact://redaction/report.json",
            "sourceRef": "finding://OPEN-1",
        },
        "subscribers": [
            {
                "subscriber_id": "owner-alice",
                "owner": "alice@example.com",
                "delivery_target": "email",
                "target_ref": "mailto:alice@example.com",
                "sourceRef": "subscriber://alice",
            }
        ],
    }, source_refs=["fixture://notifications/routing"])
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    registered = {record["record_type"] for record in registry["records"]}
    records = [
        *delivery_report["audit_events"],
        routing_plan,
        routing_plan["operating_record"],
        *routing_plan["subscribers"],
        *routing_plan["routing_entries"],
    ]

    assert {
        "notification-audit-event",
        "notification-routing-plan",
        "notification-operating-record",
        "notification-subscriber",
        "notification-routing-entry",
    } <= registered
    for record in records:
        assert record["record_type"] in registered
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["sourceRefs"], record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_notification_routing_nested_schemas_require_shared_envelope() -> None:
    for schema_name in [
        "notification-audit-event.schema.json",
        "notification-routing-plan.schema.json",
        "notification-operating-record.schema.json",
        "notification-subscriber.schema.json",
        "notification-routing-entry.schema.json",
    ]:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_plugin_distribution_nested_records_are_registered_and_enveloped() -> None:
    fixture = _fixture("plugin-distribution", "signed-allowed")
    report = evaluate_plugin_distribution_fixture(fixture)["report"]
    install_manifest = build_plugin_install_manifest(fixture["input"])
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    registered = {record["record_type"] for record in registry["records"]}
    records = [
        report["package_manifest"],
        report["signature_verification"],
        report["revocation_event"],
        report["distribution_index"],
        *install_manifest["entries"],
    ]

    assert {
        "plugin-package-manifest",
        "plugin-signature-verification",
        "plugin-revocation-event",
        "plugin-distribution-index",
        "plugin-install-entry",
    } <= registered
    for record in records:
        assert record["record_type"] in registered
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["sourceRefs"], record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_plugin_distribution_nested_schemas_require_shared_envelope() -> None:
    for schema_name in [
        "plugin-package-manifest.schema.json",
        "plugin-signature-verification.schema.json",
        "plugin-revocation-event.schema.json",
        "plugin-distribution-index.schema.json",
        "plugin-install-entry.schema.json",
    ]:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_hosted_api_nested_records_are_registered_and_enveloped() -> None:
    report = evaluate_hosted_api_fixture(_fixture("hosted-api", "tenant-allowed"))["report"]
    manifest = build_hosted_api_route_manifest(source_refs=["spec://hosted-api"])
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    registered = {record["record_type"] for record in registry["records"]}
    records = [report["request_record"], report["authz_decision"], report["rate_limit_event"], *manifest["routes"]]

    assert {
        "hosted-api-request-record",
        "hosted-authz-decision-record",
        "hosted-rate-limit-event",
        "hosted-api-route-contract",
    } <= registered
    for record in records:
        assert record["record_type"] in registered
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["sourceRefs"], record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_hosted_api_nested_schemas_require_shared_envelope() -> None:
    for schema_name in [
        "hosted-api-request-record.schema.json",
        "hosted-authz-decision-record.schema.json",
        "hosted-rate-limit-event.schema.json",
        "hosted-api-route-contract.schema.json",
    ]:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_connector_nested_records_are_registered_and_enveloped() -> None:
    fixture = _fixture("connectors", "fake-ticket-live-success")
    report = evaluate_connector_runtime_fixture(fixture)["report"]
    execution_plan = build_connector_execution_plan(fixture["input"])
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    registered = {record["record_type"] for record in registry["records"]}
    records = [
        report["runtime_plan"],
        *report["runtime_attempts"],
        *report["idempotency_records"],
        *report["rollback_visibility_records"],
        execution_plan,
    ]

    assert {
        "connector-runtime-plan",
        "connector-runtime-attempt",
        "connector-idempotency-record",
        "connector-rollback-visibility-record",
        "connector-execution-plan",
    } <= registered
    for record in records:
        assert record["record_type"] in registered
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["sourceRefs"], record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_connector_nested_schemas_require_shared_envelope() -> None:
    for schema_name in [
        "connector-runtime-plan.schema.json",
        "connector-runtime-attempt.schema.json",
        "connector-idempotency-record.schema.json",
        "connector-rollback-visibility-record.schema.json",
        "connector-execution-plan.schema.json",
    ]:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_human_review_nested_records_are_registered_and_enveloped() -> None:
    fixture = _fixture("human-review", "approve-with-evidence")
    report = evaluate_human_review_fixture(fixture)["report"]
    packet = build_human_review_queue_packet(fixture["input"])
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    registered = {record["record_type"] for record in registry["records"]}
    records = [
        report["review_state"],
        *report["requests"],
        *report["decisions"],
        *report["attachments"],
        packet["queue_item"],
    ]

    assert {
        "human-review-workflow-state",
        "human-review-workflow-request",
        "human-review-workflow-decision",
        "human-review-evidence-attachment",
        "human-review-queue-item",
    } <= registered
    for record in records:
        assert record["record_type"] in registered
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["sourceRefs"], record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_human_review_nested_schemas_require_shared_envelope() -> None:
    for schema_name in [
        "human-review-workflow-state.schema.json",
        "human-review-workflow-request.schema.json",
        "human-review-workflow-decision.schema.json",
        "human-review-evidence-attachment.schema.json",
        "human-review-queue-item.schema.json",
    ]:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_observability_nested_records_are_registered_and_enveloped() -> None:
    fixture = _fixture("observability", "telemetry-valid")
    report = evaluate_observability_fixture(fixture)["report"]
    packet = build_incident_response_packet(fixture["input"])
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    registered = {record["record_type"] for record in registry["records"]}
    records = [
        *report["runtime_telemetry_events"],
        report["slo_burn_rate_report"],
        report["incident_lifecycle_record"],
        report["post_incident_evidence_pack"],
        packet["support_pack"],
        *packet["actions"],
    ]

    assert {
        "runtime-telemetry-event",
        "slo-burn-rate-report",
        "incident-lifecycle-record",
        "post-incident-evidence-pack",
        "incident-response-action",
    } <= registered
    for record in records:
        assert record["record_type"] in registered
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["sourceRefs"], record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_observability_nested_schemas_require_shared_envelope() -> None:
    for schema_name in [
        "runtime-telemetry-event.schema.json",
        "slo-burn-rate-report.schema.json",
        "incident-lifecycle-record.schema.json",
        "post-incident-evidence-pack.schema.json",
        "incident-response-action.schema.json",
    ]:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_store_dr_nested_records_are_registered_and_enveloped() -> None:
    report = evaluate_store_dr_fixture(_fixture("dr", "backup-restore-success"))["report"]
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    registered = {record["record_type"] for record in registry["records"]}
    records = [report["backup_operation"], report["restore_operation"], report["dr_drill_result"]]

    assert {"store-backup-operation", "store-restore-operation", "store-dr-drill-result"} <= registered
    for record in records:
        assert record["record_type"] in registered
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["sourceRefs"], record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_store_dr_nested_schemas_require_shared_envelope() -> None:
    for schema_name in [
        "store-backup-operation.schema.json",
        "store-restore-operation.schema.json",
        "store-dr-drill-result.schema.json",
    ]:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_source_record_types_are_registered() -> None:
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    registered = {record["record_type"] for record in registry["records"]}
    source_records: set[str] = set()
    for path in (ROOT / "src" / "hate" / "post_poc").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        source_records.update(__import__("re").findall(r'"record_type"\s*:\s*"([^"]+)"', text))
        source_records.update(__import__("re").findall(r'record_type"\]\s*=\s*"([^"]+)"', text))

    assert sorted(source_records - registered) == []


def test_post_poc_registry_schema_paths_exist() -> None:
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    missing_paths = [
        record["schema"]
        for record in registry["records"]
        if str(record.get("phase")) == "Post-PoC"
        and not (ROOT / record["schema"]).exists()
    ]

    assert missing_paths == []


def test_post_poc_capacity_compliance_dashboard_and_handoff_nested_records_are_registered_and_enveloped() -> None:
    capacity_input = _fixture("capacity", "100-repo-baseline")["input"]
    capacity_report = evaluate_capacity_fixture(_fixture("capacity", "100-repo-baseline"))["report"]
    capacity_packet = build_capacity_regression_packet(capacity_input, capacity_input)
    compliance_report = evaluate_compliance_fixture(_fixture("compliance", "procurement-pack-valid"))["report"]
    dashboard_report = evaluate_dashboard_fixture(_fixture("dashboard", "portfolio-loaded"))["report"]
    handoff_report = evaluate_release_handoff_fixture(_fixture("handoff", "qeg-approved-reference"))["report"]
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    registered = {record["record_type"] for record in registry["records"]}
    records = [
        *capacity_report["benchmark_runs"],
        capacity_report["baseline_record"],
        *capacity_packet["comparisons"],
        compliance_report["compliance_evidence_pack"],
        compliance_report["procurement_questionnaire_export"],
        *compliance_report["control_claims"],
        *compliance_report["review_decisions"],
        dashboard_report["session_view"],
        *dashboard_report["route_states"],
        *dashboard_report["action_intents"],
        handoff_report["handoff_request"],
        handoff_report["handoff_result"],
        handoff_report["external_approval_reference"],
    ]

    assert {
        "capacity-benchmark-run",
        "capacity-baseline-record",
        "capacity-regression-comparison",
        "compliance-evidence-pack",
        "procurement-questionnaire-export",
        "control-claim-record",
        "compliance-review-decision",
        "dashboard-session-view",
        "dashboard-route-state",
        "dashboard-action-intent",
        "external-release-handoff-request",
        "external-release-handoff-result",
        "external-approval-reference",
    } <= registered
    for record in records:
        assert record["record_type"] in registered
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["sourceRefs"], record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_capacity_compliance_dashboard_and_handoff_nested_schemas_require_shared_envelope() -> None:
    for schema_name in [
        "capacity-benchmark-run.schema.json",
        "capacity-baseline-record.schema.json",
        "capacity-regression-comparison.schema.json",
        "compliance-evidence-pack.schema.json",
        "procurement-questionnaire-export.schema.json",
        "control-claim-record.schema.json",
        "compliance-review-decision.schema.json",
        "dashboard-session-view.schema.json",
        "dashboard-route-state.schema.json",
        "dashboard-action-intent.schema.json",
        "external-release-handoff-request.schema.json",
        "external-release-handoff-result.schema.json",
        "external-approval-reference.schema.json",
    ]:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]


def test_post_poc_history_scheduler_and_roster_plan_records_are_registered_and_enveloped() -> None:
    history_plan = build_history_materialization_plan(_fixture("history", "flake-rate-trend")["input"])
    scheduler_plan = build_scheduler_dispatch_plan(_fixture("scheduler", "lease-acquire-heartbeat")["input"])
    roster_manifest = build_roster_execution_manifest(_fixture("roster", "owned-repo-bootstrap")["input"])
    registry = json.loads((SCHEMAS / "schema-registry.json").read_text(encoding="utf-8"))
    registered = {record["record_type"] for record in registry["records"]}
    records = [history_plan, scheduler_plan, *scheduler_plan["dispatch_entries"], *roster_manifest["entries"]]

    assert {
        "history-materialization-plan",
        "hosted-scheduler-dispatch-plan",
        "hosted-scheduler-dispatch-entry",
        "real-repo-roster-execution-entry",
    } <= registered
    for record in records:
        assert record["record_type"] in registered
        assert record["record_id"], record["record_type"]
        assert record["created_at"], record["record_type"]
        assert record["decision_basis"], record["record_type"]
        assert record["readiness_effect"] in {"none", "hold"}, record["record_type"]
        assert record["unsafe_output_policy"] == "redact_unsafe_outputs", record["record_type"]
        assert record["sourceRefs"], record["record_type"]
        assert record.get("actor") or record.get("system_actor"), record["record_type"]


def test_post_poc_history_scheduler_and_roster_plan_schemas_require_shared_envelope() -> None:
    for schema_name in [
        "history-materialization-plan.schema.json",
        "hosted-scheduler-dispatch-plan.schema.json",
        "hosted-scheduler-dispatch-entry.schema.json",
        "real-repo-roster-execution-entry.schema.json",
    ]:
        schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))

        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["required"])
        assert {"record_id", "created_at", "decision_basis", "readiness_effect", "unsafe_output_policy", "sourceRefs"} <= set(schema["properties"])
        assert {"required": ["actor"]} in schema["anyOf"]
        assert {"required": ["system_actor"]} in schema["anyOf"]
