"""Tests for P0b QEG export."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from hate.p0a import generate_p0a
from hate.p0b import ExportError, export_qeg
from hate.p0b_support import _validate_qeg_bundle_schema


def test_p0b_export_minimal_fixture(tmp_path: Path) -> None:
    """P0b export generates all required artifacts from minimal fixture."""
    fixture_dir = _copy_fixture(Path("fixtures/golden/p0b-qeg-minimal/input"), tmp_path / "input")
    out_dir = tmp_path / "output"

    result = export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)

    assert result["export_status"] == "success"
    assert result["exit_code"] == 0
    assert "qeg-bundle.json" in result["generated"]
    assert "evidence-map.json" in result["generated"]
    assert "qeg-export-report.json" in result["generated"]
    assert "qeg-export-summary.md" in result["generated"]
    assert "risk-debt-register.json" not in result["generated"]
    assert "manual-bb-bridge-requests.jsonl" not in result["generated"]
    assert result["publish_gate_override"] is False

    # Verify generated files exist
    assert (out_dir / "qeg-bundle.json").exists()
    assert (out_dir / "evidence-map.json").exists()
    assert (out_dir / "qeg-export-report.json").exists()
    assert (out_dir / "qeg-export-summary.md").exists()
    assert not (out_dir / "risk-debt-register.json").exists()
    assert not (out_dir / "manual-bb-bridge-requests.jsonl").exists()

    # Verify qeg-bundle.json structure
    bundle = json.loads((out_dir / "qeg-bundle.json").read_text())
    assert bundle["metadata"]["qegVersion"] == "HATE/v1"
    assert bundle["metadata"]["runId"] == "1001"
    assert len(bundle["nodes"]) >= 2  # At least gate_verdict + run
    assert len(bundle["edges"]) >= 1  # At least one edge

    # Verify gate_verdict node exists
    precheck_nodes = [n for n in bundle["nodes"] if n["kind"] == "gate_verdict"]
    assert len(precheck_nodes) == 1
    assert precheck_nodes[0]["data"]["decision"] == "eligible"
    assert precheck_nodes[0]["data"]["qeg_export_allowed"] is True

    # Verify evidence-map.json structure
    ev_map = json.loads((out_dir / "evidence-map.json").read_text())
    assert ev_map["schema_version"] == "HATE/v1"
    assert ev_map["run_id"] == "1001"
    assert "risks" in ev_map
    assert "tests" in ev_map
    assert "evidence" in ev_map
    assert "links" in ev_map
    assert "gaps" in ev_map
    assert len(ev_map["gaps"]["missing_execution"]) == 0

    # Verify qeg-export-report.json structure
    report = json.loads((out_dir / "qeg-export-report.json").read_text())
    assert report["schema_version"] == "HATE/v1"
    assert report["export_status"] == "success"
    assert report["publish_gate_override"] is False
    assert "completeness" in report
    assert len(report["missing_execution"]) == 0
    assert report["completeness"]["score"] == 1.0
    assert report["completeness"]["partial"] is False
    assert len(report["completeness"]["unsupportedClaims"]) == 0
    assert report["qeg_schema_compatibility"] == {
        "schema": "schemas/HATE/v1/qeg-bundle.schema.json",
        "valid": True,
        "errors": [],
    }

    # Verify summary.md is public-safe (no absolute paths leaked)
    summary = (out_dir / "qeg-export-summary.md").read_text()
    assert "publish_gate_override=false" in summary
    assert "C:\\Users" not in summary  # No absolute Windows paths
    assert "C:\\Users" not in json.dumps(bundle)
    assert "C:\\Users" not in json.dumps(report)


def test_p0b_minimal_golden_outputs_are_stable(tmp_path: Path) -> None:
    """Minimal P0b outputs stay aligned with the checked-in golden artifacts."""
    fixture_dir = _copy_fixture(Path("fixtures/golden/p0b-qeg-minimal/input"), tmp_path / "input")
    out_dir = tmp_path / "output"
    expected_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")

    export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)

    for artifact_name in [
        "qeg-bundle.json",
        "evidence-map.json",
        "diff-risk-test.json",
        "qeg-export-report.json",
    ]:
        actual = json.loads((out_dir / artifact_name).read_text(encoding="utf-8"))
        expected = json.loads((expected_dir / artifact_name).read_text(encoding="utf-8"))
        assert actual == expected, artifact_name


def test_p0b_qeg_bundle_schema_rejects_missing_required_metadata(tmp_path: Path) -> None:
    """QEG compatibility schema catches malformed bundles before downstream import."""
    fixture_dir = _copy_fixture(Path("fixtures/golden/p0b-qeg-minimal/input"), tmp_path / "input")
    out_dir = tmp_path / "output"
    export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)
    bundle = json.loads((out_dir / "qeg-bundle.json").read_text(encoding="utf-8"))
    del bundle["metadata"]["runId"]

    compatibility = _validate_qeg_bundle_schema(bundle)

    assert compatibility["valid"] is False
    assert "$.metadata.runId is required" in compatibility["errors"]


def test_p0b_missing_execution_generates_manual_bridge(tmp_path: Path) -> None:
    """P0b keeps high-risk missing execution visible as risk debt and manual-bb bridge."""
    fixture_dir = _copy_fixture(Path("fixtures/golden/p0b-qeg-minimal/input"), tmp_path / "input")
    out_dir = tmp_path / "output"
    _remove_test_result(fixture_dir / "p0a" / "HATE-test-results.ndjson", "junit:tests/test_db.py::test_connection")

    result = export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)

    assert result["export_status"] == "partial"
    assert result["missing_executions"] == 1
    assert "risk-debt-register.json" in result["generated"]
    assert "manual-bb-bridge-requests.jsonl" in result["generated"]

    ev_map = json.loads((out_dir / "evidence-map.json").read_text())
    assert len(ev_map["gaps"]["missing_execution"]) == 1
    assert ev_map["gaps"]["missing_execution"][0]["risk_id"] == "risk-db-high"

    report = json.loads((out_dir / "qeg-export-report.json").read_text())
    assert report["export_status"] == "partial"
    assert len(report["missing_execution"]) == 1
    assert report["completeness"]["score"] == 0.9
    assert report["completeness"]["partial"] is True
    assert len(report["completeness"]["unsupportedClaims"]) == 1

    risk_debt = json.loads((out_dir / "risk-debt-register.json").read_text())
    assert risk_debt["debts"][0]["risk_id"] == "risk-db-high"
    bridge_lines = (out_dir / "manual-bb-bridge-requests.jsonl").read_text().splitlines()
    assert len(bridge_lines) == 1
    bridge = json.loads(bridge_lines[0])
    assert bridge["record_type"] == "manual_bb_bridge_request"
    assert bridge["contract_type"] == "manual_supplement_request"
    assert bridge["request_type"] == "missing_execution_review"
    assert bridge["gap_type"] == "no_execution"
    assert bridge["recommended_manual_layer"] == "manual-scripted"
    assert bridge["source_run_id"] == "1001"
    assert bridge["risk_id"] == "risk-db-high"
    assert bridge["risk_title"] == "Database connection module changed"
    assert bridge["changed_entity_id"] == "changed-src-db"
    assert bridge["changed_entities"][0]["path"] == "src/db.py"
    assert bridge["required_oracle_refs"] == ["src/db.py#L5-L10", "tests/test_db.py::test_connection"]
    assert bridge["evidence_refs"] == ["qeg-export-report.json", "risk-debt-register.json"]
    assert bridge["source_refs"][0]["kind"] == "auto_test"
    assert bridge["manual_case_seed"]["primary_view"] == "black"
    assert bridge["manual_case_seed"]["oracle"]["type"] == "specified"
    assert bridge["manual_case_seed"]["oracle"]["refs"] == bridge["required_oracle_refs"]
    assert bridge["handoff_policy"]["target_suite_id"] == "manual-bb-harness"
    assert bridge["handoff_policy"]["does_not_override_qeg_verdict"] is True
    expected_shape = json.loads(Path("fixtures/manual-bb/missing-high-risk/expected/manual-supplement-request.shape.json").read_text(encoding="utf-8"))
    assert bridge["request_id"].startswith(expected_shape["request_id_prefix"])
    assert bridge["contract_type"] == expected_shape["contract_type"]
    assert bridge["gap_type"] == expected_shape["gap_type"]
    assert bridge["manual_case_seed"]["oracle"]["type"] == expected_shape["manual_case_seed"]["oracle_type"]


def test_p0b_risk_debt_lifecycle_tracks_ack_mitigated_and_stale(tmp_path: Path) -> None:
    """Risk debt register preserves lifecycle state instead of only emitting open debts."""
    fixture_dir = _copy_fixture(Path("fixtures/golden/p0b-qeg-minimal/input"), tmp_path / "input")
    out_dir = tmp_path / "output"
    _remove_test_result(fixture_dir / "p0a" / "HATE-test-results.ndjson", "junit:tests/test_db.py::test_connection")
    shutil.copy2(
        Path("fixtures/adapters/risk-debt/lifecycle/risk-debt-lifecycle.json"),
        fixture_dir / "risk-debt-lifecycle.json",
    )

    result = export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)

    assert result["export_status"] == "partial"
    register = json.loads((out_dir / "risk-debt-register.json").read_text(encoding="utf-8"))
    assert register["summary"] == {
        "total_count": 3,
        "open_count": 0,
        "acknowledged_count": 1,
        "mitigated_count": 1,
        "stale_count": 1,
        "by_status": {"acknowledged": 1, "mitigated": 1, "stale": 1},
    }
    current = next(item for item in register["items"] if item["risk_id"] == "risk-db-high")
    assert current["status"] == "acknowledged"
    assert current["owner"] == "team-database"
    assert current["age_days"] == 8
    assert current["manual_bridge_refs"] == ["manual-bb-bridge-requests.jsonl"]
    assert {item["status"] for item in register["debts"]} == {"acknowledged", "mitigated", "stale"}


def test_p0b_export_hard_dq_raises(tmp_path: Path) -> None:
    """P0b export raises ExportError when precheck decision is hard_dq."""
    fixture_dir = _copy_fixture(Path("fixtures/golden/p0b-qeg-minimal/input"), tmp_path / "input")
    out_dir = tmp_path / "output"

    # Modify precheck-decision.json to hard_dq
    p0a_dir = fixture_dir / "p0a"
    precheck_path = p0a_dir / "precheck-decision.json"
    original_content = precheck_path.read_text()
    original = json.loads(original_content)

    # Write hard_dq version (deep copy via json roundtrip)
    hard_dq_json = json.dumps(original, indent=2)
    hard_dq_data = json.loads(hard_dq_json)
    hard_dq_data["payload"]["decision"] = "hard_dq"
    hard_dq_data["payload"]["qeg_export_allowed"] = False
    precheck_path.write_text(json.dumps(hard_dq_data, indent=2))

    try:
        export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)
        assert False, "Expected ExportError"
    except ExportError as exc:
        assert exc.exit_code == 2
        assert "hard_dq" in str(exc).lower()
    finally:
        # Restore original content exactly
        precheck_path.write_text(original_content)


def test_p0b_export_missing_artifacts_raises(tmp_path: Path) -> None:
    """P0b export raises ExportError when required P0a artifacts are missing."""
    fixture_dir = _copy_fixture(Path("fixtures/golden/p0b-qeg-minimal/input"), tmp_path / "input")
    out_dir = tmp_path / "output"

    # Temporarily remove required artifact
    p0a_dir = fixture_dir / "p0a"
    run_path = p0a_dir / "HATE-run.json"
    run_path.unlink()

    try:
        export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)
        assert False, "Expected ExportError"
    except ExportError as exc:
        assert exc.exit_code == 2
        assert "Missing" in str(exc)
        assert "HATE-run.json" in str(exc)


def test_p0b_missing_source_ref_is_visible_gap(tmp_path: Path) -> None:
    """P0b reports missing risk sourceRefs as unsupported claims."""
    fixture_dir = _copy_fixture(Path("fixtures/golden/p0b-qeg-minimal/input"), tmp_path / "input")
    out_dir = tmp_path / "output"
    diff_path = fixture_dir / "diff-risk-test.json"
    diff_data = json.loads(diff_path.read_text())
    diff_data["risks"][0]["source_refs"] = []
    diff_path.write_text(json.dumps(diff_data, indent=2))

    result = export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)

    assert result["export_status"] == "partial"
    report = json.loads((out_dir / "qeg-export-report.json").read_text())
    reasons = {claim["reason"] for claim in report["unsupportedClaims"]}
    assert "risk source_refs missing" in reasons
    assert report["completeness"]["score"] == 0.9


def test_p0b_unsafe_required_artifact_is_quarantined(tmp_path: Path) -> None:
    """P0b excludes unsafe artifacts and keeps the gap visible."""
    fixture_dir = _copy_fixture(Path("fixtures/golden/p0b-qeg-minimal/input"), tmp_path / "input")
    out_dir = tmp_path / "output"

    manifest_path = fixture_dir / "p0a" / "artifact-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"] = [
        {
            "artifact_id": "artifact-secret-trace",
            "kind": "trace",
            "path": "artifacts/secret-trace.zip",
            "sha256": "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "size_bytes": 10,
            "classification": "restricted",
            "redaction_status": "not_required",
            "safe_for_summary": False,
            "public_exposure": "none",
            "security_checks": {"secret_scan": "fail"},
        }
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2))

    test_results_path = fixture_dir / "p0a" / "HATE-test-results.ndjson"
    records = [json.loads(line) for line in test_results_path.read_text().splitlines() if line]
    records[0]["payload"]["artifacts"] = ["artifact-secret-trace"]
    test_results_path.write_text("\n".join(json.dumps(record) for record in records) + "\n")

    diff_path = fixture_dir / "diff-risk-test.json"
    diff_data = json.loads(diff_path.read_text())
    diff_data["test_obligations"][0]["required_evidence_kinds"].append("artifact")
    diff_data["test_obligations"][0]["required_artifact_refs"] = ["artifact-secret-trace"]
    diff_path.write_text(json.dumps(diff_data, indent=2))

    result = export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)

    assert result["export_status"] == "partial"
    report = json.loads((out_dir / "qeg-export-report.json").read_text())
    ev_map = json.loads((out_dir / "evidence-map.json").read_text())
    assert report["completeness"]["score"] == 0.9
    assert report["excludedArtifacts"][0]["artifact_id"] == "artifact-secret-trace"
    assert ev_map["gaps"]["unsafe_artifacts"][0]["artifact_id"] == "artifact-secret-trace"


def test_p0b_required_archive_artifact_from_p0a_manifest_is_excluded(tmp_path: Path) -> None:
    """P0b carries P0a artifact safety into excludedArtifacts / unsafe_artifacts."""
    p0a_input = Path("fixtures/adapters/artifacts/archive")
    fixture_dir = tmp_path / "fixture"
    p0a_dir = fixture_dir / "p0a"
    p0a_dir.mkdir(parents=True)
    generate_p0a(p0a_input, p0a_dir, source_version="test")

    diff_data = {
        "schema_version": "HATE/v1",
        "changed_entities": [],
        "risks": [
            {
                "risk_id": "risk-artifact-high",
                "severity": "high",
                "title": "Archive trace required for review",
                "required_test_layers": ["artifact"],
                "source_refs": ["src/archive.py#L1-L2"],
            }
        ],
        "test_obligations": [
            {
                "obligation_id": "obligation-artifact",
                "risk_id": "risk-artifact-high",
                "expected_test_refs": [],
                "required_evidence_kinds": ["artifact"],
                "required_artifact_refs": ["artifact-trace"],
            }
        ],
    }
    (fixture_dir / "diff-risk-test.json").write_text(json.dumps(diff_data, indent=2), encoding="utf-8")

    result = export_qeg(fixture_dir=fixture_dir, out_dir=tmp_path / "qeg-output")

    assert result["export_status"] == "partial"
    report = json.loads((tmp_path / "qeg-output" / "qeg-export-report.json").read_text(encoding="utf-8"))
    ev_map = json.loads((tmp_path / "qeg-output" / "evidence-map.json").read_text(encoding="utf-8"))
    bundle = json.loads((tmp_path / "qeg-output" / "qeg-bundle.json").read_text(encoding="utf-8"))
    assert any(
        item["artifact_id"] == "artifact-trace" and item["reason"] == "required artifact is unsafe for export"
        for item in report["excludedArtifacts"]
    )
    assert any(item["artifact_id"] == "artifact-trace" for item in ev_map["gaps"]["unsafe_artifacts"])
    assert not any(node["id"] == "artifact:artifact-trace" for node in bundle["nodes"])


def test_p0b_exports_sarif_findings_into_qeg_bundle(tmp_path: Path) -> None:
    """P0b maps P0a SARIF into QEG finding nodes and changed-code trace edges."""
    fixture_dir = _copy_fixture(Path("fixtures/golden/p0b-qeg-minimal/input"), tmp_path / "input")
    out_dir = tmp_path / "output"
    sarif_path = fixture_dir / "p0a" / "HATE-static.sarif"
    sarif_path.write_text(
        Path("fixtures/adapters/sarif/full-mapping/HATE-static.sarif").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)

    assert result["export_status"] == "success"
    bundle = json.loads((out_dir / "qeg-bundle.json").read_text())
    finding_nodes = [node for node in bundle["nodes"] if node["kind"] == "finding"]
    assert len(finding_nodes) == 2
    mapped_finding = next(node for node in finding_nodes if node["data"]["start_line"] == 5)
    outside_finding = next(node for node in finding_nodes if node["data"]["start_line"] == 50)
    assert mapped_finding["data"]["path"] == "src/db.py"
    assert mapped_finding["data"]["rule_id"] == "WARN001"
    assert mapped_finding["data"]["rule_name"] == "Warning Rule"
    assert mapped_finding["data"]["rule_short_description"] == "short warning"
    assert mapped_finding["data"]["rule_full_description"] == "full warning description"
    assert mapped_finding["data"]["help_uri"] == "https://example.invalid/rules/WARN001"
    assert mapped_finding["data"]["location"] == {
        "path": "src/db.py",
        "start_line": 5,
        "end_line": 6,
        "start_column": 3,
        "end_column": 12,
        "uri_base_id": "",
    }
    assert mapped_finding["data"]["fingerprints"]["primaryLocationLineHash"] == "abc123"
    assert any(
        edge["kind"] == "touches"
        and edge["to"] == mapped_finding["id"]
        and edge["from"].startswith("changed_code:src/db.py")
        for edge in bundle["edges"]
    )
    assert not any(edge["kind"] == "touches" and edge["to"] == outside_finding["id"] for edge in bundle["edges"])
    ev_map = json.loads((out_dir / "evidence-map.json").read_text())
    assert len(ev_map["findings"]) == 2
    assert any(link["to"] == mapped_finding["id"] for link in ev_map["links"]["touches"])
    input_artifacts = bundle["metadata"]["inputArtifacts"]
    assert any(artifact["kind"] == "HATE-static" for artifact in input_artifacts)


def test_p0b_links_playwright_artifacts_to_test_and_execution(tmp_path: Path) -> None:
    """P0b maps Playwright trace/screenshot/video/log artifacts onto test and execution evidence."""
    fixture_dir = _copy_fixture(Path("fixtures/golden/p0b-qeg-minimal/input"), tmp_path / "input")
    out_dir = tmp_path / "output"
    playwright_fixture = Path("fixtures/adapters/playwright/evidence")

    shutil.copy2(playwright_fixture / "artifact-manifest.json", fixture_dir / "p0a" / "artifact-manifest.json")
    test_results_path = fixture_dir / "p0a" / "HATE-test-results.ndjson"
    test_results_path.write_text(
        test_results_path.read_text(encoding="utf-8")
        + (playwright_fixture / "HATE-test-results.ndjson").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)

    assert result["export_status"] == "success"
    bundle = json.loads((out_dir / "qeg-bundle.json").read_text(encoding="utf-8"))
    ev_map = json.loads((out_dir / "evidence-map.json").read_text(encoding="utf-8"))
    artifact_nodes = [
        node for node in bundle["nodes"]
        if node["kind"] == "evidence_artifact" and node["data"].get("adapter") == "playwright"
    ]
    roles = {node["data"]["artifact_role"] for node in artifact_nodes}
    assert roles == {"trace", "screenshot", "video", "log"}

    playwright_test = next(
        node for node in bundle["nodes"]
        if node["kind"] == "test" and node["data"]["framework"] == "playwright"
    )
    playwright_execution = next(
        node for node in bundle["nodes"]
        if node["kind"] == "execution_evidence" and node["label"].endswith("login works")
    )
    for artifact_node in artifact_nodes:
        role = artifact_node["data"]["artifact_role"]
        assert any(
            edge["kind"] == "evidenced_by"
            and edge["from"] == playwright_test["id"]
            and edge["to"] == artifact_node["id"]
            and edge["traceability"]["adapter"] == "playwright"
            and edge["traceability"]["artifact_role"] == role
            for edge in bundle["edges"]
        )
        assert any(
            edge["kind"] == "evidenced_by"
            and edge["from"] == playwright_execution["id"]
            and edge["to"] == artifact_node["id"]
            and edge["traceability"]["adapter"] == "playwright"
            and edge["traceability"]["artifact_role"] == role
            for edge in bundle["edges"]
        )

    evidence_roles = {
        item["artifact_role"]
        for item in ev_map["evidence"]
        if item.get("adapter") == "playwright"
    }
    link_roles = {
        item["artifact_role"]
        for item in ev_map["links"]["evidenced_by"]
        if item.get("adapter") == "playwright"
    }
    assert evidence_roles == {"trace", "screenshot", "video", "log"}
    assert {"trace", "screenshot", "video", "log"}.issubset(link_roles)


def test_p0b_maps_pact_contract_failure_to_visible_gap(tmp_path: Path) -> None:
    """P0b maps Pact contract evidence and keeps failed required contracts visible."""
    fixture_dir = _copy_fixture(Path("fixtures/golden/p0b-qeg-minimal/input"), tmp_path / "input")
    out_dir = tmp_path / "output"
    shutil.copy2(
        Path("fixtures/adapters/pact/contract-evidence/HATE-contract.ndjson"),
        fixture_dir / "p0a" / "HATE-contract.ndjson",
    )
    diff_path = fixture_dir / "diff-risk-test.json"
    diff_data = json.loads(diff_path.read_text(encoding="utf-8"))
    diff_data["test_obligations"][0]["required_evidence_kinds"].append("contract")
    diff_data["test_obligations"][0]["required_contract_refs"] = [
        "pact-auth-provider-login",
        "pact-billing-provider-create-invoice",
    ]
    diff_path.write_text(json.dumps(diff_data, indent=2), encoding="utf-8")

    result = export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)

    assert result["export_status"] == "partial"
    bundle = json.loads((out_dir / "qeg-bundle.json").read_text(encoding="utf-8"))
    ev_map = json.loads((out_dir / "evidence-map.json").read_text(encoding="utf-8"))
    report = json.loads((out_dir / "qeg-export-report.json").read_text(encoding="utf-8"))

    contract_nodes = [node for node in bundle["nodes"] if node["kind"] == "contract_evidence"]
    assert {node["data"]["contract_id"] for node in contract_nodes} == {
        "pact-auth-provider-login",
        "pact-billing-provider-create-invoice",
    }
    assert any(
        edge["kind"] == "supports"
        and edge["from"] == "contract:pact-auth-provider-login"
        and edge["to"] == "risk:risk-auth-high"
        and edge["traceability"]["adapter"] == "pact"
        for edge in bundle["edges"]
    )
    assert any(
        edge["kind"] == "contradicts"
        and edge["from"] == "contract:pact-billing-provider-create-invoice"
        and edge["to"] == "risk:risk-auth-high"
        and edge["traceability"]["adapter"] == "pact"
        for edge in bundle["edges"]
    )
    assert ev_map["contracts"][1]["status"] == "failed"
    assert any(link["from"] == "contract:pact-billing-provider-create-invoice" for link in ev_map["links"]["contradicts"])
    assert report["completeness"]["partial"] is True
    assert report["completeness"]["score"] == 0.9
    assert report["contract_failures"] == [
        {
            "risk_id": "risk-auth-high",
            "contract_id": "pact-billing-provider-create-invoice",
            "reason": "required contract failed",
            "status": "failed",
        }
    ]
    input_artifacts = bundle["metadata"]["inputArtifacts"]
    assert any(artifact["kind"] == "HATE-contract" for artifact in input_artifacts)


def test_p0b_maps_stryker_mutation_survivor_to_oracle_gap(tmp_path: Path) -> None:
    """P0b maps Stryker mutation evidence and keeps survived/no_coverage mutants visible."""
    fixture_dir = _copy_fixture(Path("fixtures/golden/p0b-qeg-minimal/input"), tmp_path / "input")
    out_dir = tmp_path / "output"
    shutil.copy2(
        Path("fixtures/adapters/stryker/mutation-evidence/HATE-mutation.ndjson"),
        fixture_dir / "p0a" / "HATE-mutation.ndjson",
    )
    diff_path = fixture_dir / "diff-risk-test.json"
    diff_data = json.loads(diff_path.read_text(encoding="utf-8"))
    diff_data["test_obligations"][0]["required_evidence_kinds"].append("mutation")
    diff_data["test_obligations"][0]["required_mutation_refs"] = ["mut-auth-001", "mut-auth-002"]
    diff_data["test_obligations"][1]["required_evidence_kinds"].append("mutation")
    diff_data["test_obligations"][1]["required_mutation_refs"] = ["mut-db-001"]
    diff_path.write_text(json.dumps(diff_data, indent=2), encoding="utf-8")

    result = export_qeg(fixture_dir=fixture_dir, out_dir=out_dir)

    assert result["export_status"] == "partial"
    bundle = json.loads((out_dir / "qeg-bundle.json").read_text(encoding="utf-8"))
    ev_map = json.loads((out_dir / "evidence-map.json").read_text(encoding="utf-8"))
    report = json.loads((out_dir / "qeg-export-report.json").read_text(encoding="utf-8"))

    mutation_nodes = [node for node in bundle["nodes"] if node["kind"] == "mutation_evidence"]
    assert {node["data"]["mutation_id"] for node in mutation_nodes} == {"mut-auth-001", "mut-auth-002", "mut-db-001"}
    assert any(
        edge["kind"] == "supports"
        and edge["from"] == "mutation:mut-auth-001"
        and edge["to"] == "risk:risk-auth-high"
        and edge["traceability"]["adapter"] == "stryker"
        for edge in bundle["edges"]
    )
    assert any(
        edge["kind"] == "contradicts"
        and edge["from"] == "mutation:mut-auth-002"
        and edge["to"] == "risk:risk-auth-high"
        and edge["traceability"]["adapter"] == "stryker"
        for edge in bundle["edges"]
    )
    assert any(
        edge["kind"] == "contradicts"
        and edge["from"] == "mutation:mut-db-001"
        and edge["to"] == "risk:risk-db-high"
        for edge in bundle["edges"]
    )
    assert {mutation["status"] for mutation in ev_map["mutations"]} == {"killed", "survived", "no_coverage"}
    assert report["completeness"]["partial"] is True
    assert report["completeness"]["score"] == 0.9
    assert report["mutation_gaps"] == [
        {
            "risk_id": "risk-auth-high",
            "mutation_id": "mut-auth-002",
            "reason": "required mutation survived",
            "status": "survived",
        },
        {
            "risk_id": "risk-db-high",
            "mutation_id": "mut-db-001",
            "reason": "required mutation survived",
            "status": "no_coverage",
        },
    ]
    assert any(link["from"] == "mutation:mut-auth-002" for link in ev_map["links"]["contradicts"])
    input_artifacts = bundle["metadata"]["inputArtifacts"]
    assert any(artifact["kind"] == "HATE-mutation" for artifact in input_artifacts)


def test_p0b_cli_export_qeg(tmp_path: Path) -> None:
    """CLI `hate export qeg` generates expected artifacts."""
    import subprocess

    fixture_dir = _copy_fixture(Path("fixtures/golden/p0b-qeg-minimal/input"), tmp_path / "input")
    out_dir = tmp_path / "cli-output"

    result = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "export", "qeg",
            "--fixture", str(fixture_dir),
            "--out", str(out_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["export_status"] == "success"
    assert output["missing_executions"] == 0
    assert len(output["generated"]) >= 4


def _copy_fixture(src: Path, dst: Path) -> Path:
    """Copy an input fixture into a disposable path for mutation tests."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def _remove_test_result(path: Path, canonical_test_id: str) -> None:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    kept = [
        record for record in records
        if record.get("payload", {}).get("canonical_test_id") != canonical_test_id
    ]
    path.write_text("\n".join(json.dumps(record) for record in kept) + "\n", encoding="utf-8")
