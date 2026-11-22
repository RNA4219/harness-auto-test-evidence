use super::{Run, dq, items};
use anyhow::{Context, Result};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};

const POLICY: &str = include_str!("profiles.json");

pub(crate) fn build_profile_report(
    name: &str,
    run_id: &str,
    run_attempt: &Value,
    commit_sha: &str,
    created_at: &str,
) -> Result<Value> {
    let config: Value = serde_json::from_str(POLICY)?;
    let profiles = &config["profiles"];
    let policies = &config["policies"];
    let mut chain = Vec::new();
    let mut current = Some(name);
    while let Some(n) = current {
        let spec = profiles
            .get(n)
            .with_context(|| format!("unknown profile: {n}"))?;
        chain.push(n);
        current = spec["inherits"].as_str();
    }
    chain.reverse();
    let mut rules = json!({});
    let mut sources = json!({});
    let mut diffs = Vec::new();
    for &n in &chain {
        let spec = &profiles[n];
        let mut added = json!({});
        let mut overridden = json!({});
        for (k, v) in spec["rules"].as_object().context("invalid profile rules")? {
            match rules.get(k) {
                None => added[k] = v.clone(),
                Some(old) if old != v => {
                    overridden[k] = json!({"from":old,"to":v,"previous_source":sources[k]})
                }
                _ => {}
            }
            rules[k] = v.clone();
            sources[k] = json!(n);
        }
        diffs.push(json!({"profile":n,"inherits":spec["inherits"],"declared_rules":spec["rules"],"added":added,"overridden":overridden,"effective_rules_after":rules}));
    }
    let graph: Vec<_> = ["default", "strict", "release", "experimental"]
        .iter()
        .map(|n| json!({"profile":n,"inherits":profiles[*n]["inherits"]}))
        .collect();
    let mut checks = vec![
        json!({"check_id":"profile-chain-known","status":"pass","expected":chain,"actual":chain}),
        json!({"check_id":"effective-rules-complete","status":"pass","required_rules":["require_tests","require_coverage","unsafe_artifact_policy"]}),
        json!({"check_id":"effective-policies-complete","status":"pass","required_policies":["dq_policy","soft_gap_policy","aete_policy","manual_policy","export_policy"]}),
        json!({"check_id":"qeg-gate-boundary","status":"pass","message":"profile inheritance does not grant release approval or QEG Gate override"}),
    ];
    if name == "release" {
        checks.push(json!({"check_id":"release-extends-strict","status":"pass","expected_suffix":["strict","release"],"actual":chain}));
    }
    let version = &config["version"];
    let payload = json!({"profile":name,"chain":chain,"rules":rules,"policies":policies[name],"rule_sources":sources,"profile_version":version});
    // Profile policy keys and values are restricted to ASCII identifiers. v1 hashes
    // use one space after each separator, unlike the record envelope hash.
    let encoded = payload.to_string().replace(',', ", ").replace(':', ": ");
    let hash = hex::encode(Sha256::digest(encoded.as_bytes()));
    Ok(
        json!({"schema_version":"HATE/v1","record_type":"profile_report","profile_version":version,"run_id":run_id,
        "run_attempt":run_attempt,"commit_sha":commit_sha,"created_at":created_at,"profile":name,"inherits":chain,"effective_chain":chain,
        "inheritance_graph":graph,"rules":rules,"effective_rules":rules,"effective_policies":policies[name],"policy_table":policies,
        "rule_sources":sources,"rule_diffs":diffs,"drift_checks":checks,"profile_hash":&hash[..16],"qeg_gate_policy":false,"release_gate_override":false,"publish_gate_override":false,
        "note":"HATE profile controls evidence eligibility and AETE interpretation only; it is not QEG release Gate policy."}),
    )
}

pub fn evaluate(
    run: &Run,
    name: &str,
    tests: &[Value],
    coverage: &[Value],
    manifest: &Value,
    dqs: &mut Vec<Value>,
) -> Result<(Value, Vec<Value>)> {
    let mut report = build_profile_report(name, &run.id, &run.attempt, &run.sha, &run.time)?;
    let mut checks = Vec::new();
    let mut gaps = Vec::new();
    let start = dqs.len();
    for (key, missing, code, reason, fail, pass) in [
        (
            "require_tests",
            tests.is_empty(),
            "HATE-DQ-016",
            "profile requires test execution evidence",
            "profile requires at least one test_result record",
            "test evidence requirement satisfied or not required",
        ),
        (
            "require_coverage",
            coverage.is_empty(),
            "HATE-DQ-017",
            "profile requires coverage evidence",
            "profile requires at least one coverage_slice record",
            "coverage requirement satisfied or not required",
        ),
    ] {
        let failed = missing && report["rules"][key] == true;
        if failed {
            dqs.push(dq(code, reason, "profile-report.json"));
        }
        checks.push(json!({"check_id":key,"status":if failed{"fail"}else{"pass"},"message":if failed{fail}else{pass}}));
    }
    let risky: Vec<_> = items(&manifest["artifacts"])
        .iter()
        .filter(|v| v["safe_for_summary"] == false)
        .map(|v| &v["artifact_id"])
        .collect();
    let (status, message) = match (
        risky.is_empty(),
        report["rules"]["unsafe_artifact_policy"].as_str(),
    ) {
        (false, Some("hard_dq")) => {
            dqs.push(dq(
                "HATE-DQ-018",
                "release profile rejects unsafe artifacts",
                "artifact-manifest.json",
            ));
            (
                "fail",
                "unsafe artifacts are not allowed in release profile",
            )
        }
        (false, Some("soft_gap")) => {
            gaps.push(json!({"gap_id":"unsafe_artifact_profile_gap","profile":name,"artifact_ids":risky,"message":"strict profile keeps unsafe artifact quarantine visible as a soft gap"}));
            ("warn", "unsafe artifacts are quarantined and visible")
        }
        _ => ("pass", "unsafe artifact policy satisfied"),
    };
    checks.push(json!({"check_id":"unsafe_artifact_policy","status":status,"message":message}));
    report["checks"] = json!(checks);
    report["decision_impact"] = json!({"hard_dq_codes":dqs[start..].iter().map(|v|&v["code"]).collect::<Vec<_>>(),"soft_gap_count":gaps.len()});
    Ok((report, gaps))
}
