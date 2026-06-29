"""Migration compatibility checks for HATE."""

from .compatibility import (
    MigrationCompatibilityDecision,
    build_migration_compatibility_report,
    evaluate_migration_compatibility,
)
from .legal_hold import build_legal_hold_migration_report, evaluate_legal_hold_migration

__all__ = [
    "MigrationCompatibilityDecision",
    "build_legal_hold_migration_report",
    "build_migration_compatibility_report",
    "evaluate_legal_hold_migration",
    "evaluate_migration_compatibility",
]
