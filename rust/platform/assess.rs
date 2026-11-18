use super::*;
use std::collections::HashMap;

fn evidence(input: &Path) -> Result<Vec<Value>> {
    let sources = reports(input, false)?;
    let manifests: Vec<_> = sources
        .iter()
        .filter(|r| r["record_type"] == "real-repo-evaluation-run-report")
        .collect();
    let candidates = if manifests.is_empty() {
        sources
    } else {
        let base = if input.is_file() {
            parent(input)
        } else {
            input
        };
        let mut loaded = Vec::new();
        for manifest in manifests {
            for name in items(&manifest["generated_reports"])
                .iter()
                .filter_map(Value::as_str)
            {
                let path = base.join(name);
                if path.try_exists()? {
                    loaded.push(object(&path)?);
                }
            }
        }
        loaded
    };
    let mut indexes = HashMap::new();
    let mut unique = Vec::new();
    for r in candidates
        .into_iter()
        .filter(|r| r["record_type"] == "real-repo-evaluation-report")
    {
        let key = (
            field(&r, "repo_id", "").to_owned(),
            field(&r, "suite_id", "default").to_owned(),
            field(&r, "run_id", "").to_owned(),
        );
        if let Some(&i) = indexes.get(&key) {
            unique[i] = r;
        } else {
            indexes.insert(key, unique.len());
            unique.push(r);
        }
    }
    Ok(unique)
}

fn subset(r: &Value) -> bool {
    if r["subset"].is_object() {
        return r["subset"]["is_subset"] == true && r["subset"]["proves_full_suite"] != true;
    }
    truth(&r["subset"]) || truth(&r["subset_limited"])
}

pub(super) use crate::io::is_truthy as truth;

fn score(r: &Value) -> Value {
    let current = &r["current"];
    let findings = items(&r["findings"]);
    let regressions = items(&r["regressions"])
        .iter()
        .filter(|v| field(v, "regression_class", field(v, "code", "")) != "external_hold_detected")
        .count();
    let component_values = [
        (
            "evidence_strength",
            40.,
            if r["overall_status"] == "pass" {
                0.9
            } else {
                0.55
            },
        ),
        (
            "coverage_confidence",
            15.,
            if truth(&current["record_count"]) {
                0.8
            } else {
                0.2
            },
        ),
        (
            "oracle_confidence",
            15.,
            if matches!(
                current["runner_dialect"].as_str(),
                Some("nextjs-build" | "typescript-typecheck")
            ) {
                0.4
            } else {
                0.8
            },
        ),
        (
            "freshness_score",
            10.,
            if super::schedule::parse_time(field(r, "finished_at", "")).is_some() {
                1.
            } else {
                0.8
            },
        ),
        (
            "stability_score",
            10.,
            if regressions == 0 { 1. } else { 0.3 },
        ),
        (
            "ownership_clarity",
            10.,
            if r["ownership_scope"] == "owned" {
                1.
            } else {
                0.6
            },
        ),
    ];
    let penalty_values = [
        ("regression_penalty", (15. * regressions as f64).min(40.)),
        (
            "timeout_penalty",
            if truth(&r["timeout_recorded"]) {
                20.
            } else {
                0.
            },
        ),
        (
            "record_collapse_penalty",
            if findings
                .iter()
                .any(|v| v["code"] == "real_repo_record_count_collapse")
            {
                20.
            } else {
                0.
            },
        ),
        (
            "manual_debt_penalty",
            (5. * items(&r["risk_debt"]).len() as f64).min(15.),
        ),
        (
            "expired_debt_penalty",
            if findings
                .iter()
                .any(|v| field(v, "code", "").contains("expired"))
            {
                15.
            } else {
                0.
            },
        ),
        (
            "unsafe_artifact_penalty",
            if truth(&current["unsafe_artifact_findings"]) {
                20.
            } else {
                0.
            },
        ),
        ("subset_penalty", if subset(r) { 12. } else { 0. }),
    ];
    let (mut weights, mut components, mut points, mut penalties) =
        (json!({}), json!({}), json!({}), json!({}));
    let mut basis = Vec::new();
    let mut base = 0.;
    let mut penalty_total = 0.;
    for (key, weight, val) in component_values {
        weights[key] = json!(weight);
        components[key] = json!(val);
        points[key] = json!(weight * val);
        base += weight * val;
        basis.push(json!({"basis_id":format!("component:{key}"),"kind":"component","value":val,"points":weight*val,"rationale":format!("{key} contributes bounded weighted evidence.")}));
    }
    for (key, val) in penalty_values {
        penalties[key] = json!(val);
        penalty_total += val;
        if val > 0. {
            basis.push(json!({"basis_id":format!("penalty:{key}"),"kind":"penalty","value":val,"points":-val,"rationale":format!("{key} reduces confidence when the corresponding risk is present.")}));
        }
    }
    let score = (base - penalty_total).clamp(0., 100.);
    let repo = field(r, "repo_id", field(r, "report_id", "repo"));
    let suite = field(r, "suite_id", "default");
    let id = format!("score-{repo}-{suite}");
    let mut refs = refs(r, true);
    if refs.is_empty() {
        refs.push(format!("fixtures/platform/evaluation/{id}/fixture.json"));
    }
    json!({"schema_version":"HATE/v1","record_type":"real-repo-score-report","report_id":id,"repo_id":repo,"suite_id":suite,
      "source_version":"","policy_hash":"","score":score,"score_band":if score>=85.{"strong"}else if score>=70.{"usable"}else if score>=50.{"weak"}else{"blocked"},
      "release_approval":false,"score_breakdown":{"component_weights":weights,"components":components,"component_points":points,"base_score":base,
      "penalties":penalties,"penalty_total":penalty_total,"score":score},"decision_basis":basis,"sourceRefs":refs})
}

fn triage(rows: &[Value], input: &Path) -> Value {
    let mut output = Vec::new();
    let mut findings = Vec::new();
    let mut counts = BTreeMap::new();
    for r in rows {
        let hold = field(r, "overall_status", "").eq_ignore_ascii_case("hold");
        let limited = subset(r);
        if !hold && !limited {
            continue;
        }
        let current = &r["current"];
        let kind = field(current, "failure_kind", "");
        let repo = field(r, "repo_id", "");
        let suite = field(r, "suite_id", "default");
        let action = if truth(&current["split_execution"]["configured"]) {
            "rerun_failed_split_shards"
        } else if kind == "bootstrap_failed" {
            "repair_bootstrap_recipe"
        } else if repo == "axios" {
            "classify_playwright_browser_or_unit_failure"
        } else if repo == "pytest"
            || truth(&r["subset"]["is_subset"])
            || suite.contains("compileall")
        {
            "build_dedicated_self_hosted_runner_recipe"
        } else if kind == "test_failure" {
            "investigate_external_test_failure"
        } else {
            "manual_review_required"
        };
        let source = refs(r, true);
        let owner = field(r, "owner", "");
        if owner.is_empty() {
            findings.push(json!({"code":"platform_triage_missing_owner","severity":"medium","readiness_effect":"hold","message":"Triage item has no owner.","sourceRefs":source}));
        }
        output.push(json!({"triage_id":format!("{repo}:{suite}"),"repo_id":repo,"suite_id":suite,"status":"open","failure_kind":kind,
            "readiness_effect":if hold{"hold"}else{"soft_gap"},"recommended_action":action,"owner":owner,"due_date":field(r,"due_date",""),
            "record_count":current["record_count"].as_i64().unwrap_or(0),"runner_dialect":field(current,"runner_dialect",""),"subset_limited":limited,"sourceRefs":source}));
        *counts.entry(action).or_insert(0) += 1;
    }
    json!({"schema_version":"HATE/v1","record_type":"platform-triage-report","overall_status":if output.is_empty(){"pass"}else{"hold"},
        "items":output,"findings":findings,"summary":{"open_count":output.len(),"missing_owner_count":findings.len(),"by_action":counts},"sourceRefs":[input]})
}
fn verdict(rows: &[Value], input: &Path, path: &Path) -> Result<Value> {
    let corpus = object(path)?;
    let mut counts: BTreeMap<&str, u64> = [
        "missing",
        "true_positive",
        "false_positive",
        "true_negative",
        "false_negative",
        "kind_mismatch",
    ]
    .map(|k| (k, 0))
    .into();
    let mut output = Vec::new();
    let mut findings = Vec::new();
    let index: HashMap<_, _> = rows
        .iter()
        .map(|r| {
            (
                (field(r, "repo_id", ""), field(r, "suite_id", "default")),
                r,
            )
        })
        .collect();
    let raw = if truth(&corpus["entries"]) {
        &corpus["entries"]
    } else {
        &corpus["expected_verdicts"]
    };
    for expected in items(raw) {
        let repo = field(expected, "repo_id", "");
        let suite = field(expected, "suite_id", "default");
        let status = match field(
            expected,
            "expected_status",
            field(expected, "expected_verdict", ""),
        )
        .to_lowercase()
        .as_str()
        {
            "pass" | "go" | "ready" => "pass",
            "hold" | "blocked" | "no_go" | "fail" => "hold",
            _ => continue,
        };
        if repo.is_empty() {
            continue;
        }
        let kind = field(expected, "expected_failure_kind", "");
        let mut entry = json!({"repo_id":repo,"suite_id":suite,"expected_status":status,"expected_failure_kind":kind,"rationale":field(expected,"rationale","")});
        let mut finding = |code: &str, message: String| {
            findings.push(json!({"code":code,"severity":"high","readiness_effect":"hold","message":message,"sourceRefs":[format!("expected:{repo}:{suite}")]}))
        };
        if let Some(r) = index.get(&(repo, suite)) {
            let actual = if field(r, "overall_status", field(r, "status", ""))
                .eq_ignore_ascii_case("pass")
            {
                "pass"
            } else {
                "hold"
            };
            let class = match (status, actual) {
                ("hold", "hold") => "true_positive",
                ("pass", "hold") => "false_positive",
                ("hold", "pass") => "false_negative",
                _ => "true_negative",
            };
            *counts.get_mut(class).unwrap() += 1;
            let actual_kind = field(&r["current"], "failure_kind", "");
            let kind_ok = kind.is_empty() || kind == actual_kind;
            if status != actual {
                finding(
                    "platform_verdict_status_mismatch",
                    format!("Expected {status}, observed {actual}."),
                );
            }
            if !kind_ok {
                *counts.get_mut("kind_mismatch").unwrap() += 1;
                finding(
                    "platform_verdict_failure_kind_mismatch",
                    format!(
                        "Expected failure_kind {kind}, observed {}.",
                        if actual_kind.is_empty() {
                            "none"
                        } else {
                            actual_kind
                        }
                    ),
                );
            }
            entry["actual_status"] = json!(actual);
            entry["actual_failure_kind"] = json!(actual_kind);
            entry["actual_record_count"] =
                json!(r["current"]["record_count"].as_i64().unwrap_or(0));
            entry["classification"] = json!(class);
            entry["matched"] = json!(status == actual && kind_ok);
            entry["sourceRefs"] = json!(refs(r, true));
        } else {
            *counts.get_mut("missing").unwrap() += 1;
            finding(
                "platform_verdict_missing_report",
                "Expected repo/suite report was not present.".into(),
            );
            entry["actual_status"] = json!("missing");
            entry["actual_failure_kind"] = json!("");
            entry["classification"] = json!("missing");
            entry["matched"] = json!(false);
        }
        output.push(entry);
    }
    let [tp, fp, tn, miss] = [
        "true_positive",
        "false_positive",
        "true_negative",
        "false_negative",
    ]
    .map(|k| counts[k]);
    let ratio = |a: u64, b: u64| {
        if b == 0 {
            0.
        } else {
            format!("{:.4}", a as f64 / b as f64).parse().unwrap_or(0.)
        }
    };
    let mut metrics = json!(counts);
    metrics["precision"] = json!(ratio(tp, tp + fp));
    metrics["recall"] = json!(ratio(tp, tp + miss));
    metrics["specificity"] = json!(ratio(tn, tn + fp));
    metrics["accuracy"] = json!(ratio(tp + tn, tp + tn + miss + fp));
    Ok(
        json!({"schema_version":"HATE/v1","record_type":"platform-verdict-evaluation-report","overall_status":if findings.is_empty(){"pass"}else{"hold"},
        "corpus_id":field(&corpus,"corpus_id",field(&corpus,"report_id",path.file_stem().unwrap_or_default().to_str().unwrap_or(""))),
        "entries":output,"findings":findings,"metrics":metrics,"summary":{"expected_count":output.len(),"matched_count":output.iter().filter(|r|r["matched"]==true).count(),
        "finding_count":findings.len()},"sourceRefs":[input,path]}),
    )
}
pub(super) fn run(call: &Invocation) -> Result<Value> {
    let input = call.path("input");
    let rows = evidence(input)?;
    match call.command.as_str() {
        "platform triage" => Ok(triage(&rows, input)),
        "platform verdict" => verdict(&rows, input, call.path("corpus")),
        _ => {
            let scores: Vec<_> = rows.iter().map(score).collect();
            let average = if scores.is_empty() {
                0.
            } else {
                scores
                    .iter()
                    .filter_map(|v| v["score"].as_f64())
                    .sum::<f64>()
                    / scores.len() as f64
            };
            Ok(
                json!({"schema_version":"HATE/v1","record_type":"platform-score-report","overall_status":"pass","scores":scores,
                "summary":{"score_count":scores.len(),"average_score":format!("{average:.2}").parse::<f64>()?,"blocked_count":scores.iter().filter(|r|r["score_band"]=="blocked").count()},"sourceRefs":[input]}),
            )
        }
    }
}
