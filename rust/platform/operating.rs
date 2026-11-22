//! 運用レポートの共通メタデータと入力フィールドの正規化。
use super::{assess::truth, *};
use chrono::{SecondsFormat, Utc};
use std::sync::LazyLock;

static DEFAULTS: LazyLock<Value> =
    LazyLock::new(|| serde_json::from_str(include_str!("record_defaults.json")).unwrap());
pub(super) use crate::io::py_string as text;
pub(super) fn number(v: &Value) -> Result<f64> {
    v.as_f64()
        .or_else(|| v.as_str()?.parse().ok())
        .filter(|n| n.is_finite())
        .context("expected finite number")
}
pub(super) fn normalize(kind: &str, raw: &Value) -> Result<Value> {
    let mut result = DEFAULTS[kind].clone();
    for (key, value) in result
        .as_object_mut()
        .context("unknown record definition")?
    {
        if key == "record_type" {
            continue;
        }
        let mut input = raw.get(key);
        let fallback = match (kind, key.as_str()) {
            ("operating", "operating_record_id") => Some("record_id"),
            ("operating", "sourceRef") => Some("operating_record_id"),
            ("subscriber", "sourceRef") => Some("subscriber_id"),
            ("sample", "data_age_days") => Some("evidence_age_days"),
            ("sample", "sourceRef") => Some("run_id"),
            ("exclusion", "sourceRef") => Some("sample_id"),
            _ => None,
        };
        if !input.is_some_and(truth)
            && let Some(alt) = fallback
        {
            input = raw.get(alt);
        }
        let Some(input) = input else { continue };
        *value = match value {
            Value::Array(_) => json!(items(input).iter().map(text).collect::<Vec<_>>()),
            Value::Bool(_) => json!(truth(input)),
            Value::Null if input.is_null() || input == "" => Value::Null,
            Value::Null => json!(number(input)?),
            _ if !truth(input) => continue,
            Value::Number(n) if n.is_i64() || n.is_u64() => json!(
                input
                    .as_i64()
                    .or_else(|| input.as_str()?.parse().ok())
                    .or_else(|| input.as_f64().map(|f| f as i64))
                    .context("invalid integer")?
            ),
            Value::Number(_) => json!(number(input)?),
            _ => json!(text(input)),
        };
    }
    Ok(result)
}
pub(super) fn select(record: &Value, keys: &[&str]) -> Value {
    let mut out = json!({});
    for k in keys {
        out[*k] = record[*k].clone();
    }
    out
}
pub(super) fn finding(code: &str, message: &str, source: &str) -> Value {
    json!({"code":code,"severity":"high","message":message,"sourceRef":source,"readiness_effect":"hold"})
}
pub(super) fn merge(to: &mut Value, from: Value) {
    to.as_object_mut()
        .unwrap()
        .extend(from.as_object().unwrap().clone());
}

pub(super) fn envelope(input: &Value, id: &str, sources: &Value) -> Value {
    let now = Utc::now().to_rfc3339_opts(SecondsFormat::Secs, true);
    let mut out = json!({"record_id":field(input,"record_id",id),"created_at":field(input,"created_at",&now),
        "decision_basis":if truth(&input["decision_basis"]){input["decision_basis"].clone()}else{sources.clone()},
        "unsafe_output_policy":field(input,"unsafe_output_policy","redact_unsafe_outputs")});
    let actor = field(input, "actor", "");
    if actor.is_empty() {
        out["system_actor"] = json!(field(input, "system_actor", "hate-local"));
    } else {
        out["actor"] = json!(actor);
    }
    let tenant = std::iter::once(input)
        .chain(["request", "session", "slo"].iter().map(|k| &input[*k]))
        .chain(items(&input["telemetry"]))
        .find_map(|v| v["tenant_id"].as_str().filter(|s| !s.is_empty()));
    if let Some(tenant) = tenant {
        out["tenant_id"] = json!(tenant);
    }
    out
}
pub(super) fn contract(value: &mut Value, fallback: &Value) {
    if let Some(rows) = value.as_array_mut() {
        for v in rows {
            contract(v, fallback);
        }
        return;
    }
    if !value.is_object() {
        return;
    }
    let local = if !items(&value["sourceRefs"]).is_empty() {
        value["sourceRefs"].clone()
    } else if truth(&value["sourceRef"]) {
        json!([value["sourceRef"]])
    } else {
        fallback.clone()
    };
    let kind = field(value, "record_type", "");
    if [
        "baseline-",
        "capacity-",
        "compliance-",
        "connector-",
        "dashboard-",
        "docs-",
        "external-",
        "control-",
        "history-",
        "hosted-",
        "human-review-",
        "incident-",
        "notification-",
        "plugin-",
        "post-incident-",
        "procurement-",
        "real-repo-",
        "release-",
        "runtime-",
        "slo-",
        "store-",
    ]
    .iter()
    .any(|p| kind.starts_with(p))
    {
        let id = [
            "record_id",
            "report_id",
            "packet_id",
            "manifest_id",
            "plan_id",
            "runbook_id",
            "step_id",
            "event_id",
            "request_id",
            "decision_id",
            "operation_id",
            "entry_id",
            "review_id",
            "baseline_id",
            "plugin_id",
            "connector_id",
            "repo_id",
            "job_id",
            "incident_id",
            "notification_id",
            "control_id",
            "route",
            "path",
        ]
        .iter()
        .find_map(|k| value[*k].as_str().filter(|s| !s.is_empty()))
        .map_or_else(|| kind.to_owned(), |s| format!("{kind}:{s}"));
        let env = envelope(value, &id, &local);
        let hold = [
            "overall_status",
            "status",
            "delivery_status",
            "sync_status",
            "lease_state",
            "restore_status",
            "budget_status",
            "review_status",
            "decision",
        ]
        .iter()
        .any(|k| {
            matches!(
                field(value, k, ""),
                "hold"
                    | "blocked"
                    | "failed"
                    | "dead_lettered"
                    | "expired"
                    | "revoked"
                    | "denied"
                    | "rejected"
                    | "exceeded"
                    | "missing"
            )
        });
        let obj = value.as_object_mut().unwrap();
        for (k, v) in env.as_object().unwrap() {
            obj.entry(k).or_insert(v.clone());
        }
        obj.entry("readiness_effect")
            .or_insert(json!(if hold { "hold" } else { "none" }));
        obj.entry("sourceRefs").or_insert(local.clone());
    }
    for v in value.as_object_mut().unwrap().values_mut() {
        contract(v, &local);
    }
}
