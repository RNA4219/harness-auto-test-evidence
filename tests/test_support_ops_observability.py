"""UAT tests for support operations observability reports."""

from __future__ import annotations

import json
from pathlib import Path

from hate.support_ops import build_support_ops_report


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "support-ops" / "observability"
SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "HATE"
    / "v1"
    / "support-ops-report.schema.json"
)


def load_fixture(name: str) -> dict:
    with (FIXTURE_ROOT / name / "fixture.json").open(encoding="utf-8") as f:
        return json.load(f)


def report_from_fixture(name: str) -> tuple[dict, dict]:
    fixture = load_fixture(name)
    return build_support_ops_report(fixture["input"]), fixture["expected"]


def test_packet_fixture_paths_exist() -> None:
    for name in [
        "logs-valid",
        "metrics-valid",
        "alerts-valid",
        "incident-trigger",
        "raw-secret-log",
        "missing-release-metric",
    ]:
        assert (FIXTURE_ROOT / name / "fixture.json").exists()


def test_structured_logs_valid() -> None:
    report, expected = report_from_fixture("logs-valid")

    assert report["overall_status"] == expected["overall_status"]
    assert report["summary"]["log_count"] == expected["log_count"]
    assert report["summary"]["finding_count"] == expected["finding_count"]
    assert report["logs"][0]["correlation_id"] == "corr-001"


def test_metrics_valid_for_release_profile() -> None:
    report, expected = report_from_fixture("metrics-valid")

    assert report["overall_status"] == expected["overall_status"]
    assert report["summary"]["metric_count"] == expected["metric_count"]
    assert report["summary"]["finding_count"] == expected["finding_count"]


def test_alerts_valid_without_incident() -> None:
    report, expected = report_from_fixture("alerts-valid")

    assert report["overall_status"] == expected["overall_status"]
    assert report["summary"]["alert_count"] == expected["alert_count"]
    assert report["summary"]["incident_count"] == expected["incident_count"]
    assert report["alerts"][0]["triggered"] is False


def test_incident_trigger_projection() -> None:
    report, expected = report_from_fixture("incident-trigger")

    assert report["overall_status"] == expected["overall_status"]
    assert report["summary"]["incident_count"] == expected["incident_count"]
    assert report["incidents"][0]["class"] == expected["incident_class"]
    assert report["incidents"][0]["severity"] == expected["severity"]


def test_raw_secret_log_is_redacted_or_removed() -> None:
    report, expected = report_from_fixture("raw-secret-log")

    assert report["overall_status"] == expected["overall_status"]
    assert any(item["code"] == expected["finding_code"] for item in report["findings"])
    serialized = json.dumps(report, sort_keys=True)
    for forbidden in expected["forbidden"]:
        assert forbidden not in serialized
    assert report["logs"][0]["redaction_status"] == "redacted"


def test_missing_release_metric_holds() -> None:
    report, expected = report_from_fixture("missing-release-metric")

    assert report["overall_status"] == expected["overall_status"]
    missing = [item for item in report["findings"] if item["code"] == expected["finding_code"]]
    assert len(missing) == expected["missing_count"]
    assert all(item["readiness_effect"] == "hold" for item in missing)


def test_support_ops_schema_contract() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["record_type"]["const"] == "support-ops-report"
    assert set(schema["required"]) >= {
        "schema_version",
        "record_type",
        "report_id",
        "overall_status",
        "logs",
        "metrics",
        "alerts",
        "incidents",
        "findings",
        "sourceRefs",
    }
