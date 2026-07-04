"""Registry contracts for legacy runtime records that predate strict schemas."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path

from hate.p1a import compare_trust, evaluate_trust, explain_trust, recommend_trust, replay_trust
from hate.p1b import generate_workflow_mapping
from hate.p2p3 import generate_product_readiness
from hate.connectors import SCIMDiff, SSOMapping, build_scim_diff, build_sso_mapping
from hate.scale import ScaleFixtureSpec, generate_scale_fixture_manifest, validate_scale_fixture_manifest
from hate.store import HardDQFinding
from hate.store import ingest_local_store, query_local_store, read_history_index


def _evaluate_docs_freshness_gate(root: Path) -> dict:
    spec = importlib.util.spec_from_file_location(
        "docs_freshness_gate",
        Path("tools/ci/docs_freshness_gate.py"),
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.evaluate_docs_freshness_gate(root)


def _registry_by_record_type() -> dict[str, dict]:
    registry = json.loads(Path("schemas/HATE/v1/schema-registry.json").read_text(encoding="utf-8"))
    return {record["record_type"]: record for record in registry["records"]}


def _assert_registry_schema_contract(record: dict, registry: dict[str, dict]) -> None:
    assert record["record_type"] in registry
    schema = json.loads(Path(registry[record["record_type"]]["schema"]).read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(record)
    record_type_schema = schema["properties"]["record_type"]
    if "const" in record_type_schema:
        assert record["record_type"] == record_type_schema["const"]
    else:
        assert record["record_type"] in record_type_schema["enum"]
    for branch in schema.get("oneOf", []):
        branch_record_type = branch.get("properties", {}).get("record_type", {}).get("const")
        if branch_record_type == record["record_type"]:
            assert set(branch.get("required", [])) <= set(record)
            break


def test_product_runtime_records_are_registered_and_schema_compatible(tmp_path: Path) -> None:
    out_dir = tmp_path / "product-output"
    generate_product_readiness(
        bundle_path=Path("fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json"),
        trust_dir=Path("fixtures/golden/p1a-trust-minimal/expected"),
        workflow_dir=Path("fixtures/golden/p1b-workflow-minimal/expected"),
        out_dir=out_dir,
    )

    registry = _registry_by_record_type()
    for filename in [
        "product-readiness-report.json",
        "enterprise-metrics-report.json",
        "product-error-catalog.json",
        "pr-annotation-export.json",
        "enterprise-risk-debt-register.json",
        "privacy-quarantine-report.json",
        "external-export-report.json",
        "hosted-read-model-index.json",
        "domain-model-report.json",
        "rbac-matrix-report.json",
        "identity-connector-report.json",
        "enterprise-connector-report.json",
        "retention-governance-report.json",
        "release-migration-report.json",
        "entitlement-usage-report.json",
        "customer-docs-index.json",
        "incident-slo-report.json",
        "adoption-health-report.json",
        "security-trust-packet.json",
        "residency-deployment-report.json",
        "roadmap-decision-record.json",
        "accessibility-localization-report.json",
        "support-diagnostic-bundle.json",
        "privacy-telemetry-report.json",
        "governance-portfolio-report.json",
        "dashboard-view-model.json",
    ]:
        _assert_registry_schema_contract(json.loads((out_dir / filename).read_text(encoding="utf-8")), registry)


def test_trust_advisory_records_are_registered_and_schema_compatible(tmp_path: Path) -> None:
    fixture_dir = Path("fixtures/golden/p0b-qeg-minimal/expected")
    base_dir = tmp_path / "trust-base"
    head_dir = tmp_path / "trust-head"
    replay_dir = tmp_path / "trust-replay"
    compare_dir = tmp_path / "trust-compare"
    explain_dir = tmp_path / "trust-explain"
    recommend_dir = tmp_path / "trust-recommend"
    evaluate_trust(fixture_dir / "qeg-bundle.json", fixture_dir / "qeg-export-report.json", base_dir)
    evaluate_trust(fixture_dir / "qeg-bundle.json", fixture_dir / "qeg-export-report.json", head_dir)
    replay_trust(fixture_dir / "qeg-bundle.json", fixture_dir / "qeg-export-report.json", replay_dir)
    compare_trust(base_dir, head_dir, compare_dir)
    explain_trust(fixture_dir / "qeg-bundle.json", fixture_dir / "qeg-export-report.json", explain_dir)
    recommend_trust(fixture_dir / "qeg-bundle.json", fixture_dir / "qeg-export-report.json", recommend_dir)

    registry = _registry_by_record_type()
    for path in [
        replay_dir / "replay-report.json",
        compare_dir / "compare-report.json",
        explain_dir / "explain-report.json",
        recommend_dir / "recommendation-report.json",
    ]:
        _assert_registry_schema_contract(json.loads(path.read_text(encoding="utf-8")), registry)


def test_local_store_runtime_records_are_registered_and_schema_compatible(tmp_path: Path) -> None:
    store_dir = tmp_path / ".hate"
    readiness_dir = tmp_path / "product-output"
    generate_product_readiness(
        bundle_path=Path("fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json"),
        trust_dir=Path("fixtures/golden/p1a-trust-minimal/expected"),
        workflow_dir=Path("fixtures/golden/p1b-workflow-minimal/expected"),
        out_dir=readiness_dir,
    )
    ingest_local_store(
        store_dir=store_dir,
        bundle_path=Path("fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json"),
        readiness_dir=readiness_dir,
    )

    registry = _registry_by_record_type()
    records = [
        json.loads((store_dir / "runs" / "1001" / "store-manifest.json").read_text(encoding="utf-8")),
        read_history_index(store_dir),
        query_local_store(store_dir, resource="run"),
    ]
    for record in records:
        _assert_registry_schema_contract(record, registry)


def test_workflow_runtime_records_are_registered_and_schema_compatible(tmp_path: Path) -> None:
    out_dir = tmp_path / "workflow-output"
    generate_workflow_mapping(
        bundle_path=Path("fixtures/golden/p0b-qeg-minimal/expected/qeg-bundle.json"),
        report_path=Path("fixtures/golden/p0b-qeg-minimal/expected/qeg-export-report.json"),
        trust_dir=Path("fixtures/golden/p1a-trust-minimal/expected"),
        out_dir=out_dir,
    )

    registry = _registry_by_record_type()
    json_records = [
        "requirement-evidence-alignment.json",
        "workflow-task-seed.json",
        "workflow-acceptance-record.json",
        "workflow-docs-stale.json",
        "workflow-birdseye-map.json",
        "workflow-cookbook-evidence-map.json",
        "shipyard-run-evidence.json",
    ]
    records = [json.loads((out_dir / filename).read_text(encoding="utf-8")) for filename in json_records]
    records.extend(
        json.loads(line)
        for line in (out_dir / "workflow-evidence.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    for record in records:
        _assert_registry_schema_contract(record, registry)


def test_connector_projection_records_are_registered_and_schema_compatible() -> None:
    registry = _registry_by_record_type()
    enterprise_control_report = {
        "schema_version": "HATE/v1",
        "sourceRefs": ["fixture:enterprise-control"],
        "audit_event_refs": ["audit:event:1"],
        "sso_mapping": {
            "mapping_id": "sso-fixture",
            "claims": [{"name": "email", "sourceRef": "fixture:claim"}],
            "groups": [{"name": "engineering", "sourceRef": "fixture:group"}],
            "roles": [{"name": "developer", "sourceRef": "fixture:role"}],
        },
        "scim": {
            "diff_id": "scim-fixture",
            "current_users": [],
            "desired_users": [{"id": "user-1", "userName": "user@example.test"}],
            "current_groups": [],
            "desired_groups": [{"id": "group-1", "displayName": "engineering"}],
        },
    }
    records = [
        SSOMapping(mapping_id="sso-fixture", provider="oidc").to_dict(),
        build_sso_mapping(
            enterprise_control_report,
            {
                "issuer": "https://issuer.example.test",
                "audience": "hate",
                "supported_claims": ["email"],
                "supported_groups": ["engineering"],
                "supported_roles": ["developer"],
                "required_claims": ["email"],
            },
        ).to_dict(),
        SCIMDiff(diff_id="scim-fixture").to_dict(),
        build_scim_diff(enterprise_control_report, {"enabled": True}).to_dict(),
    ]

    for record in records:
        _assert_registry_schema_contract(record, registry)


def test_store_scale_records_are_registered_and_schema_compatible() -> None:
    registry = _registry_by_record_type()
    manifest = generate_scale_fixture_manifest(
        ScaleFixtureSpec(
            fixture_id="strict-schema-smoke",
            seed="schema",
            target_tests=2,
            target_coverage_records=1,
            target_artifact_metadata=1,
            target_risks=1,
            target_graph_nodes=5,
            target_graph_edges=4,
        )
    )
    records = [
        manifest.to_dict(),
        validate_scale_fixture_manifest(manifest).to_dict(),
        HardDQFinding(
            message="missing indexed record",
            index_type="runs",
            referenced_key="run-1",
            missing_path="runs/run-1.json",
        ).to_record(),
    ]

    for record in records:
        _assert_registry_schema_contract(record, registry)


def test_ci_docs_freshness_gate_is_registered_and_schema_compatible() -> None:
    registry = _registry_by_record_type()
    report = _evaluate_docs_freshness_gate(Path("."))

    _assert_registry_schema_contract(report, registry)


def test_runtime_compat_records_have_been_split_into_strict_area_schemas() -> None:
    registry = _registry_by_record_type()
    area_schemas = [
        "schemas/HATE/v1/trust-advisory-report.schema.json",
        "schemas/HATE/v1/workflow-alignment-runtime.schema.json",
        "schemas/HATE/v1/enterprise-operating-report.schema.json",
        "schemas/HATE/v1/connector-governance-runtime.schema.json",
        "schemas/HATE/v1/store-scale-runtime.schema.json",
        "schemas/HATE/v1/support-dashboard-runtime.schema.json",
    ]
    strict_record_types: set[str] = set()
    for schema_ref in area_schemas:
        schema = json.loads(Path(schema_ref).read_text(encoding="utf-8"))
        strict_record_types.update(schema["properties"]["record_type"]["enum"])

    assert strict_record_types
    assert all(record["schema"] != "schemas/HATE/v1/runtime-compat-record.schema.json" for record in registry.values())
    for record_type in strict_record_types:
        assert record_type in registry
        assert registry[record_type]["schema"] in area_schemas
