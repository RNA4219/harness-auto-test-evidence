use super::{Run, first, items, name, numbers::stringify, opt_object, s, slug};
use anyhow::{Result, bail, ensure};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::Path,
};

fn list(v: &Value) -> Vec<String> {
    if let Some(s) = v.as_str() {
        return (!s.is_empty()).then(|| s.to_owned()).into_iter().collect();
    }
    items(v)
        .iter()
        .map(stringify)
        .filter(|s| !s.is_empty())
        .collect()
}
fn pick<'a>(values: &[&'a Value]) -> Option<&'a Value> {
    values.iter().copied().find(|v| match v {
        Value::Null => false,
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64() != Some(0.0),
        _ => true,
    })
}
fn text(values: &[&Value], default: &str) -> String {
    pick(values)
        .map(stringify)
        .unwrap_or_else(|| default.into())
}
fn parse_lines(raw: &str) -> Result<Vec<Value>> {
    raw.lines()
        .filter(|l| !l.trim().is_empty())
        .map(|l| Ok(serde_json::from_str(l)?))
        .collect()
}
pub fn mutations(run: &Run, path: &Path) -> Result<Vec<Value>> {
    let text_input = fs::read_to_string(path)?;
    let data: Value = match serde_json::from_str(&text_input) {
        Ok(v) => v,
        Err(_) => Value::Array(parse_lines(&text_input)?),
    };
    ensure!(
        data.is_object() || data.is_array(),
        "Stryker input must be JSON object, array, or NDJSON"
    );
    let entries = if data.is_object() {
        vec![&data]
    } else {
        items(&data).iter().filter(|v| v.is_object()).collect()
    };
    let mut records = Vec::new();
    for (e, entry) in entries.into_iter().enumerate() {
        let hate = entry["record_type"] == "mutation_evidence";
        let mutations = pick(&[&entry["mutants"], &entry["mutations"]]);
        let rows = if hate {
            vec![&entry["payload"]]
        } else if let Some(obj) = mutations.and_then(Value::as_object) {
            obj.values().collect()
        } else {
            mutations.map(items).unwrap_or_default().iter().collect()
        };
        for (i, m) in rows.into_iter().enumerate() {
            ensure!(m.is_object(), "Stryker mutant must be an object");
            let id = if hate {
                text(
                    &[&m["mutation_id"], &m["mutant_id"], &m["id"]],
                    &format!("stryker-mutant-{}", records.len() + 1),
                )
            } else {
                text(
                    &[&m["id"]],
                    &format!("stryker-mutant-{}", records.len() + 1),
                )
            };
            let raw = s(&m["status"]).to_lowercase().replace('-', "_");
            let status = match raw.as_str() {
                "nocoverage" => "no_coverage",
                "compileerror" => "compile_error",
                "runtimeerror" => "runtime_error",
                "killed" | "survived" | "ignored" | "timeout" | "no_coverage" | "compile_error"
                | "runtime_error" => &raw,
                _ => bail!("unknown mutant status: {}", stringify(&m["status"])),
            };
            let loc = if hate {
                pick(&[&m["start_line"], &m["line"]])
            } else {
                pick(&[&m["line"], &m["location"]["start"]["line"]])
            };
            let line = loc
                .map(|v| stringify(v).parse::<i64>())
                .transpose()?
                .unwrap_or(1);
            let source = if hate {
                format!("{}#line={}", name(path), e + 1)
            } else {
                format!("{}#entry={e}/mutant={i}", name(path))
            };
            let payload = json!({"mutation_id":id,"file":text(&[&m["file"],&m["sourceFilePath"]],"").replace('\\',"/"),
              "line":line,"status":status,"mutator":text(&[&m["mutator"],&m["mutatorName"]],"unknown"),"covered_by":list(pick(&[&m["coveredBy"],&m["covered_by"]]).unwrap_or(&Value::Null)),
              "killed_by":list(pick(&[&m["killedBy"],&m["killed_by"]]).unwrap_or(&Value::Null)),"sourceRef":source});
            records.push(run.record("mutation_evidence", "mutation", &slug(&id), payload));
        }
    }
    Ok(records)
}
fn ratio(a: usize, b: usize) -> Value {
    json!(((a as f64 / b as f64) * 10000.).round_ties_even() / 10000.)
}
pub fn build(run: &Run, root: &Path, tests: &[Value], mutations: &[Value]) -> Result<Vec<Value>> {
    let settings = opt_object(&root.join("evidence-strength-config.json"))?;
    let limit = settings
        .get("recent_run_limit")
        .or_else(|| settings.get("recent_runs"))
        .and_then(|v| v.as_i64().or_else(|| v.as_str()?.parse().ok()))
        .unwrap_or(10)
        .max(2) as usize;
    let path = first(
        root,
        &[
            "run-history.json",
            "run-history.jsonl",
            "test-history.json",
            "test-history.jsonl",
        ],
    );
    let mut history = BTreeMap::<String, Vec<String>>::new();
    if let Some(path) = &path {
        let raw = fs::read_to_string(path)?;
        let entries = if raw.trim().is_empty() {
            Vec::new()
        } else if path.extension().is_some_and(|s| s == "jsonl") {
            parse_lines(&raw)?
        } else {
            let data: Value = serde_json::from_str(&raw)?;
            if data.is_array() {
                items(&data).to_vec()
            } else if data.is_object() {
                items(data.get("runs").unwrap_or(&data["history"])).to_vec()
            } else {
                bail!(
                    "{} must contain a JSON object, array, or JSONL entries",
                    name(path)
                )
            }
        };
        for e in &entries[entries.len().saturating_sub(limit)..] {
            let empty = json!([]);
            let values = e
                .get("tests")
                .or_else(|| e.get("test_results"))
                .unwrap_or(&empty);
            let rows = if values.is_array() {
                items(values)
            } else {
                std::slice::from_ref(e)
            };
            for r in rows {
                let id = text(&[&r["test_id"], &r["canonical_test_id"]], "");
                let status = text(&[&r["status"], &r["outcome"]], "").to_lowercase();
                if id.is_empty() {
                    continue;
                }
                let normalized = match status.as_str() {
                    "passed" | "pass" | "success" => "passed",
                    "failed" | "fail" | "failure" | "error" => "failed",
                    _ => continue,
                };
                history.entry(id).or_default().push(normalized.into());
            }
        }
    }
    let mut totals = BTreeMap::<String, (usize, usize)>::new();
    for r in mutations {
        let p = &r["payload"];
        let status = s(&p["status"]);
        if !matches!(status, "killed" | "timeout" | "survived" | "no_coverage") {
            continue;
        }
        let kills = list(&p["killed_by"]);
        let ids: BTreeSet<_> = list(&p["covered_by"])
            .into_iter()
            .chain(kills.iter().cloned())
            .collect();
        for id in ids {
            let detected = matches!(status, "killed" | "timeout") || kills.contains(&id);
            let (hit, total) = totals.entry(id).or_default();
            *total += 1;
            *hit += usize::from(detected);
        }
    }
    let current: BTreeMap<_, _> = tests
        .iter()
        .map(|r| {
            (
                s(&r["payload"]["canonical_test_id"]).to_owned(),
                s(&r["payload"]["status"]),
            )
        })
        .collect();
    let mut ids: BTreeSet<_> = current
        .keys()
        .chain(history.keys())
        .chain(totals.keys())
        .cloned()
        .collect();
    if ids.is_empty() {
        ids.insert("unknown".into());
    }
    let mut records = Vec::new();
    for id in ids {
        let mut statuses = history.remove(&id).unwrap_or_default();
        if let Some(&status) = current.get(&id)
            && matches!(status, "passed" | "failed" | "error")
        {
            statuses.push(if status == "error" { "failed" } else { status }.into());
        }
        let statuses = &statuses[statuses.len().saturating_sub(limit)..];
        let flake = if statuses.len() < 2 {
            json!("unknown")
        } else {
            ratio(
                statuses.windows(2).filter(|w| w[0] != w[1]).count(),
                statuses.len() - 1,
            )
        };
        let mutation = totals
            .get(&id)
            .map(|(h, t)| ratio(*h, *t))
            .unwrap_or(json!("unknown"));
        let mut inputs = Vec::new();
        if let Some(path) = &path {
            inputs.push(json!({"kind":"run_history","sourceRef":name(path)}));
        }
        if current.contains_key(&id) {
            inputs.push(json!({"kind":"test_results","sourceRef":"HATE-test-results.ndjson"}));
        }
        if !mutations.is_empty() {
            inputs.push(json!({"kind":"mutation","sourceRef":"HATE-mutation.ndjson"}));
        }
        if inputs.is_empty() {
            inputs.push(json!({"kind":"unknown","sourceRef":"none"}));
        }
        records.push(run.record("evidence_strength","evidence-strength",&slug(&id),json!({"test_id":id,"flake_score":flake,"mutation_score":mutation,"sample_size":statuses.len(),"computed_at":run.time,"inputs":inputs})));
    }
    Ok(records)
}
