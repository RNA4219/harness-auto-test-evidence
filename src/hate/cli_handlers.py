"""Public CLI dispatch boundary for HATE v0.3."""

from __future__ import annotations

import argparse
import json
import sys

from .bridge.router import BRIDGE_COMMANDS, dispatch_bridge
from .p0a import PrecheckError, generate_p0a
from .p0b import ExportError, export_qeg
from .p1a import TrustError, compare_trust, doctor_trust, evaluate_trust, explain_trust, recommend_trust, replay_trust
from .store_legacy import StoreError, ingest_local_store, query_local_store, read_history_index


def dispatch_cli(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.command in BRIDGE_COMMANDS:
        return dispatch_bridge(args, parser)

    if args.command == "bridge":
        from .bridge.materializer import dispatch_materialize

        return dispatch_materialize(args)

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
            result = export_qeg(fixture_dir=args.fixture, out_dir=args.out, source_version=args.source_version)
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
            result = compare_trust(base_dir=args.base, head_dir=args.head, out_dir=args.out)
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
            result = doctor_trust(bundle_path=args.bundle, report_path=args.report, out_dir=args.out)
        except TrustError as exc:
            print(f"HATE-E-DOCTOR: {exc}", file=sys.stderr)
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
            result = query_local_store(store_dir=args.store, resource=args.resource, run_id=args.run_id)
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

    parser.error("unsupported command")
    return 2
