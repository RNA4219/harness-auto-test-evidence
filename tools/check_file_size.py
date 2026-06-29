"""Check hand-maintained file sizes against the refactoring plan."""

from __future__ import annotations

import argparse
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


@dataclass(frozen=True)
class FileSizeFinding:
    path: str
    lines: int
    threshold: int
    level: str
    required_action: str


def collect_findings(root: Path) -> list[FileSizeFinding]:
    findings: list[FileSizeFinding] = []
    for path in sorted(root.rglob("*")):
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
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check HATE hand-maintained file size guardrails.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)

    findings = collect_findings(args.root.resolve())
    for finding in findings:
        print(
            f"{finding.level}: {finding.path} has {finding.lines} lines "
            f"(threshold {finding.threshold}); {finding.required_action}"
        )
    return 1 if findings else 0


def _should_check(path: Path, root: Path) -> bool:
    if not path.is_file():
        return False
    rel = path.relative_to(root)
    if any(part in {".git", ".venv", "__pycache__", ".pytest_cache", "tmp", ".uat-p2budget"} for part in rel.parts):
        return False
    if rel.parts[:3] == ("docs", "birdseye", "caps") or rel.as_posix() == "docs/birdseye/index.json":
        return False
    return path.suffix.lower() in {".py", ".md", ".json", ".yaml", ".yml"}


def _line_count(path: Path) -> int:
    try:
        return sum(1 for _ in path.open(encoding="utf-8"))
    except UnicodeDecodeError:
        return sum(1 for _ in path.open(encoding="utf-8-sig"))


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
        if _is_generated_fixture(rel):
            return JSON_HARD
        return JSON_HARD
    return None


def _is_generated_fixture(rel: Path) -> bool:
    parts = rel.parts
    return len(parts) >= 4 and parts[0] == "fixtures" and "golden" in parts and "expected" in parts


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
