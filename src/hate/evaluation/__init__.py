"""Evaluation reports for recurring product evidence."""

from hate.evaluation.agent_quality import (
    AgentQualityFinding,
    build_agent_quality_report,
    evaluate_agent_quality_fixture,
)
from hate.evaluation.baseline_governance import build_real_repo_baseline_governance_report
from hate.evaluation.real_repo import (
    RealRepoEvaluationFinding,
    build_real_repo_evaluation_report,
    evaluate_real_repo_fixture,
    run_real_repo_roster,
)
from hate.evaluation.history_store import (
    RealRepoHistoryStoreError,
    ingest_real_repo_history,
    query_real_repo_history,
)
from hate.evaluation.output_safety import safe_command_output
from hate.evaluation.regression_engine import classify_real_repo_regressions
from hate.evaluation.score_model import build_real_repo_score_report
from hate.evaluation.runner_dialects import build_runner_dialect_coverage_report, parse_runner_summary

__all__ = [
    "AgentQualityFinding",
    "RealRepoEvaluationFinding",
    "RealRepoHistoryStoreError",
    "build_agent_quality_report",
    "build_real_repo_baseline_governance_report",
    "build_real_repo_evaluation_report",
    "build_real_repo_score_report",
    "build_runner_dialect_coverage_report",
    "classify_real_repo_regressions",
    "evaluate_agent_quality_fixture",
    "evaluate_real_repo_fixture",
    "ingest_real_repo_history",
    "query_real_repo_history",
    "run_real_repo_roster",
    "safe_command_output",
    "parse_runner_summary",
]
