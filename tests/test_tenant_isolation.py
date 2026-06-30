from __future__ import annotations

import json
from pathlib import Path

from hate.gap_closure import generate_gap_closure_report
from hate.tenant_isolation import evaluate_tenant_isolation_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "enterprise" / "tenant"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name / "fixture.json").read_text(encoding="utf-8"))


def test_own_org_store_access_passes_with_audit_event() -> None:
    report = evaluate_tenant_isolation_fixture(_load_fixture("own-org-access"), source_version="test")

    assert report["record_type"] == "tenant-isolation-report"
    assert report["status"] == "pass"
    event = report["audit_events"][0]
    assert event["tenant_id"] == "tenant_a"
    assert event["decision"] == "allow"
    assert event["event_hash"].startswith("sha256:")


def test_cross_org_artifact_access_is_denied_before_artifact_safety() -> None:
    report = evaluate_tenant_isolation_fixture(_load_fixture("cross-org-denied"))

    assert report["status"] == "hold"
    assert report["finding_code"] == "tenant_cross_access_denied"
    assert report["audit_events"][0]["decision"] == "deny"


def test_cache_key_must_include_tenant_scope() -> None:
    report = evaluate_tenant_isolation_fixture(_load_fixture("cache-bleed-denied"))

    assert report["status"] == "hold"
    assert report["finding_code"] == "tenant_cache_key_missing_scope"


def test_auditor_cross_tenant_read_requires_global_scope() -> None:
    denied = evaluate_tenant_isolation_fixture(_load_fixture("audit-cross-read-denied"))
    allowed_fixture = _load_fixture("audit-cross-read-denied")
    allowed_fixture["input"]["global_auditor"] = True

    allowed = evaluate_tenant_isolation_fixture(allowed_fixture)

    assert denied["finding_code"] == "tenant_cross_access_denied"
    assert allowed["status"] == "pass"
    assert allowed["audit_events"][0]["decision"] == "allow"


def test_export_cannot_mix_tenant_bundles() -> None:
    report = evaluate_tenant_isolation_fixture(_load_fixture("export-mixed-tenant-denied"))

    assert report["status"] == "hold"
    assert report["finding_code"] == "tenant_export_mixed_denied"


def test_support_bundle_omits_other_tenant_metadata() -> None:
    report = evaluate_tenant_isolation_fixture(_load_fixture("support-bundle-isolated"))

    assert report["status"] == "pass"
    assert report["audit_events"][0]["decision"] == "allow"


def test_telemetry_denies_tenant_identifying_payload() -> None:
    report = evaluate_tenant_isolation_fixture(_load_fixture("telemetry-payload-denied"))

    assert report["status"] == "hold"
    assert report["finding_code"] == "tenant_telemetry_payload_denied"


def test_tenant_isolation_report_schema_is_registered() -> None:
    registry = json.loads((ROOT / "schemas" / "HATE" / "v1" / "schema-registry.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas" / "HATE" / "v1" / "tenant-isolation-report.schema.json").read_text(encoding="utf-8"))
    report = evaluate_tenant_isolation_fixture(_load_fixture("own-org-access"))

    assert any(item["record_type"] == "tenant-isolation-report" for item in registry["records"])
    for field in schema["required"]:
        assert field in report


def test_contract_named_tenant_isolation_fixtures_exist() -> None:
    fixture_names = {
        "cross-org-denied",
        "artifact-cross-access-denied",
        "cache-bleed-denied",
        "audit-cross-read-denied",
        "export-mixed-tenant-denied",
        "support-bundle-isolated",
        "telemetry-payload-denied",
    }

    missing = [name for name in fixture_names if not (FIXTURE_DIR / name / "fixture.json").is_file()]

    assert missing == []


def test_gap_closure_marks_gap_002_implemented(tmp_path: Path) -> None:
    report = generate_gap_closure_report(ROOT, tmp_path, source_version="tenant-isolation-test")
    gap_002 = next(gap for gap in report["gaps"] if gap["gap_id"] == "HATE-GAP-002")

    assert gap_002["status"] == "implemented"
    assert gap_002["implementation_evidence"]["runtime_module"] == "src/hate/tenant_isolation.py"
    assert "tests/test_tenant_isolation.py" in gap_002["implementation_evidence"]["tests"]
