use super::{failure, field, string_list, truth};
use crate::{
    cli::Invocation,
    io::{items, object, write_json},
};
use anyhow::{Context, Result};
use serde_json::{Value, json};

const STEPS: [&str; 5] = ["RanD", "Code-to-gate", "HATE", "manual-bb", "QEG"];

fn integer(v: &Value, default: i64) -> Result<i64> {
    if !truth(v) {
        return Ok(default);
    }
    if let Some(i) = v.as_i64() {
        return Ok(i);
    }
    if let Some(f) = v.as_f64() {
        return Ok(f as i64);
    }
    if let Some(b) = v.as_bool() {
        return Ok(i64::from(b));
    }
    v.as_str()
        .and_then(|s| s.parse().ok())
        .context("invalid integer in validation cycle")
}

fn normalize(raw: &Value) -> Result<Value> {
    let mut c = json!({"cycle_id":field(raw,"cycle_id",""),"missing_possibility":field(raw,"missing_possibility","")});
    for key in [
        "requirement_refs",
        "spec_refs",
        "implementation_refs",
        "test_refs",
        "sourceRefs",
    ] {
        c[key] = json!(string_list(&raw[key]));
    }
    for step in STEPS {
        c["chain_status"][step] = json!(field(&raw["chain_status"], step, ""));
    }
    let manual = &raw["manual_bb"];
    c["manual_bb"] = json!({"brief_ref":field(manual,"brief_ref",""),"open_blockers":string_list(&manual["open_blockers"]),"p0_case_count":integer(&manual["p0_case_count"],0)?});
    for key in [
        "bundle_ref",
        "validate_status",
        "import_status",
        "gate_status",
        "record_ref",
    ] {
        c["qeg_package"][key] = json!(field(&raw["qeg_package"], key, ""));
    }
    c["qeg_package"]["approval_claimed_by_hate"] =
        json!(truth(&raw["qeg_package"]["approval_claimed_by_hate"]));
    let pack = &raw["release_candidate_pack"];
    c["release_candidate_pack"] = json!({"verdict":field(pack,"verdict",""),"blocker_count":integer(&pack["summary"]["blocker_count"],0)?,"release_ready":truth(&pack["summary"]["release_ready"])});
    Ok(c)
}
fn finding(code: &str, source: &str, message: &str) -> Value {
    json!({"code":format!("validation_cycle_{code}"),"severity":"critical","message":message,"sourceRef":source,"readiness_effect":"hard_dq"})
}

fn evaluate(c: &Value) -> Vec<Value> {
    let id = field(c, "cycle_id", "cycle");
    let mut findings = Vec::new();
    let mut add = |code, message: &str| findings.push(finding(code, id, message));
    for key in [
        "missing_possibility",
        "requirement_refs",
        "spec_refs",
        "implementation_refs",
        "test_refs",
        "sourceRefs",
    ] {
        if !truth(&c[key]) {
            add("missing_trace", &format!("{key} is required."));
        }
    }
    for step in STEPS {
        if c["chain_status"][step] != "ran" {
            add(
                "chain_not_ran",
                &format!("{step} must be ran before cycle go."),
            );
        }
    }
    let manual = &c["manual_bb"];
    if manual["brief_ref"] == "" || manual["p0_case_count"].as_i64().unwrap_or(0) <= 0 {
        add(
            "manual_bb_incomplete",
            "manual-bb brief and P0 cases are required.",
        );
    }
    if truth(&manual["open_blockers"]) {
        add(
            "manual_bb_blocker_open",
            "manual-bb open blockers prevent go.",
        );
    }
    let q = &c["qeg_package"];
    if q["bundle_ref"] == "" || q["record_ref"] == "" {
        add(
            "qeg_refs_missing",
            "QEG bundle and record refs are required.",
        );
    }
    if q["validate_status"] != "pass" || q["import_status"] != "pass" {
        add("qeg_package_failed", "QEG validate/import must pass.");
    }
    if q["gate_status"] != "go" {
        add("qeg_gate_not_go", "QEG gate status must be go.");
    }
    if q["approval_claimed_by_hate"] == true {
        add(
            "qeg_approval_overclaim",
            "HATE must not claim QEG final approval.",
        );
    }
    let rc = &c["release_candidate_pack"];
    if rc["verdict"] != "ready" || rc["blocker_count"] != 0 || rc["release_ready"] != true {
        add(
            "release_pack_not_ready",
            "Release candidate pack must be ready without blockers.",
        );
    }
    findings
}

pub fn run(call: &Invocation) -> Result<Value> {
    let input = object(call.path("fixture"))
        .map_err(|e| failure(2, format!("HATE-E-VALIDATION-CYCLES: {e:#}")))?;
    let id = field(&input, "fixture_id", "validation-cycle-fixture");
    let data = input.get("input").unwrap_or(&input);
    let mut cycles: Vec<Value> = items(&data["cycles"])
        .iter()
        .filter(|c| c.is_object())
        .map(normalize)
        .collect::<Result<_>>()?;
    let expected = integer(&data["expected_cycle_count"], 10)?;
    let mut findings = Vec::new();
    if cycles.len() as i64 != expected {
        findings.push(finding(
            "count_mismatch",
            "validation-cycles",
            &format!(
                "Expected {expected} validation cycles but found {}.",
                cycles.len()
            ),
        ));
    }
    let mut go_count = 0;
    let mut qeg_go = 0;
    for c in &mut cycles {
        let errors = evaluate(c);
        let ok = errors.is_empty();
        go_count += usize::from(ok);
        qeg_go += usize::from(c["qeg_package"]["gate_status"] == "go");
        c["cycle_verdict"] = json!(if ok { "go" } else { "no_go" });
        c["finding_count"] = json!(errors.len());
        findings.extend(errors);
    }
    let ok = findings.is_empty();
    let report = json!({"schema_version":"HATE/v1","record_type":"validation-cycle-report","report_id":id,
        "overall_status":if ok {"pass"} else {"blocked"},"readiness_effect":if ok {"pass"} else {"hard_dq"},
        "verdict":if ok {"go"}else{"no_go"},"expected_cycle_count":expected,"cycles":cycles,"findings":findings,
        "summary":{"cycle_count":cycles.len(),"go_cycle_count":go_count,"no_go_cycle_count":cycles.len()-go_count,
            "finding_count":findings.len(),"hard_dq_count":findings.len(),"qeg_go_count":qeg_go},
        "qeg_final_approval_claimed":false,"limits":{"qeg_is_final_gate":true,"hate_must_not_claim_qeg_approval":true,
            "manual_bb_blockers_allowed_for_go":false},"sourceRefs":[id]});
    write_json(
        &call.path("out").join("validation-cycle-report.json"),
        &report,
    )?;
    if !ok {
        return Err(failure(2, report.to_string()));
    }
    Ok(report)
}
