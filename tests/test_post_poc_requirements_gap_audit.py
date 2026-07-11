from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "process" / "POST_POC_REQUIREMENTS_GAP_AUDIT.md"
CHECKLIST = ROOT / "docs" / "process" / "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md"
DETAIL_SPEC = ROOT / "docs" / "process" / "POST_POC_PRODUCTIZATION_DETAIL_SPEC.md"
PACKETS = ROOT / "docs" / "process" / "PRODUCT_PLATFORM_PHASE_IMPLEMENTATION_PACKETS.md"
IMPLEMENTATION_CHECKLIST = ROOT / "docs" / "process" / "POST_POC_IMPLEMENTATION_GAP_CHECKLIST.md"
GAP_REGISTRY = ROOT / "docs" / "process" / "post-poc-gap-registry.json"


def test_post_poc_gap_audit_exists_and_tracks_enough_product_gaps() -> None:
    text = AUDIT.read_text(encoding="utf-8")

    gap_ids = sorted(set(re.findall(r"HATE-POSTPOC-GAP-\d{3}", text)))
    assert len(gap_ids) >= 16
    assert gap_ids[0] == "HATE-POSTPOC-GAP-001"
    assert "PoC completion means" in text
    assert "It does not mean product" in text
    assert "No-Go" in text
    assert "Acceptance Evidence" in text


def test_post_poc_gap_audit_covers_operational_productization_categories() -> None:
    text = AUDIT.read_text(encoding="utf-8")
    required_terms = [
        "Hosted scheduler runtime",
        "Interactive dashboard frontend",
        "Notification delivery runtime",
        "Baseline promotion workflow",
        "Real-repo roster operations",
        "Plugin distribution and trust",
        "Live connector runtime",
        "Long-term history analytics",
        "Docs and acceptance freshness CI",
        "QEG and Shipyard release handoff",
        "Hosted multi-tenant API",
        "Store backup, restore, and DR operations",
        "Capacity benchmark with measured baselines",
        "Compliance and procurement evidence",
        "Observability and incident operations",
        "Human review operating UI/CLI",
    ]

    for term in required_terms:
        assert term in text


def test_post_poc_gap_audit_is_linked_from_requirements_and_readme() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    prd = (ROOT / "docs" / "process" / "PRODUCT_REQUIREMENTS_DEFINITION.md").read_text(encoding="utf-8")
    platform_requirements = (ROOT / "docs" / "process" / "PRODUCT_PLATFORM_PHASE_REQUIREMENTS.md").read_text(
        encoding="utf-8"
    )

    for text in (readme, prd, platform_requirements):
        assert "POST_POC_REQUIREMENTS_GAP_AUDIT.md" in text

    assert "POST_POC_PRODUCTIZATION_DETAIL_SPEC.md" in readme
    assert "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md" in readme
    assert "POST_POC_IMPLEMENTATION_GAP_CHECKLIST.md" in readme
    assert "PoC 100% は product / enterprise / regulated 要件完了を意味しない" in readme
    assert "Product-grade summaries must expose open post-PoC gaps" in platform_requirements


def test_spec_traceability_checklist_cross_checks_every_post_poc_gap() -> None:
    audit_text = AUDIT.read_text(encoding="utf-8")
    checklist_text = CHECKLIST.read_text(encoding="utf-8")
    audit_gap_ids = sorted(set(re.findall(r"HATE-POSTPOC-GAP-\d{3}", audit_text)))
    checklist_gap_ids = sorted(set(re.findall(r"HATE-POSTPOC-GAP-\d{3}", checklist_text)))

    assert audit_gap_ids
    assert set(audit_gap_ids).issubset(set(checklist_gap_ids))
    assert "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md" in audit_text
    assert "All 16 local evidence slices are accepted" in checklist_text
    assert "All 16 product gaps remain open" in checklist_text


def test_spec_traceability_checklist_has_required_columns_and_no_go_rule() -> None:
    text = CHECKLIST.read_text(encoding="utf-8")
    required_columns = [
        "Gap ID",
        "Local Slice",
        "Product Status",
        "Implementation",
        "Tests",
        "Acceptance",
        "Remaining Work",
    ]

    for column in required_columns:
        assert column in text

    assert "Report-only or docs-only closure" in text
    assert "BEGIN GENERATED:POST_POC_TRACEABILITY" in text
    assert "local_slice_status=accepted" in text
    assert "product_status=open" in text


def test_post_poc_productization_detail_spec_lowers_every_gap() -> None:
    audit_text = AUDIT.read_text(encoding="utf-8")
    detail_text = DETAIL_SPEC.read_text(encoding="utf-8")
    gap_ids = sorted(set(re.findall(r"HATE-POSTPOC-GAP-\d{3}", audit_text)))

    for gap_id in gap_ids:
        assert f"## {gap_id}:" in detail_text

    required_phrases = [
        "Record types:",
        "Required fields:",
        "Failure taxonomy:",
        "Required fixtures:",
        "Acceptance:",
        "HATE remains pre-QEG evidence",
    ]
    for phrase in required_phrases:
        assert phrase in detail_text


def test_post_poc_implementation_packets_cover_every_gap() -> None:
    audit_text = AUDIT.read_text(encoding="utf-8")
    packets_text = PACKETS.read_text(encoding="utf-8")
    gap_ids = sorted(set(re.findall(r"HATE-POSTPOC-GAP-\d{3}", audit_text)))

    for index, gap_id in enumerate(gap_ids, start=1):
        assert gap_id in packets_text
        assert f"POSTPOC-PKT-{index:03d}" in packets_text

    assert "POST_POC_PRODUCTIZATION_DETAIL_SPEC.md" in packets_text
    assert "Each packet must add runtime/schema/fixtures/tests" in packets_text


def test_post_poc_implementation_gap_checklist_has_workflow_task_seeds() -> None:
    audit_text = AUDIT.read_text(encoding="utf-8")
    checklist_text = IMPLEMENTATION_CHECKLIST.read_text(encoding="utf-8")
    gap_ids = sorted(set(re.findall(r"HATE-POSTPOC-GAP-\d{3}", audit_text)))

    required_seed_fields = [
        "task_id",
        "objective",
        "scope.in",
        "scope.out",
        "requirements.behavior",
        "requirements.constraints",
        "commands",
        "dependencies",
        "priority_score",
    ]
    for field in required_seed_fields:
        assert field in checklist_text

    for index, gap_id in enumerate(gap_ids, start=1):
        assert gap_id in checklist_text
        assert f"TASK-POSTPOC-{index:03d}" in checklist_text
        assert f"POSTPOC-PKT-{index:03d}" in checklist_text

    assert checklist_text.count("accepted") >= 2
    assert checklist_text.count("not_implemented") == 0
    assert "No task is marked `done` without an acceptance record." in checklist_text
    assert "Birdseye/codemap freshness is required after implementation." in checklist_text


def test_post_poc_implementation_gap_checklist_is_linked_from_canonical_docs() -> None:
    prd = (ROOT / "docs" / "process" / "PRODUCT_REQUIREMENTS_DEFINITION.md").read_text(encoding="utf-8")
    spec_checklist = CHECKLIST.read_text(encoding="utf-8")
    gap_audit = AUDIT.read_text(encoding="utf-8")

    for text in (prd, spec_checklist, gap_audit):
        assert "POST_POC_IMPLEMENTATION_GAP_CHECKLIST.md" in text

def test_post_poc_registry_is_canonical_and_separates_local_from_product_status() -> None:
    registry = json.loads(GAP_REGISTRY.read_text(encoding="utf-8"))

    assert registry["product_ready"] is False
    assert registry["release_authority"] == "external"
    assert len(registry["gaps"]) == 16
    assert len({gap["gap_id"] for gap in registry["gaps"]}) == 16
    assert {gap["local_slice_status"] for gap in registry["gaps"]} == {"accepted"}
    assert {gap["product_status"] for gap in registry["gaps"]} == {"open"}
    for gap in registry["gaps"]:
        assert gap["remaining_work"]
        assert gap["implementation_refs"]
        assert gap["test_refs"]
        assert (ROOT / gap["acceptance_ref"]).exists()