from __future__ import annotations

import json
from pathlib import Path

from hate.product_grade import REPORT_SPECS, generate_product_grade_reports


ROOT = Path(__file__).resolve().parents[1]


def test_product_grade_reports_generate_required_report_set(tmp_path: Path) -> None:
    out_dir = tmp_path / "grade-reports"

    result = generate_product_grade_reports(
        docs_root=ROOT / "docs" / "process",
        out_dir=out_dir,
        source_version="test",
    )

    expected_reports = {spec.filename for spec in REPORT_SPECS}
    assert expected_reports.issubset(set(result["generated"]))
    assert result["product_ready"] is False
    assert result["poc_ready"] is True
    assert result["poc_completion_percent"] == 100
    assert result["product_grade_implementation_status"] == "poc_complete"

    summary = json.loads((out_dir / "product-grade-evidence-summary.json").read_text(encoding="utf-8"))
    assert summary["required_report_count"] == len(REPORT_SPECS)
    assert summary["generated_report_count"] == len(REPORT_SPECS)
    assert summary["product_ready"] is False
    assert summary["poc_ready"] is True
    assert summary["poc_completion_percent"] == 100
    assert summary["product_grade_implementation_status"] == "poc_complete"
    assert summary["real_data_validation"]["repo_suite_count"] == 22
    assert summary["real_data_validation"]["executed_records"] == 12771
    assert summary["real_data_validation"]["qeg_smoke_passed"] is True
    assert summary["real_data_validation"]["residual_blockers"]
    assert summary["poc_completion"]["unmitigated_blockers"] == []
    assert all(item["mitigated"] for item in summary["poc_completion"]["mitigations"])

    api_report = json.loads((out_dir / "api-contract-report.json").read_text(encoding="utf-8"))
    assert api_report["status"] == "implemented_with_evidence"
    assert api_report["product_ready_evidence"] is True
    assert api_report["implementation_evidence_status"] == "implemented"
    assert api_report["missing_implementation_refs"] == []
    assert api_report["missing_test_refs"] == []
    assert "QEG release approval" in api_report["required_next_evidence"]


def test_product_grade_reports_detect_missing_required_docs(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    (docs_root / "API_REQUIREMENTS.md").write_text("# API\n", encoding="utf-8")
    out_dir = tmp_path / "out"

    generate_product_grade_reports(docs_root=docs_root, out_dir=out_dir)

    api_report = json.loads((out_dir / "api-contract-report.json").read_text(encoding="utf-8"))
    assert api_report["status"] == "missing_required_docs"
    assert "API_OPENAPI.yaml" in api_report["missing_required_docs"]

    summary = json.loads((out_dir / "product-grade-evidence-summary.json").read_text(encoding="utf-8"))
    assert "api-contract-report.json" in summary["missing_or_incomplete_reports"]
    assert summary["product_grade_implementation_status"] == "no_go"


def test_product_grade_without_poc_completion_record_stays_conditional(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    docs_root = repo_root / "docs" / "process"
    acceptance = repo_root / "docs" / "acceptance"
    docs_root.mkdir(parents=True)
    acceptance.mkdir(parents=True)
    for spec in REPORT_SPECS:
        for doc in spec.required_docs:
            (docs_root / doc).write_text("# doc\n", encoding="utf-8")
        for ref in [*spec.implementation_refs, *spec.test_refs]:
            path = repo_root / ref
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# ref\n", encoding="utf-8")
    (acceptance / "REAL_REPO_BULK_VALIDATION_20260702.md").write_text(
        "Primary run coverage: 22 repo/suites and 12,771 executed records.\n"
        "QEG `build`, `validate`, `gate`, and `record` passed\n"
        "`uv` cache access problem\n"
        "`memx-resolver` held due missing `yaml`\n"
        "`total_checks`, not `total_tests`\n",
        encoding="utf-8",
    )

    generate_product_grade_reports(docs_root=docs_root, out_dir=tmp_path / "out", repo_root=repo_root)

    summary = json.loads((tmp_path / "out" / "product-grade-evidence-summary.json").read_text(encoding="utf-8"))
    assert summary["product_grade_implementation_status"] == "conditional_go"
    assert summary["poc_ready"] is False
    assert summary["poc_completion"]["present"] is False
