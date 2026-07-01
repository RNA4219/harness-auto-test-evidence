from __future__ import annotations

import json
from pathlib import Path

from hate.cli import main
from hate.validation_cycles import build_validation_cycle_report, evaluate_validation_cycle_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "validation-cycles" / "ten-cycle-go" / "fixture.json"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "validation-cycle-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"
SPEC = ROOT / "docs" / "process" / "PRODUCT_REQUIREMENTS_QEG_HARDENING_CYCLES.md"
PRD = ROOT / "docs" / "process" / "PRODUCT_REQUIREMENTS_DEFINITION.md"
ACCEPTANCE = ROOT / "docs" / "acceptance" / "QEG_HARDENING_CYCLE_ACCEPTANCE.md"
ACCEPTANCE_INDEX = ROOT / "docs" / "acceptance" / "INDEX.md"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_ten_cycle_go_fixture_passes() -> None:
    payload = _fixture()
    result = evaluate_validation_cycle_fixture(payload)

    assert result["status"] == "pass"
    assert result["verdict"] == "go"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "pass"
    assert result["report"]["summary"]["go_cycle_count"] == 10
    assert result["report"]["summary"]["finding_count"] == 0
    assert result["report"]["qeg_final_approval_claimed"] is False


def test_validation_cycle_schema_and_registry_are_present() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {item["record_type"]: item["schema"] for item in registry["records"]}

    assert schema["properties"]["record_type"]["const"] == "validation-cycle-report"
    assert records["validation-cycle-report"] == "schemas/HATE/v1/validation-cycle-report.schema.json"


def test_validation_cycle_spec_defines_all_ten_cycles() -> None:
    spec = SPEC.read_text(encoding="utf-8")

    for index in range(1, 11):
        assert f"Cycle {index}" in spec
        assert f"FR-CYCLE-{index:03d}" in spec
    assert "RanD -> Code-to-gate -> HATE -> manual-bb -> QEG" in spec
    assert "HATE は QEG final approval を主張しない" in spec


def test_prd_defines_validation_cycle_requirements_before_spec() -> None:
    prd = PRD.read_text(encoding="utf-8")

    assert "### 7.24 QEG Hardening Cycle Requirements" in prd
    for index in range(1, 11):
        assert f"FR-CYCLE-{index:03d}" in prd
    assert "HATE claiming QEG final" in prd


def test_validation_cycle_acceptance_records_all_ten_go_cycles() -> None:
    acceptance = ACCEPTANCE.read_text(encoding="utf-8")
    index = ACCEPTANCE_INDEX.read_text(encoding="utf-8")

    for cycle_index in range(1, 11):
        cycle_id = f"HATE-QEG-CYCLE-{cycle_index:03d}"
        assert cycle_id in acceptance
        assert cycle_id in index
    assert "Current state" in acceptance
    assert "| go |" in acceptance
    assert "External QEG Tool Run" in acceptance
    assert "actual verdict `go`" in acceptance
    assert "own-output validation PASS" in acceptance
    assert "`qeg_go_count=10`" in acceptance
    assert "QEG_HARDENING_CYCLE_ACCEPTANCE.md" in index


def test_missing_cycle_is_no_go() -> None:
    data = _fixture()["input"]
    report = build_validation_cycle_report({**data, "cycles": data["cycles"][:9]})

    assert report["verdict"] == "no_go"
    assert report["overall_status"] == "blocked"
    assert any(finding["code"] == "validation_cycle_count_mismatch" for finding in report["findings"])


def test_qeg_gate_not_go_is_hard_dq() -> None:
    data = json.loads(json.dumps(_fixture()["input"]))
    data["cycles"][0]["qeg_package"]["gate_status"] = "conditional_go"
    report = build_validation_cycle_report(data)

    assert report["verdict"] == "no_go"
    assert any(finding["code"] == "validation_cycle_qeg_gate_not_go" for finding in report["findings"])


def test_hate_qeg_approval_overclaim_is_hard_dq() -> None:
    data = json.loads(json.dumps(_fixture()["input"]))
    data["cycles"][0]["qeg_package"]["approval_claimed_by_hate"] = True
    report = build_validation_cycle_report(data)

    assert report["verdict"] == "no_go"
    assert any(finding["code"] == "validation_cycle_qeg_approval_overclaim" for finding in report["findings"])


def test_manual_bb_open_blocker_prevents_go() -> None:
    data = json.loads(json.dumps(_fixture()["input"]))
    data["cycles"][0]["manual_bb"]["open_blockers"] = ["P0 oracle unresolved"]
    report = build_validation_cycle_report(data)

    assert report["verdict"] == "no_go"
    assert any(finding["code"] == "validation_cycle_manual_bb_blocker_open" for finding in report["findings"])


def test_validation_cycle_cli_writes_report(tmp_path: Path) -> None:
    exit_code = main(["validation", "cycles", "--fixture", str(FIXTURE), "--out", str(tmp_path)])

    assert exit_code == 0
    report = json.loads((tmp_path / "validation-cycle-report.json").read_text(encoding="utf-8"))
    assert report["record_type"] == "validation-cycle-report"
    assert report["verdict"] == "go"
