from __future__ import annotations


IMPLEMENTED_GAP_EVIDENCE = {
    "HATE-GAP-001": {
        "runtime_module": "src/hate/runtime_worker.py",
        "tests": ["tests/test_runtime_worker.py"],
        "fixtures": [
            "fixtures/runtime/worker/successful-ingest/fixture.json",
            "fixtures/runtime/worker/retry-then-success/fixture.json",
            "fixtures/runtime/worker/cancel-running/fixture.json",
            "fixtures/runtime/worker/poison-message/fixture.json",
        ],
        "contract": "docs/process/HOSTED_WORKER_RUNTIME_CONTRACT.md",
    },
    "HATE-GAP-002": {
        "runtime_module": "src/hate/tenant_isolation.py",
        "tests": ["tests/test_tenant_isolation.py"],
        "fixtures": [
            "fixtures/enterprise/tenant/own-org-access/fixture.json",
            "fixtures/enterprise/tenant/cross-org-denied/fixture.json",
            "fixtures/enterprise/tenant/artifact-cross-access-denied/fixture.json",
            "fixtures/enterprise/tenant/cache-bleed-denied/fixture.json",
            "fixtures/enterprise/tenant/audit-cross-read-denied/fixture.json",
            "fixtures/enterprise/tenant/export-mixed-tenant-denied/fixture.json",
            "fixtures/enterprise/tenant/support-bundle-isolated/fixture.json",
            "fixtures/enterprise/tenant/telemetry-payload-denied/fixture.json",
        ],
        "contract": "docs/process/TENANT_ISOLATION_CONTRACT.md",
    },
    "HATE-GAP-003": {
        "runtime_module": "src/hate/api/rate_limit.py",
        "tests": ["tests/test_api_rate_limit.py"],
        "fixtures": [
            "fixtures/api/rate-limit/burst-within-quota/fixture.json",
            "fixtures/api/rate-limit/quota-exceeded/fixture.json",
            "fixtures/api/rate-limit/missing-tenant-scope/fixture.json",
            "fixtures/api/rate-limit/mutating-without-idempotency/fixture.json",
            "fixtures/api/rate-limit/abuse-burst-denied/fixture.json",
        ],
        "contract": "docs/process/API_REQUIREMENTS.md",
    },
    "HATE-GAP-004": {
        "runtime_module": "src/hate/entitlement.py",
        "tests": ["tests/test_entitlement.py"],
        "fixtures": [
            "fixtures/entitlement/team-ga-allowed/fixture.json",
            "fixtures/entitlement/enterprise-feature-denied/fixture.json",
            "fixtures/entitlement/local-first-non-gating/fixture.json",
            "fixtures/entitlement/precheck-override-denied/fixture.json",
            "fixtures/entitlement/qeg-override-denied/fixture.json",
        ],
        "contract": "docs/process/PACKAGING_ENTITLEMENT_CONTRACT.md",
    },
    "HATE-GAP-005": {
        "runtime_module": "src/hate/github_integration.py",
        "tests": ["tests/test_github_integration.py"],
        "fixtures": [
            "fixtures/github/pr-check-success/fixture.json",
            "fixtures/github/permission-denied/fixture.json",
            "fixtures/github/rerun-preserves-run-id-link/fixture.json",
            "fixtures/github/unsafe-artifact-redacted/fixture.json",
            "fixtures/github/broad-admin-permission-denied/fixture.json",
            "fixtures/github/unsafe-annotation-denied/fixture.json",
        ],
        "contract": "docs/process/GITHUB_INTEGRATION_CONTRACT.md",
    },
    "HATE-GAP-006": {
        "runtime_module": "src/hate/store/migration_rebuild.py",
        "tests": ["tests/test_store_migration_rebuild.py"],
        "fixtures": [
            "fixtures/store/migration/forward-compatible/fixture.json",
            "fixtures/store/migration/corrupt-index/fixture.json",
            "fixtures/store/migration/rollback-required/fixture.json",
            "fixtures/store/migration/version-skew-denied/fixture.json",
            "fixtures/store/migration/rebuild-checkpoint-hash-mismatch/fixture.json",
            "fixtures/store/migration/canonical-hash-changed/fixture.json",
        ],
        "contract": "docs/process/STORE_MIGRATION_INDEX_REBUILD_CONTRACT.md",
    },
    "HATE-GAP-007": {
        "runtime_module": "src/hate/adapters/corpus_manifest.py",
        "tests": ["tests/test_adapter_corpus_manifest.py"],
        "fixtures": [
            "fixtures/corpus/manifest/minimum-dialects/fixture.json",
            "fixtures/corpus/manifest/stale-fixture/fixture.json",
        ],
        "contract": "docs/process/ADAPTER_CORPUS_MANIFEST.md",
    },
    "HATE-GAP-008": {
        "runtime_module": "src/hate/dashboard/state_report.py",
        "tests": [
            "tests/test_dashboard_state_report.py",
            "tests/test_dashboard_uat_states.py",
            "tests/test_dashboard_view_models.py",
        ],
        "fixtures": [
            "fixtures/dashboard/view-states/ready/fixture.json",
            "fixtures/dashboard/view-states/rbac-denied/fixture.json",
        ],
        "contract": "docs/process/UI_WORKFLOW_REQUIREMENTS.md",
    },
    "HATE-GAP-009": {
        "runtime_module": "src/hate/api/contract_report.py",
        "tests": [
            "tests/test_api_contract_report.py",
            "tests/test_api_read_model_contract.py",
            "tests/test_api_import_export_authz.py",
        ],
        "fixtures": [
            "fixtures/api/contract/paginated-evidence/fixture.json",
            "fixtures/api/contract/authz-leak-denied/fixture.json",
        ],
        "contract": "docs/process/HOSTED_READ_MODEL_API.md",
    },
    "HATE-GAP-010": {
        "runtime_module": "src/hate/support_ops/observability.py",
        "tests": ["tests/test_support_ops_observability.py"],
        "fixtures": [
            "fixtures/ops/observability/healthy-run/fixture.json",
            "fixtures/ops/observability/missing-trace-span/fixture.json",
            "fixtures/support-ops/observability/logs-valid/fixture.json",
            "fixtures/support-ops/observability/metrics-valid/fixture.json",
            "fixtures/support-ops/observability/alerts-valid/fixture.json",
            "fixtures/support-ops/observability/incident-trigger/fixture.json",
            "fixtures/support-ops/observability/raw-secret-log/fixture.json",
            "fixtures/support-ops/observability/missing-release-metric/fixture.json",
        ],
        "contract": "docs/process/SLO_INCIDENT_RESPONSE_CONTRACT.md",
    },
    "HATE-GAP-011": {
        "runtime_module": "src/hate/support_ops/diagnostics.py",
        "tests": ["tests/test_support_ops_diagnostics.py"],
        "fixtures": [
            "fixtures/support/diagnostics/safe-bundle/fixture.json",
            "fixtures/support/diagnostics/raw-secret-denied/fixture.json",
            "fixtures/support-ops/diagnostics/safe-diagnostic-bundle/fixture.json",
            "fixtures/support-ops/diagnostics/raw-artifact-in-bundle/fixture.json",
            "fixtures/support-ops/diagnostics/error-known/fixture.json",
            "fixtures/support-ops/diagnostics/remediation-mapped/fixture.json",
            "fixtures/support-ops/diagnostics/unknown-error-code/fixture.json",
            "fixtures/support-ops/diagnostics/missing-owner-action/fixture.json",
        ],
        "contract": "docs/process/PRODUCT_ERROR_TAXONOMY.md",
    },
    "HATE-GAP-012": {
        "runtime_module": "src/hate/evaluation/real_repo.py",
        "tests": ["tests/test_real_repo_evaluation.py"],
        "fixtures": [
            "fixtures/evaluation/real-repo/baseline-pass/fixture.json",
            "fixtures/evaluation/real-repo/regression-detected/fixture.json",
            "fixtures/evaluation/real-repo/timeout-recorded/fixture.json",
            "fixtures/evaluation/real-repo/subset-labeled/fixture.json",
        ],
        "contract": "docs/process/REAL_REPO_EVALUATION_CONTRACT.md",
    },
    "HATE-GAP-013": {
        "runtime_module": "src/hate/evaluation/agent_quality.py",
        "tests": ["tests/test_agent_quality.py"],
        "fixtures": [
            "fixtures/evaluation/agent-quality/oracle-backed/fixture.json",
            "fixtures/evaluation/agent-quality/avoidance-detected/fixture.json",
        ],
        "contract": "docs/process/PRODUCT_REQUIREMENTS_DEFINITION.md",
    },
    "HATE-GAP-014": {
        "runtime_module": "src/hate/adapters/family_packet.py",
        "tests": ["tests/test_adapter_family_packet.py"],
        "fixtures": [
            "fixtures/adapters/family/junit-pass/fixture.json",
            "fixtures/adapters/family/malformed-input/fixture.json",
        ],
        "contract": "docs/process/ADAPTER_CORPUS_MANIFEST.md",
    },
    "HATE-GAP-015": {
        "runtime_module": "src/hate/enterprise/control_packet.py",
        "tests": ["tests/test_enterprise_control_packet.py"],
        "fixtures": [
            "fixtures/enterprise/control/admin-allowed/fixture.json",
            "fixtures/enterprise/control/auditor-write-denied/fixture.json",
        ],
        "contract": "docs/process/ENTERPRISE_DOMAIN_MODEL.md",
    },
    "HATE-GAP-016": {
        "runtime_module": "src/hate/security/artifact_lifecycle.py",
        "tests": ["tests/test_artifact_lifecycle.py"],
        "fixtures": [
            "fixtures/artifacts/lifecycle/safe-retained/fixture.json",
            "fixtures/artifacts/lifecycle/legal-hold-delete-denied/fixture.json",
        ],
        "contract": "docs/process/PRIVACY_QUARANTINE_CONTRACT.md",
    },
    "HATE-GAP-017": {
        "runtime_module": "src/hate/deployment/topology.py",
        "tests": ["tests/test_deployment_topology.py"],
        "fixtures": [
            "fixtures/deployment/topology/local-single-node/fixture.json",
            "fixtures/deployment/topology/region-violation/fixture.json",
        ],
        "contract": "docs/process/DATA_RESIDENCY_DEPLOYMENT_CONTRACT.md",
    },
    "HATE-GAP-018": {
        "runtime_module": "src/hate/scale/benchmark_catalog.py",
        "tests": ["tests/test_benchmark_catalog.py"],
        "fixtures": [
            "fixtures/performance/benchmark/medium-repo-pass/fixture.json",
            "fixtures/performance/benchmark/budget-exceeded/fixture.json",
        ],
        "contract": "docs/process/SCALE_PERFORMANCE_REQUIREMENTS.md",
    },
    "HATE-GAP-019": {
        "runtime_module": "src/hate/release_channel.py",
        "tests": ["tests/test_release_channel.py"],
        "fixtures": [
            "fixtures/release/channel/minor-compatible/fixture.json",
            "fixtures/release/channel/breaking-without-migration/fixture.json",
        ],
        "contract": "docs/process/RELEASE_MIGRATION_POLICY.md",
    },
    "HATE-GAP-020": {
        "runtime_module": "src/hate/product_e2e.py",
        "tests": ["tests/test_product_e2e.py"],
        "fixtures": [
            "fixtures/e2e/developer-pr-loop/fixture.json",
            "fixtures/e2e/developer-pr-loop/parser-failure/fixture.json",
            "fixtures/e2e/qa-risk-review/fixture.json",
            "fixtures/e2e/qa-risk-review/no-oracle/fixture.json",
            "fixtures/e2e/release-review/fixture.json",
            "fixtures/e2e/release-review/qeg-invalid/fixture.json",
            "fixtures/e2e/admin-governance/fixture.json",
            "fixtures/e2e/admin-governance/rbac-denied/fixture.json",
            "fixtures/e2e/security-quarantine/fixture.json",
            "fixtures/e2e/security-quarantine/block/fixture.json",
            "fixtures/e2e/support-triage/fixture.json",
            "fixtures/e2e/support-triage/raw-artifact-denied/fixture.json",
        ],
        "contract": "docs/process/PRODUCT_E2E_UAT_CONTRACT.md",
    },
    "HATE-GAP-021": {
        "runtime_module": "src/hate/workflow_task_seed.py",
        "tests": ["tests/test_workflow_task_seed.py"],
        "fixtures": [
            "fixtures/workflow/task-seed/valid-packet/fixture.json",
            "fixtures/workflow/task-seed/missing-scope/fixture.json",
        ],
        "contract": "docs/process/WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md",
    },
    "HATE-GAP-022": {
        "runtime_module": "src/hate/workflow_acceptance.py",
        "tests": ["tests/test_workflow_acceptance.py"],
        "fixtures": [
            "fixtures/workflow/acceptance/done-linked/fixture.json",
            "fixtures/workflow/acceptance/done-without-record/fixture.json",
        ],
        "contract": "docs/process/WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md",
    },
    "HATE-GAP-023": {
        "runtime_module": "src/hate/workflow_evidence.py",
        "tests": ["tests/test_workflow_evidence.py"],
        "fixtures": [
            "fixtures/workflow/evidence/command-recorded/fixture.json",
            "fixtures/workflow/evidence/artifact-missing-hash/fixture.json",
        ],
        "contract": "docs/process/WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md",
    },
    "HATE-GAP-024": {
        "runtime_module": "src/hate/workflow_birdseye.py",
        "tests": ["tests/test_workflow_birdseye.py"],
        "fixtures": [
            "fixtures/workflow/birdseye/fresh-index/fixture.json",
            "fixtures/workflow/birdseye/stale-capsule/fixture.json",
        ],
        "contract": "docs/process/WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md",
    },
    "HATE-GAP-025": {
        "runtime_module": "src/hate/workflow_plugin.py",
        "tests": ["tests/test_workflow_plugin.py"],
        "fixtures": [
            "fixtures/workflow/plugin/cross-repo-valid/fixture.json",
            "fixtures/workflow/plugin/task-acceptance-drift/fixture.json",
        ],
        "contract": "docs/process/WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md",
    },
    "HATE-GAP-026": {
        "runtime_module": "src/hate/workflow_completion.py",
        "tests": ["tests/test_workflow_completion.py"],
        "fixtures": [
            "fixtures/workflow/completion/scope-safe/fixture.json",
            "fixtures/workflow/completion/overclaim-detected/fixture.json",
        ],
        "contract": "docs/process/WORKFLOW_COOKBOOK_OPERATION_CONTRACT.md",
    },
}
