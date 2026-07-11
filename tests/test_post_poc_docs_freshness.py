from __future__ import annotations

import json
import importlib.util
import re
from pathlib import Path

from hate.post_poc.docs_freshness import build_docs_freshness_ci_report, evaluate_docs_freshness_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "post-poc" / "docs-freshness"
SCHEMA = ROOT / "schemas" / "HATE" / "v1" / "docs-freshness-ci-report.schema.json"
REGISTRY = ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
CI_GATE = ROOT / "tools" / "ci" / "docs_freshness_gate.py"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name / "fixture.json").read_text(encoding="utf-8"))


def _codes(report: dict) -> list[str]:
    return [finding["code"] for finding in report["findings"]]


def _assert_report_contract(report: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(report)
    assert report["schema_version"] == "HATE/v1"
    assert report["record_type"] == "docs-freshness-ci-report"
    assert report["overall_status"] in {"pass", "hold"}
    assert report["readiness_effect"] in {"none", "hold"}
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)


def test_task_postpoc_009_canonical_fixture_paths_exist() -> None:
    for name in [
        "readme-current",
        "readme-stale",
        "missing-acceptance",
        "codemap-stale",
        "schema-registry-stale",
        "product-ready-overclaim",
    ]:
        assert (FIXTURES / name / "fixture.json").is_file()


def test_docs_freshness_current_fixture_passes() -> None:
    result = evaluate_docs_freshness_fixture(_fixture("readme-current"))

    assert result["status"] == "pass"
    assert result["finding_code"] == ""
    assert result["readiness_effect"] == "none"
    assert result["report"]["summary"]["finding_count"] == 0
    _assert_report_contract(result["report"])


def test_readme_stale_fixture_holds() -> None:
    result = evaluate_docs_freshness_fixture(_fixture("readme-stale"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "docs_readme_state_stale"
    _assert_report_contract(result["report"])


def test_missing_acceptance_fixture_holds() -> None:
    result = evaluate_docs_freshness_fixture(_fixture("missing-acceptance"))

    assert result["status"] == "hold"
    assert result["finding_code"] == "docs_acceptance_record_missing"


def test_codemap_stale_fixture_holds() -> None:
    result = evaluate_docs_freshness_fixture(_fixture("codemap-stale"))

    assert result["status"] == "hold"
    assert "docs_codemap_stale" in _codes(result["report"])


def test_schema_registry_stale_fixture_holds() -> None:
    result = evaluate_docs_freshness_fixture(_fixture("schema-registry-stale"))

    assert result["status"] == "hold"
    assert "docs_schema_registry_stale" in _codes(result["report"])


def test_product_ready_overclaim_fixture_holds() -> None:
    result = evaluate_docs_freshness_fixture(_fixture("product-ready-overclaim"))

    assert result["status"] == "hold"
    assert "docs_product_ready_overclaim" in _codes(result["report"])


def test_emergency_exception_requires_owner_reason_expiry_and_acceptance() -> None:
    report = build_docs_freshness_ci_report({
        "freshness": {
            "readme_state_current": True,
            "codemap_current": False,
            "schema_registry_current": True,
            "emergency_exception": True
        },
        "exceptions": [{"owner": "qa", "reason": "hotfix", "expiry": "", "acceptance_ref": "AC-1"}]
    })

    assert report["overall_status"] == "hold"
    assert "docs_freshness_exception_invalid" in _codes(report)


def test_valid_emergency_exception_does_not_add_exception_finding() -> None:
    report = build_docs_freshness_ci_report({
        "freshness": {
            "readme_state_current": True,
            "codemap_current": False,
            "schema_registry_current": True,
            "emergency_exception": True
        },
        "exceptions": [{"owner": "qa", "reason": "hotfix", "expiry": "2026-07-04", "acceptance_ref": "AC-1"}]
    })

    assert report["overall_status"] == "hold"
    assert "docs_codemap_stale" in _codes(report)
    assert "docs_freshness_exception_invalid" not in _codes(report)


def test_docs_freshness_schema_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = {record["record_type"]: record["schema"] for record in registry["records"]}

    assert records["docs-freshness-ci-report"] == "schemas/HATE/v1/docs-freshness-ci-report.schema.json"


def test_docs_freshness_gate_is_wired_into_ci_workflow() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "Docs freshness gate" in workflow
    assert "uv run python tools/ci/docs_freshness_gate.py" in workflow


def test_docs_freshness_gate_passes_current_repo_state() -> None:
    spec = importlib.util.spec_from_file_location("docs_freshness_gate", CI_GATE)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    report = module.evaluate_docs_freshness_gate(ROOT)

    assert report["overall_status"] == "pass"
    assert report["summary"]["finding_count"] == 0


def test_docs_freshness_gate_findings_include_source_refs(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "docs" / "acceptance").mkdir(parents=True)
    (root / "docs" / "process").mkdir(parents=True)
    (root / "schemas" / "HATE" / "v1").mkdir(parents=True)
    (root / "README.md").write_text("stale\n", encoding="utf-8")
    (root / "schemas" / "HATE" / "v1" / "schema-registry.json").write_text(json.dumps({"records": []}), encoding="utf-8")

    spec = importlib.util.spec_from_file_location("docs_freshness_gate", CI_GATE)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    report = module.evaluate_docs_freshness_gate(root)

    assert report["overall_status"] == "hold"
    assert report["findings"]
    for finding in report["findings"]:
        assert {"code", "severity", "message", "sourceRef", "readiness_effect"} <= set(finding)
        assert finding["sourceRef"]


def test_docs_freshness_gate_detects_malformed_acceptance_records(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "docs" / "acceptance").mkdir(parents=True)
    (root / "docs" / "process").mkdir(parents=True)
    (root / "docs" / "birdseye").mkdir(parents=True)
    (root / "schemas" / "HATE" / "v1").mkdir(parents=True)
    (root / "README.md").write_text(
        "POST_POC_REQUIREMENTS_GAP_AUDIT.md\n"
        "POST_POC_PRODUCTIZATION_DETAIL_SPEC.md\n"
        "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md\n"
        "POST_POC_IMPLEMENTATION_GAP_CHECKLIST.md\n"
        "product_ready=false\n",
        encoding="utf-8",
    )
    for index in range(1, 17):
        (root / "docs" / "acceptance" / f"AC-20260703-postpoc-{index:03d}.md").write_text("# missing metadata\n", encoding="utf-8")
    (root / "docs" / "process" / "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md").write_text(
        "## 4. Current Decision\n\nAll 16 post-PoC gaps are `accepted`.\n",
        encoding="utf-8",
    )
    (root / "docs" / "birdseye" / "index.json").write_text("{}", encoding="utf-8")
    (root / "schemas" / "HATE" / "v1" / "schema-registry.json").write_text(json.dumps({"records": []}), encoding="utf-8")

    spec = importlib.util.spec_from_file_location("docs_freshness_gate", CI_GATE)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    report = module.evaluate_docs_freshness_gate(root)

    assert report["overall_status"] == "hold"
    assert "docs_acceptance_record_malformed" in {finding["code"] for finding in report["findings"]}


def test_docs_freshness_gate_requires_canonical_registry(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "docs" / "acceptance").mkdir(parents=True)
    (root / "docs" / "process").mkdir(parents=True)
    (root / "docs" / "birdseye").mkdir(parents=True)
    (root / "schemas" / "HATE" / "v1").mkdir(parents=True)
    (root / "README.md").write_text(
        "POST_POC_REQUIREMENTS_GAP_AUDIT.md\n"
        "POST_POC_PRODUCTIZATION_DETAIL_SPEC.md\n"
        "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md\n"
        "POST_POC_IMPLEMENTATION_GAP_CHECKLIST.md\n"
        "product_ready=false\n",
        encoding="utf-8",
    )
    for index in range(1, 17):
        (root / "docs" / "acceptance" / f"AC-20260703-postpoc-{index:03d}.md").write_text("# accepted\n", encoding="utf-8")
    (root / "docs" / "process" / "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md").write_text(
        "| HATE-POSTPOC-GAP-001 | done | accepted |\n"
        "## 4. Current Decision\n\nAll 16 post-PoC gaps are `accepted`.\n",
        encoding="utf-8",
    )
    (root / "docs" / "birdseye" / "index.json").write_text("{}", encoding="utf-8")
    (root / "schemas" / "HATE" / "v1" / "schema-registry.json").write_text(json.dumps({"records": []}), encoding="utf-8")

    spec = importlib.util.spec_from_file_location("docs_freshness_gate", CI_GATE)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    report = module.evaluate_docs_freshness_gate(root)
    codes = {finding["code"] for finding in report["findings"]}

    assert "docs_post_poc_registry_missing" in codes


def test_docs_freshness_gate_detects_missing_schema_paths(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "docs" / "acceptance").mkdir(parents=True)
    (root / "docs" / "process").mkdir(parents=True)
    (root / "docs" / "birdseye").mkdir(parents=True)
    (root / "schemas" / "HATE" / "v1").mkdir(parents=True)
    (root / "README.md").write_text(
        "POST_POC_REQUIREMENTS_GAP_AUDIT.md\n"
        "POST_POC_PRODUCTIZATION_DETAIL_SPEC.md\n"
        "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md\n"
        "POST_POC_IMPLEMENTATION_GAP_CHECKLIST.md\n"
        "product_ready=false\n",
        encoding="utf-8",
    )
    for index in range(1, 17):
        (root / "docs" / "acceptance" / f"AC-20260703-postpoc-{index:03d}.md").write_text("# accepted\n", encoding="utf-8")
    (root / "docs" / "birdseye" / "index.json").write_text("{}", encoding="utf-8")
    (root / "docs" / "process" / "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md").write_text(
        "## 4. Current Decision\n\nAll 16 post-PoC gaps are `accepted`.\n",
        encoding="utf-8",
    )

    spec = importlib.util.spec_from_file_location("docs_freshness_gate", CI_GATE)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    records = [
        {"record_type": record_type, "schema": "schemas/HATE/v1/missing.schema.json"}
        for record_type in module.POST_POC_SCHEMA_RECORDS
    ]
    (root / "schemas" / "HATE" / "v1" / "schema-registry.json").write_text(json.dumps({"records": records}), encoding="utf-8")

    report = module.evaluate_docs_freshness_gate(root)

    assert report["overall_status"] == "hold"
    assert "docs_schema_registry_path_missing" in {finding["code"] for finding in report["findings"]}


def test_docs_freshness_gate_detects_schema_record_type_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "docs" / "acceptance").mkdir(parents=True)
    (root / "docs" / "process").mkdir(parents=True)
    (root / "docs" / "birdseye").mkdir(parents=True)
    schemas = root / "schemas" / "HATE" / "v1"
    schemas.mkdir(parents=True)
    (root / "README.md").write_text(
        "POST_POC_REQUIREMENTS_GAP_AUDIT.md\n"
        "POST_POC_PRODUCTIZATION_DETAIL_SPEC.md\n"
        "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md\n"
        "POST_POC_IMPLEMENTATION_GAP_CHECKLIST.md\n"
        "product_ready=false\n",
        encoding="utf-8",
    )
    for index in range(1, 17):
        (root / "docs" / "acceptance" / f"AC-20260703-postpoc-{index:03d}.md").write_text("# accepted\n", encoding="utf-8")
    (root / "docs" / "birdseye" / "index.json").write_text("{}", encoding="utf-8")
    (root / "docs" / "process" / "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md").write_text(
        "## 4. Current Decision\n\nAll 16 post-PoC gaps are `accepted`.\n",
        encoding="utf-8",
    )

    spec = importlib.util.spec_from_file_location("docs_freshness_gate", CI_GATE)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    for record_type in module.POST_POC_SCHEMA_RECORDS:
        (schemas / f"{record_type}.schema.json").write_text(
            json.dumps({"properties": {"record_type": {"const": "wrong-record-type"}}}),
            encoding="utf-8",
        )
    records = [
        {"record_type": record_type, "schema": f"schemas/HATE/v1/{record_type}.schema.json"}
        for record_type in module.POST_POC_SCHEMA_RECORDS
    ]
    (schemas / "schema-registry.json").write_text(json.dumps({"records": records}), encoding="utf-8")

    report = module.evaluate_docs_freshness_gate(root)

    assert report["overall_status"] == "hold"
    assert "docs_schema_record_type_mismatch" in {finding["code"] for finding in report["findings"]}


def test_docs_freshness_gate_covers_post_poc_emitted_artifact_record_types() -> None:
    spec = importlib.util.spec_from_file_location("docs_freshness_gate", CI_GATE)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    emitted: set[str] = set()
    for path in (ROOT / "src" / "hate" / "post_poc").glob("*.py"):
        for match in re.finditer(r'"record_type"\s*:\s*"([^"]+)"', path.read_text(encoding="utf-8")):
            record_type = match.group(1)
            if re.search(r"(report|manifest|packet|runbook|artifact|step)$", record_type):
                emitted.add(record_type)

    assert emitted <= module.POST_POC_SCHEMA_RECORDS


def test_docs_freshness_gate_detects_stale_post_poc_traceability_decision(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    process = root / "docs" / "process"
    acceptance = root / "docs" / "acceptance"
    schemas = root / "schemas" / "HATE" / "v1"
    birdseye = root / "docs" / "birdseye"
    process.mkdir(parents=True)
    acceptance.mkdir(parents=True)
    schemas.mkdir(parents=True)
    birdseye.mkdir(parents=True)

    (root / "README.md").write_text(
        "POST_POC_REQUIREMENTS_GAP_AUDIT.md\n"
        "POST_POC_PRODUCTIZATION_DETAIL_SPEC.md\n"
        "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md\n"
        "POST_POC_IMPLEMENTATION_GAP_CHECKLIST.md\n"
        "product_ready=false\n",
        encoding="utf-8",
    )
    for index in range(1, 17):
        (acceptance / f"AC-20260703-postpoc-{index:03d}.md").write_text("# accepted\n", encoding="utf-8")
    (schemas / "schema-registry.json").write_text(
        json.dumps({"records": [{"record_type": record_type} for record_type in sorted({
            "baseline-promotion-report",
            "capacity-report",
            "compliance-report",
            "connector-runtime-report",
            "dashboard-interaction-report",
            "docs-freshness-ci-report",
            "history-analytics-report",
            "hosted-api-report",
            "hosted-scheduler-runtime-report",
            "human-review-workflow-report",
            "notification-delivery-report",
            "observability-report",
            "plugin-distribution-report",
            "real-repo-roster-maintenance-report",
            "release-handoff-report",
            "store-dr-report",
        })]}),
        encoding="utf-8",
    )
    (birdseye / "index.json").write_text("{}", encoding="utf-8")
    accepted_rows = "\n".join(
        f"| HATE-POSTPOC-GAP-{index:03d} | done | done | done | done | done | done | done | accepted | done | accepted | local evidence |"
        for index in range(1, 17)
    )
    (process / "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md").write_text(
        "# Post-PoC Spec Traceability Checklist\n\n"
        "| Gap ID | Requirement | Detail Spec | Packet | Runtime | Schema | Fixtures | Tests | Acceptance | Product-Grade Exposure | Status | Blocking Spec Gaps |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        f"{accepted_rows}\n\n"
        "## 4. Current Decision\n\n"
        "All 16 post-PoC gaps are `spec-ready`. They remain not implemented until runtime, schema, fixtures, tests, and acceptance records are added.\n",
        encoding="utf-8",
    )

    spec = importlib.util.spec_from_file_location("docs_freshness_gate", CI_GATE)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    report = module.evaluate_docs_freshness_gate(root)

    assert report["overall_status"] == "hold"
    codes = {finding["code"] for finding in report["findings"]}
    assert "docs_post_poc_registry_missing" in codes

def test_docs_freshness_gate_detects_canonical_registry_status_drift(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    process = root / "docs" / "process"
    acceptance = root / "docs" / "acceptance"
    schemas = root / "schemas" / "HATE" / "v1"
    birdseye = root / "docs" / "birdseye"
    process.mkdir(parents=True)
    acceptance.mkdir(parents=True)
    schemas.mkdir(parents=True)
    birdseye.mkdir(parents=True)

    acceptance_ref = "docs/acceptance/AC-local.md"
    implementation_ref = "src/hate/post_poc/example.py"
    test_ref = "tests/test_example.py"
    (root / implementation_ref).parent.mkdir(parents=True)
    (root / implementation_ref).write_text("", encoding="utf-8")
    (root / test_ref).parent.mkdir(parents=True)
    (root / test_ref).write_text("", encoding="utf-8")
    (root / acceptance_ref).write_text(
        "intent_id: X\nowner: qa\nstatus: accepted\nlast_reviewed_at: 2026-07-11\n"
        "next_review_due: 2026-07-18\n## Verification\ncommand\n## Evidence\nrefs\n"
        "## Open Risks\nopen\n## Decision\naccepted\n",
        encoding="utf-8",
    )
    registry = {
        "product_ready": False,
        "release_authority": "external",
        "gaps": [{
            "gap_id": "HATE-POSTPOC-GAP-001",
            "area": "Example",
            "local_slice_status": "accepted",
            "product_status": "open",
            "remaining_work": "Hosted runtime",
            "implementation_refs": [implementation_ref],
            "test_refs": [test_ref],
            "acceptance_ref": acceptance_ref,
        }],
    }
    (process / "post-poc-gap-registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (root / "README.md").write_text(
        "POST_POC_REQUIREMENTS_GAP_AUDIT.md\nPOST_POC_PRODUCTIZATION_DETAIL_SPEC.md\n"
        "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md\nPOST_POC_IMPLEMENTATION_GAP_CHECKLIST.md\n"
        "post-poc-gap-registry.json\nproduct_ready=false\n",
        encoding="utf-8",
    )
    documents = {
        "POST_POC_REQUIREMENTS_GAP_AUDIT.md": "POST_POC_REQUIREMENTS",
        "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md": "POST_POC_TRACEABILITY",
        "POST_POC_IMPLEMENTATION_GAP_CHECKLIST.md": "POST_POC_IMPLEMENTATION",
    }
    for name, marker in documents.items():
        status = "closed" if name == "POST_POC_REQUIREMENTS_GAP_AUDIT.md" else "open"
        body = (
            f"<!-- BEGIN GENERATED:{marker} -->\n"
            f"| HATE-POSTPOC-GAP-001 | accepted | {status} |\n"
            f"<!-- END GENERATED:{marker} -->\n"
        )
        if name == "POST_POC_SPEC_TRACEABILITY_CHECKLIST.md":
            body += "All local evidence slices are accepted. All product gaps remain open.\n"
        (process / name).write_text(body, encoding="utf-8")
    (schemas / "schema-registry.json").write_text(json.dumps({"records": []}), encoding="utf-8")
    (birdseye / "index.json").write_text("{}", encoding="utf-8")

    spec = importlib.util.spec_from_file_location("docs_freshness_gate", CI_GATE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    report = module.evaluate_docs_freshness_gate(root)

    assert "docs_post_poc_generated_status_stale" in {finding["code"] for finding in report["findings"]}
