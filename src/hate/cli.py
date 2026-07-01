from __future__ import annotations

import argparse
from pathlib import Path

from .cli_handlers import dispatch_cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hate",
        description="Generate HATE/v1 P0a evidence artifacts from local test inputs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p0a = subparsers.add_parser("p0a", help="Run the P0a local-first golden path.")
    p0a.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Input directory containing github-context.json or ci-context.json, plus test/coverage artifacts.",
    )
    p0a.add_argument("--out", required=True, type=Path, help="Output directory for generated HATE artifacts.")
    p0a.add_argument("--source-version", default="0.1.0", help="Source version stored in generated records.")
    p0a.add_argument(
        "--profile",
        default="default",
        choices=["default", "strict", "release", "experimental"],
        help="P0a precheck profile. This is evidence eligibility only, not QEG release Gate policy.",
    )
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

    trust = subparsers.add_parser("trust", help="Generate P1a trust-hardening artifacts.")
    trust_subparsers = trust.add_subparsers(dest="trust_command", required=True)

    evaluate = trust_subparsers.add_parser("evaluate", help="Evaluate AETE trust score for a QEG bundle.")
    evaluate.add_argument("--bundle", required=True, type=Path, help="Input qeg-bundle.json path.")
    evaluate.add_argument("--report", required=True, type=Path, help="Input qeg-export-report.json path.")
    evaluate.add_argument("--out", required=True, type=Path, help="Output directory for trust artifacts.")
    evaluate.add_argument("--profile", default="default", help="AETE profile name.")
    evaluate.add_argument("--source-version", default=None, help="Source version for generated records.")

    replay = subparsers.add_parser("replay", help="Replay P1a trust evaluation from a frozen QEG bundle.")
    replay.add_argument("--bundle", required=True, type=Path, help="Input qeg-bundle.json path.")
    replay.add_argument("--report", required=True, type=Path, help="Input qeg-export-report.json path.")
    replay.add_argument("--out", required=True, type=Path, help="Output directory for replay artifacts.")
    replay.add_argument("--profile", default="default", help="AETE profile name.")

    compare = subparsers.add_parser("compare", help="Compare two P1a trust artifact directories.")
    compare.add_argument("--base", required=True, type=Path, help="Base trust artifact directory.")
    compare.add_argument("--head", required=True, type=Path, help="Head trust artifact directory.")
    compare.add_argument("--out", required=True, type=Path, help="Output directory for compare artifacts.")

    explain = subparsers.add_parser("explain", help="Explain P1a trust gaps from a frozen QEG bundle.")
    explain.add_argument("--bundle", required=True, type=Path, help="Input qeg-bundle.json path.")
    explain.add_argument("--report", required=True, type=Path, help="Input qeg-export-report.json path.")
    explain.add_argument("--out", required=True, type=Path, help="Output directory for explain artifacts.")
    explain.add_argument(
        "--mode",
        choices=["why-soft-gap", "why-excluded", "why-score-changed"],
        default="why-soft-gap",
        help="Explanation mode.",
    )

    recommend = subparsers.add_parser("recommend", help="Recommend next actions for a P1a trust gap.")
    recommend.add_argument("--bundle", required=True, type=Path, help="Input qeg-bundle.json path.")
    recommend.add_argument("--report", required=True, type=Path, help="Input qeg-export-report.json path.")
    recommend.add_argument("--out", required=True, type=Path, help="Output directory for recommendation artifacts.")
    recommend.add_argument("--gap", default="missing_execution", help="Gap id to recommend for.")

    doctor = subparsers.add_parser("doctor", help="Run P1a doctor and adapter conformance checks.")
    doctor.add_argument("--bundle", required=True, type=Path, help="Input qeg-bundle.json path.")
    doctor.add_argument("--report", required=True, type=Path, help="Input qeg-export-report.json path.")
    doctor.add_argument("--out", required=True, type=Path, help="Output directory for doctor artifacts.")

    workflow = subparsers.add_parser("workflow", help="Generate P1b workflow and downstream advisory artifacts.")
    workflow_subparsers = workflow.add_subparsers(dest="workflow_command", required=True)

    workflow_map = workflow_subparsers.add_parser("map", help="Map QEG and trust artifacts to RanD, Shipyard, and workflow-cookbook outputs.")
    workflow_map.add_argument("--bundle", required=True, type=Path, help="Input qeg-bundle.json path.")
    workflow_map.add_argument("--report", required=True, type=Path, help="Input qeg-export-report.json path.")
    workflow_map.add_argument("--trust", required=True, type=Path, help="Input P1a trust artifact directory.")
    workflow_map.add_argument("--out", required=True, type=Path, help="Output directory for P1b workflow artifacts.")
    workflow_map.add_argument("--rand-requirements", type=Path, default=None, help="Optional RanD requirements_packet.json input.")
    workflow_map.add_argument("--rand-audit", type=Path, default=None, help="Optional RanD requirements audit packet input.")
    workflow_map.add_argument("--shipyard-worker-result", type=Path, default=None, help="Optional Shipyard WorkerResult JSON input.")
    workflow_map.add_argument("--shipyard-run-system-packet", type=Path, default=None, help="Optional Shipyard RunSystemPacket JSON input.")
    workflow_map.add_argument("--source-version", default=None, help="Source version for generated records.")

    product = subparsers.add_parser("product", help="Generate P2/P3 product-readiness advisory artifacts.")
    product_subparsers = product.add_subparsers(dest="product_command", required=True)

    readiness = product_subparsers.add_parser("readiness", help="Generate product readiness and enterprise advisory artifacts.")
    readiness.add_argument("--bundle", required=True, type=Path, help="Input qeg-bundle.json path.")
    readiness.add_argument("--trust", required=True, type=Path, help="Input P1a trust artifact directory.")
    readiness.add_argument("--workflow", required=True, type=Path, help="Input P1b workflow artifact directory.")
    readiness.add_argument("--out", required=True, type=Path, help="Output directory for P2/P3 product artifacts.")
    readiness.add_argument("--source-version", default=None, help="Source version for generated records.")

    query = product_subparsers.add_parser("query", help="Query local product readiness artifacts with the hosted read model envelope.")
    query.add_argument("--readiness", required=True, type=Path, help="Input P2/P3 product readiness artifact directory.")
    query.add_argument("--resource", required=True, help="Resource name such as runs, evidence, artifacts, risk-debt, or product-readiness.")
    query.add_argument("--request-id", default="req_local", help="Request id for the API response envelope.")
    query.add_argument("--role", default="developer", help="Read model caller role: admin, maintainer, developer, auditor, or viewer.")
    query.add_argument("--filter", action="append", default=[], help="Filter in key=value form, for example status=open.")
    query.add_argument("--stale-cache", action="store_true", help="Mark the response as a stale cache view.")
    query.add_argument("--cursor", default=None, help="Pagination cursor to echo as next_cursor.")

    serve = product_subparsers.add_parser("serve", help="Serve local product readiness artifacts as hosted read model REST envelopes.")
    serve.add_argument("--readiness", required=True, type=Path, help="Input P2/P3 product readiness artifact directory.")
    serve.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    serve.add_argument("--port", default=8765, type=int, help="Port to bind.")

    grade_reports = product_subparsers.add_parser("grade-reports", help="Generate product-grade evidence report skeletons from requirement docs.")
    grade_reports.add_argument("--docs-root", default=Path("docs/process"), type=Path, help="Directory containing product requirements/specification docs.")
    grade_reports.add_argument("--out", required=True, type=Path, help="Output directory for product-grade evidence reports.")
    grade_reports.add_argument("--source-version", default=None, help="Source version for generated reports.")

    store = subparsers.add_parser("store", help="Ingest and query the local HATE history store.")
    store_subparsers = store.add_subparsers(dest="store_command", required=True)

    store_ingest = store_subparsers.add_parser("ingest", help="Ingest canonical artifacts into a local .hate store.")
    store_ingest.add_argument("--store", required=True, type=Path, help="Local store directory, for example .hate.")
    store_ingest.add_argument("--bundle", required=True, type=Path, help="Input qeg-bundle.json path.")
    store_ingest.add_argument("--readiness", required=True, type=Path, help="Input P2/P3 product readiness artifact directory.")
    store_ingest.add_argument("--source-version", default=None, help="Source version for generated store records.")

    store_query = store_subparsers.add_parser("query", help="Query a local HATE store resource.")
    store_query.add_argument("--store", required=True, type=Path, help="Local store directory.")
    store_query.add_argument("--resource", required=True, choices=["run", "bundle", "risk-debt", "product-readiness", "manifest", "history"], help="Store resource to reload.")
    store_query.add_argument("--run-id", default=None, help="Run id to query. Defaults to latest run.")

    store_history = store_subparsers.add_parser("history", help="Read the local HATE store history index.")
    store_history.add_argument("--store", required=True, type=Path, help="Local store directory.")

    release = subparsers.add_parser("release", help="Generate release candidate pack from P2/P3 product artifacts.")
    release_subparsers = release.add_subparsers(dest="release_command", required=True)

    release_candidate = release_subparsers.add_parser("candidate", help="Assemble release candidate pack from readiness reports.")
    release_candidate.add_argument("--readiness", required=True, type=Path, help="Input P2/P3 product readiness artifact directory.")
    release_candidate.add_argument("--out", required=True, type=Path, help="Output directory for release candidate pack.")
    release_candidate.add_argument("--release-id", default=None, help="Release candidate identifier.")
    release_candidate.add_argument("--source-version", default=None, help="Source version for generated records.")
    release_candidate.add_argument("--dry-run", action="store_true", help="Generate pack without blocking on missing reports.")

    gap = subparsers.add_parser("gap", help="Generate gap closure and workflow-cookbook alignment reports.")
    gap_subparsers = gap.add_subparsers(dest="gap_command", required=True)

    gap_closure = gap_subparsers.add_parser("closure", help="Validate HATE-GAP-001..026 closure docs, task seeds, acceptance, and fixtures.")
    gap_closure.add_argument("--repo-root", default=Path("."), type=Path, help="Repository root to validate.")
    gap_closure.add_argument("--out", required=True, type=Path, help="Output directory for gap-closure-report.json.")
    gap_closure.add_argument("--source-version", default=None, help="Source version for generated report.")

    expansion = subparsers.add_parser("expansion", help="Generate HATE expansion and analysis reports from canonical fixtures.")
    expansion_subparsers = expansion.add_subparsers(dest="expansion_command", required=True)

    expansion_run = expansion_subparsers.add_parser("run", help="Run HATE-GAP-027..040 and HATE-GAP-049..060 report builders.")
    expansion_run.add_argument("--fixtures-root", default=Path("fixtures/expansion"), type=Path, help="Canonical expansion fixture root.")
    expansion_run.add_argument("--out", required=True, type=Path, help="Output directory for generated expansion reports.")
    expansion_run.add_argument(
        "--case-kind",
        choices=["positive", "negative", "all"],
        default="positive",
        help="Fixture case kind to run. Positive output is release-pack compatible.",
    )
    expansion_run.add_argument("--area", action="append", default=[], help="Optional expansion area to run; repeat for multiple areas.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return dispatch_cli(args, parser)
