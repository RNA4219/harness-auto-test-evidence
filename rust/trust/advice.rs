use super::*;
use inputs::Input;

fn risk_refs<'a>(x: &'a Input, id: &str) -> Vec<&'a str> {
    let target = format!("risk:{id}");
    sorted_refs(
        items(&x.b["nodes"])
            .iter()
            .filter(|n| n["id"] == target)
            .flat_map(|n| items(&n["sourceRefs"]))
            .chain(
                items(&x.b["edges"])
                    .iter()
                    .filter(|e| e["from"] == target || e["to"] == target)
                    .flat_map(|e| items(&e["traceability"]["sourceRefs"])),
            ),
    )
}
fn issue_groups(x: &Input) -> [(&'static str, Vec<V>); 4] {
    let (permissions, gaps) = analysis::precheck(&x.b);
    [
        ("bundle_schema", analysis::schema_issues(&x.b)),
        ("export", analysis::export_issues(x)),
        ("precheck_permission", permissions),
        ("precheck", gaps),
    ]
}
fn explain(x: &Input, mode: &str) -> Vec<V> {
    let mut reasons = vec![];
    for (group, issues) in issue_groups(x) {
        for (i, p) in issues.iter().enumerate() {
            let block = match group {
                "export" => p["severity"] == "high",
                "precheck" => false,
                _ => true,
            };
            if mode != "why-score-changed"
                && mode
                    != if block {
                        "why-excluded"
                    } else {
                        "why-soft-gap"
                    }
            {
                continue;
            }
            let category = match group {
                "bundle_schema" => "schema",
                "export" => "export",
                _ => "precheck",
            };
            let mut v = overlay(
                json!({
                    "reason_id": format!("reason:{group}:{}",i+1),
                    "category": category,
                    "summary": p["message"],
                    "evidence_status": if block{"ineligible"}else{"soft_gap"},
                    "children": [],
                }),
                p,
            );
            if group != "precheck" {
                v["blocking"] = json!(block);
            }
            reasons.push(v);
        }
    }
    match mode {
        "why-soft-gap" => {
            for (i, g) in items(&x.r["missing_execution"]).iter().enumerate() {
                let id = format!("reason:soft_gap:{}", i + 1);
                reasons.push(json!({
                    "reason_id": id,
                    "category": "missing_execution",
                    "summary": g["reason"].as_str().unwrap_or("missing execution"),
                    "risk_id": s(g,"risk_id"),
                    "expected_test_ref": s(g,"expected_test_ref"),
                    "evidence_status": "missing",
                    "source_refs": ["qeg-export-report.json"],
                    "children": [{"reason_id":format!("{id}:risk"),"summary":"High-risk changed path requires execution evidence.","source_refs":risk_refs(x,s(g,"risk_id"))}],
                }));
            }
        }
        "why-excluded" => {
            for (i, a) in items(&x.r["excludedArtifacts"]).iter().enumerate() {
                reasons.push(json!({
                    "reason_id": format!("reason:excluded:{}",i+1),
                    "category": "artifact_safety",
                    "summary": a["reason"].as_str().unwrap_or("artifact excluded"),
                    "artifact_id": s(a,"artifact_id"),
                    "evidence_status": "excluded",
                    "source_refs": ["qeg-export-report.json"],
                    "children": [],
                }));
            }
        }
        _ => {
            let c = &x.b["completeness"];
            reasons.push(json!({
                "reason_id": "reason:score:completeness",
                "category": "aete_score",
                "summary": "AETE score follows bundle completeness and visible unsupported claims.",
                "score": c["score"],
                "partial": c["partial"],
                "source_refs": ["qeg-bundle.json","qeg-export-report.json"],
                "children": [{"reason_id":"reason:score:unsupported","summary":format!("Unsupported claims: {}",items(&c["unsupportedClaims"]).len()),"source_refs":["qeg-export-report.json"]}],
            }));
        }
    }
    reasons
}
fn recommend(x: &Input, gap: &str) -> Vec<V> {
    let mut rows = vec![];
    for (group, issues) in issue_groups(x) {
        for (i, p) in issues.iter().enumerate() {
            let category = if group == "export" {
                "export_metadata"
            } else {
                group
            };
            if gap != "all"
                && gap != category
                && !(group == "export" && gap == s(p, "issue"))
                && !(group == "precheck_permission" && gap == "precheck")
                && !(group == "precheck" && p["gap"]["gap_id"] == gap)
            {
                continue;
            }
            let acts = match group {
                "bundle_schema" => vec![
                    "Resolve the reported bundle schema violation and regenerate the bundle from valid source inputs.",
                ],
                "export" => vec![
                    "Review the original bundle purpose, export status, and schema validation evidence.",
                    "Resolve the reported restriction or evidence gap and regenerate the export from corrected inputs.",
                ],
                "precheck_permission" => vec![
                    "Inspect the original precheck record and resolve each reported permission condition.",
                    "Regenerate precheck and QEG export from corrected evidence; retain the original denial for diagnosis.",
                ],
                _ => vec![
                    "Review the original precheck reasons and the declared gap details.",
                    "Attach the missing evidence or context, then regenerate precheck and QEG export.",
                ],
            };
            let mut v = overlay(
                json!({
                    "recommendation_id": format!("recommend:{group}:{}",i+1),
                    "gap_id": category,
                    "recommended_actions": acts,
                    "recommended_manual_layer": "spec-clarification",
                    "related_source_refs": p["source_refs"],
                }),
                p,
            );
            if group != "precheck" {
                v["blocking"] = json!(group != "export" || p["severity"] == "high");
            }
            rows.push(v);
        }
    }
    if matches!(gap, "all" | "missing_execution") {
        for (i, g) in items(&x.r["missing_execution"]).iter().enumerate() {
            rows.push(json!({
                "recommendation_id": format!("recommend:missing_execution:{}",i+1),
                "gap_id": "missing_execution",
                "risk_id": s(g,"risk_id"),
                "expected_test_ref": s(g,"expected_test_ref"),
                "recommended_actions": ["Add or restore automated execution evidence for the expected test.","If automation is not available, create a manual-bb bridge review.","Keep the risk debt open until evidence is attached."],
                "recommended_test_layer": "unit",
                "recommended_manual_layer": "manual-scripted",
                "source_refs": ["qeg-export-report.json","risk-debt-register.json","manual-bb-bridge-requests.jsonl"],
                "related_source_refs": risk_refs(x,s(g,"risk_id")),
            }));
        }
    }
    if matches!(gap, "all" | "artifact_safety") {
        for (i, a) in items(&x.r["excludedArtifacts"]).iter().enumerate() {
            rows.push(json!({
                "recommendation_id": format!("recommend:artifact_safety:{}",i+1),
                "gap_id": "artifact_safety",
                "artifact_id": s(a,"artifact_id"),
                "recommended_actions": ["Replace the unsafe artifact with a redacted artifact reference.","Run artifact safety checks before adding it to QEG evidence."],
                "recommended_manual_layer": "spec-clarification",
                "source_refs": ["qeg-export-report.json"],
                "related_source_refs": [],
            }));
        }
    }
    rows
}
fn traced(rows: &[V]) -> bool {
    rows.iter()
        .all(|v| nonempty(&v["source_refs"]) && traced(items(&v["children"])))
}
pub(super) fn run(call: &Invocation, x: &Input) -> Result<V> {
    let mut report = json!({
        "schema_version": "HATE/v1",
        "bundle_ref": x.bundle_ref,
        "report_ref": x.report_ref,
        "source_refs": [x.bundle_ref,x.report_ref],
        "release_gate_override": false,
        "publish_gate_override": false,
    });
    let (name, result) = if call.command == "explain" {
        let mode = call.values["mode"].as_str().unwrap_or("why-soft-gap");
        let reasons = explain(x, mode);
        report = overlay(
            report,
            &json!({
                "record_type": "explain_report",
                "mode": mode,
                "reason_tree": reasons,
                "summary": {"reason_count":reasons.len(),"traceability_complete":traced(&reasons)},
            }),
        );
        (
            "explain-report.json",
            json!({"explain_status":"success","reason_count":reasons.len()}),
        )
    } else {
        let gap = call.values["gap"].as_str().unwrap_or("missing_execution");
        let rows = recommend(x, gap);
        report = overlay(
            report,
            &json!({
                "record_type": "recommendation_report",
                "gap_id": gap,
                "recommendations": rows,
                "summary": {
                    "recommendation_count": rows.len(),
                    "traceability_complete": traced(&rows),
                    "manual_bridge_recommendation_count": rows.iter().filter(|v|nonempty(&v["recommended_manual_layer"])).count(),
                },
            }),
        );
        (
            "recommendation-report.json",
            json!({"recommend_status":"success","recommendation_count":rows.len()}),
        )
    };
    write_json(&call.path("out").join(name), &report)?;
    Ok(overlay(
        result,
        &json!({"exit_code":0,"generated":[name],"publish_gate_override":false}),
    ))
}
