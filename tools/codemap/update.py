from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

INCLUDED_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".toml"}
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".uat-p2budget",
    "__pycache__",
    "dist",
    "build",
    "tmp",
}
GENERATED_DIR = Path("docs/birdseye")


@dataclass(frozen=True)
class SourceFile:
    path: Path
    rel: str
    text: str
    sha256: str
    line_count: int
    size_bytes: int


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate HATE local file-reference codemap index and capsules.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root.")
    parser.add_argument(
        "--out", type=Path, default=GENERATED_DIR, help="Output directory, relative to root by default."
    )
    parser.add_argument("--check", action="store_true", help="Fail if generated files would change.")
    args = parser.parse_args()

    root = args.root.resolve()
    out = args.out if args.out.is_absolute() else root / args.out
    generated = build_birdseye(root)

    planned = render_outputs(generated, out)
    if args.check:
        changed = [
            path
            for path, content in planned.items()
            if not path.exists() or path.read_text(encoding="utf-8") != content
        ]
        if changed:
            for path in changed:
                print(f"would update {path.relative_to(root).as_posix()}")
            return 1
        print("birdseye is up to date")
        return 0

    out.mkdir(parents=True, exist_ok=True)
    (out / "caps").mkdir(parents=True, exist_ok=True)
    for path, content in planned.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    print(f"generated {len(generated['nodes'])} birdseye nodes and {len(generated['edges'])} edges")
    return 0


def build_birdseye(root: Path) -> dict[str, Any]:
    sources = collect_sources(root)
    rels = {source.rel for source in sources}
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[list[str]] = []
    capsules: dict[str, dict[str, Any]] = {}

    for source in sources:
        role = classify_role(source.rel)
        deps = sorted(dep for dep in extract_dependencies(source, rels) if dep != source.rel)
        cap_path = f"docs/birdseye/caps/{capsule_name(source.rel)}.json"
        nodes[source.rel] = {
            "role": role,
            "caps": cap_path,
            "sha256": source.sha256,
            "line_count": source.line_count,
            "size_bytes": source.size_bytes,
        }
        for dep in deps:
            edges.append([source.rel, dep])
        capsules[source.rel] = {
            "path": source.rel,
            "role": role,
            "kind": source.path.suffix.lower().lstrip(".") or "file",
            "sha256": source.sha256,
            "line_count": source.line_count,
            "size_bytes": source.size_bytes,
            "headings": extract_headings(source.text),
            "imports": extract_python_imports(source) if source.path.suffix == ".py" else [],
            "links": extract_markdown_links(source) if source.path.suffix == ".md" else [],
            "depends_on": deps,
            "tags": infer_tags(source.rel, source.text),
        }

    graph_hash = stable_hash({"nodes": nodes, "edges": sorted(edges)})
    return {
        "generated_at": graph_hash[:12],
        "schema_version": "HATE-birdseye/v1",
        "nodes": dict(sorted(nodes.items())),
        "edges": sorted(edges),
        "capsules": capsules,
    }


def collect_sources(root: Path) -> list[SourceFile]:
    sources: list[SourceFile] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(root)
        if should_exclude(rel_path):
            continue
        if path.suffix.lower() not in INCLUDED_SUFFIXES:
            continue
        decoded = path.read_bytes().decode("utf-8", errors="ignore")
        text = decoded.replace("\r\n", "\n").replace("\r", "\n")
        normalized = text.encode("utf-8")
        sources.append(
            SourceFile(
                path=path,
                rel=rel_path.as_posix(),
                text=text,
                sha256=hashlib.sha256(normalized).hexdigest(),
                line_count=0 if not text else text.count("\n") + (0 if text.endswith("\n") else 1),
                size_bytes=len(normalized),
            )
        )
    return sources


def should_exclude(rel_path: Path) -> bool:
    parts = set(rel_path.parts)
    if parts & EXCLUDED_PARTS:
        return True
    return rel_path.as_posix().startswith(GENERATED_DIR.as_posix() + "/")


def classify_role(rel: str) -> str:
    name = Path(rel).name.lower()
    if rel.startswith("src/"):
        return "implementation"
    if rel.startswith("tests/"):
        return "test"
    if rel.startswith("fixtures/"):
        return "fixture"
    if rel.startswith("schemas/"):
        return "schema"
    if rel.startswith(".github/workflows/"):
        return "ci"
    if rel.startswith("tools/"):
        return "tooling"
    if name in {"readme.md", "hub.codex.md"}:
        return "navigation"
    if "requirement" in name or "spec" in name or "contract" in name:
        return "requirements"
    if "runbook" in name:
        return "operations"
    if "evaluation" in name or "acceptance" in name:
        return "quality"
    if "epic" in name or "roadmap" in name or "task" in name:
        return "planning"
    return "documentation" if rel.startswith("docs/") else "project"


def extract_dependencies(source: SourceFile, rels: set[str]) -> set[str]:
    deps: set[str] = set()
    if source.path.suffix == ".md":
        for link in extract_markdown_links(source):
            resolved = resolve_link(source.rel, link, rels)
            if resolved:
                deps.add(resolved)
    if source.path.suffix == ".py":
        for module in extract_python_imports(source):
            resolved = resolve_python_import(source.rel, module, rels)
            if resolved:
                deps.add(resolved)
    return deps


def extract_headings(text: str) -> list[str]:
    headings = []
    for line in text.splitlines():
        if line.startswith("#"):
            headings.append(line.strip())
        if len(headings) >= 40:
            break
    return headings


def extract_markdown_links(source: SourceFile) -> list[str]:
    links = []
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", source.text):
        href = match.group(1).split("#", 1)[0].strip()
        if href and not re.match(r"(?i)^[a-z][a-z0-9+.-]*:", href):
            links.append(href)
    return sorted(set(links))


def extract_python_imports(source: SourceFile) -> list[str]:
    imports: set[str] = set()
    for line in source.text.splitlines():
        stripped = line.strip()
        match = re.match(r"from\s+([.\w]+)\s+import\s+", stripped)
        if match:
            imports.add(match.group(1))
            continue
        match = re.match(r"import\s+([.\w]+)", stripped)
        if match:
            imports.add(match.group(1))
    return sorted(imports)


def resolve_link(source_rel: str, link: str, rels: set[str]) -> str | None:
    if link.startswith("/"):
        candidate = link.lstrip("/")
    else:
        candidate = (Path(source_rel).parent / link).as_posix()
    normalized = Path(candidate).as_posix()
    return normalized if normalized in rels else None


def resolve_python_import(source_rel: str, module: str, rels: set[str]) -> str | None:
    if module.startswith("."):
        base = Path(source_rel).parent
        while module.startswith("."):
            module = module[1:]
        candidate = (base / (module.replace(".", "/") + ".py")).as_posix()
        return candidate if candidate in rels else None
    if module.startswith("hate."):
        candidate = "src/" + module.replace(".", "/") + ".py"
        return candidate if candidate in rels else None
    return None


def infer_tags(rel: str, text: str) -> list[str]:
    tags = set()
    lowered = f"{rel}\n{text[:4000]}".lower()
    for tag in [
        "adapter",
        "api",
        "artifact",
        "birdseye",
        "coverage",
        "enterprise",
        "epic",
        "fixture",
        "qeg",
        "release",
        "schema",
        "security",
        "store",
        "test",
        "workflow",
    ]:
        if tag in lowered:
            tags.add(tag)
    return sorted(tags)


def capsule_name(rel: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", ".", rel).strip(".")


def render_outputs(generated: dict[str, Any], out: Path) -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    index = {key: value for key, value in generated.items() if key != "capsules"}
    outputs[out / "index.json"] = json.dumps(index, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    outputs[out / "README.md"] = birdseye_readme(generated)
    for rel, capsule in generated["capsules"].items():
        outputs[out / "caps" / f"{capsule_name(rel)}.json"] = (
            json.dumps(capsule, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
        )
    return outputs


def birdseye_readme(generated: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# HATE File-Reference Codemap",
            "",
            "Generated lightweight file-reference codemap for `harness-auto-test-evidence`.",
            "",
            "This is not the workflow-cookbook Birdseye source of truth for analysis or implementation.",
            "It is a HATE-local navigation artifact for docs/src/tests/fixtures/schemas at large scale.",
            "",
            f"- schema_version: `{generated['schema_version']}`",
            f"- generated_at: `{generated['generated_at']}`",
            f"- nodes: `{len(generated['nodes'])}`",
            f"- edges: `{len(generated['edges'])}`",
            "",
            "Regenerate with:",
            "",
            "```powershell",
            "uv run python tools/codemap/update.py",
            "```",
            "",
        ]
    )


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
