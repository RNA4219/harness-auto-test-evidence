from __future__ import annotations

import json
import sys
from pathlib import Path

from hate.cli import main
from hate.platform_ops import (
    build_platform_assignment_report,
    build_platform_schedule_plan,
    build_platform_score_report,
    run_platform_plugin,
)


ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_platform_schedule_plans_cache_retry_and_resume(tmp_path: Path) -> None:
    roster = tmp_path / "roster.json"
    history = tmp_path / "store" / "run_history.jsonl"
    _write_json(
        roster,
        {
            "repositories": [
                {"repo_id": "fresh", "suites": [{"suite_id": "unit"}]},
                {"repo_id": "held", "suites": [{"suite_id": "unit"}]},
                {"repo_id": "new", "suites": [{"suite_id": "unit"}]},
            ]
        },
    )
    history.parent.mkdir(parents=True)
    history.write_text(
        "\n".join([
            json.dumps({"repo_id": "fresh", "suite_id": "unit", "status": "pass", "finished_at": "2026-07-03T00:00:00Z", "run_id": "run-fresh"}),
            json.dumps({"repo_id": "held", "suite_id": "unit", "status": "hold", "finished_at": "2026-07-03T00:00:00Z", "run_id": "run-held"}),
        ])
        + "\n",
        encoding="utf-8",
    )

    report = build_platform_schedule_plan(
        roster,
        history.parent,
        cache_ttl_hours=24,
        retry_limit=2,
        now="2026-07-03T01:00:00Z",
    )

    by_repo = {task["repo_id"]: task for task in report["tasks"]}
    assert by_repo["fresh"]["action"] == "cache_hit"
    assert by_repo["fresh"]["cache"]["hit"] is True
    assert by_repo["held"]["action"] == "run"
    assert by_repo["held"]["retry"]["planned_attempts"] == 1
    assert by_repo["held"]["resume_token"] == "held:unit:run-held"
    assert by_repo["new"]["action"] == "run"
    assert report["summary"]["cache_hit_count"] == 1
    assert report["summary"]["run_count"] == 2


def test_platform_assign_holds_missing_owner_and_sla_breach(tmp_path: Path) -> None:
    source = tmp_path / "reports" / "report.json"
    _write_json(
        source,
        {
            "record_type": "test-report",
            "report_id": "R1",
            "findings": [
                {"code": "missing_owner", "severity": "high", "sourceRefs": ["a"]},
                {"code": "late", "severity": "critical", "owner": "team-a", "due_date": "2026-07-01T00:00:00Z", "sourceRefs": ["b"]},
                {"code": "ok", "severity": "medium", "owner": "team-b", "due_date": "2026-07-10T00:00:00Z", "sourceRefs": ["c"]},
            ],
        },
    )

    report = build_platform_assignment_report(source, now="2026-07-03T00:00:00Z")

    assert report["overall_status"] == "hold"
    assert report["summary"]["missing_owner_or_due_date_count"] == 1
    assert report["summary"]["sla_breach_count"] == 1
    assert {finding["code"] for finding in report["findings"]} == {
        "platform_assignment_missing_owner_or_due_date",
        "platform_assignment_sla_breached",
    }


def test_platform_plugin_run_executes_and_sandbox_validates_output(tmp_path: Path) -> None:
    manifest = tmp_path / "plugin.json"
    out = tmp_path / "plugin-report.json"
    _write_json(
        manifest,
        {
            "profile": "default",
            "plugin": {
                "plugin_id": "plugin-a",
                "detector_id": "det-a",
                "execution_mode": "subprocess_local",
                "signed": True,
            },
            "limits": {"timeout_ms": 5000, "max_output_bytes": 2000, "max_input_bytes": 2000},
            "execution": {
                "command": [
                    sys.executable,
                    "-c",
                    "import json; print(json.dumps({'schema_version':'HATE/v1','detector_id':'det-a','sourceRefs':['plugin']}))",
                ]
            },
        },
    )

    report = run_platform_plugin(manifest, out)

    assert report["record_type"] == "platform-plugin-run-report"
    assert report["overall_status"] == "pass"
    assert report["sandbox_report"]["output_decision"]["detector_scoped"] is True
    assert json.loads(out.read_text(encoding="utf-8"))["plugin_id"] == "plugin-a"


def test_platform_score_penalizes_regression_timeout_and_typecheck_oracle(tmp_path: Path) -> None:
    source = tmp_path / "real-repo.json"
    _write_json(
        source,
        {
            "record_type": "real-repo-evaluation-report",
            "repo_id": "repo-a",
            "suite_id": "typecheck",
            "overall_status": "hold",
            "ownership_scope": "owned",
            "timeout_recorded": True,
            "regressions": [{"code": "runtime"}],
            "current": {
                "record_count": 1,
                "runner_dialect": "typescript-typecheck",
                "unsafe_artifact_findings": 1,
            },
            "findings": [{"code": "real_repo_record_count_collapse"}],
            "sourceRefs": ["real-repo.json"],
        },
    )

    report = build_platform_score_report(source)
    score = report["scores"][0]

    assert report["record_type"] == "platform-score-report"
    assert score["score"] < 70
    assert score["score_breakdown"]["components"]["oracle_confidence"] == 0.4
    assert score["score_breakdown"]["penalties"]["timeout_penalty"] == 20.0
    assert any(item["kind"] == "penalty" for item in score["decision_basis"])


def test_platform_score_does_not_treat_unbaselined_external_hold_as_regression(tmp_path: Path) -> None:
    source = tmp_path / "external-hold.json"
    _write_json(
        source,
        {
            "record_type": "real-repo-evaluation-report",
            "repo_id": "external-repo",
            "suite_id": "pytest",
            "overall_status": "hold",
            "ownership_scope": "external",
            "finished_at": "2026-07-04T00:00:00Z",
            "regressions": [{"regression_class": "external_hold_detected"}],
            "current": {"record_count": 0, "runner_dialect": "pytest"},
            "findings": [{"code": "real_repo_external_hold_detected", "severity": "medium"}],
            "sourceRefs": ["external-hold"],
        },
    )

    report = build_platform_score_report(source)
    score = report["scores"][0]

    assert score["score_breakdown"]["components"]["stability_score"] == 1.0
    assert score["score_breakdown"]["penalties"]["regression_penalty"] == 0.0


def test_platform_score_reads_manifest_leaves_and_skips_aggregate(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "real-repo-repo-a-pytest.json",
        {
            "record_type": "real-repo-evaluation-report",
            "repo_id": "repo-a",
            "suite_id": "pytest",
            "overall_status": "pass",
            "ownership_scope": "owned",
            "current": {"record_count": 12, "runner_dialect": "pytest"},
            "sourceRefs": ["repo-a"],
        },
    )
    _write_json(
        tmp_path / "real-repo-evaluation-run-report.json",
        {
            "record_type": "real-repo-evaluation-run-report",
            "report_id": "real-repo-evaluation-run",
            "generated_reports": ["real-repo-repo-a-pytest.json"],
            "overall_status": "pass",
        },
    )

    report = build_platform_score_report(tmp_path / "real-repo-evaluation-run-report.json")

    assert report["summary"]["score_count"] == 1
    assert report["scores"][0]["repo_id"] == "repo-a"
    assert report["scores"][0]["suite_id"] == "pytest"


def test_platform_score_directory_with_manifest_does_not_double_count_leaves(tmp_path: Path) -> None:
    leaf = {
        "record_type": "real-repo-evaluation-report",
        "repo_id": "repo-a",
        "suite_id": "pytest",
        "overall_status": "pass",
        "ownership_scope": "owned",
        "current": {"record_count": 12, "runner_dialect": "pytest"},
        "sourceRefs": ["repo-a"],
    }
    _write_json(tmp_path / "real-repo-repo-a-pytest.json", leaf)
    _write_json(
        tmp_path / "real-repo-evaluation-run-report.json",
        {
            "record_type": "real-repo-evaluation-run-report",
            "report_id": "real-repo-evaluation-run",
            "generated_reports": ["real-repo-repo-a-pytest.json"],
            "overall_status": "pass",
        },
    )

    report = build_platform_score_report(tmp_path)

    assert report["summary"]["score_count"] == 1
    assert [item["repo_id"] for item in report["scores"]] == ["repo-a"]


def test_platform_score_penalizes_subset_reports(tmp_path: Path) -> None:
    source = tmp_path / "real-repo-subset.json"
    _write_json(
        source,
        {
            "record_type": "real-repo-evaluation-report",
            "repo_id": "repo-a",
            "suite_id": "smoke",
            "overall_status": "pass",
            "ownership_scope": "owned",
            "finished_at": "2026-07-04T00:00:00Z",
            "current": {"record_count": 10, "runner_dialect": "pytest"},
            "subset": {"is_subset": True, "proves_full_suite": False},
            "sourceRefs": ["subset"],
        },
    )

    report = build_platform_score_report(source)
    score = report["scores"][0]

    assert score["score_breakdown"]["penalties"]["subset_penalty"] == 12.0
    assert score["score"] == 78.0


def test_platform_cli_ops_and_daily_html(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    html = tmp_path / "daily.html"
    assign_out = tmp_path / "assign.json"
    _write_json(
        report,
        {
            "record_type": "test-report",
            "report_id": "R1",
            "overall_status": "hold",
            "findings": [{"code": "critical", "severity": "critical", "owner": "team-a", "due_date": "2026-07-10T00:00:00Z"}],
            "risk_debt": [{"debt_id": "D1", "owner": "team-a", "expiry": "2026-07-20"}],
            "manual_review_requests": [{"request_id": "MR1", "owner": "reviewer", "blocking": True}],
            "sourceRefs": ["report"],
        },
    )

    assert main(["platform", "assign", "--input", str(report), "--out", str(assign_out)]) == 0
    assert main(["platform", "report", "html", "--input", str(report), "--out", str(html)]) == 0

    document = html.read_text(encoding="utf-8")
    assert "HATE Platform Daily Report" in document
    assert "Operator Queue" in document
    assert "Risk Debt" in document
    assert "Manual Review" in document
    assert json.loads(assign_out.read_text(encoding="utf-8"))["record_type"] == "platform-assignment-report"


def test_platform_ops_record_types_are_registered_and_schema_compatible(tmp_path: Path) -> None:
    roster = tmp_path / "roster.json"
    history = tmp_path / "store" / "run_history.jsonl"
    source = tmp_path / "report.json"
    manifest = tmp_path / "plugin.json"
    _write_json(roster, {"repositories": [{"repo_id": "repo-a", "suites": [{"suite_id": "unit"}]}]})
    history.parent.mkdir(parents=True)
    history.write_text("", encoding="utf-8")
    _write_json(
        source,
        {
            "record_type": "test-report",
            "repo_id": "repo-a",
            "suite_id": "unit",
            "overall_status": "pass",
            "ownership_scope": "owned",
            "current": {"record_count": 1, "runner_dialect": "pytest"},
            "findings": [{"code": "ok", "severity": "medium", "owner": "team", "due_date": "2026-07-10T00:00:00Z"}],
            "sourceRefs": ["report"],
        },
    )
    _write_json(
        manifest,
        {
            "profile": "default",
            "plugin": {"plugin_id": "plugin-a", "detector_id": "det-a", "execution_mode": "subprocess_local", "signed": True},
            "limits": {"timeout_ms": 5000, "max_output_bytes": 2000, "max_input_bytes": 2000},
            "execution": {
                "command": [
                    sys.executable,
                    "-c",
                    "import json; print(json.dumps({'schema_version':'HATE/v1','detector_id':'det-a','sourceRefs':['plugin']}))",
                ]
            },
        },
    )
    reports = [
        build_platform_schedule_plan(roster, history.parent),
        build_platform_assignment_report(source),
        build_platform_score_report(source),
        run_platform_plugin(manifest),
    ]
    registry = json.loads((ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json").read_text(encoding="utf-8"))
    by_record_type = {record["record_type"]: record for record in registry["records"]}

    for report in reports:
        assert report["record_type"] in by_record_type
        schema_path = ROOT / by_record_type[report["record_type"]]["schema"]
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert set(schema["required"]) <= set(report)
        assert report["record_type"] in schema["properties"]["record_type"]["enum"]
