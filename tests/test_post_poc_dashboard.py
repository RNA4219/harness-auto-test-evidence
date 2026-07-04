from __future__ import annotations

import json
from pathlib import Path

from hate.post_poc.dashboard import (
    build_dashboard_interaction_report,
    evaluate_dashboard_fixture,
    render_dashboard_static_html,
    write_dashboard_static_html,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc" / "dashboard"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "dashboard-interaction-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "dashboard-interaction-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert report["session_view"]["record_type"] == "dashboard-session-view"
    for route in report["route_states"]:
        assert route["record_type"] == "dashboard-route-state"
        assert route["sourceRefs"]
    for action in report["action_intents"]:
        assert action["record_type"] == "dashboard-action-intent"
        assert action["sourceRefs"]
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_task_postpoc_002_canonical_fixture_paths_exist() -> None:
    for name in [
        "portfolio-loaded",
        "permission-denied",
        "stale-read-model",
        "unsafe-artifact-hidden",
        "manual-review-action",
    ]:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_portfolio_loaded_passes() -> None:
    result = evaluate_dashboard_fixture(_fixture("portfolio-loaded"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["report"]["route_states"][0]["route"] == "/dashboard/portfolio"
    _assert_report_contract(result["report"])


def test_permission_denied_state_passes_when_rbac_denied_is_explicit() -> None:
    result = evaluate_dashboard_fixture(_fixture("permission-denied"))

    assert result["status"] == "pass"
    assert result["report"]["summary"]["permission_denied_count"] == 1
    denied = [route for route in result["report"]["route_states"] if route["ui_state"] == "permission_denied"][0]
    assert denied["rbac_decision"] == "denied"


def test_stale_read_model_state_is_visible() -> None:
    result = evaluate_dashboard_fixture(_fixture("stale-read-model"))

    assert result["status"] == "pass"
    assert result["report"]["route_states"][0]["ui_state"] == "stale"
    assert "stale=true" in result["report"]["route_states"][0]["read_model_ref"]


def test_unsafe_artifact_hidden_passes_without_visible_body() -> None:
    result = evaluate_dashboard_fixture(_fixture("unsafe-artifact-hidden"))

    assert result["status"] == "pass"
    assert result["report"]["summary"]["unsafe_hidden_count"] == 1
    hidden = [route for route in result["report"]["route_states"] if route["ui_state"] == "unsafe_artifact_hidden"][0]
    assert hidden["hidden_reason"]
    assert hidden["unsafe_artifact_body_visible"] is False


def test_manual_review_action_is_auditable_intent() -> None:
    result = evaluate_dashboard_fixture(_fixture("manual-review-action"))

    assert result["status"] == "pass"
    assert result["report"]["summary"]["action_intent_count"] == 1
    intent = result["report"]["action_intents"][0]
    assert intent["actor"] == "qa@example.com"
    assert intent["idempotency_key"] == "manual-review-risk-001"


def test_dashboard_must_not_recompute_verdicts() -> None:
    report = build_dashboard_interaction_report({
        "session": {"authenticated": True, "actor": "qa"},
        "routes": [
            {
                "route": "/dashboard/portfolio",
                "ui_state": "loaded",
                "read_model_ref": "read-model://portfolio",
                "rbac_decision": "allowed",
                "canonical_verdict_ref": "product-readiness-report.json",
                "recomputed_verdict": True,
                "sourceRefs": ["route"],
            }
        ],
    })

    assert report["overall_status"] == "hold"
    assert "dashboard_recomputed_verdict" in _codes(report)


def test_dashboard_must_not_show_unsafe_body_or_raw_payload() -> None:
    report = build_dashboard_interaction_report({
        "session": {"authenticated": True, "actor": "qa"},
        "routes": [
            {
                "route": "/dashboard/portfolio",
                "ui_state": "loaded",
                "read_model_ref": "read-model://portfolio",
                "rbac_decision": "allowed",
                "canonical_verdict_ref": "product-readiness-report.json",
                "unsafe_artifact_body_visible": True,
                "raw_connector_payload_visible": True,
                "sourceRefs": ["route"],
            }
        ],
    })

    assert report["overall_status"] == "hold"
    assert "dashboard_unsafe_body_visible" in _codes(report)


def test_dashboard_action_requires_auditable_intent_fields() -> None:
    report = build_dashboard_interaction_report({
        "session": {"authenticated": True, "actor": "qa"},
        "routes": [
            {
                "route": "/dashboard/portfolio",
                "ui_state": "loaded",
                "read_model_ref": "read-model://portfolio",
                "rbac_decision": "allowed",
                "canonical_verdict_ref": "product-readiness-report.json",
                "sourceRefs": ["route"],
            }
        ],
        "actions": [{"action_type": "request_manual_review"}],
    })

    assert report["overall_status"] == "hold"
    assert "dashboard_action_intent_missing" in _codes(report)


def test_permission_denied_requires_matching_state() -> None:
    report = build_dashboard_interaction_report({
        "session": {"authenticated": True, "actor": "qa"},
        "routes": [
            {
                "route": "/dashboard/portfolio",
                "ui_state": "loaded",
                "read_model_ref": "read-model://portfolio",
                "rbac_decision": "denied",
                "canonical_verdict_ref": "product-readiness-report.json",
                "sourceRefs": ["route"],
            }
        ],
    })

    assert report["overall_status"] == "hold"
    assert "dashboard_rbac_denied_state_required" in _codes(report)


def test_dashboard_interaction_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["dashboard-interaction-report"] == "schemas/HATE/v1/dashboard-interaction-report.schema.json"


def test_static_dashboard_html_renders_canonical_route_and_actor() -> None:
    report = evaluate_dashboard_fixture(_fixture("portfolio-loaded"))["report"]

    html = render_dashboard_static_html(report)

    assert "<!doctype html>" in html
    assert "HATE Dashboard Evidence" in html
    assert "qa@example.com" in html
    assert "/dashboard/portfolio" in html
    assert "product-readiness-report.json" in html


def test_static_dashboard_html_redacts_unsafe_artifact_body() -> None:
    report = evaluate_dashboard_fixture(_fixture("unsafe-artifact-hidden"))["report"]
    report["route_states"][1]["unsafe_artifact_body"] = "SECRET_TOKEN=should-not-render"
    report["route_states"][1]["raw_connector_payload"] = {"token": "should-not-render"}

    html = render_dashboard_static_html(report)

    assert "unsafe body redacted" in html
    assert "SECRET_TOKEN" not in html
    assert "should-not-render" not in html


def test_static_dashboard_html_preserves_permission_denied_state_without_private_payload() -> None:
    report = evaluate_dashboard_fixture(_fixture("permission-denied"))["report"]
    report["route_states"][1]["raw_connector_payload"] = {"audit_log": "private-audit-body"}

    html = render_dashboard_static_html(report)

    assert "permission_denied" in html
    assert "restricted view" in html
    assert "private-audit-body" not in html


def test_static_dashboard_html_artifact_write_contract(tmp_path: Path) -> None:
    report = evaluate_dashboard_fixture(_fixture("manual-review-action"))["report"]
    out_path = tmp_path / "dashboard.html"

    artifact = write_dashboard_static_html(report, out_path)

    assert artifact["record_type"] == "dashboard-static-html-artifact"
    assert artifact["source_report_id"] == report["report_id"]
    assert artifact["overall_status"] == "pass"
    assert out_path.read_text(encoding="utf-8").startswith("<!doctype html>")
