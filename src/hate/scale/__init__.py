"""Scale fixture generation and validation."""

from hate.scale.fixtures import (
    ScaleFixtureManifest,
    ScaleFixtureSpec,
    ScaleValidationResult,
    build_scale_performance_report,
    generate_scale_fixture_manifest,
    validate_scale_fixture_manifest,
)
from hate.scale.performance_budget import (
    PerformanceBudgetInput,
    evaluate_performance_budget,
)
from hate.scale.benchmark_catalog import (
    build_benchmark_catalog_report,
    evaluate_benchmark_catalog_fixture,
)

__all__ = [
    "ScaleFixtureManifest",
    "ScaleFixtureSpec",
    "ScaleValidationResult",
    "build_scale_performance_report",
    "generate_scale_fixture_manifest",
    "validate_scale_fixture_manifest",
    "PerformanceBudgetInput",
    "build_benchmark_catalog_report",
    "evaluate_benchmark_catalog_fixture",
    "evaluate_performance_budget",
]
