from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .p0a import PrecheckError, generate_p0a
from .p0b import ExportError, export_qeg


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hate",
        description="Generate HATE/v1 P0a evidence artifacts from local test inputs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p0a = subparsers.add_parser("p0a", help="Run the P0a local-first golden path.")
    p0a.add_argument("--input", required=True, type=Path, help="Input directory containing github-context.json, junit.xml, and lcov.info.")
    p0a.add_argument("--out", required=True, type=Path, help="Output directory for generated HATE artifacts.")
    p0a.add_argument("--source-version", default="0.1.0", help="Source version stored in generated records.")
    p0a.add_argument(
        "--fixture-path-prefix",
        default=None,
        help="Optional prefix used in artifact manifest paths, for stable golden fixture summaries.",
    )

    # P0b export qeg subcommand
    export = subparsers.add_parser("export", help="Export optional evidence artifacts.")
    export_subparsers = export.add_subparsers(dest="export_command", required=True)

    qeg = export_subparsers.add_parser("qeg", help="Export QEG optional evidence from P0a outputs.")
    qeg.add_argument("--fixture", required=True, type=Path, help="Input directory containing p0a/ subfolder and diff-risk-test.json.")
    qeg.add_argument("--out", required=True, type=Path, help="Output directory for QEG bundle.")
    qeg.add_argument("--source-version", default=None, help="Source version for generated records.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "p0a":
        try:
            result = generate_p0a(
                input_dir=args.input,
                out_dir=args.out,
                source_version=args.source_version,
                fixture_path_prefix=args.fixture_path_prefix,
            )
        except PrecheckError as exc:
            if exc.decision is not None and exc.out_dir is not None:
                print(json.dumps(exc.decision, ensure_ascii=False), file=sys.stderr)
            else:
                print(f"HATE-E-CLI: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "export" and args.export_command == "qeg":
        try:
            result = export_qeg(
                fixture_dir=args.fixture,
                out_dir=args.out,
                source_version=args.source_version,
            )
        except ExportError as exc:
            if exc.report is not None and exc.out_dir is not None:
                print(json.dumps(exc.report, ensure_ascii=False), file=sys.stderr)
            else:
                print(f"HATE-E-EXPORT: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 1
