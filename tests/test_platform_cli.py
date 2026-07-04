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
