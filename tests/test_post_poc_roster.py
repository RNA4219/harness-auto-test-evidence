from __future__ import annotations

import json
from pathlib import Path

from hate.post_poc.roster import (
    build_roster_maintenance_report,
    build_roster_execution_manifest,
    discover_repositories_from_filesystem,
    evaluate_roster_fixture,
    write_roster_execution_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc" / "roster"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "real-repo-roster-maintenance-report.schema.json"
EXECUTION_SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "real-repo-roster-execution-manifest.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "real-repo-roster-maintenance-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for plan in report["maintenance_plans"]:
        assert plan["record_type"] == "real-repo-roster-maintenance-plan"
        assert plan["sourceRefs"]
    for recipe in report["environment_recipes"]:
        assert recipe["record_type"] == "real-repo-environment-recipe"
    for event in report["quarantine_events"]:
        assert event["record_type"] == "real-repo-quarantine-event"


def _assert_execution_manifest_contract(manifest: dict) -> None:
    schema = json.loads(EXECUTION_SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(manifest)
    assert manifest["schema_version"] == "HATE/v1"
    assert manifest["record_type"] == "real-repo-roster-execution-manifest"
    assert set(schema["properties"]["summary"]["required"]) <= set(manifest["summary"])
    for entry in manifest["entries"]:
        assert set(schema["properties"]["entries"]["items"]["required"]) <= set(entry)
        assert entry["record_type"] == "real-repo-roster-execution-entry"
        assert entry["execution_action"] in {"run", "quarantine", "external_hold"}
        assert entry["scheduler_job_id"].startswith("roster:")
        assert entry["sourceRefs"]


def test_task_postpoc_005_canonical_fixture_paths_exist() -> None:
    for name in [
        "owned-repo-bootstrap",
        "external-repair-denied",
        "stale-repo-quarantined",
        "dependency-bootstrap-failed",
        "large-roster-100-repos",
    ]:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_owned_repo_bootstrap_fixture_passes() -> None:
    result = evaluate_roster_fixture(_fixture("owned-repo-bootstrap"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    assert result["report"]["maintenance_plans"][0]["action"] == "maintain"
    _assert_report_contract(result["report"])


def test_external_repair_denied_holds_without_converting_to_implementation_failure() -> None:
    result = evaluate_roster_fixture(_fixture("external-repair-denied"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "roster_external_repo_repair_denied"
    assert result["report"]["maintenance_plans"][0]["action"] == "external_hold"
    assert result["report"]["maintenance_plans"][0]["external_repair_allowed"] is False


def test_stale_repo_is_quarantined() -> None:
    result = evaluate_roster_fixture(_fixture("stale-repo-quarantined"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "roster_repo_stale"
    assert result["report"]["summary"]["quarantine_count"] == 1
    assert result["report"]["quarantine_events"][0]["repo_id"] == "stale-owned"


def test_dependency_bootstrap_failure_is_quarantined() -> None:
    result = evaluate_roster_fixture(_fixture("dependency-bootstrap-failed"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "roster_dependency_bootstrap_failed"
    assert result["report"]["environment_recipes"][0]["bootstrap_status"] == "failed"


def test_missing_recipe_retry_group_and_record_floor_hold() -> None:
    report = build_roster_maintenance_report({
        "now": "2026-07-03T00:00:00Z",
        "repositories": [{"repo_id": "thin", "ownership_scope": "owned", "suites": [{"suite_id": "unit"}]}],
    })

    assert report["overall_status"] == "hold"
    assert "roster_environment_recipe_missing" in _codes(report)
    assert "roster_retry_isolation_missing" in _codes(report)
    assert "roster_expected_record_floor_missing" in _codes(report)


def test_large_roster_100_repos_is_deterministic() -> None:
    fixture = _fixture("large-roster-100-repos")
    fixture["input"]["repositories"] = [
        {
            "repo_id": f"repo-{index:03d}",
            "ownership_scope": "owned",
            "repo_class": "small",
            "discovery_source": "folder-scan",
            "last_seen_at": "2026-07-02T00:00:00Z",
            "stale_after": "2026-07-10T00:00:00Z",
            "environment_recipe_ref": f"recipes/repo-{index:03d}.json",
            "dependency_bootstrap_command": ["uv", "sync"],
            "dependency_bootstrap_status": "passed",
            "retry_isolation_group": f"repo-{index:03d}-unit",
            "expected_record_floor": 1,
            "suites": [{"suite_id": "unit"}],
        }
        for index in range(100)
    ]

    report = build_roster_maintenance_report(fixture["input"], report_id=fixture["fixture_id"])

    assert report["overall_status"] == "pass"
    assert report["summary"]["repo_count"] == 100
    assert report["summary"]["large_roster"] is True
    assert report["maintenance_plans"][0]["repo_id"] == "repo-000"
    assert report["maintenance_plans"][-1]["repo_id"] == "repo-099"


def test_filesystem_discovery_builds_roster_entries_without_executing_bootstrap(tmp_path: Path) -> None:
    python_repo = tmp_path / "python-service"
    node_repo = tmp_path / "packages" / "web"
    rust_repo = tmp_path / "crates" / "core"
    go_repo = tmp_path / "services" / "api"
    for path, marker in [
        (python_repo, "pyproject.toml"),
        (node_repo, "package.json"),
        (rust_repo, "Cargo.toml"),
        (go_repo, "go.mod"),
    ]:
        path.mkdir(parents=True)
        (path / marker).write_text("# marker\n", encoding="utf-8")

    discovered = discover_repositories_from_filesystem(tmp_path)
    report = build_roster_maintenance_report(discovered, report_id="filesystem-discovery")

    assert [repo["repo_id"] for repo in discovered["repositories"]] == [
        "crates-core",
        "packages-web",
        "python-service",
        "services-api",
    ]
    assert report["overall_status"] == "pass"
    assert report["summary"]["repo_count"] == 4
    assert {recipe["bootstrap_status"] for recipe in report["environment_recipes"]} == {"not_run"}
    assert all(plan["discovery_source"].startswith("filesystem:") for plan in report["maintenance_plans"])


def test_filesystem_discovery_respects_max_depth(tmp_path: Path) -> None:
    shallow_repo = tmp_path / "owned"
    deep_repo = tmp_path / "a" / "b" / "c" / "d"
    shallow_repo.mkdir()
    deep_repo.mkdir(parents=True)
    (shallow_repo / "pyproject.toml").write_text("# marker\n", encoding="utf-8")
    (deep_repo / "pyproject.toml").write_text("# marker\n", encoding="utf-8")

    discovered = discover_repositories_from_filesystem(tmp_path, max_depth=2)

    assert [repo["repo_id"] for repo in discovered["repositories"]] == ["owned"]


def test_roster_maintenance_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["real-repo-roster-maintenance-report"] == "schemas/HATE/v1/real-repo-roster-maintenance-report.schema.json"
    assert records["real-repo-roster-execution-manifest"] == "schemas/HATE/v1/real-repo-roster-execution-manifest.schema.json"


def test_roster_execution_manifest_is_scheduler_ready_for_clean_roster() -> None:
    manifest = build_roster_execution_manifest(_fixture("owned-repo-bootstrap")["input"], source_refs=["fixture://roster/execution"])

    assert manifest["record_type"] == "real-repo-roster-execution-manifest"
    _assert_execution_manifest_contract(manifest)
    assert manifest["summary"]["ready_for_scheduler"] is True
    assert manifest["summary"]["maintain_count"] == 1
    assert manifest["summary"]["bootstrap_required_count"] == 0
    entry = manifest["entries"][0]
    assert entry["execution_action"] == "run"
    assert entry["scheduler_job_id"].startswith("roster:")
    assert entry["retry_isolation_group"]
    assert manifest["sourceRefs"] == ["fixture://roster/execution"]


def test_roster_execution_manifest_quarantines_failed_bootstrap() -> None:
    manifest = build_roster_execution_manifest(_fixture("dependency-bootstrap-failed")["input"])

    assert manifest["summary"]["ready_for_scheduler"] is False
    assert manifest["summary"]["quarantine_count"] == 1
    assert manifest["summary"]["bootstrap_required_count"] == 1
    assert manifest["entries"][0]["execution_action"] == "quarantine"
    assert "roster_execution_blocked_by_maintenance_findings" in _codes(manifest)


def test_roster_execution_manifest_preserves_external_hold_boundary() -> None:
    manifest = build_roster_execution_manifest(_fixture("external-repair-denied")["input"])

    assert manifest["summary"]["external_hold_count"] == 1
    assert manifest["entries"][0]["execution_action"] == "external_hold"
    assert manifest["entries"][0]["ownership_scope"] == "external"


def test_roster_execution_manifest_requires_bootstrap_command_for_not_run_repo() -> None:
    report = build_roster_maintenance_report({
        "now": "2026-07-03T00:00:00Z",
        "repositories": [
            {
                "repo_id": "needs-bootstrap",
                "ownership_scope": "owned",
                "repo_class": "python",
                "discovery_source": "fixture",
                "last_seen_at": "2026-07-02T00:00:00Z",
                "stale_after": "2026-07-10T00:00:00Z",
                "environment_recipe_ref": "recipe://needs-bootstrap",
                "dependency_bootstrap_status": "not_run",
                "retry_isolation_group": "needs-bootstrap:unit",
                "expected_record_floor": 1,
                "suites": [{"suite_id": "unit"}],
            }
        ],
    })

    manifest = build_roster_execution_manifest(report)

    assert "roster_environment_recipe_missing" in _codes(manifest)
    assert manifest["entries"][0]["bootstrap_required"] is True


def test_roster_execution_manifest_write_contract(tmp_path: Path) -> None:
    manifest = build_roster_execution_manifest(_fixture("owned-repo-bootstrap")["input"], source_refs=["fixture://roster/manifest"])
    out_path = tmp_path / "roster-execution.json"

    artifact = write_roster_execution_manifest(manifest, out_path)

    assert artifact["record_type"] == "real-repo-roster-execution-manifest-artifact"
    assert artifact["entry_count"] == 1
    assert artifact["sourceRefs"] == ["fixture://roster/manifest"]
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["record_type"] == "real-repo-roster-execution-manifest"
    _assert_execution_manifest_contract(written)
    assert written["entries"][0]["execution_action"] == "run"
