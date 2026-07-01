from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "HATE/v1"
RECORD_TYPE = "validation-cycle-report"
CHAIN_STEPS = ("RanD", "Code-to-gate", "HATE", "manual-bb", "QEG")
GO_STATUSES = {"ran"}
QEG_GO_STATUSES = {"go"}


class ValidationCycleError(Exception):
    def __init__(self, message: str, exit_code: int = 2, report: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.report = report


def build_validation_cycle_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "validation-cycle-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate repeated five-tool/QEG hardening cycles."""

    cycles = [_normalize_cycle(cycle) for cycle in input_data.get("cycles", []) if isinstance(cycle, dict)]
    expected_cycle_count = int(input_data.get("expected_cycle_count", 10) or 10)
    findings: list[dict[str, Any]] = []
    evaluated_cycles = []

    if len(cycles) != expected_cycle_count:
        findings.append(_finding(
            "validation_cycle_count_mismatch",
            "hard_dq",
            "validation-cycles",
            f"Expected {expected_cycle_count} validation cycles but found {len(cycles)}.",
        ))

    for cycle in cycles:
        cycle_findings = _findings_for_cycle(cycle)
        cycle_verdict = "go" if not cycle_findings else "no_go"
        evaluated_cycles.append({**cycle, "cycle_verdict": cycle_verdict, "finding_count": len(cycle_findings)})
        findings.extend(cycle_findings)

    verdict = "go" if not findings and len(cycles) == expected_cycle_count else "no_go"
    source_refs = sorted(set(source_refs or input_data.get("sourceRefs") or ["validation-cycles"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": RECORD_TYPE,
        "report_id": report_id,
        "overall_status": "pass" if verdict == "go" else "blocked",
        "readiness_effect": "pass" if verdict == "go" else "hard_dq",
        "verdict": verdict,
        "expected_cycle_count": expected_cycle_count,
        "cycles": evaluated_cycles,
        "findings": findings,
        "summary": {
            "cycle_count": len(cycles),
            "go_cycle_count": sum(1 for cycle in evaluated_cycles if cycle["cycle_verdict"] == "go"),
            "no_go_cycle_count": sum(1 for cycle in evaluated_cycles if cycle["cycle_verdict"] != "go"),
            "finding_count": len(findings),
            "hard_dq_count": sum(1 for finding in findings if finding["readiness_effect"] == "hard_dq"),
            "qeg_go_count": sum(1 for cycle in evaluated_cycles if cycle["qeg_package"]["gate_status"] == "go"),
        },
        "qeg_final_approval_claimed": False,
        "limits": {
            "qeg_is_final_gate": True,
            "hate_must_not_claim_qeg_approval": True,
            "manual_bb_blockers_allowed_for_go": False,
        },
        "sourceRefs": source_refs,
    }


def evaluate_validation_cycle_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    report = build_validation_cycle_report(
        payload.get("input", payload),
        report_id=str(payload.get("fixture_id") or "validation-cycle-fixture"),
        source_refs=[str(payload.get("fixture_id") or "validation-cycle-fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "verdict": report["verdict"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def run_validation_cycles(*, fixture_path: Path, out_dir: Path) -> dict[str, Any]:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    result = evaluate_validation_cycle_fixture(payload)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "validation-cycle-report.json"
    report_path.write_text(json.dumps(result["report"], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if result["verdict"] != "go":
        raise ValidationCycleError("validation cycles did not reach go", report=result["report"])
    return result["report"]


def _normalize_cycle(raw: dict[str, Any]) -> dict[str, Any]:
    chain_status = raw.get("chain_status") if isinstance(raw.get("chain_status"), dict) else {}
    qeg_package = raw.get("qeg_package") if isinstance(raw.get("qeg_package"), dict) else {}
    release_candidate = raw.get("release_candidate_pack") if isinstance(raw.get("release_candidate_pack"), dict) else {}
    manual_bb = raw.get("manual_bb") if isinstance(raw.get("manual_bb"), dict) else {}
    return {
        "cycle_id": str(raw.get("cycle_id") or ""),
        "missing_possibility": str(raw.get("missing_possibility") or ""),
        "requirement_refs": [str(item) for item in raw.get("requirement_refs", []) if str(item)],
        "spec_refs": [str(item) for item in raw.get("spec_refs", []) if str(item)],
        "implementation_refs": [str(item) for item in raw.get("implementation_refs", []) if str(item)],
        "test_refs": [str(item) for item in raw.get("test_refs", []) if str(item)],
        "chain_status": {step: str(chain_status.get(step) or "") for step in CHAIN_STEPS},
        "manual_bb": {
            "brief_ref": str(manual_bb.get("brief_ref") or ""),
            "open_blockers": [str(item) for item in manual_bb.get("open_blockers", []) if str(item)],
            "p0_case_count": int(manual_bb.get("p0_case_count", 0) or 0),
        },
        "qeg_package": {
            "bundle_ref": str(qeg_package.get("bundle_ref") or ""),
            "validate_status": str(qeg_package.get("validate_status") or ""),
            "import_status": str(qeg_package.get("import_status") or ""),
            "gate_status": str(qeg_package.get("gate_status") or ""),
            "record_ref": str(qeg_package.get("record_ref") or ""),
            "approval_claimed_by_hate": bool(qeg_package.get("approval_claimed_by_hate")),
        },
        "release_candidate_pack": {
            "verdict": str(release_candidate.get("verdict") or ""),
            "blocker_count": int((release_candidate.get("summary") or {}).get("blocker_count", 0) or 0),
            "release_ready": bool((release_candidate.get("summary") or {}).get("release_ready", False)),
        },
        "sourceRefs": [str(item) for item in raw.get("sourceRefs", []) if str(item)],
    }


def _findings_for_cycle(cycle: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    cycle_id = cycle["cycle_id"] or "cycle"

    for field in ("missing_possibility", "requirement_refs", "spec_refs", "implementation_refs", "test_refs", "sourceRefs"):
        if not cycle[field]:
            findings.append(_finding("validation_cycle_missing_trace", "hard_dq", cycle_id, f"{field} is required."))

    for step, status in cycle["chain_status"].items():
        if status not in GO_STATUSES:
            findings.append(_finding("validation_cycle_chain_not_ran", "hard_dq", cycle_id, f"{step} must be ran before cycle go."))

    manual_bb = cycle["manual_bb"]
    if not manual_bb["brief_ref"] or manual_bb["p0_case_count"] <= 0:
        findings.append(_finding("validation_cycle_manual_bb_incomplete", "hard_dq", cycle_id, "manual-bb brief and P0 cases are required."))
    if manual_bb["open_blockers"]:
        findings.append(_finding("validation_cycle_manual_bb_blocker_open", "hard_dq", cycle_id, "manual-bb open blockers prevent go."))

    qeg_package = cycle["qeg_package"]
    if not qeg_package["bundle_ref"] or not qeg_package["record_ref"]:
        findings.append(_finding("validation_cycle_qeg_refs_missing", "hard_dq", cycle_id, "QEG bundle and record refs are required."))
    if qeg_package["validate_status"] != "pass" or qeg_package["import_status"] != "pass":
        findings.append(_finding("validation_cycle_qeg_package_failed", "hard_dq", cycle_id, "QEG validate/import must pass."))
    if qeg_package["gate_status"] not in QEG_GO_STATUSES:
        findings.append(_finding("validation_cycle_qeg_gate_not_go", "hard_dq", cycle_id, "QEG gate status must be go."))
    if qeg_package["approval_claimed_by_hate"]:
        findings.append(_finding("validation_cycle_qeg_approval_overclaim", "hard_dq", cycle_id, "HATE must not claim QEG final approval."))

    release_candidate = cycle["release_candidate_pack"]
    if release_candidate["verdict"] != "ready" or release_candidate["blocker_count"] != 0 or not release_candidate["release_ready"]:
        findings.append(_finding("validation_cycle_release_pack_not_ready", "hard_dq", cycle_id, "Release candidate pack must be ready without blockers."))

    return findings


def _finding(code: str, effect: str, source_ref: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "severity": "critical",
        "message": message,
        "sourceRef": source_ref,
        "readiness_effect": effect,
    }
