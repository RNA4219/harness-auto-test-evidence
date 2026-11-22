mod analytics;
mod assess;
mod baseline;
mod html;
mod notify;
mod operating;
mod plugin;
mod schedule;
use crate::{
    cli::Invocation,
    io::{items, object, parent, write_json},
};
use anyhow::{Context, Result, ensure};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::Path,
};

pub(super) fn field<'a>(v: &'a Value, key: &str, default: &'a str) -> &'a str {
    v[key].as_str().filter(|s| !s.is_empty()).unwrap_or(default)
}
pub(super) fn refs(v: &Value, singular: bool) -> Vec<String> {
    let names = if singular {
        &["sourceRefs", "source_refs", "sourceRef"][..]
    } else {
        &["sourceRefs", "source_refs"][..]
    };
    for name in names {
        let list = &v[name];
        if let Some(s) = list.as_str().filter(|s| !s.is_empty()) {
            return vec![s.into()];
        }
        let values = items(list);
        if !values.is_empty() {
            return values
                .iter()
                .filter_map(|item| item.as_str().map(str::to_owned))
                .collect();
        }
    }
    Vec::new()
}
fn self_generated(v: &Value) -> bool {
    matches!(
        v["record_type"].as_str().unwrap_or(""),
        "platform-assignment-report"
            | "platform-debt-report"
            | "platform-findings-report"
            | "platform-html-report"
            | "platform-review-report"
            | "platform-score-report"
            | "platform-triage-report"
            | "platform-verdict-evaluation-report"
            | "history-analytics-report"
            | "history-materialization-plan"
            | "history-materialization-manifest"
            | "notification-delivery-report"
            | "notification-routing-plan"
            | "baseline-review-packet"
    )
}
fn reports(path: &Path, exclude_self: bool) -> Result<Vec<Value>> {
    ensure!(
        path.try_exists()?,
        "platform input not found: {}",
        path.display()
    );
    if path.is_file() {
        return Ok(vec![object(path)?]);
    }
    let mut paths = Vec::new();
    for entry in fs::read_dir(path)? {
        let p = entry?.path();
        if p.extension().is_some_and(|ext| {
            if cfg!(windows) {
                ext.eq_ignore_ascii_case("json")
            } else {
                ext == "json"
            }
        }) {
            paths.push(p);
        }
    }
    paths.sort_by_cached_key(|p| {
        if cfg!(windows) {
            p.to_string_lossy().to_lowercase()
        } else {
            p.to_string_lossy().into_owned()
        }
    });
    let mut rows = Vec::new();
    for p in paths {
        let report = object(&p)?;
        if !exclude_self || !self_generated(&report) {
            rows.push(report);
        }
    }
    Ok(rows)
}

fn project(reports: &[Value], kind: &str, input: &Path) -> Result<Value> {
    let (keys, count_key) = match kind {
        "findings" => (&["findings"][..], "finding_count"),
        "debt" => (
            &["risk_debt", "risk_debts", "debt", "debts"][..],
            "debt_count",
        ),
        _ => (
            &[
                "manual_review_requests",
                "manual_reviews",
                "review_requests",
                "requiredHumanReview",
            ][..],
            "review_count",
        ),
    };
    let mut records = Vec::new();
    for report in reports {
        let reference = field(report, "report_id", field(report, "record_type", "report"));
        for key in keys {
            let value = &report[key];
            let entries = if value.is_object() && kind != "findings" {
                std::slice::from_ref(value)
            } else {
                items(value)
            };
            for entry in entries {
                if !entry.is_object() && kind != "findings" {
                    continue;
                }
                let mut map = entry
                    .as_object()
                    .context("finding must be an object")?
                    .clone();
                let mut source = refs(entry, false);
                if source.is_empty() {
                    source = refs(report, false);
                }
                if kind == "findings" {
                    if source.is_empty() {
                        source.push(reference.into());
                    }
                    map.insert(
                        "report_id".into(),
                        report.get("report_id").cloned().unwrap_or(json!(reference)),
                    );
                    map.insert(
                        "record_type".into(),
                        report.get("record_type").cloned().unwrap_or(json!("")),
                    );
                }
                map.entry("sourceRefs").or_insert(json!(source));
                records.push(Value::Object(map));
            }
        }
    }
    let hold = records.iter().any(|v| {
        matches!(
            field(v, "readiness_effect", field(v, "effect", ""))
                .to_lowercase()
                .as_str(),
            "hold" | "blocked" | "hard_dq"
        ) || matches!(
            field(v, "severity", "").to_lowercase().as_str(),
            "high" | "critical"
        )
    });
    Ok(
        json!({"schema_version":"HATE/v1","record_type":format!("platform-{kind}-report"),"overall_status":if hold{"hold"}else{"pass"},
        "items":records,"summary":{(count_key):records.len()},"sourceRefs":[input]}),
    )
}
fn report_map(path: &Path) -> Result<BTreeMap<String, Value>> {
    let report = object(path)?;
    let key = |v: &Value| {
        format!(
            "{}:{}",
            field(v, "repo_id", field(v, "report_id", "report")),
            field(v, "suite_id", "default")
        )
    };
    let mut map = BTreeMap::new();
    if report["record_type"] == "real-repo-evaluation-run-report" {
        for name in items(&report["generated_reports"])
            .iter()
            .filter_map(Value::as_str)
        {
            let child = parent(path).join(name);
            if child.try_exists()? {
                let v = object(&child)?;
                map.insert(key(&v), v);
            }
        }
    }
    if map.is_empty() {
        map.insert(key(&report), report);
    }
    Ok(map)
}
fn compare(call: &Invocation) -> Result<Value> {
    let base = call.path("base");
    let head = call.path("head");
    let before = report_map(base)?;
    let after = report_map(head)?;
    let keys: BTreeSet<_> = before.keys().chain(after.keys()).collect();
    let mut deltas = Vec::new();
    let mut findings = Vec::new();
    for key in keys {
        let changes = match (before.get(key), after.get(key)) {
            (None, _) => vec!["added"],
            (_, None) => vec!["removed"],
            (Some(left), Some(right)) => {
                let mut changes = Vec::new();
                for (name, pointer) in [
                    ("overall_status", "/overall_status"),
                    ("record_count", "/current/record_count"),
                    ("runtime_ms", "/current/runtime_ms"),
                    ("runner_dialect", "/current/runner_dialect"),
                ] {
                    if left.pointer(pointer).unwrap_or(&Value::Null)
                        != right.pointer(pointer).unwrap_or(&Value::Null)
                    {
                        changes.push(name);
                    }
                }
                for (trigger, code) in [
                    (
                        left["overall_status"] == "pass" && right["overall_status"] != "pass",
                        "platform_compare_status_regression",
                    ),
                    (
                        left["current"]["record_count"].as_i64().unwrap_or(0)
                            > right["current"]["record_count"].as_i64().unwrap_or(0),
                        "platform_compare_record_count_drop",
                    ),
                ] {
                    if trigger {
                        findings.push(json!({"code":code,"severity":"high","readiness_effect":"hold","message":format!("{code}: {key}"),"sourceRefs":refs(right,false)}));
                    }
                }
                changes
            }
        };
        if !changes.is_empty() {
            deltas.push(json!({"key":key,"changes":changes}));
        }
    }
    Ok(
        json!({"schema_version":"HATE/v1","record_type":"platform-comparison-report","overall_status":if findings.is_empty(){"pass"}else{"hold"},
        "readiness_effect":if findings.is_empty(){"none"}else{"hold"},"base":base,"head":head,"deltas":deltas,"findings":findings,
        "summary":{"delta_count":deltas.len(),"finding_count":findings.len()},"sourceRefs":[base,head]}),
    )
}
pub fn run(call: &Invocation) -> Result<Value> {
    let value = match call.command.as_str() {
        "platform findings" | "platform debt" | "platform review" => {
            let path = call.path("input");
            return project(
                &reports(path, true)?,
                call.command.trim_start_matches("platform "),
                path,
            );
        }
        "platform compare" => compare(call)?,
        "platform report html" => return html::run(call),
        "platform assign" => schedule::assign(call)?,
        "platform plugin run" => plugin::run(call)?,
        "platform policy explain" => {
            let mut data = object(call.path("policy"))?;
            if data.get("base_policy").is_none() && data.get("policy").is_none() {
                data = json!({"base_policy":data});
            }
            let requested = call.values["profile"].clone();
            data.as_object_mut()
                .unwrap()
                .entry("profile")
                .or_insert(requested);
            crate::downstream::rule(
                "policy_config__build_platform_policy_report",
                vec![data, json!("platform-policy-explain")],
            )?
        }
        "platform notify route" | "platform notify deliver" => notify::run(call)?,
        "platform baseline review" | "platform baseline promote" => baseline::run(call)?,
        "platform history-analytics" | "platform history-materialize" => {
            return analytics::run(call);
        }
        "platform schedule" => schedule::schedule(call)?,
        "platform score" | "platform verdict" | "platform triage" => assess::run(call)?,
        cmd => anyhow::bail!("unknown platform command: {cmd}"),
    };
    if let Some(path) = call.optional_path("out") {
        write_json(&path, &value)?;
    }
    Ok(value)
}
