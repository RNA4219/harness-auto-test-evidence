"""Checks for product requirement to worker-facing specification traceability."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROCESS = ROOT / "docs" / "process"


NEW_SPEC_DOCS = [
    "TEST_INTEGRITY_IMPLEMENTATION_SPEC.md",
    "ENTERPRISE_CONTROL_STATE_TRANSITION_SPEC.md",
    "RELEASE_CANDIDATE_PACK_VALIDATOR_SPEC.md",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_requirements_to_spec_gap_audit_exists_and_closes_findings() -> None:
    audit = _read(PROCESS / "REQUIREMENTS_TO_SPEC_GAP_AUDIT.md")

    for gap_id in [
        "HATE-REQSPEC-GAP-001",
        "HATE-REQSPEC-GAP-002",
        "HATE-REQSPEC-GAP-003",
        "HATE-REQSPEC-GAP-004",
    ]:
        assert gap_id in audit
    assert "| closed |" in audit


def test_new_requirement_spec_documents_are_referenced_by_prd_readme_and_audit() -> None:
    prd = _read(PROCESS / "PRODUCT_REQUIREMENTS_DEFINITION.md")
    readme = _read(ROOT / "README.md")
    readiness_audit = _read(PROCESS / "PRODUCT_REQUIREMENTS_500K_READINESS_AUDIT.md")
    gap_audit = _read(PROCESS / "REQUIREMENTS_TO_SPEC_GAP_AUDIT.md")

    for doc_name in NEW_SPEC_DOCS:
        assert (PROCESS / doc_name).is_file()
        assert doc_name in prd
        assert doc_name in readme
        assert doc_name in readiness_audit
        assert doc_name in gap_audit


def test_test_integrity_implementation_spec_has_executable_contract() -> None:
    spec = _read(PROCESS / "TEST_INTEGRITY_IMPLEMENTATION_SPEC.md")
    required_terms = [
        "test_skip_detected",
        "mock_abuse_detected",
        "assertion_quality",
        "implementation_test_coupling",
        "risk_without_oracle",
        "coverage_without_evidence",
        "manual_review_required",
        "Detector Output",
        "Fixture Matrix",
    ]

    assert [term for term in required_terms if term not in spec] == []


def test_enterprise_control_state_transition_spec_has_state_machines() -> None:
    spec = _read(PROCESS / "ENTERPRISE_CONTROL_STATE_TRANSITION_SPEC.md")
    required_terms = [
        "RBAC Decision Contract",
        "Audit Event Contract",
        "State Machines",
        "legal hold",
        "retention",
        "connector dry-run",
        "enterprise-control-report.schema.json",
    ]

    assert [term for term in required_terms if term not in spec] == []


def test_release_candidate_pack_validator_spec_has_blockers_and_hash() -> None:
    spec = _read(PROCESS / "RELEASE_CANDIDATE_PACK_VALIDATOR_SPEC.md")
    required_terms = [
        "Required Inputs",
        "Validator Output",
        "Blocking Rules",
        "Deterministic Hash",
        "qeg_approval_claimed: false",
        "release-candidate-pack.schema.json",
    ]

    assert [term for term in required_terms if term not in spec] == []
