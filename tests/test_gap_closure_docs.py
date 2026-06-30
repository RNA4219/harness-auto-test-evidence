"""Documentation consistency checks for HATE product gap closure."""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROCESS = ROOT / "docs" / "process"
TASKS = ROOT / "docs" / "tasks"
ACCEPTANCE = ROOT / "docs" / "acceptance"
FIXTURES = ROOT / "fixtures"


GAP_IDS = [f"HATE-GAP-{index:03d}" for index in range(1, 27)]
REQUIRED_CONTRACTS = [
    "PRODUCT_REQUIREMENTS_GAP_BACKLOG.md",
    "PRODUCT_REQUIREMENTS_GAP_CLOSURE_PACKETS.md",
    "WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md",
    "HOSTED_WORKER_RUNTIME_CONTRACT.md",
    "TENANT_ISOLATION_CONTRACT.md",
    "GITHUB_INTEGRATION_CONTRACT.md",
    "STORE_MIGRATION_INDEX_REBUILD_CONTRACT.md",
    "REAL_REPO_EVALUATION_CONTRACT.md",
    "ADAPTER_CORPUS_MANIFEST.md",
    "PRODUCT_E2E_UAT_CONTRACT.md",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_required_gap_closure_contracts_exist():
    missing = [name for name in REQUIRED_CONTRACTS if not (PROCESS / name).is_file()]
    assert missing == []


def test_all_gap_ids_are_in_backlog_packet_task_seed_and_acceptance_ledgers():
    backlog = _read(PROCESS / "PRODUCT_REQUIREMENTS_GAP_BACKLOG.md")
    packets = _read(PROCESS / "PRODUCT_REQUIREMENTS_GAP_CLOSURE_PACKETS.md")
    task_seeds = _read(TASKS / "HATE_GAP_CLOSURE_TASK_SEEDS.md")
    acceptance = _read(ACCEPTANCE / "HATE_GAP_CLOSURE_ACCEPTANCE.md")

    missing = {}
    for gap_id in GAP_IDS:
        locations = {
            "backlog": gap_id in backlog,
            "packets": gap_id in packets,
            "task_seeds": gap_id in task_seeds,
            "acceptance": gap_id in acceptance,
        }
        absent = [name for name, present in locations.items() if not present]
        if absent:
            missing[gap_id] = absent

    assert missing == {}


def test_all_gap_ids_have_task_seed_and_acceptance_ids():
    task_seeds = _read(TASKS / "HATE_GAP_CLOSURE_TASK_SEEDS.md")
    acceptance = _read(ACCEPTANCE / "HATE_GAP_CLOSURE_ACCEPTANCE.md")

    missing = {}
    for index, gap_id in enumerate(GAP_IDS, start=1):
        task_id = f"TASK-HATE-GAP-{index:03d}"
        ac_id = f"AC-HATE-GAP-{index:03d}"
        absent = []
        if task_id not in task_seeds:
            absent.append(task_id)
        if ac_id not in task_seeds:
            absent.append(f"{ac_id} task reference")
        if ac_id not in acceptance:
            absent.append(ac_id)
        if gap_id not in acceptance:
            absent.append(f"{gap_id} acceptance reference")
        if absent:
            missing[gap_id] = absent

    assert missing == {}


def test_acceptance_ledger_does_not_overclaim_implementation():
    acceptance = _read(ACCEPTANCE / "HATE_GAP_CLOSURE_ACCEPTANCE.md")
    assert "Current ledger state: HATE-GAP-001 through HATE-GAP-026 are `implemented`" in acceptance
    assert "none are accepted until UAT approval is recorded." in acceptance
    assert "| AC-HATE-GAP-001 | HATE-GAP-001 |" in acceptance
    assert "| AC-HATE-GAP-002 | HATE-GAP-002 |" in acceptance
    assert "| implemented | awaiting acceptance |" in acceptance
    assert "| `accepted` |" in acceptance
    assert "Do not use `seeded`, `fixture_ready`, `checker_ready`, or `uat_ready` as implementation completion." in acceptance


def test_workflow_acceptance_record_exists_for_uat_readiness():
    records = sorted(ACCEPTANCE.glob("AC-*.md"))
    assert records
    text = "\n".join(path.read_text(encoding="utf-8") for path in records)
    for gap_id in GAP_IDS:
        acceptance_id = gap_id.replace("HATE-GAP", "AC-HATE-GAP")
        assert acceptance_id in text
    for heading in ["## Scope", "## Acceptance Criteria", "## Evidence", "## Verification Result"]:
        assert heading in text


def test_workflow_acceptance_index_links_all_gap_acceptance_ids():
    index = _read(ACCEPTANCE / "INDEX.md")
    assert "AC-20260630-01.md" in index
    for gap_id in GAP_IDS:
        acceptance_id = gap_id.replace("HATE-GAP", "AC-HATE-GAP")
        assert acceptance_id in index


def test_workflow_cookbook_coverage_gate_is_required():
    task_seeds = _read(TASKS / "HATE_GAP_CLOSURE_TASK_SEEDS.md")
    assert "--cov-fail-under=80" in task_seeds


def test_workflow_cookbook_imported_operational_policies_are_required():
    contract = _read(PROCESS / "WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md")
    acceptance = _read(ACCEPTANCE / "AC-20260630-01.md")
    combined = contract + "\n" + acceptance

    for term in [
        "Priority Score",
        "priority_score",
        ".ga/qa-metrics.json",
        "spec_completeness",
        "birdseye_refresh_delay_minutes",
        "review_latency",
        "feature detection",
        "governance/predictor.yaml",
        "check_security_posture.py",
        "check_release_evidence.py",
        "branch protection",
    ]:
        assert term in combined


def test_workflow_cookbook_trace_checks_are_reported():
    report = json.loads((FIXTURES / "gap-closure" / "expected" / "gap-closure-report.json").read_text(encoding="utf-8"))
    check_ids = {check["check_id"] for check in report["workflow_alignment"]["checks"]}

    assert "workflow_task_seed_sync" in check_ids
    assert "workflow_acceptance_index" in check_ids
    assert "workflow_completion_trace" in check_ids
    assert "workflow_birdseye_invariants" in check_ids
    assert "workflow_evidence_minimum_fields" in check_ids
    assert "workflow_priority_score_policy" in check_ids
    assert "workflow_metrics_kpi_policy" in check_ids
    assert "workflow_feature_detection_policy" in check_ids
    assert "workflow_security_release_evidence_policy" in check_ids


def test_packet_ledger_names_fixture_and_uat_columns():
    packets = _read(PROCESS / "PRODUCT_REQUIREMENTS_GAP_CLOSURE_PACKETS.md")
    assert "Positive fixture" in packets
    assert "Negative fixture" in packets
    assert "UAT evidence" in packets
    assert "Done gate" in packets


def test_all_gap_fixture_paths_exist_and_are_canonical():
    packets = _read(PROCESS / "PRODUCT_REQUIREMENTS_GAP_CLOSURE_PACKETS.md")
    fixture_paths = sorted(
        {
            match
            for match in re.findall(r"`(fixtures/[^`]+/fixture\.json)`", packets)
        }
    )

    assert len(fixture_paths) == 76

    missing = [path for path in fixture_paths if not (ROOT / path).is_file()]
    assert missing == []

    for path in fixture_paths:
        payload = json.loads((ROOT / path).read_text(encoding="utf-8"))
        assert payload["schema_version"] in {
            "HATE/workflow-gap-fixture/v1",
            "HATE/product-gap-fixture/v1",
        }
        assert payload["fixture_id"]
        assert payload["gap_id"] in GAP_IDS
        assert payload["packet_id"].startswith("HATE-PKT-")
        assert payload["task_seed_id"].startswith("TASK-HATE-GAP-")
        assert payload["acceptance_id"].startswith("AC-HATE-GAP-")
        assert payload["case_kind"] in {"positive", "negative"}
        assert payload["expected"]["status"] in {"pass", "hold"}
        assert payload["expected"]["uat_report"].endswith(".json")
        if payload["case_kind"] == "negative":
            assert payload["expected"]["readiness_effect"] == "hold"
            assert payload["expected"]["finding_code"]
