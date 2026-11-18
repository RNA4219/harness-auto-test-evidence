use super::assess::truth;
use super::*;
use chrono::{DateTime, NaiveDate, NaiveDateTime, SecondsFormat, Utc};

pub(super) fn parse_time(value: &str) -> Option<DateTime<Utc>> {
    if let Ok(dt) = DateTime::parse_from_rfc3339(value) {
        return Some(dt.to_utc());
    }
    ["%Y-%m-%dT%H:%M:%S%.f", "%Y-%m-%d %H:%M:%S%.f"]
        .iter()
        .find_map(|fmt| {
            NaiveDateTime::parse_from_str(value, fmt)
                .ok()
                .map(|t| t.and_utc())
        })
        .or_else(|| {
            NaiveDate::parse_from_str(value, "%Y-%m-%d")
                .ok()?
                .and_hms_opt(0, 0, 0)
                .map(|t| t.and_utc())
        })
}
pub(super) fn assign(call: &Invocation) -> Result<Value> {
    let input = call.path("input");
    let now = Utc::now();
    let mut assignments = Vec::new();
    let mut findings = Vec::new();
    let mut missing = 0;
    let mut late = 0;
    for report in reports(input, false)? {
        for v in items(&report["findings"]) {
            let owner = field(v, "owner", field(&report, "owner", ""));
            let due = field(v, "due_date", field(v, "dueDate", ""));
            let code = field(v, "code", "finding");
            let mut source = refs(v, true);
            if source.is_empty() {
                source = refs(&report, true);
            }
            let (status, reason) = if owner.is_empty() || due.is_empty() {
                missing += 1;
                (
                    "missing_owner_or_due_date",
                    "platform_assignment_missing_owner_or_due_date",
                )
            } else if parse_time(due).is_some_and(|t| t < now) {
                late += 1;
                ("sla_breached", "platform_assignment_sla_breached")
            } else {
                ("assigned", "")
            };
            if !reason.is_empty() {
                findings.push(json!({"code":reason,"severity":"high","readiness_effect":"hold","message":format!("{reason}: {code}"),"sourceRefs":source}));
            }
            assignments.push(json!({"finding_code":code,"severity":field(v,"severity","medium"),"owner":owner,"due_date":due,"sla_status":status,"sourceRefs":source}));
        }
    }
    Ok(
        json!({"schema_version":"HATE/v1","record_type":"platform-assignment-report","generated_at":now.to_rfc3339_opts(SecondsFormat::Secs,true),
        "overall_status":if findings.is_empty(){"pass"}else{"hold"},"assignments":assignments,"findings":findings,
        "summary":{"assignment_count":assignments.len(),"missing_owner_or_due_date_count":missing,"sla_breach_count":late},"sourceRefs":[input]}),
    )
}
pub(super) fn schedule(call: &Invocation) -> Result<Value> {
    let roster = call.path("roster");
    let store = call.path("history_store");
    let data = object(roster)?;
    let path = if store.is_dir() {
        store.join("run_history.jsonl")
    } else {
        store.to_owned()
    };
    let mut history = BTreeMap::new();
    if path.try_exists()? {
        for line in fs::read_to_string(&path)?
            .lines()
            .filter(|s| !s.trim().is_empty())
        {
            let v: Value = serde_json::from_str(line)?;
            history.insert(
                (
                    field(&v, "repo_id", "").to_owned(),
                    field(&v, "suite_id", "default").to_owned(),
                ),
                v,
            );
        }
    }
    let now = Utc::now();
    let mut tasks = Vec::new();
    let mut runs = 0;
    use bigdecimal::{ToPrimitive, num_bigint::BigInt};
    let mut retries = BigInt::from(0);
    let ttl = &call.values["cache_ttl_hours"];
    let ttl_hours = call
        .integer("cache_ttl_hours")?
        .to_f64()
        .context("invalid ttl")?;
    let limit = &call.values["retry_limit"];
    let retry_budget = call.integer("retry_limit")?;
    let force = call.values["force"] == true;
    for repo in items(&data["repositories"]) {
        let suites = items(&repo["suites"]);
        let default = json!({});
        let suites = if suites.is_empty() {
            std::slice::from_ref(&default)
        } else {
            suites
        };
        for suite in suites {
            let mut entry = repo.as_object().context("invalid roster entry")?.clone();
            entry.extend(suite.as_object().context("invalid suite")?.clone());
            let entry = Value::Object(entry);
            let repo_id = field(repo, "repo_id", "");
            let suite_id = if suite == &default {
                field(repo, "suite_id", "default")
            } else {
                field(suite, "suite_id", "default")
            };
            let last = history
                .get(&(repo_id.to_owned(), suite_id.to_owned()))
                .unwrap_or(&Value::Null);
            let age =
                parse_time(field(last, "finished_at", field(last, "started_at", ""))).map(|t| {
                    ((now - t).num_milliseconds().max(0) as f64 / 36_000.).round_ties_even() / 100.
                });
            let status = field(last, "status", "");
            let cached = status == "pass" && age.is_some_and(|h| h <= ttl_hours);
            let held = matches!(status, "hold" | "blocked");
            let retry = retry_budget.clone().min(BigInt::from(u8::from(held)));
            let run = force || !cached || held;
            runs += usize::from(run);
            retries += &retry;
            let retry: Value = retry.to_string().parse()?;
            let split = if truth(&entry["split_execution"]) {
                &entry["split_execution"]
            } else {
                &entry["timeout_strategy"]
            };
            let commands = [
                &split["commands"],
                &split["split_commands"],
                &entry["split_commands"],
            ]
            .into_iter()
            .find(|v| truth(v))
            .unwrap_or(&Value::Null);
            let n = items(commands).iter().filter(|v| v.is_array()).count();
            let partial = field(last, "partial_result_ref", "");
            tasks.push(json!({"repo_id":repo_id,"suite_id":suite_id,"action":if run{"run"}else{"cache_hit"},
                "cache":{"hit":cached && !force && !held,"ttl_hours":ttl,"age_hours":age,"last_status":status},
                "retry":{"eligible":held,"limit":limit,"planned_attempts":retry},"bootstrap_required":([&entry["bootstrap"]["command"],&entry["bootstrap_command"],&entry["dependency_bootstrap_command"]].into_iter().any(truth)),
                "split":{"configured":n>0,"split_count":n},"resume":{"required":!partial.is_empty(),"partial_result_ref":partial},
                "resume_token":format!("{repo_id}:{suite_id}:{}",field(last,"run_id","new")),"sourceRefs":[roster]}));
        }
    }
    let retries: Value = retries.to_string().parse()?;
    Ok(
        json!({"schema_version":"HATE/v1","record_type":"platform-schedule-plan","generated_at":now.to_rfc3339_opts(SecondsFormat::Secs,true),"overall_status":"pass",
        "cache_ttl_hours":ttl,"retry_limit":limit,"force":force,"tasks":tasks,"summary":{"task_count":tasks.len(),"run_count":runs,"cache_hit_count":tasks.len()-runs,"retry_count":retries},"sourceRefs":[roster,store]}),
    )
}
