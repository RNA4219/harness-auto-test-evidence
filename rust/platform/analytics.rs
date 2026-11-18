use super::{assess::truth, operating::*, *};
use crate::io::ascii_digest;
fn round(v: f64, places: usize) -> f64 {
    format!("{v:.places$}").parse().unwrap_or(v)
}
fn metrics(samples: &[Value]) -> Value {
    if samples.is_empty() {
        return json!({});
    }
    let sum = |k: &str| samples.iter().filter_map(|s| s[k].as_f64()).sum::<f64>();
    let avg = |k: &str| sum(k) / samples.len() as f64;
    let health: Vec<_> = samples
        .iter()
        .filter_map(|s| s["repo_health_score"].as_f64())
        .collect();
    let drift: Vec<_> = samples
        .iter()
        .filter_map(|s| Some((s["current_score"].as_f64()? - s["baseline_score"].as_f64()?).abs()))
        .collect();
    let optional = |v: &[f64]| {
        if v.is_empty() {
            None
        } else {
            Some(round(v.iter().sum::<f64>() / v.len() as f64, 4))
        }
    };
    let tests = sum("test_count");
    json!({"flake_rate":if tests==0.{None}else{Some(round(sum("flake_count")/tests,4))},"evidence_freshness":round((1.-avg("evidence_age_days")/30.).max(0.),4),
        "debt_age":round(avg("debt_age_days"),2),"repo_health_score":optional(&health),"baseline_drift":optional(&drift),
        "regression_cluster_count":samples.iter().filter_map(|s|s["regression_clusters"].as_i64()).sum::<i64>(),"manual_review_latency":round(avg("manual_review_latency_hours"),2)})
}
struct Window<'a> {
    q: Value,
    samples: Vec<Value>,
    excluded: Vec<Value>,
    src: &'a str,
}
impl Window<'_> {
    fn small(&self) -> bool {
        (self.samples.len() as i64) < self.q["min_sample_count"].as_i64().unwrap_or(2)
    }
    fn stale(&self) -> bool {
        self.samples
            .iter()
            .any(|s| s["data_age_days"].as_f64() > self.q["stale_after_days"].as_f64())
    }
    fn analytics(&self, id: &str) -> Value {
        let q = &self.q;
        let src = self.src;
        let m = metrics(&self.samples);
        let mut findings = Vec::new();
        if self.small() {
            findings.push(finding(
                "history_window_too_small",
                "Trend query sample_count is below min_sample_count.",
                src,
            ));
        }
        if q["actual_runtime_ms"].as_i64() > q["performance_budget_ms"].as_i64() {
            findings.push(finding(
                "history_query_budget_exceeded",
                "Trend query exceeded performance_budget_ms.",
                src,
            ));
        }
        if self.stale() {
            findings.push(finding(
                "history_stale_data",
                "Trend query includes samples older than stale_after_days.",
                src,
            ));
        }
        let missing: Vec<_> = items(&q["required_metrics"])
            .iter()
            .filter_map(Value::as_str)
            .filter(|k| m[*k].is_null())
            .collect();
        if !missing.is_empty() {
            findings.push(finding(
                "history_metric_source_missing",
                &format!(
                    "Trend query is missing metric sources: {}.",
                    missing.join(", ")
                ),
                src,
            ));
        }
        if self
            .samples
            .iter()
            .filter_map(|s| s["unexplained_regression_clusters"].as_i64())
            .sum::<i64>()
            != 0
        {
            findings.push(finding(
                "history_regression_cluster_unexplained",
                "Regression clusters require explanatory sourceRefs before pass.",
                src,
            ));
        }
        let reasons: BTreeSet<_> = self
            .excluded
            .iter()
            .filter_map(|x| x["reason"].as_str().filter(|s| !s.is_empty()))
            .collect();
        if !self.excluded.is_empty() && reasons.is_empty() {
            findings.push(finding(
                "history_metric_source_missing",
                "Excluded samples require exclusion reasons.",
                src,
            ));
        }
        let mut window = select(
            q,
            &[
                "window_start",
                "window_end",
                "repo_filter",
                "suite_filter",
                "aggregation_level",
                "performance_budget_ms",
            ],
        );
        merge(
            &mut window,
            json!({"record_type":"history-trend-window","sample_count":self.samples.len(),"excluded_count":self.excluded.len(),"exclusion_reasons":reasons,
            "sourceRefs":self.samples.iter().map(|s|&s["sourceRef"]).collect::<Vec<_>>()}),
        );
        json!({"schema_version":"HATE/v1","record_type":"history-analytics-report","report_id":id,"overall_status":if findings.is_empty(){"pass"}else{"hold"},
            "readiness_effect":if findings.is_empty(){"none"}else{"hold"},"query":q,"trend_window":window,"result":{"record_type":"history-analytics-result",
            "metrics":m,"sample_count":self.samples.len(),"excluded_count":self.excluded.len(),"exclusion_reasons":reasons,"sourceRefs":[src]},"findings":findings,
            "summary":{"metric_count":m.as_object().unwrap().len(),"sample_count":self.samples.len(),"excluded_count":self.excluded.len(),"finding_count":findings.len(),
            "aggregation_level":q["aggregation_level"],"performance_budget_ms":q["performance_budget_ms"],"actual_runtime_ms":q["actual_runtime_ms"]},"sourceRefs":[src]})
    }
    fn plan(&self, id: &str, previous: &Value) -> Value {
        let mut entries = Vec::new();
        let mut current = BTreeSet::new();
        let prev = items(&previous["entries"]);
        for sample in &self.samples {
            let hash = ascii_digest(&select(
                sample,
                &[
                    "run_id",
                    "repo_id",
                    "suite_id",
                    "run_started_at",
                    "test_count",
                    "flake_count",
                    "evidence_age_days",
                    "debt_age_days",
                    "repo_health_score",
                    "baseline_score",
                    "current_score",
                    "regression_clusters",
                    "manual_review_latency_hours",
                ],
            ));
            let mut key = select(sample, &["repo_id", "suite_id", "run_id"]);
            key["aggregation_level"] = self.q["aggregation_level"].clone();
            let key = ascii_digest(&key);
            let prior = prev.iter().rev().find(|p| {
                p["cache_key"] == key
                    && p["sample_fingerprint"] == hash
                    && truth(&p["materialized_ref"])
            });
            entries.push(json!({"record_type":"history-materialization-entry","sample_id":sample["run_id"],"repo_id":sample["repo_id"],"suite_id":sample["suite_id"],"cache_key":key,
                "sample_fingerprint":hash,"materialization_action":if prior.is_some(){"reuse"}else{"recompute"},"materialized_ref":prior.map(|p|p["materialized_ref"].clone()).unwrap_or_else(||json!(format!("history-cache://{key}"))),"sourceRef":sample["sourceRef"]}));
            current.insert(key);
        }
        for p in prev {
            let key = field(p, "cache_key", "");
            if key.is_empty() || !current.insert(key.into()) {
                continue;
            }
            let mut entry = json!({"record_type":"history-materialization-entry","materialization_action":"drop","sourceRef":field(p,"sourceRef",field(p,"sample_id","previous-manifest"))});
            for k in [
                "sample_id",
                "repo_id",
                "suite_id",
                "cache_key",
                "sample_fingerprint",
                "materialized_ref",
            ] {
                entry[k] = json!(field(p, k, ""));
            }
            entries.push(entry);
        }
        let mut findings = Vec::new();
        let src = self.src;
        for (fail, code, msg) in [
            (
                self.small(),
                "history_window_too_small",
                "Incremental plan sample_count is below min_sample_count.",
            ),
            (
                self.stale(),
                "history_stale_data",
                "Incremental plan includes stale samples.",
            ),
            (
                entries
                    .iter()
                    .any(|e| !truth(&e["cache_key"]) || !truth(&e["sample_fingerprint"])),
                "history_materialization_key_missing",
                "Materialization entries require cache_key and sample_fingerprint.",
            ),
            (
                self.excluded.iter().any(|e| !truth(&e["reason"])),
                "history_metric_source_missing",
                "Excluded samples require exclusion reasons.",
            ),
        ] {
            if fail {
                findings.push(finding(code, msg, src));
            }
        }
        let count = |action: &str| {
            entries
                .iter()
                .filter(|e| e["materialization_action"] == action)
                .count()
        };
        let counts = json!({"reused_count":count("reuse"),"recompute_count":count("recompute"),"drop_count":count("drop")});
        let mut inc = counts.clone();
        merge(
            &mut inc,
            json!({"record_type":"history-incremental-materialization","strategy":"sample-fingerprint","excluded_count":self.excluded.len(),"sourceRefs":[src]}),
        );
        let mut summary = counts;
        merge(
            &mut summary,
            json!({"entry_count":entries.len(),"sample_count":self.samples.len(),"finding_count":findings.len()}),
        );
        json!({"schema_version":"HATE/v1","record_type":"history-materialization-plan","plan_id":id,"readiness_effect":if findings.is_empty(){"none"}else{"hold"},
          "query_fingerprint":ascii_digest(&select(&self.q,&["window_start","window_end","repo_filter","suite_filter","aggregation_level","required_metrics"])),
          "incremental":inc,"entries":entries,"excluded":self.excluded,"findings":findings,"summary":summary,"sourceRefs":[src]})
    }
}
fn manifest(plan: &Value, path: &Path) -> Result<Value> {
    let id = field(plan, "plan_id", "history-materialization-manifest");
    let refs = &plan["sourceRefs"];
    let rows: Vec<_> = items(&plan["entries"])
        .iter()
        .filter(|e| e["materialization_action"] != "drop")
        .map(|e| {
            select(
                e,
                &[
                    "record_type",
                    "cache_key",
                    "sample_id",
                    "repo_id",
                    "suite_id",
                    "sample_fingerprint",
                    "materialized_ref",
                    "sourceRefs",
                ],
            )
        })
        .collect();
    let mut m = json!({"schema_version":"HATE/v1","record_type":"history-materialization-manifest","plan_id":id,"readiness_effect":plan["readiness_effect"],
        "query_fingerprint":plan["query_fingerprint"],"entries":rows,"sourceRefs":refs});
    merge(&mut m, envelope(plan, id, refs));
    contract(&mut m, refs);
    write_json(path, &m)?;
    let mut artifact = json!({"schema_version":"HATE/v1","record_type":"history-materialization-manifest-artifact","readiness_effect":m["readiness_effect"],
      "artifact_path":path,"entry_count":rows.len(),"sourceRefs":refs});
    merge(&mut artifact, envelope(&m, &format!("{id}:artifact"), refs));
    Ok(artifact)
}
pub(super) fn run(call: &Invocation) -> Result<Value> {
    let path = call.path("input");
    let data = object(path)?;
    let input = data.get("input").unwrap_or(&data);
    let src = path.to_string_lossy();
    let window = Window {
        q: normalize("query", input.get("query").unwrap_or(input))?,
        samples: items(&input["samples"])
            .iter()
            .map(|v| normalize("sample", v))
            .collect::<Result<_>>()?,
        excluded: items(&input["excluded"])
            .iter()
            .map(|v| normalize("exclusion", v))
            .collect::<Result<_>>()?,
        src: &src,
    };
    let (id, mut value) = if call.command.ends_with("analytics") {
        let id = field(
            &data,
            "fixture_id",
            field(&data, "report_id", "platform-history-analytics"),
        );
        (id, window.analytics(id))
    } else {
        let id = field(
            &data,
            "fixture_id",
            field(&data, "plan_id", "platform-history-materialization"),
        );
        let previous = call
            .optional_path("previous_manifest")
            .map(|p| object(&p))
            .transpose()?
            .unwrap_or(Value::Null);
        (id, window.plan(id, &previous))
    };
    let refs = json!([src]);
    merge(&mut value, envelope(input, id, &refs));
    contract(&mut value, &refs);
    if let Some(path) = call.optional_path("out") {
        write_json(&path, &value)?;
    }
    if let Some(path) = call.optional_path("manifest_out") {
        value["manifest_artifact"] = manifest(&value, &path)?;
    }
    Ok(value)
}
