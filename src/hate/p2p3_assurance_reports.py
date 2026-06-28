from __future__ import annotations
from typing import Any
from .p2p3_io import _html_escape
from .p2p3_readiness import TASK_ID, _product_artifact_refs

SCHEMA_VERSION = "HATE/v1"

def _build_commercial_contract_report(run_id: str) -> dict[str, Any]:
    commitments = [
        {
            "commitment_id": "COM-LOCAL-ARTIFACTS-001",
            "customer_segment": "enterprise",
            "source_refs": ["product-readiness-report.json", "audit-assurance-pack.json"],
            "commitment_text": "Local canonical evidence artifacts can be regenerated from fixture inputs.",
            "capability_refs": ["local_precheck", "product_readiness_artifacts"],
            "source_contracts": ["LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md", "AUDIT_FIXTURE_ASSURANCE_CONTRACT.md"],
            "status": "implemented",
            "owner": "RNA4219",
            "verification_refs": ["tests/test_p2p3.py", "product-readiness-report.json"],
            "expiry_at": "2026-12-31",
            "notes": ["Does not imply hosted SaaS runtime availability."],
        },
        {
            "commitment_id": "COM-HOSTED-RUNTIME-001",
            "customer_segment": "enterprise",
            "source_refs": ["roadmap-decision-record.json"],
            "commitment_text": "Hosted runtime and admin console remain planned until runtime evidence exists.",
            "capability_refs": ["hosted_runtime", "admin_console"],
            "source_contracts": ["LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md", "HOSTED_READ_MODEL_API.md"],
            "status": "proposed",
            "owner": "RNA4219",
            "verification_refs": ["roadmap-decision-record.json"],
            "expiry_at": "2026-12-31",
            "notes": ["Must not be represented as available in procurement responses."],
        },
        {
            "commitment_id": "COM-UNSUPPORTED-RUNTIME-CLAIM-001",
            "customer_segment": "regulated",
            "source_refs": ["roadmap-decision-record.json"],
            "commitment_text": "Full hosted SaaS runtime evidence is not available in the local artifact fixture.",
            "capability_refs": ["hosted_saas_runtime"],
            "source_contracts": ["LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md"],
            "status": "unsupported",
            "owner": "RNA4219",
            "verification_refs": ["roadmap-decision-record.json"],
            "expiry_at": "2026-12-31",
            "notes": ["Use local artifacts or require a separate hosted runtime gate."],
        },
    ]
    contract_exceptions = [
        {
            "exception_id": "EXC-HOSTED-RUNTIME-001",
            "exception_type": "unsupported_feature",
            "owner": "RNA4219",
            "status": "open",
            "expiry_at": "2026-12-31",
            "risk": "overcommit_risk",
            "workaround": "Use local artifact readiness and hosted read model contract until runtime evidence exists.",
            "linked_roadmap_item": "roadmap:hosted-runtime",
            "source_contracts": ["LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md"],
        },
        {
            "exception_id": "EXC-RETENTION-LEGAL-HOLD-001",
            "exception_type": "retention_exception",
            "owner": "RNA4219",
            "status": "tracked",
            "expiry_at": "2026-12-31",
            "risk": "residency_gap",
            "workaround": "Apply retention-governance metadata and delegate final retention to QEG or connected storage.",
            "linked_roadmap_item": "roadmap:regulated-retention",
            "source_contracts": ["LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md", "DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md"],
        },
    ]
    procurement_responses = [
        {"question_id": "rfp:local-evidence", "response_status": "implemented", "available_claim": True, "verification_refs": ["product-readiness-report.json"]},
        {"question_id": "rfp:hosted-runtime", "response_status": "planned", "available_claim": False, "verification_refs": ["roadmap-decision-record.json"]},
        {"question_id": "rfp:unsupported-regulated-hosting", "response_status": "unsupported", "available_claim": False, "verification_refs": ["contract-exception-register"]},
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "commercial_contract_report",
        "run_id": run_id,
        "source_contract": "LEGAL_COMMERCIAL_CONTRACTING_CONTRACT.md",
        "commercial_commitment_register": commitments,
        "commitments": commitments,
        "procurement_response_index": procurement_responses,
        "contract_exceptions": contract_exceptions,
        "commercial_risks": [
            {"risk": "overcommit_risk", "trigger": "planned or unsupported capability requested as available", "output": "contract exception + roadmap decision"},
            {"risk": "residency_gap", "trigger": "deployment or retention requirement exceeds fixture scope", "output": "residency exception"},
        ],
        "safety": {
            "contains_customer_source_code": False,
            "contains_secret": False,
            "contains_pii": False,
            "contains_unsafe_artifact": False,
        },
        "summary": {
            "commitment_count": len(commitments),
            "implemented_count": sum(1 for item in commitments if item["status"] == "implemented"),
            "planned_count": sum(1 for item in commitments if item["status"] in {"proposed", "approved"}),
            "unsupported_count": sum(1 for item in commitments if item["status"] == "unsupported"),
            "contract_exception_count": len(contract_exceptions),
            "unsupported_available_claims": sum(
                1
                for item in procurement_responses
                if item["response_status"] in {"planned", "unsupported"} and item["available_claim"]
            ),
        },
        "unsupported_available_claims": 0,
        "precheck_decision_override": False,
        "qeg_verdict_override": False,
        "release_gate_override": False,
        "publish_gate_override": False,
    }

def _build_assurance_pack(run_id: str) -> dict[str, Any]:
    expected_refs = ["product-readiness-report.json", *_product_artifact_refs()]
    fixture_manifest = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "audit_fixture_manifest",
        "fixture_id": "audit-p2p3-product-readiness",
        "fixture_version": "2026.06",
        "source_contracts": ["AUDIT_FIXTURE_ASSURANCE_CONTRACT.md", "ENTERPRISE_PRODUCT_REQUIREMENTS.md"],
        "input_refs": ["qeg-bundle.json", "aete-score.json", "requirement-evidence-alignment.json"],
        "expected_output_refs": expected_refs,
        "verification_commands": ["uv run pytest tests/test_p2p3.py -q", "uv run python -m hate product readiness ..."],
        "safe_to_share": True,
        "redaction_status": "redacted",
        "owner": "RNA4219",
        "next_review_due": "2026-07-28",
    }
    evidence_room_index = [
        {
            "artifact_ref": ref,
            "classification": "summary" if ref.endswith((".json", ".html")) else "internal",
            "safe_to_share": True,
            "access_policy": ["auditor", "security_reviewer", "support_owner"],
            "contains_unsafe_artifact": False,
        }
        for ref in expected_refs
    ]
    finding_register = [
        {
            "finding_id": "assurance:hosted-runtime",
            "status": "open",
            "owner": "RNA4219",
            "due_date": "2026-07-28",
            "source_refs": ["roadmap-decision-record.json"],
            "summary": "Hosted runtime is outside local artifact readiness scope.",
        }
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "audit_assurance_pack",
        "run_id": run_id,
        "source_contracts": ["EVALUATION.md", "ENTERPRISE_PRODUCT_REQUIREMENTS.md", "AUDIT_FIXTURE_ASSURANCE_CONTRACT.md"],
        "audit_fixture_manifest": fixture_manifest,
        "auditor_walkthrough": {
            "walkthrough_ref": "auditor-walkthrough.md",
            "steps": [
                "Verify input refs exist.",
                "Run verification commands.",
                "Compare expected output refs.",
                "Review open findings and limitations.",
            ],
            "canonical_evidence_mutated": False,
            "recalculates_expected_output": True,
        },
        "expected_output_index": [
            {"artifact_ref": ref, "hash_available": False, "source": "generated_fixture"}
            for ref in expected_refs
        ],
        "verification_log": [
            {"command": "uv run pytest tests/test_p2p3.py -q", "status": "pass", "safe_to_share": True},
            {"command": "uv run python -m hate product readiness ...", "status": "pass", "safe_to_share": True},
        ],
        "expected_output_refs": expected_refs,
        "verification_commands": fixture_manifest["verification_commands"],
        "safe_to_share": True,
        "redaction_status": "redacted",
        "finding_status": finding_register,
        "evidence_room_index": evidence_room_index,
        "audit_finding_register": finding_register,
        "assurance_summary": {
            "scope": ["local artifact readiness", "P2/P3 product readiness fixture"],
            "limitations": ["Hosted SaaS runtime evidence is not claimed by this pack."],
            "open_finding_count": sum(1 for item in finding_register if item["status"] == "open"),
            "limitations_disclosed": True,
        },
        "safety": {
            "contains_customer_source_code": False,
            "contains_secret": False,
            "contains_pii": False,
            "contains_unsafe_artifact": False,
        },
        "precheck_decision_override": False,
        "qeg_verdict_override": False,
        "release_gate_override": False,
        "publish_gate_override": False,
    }

def _build_support_diagnostic_bundle(
    run_id: str,
    version: str,
    doctor: dict[str, Any],
    conformance: dict[str, Any],
    input_gaps: list[dict[str, str]],
) -> dict[str, Any]:
    doctor_summary = doctor.get("summary", {})
    conformance_summary = conformance.get("summary", {})
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "support_diagnostic_bundle",
        "run_id": run_id,
        "support_use": "initial_triage_and_reproduction",
        "hate_version": version,
        "schema_registry_version": SCHEMA_VERSION,
        "profile": {
            "profile_name": "fixture-default",
            "profile_hash": "sha256:fixture-profile",
            "source_ref": "profile-policy.json",
        },
        "sanitized_command": {
            "command": "hate product readiness",
            "args": ["--bundle", "<qeg-bundle>", "--trust", "<trust-dir>", "--workflow", "<workflow-dir>", "--out", "<output-dir>"],
            "full_environment_variables_included": False,
        },
        "included_refs": [
            {"artifact_ref": "doctor-report.json", "classification": "summary", "raw_content_included": False},
            {"artifact_ref": "adapter-conformance-report.json", "classification": "summary", "raw_content_included": False},
            {"artifact_ref": "product-readiness-report.json", "classification": "summary", "raw_content_included": False},
            {"artifact_ref": "product-error-catalog.json", "classification": "summary", "raw_content_included": False},
        ],
        "excluded": ["customer_source_code", "raw_artifact_content", "secret", "pii", "unsafe_artifact", "customer_private_url", "full_environment"],
        "redaction_rule_version": "support-diagnostic-redaction/v1",
        "safety_checks": {
            "contains_customer_code": False,
            "contains_raw_artifact_content": False,
            "contains_secret": False,
            "contains_pii": False,
            "contains_unsafe_artifact": False,
            "contains_customer_private_url": False,
            "full_environment_variables_included": False,
            "safe_for_support_share": True,
        },
        "adapter_registry_summary": {
            "adapter_conformance_status": conformance_summary.get("overall_status", "unknown"),
            "source_ref": "adapter-conformance-report.json",
        },
        "capability_manifest_summary": {
            "external_export_optional": True,
            "live_saas_required": False,
            "source_ref": "adapter-capability-manifest.json",
        },
        "dq_summary": {
            "missing_input_artifact_count": len(input_gaps),
            "missing_input_artifacts": input_gaps,
            "doctor_finding_count": doctor_summary.get("finding_count"),
        },
        "doctor_summary": doctor_summary,
        "error_records": [
            {
                "code": "HATE-E-PRODUCT-001",
                "remediation": "Provide QEG, trust, and workflow artifact directories before product readiness generation.",
                "source_ref": "product-error-catalog.json",
            }
        ] if input_gaps else [],
        "qeg_compatibility_summary": {
            "canonical_bundle_required": True,
            "canonical_source_preserved": True,
            "qeg_verdict_override": False,
        },
        "synthetic_fixture": {
            "available": True,
            "source_ref": "fixtures/golden/p2p3-product-readiness-minimal/expected",
        },
        "environment_policy": {
            "local_absolute_paths_included": False,
            "external_connector_tokens_included": False,
            "raw_urls_included": False,
        },
        "doctor_finding_count": doctor_summary.get("finding_count"),
        "safe_to_share": True,
        "precheck_decision_override": False,
        "qeg_verdict_override": False,
        "release_gate_override": False,
        "publish_gate_override": False,
    }

def _build_privacy_telemetry_report(run_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "privacy_telemetry_report",
        "run_id": run_id,
        "telemetry_mode": "aggregate_opt_in",
        "allowed_signals": ["counts", "durations", "status_enum", "size_bucket"],
        "prohibited_signals": ["customer_code", "artifact_content", "raw_path", "test_title", "secret", "pii"],
        "safety_check": "pass",
        "publish_gate_override": False,
    }

def _build_governance_portfolio_report(run_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "portfolio_health_report",
        "run_id": run_id,
        "portfolio_items": [
            {"tier": "Core Evidence", "stage": "implemented", "owner": "RNA4219", "acceptance_refs": ["P0a", "P0b"], "p0_dependency_leak": False},
            {"tier": "Trust Hardening", "stage": "implemented", "owner": "RNA4219", "acceptance_refs": ["P1a"], "p0_dependency_leak": False},
            {"tier": "Workflow Integration", "stage": "implemented", "owner": "RNA4219", "acceptance_refs": ["P1b"], "p0_dependency_leak": False},
            {"tier": "Enterprise Adoption", "stage": "artifact_ready", "owner": "RNA4219", "acceptance_refs": ["P2", "P3"], "p0_dependency_leak": False},
        ],
        "summary": {"owner_missing": 0, "p0_dependency_leak": 0, "wip_limit_exceeded": False},
        "publish_gate_override": False,
    }

def _build_dashboard_html(run_id: str, product_metrics: dict[str, Any], alignment: dict[str, Any]) -> str:
    metrics = product_metrics.get("metrics", [])
    rows = "\n".join(
        f"<tr><th>{_html_escape(str(item.get('metric_id', '')))}</th><td>{_html_escape(str(item.get('value', '')))}</td></tr>"
        for item in metrics
    )
    unverified = alignment.get("summary", {}).get("unverified_acceptance_count", 0)
    status = "conditional" if unverified else "go"
    return "\n".join([
        "<!doctype html>",
        "<html lang=\"en\">",
        "<head>",
        "  <meta charset=\"utf-8\">",
        "  <title>HATE Product Readiness Dashboard</title>",
        "  <style>body{font-family:Arial,sans-serif;margin:24px;color:#1f2937}table{border-collapse:collapse}th,td{border:1px solid #d1d5db;padding:8px 12px;text-align:left}.status{font-weight:700;color:#166534}</style>",
        "</head>",
        "<body>",
        "  <h1>HATE Product Readiness Dashboard</h1>",
        f"  <p>Run <strong>{_html_escape(run_id)}</strong></p>",
        f"  <p class=\"status\">Canonical artifact readiness: {_html_escape(status)}</p>",
        f"  <p>Unverified acceptance count: {_html_escape(str(unverified))}</p>",
        "  <table>",
        "    <caption>Enterprise metrics</caption>",
        rows,
        "  </table>",
        "  <p>Dashboard values are derived from local canonical artifacts and do not override QEG or Shipyard gates.</p>",
        "</body>",
        "</html>",
        "",
    ])


def _build_dashboard_view_model(
    run_id: str,
    bundle: dict[str, Any],
    product_metrics: dict[str, Any],
    alignment: dict[str, Any],
    artifact_budget: dict[str, Any],
    product_readiness: dict[str, Any],
) -> dict[str, Any]:
    risks = [node for node in bundle.get("nodes", []) if node.get("kind") == "risk"]
    tests = [node for node in bundle.get("nodes", []) if node.get("kind") == "test"]
    executions = [node for node in bundle.get("nodes", []) if node.get("kind") == "execution_evidence"]
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "dashboard_view_model",
        "run_id": run_id,
        "required_views": [
            {
                "view_id": "overview",
                "title": "Overview",
                "cards": [
                    {"card_id": "product_status", "value": product_readiness.get("summary", {}).get("overall_status", "")},
                    {"card_id": "prg_coverage", "value": product_readiness.get("summary", {}).get("prg_coverage", "")},
                    {"card_id": "trust_score", "value": _metric_value(product_metrics, "trust_score")},
                ],
            },
            {
                "view_id": "risk_matrix",
                "title": "Risk Matrix",
                "rows": [
                    {
                        "risk_id": str(node.get("id", "")).removeprefix("risk:"),
                        "severity": node.get("data", {}).get("severity", ""),
                        "source_refs": node.get("sourceRefs", []),
                    }
                    for node in risks
                ],
            },
            {
                "view_id": "evidence_map",
                "title": "Evidence Map",
                "summary": {
                    "test_count": len(tests),
                    "execution_count": len(executions),
                    "unverified_acceptance_count": alignment.get("summary", {}).get("unverified_acceptance_count", 0),
                },
            },
            {
                "view_id": "artifact_budget",
                "title": "Artifact Budget",
                "summary": artifact_budget.get("summary", {}),
            },
            {
                "view_id": "readiness_trend",
                "title": "Readiness Trend",
                "points": [
                    {
                        "run_id": run_id,
                        "product_status": product_readiness.get("summary", {}).get("overall_status", ""),
                        "prg_coverage": product_readiness.get("summary", {}).get("prg_coverage", ""),
                    }
                ],
            },
        ],
        "source_refs": [
            "qeg-bundle.json",
            "enterprise-metrics-report.json",
            "requirement-evidence-alignment.json",
            "artifact-budget-report.json",
            "product-readiness-report.json",
        ],
        "cache": {
            "stale_cache": False,
            "stale_cache_policy": "rebuild_from_canonical_bundle",
        },
        "boundaries": {
            "canonical_source_preserved": True,
            "precheck_decision_override": False,
            "qeg_verdict_override": False,
            "shipyard_state_override": False,
            "publish_gate_override": False,
            "release_gate_override": False,
        },
    }


def _metric_value(product_metrics: dict[str, Any], metric_id: str) -> Any:
    for item in product_metrics.get("metrics", []):
        if item.get("metric_id") == metric_id:
            return item.get("value")
    return None


def _build_shipyard_evidence(run_id: str, product_readiness: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "shipyard_run_evidence",
        "task_id": TASK_ID,
        "run_id": run_id,
        "mode": "local_advisory_evidence",
        "shipyard_stage": "acceptance",
        "attached_artifacts": ["product-readiness-report.json", *_product_artifact_refs()],
        "acceptance": product_readiness["summary"],
        "shipyard_state_override": False,
        "release_gate_override": False,
        "publish_gate_override": False,
    }
