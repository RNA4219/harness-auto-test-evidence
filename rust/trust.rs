mod advice;
mod analysis;
mod assessment;
mod execution;
mod inputs;

pub(crate) use inputs::{commit, count, normalize_fields, strict_json, strict_value};

use crate::{
    cli::Invocation,
    io::{items, object, stable_ref, write_json},
    p0a::{Document, canonical_digest as digest},
};
use anyhow::{Context, Result, ensure};
use serde_json::{Value as V, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    path::Path,
};

const WEIGHTS: [(&str, i64); 8] = [
    ("provenance_integrity", 20),
    ("determinism_flakiness", 15),
    ("traceability_lineage", 15),
    ("oracle_strength", 15),
    ("change_relevance", 15),
    ("coverage_adequacy", 10),
    ("cross_signal_corroboration", 5),
    ("freshness_profile_conformance", 5),
];
fn s<'a>(v: &'a V, k: &str) -> &'a str {
    v[k].as_str().unwrap_or("")
}
fn nonempty(v: &V) -> bool {
    match v {
        V::Null => false,
        V::Bool(b) => *b,
        V::Array(a) => !a.is_empty(),
        V::Object(o) => !o.is_empty(),
        V::String(s) => !s.is_empty(),
        V::Number(n) => n.as_f64() != Some(0.0),
    }
}
fn overlay(mut a: V, b: &V) -> V {
    if let Some(m) = b.as_object() {
        a.as_object_mut().unwrap().extend(m.clone());
    }
    a
}
fn sorted_refs<'a>(refs: impl Iterator<Item = &'a V>) -> Vec<&'a str> {
    refs.filter_map(V::as_str)
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect()
}

pub fn run(call: &Invocation) -> Result<V> {
    let category = match call.command.as_str() {
        "trust evaluate" => "TRUST",
        other => other,
    };
    if matches!(call.command.as_str(), "trust evaluate" | "replay") {
        for (key, label) in [("bundle", "QEG bundle"), ("report", "QEG export report")] {
            let path = call.path(key);
            if !path.exists() {
                return Err(crate::error::CommandFailure {
                    code: 2,
                    diagnostic: format!(
                        "HATE-E-{}: {label} not found: {}",
                        category.to_uppercase(),
                        path.display()
                    ),
                }
                .into());
            }
        }
    }
    dispatch(call).map_err(|e| {
        crate::error::CommandFailure {
            code: 1,
            diagnostic: format!("HATE-E-{}: {e:#}", category.to_uppercase()),
        }
        .into()
    })
}

fn dispatch(call: &Invocation) -> Result<V> {
    if call.command == "compare" {
        return compare(call);
    }
    let input = inputs::read(call)?;
    match call.command.as_str() {
        "explain" | "recommend" => advice::run(call, &input),
        _ => assessment::run(call, &input),
    }
}

fn read_score(path: &Path) -> Result<V> {
    use bigdecimal::BigDecimal;
    use std::str::FromStr;
    let doc = Document::read(path, true)
        .with_context(|| format!("cannot read JSON input {}", path.display()))?;
    let number = |key: &str| {
        doc.token(&format!("{}.{key}", path.file_name()?.to_str()?))
            .and_then(|text| BigDecimal::from_str(text).ok())
    };
    let score = &doc.value;
    let dim = score["dimensions"]
        .as_object()
        .context("missing AETE dimensions")?;
    ensure!(
        dim.len() == WEIGHTS.len() && WEIGHTS.iter().all(|(name, _)| dim.contains_key(*name)),
        "{}: dimensions must contain exactly the eight AETE dimensions",
        path.display()
    );
    let mut sum = 0;
    for (name, weight) in WEIGHTS {
        let v = number(&format!("dimensions.{name}"))
            .and_then(|n| [0, 1, 3, 5].into_iter().find(|v| n == BigDecimal::from(*v)))
            .with_context(|| {
                format!(
                    "{}: dimensions.{name} must be a numeric rubric value (0, 1, 3, 5)",
                    path.display()
                )
            })?;
        sum += v * weight;
        if let Some(weights) = score.get("dimension_weights") {
            ensure!(
                weights.as_object().is_some_and(|m| m.len() == 8)
                    && number(&format!("dimension_weights.{name}"))
                        == Some(BigDecimal::from(weight)),
                "{}: dimension_weights do not match the supported AETE weights; run hate replay",
                path.display()
            );
        }
    }
    ensure!(
        score
            .get("aggregation_method")
            .is_none_or(|v| v == "weighted_mean"),
        "aggregation_method is unsupported; run hate replay"
    );
    let actual = number("weighted_score")
        .filter(|v| v >= &BigDecimal::from(0) && v <= &BigDecimal::from(1))
        .context("weighted_score must be a finite number between 0 and 1")?;
    let expected = BigDecimal::from(sum) / BigDecimal::from(500);
    ensure!(
        actual == expected,
        "{}: weighted_score disagrees with dimensions and weights (expected {expected:.3}); run hate replay with the original bundle and report before comparing",
        path.display()
    );
    Ok(doc.value)
}

fn compare(call: &Invocation) -> Result<V> {
    let base = call.path("base");
    let head = call.path("head");
    let before = read_score(&base.join("aete-score.json"))?;
    let after = read_score(&head.join("aete-score.json"))?;
    let pair = |name: &str| -> Result<(V, V)> {
        Ok((object(&base.join(name))?, object(&head.join(name))?))
    };
    use bigdecimal::{Signed, Zero, num_bigint::BigInt};
    let count_delta = |file: &str, field: &str, optional: bool| -> Result<BigInt> {
        let (a, b) = pair(file)?;
        let get = |v: &V| -> Result<BigInt> {
            match v["summary"].get(field) {
                None if optional => Ok(BigInt::zero()),
                Some(v) => coerced_integer(v).context("invalid summary count"),
                None => anyhow::bail!("missing {field}"),
            }
        };
        Ok(get(&b)? - get(&a)?)
    };
    let doctor = count_delta("doctor-report.json", "finding_count", false)?;
    let retries = count_delta("retry-aggregation.json", "aggregate_count", false)?;
    let (old_profile, new_profile) = pair("profile-report.json")?;
    let unsafe_delta = count_delta("artifact-resolver-map.json", "unsafe_count", true)?;
    let duplicates = count_delta("canonical-identity-index.json", "has_duplicates", true)?;
    let (old_signal, new_signal) = pair("aete-signal-report.json")?;
    let delta = ((after["weighted_score"].as_f64().unwrap()
        - before["weighted_score"].as_f64().unwrap())
        * 1000.)
        .round()
        / 1000.;
    let mut dimensions = BTreeMap::new();
    let mut signals = BTreeMap::new();
    for (name, _) in WEIGHTS {
        dimensions.insert(
            name,
            after["dimensions"][name].as_f64().unwrap() as i64
                - before["dimensions"][name].as_f64().unwrap() as i64,
        );
        let signal = |r: &V| {
            items(&r["signals"])
                .iter()
                .find(|v| v["dimension"] == name)
                .and_then(|v| coerced_integer(&v["score"]))
                .unwrap_or_default()
        };
        signals.insert(
            name,
            json_integer(&(signal(&new_signal) - signal(&old_signal))),
        );
    }
    let regression = delta < 0.
        || doctor.is_positive()
        || unsafe_delta.is_positive()
        || duplicates.is_positive();
    let (doctor, retries, unsafe_delta, duplicates) = (
        json_integer(&doctor),
        json_integer(&retries),
        json_integer(&unsafe_delta),
        json_integer(&duplicates),
    );
    let report = json!({"schema_version":"HATE/v1","record_type":"compare_report","base_ref":stable_ref(base,true)?,"head_ref":stable_ref(head,true)?,
        "trust_delta":delta,"doctor_finding_delta":doctor,"retry_aggregate_delta":retries,"resolver_unsafe_delta":unsafe_delta,"identity_duplicate_delta":duplicates,
        "profile_hash_changed":old_profile["profile_hash"]!=new_profile["profile_hash"],"dimension_delta":dimensions,"signal_delta":signals,
        "regression":regression,"release_gate_override":false,"publish_gate_override":false});
    write_json(&call.path("out").join("compare-report.json"), &report)?;
    Ok(
        json!({"compare_status":if regression {"regression"} else {"stable"},"exit_code":0,"generated":["compare-report.json"],"trust_delta":delta,
        "doctor_finding_delta":doctor,"resolver_unsafe_delta":unsafe_delta,"publish_gate_override":false}),
    )
}
pub(crate) use analysis::validator as bundle_validator;
pub(crate) use integers::{coerced_integer, json_integer};
mod integers;
