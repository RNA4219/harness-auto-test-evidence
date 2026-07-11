"""Command handlers for the HATE CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ...evaluation import (
    RealRepoHistoryStoreError,
    ingest_real_repo_history,
    query_real_repo_history,
    run_real_repo_roster,
)
from ...expansion_runner import ExpansionRunError, run_expansion_suite
from ...gap_closure import GapClosureError, generate_gap_closure_report
from ...p0a import PrecheckError, generate_p0a
from ...p0b import ExportError, export_qeg
from ...p1a import TrustError, compare_trust, doctor_trust, evaluate_trust, explain_trust, recommend_trust, replay_trust
from ...p1b import WorkflowError, generate_workflow_mapping
from ...p2p3 import ProductError, generate_product_readiness, query_product_read_model, serve_product_read_model
from ...platform_cli import (
    PlatformCliError,
    platform_assign,
    platform_baseline_promote,
    platform_baseline_review,
    platform_compare,
    platform_debt,
    platform_findings,
    platform_history,
    platform_history_analytics,
    platform_history_materialize,
    platform_notify_deliver,
    platform_notify_route,
    platform_plugin_run,
    platform_policy_explain,
    platform_report_html,
    platform_review,
    platform_run,
    platform_schedule,
    platform_score,
    platform_serve,
    platform_triage,
    platform_verdict,
)
from ...product_grade import ProductGradeError, generate_product_grade_reports
from ...release import RELEASE_PACK_REQUIRED_REPORT_TYPES, assemble_release_candidate_pack
from ...store_legacy import StoreError, ingest_local_store, query_local_store, read_history_index
from ...validation_cycles import ValidationCycleError, run_validation_cycles


class ReleaseError(Exception):
    def __init__(self, message: str, exit_code: int = 2, pack: dict | None = None) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.pack = pack


def dispatch_compat_cli(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
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

    if args.command == "release" and args.release_command == "candidate":
        try:
            result = _assemble_release_candidate(
                readiness_dir=args.readiness,
                out_dir=args.out,
                release_id=args.release_id,
                source_version=args.source_version,
                dry_run=args.dry_run,
            )
        except ReleaseError as exc:
            if exc.pack is not None:
                print(json.dumps(exc.pack, ensure_ascii=False), file=sys.stderr)
            else:
                print(f"HATE-E-RELEASE: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "gap" and args.gap_command == "closure":
        try:
            result = generate_gap_closure_report(
                repo_root=args.repo_root,
                out_dir=args.out,
                source_version=args.source_version,
            )
        except GapClosureError as exc:
            if exc.report is not None:
                print(json.dumps(exc.report, ensure_ascii=False), file=sys.stderr)
            else:
                print(f"HATE-E-GAP: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "expansion" and args.expansion_command == "run":
        try:
            result = run_expansion_suite(
                fixtures_root=args.fixtures_root,
                out_dir=args.out,
                areas=args.area,
                case_kind=args.case_kind,
            )
        except ExpansionRunError as exc:
            print(f"HATE-E-EXPANSION: {exc}", file=sys.stderr)
            return exc.exit_code

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "real-repo" and args.real_repo_command == "run":
        try:
            result = run_real_repo_roster(
                roster_path=args.roster,
                out_dir=args.out,
                source_version=args.source_version,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"HATE-E-REAL-REPO: {exc}", file=sys.stderr)
            return 2

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "real-repo" and args.real_repo_command == "history-ingest":
        try:
            result = ingest_real_repo_history(args.history, args.store)
        except RealRepoHistoryStoreError as exc:
            print(f"HATE-E-REAL-REPO-HISTORY: {exc}", file=sys.stderr)
            return 2

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "real-repo" and args.real_repo_command == "history-query":
        try:
            result = query_real_repo_history(
                args.store,
                repo_id=args.repo_id,
                suite_id=args.suite_id,
                source_version=args.source_version,
                status=args.status,
                since=args.since,
                until=args.until,
                limit=args.limit,
            )
        except RealRepoHistoryStoreError as exc:
            print(f"HATE-E-REAL-REPO-HISTORY: {exc}", file=sys.stderr)
            return 2

        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "platform":
        try:
            result = _dispatch_platform(args)
        except (PlatformCliError, RealRepoHistoryStoreError, OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"HATE-E-PLATFORM: {exc}", file=sys.stderr)
            return getattr(exc, "exit_code", 2)
        except KeyboardInterrupt:
            return 0

        if result is not None:
            print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "validation" and args.validation_command == "cycles":
        try:
            result = run_validation_cycles(fixture_path=args.fixture, out_dir=args.out)
        except (OSError, json.JSONDecodeError, ValidationCycleError) as exc:
            if isinstance(exc, ValidationCycleError) and exc.report is not None:
                print(json.dumps(exc.report, ensure_ascii=False), file=sys.stderr)
                return exc.exit_code
            print(f"HATE-E-VALIDATION-CYCLES: {exc}", file=sys.stderr)
            return 2

        print(json.dumps(result, ensure_ascii=False))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 1


def _dispatch_platform(args: argparse.Namespace) -> dict[str, Any] | None:
    if args.platform_command == "run":
        return platform_run(args.roster, args.out, source_version=args.source_version)
    if args.platform_command == "history":
        return platform_history(
            args.store,
            repo_id=args.repo_id,
            suite_id=args.suite_id,
            source_version=args.source_version,
            status=args.status,
            since=args.since,
            until=args.until,
            limit=args.limit,
        )
    if args.platform_command == "history-analytics":
        return platform_history_analytics(args.input, out_path=args.out)
    if args.platform_command == "history-materialize":
        return platform_history_materialize(
            args.input,
            out_path=args.out,
            previous_manifest_path=args.previous_manifest,
            manifest_out_path=args.manifest_out,
        )
    if args.platform_command == "compare":
        return platform_compare(args.base, args.head, out_path=args.out)
    if args.platform_command == "schedule":
        return platform_schedule(
            args.roster,
            args.history_store,
            out_path=args.out,
            cache_ttl_hours=args.cache_ttl_hours,
            retry_limit=args.retry_limit,
            force=args.force,
        )
    if args.platform_command == "findings":
        return platform_findings(args.input)
    if args.platform_command == "debt":
        return platform_debt(args.input)
    if args.platform_command == "review":
        return platform_review(args.input)
    if args.platform_command == "assign":
        return platform_assign(args.input, out_path=args.out)
    if args.platform_command == "score":
        return platform_score(args.input, out_path=args.out)
    if args.platform_command == "verdict":
        return platform_verdict(args.input, args.corpus, out_path=args.out)
    if args.platform_command == "triage":
        return platform_triage(args.input, out_path=args.out)
    if args.platform_command == "baseline" and args.platform_baseline_command == "promote":
        return platform_baseline_promote(args.input, out_path=args.out)
    if args.platform_command == "baseline" and args.platform_baseline_command == "review":
        return platform_baseline_review(args.input, out_path=args.out)
    if args.platform_command == "notify" and args.platform_notify_command == "route":
        return platform_notify_route(args.input, out_path=args.out)
    if args.platform_command == "notify" and args.platform_notify_command == "deliver":
        return platform_notify_deliver(args.input, out_path=args.out)
    if args.platform_command == "plugin" and args.platform_plugin_command == "run":
        return platform_plugin_run(args.manifest, out_path=args.out, allow_local_exec=args.allow_local_exec)
    if args.platform_command == "policy" and args.platform_policy_command == "explain":
        return platform_policy_explain(args.policy, out_path=args.out, profile=args.profile)
    if args.platform_command == "report" and args.platform_report_command == "html":
        return platform_report_html(args.input, args.out)
    if args.platform_command == "serve":
        platform_serve(args.readiness, args.host, args.port)
        return None
    raise PlatformCliError(f"unknown platform command: {args.platform_command}")


def _parse_cli_filters(values: list[str]) -> dict[str, str]:
    filters: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"invalid --filter value, expected key=value: {value}")
        key, item = value.split("=", 1)
        filters[key] = item
    return filters


def _assemble_release_candidate(
    readiness_dir: Path,
    out_dir: Path,
    release_id: str | None,
    source_version: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    """Assemble release candidate pack from P2/P3 readiness artifacts."""
    if not readiness_dir.exists():
        raise ReleaseError(f"readiness directory not found: {readiness_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)

    reports: list[dict[str, Any]] = []
    for report_type in RELEASE_PACK_REQUIRED_REPORT_TYPES:
        report_path = readiness_dir / f"{report_type}.json"
        if report_path.exists():
            try:
                report_data = json.loads(report_path.read_text(encoding="utf-8"))
                reports.append(report_data)
            except json.JSONDecodeError:
                reports.append({
                    "record_type": report_type,
                    "report_id": report_type,
                    "status": "malformed",
                    "readiness_effect": "hard_dq",
                    "sourceRefs": [str(report_path)],
                })

    input_data = {
        "release_id": release_id or f"rc-{readiness_dir.name}",
        "source_version": source_version or "unknown",
        "reports": reports,
        "required_reports": RELEASE_PACK_REQUIRED_REPORT_TYPES,
        "evidence_room_artifacts": [],
        "qeg_refs": [],
        "qeg_approval_claimed": False,
        "sign_off": {"status": "pending", "owner": "", "sourceRefs": []},
    }

    pack = assemble_release_candidate_pack(input_data)
    pack_path = out_dir / "release-candidate-pack.json"
    pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if pack["verdict"] == "blocked" and not dry_run:
        raise ReleaseError(
            f"release candidate pack is blocked: {len(pack['blockers'])} blockers",
            exit_code=3,
            pack=pack,
        )

    return {
        "generated": ["release-candidate-pack.json"],
        "out_dir": str(out_dir),
        "verdict": pack["verdict"],
        "release_ready": pack["summary"]["release_ready"],
        "blocker_count": pack["summary"]["blocker_count"],
    }
