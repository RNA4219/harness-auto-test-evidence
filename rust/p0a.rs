mod artifacts;
mod coverage;
mod numbers;
mod profile;
mod schema;
mod strength;
mod tests;
use crate::{
    cli::Invocation,
    io::{items, object, resolve, stable_ref, write_json},
};
use anyhow::{Context, Result, ensure};
pub(crate) use numbers::{Document, canonical_json, exact_uint, hash as canonical_digest};
pub(crate) use profile::build_profile_report;
pub(crate) use schema::message as schema_message;
use serde_json::{Value, json};
use std::{
    fs,
    io::Write,
    path::{Path, PathBuf},
};

struct Run {
    id: String,
    attempt: Value,
    sha: String,
    time: String,
    version: String,
}
impl Run {
    fn envelope(&self, kind: &str, id: String, payload: Value) -> Value {
        let mut record = json!({"schema_version":"HATE/v1","record_type":kind,"record_id":id,"run_id":self.id,"run_attempt":self.attempt,
            "commit_sha":self.sha,"created_at":self.time,"source_tool":"harness-auto-test-evidence","source_version":self.version,
            "sha256":"","redaction_status":"not_required","payload":payload});
        record["sha256"] = json!(format!("sha256:{}", numbers::hash(&record)));
        record
    }
    fn record(&self, kind: &str, prefix: &str, suffix: &str, payload: Value) -> Value {
        self.envelope(
            kind,
            format!("{prefix}-{}-{}-{suffix}", self.id, self.attempt),
            payload,
        )
    }
    fn attempt_record(&self, kind: &str, prefix: &str, payload: Value) -> Value {
        self.envelope(
            kind,
            format!("{prefix}-{}-attempt-{}", self.id, self.attempt),
            payload,
        )
    }
    fn base(&self) -> Value {
        json!({"schema_version":"HATE/v1","run_id":self.id,"run_attempt":self.attempt,"commit_sha":self.sha,"created_at":self.time})
    }
}
fn slug(value: &str) -> String {
    let mut out = String::new();
    let mut separator = false;
    for c in value.to_lowercase().chars() {
        if c.is_ascii_alphanumeric() {
            if separator && !out.is_empty() {
                out.push('-')
            }
            out.push(c);
            separator = false
        } else {
            separator = true;
        }
    }
    if out.is_empty() { "item".into() } else { out }
}
fn dq(code: &str, msg: &str, source: &str) -> Value {
    json!({"code":code,"message":msg,"source_ref":source})
}
fn opt_object(path: &Path) -> Result<Value> {
    if path.try_exists()? {
        object(path)
    } else {
        Ok(json!({}))
    }
}
fn first(root: &Path, names: &[&str]) -> Option<PathBuf> {
    names.iter().map(|n| root.join(n)).find(|p| p.exists())
}
fn s(v: &Value) -> &str {
    v.as_str().unwrap_or("")
}
fn name(path: &Path) -> &str {
    path.file_name().and_then(|s| s.to_str()).unwrap_or("")
}
fn sha_valid(s: &str) -> bool {
    (7..=64).contains(&s.len()) && s.bytes().all(|c| c.is_ascii_hexdigit())
}

fn xml_error(e: &roxmltree::Error, text: &str) -> String {
    if matches!(
        e,
        roxmltree::Error::UnclosedRootNode
            | roxmltree::Error::NoRootNode
            | roxmltree::Error::UnexpectedEndOfStream
    ) {
        let row = text.bytes().filter(|b| *b == b'\n').count() + 1;
        let col = text.rsplit('\n').next().unwrap_or("").chars().count();
        return format!("no element found: line {row}, column {col}");
    }
    let p = e.pos();
    let msg = if matches!(e, roxmltree::Error::UnexpectedCloseTag(..)) {
        "mismatched tag"
    } else {
        "not well-formed (invalid token)"
    };
    format!("{msg}: line {}, column {}", p.row, p.col.saturating_sub(1))
}

fn context(path: &Path, version: &str) -> Result<(Run, Value)> {
    let parsed = numbers::Document::read(path, true)?;
    let c = &parsed.value;
    ensure!(c.is_object(), "{} must contain a JSON object", name(path));
    let missing: Vec<_> = [
        "repository",
        "workflow",
        "job",
        "run_id",
        "run_attempt",
        "started_at",
    ]
    .into_iter()
    .filter(|k| c.get(k).is_none())
    .collect();
    ensure!(
        missing.is_empty(),
        "{} missing fields: {}",
        name(path),
        missing.join(", ")
    );
    let loc = |key: &str| format!("{}.{}", name(path), key);
    let id = match &c["run_id"] {
        Value::String(id) if !id.trim().is_empty() => id.clone(),
        Value::Number(_)
            if parsed
                .token(&loc("run_id"))
                .is_some_and(|t| !t.contains(['.', 'e', 'E'])) =>
        {
            parsed.token(&loc("run_id")).unwrap().to_string()
        }
        _ => anyhow::bail!("{}.run_id: must be a non-empty run identifier", name(path)),
    };
    let attempt=numbers::run_attempt(&c["run_attempt"],parsed.token(&loc("run_attempt"))).with_context(||format!("{}.run_attempt: must be a positive integer; booleans and fractional values are invalid",name(path)))?;
    let time = c["finished_at"]
        .as_str()
        .filter(|s| !s.is_empty())
        .or_else(|| c["started_at"].as_str())
        .unwrap_or("");
    ensure!(
        !time.is_empty(),
        "{} requires finished_at or started_at",
        name(path)
    );
    let mut provider = c["provider"]
        .as_str()
        .filter(|s| !s.is_empty())
        .or_else(|| c["ci_provider"].as_str())
        .unwrap_or("")
        .trim()
        .to_lowercase()
        .replace('_', "-");
    provider = match provider.as_str() {
        "" if name(path) == "github-context.json" => "github-actions".into(),
        "" | "generic" | "genericci" => "generic-ci".into(),
        "github" | "github-action" => "github-actions".into(),
        _ => provider,
    };
    let sha = c
        .get("commit_sha")
        .map(numbers::stringify)
        .unwrap_or_default();
    let run = Run {
        id,
        attempt,
        sha,
        time: time.into(),
        version: version.into(),
    };
    let mut payload = json!({"repository":c["repository"],"workflow":c["workflow"],"job":c["job"],"event_name":c.get("event_name").cloned().unwrap_or(json!("unknown")),
        "started_at":c["started_at"],"finished_at":c["finished_at"],"ci":{"provider":provider,"run_id":run.id,"run_attempt":run.attempt,"actor":c["actor"],"ref":c["ref"]}});
    if sha_valid(s(&c["base_sha"])) {
        payload["base_sha"] = c["base_sha"].clone();
    }
    let record = run.attempt_record("run", "run", payload);
    Ok((run, record))
}

fn decision(run: &Run, dqs: &[Value], gaps: &[Value]) -> Value {
    let status = if !dqs.is_empty() {
        "hard_dq"
    } else if !gaps.is_empty() {
        "conditional"
    } else {
        "eligible"
    };
    let reasons = if status == "eligible" {
        json!([
            "Minimal P0a inputs satisfy HATE/v1 schema bootstrap contracts.",
            "QEG export is allowed as optional evidence and scheduled for P0b bundling."
        ])
    } else {
        json!(
            dqs.iter()
                .chain(gaps)
                .map(|hit| &hit["message"])
                .collect::<Vec<_>>()
        )
    };
    run.attempt_record("precheck_decision","precheck",json!({"decision":status,"exit_code":if dqs.is_empty(){0}else{2},"dq_hits":dqs,"soft_gaps":gaps,"reasons":reasons,"qeg_export_allowed":dqs.is_empty(),"qeg_export_ref":null,"qeg_export_phase":"P0b"}))
}

fn adapter<T>(
    path: &Path,
    label: &str,
    hits: &mut Vec<Value>,
    parse: impl FnOnce() -> Result<T>,
) -> Option<T> {
    if !path.exists() {
        return None;
    }
    match parse() {
        Ok(value) => Some(value),
        Err(error) => {
            hits.push(dq(
                "HATE-DQ-002",
                &format!("{label} parse failure: {error}"),
                name(path),
            ));
            None
        }
    }
}

pub fn run(call: &Invocation) -> Result<Value> {
    let root = resolve(call.path("input"))?;
    let out = call.path("out");
    let profile = s(&call.values["profile"]);
    let context_path = first(
        &root,
        &[
            "github-context.json",
            "ci-context.json",
            "generic-ci-context.json",
        ],
    )
    .context(
        "missing required input: github-context.json, ci-context.json, or generic-ci-context.json",
    )?;
    let version = call.values["source_version"]
        .as_str()
        .filter(|v| !v.is_empty())
        .unwrap_or(env!("CARGO_PKG_VERSION"));
    let (run, run_record) = context(&context_path, version)?;
    let mut dqs = Vec::new();
    if !sha_valid(&run.sha) {
        dqs.push(dq(
            "HATE-DQ-001",
            if run.sha.is_empty() {
                "commit_sha is missing"
            } else {
                "commit_sha is not a hex sha"
            },
            name(&context_path),
        ));
    }
    let mut adapter_errors = Vec::new();
    let mut tests = Vec::new();
    for (family, file) in [
        ("junit", "junit.xml"),
        ("pytest", "pytest-report.json"),
        ("vitest", "vitest-report.json"),
        ("jest", "jest-report.json"),
    ] {
        let path = root.join(file);
        if let Some(entries) = adapter(&path, family, &mut adapter_errors, || {
            tests::parse(&run, &path, family)
        }) {
            tests.extend(entries);
        }
    }
    let mut coverage = Vec::new();
    for (format, file) in [
        ("lcov", "lcov.info"),
        ("cobertura", "cobertura.xml"),
        ("jacoco", "jacoco.xml"),
        ("coverage.py", "coverage.json"),
    ] {
        let path = root.join(file);
        if let Some(entries) = adapter(&path, format, &mut adapter_errors, || {
            coverage::parse(&run, &path, format, &tests)
        }) {
            coverage.extend(entries);
        }
    }
    let mutations = first(
        &root,
        &["mutation.json", "stryker-report.json", "stryker.json"],
    )
    .and_then(|p| {
        adapter(&p, "stryker mutation", &mut adapter_errors, || {
            strength::mutations(&run, &p)
        })
    })
    .unwrap_or_default();
    let sarif = first(&root, &["results.sarif", "sarif.json", "HATE-static.sarif"]).and_then(|p| {
        adapter(&p, "sarif", &mut adapter_errors, || {
            let v = object(&p)?;
            ensure!(
                !v["version"].is_null() && v["runs"].is_array(),
                "SARIF requires version and runs"
            );
            for result in items(&v["runs"]).iter().flat_map(|r| items(&r["results"])) {
                let prop = &result["properties"];
                let severity = prop["security-severity"]
                    .as_str()
                    .filter(|s| !s.is_empty())
                    .or_else(|| prop["severity"].as_str())
                    .unwrap_or("")
                    .to_lowercase();
                if s(&result["level"]).eq_ignore_ascii_case("error")
                    || matches!(severity.as_str(), "high" | "critical")
                {
                    dqs.push(dq(
                        "HATE-DQ-010",
                        "unresolved high or critical SARIF finding",
                        "results.sarif",
                    ));
                }
            }
            Ok(v)
        })
    });
    dqs.extend(adapter_errors);
    if !coverage.is_empty() && tests.is_empty() {
        dqs.push(dq(
            "HATE-DQ-008",
            "coverage exists but no test execution result exists",
            "lcov.info",
        ));
    }
    let strength = strength::build(&run, &root, &tests, &mutations)?;
    let (manifest, quarantine) =
        artifacts::build(&run, &root, call.values["fixture_path_prefix"].as_str())?;
    if items(&manifest["artifacts"])
        .iter()
        .any(|v| v["security_checks"]["path_exists"] == "fail")
    {
        dqs.push(dq(
            "HATE-DQ-003",
            "artifact manifest references missing files",
            "artifact-refs.json",
        ));
    }
    if opt_object(&root.join("record-control.json"))?["force_record_missing"] == true {
        dqs.push(dq(
            "HATE-DQ-015",
            "record generation was forced to fail by fixture control",
            "record-control.json",
        ));
    }
    let control = opt_object(&root.join("dq-control.json"))?;
    for (key, code, msg) in [
        (
            "unresolved_flaky_over_threshold",
            "HATE-DQ-005",
            "unresolved flakiness is over threshold",
        ),
        (
            "high_risk_without_execution",
            "HATE-DQ-007",
            "high-risk changed path has no execution evidence",
        ),
        (
            "unresolved_high_critical_sarif",
            "HATE-DQ-010",
            "unresolved high or critical SARIF finding on changed path",
        ),
    ] {
        if control[key] == true {
            dqs.push(dq(code, msg, "dq-control.json"));
        }
    }
    let (profiles, gaps) =
        profile::evaluate(&run, profile, &tests, &coverage, &manifest, &mut dqs)?;
    let provisional = decision(&run, &dqs, &gaps);
    let mut outputs = vec![
        ("HATE-run.json", run_record),
        ("HATE-test-results.ndjson", json!(tests)),
        ("HATE-coverage.ndjson", json!(coverage)),
        ("HATE-evidence-strength.ndjson", json!(strength)),
        ("artifact-manifest.json", manifest),
        ("quarantine-report.json", quarantine),
        ("profile-report.json", profiles),
        ("precheck-decision.json", provisional),
    ];
    if let Some(value) = sarif {
        outputs.push(("HATE-static.sarif", value));
    }
    if !mutations.is_empty() {
        outputs.push(("HATE-mutation.ndjson", json!(mutations)));
    }
    let audit=run.attempt_record("audit_record","audit",json!({"validated_artifacts":outputs.iter().map(|(n,_)|*n).collect::<Vec<_>>(),"validation_result":"pass",
      "source_refs":[stable_ref(&context_path,true)?,stable_ref(&root.join("junit.xml"),true)?,stable_ref(&root.join("lcov.info"),true)?],
      "notes":["This record is generated from local P0a inputs and does not contain a release Gate verdict."]}));
    outputs.push(("record.json", audit));
    dqs.extend(schema::validate(&outputs)?);
    let precheck = decision(&run, &dqs, &gaps);
    let summary = summary(
        &run,
        &outputs[0].1["payload"]["repository"],
        &tests,
        &coverage,
        &strength,
        &outputs[4].1,
        &precheck,
    );
    outputs[7].1 = precheck.clone();
    fs::create_dir_all(out)?;
    for (file, data) in &outputs {
        let path = out.join(file);
        if file.ends_with(".ndjson") {
            let mut tmp = tempfile::NamedTempFile::new_in(out)?;
            for row in items(data) {
                writeln!(tmp, "{row}")?;
            }
            tmp.persist(path)?;
        } else {
            write_json(&path, data)?;
        }
    }
    fs::write(out.join("summary.md"), summary)?;
    if !dqs.is_empty() {
        return Err(crate::error::CommandFailure {
            code: 2,
            diagnostic: precheck.to_string(),
        }
        .into());
    }
    let mut generated: Vec<_> = outputs
        .iter()
        .map(|(n, _)| *n)
        .chain(["summary.md"])
        .collect();
    generated.sort();
    Ok(
        json!({"decision":precheck["payload"]["decision"],"exit_code":0,"generated":generated,"out_dir":out}),
    )
}

fn summary(
    run: &Run,
    repo: &Value,
    tests: &[Value],
    coverage: &[Value],
    strength: &[Value],
    manifest: &Value,
    decision: &Value,
) -> String {
    let passed = tests
        .iter()
        .filter(|v| v["payload"]["status"] == "passed")
        .count();
    let failed = tests
        .iter()
        .filter(|v| matches!(s(&v["payload"]["status"]), "error" | "failed"))
        .count();
    let coverage_line = if let Some(first) = coverage.first() {
        let hits: Vec<_> = coverage
            .iter()
            .filter_map(|v| v["payload"]["line_hits"].as_object())
            .flat_map(|m| m.values())
            .collect();
        let covered = hits.iter().filter(|v| v.as_i64().unwrap_or(0) > 0).count();
        let uncovered = hits.len() - covered;
        format!(
            "Coverage sample: `{}` has {covered} covered lines and {uncovered} uncovered line{}",
            s(&first["payload"]["file"]),
            if uncovered == 1 { "" } else { "s" }
        )
    } else {
        "No coverage records generated".into()
    };
    let flake = strength
        .iter()
        .filter(|v| v["payload"]["flake_score"].is_number())
        .count();
    let mutation = strength
        .iter()
        .filter(|v| v["payload"]["mutation_score"].is_number())
        .count();
    let n = strength.len();
    let names = items(&manifest["artifacts"])
        .iter()
        .map(|v| s(&v["artifact_id"]))
        .collect::<Vec<_>>()
        .join(", ");
    format!(
        "# P0a Minimal Evidence Summary\n\n- Run: `{}` attempt `{}`\n- Repository: `{}`\n- Commit: `{}`\n- Test result: {passed} passed, {failed} failed\n- {coverage_line}\n- Evidence strength: {n} tests, flake known {flake}/unknown {}, mutation known {mutation}/unknown {}\n- Precheck: {} for optional QEG evidence export in P0b\n- Generated artifacts: {}\n\nThis summary is public-safe and generated from local P0a inputs.\n",
        run.id,
        run.attempt,
        s(repo),
        run.sha.chars().take(40).collect::<String>(),
        n - flake,
        n - mutation,
        s(&decision["payload"]["decision"]),
        if names.is_empty() { "none" } else { &names }
    )
}
