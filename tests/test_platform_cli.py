from __future__ import annotations

import json
from pathlib import Path

from hate.cli import main
from hate.platform_cli import platform_compare, platform_debt, platform_findings, platform_report_html, platform_review


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_platform_compare_detects_status_and_count_regression(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    head = tmp_path / "head.json"
    out = tmp_path / "compare.json"
    _write_json(
        base,
        {
            "schema_version": "HATE/v1",
            "record_type": "real-repo-evaluation-report",
            "repo_id": "repo-a",
            "suite_id": "pytest",
            "overall_status": "pass",
            "current": {"record_count": 5},
            "sourceRefs": ["base"],
        },
    )
    _write_json(
        head,
        {
            "schema_version": "HATE/v1",
            "record_type": "real-repo-evaluation-report",
            "repo_id": "repo-a",
            "suite_id": "pytest",
            "overall_status": "hold",
            "current": {"record_count": 3},
            "sourceRefs": ["head"],
        },
    )

    result = platform_compare(base, head, out_path=out)

    assert result["record_type"] == "platform-comparison-report"
    assert result["overall_status"] == "hold"
    assert {item["code"] for item in result["findings"]} == {
        "platform_compare_status_regression",
        "platform_compare_record_count_drop",
    }
    assert json.loads(out.read_text(encoding="utf-8"))["summary"]["finding_count"] == 2


def test_platform_compare_manifest_reads_generated_reports_from_manifest_dir(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "base-report.json",
        {
            "record_type": "real-repo-evaluation-report",
            "repo_id": "repo-a",
            "suite_id": "pytest",
            "overall_status": "pass",
            "current": {"record_count": 10},
        },
    )
    _write_json(
        tmp_path / "head-report.json",
        {
            "record_type": "real-repo-evaluation-report",
            "repo_id": "repo-a",
            "suite_id": "pytest",
            "overall_status": "pass",
            "current": {"record_count": 9},
        },
    )
    base = tmp_path / "base-manifest.json"
    head = tmp_path / "head-manifest.json"
    _write_json(base, {"record_type": "real-repo-evaluation-run-report", "generated_reports": ["base-report.json"]})
    _write_json(head, {"record_type": "real-repo-evaluation-run-report", "generated_reports": ["head-report.json"]})

    result = platform_compare(base, head)

    assert result["summary"]["finding_count"] == 1
    assert result["findings"][0]["code"] == "platform_compare_record_count_drop"


def test_platform_projection_commands_collect_findings_debt_and_reviews(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    _write_json(
        report,
        {
            "record_type": "test-report",
            "report_id": "R1",
            "findings": [{"code": "risk_without_oracle", "severity": "high"}],
            "risk_debt": [{"debt_id": "D1", "owner": "team-a"}],
            "manual_review_requests": [{"request_id": "MR1", "owner": "reviewer"}],
            "sourceRefs": ["fixture"],
        },
    )

    findings = platform_findings(report)
    debt = platform_debt(report)
    review = platform_review(report)

    assert findings["record_type"] == "platform-findings-report"
    assert findings["overall_status"] == "hold"
    assert findings["summary"]["finding_count"] == 1
    assert findings["items"][0]["sourceRefs"] == ["fixture"]
    assert debt["summary"]["debt_count"] == 1
    assert review["summary"]["review_count"] == 1


def test_platform_findings_passes_when_only_nonblocking_items_exist(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    _write_json(
        report,
        {
            "record_type": "test-report",
            "report_id": "R1",
            "findings": [{"code": "note", "severity": "low", "readiness_effect": "none"}],
            "sourceRefs": ["fixture"],
        },
    )

    findings = platform_findings(report)

    assert findings["overall_status"] == "pass"
    assert findings["summary"]["finding_count"] == 1


def test_platform_cli_report_html_and_policy_explain(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    policy = tmp_path / "policy.json"
    html = tmp_path / "out" / "report.html"
    policy_out = tmp_path / "out" / "policy.json"
    _write_json(
        report,
        {
            "record_type": "test-report",
            "report_id": "R1",
            "overall_status": "hold",
            "findings": [{"code": "manual_review_required", "severity": "medium", "readiness_effect": "hold"}],
            "sourceRefs": ["fixture"],
        },
    )
    _write_json(
        policy,
        {
            "schema_version": "HATE/v1",
            "record_type": "platform-policy-config",
            "policy_id": "policy-test",
            "policy_version": "1",
            "profiles": {"default": {"score_floor": 0.8}},
            "thresholds": [],
            "detectors": {},
            "plugins": {},
            "scheduler": {},
            "retention": {},
            "artifact_safety": {},
            "sourceRefs": ["policy.json"],
        },
    )

    assert main(["platform", "report", "html", "--input", str(report), "--out", str(html)]) == 0
    assert "manual_review_required" in html.read_text(encoding="utf-8")

    assert main(["platform", "policy", "explain", "--policy", str(policy), "--out", str(policy_out)]) == 0
    explained = json.loads(policy_out.read_text(encoding="utf-8"))
    assert explained["record_type"] == "platform-policy-report"
    assert explained["policy_id"] == "policy-test"


def test_platform_cli_verdict_and_triage_commands(tmp_path: Path) -> None:
    report = tmp_path / "reports" / "real-repo-repo-a-pytest.json"
    manifest = tmp_path / "reports" / "real-repo-evaluation-run-report.json"
    corpus = tmp_path / "expected.json"
    verdict_out = tmp_path / "out" / "verdict.json"
    triage_out = tmp_path / "out" / "triage.json"
    _write_json(
        report,
        {
            "record_type": "real-repo-evaluation-report",
            "repo_id": "repo-a",
            "suite_id": "pytest",
            "overall_status": "hold",
            "current": {"failure_kind": "test_failure", "record_count": 3, "runner_dialect": "pytest"},
            "sourceRefs": ["repo-a"],
        },
    )
    _write_json(
        manifest,
        {
            "record_type": "real-repo-evaluation-run-report",
            "generated_reports": ["real-repo-repo-a-pytest.json"],
        },
    )
    _write_json(
        corpus,
        {
            "record_type": "platform-expected-verdict-corpus",
            "entries": [{"repo_id": "repo-a", "suite_id": "pytest", "expected_status": "hold", "expected_failure_kind": "test_failure"}],
        },
    )

    assert main(["platform", "verdict", "--input", str(manifest), "--corpus", str(corpus), "--out", str(verdict_out)]) == 0
    assert main(["platform", "triage", "--input", str(manifest), "--out", str(triage_out)]) == 0

    assert json.loads(verdict_out.read_text(encoding="utf-8"))["metrics"]["recall"] == 1.0
    triage = json.loads(triage_out.read_text(encoding="utf-8"))
    assert triage["record_type"] == "platform-triage-report"
    assert triage["summary"]["open_count"] == 1


def test_platform_cli_long_term_history_commands(tmp_path: Path) -> None:
    history_input = tmp_path / "history.json"
    plan_out = tmp_path / "out" / "history-plan.json"
    manifest_out = tmp_path / "out" / "history-manifest.json"
    analytics_out = tmp_path / "out" / "history-analytics.json"
    _write_json(
        history_input,
        {
            "input": {
                "query": {
                    "window_start": "2026-07-01T00:00:00Z",
                    "window_end": "2026-07-03T00:00:00Z",
                    "aggregation_level": "suite",
                    "performance_budget_ms": 1000,
                    "actual_runtime_ms": 50,
                    "min_sample_count": 2,
                },
                "samples": [
                    {
                        "run_id": "run-1",
                        "repo_id": "repo-a",
                        "suite_id": "pytest",
                        "test_count": 100,
                        "flake_count": 1,
                        "repo_health_score": 0.9,
                        "baseline_score": 0.9,
                        "current_score": 0.91,
                        "sourceRef": "run-1",
                    },
                    {
                        "run_id": "run-2",
                        "repo_id": "repo-a",
                        "suite_id": "pytest",
                        "test_count": 100,
                        "flake_count": 3,
                        "repo_health_score": 0.88,
                        "baseline_score": 0.9,
                        "current_score": 0.89,
                        "sourceRef": "run-2",
                    },
                ],
            }
        },
    )

    assert main(["platform", "history-analytics", "--input", str(history_input), "--out", str(analytics_out)]) == 0
    assert main(["platform", "history-materialize", "--input", str(history_input), "--out", str(plan_out), "--manifest-out", str(manifest_out)]) == 0

    analytics = json.loads(analytics_out.read_text(encoding="utf-8"))
    plan = json.loads(plan_out.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_out.read_text(encoding="utf-8"))
    assert analytics["record_type"] == "history-analytics-report"
    assert analytics["overall_status"] == "pass"
    assert analytics["result"]["metrics"]["flake_rate"] == 0.02
    assert plan["record_type"] == "history-materialization-plan"
    assert plan["summary"]["recompute_count"] == 2
    assert manifest["record_type"] == "history-materialization-manifest"


def test_platform_cli_notification_and_baseline_review_commands(tmp_path: Path) -> None:
    notify_route_input = tmp_path / "notify-route.json"
    notify_deliver_input = tmp_path / "notify-deliver.json"
    baseline_input = tmp_path / "baseline-review.json"
    route_out = tmp_path / "out" / "route.json"
    deliver_out = tmp_path / "out" / "deliver.json"
    review_out = tmp_path / "out" / "baseline-review.json"
    _write_json(
        notify_route_input,
        {
            "input": {
                "operating_record": {
                    "operating_record_id": "finding:repo-a:pytest",
                    "severity": "high",
                    "owner": "team-a",
                    "team": "qa",
                    "sla_breached": True,
                    "payload_hash": "sha256:payload",
                    "redaction_report_ref": "artifact://redaction/report.json",
                },
                "subscribers": [
                    {
                        "subscriber_id": "qa-primary",
                        "team": "qa",
                        "delivery_target": "slack_channel",
                        "target_ref": "slack://channel/qa",
                    },
                    {
                        "subscriber_id": "qa-escalation",
                        "delivery_target": "email",
                        "target_ref": "mailto:qa-lead@example.test",
                        "routing_role": "escalation",
                    },
                ],
            }
        },
    )
    _write_json(
        notify_deliver_input,
        {
            "input": {
                "plan": {
                    "notification_id": "notify-1",
                    "operating_record_id": "finding:repo-a:pytest",
                    "delivery_target": "slack_channel",
                    "target_ref": "slack://channel/qa",
                    "dedupe_key": "finding-repo-a-pytest",
                    "payload_hash": "sha256:payload",
                    "payload_safe": True,
                    "redaction_report_ref": "artifact://redaction/report.json",
                    "max_attempts": 3,
                },
                "attempts": [{"event_type": "sent", "attempt": 1, "delivery_status": "delivered"}],
            }
        },
    )
    _write_json(
        baseline_input,
        {
            "input": {
                "baseline": {
                    "baseline_id": "base-repo-a-pytest",
                    "repo_id": "repo-a",
                    "suite_id": "pytest",
                    "actor": "alice",
                    "policy_hash": "sha256:policy",
                    "expires_at": "2026-10-01T00:00:00Z",
                },
                "events": [
                    {"event_type": "proposed", "candidate_run_id": "run-2", "evidence_refs": ["artifact://run-2/report.json"]},
                    {"event_type": "approved", "reviewer": "bob"},
                    {"event_type": "frozen", "frozen_at": "2026-07-05T00:00:00Z", "immutability_hash": "sha256:frozen"},
                ],
                "comparison": {
                    "previous_baseline_ref": "baseline://base-old",
                    "previous_score": 80,
                    "candidate_score": 82,
                    "previous_regression_count": 1,
                    "candidate_regression_count": 0,
                    "comparison_artifact_ref": "artifact://compare/base-old-run-2.json",
                },
            }
        },
    )

    assert main(["platform", "notify", "route", "--input", str(notify_route_input), "--out", str(route_out)]) == 0
    assert main(["platform", "notify", "deliver", "--input", str(notify_deliver_input), "--out", str(deliver_out)]) == 0
    assert main(["platform", "baseline", "review", "--input", str(baseline_input), "--out", str(review_out)]) == 0

    route = json.loads(route_out.read_text(encoding="utf-8"))
    deliver = json.loads(deliver_out.read_text(encoding="utf-8"))
    review = json.loads(review_out.read_text(encoding="utf-8"))
    assert route["record_type"] == "notification-routing-plan"
    assert route["summary"]["routing_entry_count"] == 2
    assert route["summary"]["escalation_count"] == 1
    assert deliver["record_type"] == "notification-delivery-report"
    assert deliver["overall_status"] == "pass"
    assert review["record_type"] == "baseline-review-packet"
    assert review["summary"]["ready_for_review"] is True


def test_platform_report_html_holds_when_operator_queue_has_high_findings(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    html = tmp_path / "report.html"
    _write_json(
        report,
        {
            "record_type": "test-report",
            "report_id": "R1",
            "overall_status": "hold",
            "findings": [{"code": "real_repo_missing_test_dependency", "severity": "high"}],
            "sourceRefs": ["fixture"],
        },
    )

    result = platform_report_html(report, html)

    assert result["overall_status"] == "hold"
    assert result["critical_queue_count"] == 1
    assert "real_repo_missing_test_dependency" in html.read_text(encoding="utf-8")


def test_platform_report_html_directory_input_ignores_prior_platform_outputs(tmp_path: Path) -> None:
    html = tmp_path / "report.html"
    _write_json(
        tmp_path / "real-repo.json",
        {
            "record_type": "real-repo-evaluation-report",
            "report_id": "real-repo-a",
            "overall_status": "pass",
            "findings": [],
            "sourceRefs": ["real-repo"],
        },
    )
    _write_json(
        tmp_path / "platform-score.json",
        {
            "record_type": "platform-score-report",
            "overall_status": "pass",
            "scores": [],
            "findings": [{"code": "stale_self_output", "severity": "high"}],
        },
    )

    result = platform_report_html(tmp_path, html)

    assert result["report_count"] == 1
    assert result["finding_count"] == 0
    assert "stale_self_output" not in html.read_text(encoding="utf-8")
