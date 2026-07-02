from __future__ import annotations

import json
from pathlib import Path

from hate.cli import main
from hate.platform_cli import platform_compare, platform_debt, platform_findings, platform_review


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
    assert findings["summary"]["finding_count"] == 1
    assert findings["items"][0]["sourceRefs"] == ["fixture"]
    assert debt["summary"]["debt_count"] == 1
    assert review["summary"]["review_count"] == 1


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
