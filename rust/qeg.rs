mod gaps;
mod graph;
mod output;
mod sources;
use crate::{
    cli::Invocation,
    error::CommandFailure,
    io::{items, write_json},
    p0a::canonical_digest as digest,
    trust::{commit, count, normalize_fields, strict_json, strict_value},
};
use anyhow::{Context, Result, ensure};
use serde_json::{Value as V, json};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::Path,
};

const RUN: &str = "HATE-run.json";
const TEST: &str = "HATE-test-results.ndjson";
const COV: &str = "HATE-coverage.ndjson";
const ART: &str = "artifact-manifest.json";
const PRE: &str = "precheck-decision.json";
const DIFF: &str = "diff-risk-test.json";
const CONTRACT: &str = "HATE-contract.ndjson";
const MUT: &str = "HATE-mutation.ndjson";
const STRENGTH: &str = "HATE-evidence-strength.ndjson";
const SARIF: &str = "HATE-static.sarif";
const ID_FIELDS: [&str; 9] = [
    "framework",
    "file",
    "name",
    "classname",
    "class_name",
    "package",
    "parameters",
    "params",
    "identity_components",
];
const META: [&str; 9] = [
    "retry_index",
    "attempt_index",
    "retry_count",
    "matrix",
    "matrix_values",
    "shard_index",
    "shard_total",
    "shard_count",
    "flaky",
];
const OUTCOME: [&str; 6] = [
    "source_status",
    "wouldRun",
    "xfail",
    "xpass",
    "todo",
    "only",
];
fn s<'a>(v: &'a V, k: &str) -> &'a str {
    v[k].as_str().unwrap_or("")
}
fn text(v: &V) -> String {
    v.as_str()
        .map(str::to_owned)
        .unwrap_or_else(|| v.to_string())
}
fn alt<'a>(d: &'a V, keys: &[&str], default: &'a str) -> &'a str {
    keys.iter()
        .find_map(|k| d[k].as_str().filter(|v| !v.is_empty()))
        .unwrap_or(default)
}
fn get(d: &V, k: &str, default: V) -> V {
    d.get(k).cloned().unwrap_or(default)
}
fn project(d: &V, mut defaults: V) -> V {
    for (k, v) in defaults.as_object_mut().unwrap() {
        if let Some(src) = d.get(k) {
            *v = src.clone();
        }
    }
    defaults
}
fn merge_fields(target: &mut V, source: &V, fields: &[&str]) {
    for k in fields {
        if let Some(v) = source.get(k) {
            target[k] = v.clone()
        }
    }
}
fn hash(s: &str) -> String {
    hex::encode(Sha256::digest(s.as_bytes()))[..16].to_owned()
}
fn source(name: &str) -> String {
    if name == DIFF || name.starts_with("escaped-defects.") {
        format!("fixture:/{name}")
    } else {
        format!("fixture:/p0a/{name}")
    }
}
fn edge(kind: &str, a: &str, b: &str, files: &[&str], conf: &str, assume: &[&str]) -> V {
    json!({
        "kind": kind,
        "from": a,
        "to": b,
        "traceability": {
            "sourceRefs": files.iter().map(|n|source(n)).collect::<Vec<_>>(),
            "confidence": conf,
            "assumptions": assume,
        },
    })
}
fn node(kind: &str, id: &str, label: &str, data: V, file: &str) -> V {
    json!({"kind":kind,"id":id,"label":label,"data":data,"sourceRefs":[source(file)]})
}

struct Inputs {
    run: V,
    pre: V,
    diff: V,
    art: V,
    tests: Vec<V>,
    cov: Vec<V>,
    contract: Vec<V>,
    mutation: Vec<V>,
    strength: Vec<V>,
    sarif: V,
    life: V,
    defects: Vec<V>,
    defect_claims: Vec<V>,
    defect_file: Option<String>,
    has_diff: bool,
}
impl Inputs {
    fn id(&self) -> &str {
        s(&self.run, "run_id")
    }
    fn attempt(&self) -> &V {
        &self.run["run_attempt"]
    }
}
fn identity(row: &mut V, base: Option<&V>, required: bool, loc: &str) -> Result<()> {
    for field in ["run_id", "run_attempt", "commit_sha"] {
        let Some(v) = row.get(field) else {
            ensure!(!required, "{loc}.{field} is required");
            continue;
        };
        let normal=match field{"run_id"=>{ensure!(v.as_str().is_some_and(|v|!v.trim().is_empty()),"{loc}.{field}: must be a non-empty run identifier");v.clone()},"run_attempt"=>count(v,true).with_context(||format!("{loc}.{field}: must be a positive integer; booleans and fractional values are invalid"))?.clone(),_=>{ensure!(commit(v),"{loc}.{field}: must be a 7–64 character hexadecimal commit ID");json!(v.as_str().unwrap().to_lowercase())}};
        if let Some(b) = base {
            let expected = if field == "commit_sha" {
                json!(s(b, field).to_lowercase())
            } else {
                b[field].clone()
            };
            ensure!(
                expected == normal,
                "{loc}.{field} mismatch with HATE-run.json.{field}"
            );
        }
        if field == "run_attempt" {
            row[field] = normal;
        }
    }
    Ok(())
}
fn read_inputs(dir: &Path) -> Result<Inputs> {
    let p = dir.join("p0a");
    let missing: Vec<_> = [RUN, TEST, COV, ART, PRE, "record.json"]
        .into_iter()
        .filter(|n| !p.join(n).is_file())
        .collect();
    if !missing.is_empty() {
        return Err(CommandFailure {
            code: 2,
            diagnostic: format!(
                "HATE-E-EXPORT: Missing required P0a artifacts: {}",
                missing.join(", ")
            ),
        }
        .into());
    }
    let mut run = strict_json(&p.join(RUN), RUN)?;
    identity(&mut run, None, true, RUN)?;
    let base = run.clone();
    ensure!(
        run["payload"].is_object(),
        "{RUN}.payload must be a JSON object"
    );
    if let Some(ci) = run["payload"].get_mut("ci") {
        ensure!(ci.is_object(), "{RUN}.payload.ci must be a JSON object");
        identity(ci, Some(&base), false, "HATE-run.json.payload.ci")?;
    }
    let require = |file: &str| -> Result<V> {
        let mut v = strict_json(&p.join(file), file)?;
        identity(&mut v, Some(&base), true, file)?;
        if file != ART {
            ensure!(
                v["payload"].is_object(),
                "{file}.payload must be a JSON object"
            );
        }
        Ok(v)
    };
    let pre = require(PRE)?;
    let art = require(ART)?;
    require("record.json")?;
    let records = |name: &str| -> Result<Vec<V>> {
        let path = p.join(name);
        if !path.try_exists()? {
            return Ok(vec![]);
        }
        let mut rows = vec![];
        for (i, line) in fs::read_to_string(&path)?.lines().enumerate() {
            if line.trim().is_empty() {
                continue;
            }
            let mut v = strict_value(line, name)
                .with_context(|| format!("{}:{}", path.display(), i + 1))?;
            ensure!(v.is_object(), "{name}: record must be a JSON object");
            identity(
                &mut v,
                Some(&base),
                true,
                &format!("{name}: records[{}]", rows.len()),
            )?;
            ensure!(
                v["payload"].is_object(),
                "{name}.payload must be a JSON object"
            );
            if name == TEST {
                ensure!(
                    v.get("record_id")
                        .is_none_or(|id| id.as_str().is_some_and(|v| !v.trim().is_empty())),
                    "record_id must be a non-empty string"
                );
                let d = &mut v["payload"];
                ensure!(
                    !s(d, "canonical_test_id").trim().is_empty(),
                    "payload.canonical_test_id must be a non-empty string"
                );
                for k in ID_FIELDS {
                    if let Some(v) = d.get(k) {
                        ensure!(
                            if matches!(k, "parameters" | "params" | "identity_components") {
                                v.is_object()
                            } else {
                                v.is_string()
                            },
                            "invalid payload.{k}"
                        );
                    }
                }
                normalize_fields(d, true).with_context(|| format!("{name}:{}", i + 1))?;
            }
            rows.push(v);
        }
        Ok(rows)
    };
    let optional = |path: &Path| {
        if path.try_exists()? {
            strict_json(
                path,
                path.file_name().and_then(|v| v.to_str()).unwrap_or(""),
            )
        } else {
            Ok(json!({}))
        }
    };
    let mut diff = optional(&dir.join(DIFF))?;
    identity(&mut diff, Some(&base), false, DIFF)?;
    let mut sarif = optional(&p.join(SARIF))?;
    identity(&mut sarif, Some(&base), false, SARIF)?;
    let mut life = optional(&dir.join("risk-debt-lifecycle.json"))?;
    if let Some(list) = life.get_mut("items") {
        for item in list
            .as_array_mut()
            .context("risk-debt-lifecycle.json: $.items must be an array of objects")?
        {
            ensure!(item.is_object(), "lifecycle item must be an object");
            if let Some(age) = item.get("age_days") {
                ensure!(
                    count(age, false).is_some(),
                    "age_days must be a non-negative integer"
                );
            }
        }
    }
    let (defects, defect_claims, defect_file) = sources::defects(dir)?;
    Ok(Inputs {
        run,
        pre,
        art,
        diff,
        tests: records(TEST)?,
        cov: records(COV)?,
        contract: records(CONTRACT)?,
        mutation: records(MUT)?,
        strength: records(STRENGTH)?,
        sarif,
        life,
        defects,
        defect_claims,
        defect_file,
        has_diff: dir.join(DIFF).is_file(),
    })
}
fn authorize(pre: &V) -> Result<()> {
    let p = &pre["payload"];
    let dec = s(p, "decision");
    for key in [
        "decision",
        "exit_code",
        "dq_hits",
        "soft_gaps",
        "reasons",
        "qeg_export_allowed",
    ] {
        ensure!(
            p.get(key).is_some(),
            "precheck-decision.json: payload.{key}: required field is missing"
        );
    }
    ensure!(
        matches!(dec, "eligible" | "conditional" | "ineligible" | "hard_dq"),
        "invalid precheck decision"
    );
    let code = p["exit_code"].as_f64();
    ensure!(
        matches!(code, Some(0. | 2.)),
        "exit_code: must be the JSON integer 0 or 2"
    );
    ensure!(
        p["qeg_export_allowed"].is_boolean(),
        "qeg_export_allowed: must be a boolean"
    );
    for k in ["dq_hits", "soft_gaps", "reasons"] {
        ensure!(
            p[k].as_array()
                .is_some_and(|a| a.iter().all(|v| if k == "reasons" {
                    v.is_string()
                } else {
                    v.is_object()
                })),
            "invalid precheck {k}"
        );
    }
    let mut reasons = vec![];
    if matches!(dec, "ineligible" | "hard_dq") {
        reasons.push(format!("decision is {dec}"))
    }
    if p["qeg_export_allowed"] == false {
        reasons.push("qeg_export_allowed is false".into())
    }
    if code == Some(2.) {
        reasons.push("exit_code is 2".into())
    }
    if !items(&p["dq_hits"]).is_empty() {
        reasons.push("dq_hits is not empty".into())
    }
    if !reasons.is_empty() {
        return Err(CommandFailure{code:2,diagnostic:json!({
            "decision": dec,
            "reason": if dec=="hard_dq"{"P0a precheck disqualified".into()}else{reasons.join("; ")},
        }).to_string()}.into());
    }
    Ok(())
}

#[derive(Default)]
struct Graph {
    nodes: Vec<V>,
    edges: Vec<V>,
    claims: Vec<V>,
    unsafe_artifacts: Vec<V>,
    missing: Vec<V>,
}
pub fn run(call: &Invocation) -> Result<V> {
    let x = read_inputs(call.path("fixture"))?;
    authorize(&x.pre)?;
    let mut graph = Graph::default();
    graph::build(&x, &mut graph)?;
    output::write(&x, &mut graph, call.path("out"))
}
