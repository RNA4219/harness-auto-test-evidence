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

    expansion_run = expansion_subparsers.add_parser("run", help="Run HATE-GAP-027..060 expansion report and UAT builders.")
    expansion_run.add_argument("--fixtures-root", default=Path("fixtures/expansion"), type=Path, help="Canonical expansion fixture root.")
    expansion_run.add_argument("--out", required=True, type=Path, help="Output directory for generated expansion reports.")
    expansion_run.add_argument(
        "--case-kind",
        choices=["positive", "negative", "all"],
        default="positive",
        help="Fixture case kind to run. Positive output is release-pack compatible.",
    )
    expansion_run.add_argument("--area", action="append", default=[], help="Optional expansion area to run; repeat for multiple areas.")

    real_repo = subparsers.add_parser("real-repo", help="Run recurring real repository evaluation from a roster.")
    real_repo_subparsers = real_repo.add_subparsers(dest="real_repo_command", required=True)

    real_repo_run = real_repo_subparsers.add_parser("run", help="Run local real-repo commands with timeout evidence.")
    real_repo_run.add_argument("--roster", required=True, type=Path, help="JSON roster containing repositories[].")
    real_repo_run.add_argument("--out", required=True, type=Path, help="Output directory for real-repo reports.")
    real_repo_run.add_argument("--source-version", default=None, help="Source version for generated records.")

    real_repo_ingest = real_repo_subparsers.add_parser("history-ingest", help="Append real-repo run history JSONL into a local store.")
    real_repo_ingest.add_argument("--history", required=True, type=Path, help="real-repo-run-history.jsonl produced by real-repo run.")
    real_repo_ingest.add_argument("--store", required=True, type=Path, help="Local real-repo history store directory.")

    real_repo_query = real_repo_subparsers.add_parser("history-query", help="Query the local real-repo history store.")
    real_repo_query.add_argument("--store", required=True, type=Path, help="Local real-repo history store directory.")
    real_repo_query.add_argument("--repo-id", default=None, help="Filter by repository id.")
    real_repo_query.add_argument("--suite-id", default=None, help="Filter by suite id.")
    real_repo_query.add_argument("--source-version", default=None, help="Filter by source version.")
    real_repo_query.add_argument("--status", choices=["pass", "hold", "blocked"], default=None, help="Filter by run status.")
    real_repo_query.add_argument("--since", default=None, help="Inclusive started_at lower bound.")
    real_repo_query.add_argument("--until", default=None, help="Inclusive started_at upper bound.")
    real_repo_query.add_argument("--limit", type=int, default=100, help="Maximum returned entries.")

    platform = subparsers.add_parser("platform", help="Operate HATE platform workflows from canonical reports.")
    platform_subparsers = platform.add_subparsers(dest="platform_command", required=True)

    platform_run = platform_subparsers.add_parser("run", help="Run a real-repo roster through the platform entrypoint.")
    platform_run.add_argument("--roster", required=True, type=Path, help="JSON roster containing repositories[].")
    platform_run.add_argument("--out", required=True, type=Path, help="Output directory for platform run reports.")
    platform_run.add_argument("--source-version", default=None, help="Source version for generated records.")

    platform_history = platform_subparsers.add_parser("history", help="Query the platform real-repo history store.")
    platform_history.add_argument("--store", required=True, type=Path, help="Local real-repo history store directory.")
    platform_history.add_argument("--repo-id", default=None, help="Filter by repository id.")
    platform_history.add_argument("--suite-id", default=None, help="Filter by suite id.")
    platform_history.add_argument("--source-version", default=None, help="Filter by source version.")
    platform_history.add_argument("--status", choices=["pass", "hold", "blocked"], default=None, help="Filter by run status.")
    platform_history.add_argument("--since", default=None, help="Inclusive started_at lower bound.")
    platform_history.add_argument("--until", default=None, help="Inclusive started_at upper bound.")
    platform_history.add_argument("--limit", type=int, default=100, help="Maximum returned entries.")

    platform_history_analytics = platform_subparsers.add_parser("history-analytics", help="Build long-term history trend analytics from samples.")
    platform_history_analytics.add_argument("--input", required=True, type=Path, help="History analytics input JSON.")
    platform_history_analytics.add_argument("--out", default=None, type=Path, help="Optional output JSON path.")

    platform_history_materialize = platform_subparsers.add_parser("history-materialize", help="Plan incremental history materialization and optional manifest output.")
    platform_history_materialize.add_argument("--input", required=True, type=Path, help="History materialization input JSON.")
    platform_history_materialize.add_argument("--previous-manifest", default=None, type=Path, help="Optional previous history materialization manifest.")
    platform_history_materialize.add_argument("--manifest-out", default=None, type=Path, help="Optional output path for reusable history materialization manifest.")
    platform_history_materialize.add_argument("--out", default=None, type=Path, help="Optional output JSON path for the materialization plan.")

    platform_compare = platform_subparsers.add_parser("compare", help="Compare two platform report JSON files.")
    platform_compare.add_argument("--base", required=True, type=Path, help="Base report JSON.")
    platform_compare.add_argument("--head", required=True, type=Path, help="Head report JSON.")
    platform_compare.add_argument("--out", default=None, type=Path, help="Optional output JSON path.")

    platform_schedule = platform_subparsers.add_parser("schedule", help="Plan scheduled platform runs with cache, retry, and resume tokens.")
    platform_schedule.add_argument("--roster", required=True, type=Path, help="JSON roster containing repositories[].")
    platform_schedule.add_argument("--history-store", required=True, type=Path, help="History store directory or run_history.jsonl path.")
    platform_schedule.add_argument("--out", default=None, type=Path, help="Optional output JSON path.")
    platform_schedule.add_argument("--cache-ttl-hours", type=int, default=24, help="Fresh pass cache TTL.")
    platform_schedule.add_argument("--retry-limit", type=int, default=1, help="Retry attempts planned for held suites.")
    platform_schedule.add_argument("--force", action="store_true", help="Bypass cache hits and plan all suites.")

    for name, help_text in (
        ("findings", "List findings from a platform report file or directory."),
        ("debt", "List risk debt items from a platform report file or directory."),
        ("review", "List manual review requests from a platform report file or directory."),
    ):
        sub = platform_subparsers.add_parser(name, help=help_text)
        sub.add_argument("--input", required=True, type=Path, help="Input report JSON file or directory.")

    platform_assign = platform_subparsers.add_parser("assign", help="Build owner, due-date, and SLA assignment queue from findings.")
    platform_assign.add_argument("--input", required=True, type=Path, help="Input report JSON file or directory.")
    platform_assign.add_argument("--out", default=None, type=Path, help="Optional output JSON path.")

    platform_score = platform_subparsers.add_parser("score", help="Compute explainable platform scores from real-repo reports.")
    platform_score.add_argument("--input", required=True, type=Path, help="Input report JSON file or directory.")
    platform_score.add_argument("--out", default=None, type=Path, help="Optional output JSON path.")

    platform_verdict = platform_subparsers.add_parser("verdict", help="Evaluate reports against an expected verdict corpus.")
    platform_verdict.add_argument("--input", required=True, type=Path, help="Input report JSON file or directory.")
    platform_verdict.add_argument("--corpus", required=True, type=Path, help="Expected verdict corpus JSON.")
    platform_verdict.add_argument("--out", default=None, type=Path, help="Optional output JSON path.")

    platform_triage = platform_subparsers.add_parser("triage", help="Build an operator triage queue from held platform reports.")
    platform_triage.add_argument("--input", required=True, type=Path, help="Input report JSON file or directory.")
    platform_triage.add_argument("--out", default=None, type=Path, help="Optional output JSON path.")

    platform_baseline = platform_subparsers.add_parser("baseline", help="Operate baseline promotion workflow evidence.")
    platform_baseline_subparsers = platform_baseline.add_subparsers(dest="platform_baseline_command", required=True)
    platform_baseline_promote = platform_baseline_subparsers.add_parser("promote", help="Build a baseline promotion report from local approval events.")
    platform_baseline_promote.add_argument("--input", required=True, type=Path, help="Baseline promotion input JSON.")
    platform_baseline_promote.add_argument("--out", default=None, type=Path, help="Optional output JSON path.")
    platform_baseline_review = platform_baseline_subparsers.add_parser("review", help="Build a human baseline review packet from promotion and comparison evidence.")
    platform_baseline_review.add_argument("--input", required=True, type=Path, help="Baseline review input JSON.")
    platform_baseline_review.add_argument("--out", default=None, type=Path, help="Optional output JSON path.")

    platform_notify = platform_subparsers.add_parser("notify", help="Plan and verify operator notifications.")
    platform_notify_subparsers = platform_notify.add_subparsers(dest="platform_notify_command", required=True)
    platform_notify_route = platform_notify_subparsers.add_parser("route", help="Build notification routing plan from operating records and subscribers.")
    platform_notify_route.add_argument("--input", required=True, type=Path, help="Notification routing input JSON.")
    platform_notify_route.add_argument("--out", default=None, type=Path, help="Optional output JSON path.")
    platform_notify_deliver = platform_notify_subparsers.add_parser("deliver", help="Build notification delivery report from delivery attempts.")
    platform_notify_deliver.add_argument("--input", required=True, type=Path, help="Notification delivery input JSON.")
    platform_notify_deliver.add_argument("--out", default=None, type=Path, help="Optional output JSON path.")

    platform_plugin = platform_subparsers.add_parser("plugin", help="Run and isolate platform detector plugins.")
    platform_plugin_subparsers = platform_plugin.add_subparsers(dest="platform_plugin_command", required=True)
    platform_plugin_run = platform_plugin_subparsers.add_parser("run", help="Execute a plugin manifest under platform isolation checks.")
    platform_plugin_run.add_argument("--manifest", required=True, type=Path, help="Plugin manifest JSON.")
    platform_plugin_run.add_argument("--out", default=None, type=Path, help="Optional output JSON path.")
    platform_plugin_run.add_argument("--allow-local-exec", action="store_true", help="Explicitly authorize a trusted local subprocess plugin.")

    platform_policy = platform_subparsers.add_parser("policy", help="Explain effective platform policy.")
    platform_policy_subparsers = platform_policy.add_subparsers(dest="platform_policy_command", required=True)
    platform_policy_explain = platform_policy_subparsers.add_parser("explain", help="Evaluate platform policy JSON.")
    platform_policy_explain.add_argument("--policy", required=True, type=Path, help="Policy JSON or wrapper input.")
    platform_policy_explain.add_argument("--profile", default="default", help="Profile to evaluate when input has no profile.")
    platform_policy_explain.add_argument("--out", default=None, type=Path, help="Optional output JSON path.")

    platform_report = platform_subparsers.add_parser("report", help="Generate platform reports.")
    platform_report_subparsers = platform_report.add_subparsers(dest="platform_report_command", required=True)
    platform_report_html = platform_report_subparsers.add_parser("html", help="Generate an offline HTML summary.")
    platform_report_html.add_argument("--input", required=True, type=Path, help="Input report JSON file or directory.")
    platform_report_html.add_argument("--out", required=True, type=Path, help="Output HTML path.")

    platform_serve = platform_subparsers.add_parser("serve", help="Serve local product readiness artifacts through platform entrypoint.")
    platform_serve.add_argument("--readiness", required=True, type=Path, help="Input P2/P3 product readiness artifact directory.")
    platform_serve.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    platform_serve.add_argument("--port", default=8765, type=int, help="Port to bind.")

    validation = subparsers.add_parser("validation", help="Run repeated five-tool/QEG validation cycles.")
    validation_subparsers = validation.add_subparsers(dest="validation_command", required=True)

    validation_cycles = validation_subparsers.add_parser("cycles", help="Evaluate ten QEG hardening cycles.")
    validation_cycles.add_argument("--fixture", required=True, type=Path, help="Validation cycle fixture JSON.")
    validation_cycles.add_argument("--out", required=True, type=Path, help="Output directory for validation-cycle-report.json.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return dispatch_cli(args, parser)
