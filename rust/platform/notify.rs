use super::{operating::*, *};
const TARGETS: [&str; 6] = [
    "slack_channel",
    "slack_dm",
    "email",
    "github_comment",
    "github_check_annotation",
    "webhook",
];
fn supported(v: &Value) -> bool {
    TARGETS.contains(&field(v, "delivery_target", "")) && !field(v, "target_ref", "").is_empty()
}

fn route(input: &Value, id: &str, source: &str) -> Result<Value> {
    let record = normalize("operating", input.get("operating_record").unwrap_or(input))?;
    let subs = items(&input["subscribers"])
        .iter()
        .map(|v| normalize("subscriber", v))
        .collect::<Result<Vec<_>>>()?;
    let mut entries = Vec::new();
    let mut findings = Vec::new();
    let sla = record["sla_breached"] == true;
    for sub in subs.iter().filter(|s| s["active"] == true) {
        let escalated = sub["routing_role"] == "escalation" && sla;
        if !escalated
            && !["owner", "team"]
                .iter()
                .any(|k| record[*k] != "" && record[*k] == sub[*k])
        {
            continue;
        }
        let role = if escalated { "escalation" } else { "primary" };
        entries.push(json!({"record_type":"notification-routing-entry","operating_record_id":record["operating_record_id"],
         "subscriber_id":sub["subscriber_id"],"routing_role":role,"delivery_target":sub["delivery_target"],"target_ref":sub["target_ref"],
         "dedupe_key":format!("{}:{}:{role}",field(&record,"operating_record_id",""),field(sub,"subscriber_id","")),
         "payload_hash":record["payload_hash"],"redaction_report_ref":record["redaction_report_ref"],"sourceRefs":[record["sourceRef"],sub["sourceRef"]]}));
    }
    let mut check = |failed: bool, code: &str, msg: &str| {
        if failed {
            findings.push(finding(code, msg, source));
        }
    };
    check(
        record["operating_record_id"] == "" || record["owner"] == "",
        "notification_owner_missing",
        "Operating record requires owner before notification routing.",
    );
    check(
        record["payload_hash"] == "" || record["redaction_report_ref"] == "",
        "notification_payload_unsafe",
        "Routing plan requires payload_hash and redaction_report_ref.",
    );
    check(
        entries.is_empty(),
        "notification_target_missing",
        "Routing plan requires at least one active owner/team subscriber.",
    );
    for e in &entries {
        check(
            !supported(e),
            "notification_target_missing",
            "Routing entry has unsupported delivery target or missing target_ref.",
        );
    }
    let escalations = entries
        .iter()
        .filter(|e| e["routing_role"] == "escalation")
        .count();
    check(
        sla && escalations == 0,
        "notification_escalation_target_missing",
        "SLA-breached operating record requires escalation routing.",
    );
    check(
        !subs.is_empty() && subs.iter().all(|v| v["active"] != true),
        "notification_target_missing",
        "All notification subscribers are inactive.",
    );
    Ok(
        json!({"schema_version":"HATE/v1","record_type":"notification-routing-plan","plan_id":id,"readiness_effect":if findings.is_empty(){"none"}else{"hold"},
      "operating_record":record,"subscribers":subs,"routing_entries":entries,"findings":findings,"summary":{"subscriber_count":subs.len(),
      "routing_entry_count":entries.len(),"primary_count":entries.len()-escalations,"escalation_count":escalations,"hold_count":findings.len(),"sla_breached":sla},"sourceRefs":[source]}),
    )
}
fn event(kind: &str, state: &Value, keys: &[&str], source: &str) -> Value {
    let mut v = select(state, keys);
    v["record_type"] = json!(kind);
    v["sourceRefs"] = json!([source]);
    v
}
fn deliver(input: &Value, id: &str, source: &str) -> Result<Value> {
    let mut state = normalize("delivery", input.get("plan").unwrap_or(input))?;
    let mut findings = Vec::new();
    let mut events = Vec::new();
    let mut letters = Vec::new();
    let mut audits = Vec::new();
    for (failed, code, msg) in [
        (
            !supported(&state),
            "notification_target_missing",
            "Notification delivery requires a supported delivery_target and target_ref.",
        ),
        (
            state["payload_safe"] != true || state["redaction_report_ref"] == "",
            "notification_payload_unsafe",
            "Notification payload requires redaction evidence and must not include unsafe body content.",
        ),
        (
            state["delivery_target"] == "webhook" && state["signature_ref"] == "",
            "notification_signature_missing",
            "Webhook notification requires signature_ref.",
        ),
        (
            state["dedupe_key"] == "" || state["payload_hash"] == "",
            "notification_target_missing",
            "Notification delivery requires dedupe_key and payload_hash.",
        ),
    ] {
        if failed {
            findings.push(finding(code, msg, source));
        }
    }
    let holds = |v: &Value| {
        matches!(
            field(v, "delivery_status", ""),
            "failed" | "retry_scheduled" | "dead_lettered"
        )
    };
    for (i, raw) in items(&input["attempts"]).iter().enumerate() {
        let a = normalize("attempt", raw)?;
        let fallback = format!("{source}#/attempts/{i}");
        let src = a["sourceRefs"][0].as_str().unwrap_or(&fallback);
        for key in [
            "delivery_status",
            "error_code",
            "next_retry_at",
            "signature_ref",
            "redaction_report_ref",
            "payload_hash",
            "dedupe_key",
            "attempt",
        ] {
            if super::assess::truth(&a[key]) {
                state[key] = a[key].clone();
            }
        }
        if a["event_type"] == "duplicate_suppressed" {
            findings.push(finding(
                "notification_duplicate_suppressed",
                "Duplicate notification was suppressed and retained as an audit event.",
                src,
            ));
            state["delivery_status"] = json!("duplicate_suppressed");
        } else {
            events.push(event(
                "notification-delivery-attempt",
                &state,
                &[
                    "notification_id",
                    "operating_record_id",
                    "delivery_target",
                    "target_ref",
                    "dedupe_key",
                    "payload_hash",
                    "attempt",
                    "max_attempts",
                    "next_retry_at",
                    "delivery_status",
                    "error_code",
                    "signature_ref",
                    "redaction_report_ref",
                ],
                src,
            ));
            if holds(&state) {
                findings.push(finding(
                    "notification_delivery_failed",
                    "Notification delivery failed and must not close the operating record.",
                    src,
                ));
            }
            if state["delivery_status"] == "dead_lettered" || a["event_type"] == "dead_lettered" {
                findings.push(finding(
                    "notification_dead_lettered",
                    "Notification reached dead-letter state.",
                    src,
                ));
                letters.push(event(
                    "notification-dead-letter-event",
                    &state,
                    &[
                        "notification_id",
                        "operating_record_id",
                        "delivery_target",
                        "target_ref",
                        "attempt",
                        "max_attempts",
                        "error_code",
                    ],
                    src,
                ));
            }
            if state["delivery_status"] == "retry_scheduled" && state["next_retry_at"] == "" {
                findings.push(finding(
                    "notification_delivery_failed",
                    "Retry-scheduled notification requires next_retry_at.",
                    src,
                ));
            }
        }
        let mut audit = event(
            "notification-audit-event",
            &state,
            &["notification_id", "operating_record_id", "delivery_status"],
            src,
        );
        audit["event_type"] = a["event_type"].clone();
        audits.push(audit);
    }
    if holds(&state) {
        state["operating_record_status_after"] = state["operating_record_status_before"].clone();
    }
    Ok(
        json!({"schema_version":"HATE/v1","record_type":"notification-delivery-report","report_id":id,"overall_status":if findings.is_empty(){"pass"}else{"hold"},
       "readiness_effect":if findings.is_empty(){"none"}else{"hold"},"delivery_plan":state,"delivery_attempts":events,"dead_letter_events":letters,"audit_events":audits,"findings":findings,
       "summary":{"attempt_count":events.len(),"dead_letter_count":letters.len(),"audit_event_count":audits.len(),"finding_count":findings.len(),"final_delivery_status":state["delivery_status"],
       "operating_record_status_after":state["operating_record_status_after"]},"sourceRefs":[source]}),
    )
}
pub(super) fn run(call: &Invocation) -> Result<Value> {
    let source = call.path("input").to_string_lossy();
    let raw = object(call.path("input"))?;
    let input = raw.get("input").unwrap_or(&raw);
    let routing = call.command.ends_with("route");
    let (key, default) = if routing {
        ("plan_id", "platform-notification-routing")
    } else {
        ("report_id", "platform-notification-delivery")
    };
    let id = field(&raw, "fixture_id", field(&raw, key, default));
    let mut result = if routing {
        route(input, id, &source)?
    } else {
        deliver(input, id, &source)?
    };
    let refs = json!([source]);
    merge(&mut result, envelope(input, id, &refs));
    contract(&mut result, &refs);
    Ok(result)
}
