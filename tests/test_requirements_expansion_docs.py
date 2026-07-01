"""Documentation consistency checks for HATE requirement expansion gaps."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROCESS = ROOT / "docs" / "process"
TASKS = ROOT / "docs" / "tasks"
ACCEPTANCE = ROOT / "docs" / "acceptance"
FIXTURES = ROOT / "fixtures" / "expansion"
SCHEMAS = ROOT / "schemas" / "HATE" / "v1"

EXPANSION_GAP_IDS = [f"HATE-GAP-{index:03d}" for index in range(27, 61)]
W34_GAP_IDS = [f"HATE-GAP-{index:03d}" for index in range(41, 49)]
W35_GAP_IDS = [f"HATE-GAP-{index:03d}" for index in range(49, 61)]

W32_FIXTURES = {
    "HATE-GAP-027": (
        "HATE-PKT-EXP-001-onboarding",
        "TASK-HATE-GAP-027",
        "AC-HATE-GAP-027",
        "onboarding",
        "onboarding-uat-report.json",
        ("golden-walkthrough", "parser-failure-tutorial"),
    ),
    "HATE-GAP-028": (
        "HATE-PKT-EXP-002-policy-simulation",
        "TASK-HATE-GAP-028",
        "AC-HATE-GAP-028",
        "policy-simulation",
        "policy-simulation-uat-report.json",
        ("safe-dry-run", "blast-radius-unbounded"),
    ),
    "HATE-GAP-029": (
        "HATE-PKT-EXP-003-bulk-portability",
        "TASK-HATE-GAP-029",
        "AC-HATE-GAP-029",
        "bulk-portability",
        "bulk-portability-uat-report.json",
        ("resumable-export", "cross-tenant-import-denied"),
    ),
    "HATE-GAP-030": (
        "HATE-PKT-EXP-004-notifications",
        "TASK-HATE-GAP-030",
        "AC-HATE-GAP-030",
        "notifications",
        "notification-uat-report.json",
        ("signed-delivery", "unsigned-webhook-denied"),
    ),
    "HATE-GAP-031": (
        "HATE-PKT-EXP-005-self-hosted",
        "TASK-HATE-GAP-031",
        "AC-HATE-GAP-031",
        "self-hosted",
        "self-hosted-uat-report.json",
        ("upgrade-compatible", "rollback-required"),
    ),
    "HATE-GAP-032": (
        "HATE-PKT-EXP-006-data-classification",
        "TASK-HATE-GAP-032",
        "AC-HATE-GAP-032",
        "data-classification",
        "data-classification-uat-report.json",
        ("public-summary-safe", "prohibited-telemetry-denied"),
    ),
    "HATE-GAP-033": (
        "HATE-PKT-EXP-007-docs-lifecycle",
        "TASK-HATE-GAP-033",
        "AC-HATE-GAP-033",
        "docs-lifecycle",
        "docs-lifecycle-uat-report.json",
        ("version-bound-docs", "stale-claim-denied"),
    ),
}

W33_DETAIL_TERMS = {
    "HATE-GAP-034": [
        "src/hate/expansion/dependency_compliance.py",
        "build_dependency_compliance_report",
        "evaluate_dependency_compliance_fixture",
        "tests/test_expansion_dependency_compliance.py",
        "dependency-compliance-report.schema.json",
        "dependency_compliance_denied_license",
        "dependency_compliance_vulnerability_exception_expired",
        "fixtures/expansion/dependency-compliance/sbom-clean/fixture.json",
        "fixtures/expansion/dependency-compliance/denied-license/fixture.json",
    ],
    "HATE-GAP-035": [
        "src/hate/expansion/adapter_marketplace.py",
        "build_adapter_marketplace_report",
        "evaluate_adapter_marketplace_fixture",
        "tests/test_expansion_adapter_marketplace.py",
        "adapter-marketplace-report.schema.json",
        "adapter_marketplace_revoked_plugin_denied",
        "adapter_marketplace_signature_invalid",
        "fixtures/expansion/adapter-marketplace/signed-compatible-plugin/fixture.json",
        "fixtures/expansion/adapter-marketplace/revoked-plugin-denied/fixture.json",
    ],
    "HATE-GAP-036": [
        "src/hate/expansion/product_analytics.py",
        "build_product_analytics_report",
        "evaluate_product_analytics_fixture",
        "tests/test_expansion_product_analytics.py",
        "product-analytics-report.schema.json",
        "product_analytics_raw_path_event_denied",
        "product_analytics_opt_in_missing",
        "fixtures/expansion/product-analytics/aggregate-opt-in/fixture.json",
        "fixtures/expansion/product-analytics/raw-path-event-denied/fixture.json",
    ],
    "HATE-GAP-037": [
        "src/hate/expansion/disaster_recovery.py",
        "build_disaster_recovery_report",
        "evaluate_disaster_recovery_fixture",
        "tests/test_expansion_disaster_recovery.py",
        "disaster-recovery-report.schema.json",
        "disaster_recovery_corrupt_backup_denied",
        "disaster_recovery_rpo_exceeded",
        "fixtures/expansion/disaster-recovery/restore-drill-pass/fixture.json",
        "fixtures/expansion/disaster-recovery/corrupt-backup-denied/fixture.json",
    ],
    "HATE-GAP-038": [
        "src/hate/expansion/a11y_l10n.py",
        "build_a11y_l10n_report",
        "evaluate_a11y_l10n_fixture",
        "tests/test_expansion_a11y_l10n.py",
        "a11y-l10n-report.schema.json",
        "a11y_l10n_color_only_severity_denied",
        "a11y_l10n_locale_fallback_missing",
        "fixtures/expansion/a11y-l10n/locale-fallback-safe/fixture.json",
        "fixtures/expansion/a11y-l10n/color-only-severity-denied/fixture.json",
    ],
    "HATE-GAP-039": [
        "src/hate/expansion/cost_governance.py",
        "build_cost_governance_report",
        "evaluate_cost_governance_fixture",
        "tests/test_expansion_cost_governance.py",
        "cost-governance-report.schema.json",
        "cost_governance_egress_risk_hold",
        "cost_governance_storage_budget_exceeded",
        "fixtures/expansion/cost-governance/forecast-within-budget/fixture.json",
        "fixtures/expansion/cost-governance/egress-risk-hold/fixture.json",
    ],
    "HATE-GAP-040": [
        "src/hate/expansion/beta_acceptance.py",
        "build_beta_acceptance_report",
        "evaluate_beta_acceptance_fixture",
        "tests/test_expansion_beta_acceptance.py",
        "beta-acceptance-report.schema.json",
        "beta_acceptance_blocker_feedback_hold",
        "beta_acceptance_customer_secret_denied",
        "fixtures/expansion/beta-acceptance/cohort-exit-pass/fixture.json",
        "fixtures/expansion/beta-acceptance/blocker-feedback-hold/fixture.json",
    ],
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_expansion_requirement_documents_exist() -> None:
    assert (PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md").is_file()
    assert (PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_PACKETS.md").is_file()
    assert (PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md").is_file()
    assert (TASKS / "HATE_REQUIREMENTS_EXPANSION_TASK_SEEDS.md").is_file()
    assert (ACCEPTANCE / "HATE_REQUIREMENTS_EXPANSION_ACCEPTANCE.md").is_file()


def test_expansion_gap_ids_are_projected_to_packet_task_and_acceptance_ledgers() -> None:
    backlog = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md")
    packets = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_PACKETS.md")
    tasks = _read(TASKS / "HATE_REQUIREMENTS_EXPANSION_TASK_SEEDS.md")
    acceptance = _read(ACCEPTANCE / "HATE_REQUIREMENTS_EXPANSION_ACCEPTANCE.md")
    index = _read(ACCEPTANCE / "INDEX.md")

    missing: dict[str, list[str]] = {}
    for gap_id in EXPANSION_GAP_IDS:
        index_number = gap_id.rsplit("-", 1)[1]
        task_id = f"TASK-HATE-GAP-{index_number}"
        acceptance_id = f"AC-HATE-GAP-{index_number}"
        absent = []
        if gap_id not in backlog:
            absent.append("backlog")
        if gap_id not in packets:
            absent.append("packets")
        if gap_id not in tasks or task_id not in tasks:
            absent.append("task_seed")
        if gap_id not in acceptance or acceptance_id not in acceptance:
            absent.append("acceptance")
        if acceptance_id not in index:
            absent.append("acceptance_index")
        if absent:
            missing[gap_id] = absent

    assert missing == {}


def test_expansion_packets_are_complete_enough_for_worker_handoff() -> None:
    packets = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_PACKETS.md")
    rows = [line for line in packets.splitlines() if line.startswith("| HATE-GAP-")]

    assert len(rows) == 34
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert len(cells) == 8
        gap_id, packet_id, contract_ref, positive_fixture, negative_fixture, uat_evidence, owner, done_gate = cells
        assert gap_id in EXPANSION_GAP_IDS
        assert packet_id.startswith("HATE-PKT-EXP-")
        assert contract_ref.startswith("`") and contract_ref.endswith("`")
        assert re.fullmatch(r"`fixtures/expansion/[^`]+/fixture\.json`", positive_fixture)
        assert re.fullmatch(r"`fixtures/expansion/[^`]+/fixture\.json`", negative_fixture)
        assert uat_evidence.endswith("-uat-report.json`")
        assert owner
        assert done_gate.endswith("tests")


def test_expansion_acceptance_does_not_overclaim_implementation() -> None:
    acceptance = _read(ACCEPTANCE / "HATE_REQUIREMENTS_EXPANSION_ACCEPTANCE.md")

    assert "connected to the expansion runner/release pack path" in acceptance
    assert "implementation requires runtime code, schema, fixtures, tests, and a CLI/release-pack connection" in acceptance
    for gap_id in EXPANSION_GAP_IDS:
        assert f"| {gap_id} |" in acceptance
        row = next(line for line in acceptance.splitlines() if f"| {gap_id} |" in line)
        assert "| implemented | connected to expansion runner and release pack |" in row


def test_top_level_prd_references_expansion_backlog() -> None:
    prd = _read(PROCESS / "PRODUCT_REQUIREMENTS_DEFINITION.md")
    backlog = _read(PROCESS / "PRODUCT_REQUIREMENTS_GAP_BACKLOG.md")

    assert "PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md" in prd
    assert "PRODUCT_REQUIREMENTS_EXPANSION_PACKETS.md" in prd
    assert "The next requirement-gap wave starts at HATE-GAP-027" in backlog


def test_w34_requirement_expansion_closes_narrow_company_use_scope() -> None:
    prd = _read(PROCESS / "PRODUCT_REQUIREMENTS_DEFINITION.md")
    backlog = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md")
    packets = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_PACKETS.md")
    detail = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md")
    portfolio_detail = _read(PROCESS / "PRODUCT_REQUIREMENTS_PORTFOLIO_READINESS_DETAIL_SPEC.md")
    tasks = _read(TASKS / "HATE_REQUIREMENTS_EXPANSION_TASK_SEEDS.md")
    acceptance = _read(ACCEPTANCE / "HATE_REQUIREMENTS_EXPANSION_ACCEPTANCE.md")

    required_prd_terms = [
        "### 7.15 Company Rollout and Adoption Requirements",
        "### 7.16 CI, SCM, and Repository Provider Coverage",
        "### 7.17 Language and Test Runner Coverage",
        "### 7.18 Real Repository Evaluation Requirements",
        "### 7.19 Organizational Governance Requirements",
        "### 7.20 Security Procurement and Trust Package Requirements",
        "### 7.21 Value Measurement and ROI Requirements",
        "### 7.22 Daily Developer Experience Requirements",
        "FR-ROLL-001",
        "FR-CI-001",
        "FR-LANG-001",
        "FR-REEVAL-001",
        "FR-GOV-001",
        "FR-PROC-001",
        "FR-VALUE-001",
        "FR-DX-001",
        "AC-REQ-026",
    ]
    required_backlog_terms = [
        "Company rollout and adoption operations",
        "CI/SCM provider matrix",
        "Language and runner coverage",
        "Recurring real repository evaluation",
        "Organizational governance workflow",
        "Security procurement and trust package",
        "Value measurement and ROI",
        "Daily developer experience",
    ]
    required_packet_terms = [
        "HATE-PKT-EXP-015-rollout-adoption",
        "HATE-PKT-EXP-016-provider-matrix",
        "HATE-PKT-EXP-017-runner-dialects",
        "HATE-PKT-EXP-018-recurring-real-repo-eval",
        "HATE-PKT-EXP-019-governance-workflow",
        "HATE-PKT-EXP-020-security-procurement",
        "HATE-PKT-EXP-021-value-measurement",
        "HATE-PKT-EXP-022-developer-experience",
        "implemented-ready",
        "src/hate/expansion/portfolio_readiness.py",
        "PRODUCT_REQUIREMENTS_PORTFOLIO_READINESS_DETAIL_SPEC.md",
    ]
    required_detail_terms = [
        "## 1. HATE-GAP-041 Through HATE-GAP-048 Runtime Contract",
        "## 2. Schemas, Fixtures, And Findings",
        "## 3. Test And Release Minimum",
        "build_rollout_adoption_report",
        "build_developer_experience_report",
        "rollout-adoption-report.schema.json",
        "developer-experience-report.schema.json",
        "runner_dialect_unsupported_capability_gap",
        "recurring_eval_regression_detected",
        "developer_experience_broad_suppression_denied",
    ]

    assert [term for term in required_prd_terms if term not in prd] == []
    assert [term for term in required_backlog_terms if term not in backlog] == []
    assert [term for term in required_packet_terms if term not in packets] == []
    assert "PRODUCT_REQUIREMENTS_PORTFOLIO_READINESS_DETAIL_SPEC.md" in detail
    assert [term for term in required_detail_terms if term not in portfolio_detail] == []
    for gap_id in W34_GAP_IDS:
        suffix = gap_id.rsplit("-", 1)[1]
        assert f"TASK-HATE-GAP-{suffix}" in tasks
        assert f"AC-HATE-GAP-{suffix}" in acceptance


def test_w35_core_functional_expansion_follows_requirements_then_spec_order() -> None:
    prd = _read(PROCESS / "PRODUCT_REQUIREMENTS_DEFINITION.md")
    backlog = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md")
    packets = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_PACKETS.md")
    detail = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md")
    tasks = _read(TASKS / "HATE_REQUIREMENTS_EXPANSION_TASK_SEEDS.md")
    acceptance = _read(ACCEPTANCE / "HATE_REQUIREMENTS_EXPANSION_ACCEPTANCE.md")
    index = _read(ACCEPTANCE / "INDEX.md")

    required_prd_terms = [
        "### 7.23 Core Analysis Expansion Requirements",
        "FR-ANALYSIS-001",
        "FR-ANALYSIS-012",
        "AC-REQ-038",
        "ImpactAnalysis",
        "AdapterCapabilityDiff",
        "NFR-017",
        "NFR-018",
    ]
    required_backlog_terms = [
        "Impact analysis",
        "Test recommendation engine",
        "Flaky classification",
        "Oracle classification",
        "Evidence synthesis",
        "Test code quality analysis",
        "Execution environment diff",
        "Cross-evidence contradiction detection",
        "Historical regression analysis",
        "Multi-audience report generation",
        "Fixture and corpus quality detection",
        "Adapter capability diff",
    ]
    required_packet_terms = [
        "HATE-PKT-EXP-023-impact-analysis",
        "HATE-PKT-EXP-024-test-recommendation",
        "HATE-PKT-EXP-025-flaky-classification",
        "HATE-PKT-EXP-026-oracle-classification",
        "HATE-PKT-EXP-027-evidence-synthesis",
        "HATE-PKT-EXP-028-test-quality",
        "HATE-PKT-EXP-029-environment-diff",
        "HATE-PKT-EXP-030-contradiction-detection",
        "HATE-PKT-EXP-031-historical-regression",
        "HATE-PKT-EXP-032-audience-report-pack",
        "HATE-PKT-EXP-033-fixture-quality",
        "HATE-PKT-EXP-034-adapter-capability-diff",
    ]
    required_detail_sections = [
        "## 23. W34 Core Functional Expansion Scope",
        "## 24. W34 Canonical File And Function Contract",
        "## 25. W34 Canonical Fixtures, Schemas, And Findings",
        "## 26. W34 Schema And Test Minimum",
    ]
    required_detail_terms = [
        "src/hate/analysis/impact_analysis.py",
        "build_impact_analysis_report",
        "tests/test_analysis_adapter_capability_diff.py",
        "adapter_capability_diff_lossy_field_drop_hold",
        "impact-analysis-report.schema.json",
        "adapter-capability-diff-report.schema.json",
        "verdict_recomputed",
        "lossy_transforms",
    ]

    assert [term for term in required_prd_terms if term not in prd] == []
    assert [term for term in required_backlog_terms if term not in backlog] == []
    assert [term for term in required_packet_terms if term not in packets] == []
    assert [section for section in required_detail_sections if section not in detail] == []
    assert [term for term in required_detail_terms if term not in detail] == []
    assert "FR-ANALYSIS-001" in prd
    assert "HATE-GAP-049" in detail
    for gap_id in W35_GAP_IDS:
        suffix = gap_id.rsplit("-", 1)[1]
        assert gap_id in backlog
        assert gap_id in packets
        assert f"TASK-HATE-GAP-{suffix}" in tasks
        assert f"AC-HATE-GAP-{suffix}" in acceptance
        assert f"AC-HATE-GAP-{suffix}" in index


def test_expansion_detail_spec_hardens_uat_rough_edges() -> None:
    detail = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md")
    packets = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_PACKETS.md")
    backlog = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_GAP_BACKLOG.md")
    readme = _read(ROOT / "README.md")

    assert "PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md" in packets
    assert "PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md" in backlog
    assert "PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md" in readme
    assert "pytest.skip" in detail
    assert "*.schema.json" in detail
    assert "Noncanonical fixture aliases are prohibited" in detail
    assert "HATE-GAP-034 through HATE-GAP-040 are `specified-ready`" in packets
    assert "no longer `specified-thin`" in backlog


def test_w32_expansion_detail_spec_defines_runtime_contract_edges() -> None:
    detail = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md")
    required_terms = [
        "self_hosted_installer_contract_missing",
        "self_hosted_installer_missing",
        "data_classification_sink_allowlist_missing",
        "data_classification_allowed_sinks_missing",
        "telemetry_sink_allowed",
        "docs_lifecycle_required_docs_missing",
        "docs_lifecycle_inventory_missing",
        "docs_lifecycle_version_mismatch",
        "required_docs_inventory_defined",
        "schema-registry",
        "HATE/expansion-gap-fixture/v1",
    ]

    missing_terms = [term for term in required_terms if term not in detail]
    assert missing_terms == []


def test_w33_expansion_detail_spec_defines_implementation_contracts() -> None:
    detail = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md")
    packets = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_PACKETS.md")

    assert "## 18. W33 Implementation Readiness" in detail
    assert "specified-ready" in packets
    for gap_id, required_terms in W33_DETAIL_TERMS.items():
        assert gap_id in detail
        missing_terms = [term for term in required_terms if term not in detail]
        assert missing_terms == []


def test_w33_expansion_detail_spec_no_longer_allows_thin_handoff() -> None:
    detail = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md")

    assert "The current W33 packets are therefore `specified-thin`" not in detail
    assert "must not start implementation until each packet" not in detail
    assert "runtime modules, schemas, fixtures, tests" in detail


def test_w33_expansion_detail_spec_pins_file_schema_and_test_contracts() -> None:
    detail = _read(PROCESS / "PRODUCT_REQUIREMENTS_EXPANSION_DETAIL_SPEC.md")
    required_sections = [
        "## 19. W33 File And Function Contract",
        "## 20. W33 Schema Minimum",
        "## 21. W33 Minimum Test Contract",
    ]
    required_terms = [
        "Alternate names are noncanonical aliases",
        "Each builder function must accept",
        "Each fixture evaluator must accept",
        "Every schema must require",
        "schema registry assertion",
        "assertion that sibling `*-report.json` schema alias does not exist",
        "Tests must not use `pytest.skip`",
        "fixture name as the only behavioral oracle",
    ]

    missing_sections = [section for section in required_sections if section not in detail]
    missing_terms = [term for term in required_terms if term not in detail]
    assert missing_sections == []
    assert missing_terms == []


def test_w32_expansion_fixtures_follow_canonical_packet_contract() -> None:
    for gap_id, fixture_spec in W32_FIXTURES.items():
        packet_id, task_id, acceptance_id, area, uat_report, fixture_names = fixture_spec
        for fixture_name in fixture_names:
            fixture_path = FIXTURES / area / fixture_name / "fixture.json"
            assert fixture_path.is_file(), f"missing canonical fixture: {fixture_path}"
            payload = json.loads(fixture_path.read_text(encoding="utf-8"))
            assert payload["schema_version"] == "HATE/expansion-gap-fixture/v1"
            assert payload["gap_id"] == gap_id
            assert payload["packet_id"] == packet_id
            assert payload["task_seed_id"] == task_id
            assert payload["acceptance_id"] == acceptance_id
            assert payload["fixture_id"] == f"expansion-{area}-{fixture_name}"
            assert payload["expected"]["uat_report"] == uat_report


def test_w32_expansion_has_no_noncanonical_golden_fixture_aliases() -> None:
    noncanonical_areas = [
        "policy-simulation",
        "bulk-portability",
        "notifications",
        "self-hosted",
        "data-classification",
        "docs-lifecycle",
    ]

    for area in noncanonical_areas:
        assert not (FIXTURES / area / "golden-walkthrough" / "fixture.json").exists()


def test_w32_expansion_registry_uses_schema_files_only() -> None:
    registry = _read(SCHEMAS / "schema-registry.json")
    record_types = [
        "onboarding",
        "policy-simulation",
        "bulk-portability",
        "notification",
        "self-hosted",
        "data-classification",
        "docs-lifecycle",
    ]

    for record_type in record_types:
        schema_name = f"{record_type}-report"
        assert f"schemas/HATE/v1/{schema_name}.schema.json" in registry
        assert not (SCHEMAS / f"{schema_name}.json").exists()
