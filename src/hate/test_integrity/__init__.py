"""Test integrity detection package - HATE-PG-004A.

This package provides detectors for test integrity signals including:
- skip markers without justification
- xfail markers without expiry
- only/focus markers leaking into CI
- todo markers in release profile
"""

from .models import IntegrityFinding, TestIntegrityFinding, IntegritySignalType
from .skip_focus import detect_test_integrity_signals, build_test_integrity_report

__all__ = [
    "IntegrityFinding",
    "TestIntegrityFinding",
    "IntegritySignalType",
    "detect_test_integrity_signals",
    "build_test_integrity_report",
]