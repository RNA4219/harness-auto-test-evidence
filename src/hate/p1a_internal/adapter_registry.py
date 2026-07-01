"""P1A adapter registry and manifest construction."""

from __future__ import annotations

from typing import Any

from hate import __version__
from hate.p1a_io import _stable_hash

SCHEMA_VERSION = "HATE/v1"
ADAPTER_REGISTRY_VERSION = "adapter-registry-2026-06-29"


def _build_adapter_registry() -> dict[str, Any]:
    adapters = [
        _adapter_manifest("context-github-actions", "GitHub Actions context", "context", ["github-context.json"], ["run"]),
        _adapter_manifest("context-generic-ci", "Generic CI context", "context", ["ci-context.json", "generic-ci-context.json"], ["run"]),
        _adapter_manifest("test-result-junit", "JUnit XML", "test-result", ["junit.xml"], ["test_result"], retry=True),
        _adapter_manifest("test-result-pytest-json", "pytest JSON", "test-result", ["pytest.json"], ["test_result"], flaky_history=True),
        _adapter_manifest("test-result-vitest-json", "Vitest JSON", "test-result", ["vitest.json"], ["test_result"], retry=True, matrix=True),
        _adapter_manifest("test-result-jest-json", "Jest JSON", "test-result", ["jest.json"], ["test_result"], matrix=True),
        _adapter_manifest("coverage-cobertura", "Cobertura XML", "coverage", ["cobertura.xml"], ["coverage_record"], coverage_context=True),
        _adapter_manifest("coverage-lcov", "LCOV", "coverage", ["lcov.info"], ["coverage_record"]),
        _adapter_manifest("coverage-coveragepy-json", "coverage.py JSON", "coverage", ["coverage.json"], ["coverage_record"], coverage_context=True),
        _adapter_manifest("coverage-gcov-json", "Gcov JSON", "coverage", ["gcov.json"], ["coverage_record"]),
        _adapter_manifest("coverage-jacoco", "JaCoCo HTML artifact", "coverage", ["jacoco-html/"], ["coverage_record"]),
        _adapter_manifest("artifact-manifest", "Artifact manifest", "artifact", ["artifact-manifest.json"], ["artifact"]),
        _adapter_manifest("browser-playwright-artifacts", "Browser Playwright artifacts", "artifact", ["playwright-report/"], ["artifact"]),
        _adapter_manifest("static-sarif", "SARIF", "static-analysis", ["sarif.json"], ["finding"]),
        _adapter_manifest("contract-pact", "Pact JSON", "contract", ["pact.json"], ["contract_evidence"]),
        _adapter_manifest("mutation-stryker", "Stryker JSON", "mutation", ["stryker.json"], ["mutation_evidence"]),
        _adapter_manifest("export-qeg-bundle", "QEG bundle export", "upstream", ["qeg-bundle.json"], ["bundle"], artifact_hash=True, redaction=True),
        _adapter_manifest("export-qeg-report", "QEG report export", "upstream", ["qeg-export-report.json"], ["export_report"], artifact_hash=True),
    ]
    by_type: dict[str, int] = {}
    for adapter in adapters:
        by_type[adapter["adapter_type"]] = by_type.get(adapter["adapter_type"], 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "adapter_registry",
        "registry_version": ADAPTER_REGISTRY_VERSION,
        "adapters": adapters,
        "summary": {
            "adapter_count": len(adapters),
            "by_type": by_type,
            "all_have_required_manifest_fields": all(_adapter_manifest_is_complete(adapter) for adapter in adapters),
        },
        "source_refs": ["docs/process/ADAPTER_SDK_CONTRACT.md", "docs/process/P1A_TRUST_HARDENING_IMPLEMENTATION_CONTRACT.md"],
        "release_gate_override": False,
        "publish_gate_override": False,
    }


def _adapter_manifest(
    adapter_id: str,
    name: str,
    adapter_type: str,
    input_formats: list[str],
    output_record_types: list[str],
    *,
    retry: bool = False,
    matrix: bool = False,
    flaky_history: bool = False,
    coverage_context: bool = False,
    artifact_hash: bool = False,
    redaction: bool = False,
) -> dict[str, Any]:
    fixture_id = adapter_id.replace("_", "-")
    return {
        "adapter_id": adapter_id,
        "name": name,
        "version": __version__,
        "adapter_type": adapter_type,
        "kind": adapter_type,
        "input_formats": input_formats,
        "output_record_types": output_record_types,
        "capabilities": {
            "flaky": flaky_history,
            "retry": retry,
            "matrix": matrix,
            "artifact_hash": artifact_hash,
            "coverage_context": coverage_context,
            "redaction": redaction,
            "source_refs": True,
        },
        "capability": {
            "execution_result": adapter_type == "test-result",
            "retry": retry,
            "matrix": matrix,
            "flaky_history": flaky_history,
            "coverage_context": coverage_context,
            "artifact_hash": artifact_hash,
            "source_refs": True,
            "redaction": redaction,
        },
        "known_limits": _adapter_known_limits(adapter_type, coverage_context, matrix, flaky_history),
        "fixtures": [f"fixtures/adapters/{fixture_id}"],
        "conformance_fixtures": ["valid-minimal", "malformed", "missing-required"],
        "profile_support": {
            "default": "supported",
            "strict": "supported" if adapter_type in {"test-result", "coverage", "context"} else "partial",
            "release": "supported" if adapter_type in {"test-result", "coverage", "context"} else "partial",
        },
    }


def _adapter_known_limits(adapter_type: str, coverage_context: bool, matrix: bool, flaky_history: bool) -> list[str]:
    limits: list[str] = []
    if adapter_type == "coverage" and not coverage_context:
        limits.append("coverage context is unavailable unless the source format carries per-test context")
    if adapter_type == "test-result" and not matrix:
        limits.append("matrix values are preserved only when present in source records")
    if adapter_type == "test-result" and not flaky_history:
        limits.append("flaky history requires explicit source fields or future baseline-history input")
    return limits


def _adapter_manifest_is_complete(adapter: dict[str, Any]) -> bool:
    required = ["adapter_id", "name", "version", "adapter_type", "input_formats", "output_record_types", "capabilities", "fixtures", "profile_support"]
    for field in required:
        value = adapter.get(field)
        if value is None or value == "" or value == []:
            return False
    return True


def _build_adapter_capability_manifest() -> dict[str, Any]:
    registry = _build_adapter_registry()
    upstream = next(adapter for adapter in registry["adapters"] if adapter["adapter_id"] == "export-qeg-bundle")
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "adapter_capability_manifest",
        "adapter_id": "hate-p0b-qeg-bundle",
        "adapter_version": __version__,
        "kind": "upstream",
        "input_formats": upstream["input_formats"],
        "output_record_types": [
            "aete_score",
            "doctor_report",
            "artifact_resolution",
            "adapter_conformance",
            "replay_report",
            "compare_report",
            "explain_report",
            "recommendation_report",
        ],
        "capability": upstream["capability"],
        "known_limits": upstream["known_limits"],
        "conformance_fixtures": [
            "qeg_fixture",
            "path",
            "artifact_safety",
            "schema",
            "profile",
        ],
        "profile_support": {
            "default": "supported",
            "strict": "partial",
            "release": "partial",
        },
        "registry_ref": "adapter-registry.json",
    }
