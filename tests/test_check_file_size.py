"""Tests for file size guardrail tool."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("check_file_size", ROOT / "tools" / "check_file_size.py")
check_file_size = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = check_file_size
assert SPEC.loader is not None
SPEC.loader.exec_module(check_file_size)


def test_file_size_guard_passes_current_tree() -> None:
    assert check_file_size.collect_findings(ROOT) == []


def test_file_size_guard_reports_oversized_test_module(tmp_path: Path) -> None:
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    oversized = test_dir / "test_large.py"
    oversized.write_text("\n".join("x = 1" for _ in range(901)), encoding="utf-8")

    findings = check_file_size.collect_findings(tmp_path)

    assert len(findings) == 1
    assert findings[0].path == "tests/test_large.py"
    assert findings[0].threshold == 900
    assert "split this test module" in findings[0].required_action


def test_file_size_guard_allows_approved_root_spec_index(tmp_path: Path) -> None:
    docs = tmp_path / "docs" / "process"
    docs.mkdir(parents=True)
    spec = docs / "SPECIFICATION.md"
    spec.write_text("\n".join("# index" for _ in range(1200)), encoding="utf-8")

    assert check_file_size.collect_findings(tmp_path) == []
