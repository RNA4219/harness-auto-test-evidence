"""Tests for HATE-GAP-021 workflow Task Seed loop evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from hate.workflow_task_seed import build_task_seed_report, evaluate_task_seed_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "workflow" / "task-seed"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "workflow-task-seed-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _valid_seed() -> dict:
    return {
        "task_seed": {
            "task_id": "TASK-HATE-GAP-021",
            "objective": "Implement Task Seed projection and validation",
            "scope": {
                "in": ["src/hate/workflow_task_seed.py", "tests/test_workflow_task_seed.py"],
                "out": ["external issue tracker sync"],
            },
            "requirements": {
                "behavior": ["valid task seeds include required fields"],
                "constraints": ["task seed slices target <=0.5d"],
            },
            "commands": ["uv run pytest tests/test_workflow_task_seed.py -q"],
            "dependencies": ["WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md#task-seed-loop"],
        }
    }


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "workflow-task-seed-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    assert set(schema["properties"]["task_seed"]["required"]) <= set(report["task_seed"])
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_canonical_gap_021_fixture_paths_exist() -> None:
    assert (FIXTURES / "valid-packet" / "fixture.json").is_file()
    assert (FIXTURES / "missing-scope" / "fixture.json").is_file()


def test_valid_task_seed_fixture_passes() -> None:
    result = evaluate_task_seed_fixture(_fixture("valid-packet"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    _assert_report_contract(result["report"])
    assert result["report"]["task_seed"]["task_id"] == "TASK-HATE-GAP-021"


def test_missing_scope_fixture_holds() -> None:
    result = evaluate_task_seed_fixture(_fixture("missing-scope"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "task_seed_missing_scope"
    assert result["readiness_effect"] == "hold"
    _assert_report_contract(result["report"])


def test_missing_required_fields_are_reported() -> None:
    report = build_task_seed_report({"task_seed": {"task_id": "TASK-HATE-GAP-021"}})

    assert report["overall_status"] == "hold"
    assert "task_seed_missing_objective" in _codes(report)
    assert "task_seed_missing_scope" in _codes(report)
    assert "task_seed_missing_behavior" in _codes(report)
    assert "task_seed_missing_constraints" in _codes(report)
    assert "task_seed_missing_commands" in _codes(report)
    assert "task_seed_missing_dependencies" in _codes(report)


def test_hidden_future_optional_advisory_language_is_hold() -> None:
    seed = _valid_seed()
    seed["task_seed"]["requirements"]["constraints"] = ["optional future tracker sync may cover this later"]

    report = build_task_seed_report(seed)

    assert report["overall_status"] == "hold"
    assert "task_seed_hides_missing_work" in _codes(report)


def test_slice_over_half_day_is_hold() -> None:
    seed = _valid_seed()
    seed["task_seed"]["slice_days"] = 0.75

    report = build_task_seed_report(seed)

    assert report["overall_status"] == "hold"
    assert "task_seed_slice_too_large" in _codes(report)


def test_large_packet_requires_split_seeds() -> None:
    seed = _valid_seed()
    seed["task_seed"]["packet_size_days"] = 2.0

    report = build_task_seed_report(seed)

    assert report["overall_status"] == "hold"
    assert "task_seed_large_packet_unsplit" in _codes(report)


def test_generated_artifact_change_requires_birdseye_update_plan() -> None:
    seed = _valid_seed()
    seed["task_seed"]["changes_generated_artifacts"] = True
    seed["task_seed"]["birdseye_update"] = False

    report = build_task_seed_report(seed)

    assert report["overall_status"] == "hold"
    assert "task_seed_birdseye_update_missing" in _codes(report)


def test_done_task_seed_requires_acceptance_or_exception() -> None:
    seed = _valid_seed()
    seed["task_seed"]["status"] = "done"

    report = build_task_seed_report(seed)

    assert report["overall_status"] == "hold"
    assert "task_seed_done_missing_acceptance" in _codes(report)


def test_done_task_seed_with_acceptance_can_pass() -> None:
    seed = _valid_seed()
    seed["task_seed"]["status"] = "done"
    seed["task_seed"]["acceptance_record"] = "docs/acceptance/AC-20260630-01.md"

    report = build_task_seed_report(seed)

    assert report["overall_status"] == "pass"
    assert report["findings"] == []


def test_workflow_task_seed_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["workflow-task-seed-report"] == "schemas/HATE/v1/workflow-task-seed-report.schema.json"
