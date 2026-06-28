"""Tests for P1b workflow and downstream advisory artifact mapping."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from hate.p0b import export_qeg
from hate.p1b import generate_workflow_mapping


def test_p1b_generates_downstream_mapping_artifacts(tmp_path: Path) -> None:
    """P1b links QEG and trust artifacts to RanD, Shipyard, and workflow records."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    trust_dir = Path("fixtures/golden/p1a-trust-minimal/expected")
    out_dir = tmp_path / "workflow-output"

    result = generate_workflow_mapping(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        trust_dir=trust_dir,
        out_dir=out_dir,
    )

    assert result["workflow_status"] == "success"
    assert result["publish_gate_override"] is False
    assert result["shipyard_state_override"] is False
    assert "requirement-evidence-alignment.json" in result["generated"]
    assert "shipyard-run-evidence.json" in result["generated"]
    assert "workflow-evidence.jsonl" in result["generated"]
    assert "workflow-cookbook-evidence-map.json" in result["generated"]

    alignment = json.loads((out_dir / "requirement-evidence-alignment.json").read_text())
    assert alignment["record_type"] == "requirement_alignment"
    assert alignment["summary"]["gate_verdict"] == "go"
    assert alignment["summary"]["unverified_acceptance_count"] == 0
    assert alignment["requirements"][0]["unverified_acceptance"] == []
    assert alignment["boundary"]["rand_verdict_override"] is False
    assert alignment["boundary"]["manual_bb_gate_override"] is False

    task_seed = json.loads((out_dir / "workflow-task-seed.json").read_text())
    assert task_seed["task_id"] == "HATE-MVP-007-P1B-WORKFLOW-MAPPING"
    assert task_seed["acceptance_refs"] == ["AC-HATE-P1B-WORKFLOW-MAPPING"]
    assert "shipyard-run-evidence.json" in task_seed["evidence_refs"]

    acceptance = json.loads((out_dir / "workflow-acceptance-record.json").read_text())
    assert acceptance["verdict"] == "accepted"
    assert acceptance["release_gate_override"] is False
    assert any(check["check_id"] == "p1b-shipyard-advisory-only" for check in acceptance["checks"])

    shipyard = json.loads((out_dir / "shipyard-run-evidence.json").read_text())
    assert shipyard["mode"] == "local_advisory_evidence"
    assert shipyard["shipyard_state_override"] is False
    assert shipyard["publish_gate_override"] is False
    assert shipyard["dq_summary"]["unverified_acceptance_count"] == 0

    stale = json.loads((out_dir / "workflow-docs-stale.json").read_text())
    assert stale["checker_reimplemented"] is False
    assert stale["docs"]

    birdseye = json.loads((out_dir / "workflow-birdseye-map.json").read_text())
    assert birdseye["birdseye_generator_reimplemented"] is False
    assert birdseye["nodes"]
    assert birdseye["edges"]

    workflow_map = json.loads((out_dir / "workflow-cookbook-evidence-map.json").read_text())
    assert workflow_map["record_type"] == "workflow_cookbook_evidence_map"
    assert workflow_map["workflow_cookbook"]["plugin_host_reimplemented"] is False
    assert workflow_map["workflow_cookbook"]["birdseye_generator_reimplemented"] is False
    assert workflow_map["workflow_cookbook"]["checker_reimplemented"] is False
    assert workflow_map["task_seed"]["artifact_ref"] == "workflow-task-seed.json"
    assert workflow_map["acceptance_record"]["artifact_ref"] == "workflow-acceptance-record.json"
    assert len(workflow_map["evidence_records"]) == 4
    assert workflow_map["birdseye"]["artifact_ref"] == "workflow-birdseye-map.json"
    assert workflow_map["docs_stale"]["artifact_ref"] == "workflow-docs-stale.json"

    evidence_records = [
        json.loads(line)
        for line in (out_dir / "workflow-evidence.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert len(evidence_records) == 4
    assert {record["record_type"] for record in evidence_records} == {"workflow_evidence"}
    assert all("C:\\Users" not in json.dumps(record) for record in evidence_records)


def test_p1b_cli_workflow_map(tmp_path: Path) -> None:
    """CLI `hate workflow map` generates the same P1b artifact set."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    trust_dir = Path("fixtures/golden/p1a-trust-minimal/expected")
    out_dir = tmp_path / "workflow-cli-output"

    result = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "workflow", "map",
            "--bundle", str(fixture_dir / "qeg-bundle.json"),
            "--report", str(fixture_dir / "qeg-export-report.json"),
            "--trust", str(trust_dir),
            "--out", str(out_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["workflow_status"] == "success"
    assert output["release_gate_override"] is False
    assert output["shipyard_state_override"] is False
    assert (out_dir / "workflow-evidence.jsonl").exists()


def test_p1b_ingests_rand_requirements_packet(tmp_path: Path) -> None:
    """P1b ingests RanD requirements/KPI/acceptance without inventing verdicts."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    trust_dir = Path("fixtures/golden/p1a-trust-minimal/expected")
    rand_packet = Path("fixtures/rand/requirements-packet/input/requirements_packet.json")
    out_dir = tmp_path / "workflow-rand-output"

    result = generate_workflow_mapping(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        trust_dir=trust_dir,
        out_dir=out_dir,
        rand_requirements_path=rand_packet,
    )

    assert result["workflow_status"] == "conditional"
    alignment = json.loads((out_dir / "requirement-evidence-alignment.json").read_text(encoding="utf-8"))
    assert alignment["rand"]["requirements_packet_ingested"] is True
    assert alignment["rand"]["packet_id"] == "rand-packet-hate-p1b-001"
    assert alignment["summary"]["requirement_count"] == 2
    assert alignment["summary"]["gate_verdict"] == "conditional_go"
    assert alignment["summary"]["rand_requirement_count"] == 2
    requirements = {item["requirement_id"]: item for item in alignment["requirements"]}
    assert requirements["REQ-RAND-AUTH-EVIDENCE"]["gate_verdict"] == "go"
    assert requirements["REQ-RAND-AUTH-EVIDENCE"]["upstream_gate_verdict"] == "go"
    assert requirements["REQ-RAND-AUTH-EVIDENCE"]["kpis"][0]["kpi_id"] == "KPI-AUTH-COVERAGE"
    auth_trace = requirements["REQ-RAND-AUTH-EVIDENCE"]["trace_links"][0]
    assert auth_trace["risk_id"] == "risk-auth-high"
    assert auth_trace["canonical_test_id"] == "junit:tests/test_auth.py::test_login"
    assert auth_trace["execution_status"] == "passed"
    assert auth_trace["coverage_refs"][0]["file"] == "src/auth.py"
    assert requirements["REQ-RAND-DB-EVIDENCE"]["gate_verdict"] == "conditional_go"
    assert requirements["REQ-RAND-DB-EVIDENCE"]["acceptance_criteria"][0]["acceptance_id"] == "AC-DB-MANUAL-BRIDGE"
    assert alignment["summary"]["trace_link_count"] == 2
    assert alignment["summary"]["fully_linked_requirement_count"] == 2
    assert alignment["boundary"]["rand_verdict_override"] is False
    assert any("requirements_packet.json" in ref for ref in alignment["source_refs"])


def test_p1b_rand_requirements_packet_maps_missing_execution_to_related_requirement(tmp_path: Path) -> None:
    """RanD requirement risk refs select the matching missing-execution gap."""
    fixture_dir = _missing_execution_p0b_output(tmp_path)
    trust_dir = Path("fixtures/golden/p1a-trust-minimal/expected")
    rand_packet = Path("fixtures/rand/requirements-packet/input/requirements_packet.json")
    out_dir = tmp_path / "workflow-rand-gap-output"

    result = generate_workflow_mapping(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        trust_dir=trust_dir,
        out_dir=out_dir,
        rand_requirements_path=rand_packet,
    )

    assert result["workflow_status"] == "conditional"
    alignment = json.loads((out_dir / "requirement-evidence-alignment.json").read_text(encoding="utf-8"))
    requirements = {item["requirement_id"]: item for item in alignment["requirements"]}
    assert requirements["REQ-RAND-AUTH-EVIDENCE"]["evidence_coverage"] == "covered"
    assert requirements["REQ-RAND-AUTH-EVIDENCE"]["unverified_acceptance"] == []
    db_requirement = requirements["REQ-RAND-DB-EVIDENCE"]
    assert db_requirement["evidence_coverage"] == "partial"
    assert db_requirement["unverified_acceptance"][0]["risk_id"] == "risk-db-high"
    assert db_requirement["gate_verdict"] == "conditional_go"
    db_trace = db_requirement["trace_links"][0]
    assert db_trace["risk_id"] == "risk-db-high"
    assert db_trace["evidence_state"] == "missing_execution"


def test_p1b_ingests_rand_audit_no_go_without_overwrite(tmp_path: Path) -> None:
    """RanD audit no_go remains no_go and is not promoted by HATE."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    trust_dir = Path("fixtures/golden/p1a-trust-minimal/expected")
    rand_audit = Path("fixtures/rand/audit-no-overwrite/input/audit_packet.json")
    out_dir = tmp_path / "workflow-rand-audit-output"

    result = generate_workflow_mapping(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        trust_dir=trust_dir,
        out_dir=out_dir,
        rand_audit_path=rand_audit,
    )

    assert result["workflow_status"] == "conditional"
    alignment = json.loads((out_dir / "requirement-evidence-alignment.json").read_text(encoding="utf-8"))
    assert alignment["summary"]["gate_verdict"] == "no_go"
    assert alignment["summary"]["rand_audit_overall_assessment"] == "no_go"
    assert alignment["rand_audit"]["audit_packet_ingested"] is True
    assert alignment["rand_audit"]["packet_id"] == "rand-audit-hate-p1b-002"
    assert alignment["rand_audit"]["overall_assessment"] == "no_go"
    assert alignment["rand_audit"]["verdicts_preserved"] is True
    assert alignment["rand_audit"]["no_overwrite_enforced"] is True
    audit_verdicts = {item["requirement_id"]: item for item in alignment["rand_audit"]["requirement_verdicts"]}
    assert audit_verdicts["REQ-HATE-P0B-QEG-EXPORT"]["gate_verdict"] == "no_go"
    assert audit_verdicts["REQ-HATE-P0B-QEG-EXPORT"]["upstream_gate_verdict"] == "no_go"
    assert alignment["boundary"]["rand_verdict_override"] is False
    assert alignment["boundary"]["rand_audit_overwrite"] is False

    acceptance = json.loads((out_dir / "workflow-acceptance-record.json").read_text(encoding="utf-8"))
    assert any(check["check_id"] == "p1b-rand-audit-no-overwrite" for check in acceptance["checks"])

    shipyard = json.loads((out_dir / "shipyard-run-evidence.json").read_text(encoding="utf-8"))
    assert shipyard["dq_summary"]["gate_verdict"] == "no_go"
    assert shipyard["dq_summary"]["rand_audit_overall_assessment"] == "no_go"
    assert shipyard["publish_gate_override"] is False

    evidence_records = [
        json.loads(line)
        for line in (out_dir / "workflow-evidence.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(record["evidence_id"] == "evidence:p1b:rand-audit" for record in evidence_records)
    audit_record = next(record for record in evidence_records if record["evidence_id"] == "evidence:p1b:rand-audit")
    assert audit_record["rand_audit_overwrite"] is False


def test_p1b_rand_audit_no_go_wins_over_requirements_packet(tmp_path: Path) -> None:
    """A conditional requirements packet cannot hide a no_go RanD audit packet."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    trust_dir = Path("fixtures/golden/p1a-trust-minimal/expected")
    rand_packet = Path("fixtures/rand/requirements-packet/input/requirements_packet.json")
    rand_audit = Path("fixtures/rand/audit-no-overwrite/input/audit_packet.json")
    out_dir = tmp_path / "workflow-rand-requirements-and-audit-output"

    generate_workflow_mapping(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        trust_dir=trust_dir,
        out_dir=out_dir,
        rand_requirements_path=rand_packet,
        rand_audit_path=rand_audit,
    )

    alignment = json.loads((out_dir / "requirement-evidence-alignment.json").read_text(encoding="utf-8"))
    assert alignment["summary"]["gate_verdict"] == "no_go"
    assert alignment["rand"]["requirements_packet_ingested"] is True
    assert alignment["rand_audit"]["overall_assessment"] == "no_go"
    assert alignment["boundary"]["rand_verdict_override"] is False


def test_p1b_ingests_shipyard_worker_result_and_run_system_packet_refs(tmp_path: Path) -> None:
    """Shipyard WorkerResult/RunSystemPacket refs are preserved as advisory evidence."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    trust_dir = Path("fixtures/golden/p1a-trust-minimal/expected")
    worker_result = Path("fixtures/shipyard/worker-result/input/worker_result.json")
    run_system_packet = Path("fixtures/shipyard/worker-result/input/run_system_packet.json")
    out_dir = tmp_path / "workflow-shipyard-output"

    result = generate_workflow_mapping(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        trust_dir=trust_dir,
        out_dir=out_dir,
        shipyard_worker_result_path=worker_result,
        shipyard_run_system_packet_path=run_system_packet,
    )

    assert result["workflow_status"] == "success"
    assert result["shipyard_state_override"] is False
    shipyard = json.loads((out_dir / "shipyard-run-evidence.json").read_text(encoding="utf-8"))
    assert shipyard["shipyard_inputs"]["worker_result_ingested"] is True
    assert shipyard["shipyard_inputs"]["run_system_packet_ingested"] is True
    assert shipyard["shipyard_inputs"]["refs_preserved"] is True
    assert shipyard["shipyard_inputs"]["advisory_only"] is True
    assert shipyard["shipyard_refs"]["worker_result"]["job_id"] == "job_hate_p1b_004_acceptance"
    assert shipyard["shipyard_refs"]["worker_result"]["typed_ref"] == "shipyard-cp:worker_result:claude_code:job_hate_p1b_004_acceptance"
    assert shipyard["shipyard_refs"]["worker_result"]["artifact_refs"][0]["artifact_id"] == "artifact:p1b:workflow-evidence"
    assert shipyard["shipyard_refs"]["run_system_packet"]["mode"] == "advisory"
    assert shipyard["shipyard_refs"]["run_system_packet"]["run_ref"] == "agent-taskstate:run:job_hate_p1b_004_acceptance"
    assert shipyard["shipyard_refs"]["run_system_packet"]["job_ref"] == "shipyard-cp:worker_job:claude_code:job_hate_p1b_004_acceptance"
    assert shipyard["shipyard_refs"]["run_system_packet"]["contract_refs"]["evidence_ref"] == "agent-protocols:evidence:job_hate_p1b_004_acceptance-succeeded"
    assert shipyard["shipyard_refs"]["audit_refs"] == ["run.systemPacketPrepared", "run.systemGateEvaluated"]
    assert shipyard["shipyard_state_override"] is False
    assert shipyard["publish_gate_override"] is False

    evidence_records = [
        json.loads(line)
        for line in (out_dir / "workflow-evidence.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    shipyard_record = next(record for record in evidence_records if record["evidence_id"] == "evidence:p1b:shipyard")
    assert shipyard_record["shipyard_refs_preserved"] is True
    assert shipyard_record["shipyard_state_override"] is False


def test_p1b_shipyard_publish_claim_does_not_override_hate_boundaries(tmp_path: Path) -> None:
    """Shipyard publish-looking input never flips HATE override flags."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    trust_dir = Path("fixtures/golden/p1a-trust-minimal/expected")
    worker_result = Path("fixtures/shipyard/no-overwrite/input/worker_result.json")
    run_system_packet = Path("fixtures/shipyard/no-overwrite/input/run_system_packet.json")
    out_dir = tmp_path / "workflow-shipyard-no-overwrite-output"

    result = generate_workflow_mapping(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        trust_dir=trust_dir,
        out_dir=out_dir,
        shipyard_worker_result_path=worker_result,
        shipyard_run_system_packet_path=run_system_packet,
    )

    assert result["publish_gate_override"] is False
    assert result["release_gate_override"] is False
    assert result["shipyard_state_override"] is False
    alignment = json.loads((out_dir / "requirement-evidence-alignment.json").read_text(encoding="utf-8"))
    assert alignment["boundary"]["publish_gate_override"] is False
    assert alignment["boundary"]["release_gate_override"] is False

    acceptance = json.loads((out_dir / "workflow-acceptance-record.json").read_text(encoding="utf-8"))
    assert acceptance["publish_gate_override"] is False
    assert acceptance["release_gate_override"] is False

    shipyard = json.loads((out_dir / "shipyard-run-evidence.json").read_text(encoding="utf-8"))
    assert shipyard["shipyard_refs"]["run_system_packet"]["mode"] == "enforce"
    assert shipyard["shipyard_refs"]["run_system_packet"]["stage"] == "publish"
    assert shipyard["shipyard_refs"]["worker_result"]["external_refs"][0]["ref"] == "publish:requested"
    assert shipyard["shipyard_state_override"] is False
    assert shipyard["release_gate_override"] is False
    assert shipyard["publish_gate_override"] is False
    assert shipyard["shipyard_inputs"]["advisory_only"] is True


def _missing_execution_p0b_output(tmp_path: Path) -> Path:
    fixture_dir = tmp_path / "missing-execution-input"
    if fixture_dir.exists():
        shutil.rmtree(fixture_dir)
    shutil.copytree(Path("fixtures/golden/p0b-qeg-minimal/input"), fixture_dir)
    test_results = fixture_dir / "p0a" / "HATE-test-results.ndjson"
    records = [json.loads(line) for line in test_results.read_text(encoding="utf-8").splitlines() if line]
    kept = [
        record for record in records
        if record.get("payload", {}).get("canonical_test_id") != "junit:tests/test_db.py::test_connection"
    ]
    test_results.write_text("\n".join(json.dumps(record) for record in kept) + "\n", encoding="utf-8")
    out_dir = tmp_path / "missing-execution-p0b"
    export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)
    return out_dir
