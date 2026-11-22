use super::{assess::truth, operating::*, *};
fn approved(b: &Value) -> bool {
    matches!(field(b, "state", ""), "approved" | "frozen" | "superseded")
}
fn promote(input: &Value, id: &str, source: &str) -> Result<Value> {
    let mut state = normalize("baseline", input.get("baseline").unwrap_or(input))?;
    let mut requests = Vec::new();
    let mut decisions = Vec::new();
    let mut events = Vec::new();
    let mut findings = Vec::new();
    for (i, raw) in items(&input["events"]).iter().enumerate() {
        let event = normalize("baseline_event", raw)?;
        let kind = field(&event, "event_type", "");
        let fallback = format!("{source}#/events/{i}");
        let src = event["sourceRefs"][0].as_str().unwrap_or(&fallback);
        let before = state["state"].clone();
        let hash = state["immutability_hash"].clone();
        for (k, v) in event.as_object().unwrap() {
            if !matches!(k.as_str(), "event_type" | "sourceRefs") && truth(v) {
                state[k] = v.clone();
            }
        }
        let mut issue = |code, msg| findings.push(finding(code, msg, src));
        match kind {
            "proposed" => {
                if state["candidate_run_id"] == "" || !truth(&state["evidence_refs"]) {
                    issue(
                        "baseline_candidate_missing_evidence",
                        "Baseline proposal requires candidate_run_id and evidence_refs.",
                    );
                }
                state["state"] = json!(kind);
                let mut req = select(
                    &state,
                    &[
                        "baseline_id",
                        "repo_id",
                        "suite_id",
                        "candidate_run_id",
                        "actor",
                        "reason",
                        "evidence_refs",
                        "policy_hash",
                        "expires_at",
                        "ownership_scope",
                        "external_run_ref",
                        "external_decision_ref",
                        "observation_count",
                    ],
                );
                req["record_type"] = json!("baseline-promotion-request");
                req["sourceRefs"] = json!([src]);
                requests.push(req);
            }
            "approved" | "frozen" | "expired" | "revoked" | "superseded" | "rejected" => {
                match kind {
                    "approved" if state["reviewer"] == "" => issue(
                        "baseline_approval_missing_reviewer",
                        "Baseline approval requires a reviewer.",
                    ),
                    "approved" if state["reviewer"] == state["actor"] => issue(
                        "baseline_self_approval_denied",
                        "Baseline approval cannot be performed by the proposal actor.",
                    ),
                    "frozen" if state["frozen_at"] == "" || state["immutability_hash"] == "" => {
                        issue(
                            "baseline_candidate_missing_evidence",
                            "Frozen baseline requires frozen_at and immutability_hash.",
                        )
                    }
                    _ => state["state"] = json!(kind),
                }
                if kind == "expired" {
                    issue(
                        "baseline_expired",
                        "Expired baseline cannot be used to hide regressions.",
                    );
                }
                if kind == "revoked" {
                    issue(
                        "baseline_revoked",
                        "Revoked baseline cannot be used for comparison.",
                    );
                }
                let mut d = select(
                    &state,
                    &[
                        "baseline_id",
                        "actor",
                        "reviewer",
                        "reason",
                        "policy_hash",
                        "expires_at",
                        "frozen_at",
                        "immutability_hash",
                        "previous_baseline_ref",
                        "ownership_scope",
                        "external_run_ref",
                        "external_decision_ref",
                        "observation_count",
                    ],
                );
                d["record_type"] = json!("baseline-promotion-decision");
                d["decision"] = json!(kind);
                d["sourceRefs"] = json!([src]);
                decisions.push(d);
            }
            _ => findings.push(finding(
                "baseline_unapproved_for_comparison",
                &format!("Unsupported baseline promotion event: {kind}."),
                src,
            )),
        }
        events.push(json!({"record_type":"baseline-immutability-event","baseline_id":state["baseline_id"],"event_type":kind,
            "before_state":before,"after_state":state["state"],"before_hash":hash,"after_hash":state["immutability_hash"],"sourceRefs":[src]}));
    }
    if state["comparison_requested"] == true && !approved(&state) {
        findings.push(finding(
            "baseline_unapproved_for_comparison",
            "Comparison requested against a baseline that is not approved, frozen, or superseded.",
            source,
        ));
    }
    if state["ownership_scope"] == "external" && approved(&state) {
        if state["external_run_ref"] == "" || state["external_decision_ref"] == "" {
            findings.push(finding("baseline_external_reference_missing","External OSS baseline approval requires external_run_ref and external_decision_ref.",source));
        }
        if state["observation_count"].as_i64().unwrap_or(0) < 2 {
            findings.push(finding(
                "baseline_external_observation_floor_missing",
                "External OSS baseline approval requires at least two successful observations.",
                source,
            ));
        }
    }
    let refs = json!([source]);
    let mut report = json!({"schema_version":"HATE/v1","record_type":"baseline-promotion-report","report_id":id,"overall_status":if findings.is_empty(){"pass"}else{"hold"},
       "readiness_effect":if findings.is_empty(){"none"}else{"hold"},"baseline_state":state,"promotion_requests":requests,"promotion_decisions":decisions,"immutability_events":events,"findings":findings,
       "summary":{"event_count":events.len(),"request_count":requests.len(),"decision_count":decisions.len(),"immutability_event_count":events.len(),"finding_count":findings.len(),
       "final_state":state["state"],"comparison_allowed":approved(&state)&&findings.is_empty()},"sourceRefs":refs});
    merge(&mut report, envelope(input, id, &refs));
    contract(&mut report, &refs);
    Ok(report)
}

fn review(input: &Value, id: &str, source: &str) -> Result<Value> {
    let report = if input["record_type"] == "baseline-promotion-report" {
        input.clone()
    } else {
        promote(input, &format!("{id}:promotion"), source)?
    };
    let b = &report["baseline_state"];
    let c = &input["comparison"];
    let refs = json!([source]);
    let opt = |key: &str| {
        if c[key].is_null() || c[key] == "" {
            Ok(None)
        } else {
            number(&c[key]).map(Some)
        }
    };
    let previous = opt("previous_score")?;
    let candidate = opt("candidate_score")?;
    let delta = previous
        .zip(candidate)
        .map(|(a, b)| format!("{:.4}", b - a).parse::<f64>())
        .transpose()?;
    let count = |k: &str| {
        c[k].as_i64()
            .or_else(|| c[k].as_str()?.parse().ok())
            .unwrap_or(0)
    };
    let old = count("previous_regression_count");
    let new = count("candidate_regression_count");
    let comparison = json!({"record_type":"baseline-review-comparison","previous_baseline_ref":field(c,"previous_baseline_ref",""),"previous_score":previous,"candidate_score":candidate,
        "score_delta":delta,"previous_regression_count":old,"candidate_regression_count":new,"regression_count_delta":new-old,"comparison_artifact_ref":field(c,"comparison_artifact_ref","")});
    let tests = [
        (
            "candidate_evidence",
            truth(&b["candidate_run_id"]) && truth(&b["evidence_refs"]),
            "Candidate run and evidence refs must be present.",
        ),
        (
            "reviewer_separation",
            truth(&b["reviewer"]) && b["actor"] != b["reviewer"],
            "Reviewer must be present and separate from actor.",
        ),
        (
            "policy_hash",
            truth(&b["policy_hash"]),
            "Policy hash must bind the promotion decision.",
        ),
        (
            "expiry",
            truth(&b["expires_at"]),
            "Baseline must carry an expiry date.",
        ),
        (
            "immutability",
            truth(&b["immutability_hash"]) || truth(&report["immutability_events"]),
            "Immutable before/after state must be visible.",
        ),
        (
            "comparison_artifact",
            truth(&comparison["comparison_artifact_ref"]),
            "Reviewer needs comparison artifact for delta inspection.",
        ),
        (
            "regression_delta",
            new <= old,
            "Candidate must not add unexplained regressions.",
        ),
        (
            "external_reference",
            b["ownership_scope"] != "external"
                || (truth(&b["external_run_ref"]) && truth(&b["external_decision_ref"])),
            "External OSS baseline requires external run and decision refs.",
        ),
    ];
    let mut findings = Vec::new();
    let mut checks = Vec::new();
    for (key, ok, desc) in tests {
        checks.push(json!({"record_type":"baseline-review-item","item_id":key,"required":true,"status":if ok{"satisfied"}else{"missing"},"description":desc}));
        if !ok {
            findings.push(finding(
                "baseline_review_item_missing",
                &format!("Baseline review item missing: {key}."),
                source,
            ));
        }
    }
    let satisfied = tests.len() - findings.len();
    if truth(&report["findings"]) {
        findings.push(finding(
            "baseline_review_blocked_by_promotion_findings",
            "Review packet cannot be ready while promotion report has findings.",
            source,
        ));
    }
    if matches!(field(b, "state", ""), "expired" | "revoked" | "rejected") {
        findings.push(finding(
            "baseline_unapproved_for_comparison",
            "Rejected, revoked, or expired baseline cannot be review-ready.",
            source,
        ));
    }
    let sources: BTreeSet<_> = std::iter::once(source)
        .chain(
            items(&report["sourceRefs"])
                .iter()
                .filter_map(Value::as_str),
        )
        .collect();
    let mut result = json!({"schema_version":"HATE/v1","record_type":"baseline-review-packet","packet_id":id,"readiness_effect":if findings.is_empty(){"none"}else{"hold"},
       "baseline_id":field(b,"baseline_id",""),"repo_id":field(b,"repo_id",""),"suite_id":field(b,"suite_id",""),"candidate_run_id":field(b,"candidate_run_id",""),
       "reviewer":field(b,"reviewer",""),"promotion_report_ref":field(&report,"report_id",""),"comparison":comparison,"review_items":checks,"findings":findings,
       "summary":{"review_item_count":checks.len(),"required_item_count":checks.len(),"satisfied_required_count":satisfied,"finding_count":findings.len(),
       "score_delta":delta,"regression_count_delta":new-old,"ready_for_review":findings.is_empty()},"sourceRefs":sources});
    merge(&mut result, envelope(input, id, &refs));
    contract(&mut result, &refs);
    Ok(result)
}
pub(super) fn run(call: &Invocation) -> Result<Value> {
    let raw = object(call.path("input"))?;
    let input = raw.get("input").unwrap_or(&raw);
    let source = call.path("input").to_string_lossy();
    if call.command.ends_with("review") {
        review(
            input,
            field(
                &raw,
                "fixture_id",
                field(&raw, "packet_id", "platform-baseline-review"),
            ),
            &source,
        )
    } else {
        promote(
            input,
            field(
                &raw,
                "fixture_id",
                field(&raw, "report_id", "platform-baseline-promotion"),
            ),
            &source,
        )
    }
}
