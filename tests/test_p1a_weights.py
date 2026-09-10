"""仕様の重み、再計算の再現性、比較時の総合スコア整合性を検証する。"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hate import cli, p1a
from hate.schema_resources import read_schema, validate_schema_instance

FIXTURE = Path("fixtures/golden/p0b-qeg-minimal/expected")
# SPECIFICATION.md section 12 の独立した期待値。
WEIGHTS = {
    "provenance_integrity": 20, "determinism_flakiness": 15, "traceability_lineage": 15,
    "oracle_strength": 15, "change_relevance": 15, "coverage_adequacy": 10,
    "cross_signal_corroboration": 5, "freshness_profile_conformance": 5,
}


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _evaluate(out: Path, operation=p1a.evaluate_trust, profile="default"):
    return operation(FIXTURE / "qeg-bundle.json", FIXTURE / "qeg-export-report.json", out, profile=profile)


@pytest.mark.parametrize(("dimension", "expected"), [
    ("provenance_integrity", 0.20), ("determinism_flakiness", 0.15), ("traceability_lineage", 0.15),
    ("oracle_strength", 0.15), ("change_relevance", 0.15), ("coverage_adequacy", 0.10),
    ("cross_signal_corroboration", 0.05), ("freshness_profile_conformance", 0.05),
])
def test_each_dimension_contributes_its_specified_weight(dimension, expected, tmp_path, monkeypatch):
    dimensions = {name: 5 if name == dimension else 0 for name in WEIGHTS}
    monkeypatch.setattr(p1a, "_score_dimensions_with_signals", lambda *_: (dimensions, [], []))
    result = _evaluate(tmp_path)
    assert result["weighted_score"] == expected
    assert _read(tmp_path / "aete-score.json")["weighted_score"] == expected


@pytest.mark.parametrize(("value", "expected"), [(0, 0.0), (5, 1.0)])
def test_total_score_preserves_zero_to_one_scale(value, expected, tmp_path, monkeypatch):
    dimensions = {name: value for name in WEIGHTS}
    monkeypatch.setattr(p1a, "_score_dimensions_with_signals", lambda *_: (dimensions, [], []))
    assert _evaluate(tmp_path)["weighted_score"] == expected


@pytest.mark.parametrize("profile", ["default", "strict", "release", "experimental"])
@pytest.mark.parametrize("operation", [p1a.evaluate_trust, p1a.replay_trust])
def test_published_weights_reproduce_total_for_all_profiles(profile, operation, tmp_path):
    result = _evaluate(tmp_path, operation, profile)
    score = _read(tmp_path / "aete-score.json")
    signals = _read(tmp_path / "aete-signal-report.json")
    assert score["dimension_weights"] == signals["dimension_weights"] == WEIGHTS
    assert score["aggregation_method"] == signals["aggregation_method"] == "weighted_mean"
    expected = round(sum(score["dimensions"][key] * weight for key, weight in WEIGHTS.items()) / 500, 3)
    assert result["weighted_score"] == score["weighted_score"] == signals["weighted_score"] == expected
    assert f"Weighted score: `{expected:.3f}`" in (tmp_path / "trust-summary.md").read_text(encoding="utf-8")
    for payload, schema in [(score, "aete-score.schema.json"), (signals, "aete-signal-report.schema.json")]:
        assert not validate_schema_instance(payload, read_schema(schema))
    if operation is p1a.replay_trust:
        assert _read(tmp_path / "replay-report.json")["weighted_score"] == expected


def test_compare_does_not_cancel_provenance_loss_with_lower_weight_coverage_gain(tmp_path, capsys):
    bundle = _read(FIXTURE / "qeg-bundle.json")
    for node in bundle["nodes"]:
        if node["kind"] == "coverage":
            node["data"].pop("contexts", None)
            node["data"].pop("branch_hits", None)
    bundle["nodes"].extend([
        {"id": "finding:weight", "kind": "finding", "label": "finding", "data": {}, "sourceRefs": ["finding.json"]},
        {"id": "artifact:weight", "kind": "evidence_artifact", "label": "artifact",
         "data": {"path": "trace.zip", "sha256": "a" * 64}, "sourceRefs": ["manifest.json"]},
    ])
    for name in ("base", "head"):
        if name == "head":
            bundle["nodes"] = [node for node in bundle["nodes"] if node["kind"] != "evidence_artifact"]
            next(node for node in bundle["nodes"] if node["kind"] == "coverage")["data"]["branch_hits"] = {"main": 1}
        path = tmp_path / f"{name}.json"
        _write(path, bundle)
        assert p1a.evaluate_trust(path, FIXTURE / "qeg-export-report.json", tmp_path / name)["trust_status"] == "success"
    base, head = (_read(tmp_path / name / "aete-score.json") for name in ("base", "head"))
    assert sum(base["dimensions"].values()) == sum(head["dimensions"].values())
    assert base["weighted_score"] == 0.74 and head["weighted_score"] == 0.70
    result = p1a.compare_trust(tmp_path / "base", tmp_path / "head", tmp_path / "compare")
    assert result["compare_status"] == "regression" and result["trust_delta"] == -0.04
    assert result["doctor_finding_delta"] == 0
    assert cli.main(["compare", "--base", str(tmp_path / "base"), "--head", str(tmp_path / "head"),
                     "--out", str(tmp_path / "compare")]) == 0
    assert json.loads(capsys.readouterr().out)["trust_delta"] == -0.04


@pytest.mark.parametrize("side", ["base", "head"])
@pytest.mark.parametrize(("field", "value"), [
    ("weighted_score", "0.7"), ("weighted_score", True), ("weighted_score", None),
    ("weighted_score", float("nan")), ("weighted_score", -0.1), ("weighted_score", 1.1),
    ("weighted_score", 0.999), ("dimensions", None), ("dimensions", {}),
    ("dimension_weights", {**WEIGHTS, "provenance_integrity": 5}),
    ("aggregation_method", "arithmetic_mean"),
])
def test_invalid_score_inputs_fail_before_compare_output(field, value, side, tmp_path, capsys):
    for name in ("base", "head"):
        _evaluate(tmp_path / name)
    path = tmp_path / side / "aete-score.json"
    score = _read(path)
    score[field] = value
    _write(path, score)
    before = path.read_bytes()
    out = tmp_path / "compare"
    out.mkdir()
    sentinel = out / "compare-report.json"
    sentinel.write_bytes(b"previous comparison")
    saved = sentinel.read_bytes(), sentinel.stat().st_mtime_ns
    with pytest.raises(p1a.TrustError) as caught:
        p1a.compare_trust(tmp_path / "base", tmp_path / "head", out)
    assert caught.value.exit_code == 1
    assert field in str(caught.value) and str(path) in str(caught.value)
    assert cli.main(["compare", "--base", str(tmp_path / "base"), "--head", str(tmp_path / "head"), "--out", str(out)]) == 1
    captured = capsys.readouterr()
    assert not captured.out and "HATE-E-COMPARE:" in captured.err
    assert (sentinel.read_bytes(), sentinel.stat().st_mtime_ns) == saved
    assert list(out.iterdir()) == [sentinel] and path.read_bytes() == before


@pytest.mark.parametrize("value", [True, 2, "3", None])
def test_comparison_rejects_values_outside_the_discrete_dimension_rubric(value, tmp_path):
    _evaluate(tmp_path / "base")
    path = tmp_path / "base" / "aete-score.json"
    score = _read(path)
    score["dimensions"]["coverage_adequacy"] = value
    _write(path, score)
    with pytest.raises(p1a.TrustError, match="dimensions.coverage_adequacy"):
        p1a.compare_trust(tmp_path / "base", tmp_path / "base", tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_legacy_scores_require_replay_when_total_disagrees_with_specified_weights(tmp_path):
    _evaluate(tmp_path / "base")
    path = tmp_path / "base" / "aete-score.json"
    score = _read(path)
    score.pop("dimension_weights", None)
    score.pop("aggregation_method", None)
    legacy = copy.deepcopy(score)
    legacy["weighted_score"] = round(sum(legacy["dimensions"].values()) / 40, 3)
    _write(path, legacy)
    with pytest.raises(p1a.TrustError, match="replay"):
        p1a.compare_trust(tmp_path / "base", tmp_path / "base", tmp_path / "out")
    assert not (tmp_path / "out").exists()
    # 追加metadataの有無ではなく、公開次元から再現できる総合スコアを検証する。
    _write(path, score)
    assert p1a.compare_trust(tmp_path / "base", tmp_path / "base", tmp_path / "out")["compare_status"] == "stable"


@pytest.mark.parametrize("field", ["dimensions", "dimension_weights", "weighted_score"])
def test_comparison_checks_number_tokens_before_float_rounding(field, tmp_path):
    _evaluate(tmp_path / "base")
    path = tmp_path / "base" / "aete-score.json"
    score = _read(path)
    if field == "dimensions":
        score[field]["provenance_integrity"] = "RAW_NUMBER"
        token = "1.00000000000000001"
    elif field == "dimension_weights":
        score[field]["provenance_integrity"] = "RAW_NUMBER"
        token = "20.00000000000000001"
    else:
        token = str(score[field]) + "00000000000000001"
        score[field] = "RAW_NUMBER"
    path.write_text(json.dumps(score).replace('"RAW_NUMBER"', token), encoding="utf-8")
    with pytest.raises(p1a.TrustError, match=field):
        p1a.compare_trust(tmp_path / "base", tmp_path / "base", tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_integral_float_dimensions_and_weight_notation_remain_supported(tmp_path):
    _evaluate(tmp_path / "base")
    path = tmp_path / "base" / "aete-score.json"
    score = _read(path)
    score["dimensions"] = {key: float(value) for key, value in score["dimensions"].items()}
    score["dimension_weights"] = {key: float(value) for key, value in WEIGHTS.items()}
    _write(path, score)
    assert p1a.compare_trust(tmp_path / "base", tmp_path / "base", tmp_path / "out")["compare_status"] == "stable"


@pytest.mark.parametrize("schema_name", ["aete-score.schema.json", "aete-signal-report.schema.json"])
@pytest.mark.parametrize("field", ["dimension_weights", "aggregation_method", "weighted_score"])
def test_public_schema_checks_declared_aggregation_fields(schema_name, field, tmp_path):
    _evaluate(tmp_path)
    score = _read(tmp_path / schema_name.replace(".schema", ""))
    score[field] = {"provenance_integrity": 1} if field == "dimension_weights" else "unknown" if field == "aggregation_method" else 1.1
    errors = validate_schema_instance(score, read_schema(schema_name))
    assert errors
