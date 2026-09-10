"""Check hand-maintained file sizes against the refactoring plan."""

from __future__ import annotations

import argparse
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_WARNING = 700
SOURCE_HARD = 900
TEST_WARNING = 700
TEST_HARD = 900
MARKDOWN_WARNING = 800
MARKDOWN_HARD = 1000
JSON_WARNING = 1000
JSON_HARD = 5000

APPROVED_MARKDOWN_ROOT_INDEXES = {
    Path("docs/process/SPECIFICATION.md"),
}

IGNORED_DIRECTORIES = {
    ".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".runtime", "tmp", ".uat-p2budget",
}


def _skip_directory(rel: Path) -> bool:
    return (
        any(part in IGNORED_DIRECTORIES for part in rel.parts)
        or rel.parts[:3] == ("docs", "birdseye", "caps")
        or rel.parts[:1] in {("dist",), ("build",)}
    )


def _files(root: Path) -> Iterator[Path]:
    # 大きな依存キャッシュは、列挙後に除外するのではなく探索前に枝刈りする。
    for directory, children, files in os.walk(root):
        parent = Path(directory)
        children[:] = sorted(child for child in children if not _skip_directory((parent / child).relative_to(root)))
        for name in sorted(files):
            yield parent / name


@dataclass(frozen=True)
class FileSizeFinding:
    path: str
    lines: int
    threshold: int
    level: str
    required_action: str


def collect_findings(root: Path, *, include_warnings: bool = False) -> list[FileSizeFinding]:
    findings: list[FileSizeFinding] = []
    for path in _files(root):
        if not _should_check(path, root):
            continue
        rel = path.relative_to(root)
        lines = _line_count(path)
        threshold = _hard_threshold(rel)
        if threshold is None:
            continue
        if lines > threshold:
            findings.append(FileSizeFinding(
                path=rel.as_posix(),
                lines=lines,
                threshold=threshold,
                level="fail",
                required_action=_required_action(rel),
            ))
        elif include_warnings and lines > _warning_threshold(rel):
            findings.append(FileSizeFinding(
                path=rel.as_posix(),
                lines=lines,
                threshold=_warning_threshold(rel),
                level="warning",
                required_action=_required_action(rel),
            ))
    return sorted(findings, key=lambda finding: finding.path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check HATE hand-maintained file size guardrails.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)

    findings = collect_findings(args.root.resolve(), include_warnings=True)
    for finding in findings:
        print(
            f"{finding.level}: {finding.path} has {finding.lines} lines "
            f"(threshold {finding.threshold}); {finding.required_action}"
        )
    return 1 if any(finding.level == "fail" for finding in findings) else 0


def _should_check(path: Path, root: Path) -> bool:
    if not path.is_file():
        return False
    rel = path.relative_to(root)
    if _skip_directory(rel.parent):
        return False
    if rel.parts[:3] == ("docs", "birdseye", "caps") or rel.as_posix() == "docs/birdseye/index.json":
        return False
    return path.suffix.lower() in {".py", ".md", ".json", ".yaml", ".yml"}


def _line_count(path: Path) -> int:
    with path.open(encoding="utf-8-sig") as stream:
        return sum(1 for _ in stream)


def _warning_threshold(rel: Path) -> int:
    if rel.suffix.lower() == ".py":
        return TEST_WARNING if rel.parts[:1] == ("tests",) else SOURCE_WARNING
    if rel.suffix.lower() == ".md":
        return MARKDOWN_WARNING
    return JSON_WARNING


def _hard_threshold(rel: Path) -> int | None:
    suffix = rel.suffix.lower()
    if suffix == ".py" and rel.parts[:1] == ("tests",):
        return TEST_HARD
    if suffix == ".py":
        return SOURCE_HARD
    if suffix == ".md":
        if rel in APPROVED_MARKDOWN_ROOT_INDEXES:
            return None
        return MARKDOWN_HARD
    if suffix in {".json", ".yaml", ".yml"}:
        if rel.parts[:1] == ("fixtures",) and not _is_generated_fixture(rel):
            return JSON_WARNING
        return JSON_HARD
    return None


def _is_generated_fixture(rel: Path) -> bool:
    parts = rel.parts
    return len(parts) >= 4 and parts[:2] == ("fixtures", "golden") and parts[-2] == "expected" and rel.suffix == ".json"


def _required_action(rel: Path) -> str:
    suffix = rel.suffix.lower()
    if suffix == ".py" and rel.parts[:1] == ("tests",):
        return "split this test module by feature packet or fixture family"
    if suffix == ".py":
        return "split this source module before adding major behavior"
    if suffix == ".md":
        return "move detailed sections to focused contract docs and keep this file as an index"
    return "replace hand-maintained bulk data with generated fixture evidence or split the fixture"


if __name__ == "__main__":
    raise SystemExit(main())
