from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("codemap_update", ROOT / "tools/codemap/update.py")
assert SPEC is not None
codemap_update = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = codemap_update
SPEC.loader.exec_module(codemap_update)

build_birdseye = codemap_update.build_birdseye
collect_sources = codemap_update.collect_sources
render_outputs = codemap_update.render_outputs


def test_codemap_builds_index_and_capsules(tmp_path: Path) -> None:
    (tmp_path / "src/hate").mkdir(parents=True)
    (tmp_path / "docs/process").mkdir(parents=True)
    (tmp_path / "README.md").write_text("[Spec](docs/process/SPEC.md)\n", encoding="utf-8")
    (tmp_path / "docs/process/SPEC.md").write_text("# Spec\n", encoding="utf-8")
    (tmp_path / "src/hate/example.py").write_text("from .other import value\n", encoding="utf-8")
    (tmp_path / "src/hate/other.py").write_text("value = 1\n", encoding="utf-8")

    generated = build_birdseye(tmp_path)

    assert generated["schema_version"] == "HATE-birdseye/v1"
    assert "README.md" in generated["nodes"]
    assert "src/hate/example.py" in generated["nodes"]
    assert ["README.md", "docs/process/SPEC.md"] in generated["edges"]
    assert ["src/hate/example.py", "src/hate/other.py"] in generated["edges"]


def test_codemap_render_outputs_are_json(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Readme\n", encoding="utf-8")
    generated = build_birdseye(tmp_path)

    outputs = render_outputs(generated, tmp_path / "docs/birdseye")

    index = json.loads(outputs[tmp_path / "docs/birdseye/index.json"])
    assert index["nodes"]["README.md"]["caps"] == "docs/birdseye/caps/README.md.json"
    assert outputs[tmp_path / "docs/birdseye/caps/README.md.json"].endswith("\n")


def test_codemap_hash_is_stable_across_line_endings(tmp_path: Path) -> None:
    source_path = tmp_path / "README.md"
    source_path.write_bytes(b"# Readme\nsecond line\n")
    lf_source = collect_sources(tmp_path)[0]

    source_path.write_bytes(b"# Readme\r\nsecond line\r\n")
    crlf_source = collect_sources(tmp_path)[0]

    assert crlf_source.sha256 == lf_source.sha256
    assert crlf_source.size_bytes == lf_source.size_bytes
    assert crlf_source.line_count == lf_source.line_count
    assert crlf_source.text == lf_source.text
