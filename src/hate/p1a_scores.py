"""AETEの仕様上の重みと、比較前の保存スコア整合性検証。"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .input_values import ParsedFloat
from .p1a_io import TrustError, _read_json

# SPECIFICATION.md section 12。現行profileは閾値・運用方針を変え、重みは共通とする。
AETE_WEIGHTS: Mapping[str, int] = MappingProxyType({
    "provenance_integrity": 20,
    "determinism_flakiness": 15,
    "traceability_lineage": 15,
    "oracle_strength": 15,
    "change_relevance": 15,
    "coverage_adequacy": 10,
    "cross_signal_corroboration": 5,
    "freshness_profile_conformance": 5,
})
AGGREGATION_METHOD = "weighted_mean"


def compute_weighted_score(dimensions: Mapping[str, int]) -> float:
    total = sum(dimensions[name] * weight for name, weight in AETE_WEIGHTS.items())
    return round(total / (5 * sum(AETE_WEIGHTS.values())), 3)


def _number(value: Any) -> Decimal | None:
    if isinstance(value, ParsedFloat):
        token = value.lexeme
    elif type(value) in (int, float):
        token = str(value)
    else:
        return None
    try:
        number = Decimal(token)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def read_score_input(path: Path) -> dict[str, Any]:
    score = _read_json(path, exact_run_numbers=True)
    dimensions = score.get("dimensions")
    if not isinstance(dimensions, dict) or set(dimensions) != set(AETE_WEIGHTS):
        raise TrustError(f"{path}: dimensions must contain exactly the eight AETE dimensions", exit_code=1)
    validated: dict[str, int] = {}
    for name, value in dimensions.items():
        number = _number(value)
        if number is None or number not in (0, 1, 3, 5):
            raise TrustError(f"{path}: dimensions.{name} must be a numeric rubric value (0, 1, 3, 5)", exit_code=1)
        validated[name] = int(number)
    if "dimension_weights" in score:
        weights = score["dimension_weights"]
        if (not isinstance(weights, dict) or set(weights) != set(AETE_WEIGHTS)
                or any(_number(weights[name]) != weight for name, weight in AETE_WEIGHTS.items())):
            raise TrustError(f"{path}: dimension_weights do not match the supported AETE weights; run hate replay", exit_code=1)
    if score.get("aggregation_method", AGGREGATION_METHOD) != AGGREGATION_METHOD:
        raise TrustError(f"{path}: aggregation_method is unsupported; run hate replay", exit_code=1)
    value = _number(score.get("weighted_score"))
    if value is None or not 0 <= value <= 1:
        raise TrustError(f"{path}: weighted_score must be a finite number between 0 and 1", exit_code=1)
    expected = compute_weighted_score(validated)
    if value != Decimal(str(expected)):
        raise TrustError(
            f"{path}: weighted_score disagrees with dimensions and weights (expected {expected:.3f}); "
            "run hate replay with the original bundle and report before comparing", exit_code=1,
        )
    return score
