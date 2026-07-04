"""Third-wave portfolio readiness evaluations for HATE-GAP-041..048."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .governance import (
    governance_diagnostic_summary,
    governance_diagnostics,
    governance_findings,
    governance_summary,
    normalize_governance_config,
)
from .recurring_eval import (
    normalize_recurring_eval_config,
    recurring_eval_diagnostic_summary,
    recurring_eval_diagnostics,
    recurring_eval_findings,
    recurring_eval_summary,
)
from .rollout_adoption import (
    normalize_rollout_config,
    rollout_diagnostic_summary,
    rollout_diagnostics,
    rollout_findings,
    rollout_summary,
)
from .security_procurement import (
    normalize_procurement_config,
    procurement_diagnostic_summary,
    procurement_diagnostics,
    procurement_findings,
    procurement_summary,
)
from .value_measurement import (
    normalize_value_config,
    value_diagnostic_summary,
    value_diagnostics,
    value_findings,
    value_summary,
)

@dataclass(frozen=True)
class PortfolioFinding:
    code: str
    severity: str
    message: str
    sourceRef: str
    readiness_effect: str = "hold"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "sourceRef": self.sourceRef,
            "readiness_effect": self.readiness_effect,
        }


Rule = Callable[[dict[str, Any], str], list[PortfolioFinding]]


def evaluate_rollout_adoption_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_fixture(payload, build_rollout_adoption_report, "rollout-adoption-fixture")


def evaluate_provider_integration_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_fixture(payload, build_provider_integration_report, "provider-integration-fixture")


def evaluate_runner_dialect_coverage_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_fixture(payload, build_runner_dialect_coverage_report, "runner-dialect-coverage-fixture")


def evaluate_recurring_real_repo_eval_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_fixture(payload, build_recurring_real_repo_eval_report, "recurring-real-repo-eval-fixture")


def evaluate_governance_review_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_fixture(payload, build_governance_review_report, "governance-review-fixture")


def evaluate_security_procurement_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_fixture(payload, build_security_procurement_report, "security-procurement-fixture")


def evaluate_value_measurement_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_fixture(payload, build_value_measurement_report, "value-measurement-fixture")


def evaluate_developer_experience_fixture(payload: dict[str, Any]) -> dict[str, Any]:
    return _evaluate_fixture(payload, build_developer_experience_report, "developer-experience-fixture")


def build_rollout_adoption_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "rollout-adoption-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    config = normalize_rollout_config(input_data.get("rollout_config", input_data))
    diagnostics = rollout_diagnostics(config)
    report = _build_report(
        record_type="rollout-adoption-report",
        report_id=report_id,
        config_key="rollout_config",
        config=config,
        source_refs=source_refs or input_data.get("sourceRefs") or ["rollout-adoption"],
        summary={**rollout_summary(config), **rollout_diagnostic_summary(diagnostics)},
        findings=rollout_findings(config, diagnostics, _first_source(source_refs, input_data, "rollout-adoption")),
    )
    report["rollout_diagnostics"] = diagnostics
    return report


def build_provider_integration_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "provider-integration-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    config = _normalize_provider_config(input_data.get("provider_config", input_data))
    diagnostics = _provider_diagnostics(config)
    report = _build_report(
        record_type="provider-integration-report",
        report_id=report_id,
        config_key="provider_config",
        config=config,
        source_refs=source_refs or input_data.get("sourceRefs") or ["provider-integration"],
        summary={**_provider_summary(config), **_provider_diagnostic_summary(diagnostics)},
        findings=_provider_findings(config, diagnostics, _first_source(source_refs, input_data, "provider-integration")),
    )
    report["provider_diagnostics"] = diagnostics
    return report


def build_runner_dialect_coverage_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "runner-dialect-coverage-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    config = _normalize_runner_config(input_data.get("runner_config", input_data))
    diagnostics = _runner_diagnostics(config)
    report = _build_report(
        record_type="runner-dialect-coverage-report",
        report_id=report_id,
        config_key="runner_config",
        config=config,
        source_refs=source_refs or input_data.get("sourceRefs") or ["runner-dialect-coverage"],
        summary={**_runner_summary(config), **_runner_diagnostic_summary(diagnostics)},
        findings=_runner_findings(config, diagnostics, _first_source(source_refs, input_data, "runner-dialect-coverage")),
    )
    report["results"] = _runner_results(config)
    report["runner_diagnostics"] = diagnostics
    return report


def build_recurring_real_repo_eval_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "recurring-real-repo-eval-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    config = normalize_recurring_eval_config(input_data.get("evaluation_config", input_data))
    diagnostics = recurring_eval_diagnostics(config)
    report = _build_report(
        record_type="recurring-real-repo-eval-report",
        report_id=report_id,
        config_key="evaluation_config",
        config=config,
        source_refs=source_refs or input_data.get("sourceRefs") or ["recurring-real-repo-eval"],
        summary={**recurring_eval_summary(config), **recurring_eval_diagnostic_summary(diagnostics)},
        findings=recurring_eval_findings(config, diagnostics, _first_source(source_refs, input_data, "recurring-real-repo-eval")),
    )
    report["recurring_eval_diagnostics"] = diagnostics
    return report


def build_governance_review_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "governance-review-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    config = normalize_governance_config(input_data.get("governance_config", input_data))
    diagnostics = governance_diagnostics(config)
    report = _build_report(
        record_type="governance-review-report",
        report_id=report_id,
        config_key="governance_config",
        config=config,
        source_refs=source_refs or input_data.get("sourceRefs") or ["governance-review"],
        summary={**governance_summary(config), **governance_diagnostic_summary(diagnostics)},
        findings=governance_findings(config, diagnostics, _first_source(source_refs, input_data, "governance-review")),
    )
    report["governance_diagnostics"] = diagnostics
    return report


def build_security_procurement_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "security-procurement-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    config = normalize_procurement_config(input_data.get("procurement_config", input_data))
    diagnostics = procurement_diagnostics(config)
    report = _build_report(
        record_type="security-procurement-report",
        report_id=report_id,
        config_key="procurement_config",
        config=config,
        source_refs=source_refs or input_data.get("sourceRefs") or ["security-procurement"],
        summary={**procurement_summary(config), **procurement_diagnostic_summary(diagnostics)},
        findings=procurement_findings(config, diagnostics, _first_source(source_refs, input_data, "security-procurement")),
    )
    report["procurement_diagnostics"] = diagnostics
    return report


def build_value_measurement_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "value-measurement-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    config = normalize_value_config(input_data.get("value_config", input_data))
    diagnostics = value_diagnostics(config)
    report = _build_report(
        record_type="value-measurement-report",
        report_id=report_id,
        config_key="value_config",
        config=config,
        source_refs=source_refs or input_data.get("sourceRefs") or ["value-measurement"],
        summary={**value_summary(config), **value_diagnostic_summary(diagnostics)},
        findings=value_findings(config, diagnostics, _first_source(source_refs, input_data, "value-measurement")),
    )
    report["value_diagnostics"] = diagnostics
    return report


def build_developer_experience_report(
    input_data: dict[str, Any],
    *,
    report_id: str = "developer-experience-report",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    config = _normalize_dx_config(input_data.get("dx_config", input_data))
    diagnostics = _dx_diagnostics(config)
    report = _build_report(
        record_type="developer-experience-report",
        report_id=report_id,
        config_key="dx_config",
        config=config,
        source_refs=source_refs or input_data.get("sourceRefs") or ["developer-experience"],
        summary={**_dx_summary(config), **_dx_diagnostic_summary(diagnostics)},
        findings=_dx_findings(config, diagnostics, _first_source(source_refs, input_data, "developer-experience")),
    )
    report["dx_diagnostics"] = diagnostics
    return report


def _evaluate_fixture(payload: dict[str, Any], builder: Callable[..., dict[str, Any]], fallback_id: str) -> dict[str, Any]:
    input_data = payload.get("input", {})
    report = builder(
        input_data,
        report_id=str(payload.get("fixture_id") or fallback_id),
        source_refs=[str(payload.get("fixture_id") or "fixture")],
    )
    first_finding = report["findings"][0] if report["findings"] else {}
    return {
        "status": report["overall_status"],
        "finding_code": first_finding.get("code", ""),
        "readiness_effect": report["readiness_effect"],
        "report": report,
    }


def _build_report(
    *,
    record_type: str,
    report_id: str,
    config_key: str,
    config: dict[str, Any],
    source_refs: list[str],
    summary: dict[str, Any],
    findings: list[PortfolioFinding],
) -> dict[str, Any]:
    status = "hold" if findings else "pass"
    return {
        "schema_version": "HATE/v1",
        "record_type": record_type,
        "report_id": report_id,
        "overall_status": status,
        "readiness_effect": "hold" if findings else "none",
        config_key: config,
        "findings": [finding.to_dict() for finding in findings],
        "summary": {**summary, "finding_count": len(findings)},
        "sourceRefs": sorted({str(ref) for ref in source_refs}),
    }


def _first_source(source_refs: list[str] | None, input_data: dict[str, Any], fallback: str) -> str:
    refs = source_refs or input_data.get("sourceRefs") or [fallback]
    return str(refs[0]) if refs else fallback


def _finding(code: str, message: str, source_ref: str, severity: str = "high") -> PortfolioFinding:
    return PortfolioFinding(code=code, severity=severity, message=message, sourceRef=source_ref)


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value if str(item)] if isinstance(value, list) else []


def _normalize_provider_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw or {})
    return {
        "providers": _list_of_dicts(config.get("providers", [])),
        "required_providers": _strings(config.get("required_providers", [])),
        "permission_matrix": _list_of_dicts(config.get("permission_matrix", [])),
        "artifact_policies": _list_of_dicts(config.get("artifact_policies", [])),
        "annotation_policies": _list_of_dicts(config.get("annotation_policies", [])),
        "rerun_policies": _list_of_dicts(config.get("rerun_policies", [])),
        "minimum_permissions_declared": bool(config.get("minimum_permissions_declared", False)),
        "ambiguous_identity_detected": bool(config.get("ambiguous_identity_detected", False)),
        "overbroad_permission_detected": bool(config.get("overbroad_permission_detected", False)),
        "raw_token_present": bool(config.get("raw_token_present", False)),
    }


def _provider_summary(config: dict[str, Any]) -> dict[str, Any]:
    covered = {provider.get("provider") for provider in config["providers"] if provider.get("support_state") in {"supported", "partial"}}
    missing = sorted(set(config["required_providers"]) - covered)
    return {
        "provider_count": len(config["providers"]),
        "required_provider_count": len(config["required_providers"]),
        "missing_required_providers": missing,
        "minimum_permissions_declared": config["minimum_permissions_declared"],
        "permission_rule_count": len(config["permission_matrix"]),
        "artifact_policy_count": len(config["artifact_policies"]),
        "annotation_policy_count": len(config["annotation_policies"]),
        "rerun_policy_count": len(config["rerun_policies"]),
    }


def _provider_diagnostics(config: dict[str, Any]) -> dict[str, Any]:
    provider_names = [str(provider.get("provider") or "") for provider in config["providers"] if provider.get("provider")]
    provider_set = set(provider_names)
    permission_providers = {str(rule.get("provider") or "") for rule in config["permission_matrix"] if rule.get("provider")}
    artifact_providers = {str(policy.get("provider") or "") for policy in config["artifact_policies"] if policy.get("provider")}
    annotation_providers = {str(policy.get("provider") or "") for policy in config["annotation_policies"] if policy.get("provider")}
    rerun_providers = {str(policy.get("provider") or "") for policy in config["rerun_policies"] if policy.get("provider")}
    overbroad_permissions = sorted(
        str(rule.get("provider") or "provider")
        for rule in config["permission_matrix"]
        if rule.get("scope") in {"admin", "write_all", "*"} or bool(rule.get("write_repository"))
    )
    missing_permission_source_refs = sorted(
        str(rule.get("provider") or "provider")
        for rule in config["permission_matrix"]
        if not rule.get("sourceRef")
    )
    unsafe_artifacts = sorted(
        str(policy.get("provider") or "provider")
        for policy in config["artifact_policies"]
        if not policy.get("redaction") or not policy.get("retention_days") or policy.get("allows_raw_logs")
    )
    unsafe_annotations = sorted(
        str(policy.get("provider") or "provider")
        for policy in config["annotation_policies"]
        if not policy.get("sourceRef") or not policy.get("stable_target") or policy.get("can_post_secret")
    )
    nondeterministic_reruns = sorted(
        str(policy.get("provider") or "provider")
        for policy in config["rerun_policies"]
        if not policy.get("attempt_identity") or not policy.get("idempotency_key") or not policy.get("preserves_previous_attempt")
    )
    return {
        "duplicate_providers": sorted({item for item in provider_names if provider_names.count(item) > 1}),
        "providers_missing_permission_policy": sorted(provider_set - permission_providers),
        "providers_missing_artifact_policy": sorted(provider_set - artifact_providers),
        "providers_missing_annotation_policy": sorted(provider_set - annotation_providers),
        "providers_missing_rerun_policy": sorted(provider_set - rerun_providers),
        "overbroad_permission_providers": sorted(set(overbroad_permissions)),
        "permission_source_ref_missing_providers": missing_permission_source_refs,
        "unsafe_artifact_policy_providers": unsafe_artifacts,
        "unsafe_annotation_policy_providers": unsafe_annotations,
        "nondeterministic_rerun_providers": nondeterministic_reruns,
    }


def _provider_diagnostic_summary(diagnostics: dict[str, Any]) -> dict[str, Any]:
    return {
        "duplicate_provider_count": len(diagnostics["duplicate_providers"]),
        "missing_permission_policy_count": len(diagnostics["providers_missing_permission_policy"]),
        "missing_artifact_policy_count": len(diagnostics["providers_missing_artifact_policy"]),
        "missing_annotation_policy_count": len(diagnostics["providers_missing_annotation_policy"]),
        "missing_rerun_policy_count": len(diagnostics["providers_missing_rerun_policy"]),
        "unsafe_artifact_policy_count": len(diagnostics["unsafe_artifact_policy_providers"]),
        "unsafe_annotation_policy_count": len(diagnostics["unsafe_annotation_policy_providers"]),
        "nondeterministic_rerun_count": len(diagnostics["nondeterministic_rerun_providers"]),
    }


def _provider_findings(
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    source_ref: str,
) -> list[PortfolioFinding]:
    findings: list[PortfolioFinding] = []
    missing = _provider_summary(config)["missing_required_providers"]
    if missing:
        findings.append(_finding("provider_integration_required_provider_missing", f"Provider matrix missing: {', '.join(missing)}.", source_ref))
    for provider in config["providers"]:
        missing_fields = [
            key
            for key in ("commit_identity", "review_identity", "run_attempt", "artifact_lifetime", "annotation_target", "rerun_semantics")
            if not provider.get(key)
        ]
        if missing_fields:
            findings.append(_finding("provider_integration_identity_semantics_incomplete", f"{provider.get('provider', 'provider')} missing: {', '.join(missing_fields)}.", source_ref))
    if diagnostics["duplicate_providers"]:
        findings.append(_finding("provider_integration_duplicate_provider", "Provider matrix contains duplicate provider entries.", source_ref))
    if diagnostics["providers_missing_permission_policy"]:
        findings.append(_finding("provider_integration_permission_policy_missing", "Provider permission policy missing for one or more providers.", source_ref))
    if diagnostics["providers_missing_artifact_policy"]:
        findings.append(_finding("provider_integration_artifact_policy_missing", "Provider artifact retention/redaction policy missing.", source_ref))
    if diagnostics["providers_missing_annotation_policy"]:
        findings.append(_finding("provider_integration_annotation_policy_missing", "Provider annotation target policy missing.", source_ref))
    if diagnostics["providers_missing_rerun_policy"]:
        findings.append(_finding("provider_integration_rerun_policy_missing", "Provider rerun policy missing.", source_ref))
    if diagnostics["permission_source_ref_missing_providers"]:
        findings.append(_finding("provider_integration_permission_source_ref_missing", "Provider permission rules require sourceRef.", source_ref))
    if diagnostics["unsafe_artifact_policy_providers"]:
        findings.append(_finding("provider_integration_artifact_policy_unsafe", "Provider artifact policy must set retention and redaction and deny raw logs.", source_ref))
    if diagnostics["unsafe_annotation_policy_providers"]:
        findings.append(_finding("provider_integration_annotation_policy_unsafe", "Provider annotation policy must use stable targets and safe payloads.", source_ref))
    if diagnostics["nondeterministic_rerun_providers"]:
        findings.append(_finding("provider_integration_rerun_nondeterministic", "Provider rerun policy must preserve attempt identity and idempotency.", source_ref))
    if not config["minimum_permissions_declared"]:
        findings.append(_finding("provider_integration_minimum_permissions_missing", "Provider integrations must declare minimum permissions.", source_ref))
    if config["ambiguous_identity_detected"]:
        findings.append(_finding("provider_integration_ambiguous_identity_hard_dq", "Ambiguous provider identity must not become silent advisory output.", source_ref))
    if config["overbroad_permission_detected"] or diagnostics["overbroad_permission_providers"]:
        findings.append(_finding("provider_integration_overbroad_permission_denied", "Broad or admin provider permission is denied.", source_ref))
    if config["raw_token_present"]:
        findings.append(_finding("provider_integration_raw_token_denied", "Provider report must not expose raw provider tokens.", source_ref))
    return findings


def _normalize_runner_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw or {})
    return {
        "runner_families": _list_of_dicts(config.get("runner_families", [])),
        "dialects": _list_of_dicts(config.get("dialects", [])),
        "required_families": _strings(config.get("required_families", [])),
        "required_capabilities": _strings(config.get("required_capabilities", ["summary_counts", "failure_location", "duration", "retry_attempt", "stdout_noise_filter"])),
        "unsupported_capability_gap_detected": bool(config.get("unsupported_capability_gap_detected", False)),
        "claim_without_conformance_detected": bool(config.get("claim_without_conformance_detected", False)),
        "raw_log_retention_denied": bool(config.get("raw_log_retention_denied", False)),
    }


def _runner_summary(config: dict[str, Any]) -> dict[str, Any]:
    covered = {family.get("family") for family in config["runner_families"] if family.get("support_state") in {"supported", "partial"}}
    missing = sorted(set(config["required_families"]) - covered)
    return {
        "runner_family_count": len(config["runner_families"]),
        "dialect_count": len(config["dialects"]),
        "missing_required_families": missing,
        "required_capability_count": len(config["required_capabilities"]),
    }


def _runner_diagnostics(config: dict[str, Any]) -> dict[str, Any]:
    dialect_ids = [str(dialect.get("dialect") or dialect.get("id") or "") for dialect in config["dialects"] if dialect.get("dialect") or dialect.get("id")]
    required_capabilities = set(config["required_capabilities"])
    missing_capabilities = {}
    unsupported_capabilities = {}
    summary_mismatches = []
    missing_source_refs = []
    noisy_without_filter = []
    partial_parse_without_gap = []
    malformed_missing_negative = []
    for dialect in config["dialects"]:
        dialect_id = str(dialect.get("dialect") or dialect.get("id") or "dialect")
        capabilities = set(_strings(dialect.get("capabilities", [])))
        unsupported = set(_strings(dialect.get("unsupported_capabilities", [])))
        missing = sorted(required_capabilities - capabilities)
        if missing:
            missing_capabilities[dialect_id] = missing
        if unsupported:
            unsupported_capabilities[dialect_id] = sorted(unsupported)
        if not dialect.get("sourceRef"):
            missing_source_refs.append(dialect_id)
        expected_summary = dict(dialect.get("expected_summary", {}) or {})
        observed_summary = dict(dialect.get("observed_summary", {}) or {})
        if expected_summary and observed_summary and expected_summary != observed_summary:
            summary_mismatches.append(dialect_id)
        if dialect.get("noise_lines") and not dialect.get("noise_filter_ref"):
            noisy_without_filter.append(dialect_id)
        if dialect.get("parser_status") == "partial" and not dialect.get("capability_gap_ref"):
            partial_parse_without_gap.append(dialect_id)
        if not dialect.get("malformed_fixture_ref"):
            malformed_missing_negative.append(dialect_id)
    return {
        "duplicate_dialects": sorted({item for item in dialect_ids if dialect_ids.count(item) > 1}),
        "missing_capabilities_by_dialect": missing_capabilities,
        "unsupported_capabilities_by_dialect": unsupported_capabilities,
        "summary_mismatch_dialects": sorted(summary_mismatches),
        "missing_source_ref_dialects": sorted(missing_source_refs),
        "noisy_without_filter_dialects": sorted(noisy_without_filter),
        "partial_parse_without_gap_dialects": sorted(partial_parse_without_gap),
        "malformed_fixture_missing_dialects": sorted(malformed_missing_negative),
    }


def _runner_diagnostic_summary(diagnostics: dict[str, Any]) -> dict[str, Any]:
    return {
        "duplicate_dialect_count": len(diagnostics["duplicate_dialects"]),
        "missing_capability_dialect_count": len(diagnostics["missing_capabilities_by_dialect"]),
        "unsupported_capability_dialect_count": len(diagnostics["unsupported_capabilities_by_dialect"]),
        "summary_mismatch_count": len(diagnostics["summary_mismatch_dialects"]),
        "missing_source_ref_dialect_count": len(diagnostics["missing_source_ref_dialects"]),
        "noisy_without_filter_count": len(diagnostics["noisy_without_filter_dialects"]),
        "partial_parse_without_gap_count": len(diagnostics["partial_parse_without_gap_dialects"]),
        "malformed_fixture_missing_count": len(diagnostics["malformed_fixture_missing_dialects"]),
    }


def _runner_findings(
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    source_ref: str,
) -> list[PortfolioFinding]:
    findings: list[PortfolioFinding] = []
    missing = _runner_summary(config)["missing_required_families"]
    if missing:
        findings.append(_finding("runner_dialect_required_family_missing", f"Runner family coverage missing: {', '.join(missing)}.", source_ref))
    for dialect in config["dialects"]:
        if not dialect.get("conformance_fixture_ref"):
            findings.append(_finding("runner_dialect_conformance_fixture_missing", f"{dialect.get('dialect', 'dialect')} missing conformance fixture.", source_ref))
    if config["unsupported_capability_gap_detected"]:
        findings.append(_finding("runner_dialect_unsupported_capability_gap", "Unsupported runner output must emit a capability gap.", source_ref))
    if config["claim_without_conformance_detected"]:
        findings.append(_finding("runner_dialect_claim_without_conformance", "Runner support claim without conformance fixture blocks product-ready.", source_ref))
    if diagnostics["duplicate_dialects"]:
        findings.append(_finding("runner_dialect_duplicate_dialect", "Runner dialect matrix contains duplicate dialect ids.", source_ref))
    if diagnostics["missing_capabilities_by_dialect"]:
        findings.append(_finding("runner_dialect_required_capability_missing", "Runner dialect is missing required parser capabilities.", source_ref))
    if diagnostics["summary_mismatch_dialects"]:
        findings.append(_finding("runner_dialect_summary_mismatch", "Runner dialect observed summary differs from expected fixture summary.", source_ref))
    if diagnostics["missing_source_ref_dialects"]:
        findings.append(_finding("runner_dialect_source_ref_missing", "Runner dialect claims require sourceRef.", source_ref))
    if diagnostics["noisy_without_filter_dialects"]:
        findings.append(_finding("runner_dialect_noise_filter_missing", "Noisy runner output requires ignored-noise filter reference.", source_ref))
    if diagnostics["partial_parse_without_gap_dialects"]:
        findings.append(_finding("runner_dialect_partial_parse_gap_missing", "Partial parser support requires explicit capability gap ref.", source_ref))
    if diagnostics["malformed_fixture_missing_dialects"]:
        findings.append(_finding("runner_dialect_malformed_fixture_missing", "Runner dialect requires malformed negative fixture.", source_ref))
    if config["raw_log_retention_denied"]:
        findings.append(_finding("runner_dialect_raw_log_retention_denied", "Runner dialect report must not retain raw logs as evidence.", source_ref))
    return findings


def _runner_results(config: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for dialect in config["dialects"]:
        dialect_id = str(dialect.get("dialect") or dialect.get("id") or "")
        has_fixture = bool(dialect.get("conformance_fixture_ref"))
        results.append({
            "case_id": dialect_id or "dialect",
            "expected": {
                "dialect": dialect_id,
                "conformance_fixture_required": True,
                "summary": dict(dialect.get("expected_summary", {}) or {}),
            },
            "actual": {
                "dialect": dialect_id,
                "summary": dict(dialect.get("observed_summary", {}) or {}),
                "ignored_noise": _strings(dialect.get("ignored_noise", [])),
                "parser_status": str(dialect.get("parser_status") or ("parsed" if has_fixture else "unparsed")),
            },
            "passed": has_fixture and dict(dialect.get("expected_summary", {}) or {}) == dict(dialect.get("observed_summary", {}) or {}),
        })
    return results


def _normalize_dx_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw or {})
    return {
        "feedback_groups": _list_of_dicts(config.get("feedback_groups", [])),
        "local_explain_available": bool(config.get("local_explain_available", False)),
        "local_replay_available": bool(config.get("local_replay_available", False)),
        "ide_loop_available": bool(config.get("ide_loop_available", False)),
        "offline_safe_mode": bool(config.get("offline_safe_mode", False)),
        "suppression_controls": dict(config.get("suppression_controls", {}) or {}),
        "recommendation_quality_score": float(config.get("recommendation_quality_score", 0.0) or 0.0),
        "latency_ms": int(config.get("latency_ms", 0) or 0),
        "latency_budget_ms": int(config.get("latency_budget_ms", 5000) or 5000),
        "recommendation_actions": _strings(config.get("recommendation_actions", [])),
        "replay_command": str(config.get("replay_command", "") or ""),
        "explain_command": str(config.get("explain_command", "") or ""),
        "raw_secret_present": bool(config.get("raw_secret_present", False)),
        "broad_suppression_detected": bool(config.get("broad_suppression_detected", False)),
        "stable_deep_links": bool(config.get("stable_deep_links", False)),
    }


def _dx_summary(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "feedback_group_count": len(config["feedback_groups"]),
        "local_explain_available": config["local_explain_available"],
        "local_replay_available": config["local_replay_available"],
        "ide_loop_available": config["ide_loop_available"],
        "offline_safe_mode": config["offline_safe_mode"],
        "recommendation_quality_score": config["recommendation_quality_score"],
        "latency_ms": config["latency_ms"],
        "latency_budget_ms": config["latency_budget_ms"],
    }


def _dx_diagnostics(config: dict[str, Any]) -> dict[str, Any]:
    action_verbs = {"add", "modify", "remove", "rerun", "open", "link", "assign", "expire", "narrow", "split"}
    generic_actions = {"fix", "improve", "review", "check", "look", "handle", "ignore all"}
    missing_source_refs = [
        str(group.get("group_id") or group.get("deep_link") or "feedback-group")
        for group in config["feedback_groups"]
        if not group.get("sourceRef") and not group.get("sourceRefs")
    ]
    missing_explain_or_replay = [
        str(group.get("group_id") or group.get("deep_link") or "feedback-group")
        for group in config["feedback_groups"]
        if not group.get("explain_ref") or not group.get("replay_ref")
    ]
    generic_feedback = []
    for group in config["feedback_groups"]:
        fix_action = str(group.get("fix_action") or "").strip().lower()
        first_word = fix_action.split(" ", 1)[0] if fix_action else ""
        if fix_action in generic_actions or (first_word and first_word not in action_verbs):
            generic_feedback.append(str(group.get("group_id") or group.get("deep_link") or fix_action or "feedback-group"))
    suppression = config["suppression_controls"]
    suppression_scope = str(suppression.get("scope") or "")
    suppression_has_review = bool(suppression.get("reviewer") and suppression.get("rationale") and suppression.get("audit_ref"))
    return {
        "missing_source_ref_groups": sorted(missing_source_refs),
        "missing_explain_or_replay_groups": sorted(missing_explain_or_replay),
        "generic_feedback_groups": sorted(generic_feedback),
        "suppression_scope": suppression_scope,
        "suppression_has_review_record": suppression_has_review,
        "recommendation_actions_count": len(config["recommendation_actions"]),
        "command_loop_complete": bool(config["replay_command"] and config["explain_command"]),
        "latency_budget_exceeded": config["latency_ms"] > config["latency_budget_ms"],
    }


def _dx_diagnostic_summary(diagnostics: dict[str, Any]) -> dict[str, Any]:
    return {
        "missing_source_ref_group_count": len(diagnostics["missing_source_ref_groups"]),
        "missing_explain_or_replay_group_count": len(diagnostics["missing_explain_or_replay_groups"]),
        "generic_feedback_group_count": len(diagnostics["generic_feedback_groups"]),
        "recommendation_actions_count": diagnostics["recommendation_actions_count"],
        "command_loop_complete": diagnostics["command_loop_complete"],
    }


def _dx_findings(
    config: dict[str, Any],
    diagnostics: dict[str, Any],
    source_ref: str,
) -> list[PortfolioFinding]:
    findings: list[PortfolioFinding] = []
    for group in config["feedback_groups"]:
        missing = [key for key in ("fix_action", "risk_impact", "owner", "blocking_status", "deep_link") if not group.get(key)]
        if missing:
            findings.append(_finding("developer_experience_feedback_group_incomplete", f"PR/MR feedback group missing: {', '.join(missing)}.", source_ref))
    if not config["feedback_groups"]:
        findings.append(_finding("developer_experience_feedback_group_missing", "PR/MR feedback must group findings by fix action and risk.", source_ref))
    if not config["stable_deep_links"]:
        findings.append(_finding("developer_experience_deep_links_unstable", "Developer feedback requires stable deep links.", source_ref))
    if not config["local_explain_available"] or not config["local_replay_available"]:
        findings.append(_finding("developer_experience_local_loop_missing", "Local explain and replay must be available.", source_ref))
    if not config["ide_loop_available"] or not config["offline_safe_mode"]:
        findings.append(_finding("developer_experience_ide_offline_loop_missing", "Developer experience requires IDE loop and offline-safe mode evidence.", source_ref))
    if not config["suppression_controls"].get("owner") or not config["suppression_controls"].get("expiry_required"):
        findings.append(_finding("developer_experience_suppression_controls_incomplete", "Suppressions require owner and expiry.", source_ref))
    if config["suppression_controls"].get("scope") in {"global", "repo", "*"} or not diagnostics["suppression_has_review_record"]:
        findings.append(_finding("developer_experience_suppression_review_incomplete", "Suppressions require narrow scope, reviewer, rationale, and audit ref.", source_ref))
    if config["broad_suppression_detected"]:
        findings.append(_finding("developer_experience_broad_suppression_denied", "Broad suppression is denied.", source_ref))
    if config["recommendation_quality_score"] < 0.7:
        findings.append(_finding("developer_experience_recommendation_quality_low", "Recommendation quality score is below release threshold.", source_ref))
    if diagnostics["latency_budget_exceeded"]:
        findings.append(_finding("developer_experience_latency_budget_exceeded", "Developer feedback latency budget exceeded.", source_ref))
    if config["raw_secret_present"]:
        findings.append(_finding("developer_experience_raw_secret_denied", "Developer feedback must not expose raw secrets.", source_ref))
    if diagnostics["missing_source_ref_groups"]:
        findings.append(_finding("developer_experience_source_ref_missing", "Feedback groups must preserve sourceRefs.", source_ref))
    if diagnostics["missing_explain_or_replay_groups"] or not diagnostics["command_loop_complete"]:
        findings.append(_finding("developer_experience_explain_replay_link_missing", "Feedback groups and report need explain/replay links.", source_ref))
    if diagnostics["generic_feedback_groups"] or not config["recommendation_actions"]:
        findings.append(_finding("developer_experience_recommendation_action_weak", "Developer recommendations must be concrete action taxonomy entries.", source_ref))
    return findings
