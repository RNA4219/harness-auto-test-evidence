from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .p0a import PrecheckError, generate_p0a
from .p0b import ExportError, export_qeg
from .p1a import TrustError, compare_trust, doctor_trust, evaluate_trust, explain_trust, recommend_trust, replay_trust
from .p1b import WorkflowError, generate_workflow_mapping
from .p2p3 import ProductError, generate_product_readiness, query_product_read_model, serve_product_read_model
from .product_grade import ProductGradeError, generate_product_grade_reports
from .store import StoreError, ingest_local_store, query_local_store, read_history_index


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
                profile=args.profile,
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

    if args.command == "trust" and args.trust_command == "evaluate":
        try:
            result = evaluate_trust(
                bundle_path=args.bundle,
                report_path=args.report,
                out_dir=args.out,
                profile=args.profile,
                source_version=args.source_version,
            )
        except TrustError as exc:
            print(f"HATE-E-TRUST: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "replay":
        try:
            result = replay_trust(
                bundle_path=args.bundle,
                report_path=args.report,
                out_dir=args.out,
                profile=args.profile,
            )
        except TrustError as exc:
            print(f"HATE-E-REPLAY: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "compare":
        try:
            result = compare_trust(
                base_dir=args.base,
                head_dir=args.head,
                out_dir=args.out,
            )
        except TrustError as exc:
            print(f"HATE-E-COMPARE: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "explain":
        try:
            result = explain_trust(
                bundle_path=args.bundle,
                report_path=args.report,
                out_dir=args.out,
                mode=args.mode,
            )
        except TrustError as exc:
            print(f"HATE-E-EXPLAIN: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "recommend":
        try:
            result = recommend_trust(
                bundle_path=args.bundle,
                report_path=args.report,
                out_dir=args.out,
                gap_id=args.gap,
            )
        except TrustError as exc:
            print(f"HATE-E-RECOMMEND: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "doctor":
        try:
            result = doctor_trust(
                bundle_path=args.bundle,
                report_path=args.report,
                out_dir=args.out,
            )
        except TrustError as exc:
            print(f"HATE-E-DOCTOR: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "workflow" and args.workflow_command == "map":
        try:
            result = generate_workflow_mapping(
                bundle_path=args.bundle,
                report_path=args.report,
                trust_dir=args.trust,
                out_dir=args.out,
                rand_requirements_path=args.rand_requirements,
                rand_audit_path=args.rand_audit,
                shipyard_worker_result_path=args.shipyard_worker_result,
                shipyard_run_system_packet_path=args.shipyard_run_system_packet,
                source_version=args.source_version,
            )
        except WorkflowError as exc:
            print(f"HATE-E-WORKFLOW: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "product" and args.product_command == "readiness":
        try:
            result = generate_product_readiness(
                bundle_path=args.bundle,
                trust_dir=args.trust,
                workflow_dir=args.workflow,
                out_dir=args.out,
                source_version=args.source_version,
            )
        except ProductError as exc:
            print(f"HATE-E-PRODUCT: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "product" and args.product_command == "query":
        try:
            result = query_product_read_model(
                readiness_dir=args.readiness,
                resource=args.resource,
                request_id=args.request_id,
                role=args.role,
                filters=_parse_cli_filters(args.filter),
                stale_cache=args.stale_cache,
                cursor=args.cursor,
            )
        except ProductError as exc:
            print(f"HATE-E-PRODUCT: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "product" and args.product_command == "serve":
        try:
            serve_product_read_model(
                readiness_dir=args.readiness,
                host=args.host,
                port=args.port,
            )
        except ProductError as exc:
            print(f"HATE-E-PRODUCT: {exc}", file=sys.stderr)
            return exc.exit_code
        except KeyboardInterrupt:
            return 0

    if args.command == "product" and args.product_command == "grade-reports":
        try:
            result = generate_product_grade_reports(
                docs_root=args.docs_root,
                out_dir=args.out,
                source_version=args.source_version,
            )
        except ProductGradeError as exc:
            print(f"HATE-E-PRODUCT-GRADE: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "store" and args.store_command == "ingest":
        try:
            result = ingest_local_store(
                store_dir=args.store,
                bundle_path=args.bundle,
                readiness_dir=args.readiness,
                source_version=args.source_version,
            )
        except StoreError as exc:
            print(f"HATE-E-STORE: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "store" and args.store_command == "query":
        try:
            result = query_local_store(
                store_dir=args.store,
                resource=args.resource,
                run_id=args.run_id,
            )
        except StoreError as exc:
            print(f"HATE-E-STORE: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "store" and args.store_command == "history":
        try:
            result = read_history_index(store_dir=args.store)
        except StoreError as exc:
            print(f"HATE-E-STORE: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 1


def _parse_cli_filters(values: list[str]) -> dict[str, str]:
    filters: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"invalid --filter value, expected key=value: {value}")
        key, item = value.split("=", 1)
        filters[key] = item
    return filters
