"""Tests for P1a trust hardening."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from hate.p0b import export_qeg
from hate.p1a import compare_trust, doctor_trust, evaluate_trust, explain_trust, recommend_trust, replay_trust


def test_p1a_evaluate_trust_from_p0b_bundle(tmp_path: Path) -> None:
    """P1a generates AETE score, resolver map, doctor report, and summary."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    out_dir = tmp_path / "trust-output"

    result = evaluate_trust(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        out_dir=out_dir,
    )

    assert result["trust_status"] == "success"
    assert result["exit_code"] == 0
    assert result["publish_gate_override"] is False
    assert result["weighted_score"] > 0
    assert result["score_confidence"] == "high"
    assert "aete-score.json" in result["generated"]
    assert "aete-signal-report.json" in result["generated"]
    assert "profile-report.json" in result["generated"]
    assert "doctor-report.json" in result["generated"]
    assert "adapter-registry.json" in result["generated"]
    assert "adapter-capability-manifest.json" in result["generated"]
    assert "adapter-conformance-report.json" in result["generated"]
    assert "canonical-identity-index.json" in result["generated"]
    assert "retry-aggregation.json" in result["generated"]

    aete = json.loads((out_dir / "aete-score.json").read_text())
    assert aete["schema_version"] == "HATE/v1"
    assert aete["record_type"] == "aete_score"
    assert aete["calibration_status"] == "uncalibrated"
    assert aete["release_gate_override"] is False
    assert aete["profile_version"].startswith("hate-profile-inheritance-")
    assert len(aete["dimension_signals"]) == 8
    assert set(aete["dimensions"]) == {
        "provenance_integrity",
        "determinism_flakiness",
        "traceability_lineage",
        "oracle_strength",
        "change_relevance",
        "coverage_adequacy",
        "cross_signal_corroboration",
        "freshness_profile_conformance",
    }
    assert len(aete["reason_refs"]) == 8
    assert {reason["dimension"] for reason in aete["reason_refs"]} == set(aete["dimensions"])
    assert {signal["dimension"] for signal in aete["dimension_signals"]} == set(aete["dimensions"])
    assert all(reason["reason_ref"].startswith("signal:") for reason in aete["reason_refs"])
    signal_report = json.loads((out_dir / "aete-signal-report.json").read_text())
    assert signal_report["record_type"] == "aete_signal_report"
    assert signal_report["deterministic"] is True
    assert signal_report["dimensions"] == aete["dimensions"]
    assert signal_report["signals"] == aete["dimension_signals"]
    coverage_signal = next(signal for signal in signal_report["signals"] if signal["dimension"] == "coverage_adequacy")
    assert "has_coverage" in coverage_signal["observed"]

    profile_report = json.loads((out_dir / "profile-report.json").read_text())
    assert profile_report["record_type"] == "profile_report"
    assert profile_report["profile"] == "default"
    assert profile_report["inherits"] == ["default"]
    assert profile_report["rules"]["unsafe_artifact_policy"] == "quarantine"
    assert profile_report["rule_sources"]["unsafe_artifact_policy"] == "default"
    assert profile_report["drift_checks"][0]["check_id"] == "profile-chain-known"
    assert all(check["status"] == "pass" for check in profile_report["drift_checks"])
    assert profile_report["qeg_gate_policy"] is False
    assert profile_report["publish_gate_override"] is False

    doctor = json.loads((out_dir / "doctor-report.json").read_text())
    assert doctor["record_type"] == "doctor_report"
    assert doctor["summary"]["finding_count"] == 0
    assert doctor["findings"] == []

    conformance = json.loads((out_dir / "adapter-conformance-report.json").read_text())
    assert conformance["summary"]["overall_status"] == "pass"
    assert "qeg_fixture" in conformance["summary"]["covered_categories"]
    assert "adapter_registry" in conformance["summary"]["covered_categories"]
    assert conformance["summary"]["adapter_count"] >= 16
    assert conformance["summary"]["adapter_result_count"] == conformance["summary"]["adapter_count"]
    assert conformance["summary"]["fixture_result_count"] >= conformance["summary"]["adapter_count"] * 3
    assert "test-result-pytest-json" in conformance["adapter_registry"]["adapter_ids"]
    assert "coverage-coveragepy-json" in conformance["adapter_registry"]["adapter_ids"]
    assert "mutation-stryker" in conformance["adapter_registry"]["adapter_ids"]
    pytest_result = next(result for result in conformance["adapter_results"] if result["adapter_id"] == "test-result-pytest-json")
    assert pytest_result["conformance_status"] == "pass"
    assert {item["fixture_id"] for item in pytest_result["fixture_results"]} == {
        "manifest-required-fields",
        "capability-fields",
        "profile-support",
    }

    registry = json.loads((out_dir / "adapter-registry.json").read_text())
    assert registry["record_type"] == "adapter_registry"
    assert registry["summary"]["all_have_required_manifest_fields"] is True
    adapter_ids = {adapter["adapter_id"] for adapter in registry["adapters"]}
    assert {
        "context-generic-ci",
        "test-result-junit",
        "test-result-pytest-json",
        "test-result-vitest-json",
        "test-result-jest-json",
        "coverage-lcov",
        "coverage-cobertura",
        "coverage-jacoco",
        "coverage-coveragepy-json",
        "static-sarif",
        "artifact-manifest",
        "browser-playwright-artifacts",
        "contract-pact",
        "mutation-stryker",
        "export-qeg-bundle",
    }.issubset(adapter_ids)

    resolver_map = json.loads((out_dir / "artifact-resolver-map.json").read_text())
    assert resolver_map["entries"]
    assert resolver_map["record_type"] == "artifact_resolution"
    assert resolver_map["summary"]["source_ref_count"] > 0
    assert all("C:\\Users" not in json.dumps(entry) for entry in resolver_map["entries"])

    identity = json.loads((out_dir / "canonical-identity-index.json").read_text())
    assert identity["record_type"] == "canonical_identity_index"
    assert identity["summary"]["identity_count"] >= 2
    assert identity["summary"]["has_duplicates"] is False
    assert identity["identities"][0]["canonical_test_id"] == "junit:tests/test_auth.py::test_login"
    assert identity["identities"][0]["normalized_canonical_test_id"] == "junit:tests/test_auth.py::::test_login"

    retry = json.loads((out_dir / "retry-aggregation.json").read_text())
    assert retry["aggregates"][0]["aggregate_status"] == "stable_passed"

    summary = (out_dir / "trust-summary.md").read_text()
    assert "publish_gate_override=false" in summary
    assert "release_gate_override=false" in summary


def test_p1a_cli_trust_evaluate(tmp_path: Path) -> None:
    """CLI `hate trust evaluate` generates expected trust artifacts."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    out_dir = tmp_path / "trust-cli-output"

    result = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "trust", "evaluate",
            "--bundle", str(fixture_dir / "qeg-bundle.json"),
            "--report", str(fixture_dir / "qeg-export-report.json"),
            "--out", str(out_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["trust_status"] == "success"
    assert output["doctor_findings"] == 0


def test_p1a_profile_inheritance_release_profile(tmp_path: Path) -> None:
    """P1a emits deterministic machine-readable profile inheritance and drift checks."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    out_dir = tmp_path / "trust-release-profile"

    result = evaluate_trust(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        out_dir=out_dir,
        profile="release",
    )

    assert result["trust_status"] == "success"
    profile_report = json.loads((out_dir / "profile-report.json").read_text(encoding="utf-8"))
    aete = json.loads((out_dir / "aete-score.json").read_text(encoding="utf-8"))
    assert profile_report["profile"] == "release"
    assert profile_report["inherits"] == ["default", "strict", "release"]
    assert profile_report["rules"] == {
        "require_tests": True,
        "require_coverage": True,
        "unsafe_artifact_policy": "hard_dq",
    }
    assert profile_report["rule_sources"] == {
        "require_tests": "release",
        "require_coverage": "release",
        "unsafe_artifact_policy": "release",
    }
    release_diff = profile_report["rule_diffs"][-1]
    assert release_diff["profile"] == "release"
    assert release_diff["overridden"]["unsafe_artifact_policy"]["from"] == "soft_gap"
    assert release_diff["overridden"]["unsafe_artifact_policy"]["to"] == "hard_dq"
    assert any(check["check_id"] == "release-extends-strict" and check["status"] == "pass" for check in profile_report["drift_checks"])
    assert profile_report["profile_hash"]
    assert aete["profile"] == "release"
    assert aete["profile_version"] == profile_report["profile_version"]


def test_p1a_aete_scoring_uses_negative_gap_signals(tmp_path: Path) -> None:
    """Missing execution gaps lower freshness/determinism through explicit signals."""
    fixture_dir = _missing_execution_p0b_output(tmp_path)
    out_dir = tmp_path / "trust-missing-execution-signals"

    result = evaluate_trust(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        out_dir=out_dir,
    )

    assert result["trust_status"] == "partial"
    signal_report = json.loads((out_dir / "aete-signal-report.json").read_text(encoding="utf-8"))
    signals = {signal["dimension"]: signal for signal in signal_report["signals"]}
    assert signals["determinism_flakiness"]["score"] == 1
    assert signals["determinism_flakiness"]["observed"]["missing_execution"] is True
    assert signals["freshness_profile_conformance"]["score"] == 1
    assert signals["freshness_profile_conformance"]["observed"]["has_unsupported_claims"] is True
    aete = json.loads((out_dir / "aete-score.json").read_text(encoding="utf-8"))
    assert aete["dimensions"]["determinism_flakiness"] == 1
    assert any(reason["reason_ref"] == "signal:freshness_profile_conformance:1" for reason in aete["reason_refs"])


def test_p1a_canonical_identity_hardens_components_parameters_and_matrix(tmp_path: Path) -> None:
    """Canonical identity separates framework/file/class/name/parameters/matrix deterministically."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    bundle = json.loads((fixture_dir / "qeg-bundle.json").read_text(encoding="utf-8"))
    report_path = fixture_dir / "qeg-export-report.json"
    test_node = next(node for node in bundle["nodes"] if node["kind"] == "test")
    test_node["data"].update({
        "canonical_test_id": "pytest:C:\\repo\\tests\\test_api.py::TestApi::test_lookup",
        "framework": "pytest",
        "file": "C:\\repo\\tests\\test_api.py",
        "classname": "TestApi",
        "name": "test_lookup",
        "parameters": {"user": "admin", "locale": "ja-JP"},
        "matrix": {"python": "3.12", "os": "windows-latest"},
    })
    mutated_bundle = tmp_path / "qeg-bundle.json"
    mutated_bundle.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    out_dir = tmp_path / "trust-identity"

    evaluate_trust(bundle_path=mutated_bundle, report_path=report_path, out_dir=out_dir)

    identity = json.loads((out_dir / "canonical-identity-index.json").read_text(encoding="utf-8"))
    item = next(entry for entry in identity["identities"] if entry["identity_components"]["framework"] == "pytest")
    components = item["identity_components"]
    assert item["identity_id"].startswith("identity:")
    assert components["file"] == "C:/repo/tests/test_api.py"
    assert components["classname"] == "TestApi"
    assert components["name"] == "test_lookup"
    assert components["parameters"] == {"locale": "ja-JP", "user": "admin"}
    assert components["matrix"] == {"os": "windows-latest", "python": "3.12"}
    assert item["normalized_canonical_test_id"].startswith("pytest:C:/repo/tests/test_api.py::TestApi::test_lookup::")
    assert "windows-latest" not in item["normalized_canonical_test_id"]
    assert item["aliases"][0]["reason"] == "path_normalization"


def test_p1a_retry_matrix_and_shard_aggregation_is_deterministic(tmp_path: Path) -> None:
    """Retry aggregation uses normalized identity, matrix group, retry order, and shard completeness."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    bundle = json.loads((fixture_dir / "qeg-bundle.json").read_text(encoding="utf-8"))
    report_path = fixture_dir / "qeg-export-report.json"
    test_nodes = [node for node in bundle["nodes"] if node["kind"] == "test"]
    execution_nodes = [node for node in bundle["nodes"] if node["kind"] == "execution_evidence"]

    first_test = test_nodes[0]
    first_exec = next(
        node for node in execution_nodes
        if any(edge["kind"] == "evidenced_by" and edge["from"] == first_test["id"] and edge["to"] == node["id"] for edge in bundle["edges"])
    )
    first_test["data"]["matrix"] = {"os": "windows-latest", "python": "3.12"}
    first_exec["data"].update({"status": "failed", "retry_index": 0, "matrix": {"os": "windows-latest", "python": "3.12"}})
    retry_exec = json.loads(json.dumps(first_exec))
    retry_exec["id"] = first_exec["id"] + ":retry1"
    retry_exec["data"]["status"] = "passed"
    retry_exec["data"]["retry_index"] = 1
    bundle["nodes"].append(retry_exec)
    bundle["edges"].append({
        "kind": "evidenced_by",
        "from": first_test["id"],
        "to": retry_exec["id"],
        "traceability": {"sourceRefs": ["qeg-bundle.json"], "confidence": "high", "assumptions": []},
    })

    second_test = test_nodes[1]
    second_exec = next(
        node for node in execution_nodes
        if any(edge["kind"] == "evidenced_by" and edge["from"] == second_test["id"] and edge["to"] == node["id"] for edge in bundle["edges"])
    )
    second_exec["data"].update({"status": "passed", "retry_index": 0, "shard_index": 0, "shard_total": 2})

    mutated_bundle = tmp_path / "qeg-bundle.json"
    mutated_bundle.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    out_dir = tmp_path / "trust-retry-matrix"

    evaluate_trust(bundle_path=mutated_bundle, report_path=report_path, out_dir=out_dir)

    retry = json.loads((out_dir / "retry-aggregation.json").read_text(encoding="utf-8"))
    first_aggregate = next(item for item in retry["aggregates"] if item["test_node_id"] == first_test["id"])
    assert first_aggregate["aggregate_status"] == "flaky_passed"
    assert first_aggregate["raw_statuses"] == ["failed", "passed"]
    assert first_aggregate["matrix"] == {"os": "windows-latest", "python": "3.12"}
    assert first_aggregate["matrix_group"].startswith("matrix:")
    assert first_aggregate["retry_attempts"][0]["retry_index"] == 0
    assert first_aggregate["retry_attempts"][1]["retry_index"] == 1

    second_aggregate = next(item for item in retry["aggregates"] if item["test_node_id"] == second_test["id"])
    assert second_aggregate["aggregate_status"] == "inconclusive"
    assert second_aggregate["shards"] == {"observed": ["0"], "expected_count": 2, "missing": True}
    assert retry["summary"]["flaky_count"] >= 1
    assert retry["summary"]["missing_shard_count"] >= 1


def test_p1a_artifact_resolver_maps_artifact_paths_and_unsafe_refs(tmp_path: Path) -> None:
    """Artifact resolver includes artifact paths and flags URL/traversal as unsafe."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    bundle = json.loads((fixture_dir / "qeg-bundle.json").read_text(encoding="utf-8"))
    report_path = fixture_dir / "qeg-export-report.json"
    bundle["nodes"].extend([
        {
            "id": "artifact:trace-safe",
            "kind": "evidence_artifact",
            "label": "trace-safe",
            "data": {
                "kind": "trace",
                "adapter": "playwright",
                "artifact_role": "trace",
                "path": "artifacts/playwright/trace.zip",
                "sha256": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            },
            "sourceRefs": ["artifact-manifest.json"],
        },
        {
            "id": "artifact:external-log",
            "kind": "evidence_artifact",
            "label": "external-log",
            "data": {
                "kind": "log",
                "path": "https://example.invalid/log.txt",
                "sha256": "",
            },
            "sourceRefs": ["artifact-manifest.json"],
        },
        {
            "id": "artifact:traversal",
            "kind": "evidence_artifact",
            "label": "traversal",
            "data": {
                "kind": "report",
                "path": "../secret/report.txt",
                "sha256": "",
            },
            "sourceRefs": ["artifact-manifest.json"],
        },
    ])
    mutated_bundle = tmp_path / "qeg-bundle.json"
    mutated_bundle.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    out_dir = tmp_path / "trust-resolver"

    evaluate_trust(bundle_path=mutated_bundle, report_path=report_path, out_dir=out_dir)

    resolver = json.loads((out_dir / "artifact-resolver-map.json").read_text(encoding="utf-8"))
    artifact_entries = [entry for entry in resolver["entries"] if entry["entry_type"] == "artifact_path"]
    assert resolver["summary"]["artifact_path_count"] == 3
    safe = next(entry for entry in artifact_entries if entry["artifact_id"] == "trace-safe")
    assert safe["normalized"] == "artifacts/playwright/trace.zip"
    assert safe["artifact_role"] == "trace"
    assert safe["resolution_status"] == "resolved"
    unsafe = {entry["artifact_id"]: entry["resolution_status"] for entry in artifact_entries}
    assert unsafe["external-log"] == "unsafe"
    assert unsafe["traversal"] == "unsafe"
    doctor = json.loads((out_dir / "doctor-report.json").read_text(encoding="utf-8"))
    assert "path" in doctor["summary"]["blocking_categories"]
    path_finding = next(finding for finding in doctor["findings"] if finding["category"] == "path")
    assert path_finding["finding_code"] == "HATE-DOC-PATH-001"
    assert path_finding["blocking"] is True
    assert path_finding["remediation"]
    assert doctor["summary"]["by_category"]["path"] == 2
    assert doctor["summary"]["by_severity"]["high"] >= 2
    assert doctor["summary"]["taxonomy_version"].startswith("doctor-taxonomy-")


def test_p1a_replay_is_deterministic(tmp_path: Path) -> None:
    """Replay emits a stable recalculation hash for the same frozen bundle."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    out_dir = tmp_path / "replay-output"

    first = replay_trust(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        out_dir=out_dir,
    )
    second = replay_trust(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        out_dir=out_dir,
    )

    assert first["recalculation_hash"] == second["recalculation_hash"]
    replay_report = json.loads((out_dir / "replay-report.json").read_text())
    assert replay_report["deterministic"] is True
    assert set(replay_report["deterministic_inputs"]) == {
        "aete_score",
        "aete_signal_report",
        "profile_report",
        "artifact_resolver_map",
        "doctor_report",
        "adapter_conformance_report",
        "canonical_identity_index",
        "retry_aggregation",
    }
    assert replay_report["publish_gate_override"] is False
    assert replay_report["release_gate_override"] is False


def test_p1a_compare_identical_trust_dirs_is_stable(tmp_path: Path) -> None:
    """Compare reports zero delta for identical P1a trust artifacts."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    trust_dir = tmp_path / "compare-trust"
    out_dir = tmp_path / "compare-output"
    evaluate_trust(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        out_dir=trust_dir,
    )

    result = compare_trust(base_dir=trust_dir, head_dir=trust_dir, out_dir=out_dir)

    assert result["compare_status"] == "stable"
    assert result["trust_delta"] == 0
    compare_report = json.loads((out_dir / "compare-report.json").read_text())
    assert compare_report["regression"] is False
    assert compare_report["doctor_finding_delta"] == 0
    assert compare_report["resolver_unsafe_delta"] == 0
    assert compare_report["identity_duplicate_delta"] == 0
    assert compare_report["profile_hash_changed"] is False
    assert set(compare_report["signal_delta"]) == set(compare_report["dimension_delta"])


def test_p1a_cli_replay_and_compare(tmp_path: Path) -> None:
    """CLI replay and compare commands generate expected reports."""
    fixture_dir = _missing_execution_p0b_output(tmp_path)
    replay_dir = tmp_path / "cli-replay"
    compare_dir = tmp_path / "cli-compare"

    replay_result = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "replay",
            "--bundle", str(fixture_dir / "qeg-bundle.json"),
            "--report", str(fixture_dir / "qeg-export-report.json"),
            "--out", str(replay_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert replay_result.returncode == 0
    replay_output = json.loads(replay_result.stdout)
    assert "replay-report.json" in replay_output["generated"]

    compare_result = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "compare",
            "--base", str(replay_dir),
            "--head", str(replay_dir),
            "--out", str(compare_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert compare_result.returncode == 0
    compare_output = json.loads(compare_result.stdout)
    assert compare_output["compare_status"] == "stable"


def test_p1a_explain_and_recommend_missing_execution(tmp_path: Path) -> None:
    """Explain and recommend reports describe the visible P0b missing execution."""
    fixture_dir = _missing_execution_p0b_output(tmp_path)
    explain_dir = tmp_path / "explain-output"
    recommend_dir = tmp_path / "recommend-output"

    explain_result = explain_trust(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        out_dir=explain_dir,
        mode="why-soft-gap",
    )
    recommend_result = recommend_trust(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        out_dir=recommend_dir,
        gap_id="missing_execution",
    )

    assert explain_result["reason_count"] == 1
    explain_report = json.loads((explain_dir / "explain-report.json").read_text())
    assert explain_report["reason_tree"][0]["risk_id"] == "risk-db-high"
    assert explain_report["reason_tree"][0]["source_refs"]
    assert explain_report["summary"]["traceability_complete"] is True
    assert explain_report["publish_gate_override"] is False

    assert recommend_result["recommendation_count"] == 1
    recommendation_report = json.loads((recommend_dir / "recommendation-report.json").read_text())
    recommendation = recommendation_report["recommendations"][0]
    assert recommendation["gap_id"] == "missing_execution"
    assert recommendation["risk_id"] == "risk-db-high"
    assert "manual-bb bridge review" in " ".join(recommendation["recommended_actions"])
    assert recommendation_report["summary"]["traceability_complete"] is True
    assert recommendation_report["summary"]["manual_bridge_recommendation_count"] == 1


def test_p1a_cli_explain_and_recommend(tmp_path: Path) -> None:
    """CLI explain and recommend commands generate expected reports."""
    fixture_dir = _missing_execution_p0b_output(tmp_path)
    explain_dir = tmp_path / "cli-explain"
    recommend_dir = tmp_path / "cli-recommend"

    explain_result = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "explain",
            "--bundle", str(fixture_dir / "qeg-bundle.json"),
            "--report", str(fixture_dir / "qeg-export-report.json"),
            "--out", str(explain_dir),
            "--mode", "why-soft-gap",
        ],
        capture_output=True,
        text=True,
    )
    assert explain_result.returncode == 0
    explain_output = json.loads(explain_result.stdout)
    assert explain_output["reason_count"] == 1

    recommend_result = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "recommend",
            "--bundle", str(fixture_dir / "qeg-bundle.json"),
            "--report", str(fixture_dir / "qeg-export-report.json"),
            "--out", str(recommend_dir),
            "--gap", "missing_execution",
        ],
        capture_output=True,
        text=True,
    )
    assert recommend_result.returncode == 0
    recommend_output = json.loads(recommend_result.stdout)
    assert recommend_output["recommendation_count"] == 1


def test_p1a_doctor_conformance_matrix(tmp_path: Path) -> None:
    """Doctor emits adapter capability and conformance reports."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    out_dir = tmp_path / "doctor-output"

    result = doctor_trust(
        bundle_path=fixture_dir / "qeg-bundle.json",
        report_path=fixture_dir / "qeg-export-report.json",
        out_dir=out_dir,
    )

    assert result["doctor_status"] == "success"
    assert result["conformance_status"] == "pass"
    assert "profile-report.json" in result["generated"]
    profile_report = json.loads((out_dir / "profile-report.json").read_text())
    assert profile_report["inherits"] == ["default"]
    manifest = json.loads((out_dir / "adapter-capability-manifest.json").read_text())
    assert manifest["capability"]["source_refs"] is True
    registry = json.loads((out_dir / "adapter-registry.json").read_text())
    assert registry["summary"]["adapter_count"] >= 16
    conformance = json.loads((out_dir / "adapter-conformance-report.json").read_text())
    assert conformance["summary"]["check_count"] >= 5
    assert conformance["adapter_registry"]["adapter_count"] == registry["summary"]["adapter_count"]
    assert len(conformance["adapter_results"]) == registry["summary"]["adapter_count"]
    assert all(result["conformance_status"] == "pass" for result in conformance["adapter_results"])


def test_p1a_cli_doctor(tmp_path: Path) -> None:
    """CLI doctor generates conformance artifacts."""
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    out_dir = tmp_path / "cli-doctor"

    result = subprocess.run(
        [
            "uv", "run", "python", "-m", "hate", "doctor",
            "--bundle", str(fixture_dir / "qeg-bundle.json"),
            "--report", str(fixture_dir / "qeg-export-report.json"),
            "--out", str(out_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["conformance_status"] == "pass"


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
