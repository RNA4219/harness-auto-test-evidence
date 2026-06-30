from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .analysis.adapter_capability_diff import build_adapter_capability_diff_report
from .analysis.audience_report_pack import build_audience_report_pack
from .analysis.contradiction_detection import build_contradiction_report
from .analysis.environment_diff import build_environment_diff_report
from .analysis.evidence_synthesis import build_evidence_synthesis_report
from .analysis.fixture_quality import build_fixture_quality_report
from .analysis.flaky_classification import build_flaky_classification_report
from .analysis.historical_regression import build_historical_regression_report
from .analysis.impact_analysis import build_impact_analysis_report
from .analysis.oracle_classification import build_oracle_classification_report
from .analysis.test_quality import build_test_quality_report
from .analysis.test_recommendation import build_test_recommendation_report
from .expansion.a11y_l10n import build_a11y_l10n_report
from .expansion.adapter_marketplace import build_adapter_marketplace_report
from .expansion.beta_acceptance import build_beta_acceptance_report
from .expansion.bulk_portability import build_bulk_portability_report
from .expansion.cost_governance import build_cost_governance_report
from .expansion.data_classification import build_data_classification_report
from .expansion.dependency_compliance import build_dependency_compliance_report
from .expansion.disaster_recovery import build_disaster_recovery_report
from .expansion.docs_lifecycle import build_docs_lifecycle_report
from .expansion.notifications import build_notification_report
from .expansion.onboarding import build_onboarding_report
from .expansion.policy_simulation import build_policy_simulation_report
from .expansion.product_analytics import build_product_analytics_report
from .expansion.self_hosted import build_self_hosted_report


ReportBuilder = Callable[..., dict[str, Any]]


class ExpansionRunError(Exception):
    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class ExpansionReportSpec:
    area: str
    gap_id: str
    record_type: str
    builder: ReportBuilder


EXPANSION_REPORT_SPECS: tuple[ExpansionReportSpec, ...] = (
    ExpansionReportSpec("onboarding", "HATE-GAP-027", "onboarding-report", build_onboarding_report),
    ExpansionReportSpec("policy-simulation", "HATE-GAP-028", "policy-simulation-report", build_policy_simulation_report),
    ExpansionReportSpec("bulk-portability", "HATE-GAP-029", "bulk-portability-report", build_bulk_portability_report),
    ExpansionReportSpec("notifications", "HATE-GAP-030", "notification-report", build_notification_report),
    ExpansionReportSpec("self-hosted", "HATE-GAP-031", "self-hosted-report", build_self_hosted_report),
    ExpansionReportSpec("data-classification", "HATE-GAP-032", "data-classification-report", build_data_classification_report),
    ExpansionReportSpec("docs-lifecycle", "HATE-GAP-033", "docs-lifecycle-report", build_docs_lifecycle_report),
    ExpansionReportSpec("dependency-compliance", "HATE-GAP-034", "dependency-compliance-report", build_dependency_compliance_report),
    ExpansionReportSpec("adapter-marketplace", "HATE-GAP-035", "adapter-marketplace-report", build_adapter_marketplace_report),
    ExpansionReportSpec("product-analytics", "HATE-GAP-036", "product-analytics-report", build_product_analytics_report),
    ExpansionReportSpec("disaster-recovery", "HATE-GAP-037", "disaster-recovery-report", build_disaster_recovery_report),
    ExpansionReportSpec("a11y-l10n", "HATE-GAP-038", "a11y-l10n-report", build_a11y_l10n_report),
    ExpansionReportSpec("cost-governance", "HATE-GAP-039", "cost-governance-report", build_cost_governance_report),
    ExpansionReportSpec("beta-acceptance", "HATE-GAP-040", "beta-acceptance-report", build_beta_acceptance_report),
    ExpansionReportSpec("impact-analysis", "HATE-GAP-049", "impact-analysis-report", build_impact_analysis_report),
    ExpansionReportSpec("test-recommendation", "HATE-GAP-050", "test-recommendation-report", build_test_recommendation_report),
    ExpansionReportSpec("flaky-classification", "HATE-GAP-051", "flaky-classification-report", build_flaky_classification_report),
    ExpansionReportSpec("oracle-classification", "HATE-GAP-052", "oracle-classification-report", build_oracle_classification_report),
    ExpansionReportSpec("evidence-synthesis", "HATE-GAP-053", "evidence-synthesis-report", build_evidence_synthesis_report),
    ExpansionReportSpec("test-quality", "HATE-GAP-054", "test-quality-report", build_test_quality_report),
    ExpansionReportSpec("environment-diff", "HATE-GAP-055", "environment-diff-report", build_environment_diff_report),
    ExpansionReportSpec("contradiction-detection", "HATE-GAP-056", "contradiction-report", build_contradiction_report),
    ExpansionReportSpec("historical-regression", "HATE-GAP-057", "historical-regression-report", build_historical_regression_report),
    ExpansionReportSpec("audience-report-pack", "HATE-GAP-058", "audience-report-pack", build_audience_report_pack),
    ExpansionReportSpec("fixture-quality", "HATE-GAP-059", "fixture-quality-report", build_fixture_quality_report),
    ExpansionReportSpec("adapter-capability-diff", "HATE-GAP-060", "adapter-capability-diff-report", build_adapter_capability_diff_report),
)

EXPANSION_REPORT_TYPES = tuple(spec.record_type for spec in EXPANSION_REPORT_SPECS)


def run_expansion_suite(
    *,
    fixtures_root: Path,
    out_dir: Path,
    areas: list[str] | None = None,
    case_kind: str = "positive",
) -> dict[str, Any]:
    """Generate expansion/analysis reports from canonical expansion fixtures."""
    if not fixtures_root.exists():
        raise ExpansionRunError(f"fixtures root not found: {fixtures_root}")
    if case_kind not in {"positive", "negative", "all"}:
        raise ExpansionRunError(f"invalid case kind: {case_kind}")

    selected_areas = set(areas or [])
    unknown = selected_areas - {spec.area for spec in EXPANSION_REPORT_SPECS}
    if unknown:
        raise ExpansionRunError(f"unknown expansion areas: {', '.join(sorted(unknown))}")

    out_dir.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, Any]] = []
    generated: list[str] = []
    missing: list[str] = []

    for spec in EXPANSION_REPORT_SPECS:
        if selected_areas and spec.area not in selected_areas:
            continue
        fixture_paths = _select_fixture_paths(fixtures_root / spec.area, case_kind)
        if not fixture_paths:
            missing.append(spec.area)
            continue
        for fixture_path in fixture_paths:
            report = build_report_from_fixture(spec, fixture_path)
            reports.append(report)
            output_path = _write_report(out_dir, spec, fixture_path, report, single_case=len(fixture_paths) == 1)
            generated.append(str(output_path.as_posix()))

    status = "pass" if not missing else "hold"
    manifest = {
        "schema_version": "HATE/v1",
        "record_type": "expansion-run-report",
        "report_id": f"expansion-run-{case_kind}",
        "overall_status": status,
        "readiness_effect": "none" if status == "pass" else "hold",
        "case_kind": case_kind,
        "generated_report_count": len(generated),
        "generated_reports": sorted(generated),
        "missing_areas": sorted(missing),
        "report_types": sorted({report["record_type"] for report in reports}),
        "sourceRefs": sorted({ref for report in reports for ref in report.get("sourceRefs", [])}),
    }
    manifest_path = out_dir / "expansion-run-report.json"
    _write_json(manifest_path, manifest)
    return manifest


def build_report_from_fixture(spec: ExpansionReportSpec, fixture_path: Path) -> dict[str, Any]:
    payload = _load_json(fixture_path)
    input_data = payload.get("input", payload)
    fixture_id = str(payload.get("fixture_id") or fixture_path.parent.name)
    report = spec.builder(
        input_data,
        report_id=fixture_id,
        source_refs=[fixture_id],
    )
    if report.get("record_type") != spec.record_type:
        raise ExpansionRunError(
            f"record type mismatch for {spec.area}: expected {spec.record_type}, got {report.get('record_type')}"
        )
    return report


def _select_fixture_paths(area_root: Path, case_kind: str) -> list[Path]:
    if not area_root.exists():
        return []
    fixture_paths = sorted(area_root.glob("*/fixture.json"))
    if case_kind == "all":
        return fixture_paths

    selected: list[Path] = []
    for fixture_path in fixture_paths:
        payload = _load_json(fixture_path)
        if payload.get("case_kind") == case_kind:
            selected.append(fixture_path)
    return selected


def _write_report(
    out_dir: Path,
    spec: ExpansionReportSpec,
    fixture_path: Path,
    report: dict[str, Any],
    *,
    single_case: bool,
) -> Path:
    if single_case:
        output_path = out_dir / f"{spec.record_type}.json"
    else:
        output_path = out_dir / spec.area / fixture_path.parent.name / f"{spec.record_type}.json"
    _write_json(output_path, report)
    return output_path


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExpansionRunError(f"malformed JSON fixture: {path}: {exc}") from exc


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
