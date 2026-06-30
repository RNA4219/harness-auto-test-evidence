from __future__ import annotations

import json
from pathlib import Path

from hate.gap_closure import generate_gap_closure_report
from hate.runtime_worker import evaluate_worker_runtime_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "runtime" / "worker"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name / "fixture.json").read_text(encoding="utf-8"))


def test_successful_ingest_reaches_succeeded_with_bundle_hash() -> None:
    report = evaluate_worker_runtime_fixture(_load_fixture("successful-ingest"), source_version="test")

    assert report["record_type"] == "worker-runtime-report"
    assert report["status"] == "pass"
    assert report["job"]["status"] == "succeeded"
    assert report["job"]["artifacts"][0]["hash"].startswith("sha256:")
    assert report["job"]["audit_events"][0]["event_type"] == "lease_acquired"


def test_worker_runtime_report_schema_is_registered() -> None:
    registry = json.loads((ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas" / "HATE" / "v1" / "worker-runtime-report.schema.json").read_text(encoding="utf-8"))
    report = evaluate_worker_runtime_fixture(_load_fixture("successful-ingest"))

    assert any(item["record_type"] == "worker-runtime-report" for item in registry["records"])
    for field in schema["required"]:
        assert field in report
    for field in schema["properties"]["job"]["required"]:
        assert field in report["job"]


def test_retry_then_success_preserves_retry_wait_before_success() -> None:
    report = evaluate_worker_runtime_fixture(_load_fixture("retry-then-success"))

    assert report["status"] == "pass"
    assert report["job"]["status"] == "succeeded"
    assert "retry_wait" in report["job"]["worker_events"]
    assert report["job"]["attempts"] == 2


def test_cancel_running_preserves_partial_evidence() -> None:
    report = evaluate_worker_runtime_fixture(_load_fixture("cancel-running"))

    assert report["status"] == "pass"
    assert report["job"]["status"] == "cancelled"
    assert report["job"]["artifacts"][0]["retention_class"] == "partial"
    assert report["job"]["audit_events"][-1]["event_type"] == "job_cancelled"


def test_poison_message_emits_visible_audit_and_hold() -> None:
    report = evaluate_worker_runtime_fixture(_load_fixture("poison-message"))

    assert report["status"] == "hold"
    assert report["finding_code"] == "worker_poison_message"
    assert report["job"]["status"] == "poison"
    assert report["job"]["audit_events"][-1]["event_type"] == "poison_message"


def test_idempotency_key_is_required_for_mutating_job_creation() -> None:
    fixture = _load_fixture("successful-ingest")
    fixture["input"]["job"].pop("idempotency_key")

    report = evaluate_worker_runtime_fixture(fixture)

    assert report["status"] == "hold"
    assert report["finding_code"] == "worker_idempotency_key_missing"
    assert report["job"]["status"] == "failed"


def test_gap_closure_uses_worker_runtime_evaluator_for_gap_001(tmp_path: Path) -> None:
    report = generate_gap_closure_report(ROOT, tmp_path, source_version="runtime-worker-test")
    gap_001 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-001")

    assert gap_001["status"] == "implemented"
    assert gap_001["implementation_evidence"]["runtime_module"] == "src/hate/runtime_worker.py"
    assert "tests/test_runtime_worker.py" in gap_001["implementation_evidence"]["tests"]
