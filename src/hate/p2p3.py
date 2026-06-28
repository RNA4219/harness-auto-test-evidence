from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Any

from .p2p3_io import ProductError, _api_envelope, _missing_conformance_report, _read_json, _read_optional_json, _stable_ref, _write_json
from .p2p3_readiness import _build_product_metrics, _build_product_readiness_report, _missing_product_input_refs, _product_artifact_refs
from .p2p3_reports import (
    _build_artifact_budget_report,
    _build_attestation_report,
    _build_enterprise_risk_debt,
    _build_error_catalog,
    _build_external_export_report,
    _build_hosted_read_model_index,
    _build_privacy_quarantine_report,
    _build_pr_annotation_export,
)
from .p2p3_enterprise_reports import (
    _build_accessibility_localization_report,
    _build_adoption_health_report,
    _build_customer_docs_index,
    _build_entitlement_usage_report,
    _build_incident_slo_report,
    _build_release_migration_report,
    _build_residency_deployment_report,
    _build_roadmap_decision_report,
    _build_security_trust_packet,
)
from .p2p3_assurance_reports import (
    _build_assurance_pack,
    _build_commercial_contract_report,
    _build_dashboard_html,
    _build_dashboard_view_model,
    _build_governance_portfolio_report,
    _build_privacy_telemetry_report,
    _build_shipyard_evidence,
    _build_support_diagnostic_bundle,
)

from . import __version__
from .audit import build_audit_event_log
from .authz import build_rbac_matrix_report, read_model_allowed
from .connectors import build_enterprise_connector_report, build_identity_connector_report
from .domain import build_enterprise_domain_model
from .governance import build_retention_governance_report
from .release import build_release_candidate_pack

SCHEMA_VERSION = "HATE/v1"
TASK_ID = "HATE-MVP-008-P2P3-PRODUCT-READINESS"


def query_product_read_model(
    readiness_dir: Path,
    resource: str,
    request_id: str = "req_local",
    role: str = "developer",
    filters: dict[str, str] | None = None,
    stale_cache: bool = False,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Return a hosted-read-model-compatible API response envelope from local artifacts."""
    if not readiness_dir.exists():
        raise ProductError(f"product readiness directory not found: {readiness_dir}", exit_code=2)
    artifact_map = {
        "runs": "product-readiness-report.json",
        "bundles": "product-readiness-report.json",
        "evidence": "product-readiness-report.json",
        "artifacts": "artifact-budget-report.json",
        "risk-debt": "enterprise-risk-debt-register.json",
        "profiles": "hosted-read-model-index.json",
        "adapters": "enterprise-metrics-report.json",
        "audit-events": "audit-event-log.json",
        "product-readiness": "product-readiness-report.json",
    }
    if resource not in artifact_map:
        return _api_envelope(
            request_id=request_id,
            data={},
            errors=[{
                "code": "HATE-E-PRODUCT-QUERY-404",
                "http_status": 404,
                "category": "SYS",
                "message": f"unknown read model resource: {resource}",
                "remediation": "Use one of the hosted read model resource names.",
            }],
            source={"bundle_id": "", "record_id": "", "generated_at": ""},
        )
    if _forbidden_read_model_resource(resource, role):
        return _api_envelope(
            request_id=request_id,
            data={},
            errors=[{
                "code": "HATE-E-PRODUCT-QUERY-403",
                "http_status": 403,
                "category": "SEC",
                "message": f"role {role} cannot read resource: {resource}",
                "remediation": "Use a role with read permission or query a less sensitive resource.",
            }],
            source={"bundle_id": "", "record_id": "", "generated_at": ""},
        )
    source_path = readiness_dir / artifact_map[resource]
    data = _read_json(source_path)
    filtered = _apply_read_model_filters(resource, data, filters or {})
    return _api_envelope(
        request_id=request_id,
        data={
            "resource": resource,
            "path": f"/v1/{resource}",
            "attributes": filtered,
            "filters": filters or {},
            "role": role,
            "stale_cache": stale_cache,
            "canonical_source_preserved": True,
            "release_gate_override": False,
            "publish_gate_override": False,
        },
        errors=[],
        source={
            "bundle_id": str(data.get("run_id", "local-bundle")),
            "record_id": str(data.get("record_type", resource)),
            "generated_at": "fixture-time",
        },
        next_cursor=cursor,
    )


def _forbidden_read_model_resource(resource: str, role: str) -> bool:
    return not read_model_allowed(role, resource)


def _apply_read_model_filters(resource: str, data: dict[str, Any], filters: dict[str, str]) -> dict[str, Any]:
    if not filters:
        return data
    filtered = json.loads(json.dumps(data))
    if resource == "risk-debt" and "status" in filters:
        expected = filters["status"]
        items = filtered.get("items", [])
        if isinstance(items, list):
            filtered["items"] = [
                item for item in items
                if isinstance(item, dict) and str(item.get("status", "open")) == expected
            ]
            summary = filtered.setdefault("summary", {})
            if isinstance(summary, dict):
                summary["filtered_count"] = len(filtered["items"])
                summary["filter_status"] = expected
    if resource == "product-readiness" and "status" in filters:
        summary = filtered.setdefault("summary", {})
        if isinstance(summary, dict):
            summary["filter_status"] = filters["status"]
            summary["filter_match"] = summary.get("overall_status") == filters["status"]
    return filtered


def make_product_read_model_handler(readiness_dir: Path) -> type[BaseHTTPRequestHandler]:
    """Create a minimal REST handler backed by local product readiness artifacts."""
    root = readiness_dir

    class ProductReadModelHandler(BaseHTTPRequestHandler):
        server_version = "HATEProductReadModel/0.1"

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urlparse(self.path)
            resource = parsed.path.removeprefix("/v1/").strip("/")
            if not resource:
                resource = "product-readiness"
            query = parse_qs(parsed.query)
            role = query.get("role", ["developer"])[0]
            request_id = query.get("request_id", ["req_http"])[0]
            filters = {
                key.removeprefix("filter."): values[0]
                for key, values in query.items()
                if key.startswith("filter.") and values
            }
            stale_cache = query.get("stale_cache", ["false"])[0].lower() == "true"
            cursor = query.get("cursor", [None])[0]
            envelope = query_product_read_model(
                root,
                resource=resource,
                request_id=request_id,
                role=role,
                filters=filters,
                stale_cache=stale_cache,
                cursor=cursor,
            )
            status = envelope["errors"][0].get("http_status", 500) if envelope["errors"] else 200
            payload = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
            return

    return ProductReadModelHandler


def serve_product_read_model(readiness_dir: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Serve local product readiness artifacts through the hosted read model REST envelope."""
    if not readiness_dir.exists():
        raise ProductError(f"product readiness directory not found: {readiness_dir}", exit_code=2)
    handler = make_product_read_model_handler(readiness_dir)
    with ThreadingHTTPServer((host, port), handler) as server:
        server.serve_forever()


def generate_product_readiness(
    bundle_path: Path,
    trust_dir: Path,
    workflow_dir: Path,
    out_dir: Path,
    source_version: str | None = None,
) -> dict[str, Any]:
    """Generate P2/P3 product-readiness and enterprise advisory artifacts."""
    if not bundle_path.exists():
        raise ProductError(f"QEG bundle not found: {bundle_path}", exit_code=2)
    if not trust_dir.exists():
        raise ProductError(f"trust artifact directory not found: {trust_dir}", exit_code=2)
    if not workflow_dir.exists():
        raise ProductError(f"workflow artifact directory not found: {workflow_dir}", exit_code=2)

    out_dir.mkdir(parents=True, exist_ok=True)
    version = source_version or __version__
    bundle = _read_json(bundle_path)
    aete = _read_json(trust_dir / "aete-score.json")
    doctor = _read_json(trust_dir / "doctor-report.json")
    conformance = _read_optional_json(trust_dir / "adapter-conformance-report.json", _missing_conformance_report())
    alignment = _read_json(workflow_dir / "requirement-evidence-alignment.json")
    workflow_acceptance = _read_json(workflow_dir / "workflow-acceptance-record.json")
    input_gaps = _missing_product_input_refs(trust_dir, workflow_dir)

    run_id = str(bundle.get("metadata", {}).get("runId", ""))
    source_refs = [
        _stable_ref(bundle_path),
        _stable_ref(trust_dir / "aete-score.json"),
        _stable_ref(workflow_dir / "requirement-evidence-alignment.json"),
    ]
    product_metrics = _build_product_metrics(run_id, aete, doctor, conformance, alignment)
    pr_annotation = _build_pr_annotation_export(run_id, bundle, aete, alignment)
    artifact_budget = _build_artifact_budget_report(run_id, bundle)
    attestation = _build_attestation_report(run_id, bundle, aete, alignment)
    external_export = _build_external_export_report(run_id, bundle, alignment)
    error_catalog = _build_error_catalog()
    risk_debt = _build_enterprise_risk_debt(run_id, alignment)
    privacy_quarantine = _build_privacy_quarantine_report(run_id, bundle)
    hosted_index = _build_hosted_read_model_index(run_id, source_refs)
    domain_model = build_enterprise_domain_model(run_id, bundle)
    rbac_matrix = build_rbac_matrix_report(run_id)
    identity_connector = build_identity_connector_report(run_id, rbac_matrix)
    enterprise_connector = build_enterprise_connector_report(run_id)
    audit_event_log = build_audit_event_log(run_id, bundle)
    retention_governance = build_retention_governance_report(run_id, artifact_budget, domain_model)
    release_migration = _build_release_migration_report(run_id)
    entitlement = _build_entitlement_usage_report(run_id)
    docs_index = _build_customer_docs_index()
    incident = _build_incident_slo_report(run_id)
    adoption = _build_adoption_health_report(run_id)
    security_trust = _build_security_trust_packet(run_id)
    residency = _build_residency_deployment_report(run_id)
    roadmap = _build_roadmap_decision_report(run_id)
    accessibility = _build_accessibility_localization_report(run_id)
    commercial = _build_commercial_contract_report(run_id)
    assurance = _build_assurance_pack(run_id)
    support_bundle = _build_support_diagnostic_bundle(run_id, version, doctor, conformance, input_gaps)
    privacy_report = _build_privacy_telemetry_report(run_id)
    governance_report = _build_governance_portfolio_report(run_id)
    dashboard_html = _build_dashboard_html(run_id, product_metrics, alignment)
    product_readiness = _build_product_readiness_report(
        run_id=run_id,
        version=version,
        source_refs=source_refs,
        aete=aete,
        doctor=doctor,
        alignment=alignment,
        workflow_acceptance=workflow_acceptance,
        product_metrics=product_metrics,
        generated_refs=_product_artifact_refs(),
        input_gaps=input_gaps,
    )
    dashboard_view_model = _build_dashboard_view_model(run_id, bundle, product_metrics, alignment, artifact_budget, product_readiness)
    release_candidate = build_release_candidate_pack(run_id, ["product-readiness-report.json", *_product_artifact_refs()])
    shipyard = _build_shipyard_evidence(run_id, product_readiness)

    _write_json(out_dir / "product-readiness-report.json", product_readiness)
    _write_json(out_dir / "pr-annotation-export.json", pr_annotation)
    _write_json(out_dir / "artifact-budget-report.json", artifact_budget)
    _write_json(out_dir / "attestation-report.json", attestation)
    _write_json(out_dir / "external-export-report.json", external_export)
    _write_json(out_dir / "product-error-catalog.json", error_catalog)
    _write_json(out_dir / "enterprise-risk-debt-register.json", risk_debt)
    _write_json(out_dir / "privacy-quarantine-report.json", privacy_quarantine)
    _write_json(out_dir / "hosted-read-model-index.json", hosted_index)
    _write_json(out_dir / "domain-model-report.json", domain_model)
    _write_json(out_dir / "rbac-matrix-report.json", rbac_matrix)
    _write_json(out_dir / "identity-connector-report.json", identity_connector)
    _write_json(out_dir / "enterprise-connector-report.json", enterprise_connector)
    _write_json(out_dir / "audit-event-log.json", audit_event_log)
    _write_json(out_dir / "retention-governance-report.json", retention_governance)
    _write_json(out_dir / "release-migration-report.json", release_migration)
    _write_json(out_dir / "entitlement-usage-report.json", entitlement)
    _write_json(out_dir / "enterprise-metrics-report.json", product_metrics)
    _write_json(out_dir / "customer-docs-index.json", docs_index)
    _write_json(out_dir / "incident-slo-report.json", incident)
    _write_json(out_dir / "adoption-health-report.json", adoption)
    _write_json(out_dir / "security-trust-packet.json", security_trust)
    _write_json(out_dir / "residency-deployment-report.json", residency)
    _write_json(out_dir / "roadmap-decision-record.json", roadmap)
    _write_json(out_dir / "accessibility-localization-report.json", accessibility)
    _write_json(out_dir / "commercial-contract-report.json", commercial)
    _write_json(out_dir / "audit-assurance-pack.json", assurance)
    _write_json(out_dir / "support-diagnostic-bundle.json", support_bundle)
    _write_json(out_dir / "privacy-telemetry-report.json", privacy_report)
    _write_json(out_dir / "governance-portfolio-report.json", governance_report)
    _write_json(out_dir / "dashboard-view-model.json", dashboard_view_model)
    _write_json(out_dir / "release-candidate-pack.json", release_candidate)
    _write_json(out_dir / "shipyard-run-evidence.json", shipyard)
    (out_dir / "dashboard-report.html").write_text(dashboard_html, encoding="utf-8")

    return {
        "product_status": product_readiness["summary"]["overall_status"],
        "exit_code": 0,
        "generated": ["product-readiness-report.json", *_product_artifact_refs(), "shipyard-run-evidence.json"],
        "prg_coverage": product_readiness["summary"]["prg_coverage"],
        "publish_gate_override": False,
        "release_gate_override": False,
    }


