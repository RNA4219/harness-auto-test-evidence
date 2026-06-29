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
    assert result["product_grade_implementation_status"] == "no_go"

    summary = json.loads((out_dir / "product-grade-evidence-summary.json").read_text(encoding="utf-8"))
    assert summary["required_report_count"] == len(REPORT_SPECS)
    assert summary["generated_report_count"] == len(REPORT_SPECS)
    assert summary["product_ready"] is False
    assert summary["product_grade_implementation_status"] == "no_go"

    api_report = json.loads((out_dir / "api-contract-report.json").read_text(encoding="utf-8"))
    assert api_report["status"] == "specified"
    assert api_report["product_ready_evidence"] is False
    assert "implementation code" in api_report["required_next_evidence"]


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
