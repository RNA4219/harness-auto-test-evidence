"""Tests for file size guardrail tool."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

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


@pytest.mark.parametrize(("lines", "level", "exit_code"), [(700, None, 0), (701, "warning", 0), (900, "warning", 0), (901, "fail", 1)])
def test_warning_and_failure_boundaries(tmp_path, capsys, lines, level, exit_code):
    (tmp_path / "module.py").write_text("x = 1\n" * lines, encoding="utf-8")
    findings = check_file_size.collect_findings(tmp_path, include_warnings=True)
    assert [finding.level for finding in findings] == ([] if level is None else [level])
    assert check_file_size.main(["--root", str(tmp_path)]) == exit_code
    output = capsys.readouterr().out
    assert ("warning:" in output) == (level == "warning")
    assert ("fail:" in output) == (level == "fail")


@pytest.mark.parametrize("directory", [".runtime", ".venv", ".mypy_cache", ".ruff_cache", "tmp", "dist", "build"])
def test_generated_directories_are_not_traversed(tmp_path, monkeypatch, directory):
    cache = tmp_path / directory
    cache.mkdir()
    (cache / "generated.py").write_text("x = 1\n" * 1001, encoding="utf-8")
    scandir = check_file_size.os.scandir

    def checked_scandir(path):
        assert Path(path) != cache, "generated cache must be pruned before traversal"
        return scandir(path)

    with monkeypatch.context() as patch:
        patch.setattr(check_file_size.os, "scandir", checked_scandir)
        assert check_file_size.collect_findings(tmp_path, include_warnings=True) == []


@pytest.mark.parametrize(("relative", "lines", "fails"), [
    ("fixtures/case.json", 1000, False),
    ("fixtures/case.json", 1001, True),
    ("fixtures/golden/case/expected/report.json", 5000, False),
    ("fixtures/golden/case/expected/report.json", 5001, True),
    ("fixtures/other/golden/case/expected/report.json", 1001, True),
    ("fixtures/golden/case/input.json", 1001, True),
    ("schemas/schema-registry.json", 1001, False),
])
def test_large_fixture_exception_is_limited_to_golden_expected_json(tmp_path, relative, lines, fails):
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text("\n" * lines, encoding="utf-8")
    assert bool(check_file_size.collect_findings(tmp_path)) is fails
