use crate::cli::Invocation;
use crate::error::CommandFailure;
use crate::io::is_truthy as truth;
use anyhow::{Result, bail};
use serde_json::{Value, json};
use std::path::Path;

mod query;
mod rules;
mod validation;

pub(crate) fn rule(name: &str, args: Vec<Value>) -> Result<Value> {
    rules::execute(name, args)
}

fn failure(code: u8, diagnostic: String) -> anyhow::Error {
    CommandFailure { code, diagnostic }.into()
}

fn required_dir(path: &Path, prefix: &str, label: &str) -> Result<()> {
    if !path.exists() {
        return Err(failure(
            2,
            format!("{prefix}: {label} not found: {}", path.display()),
        ));
    }
    Ok(())
}

pub fn run(call: &Invocation) -> Result<Value> {
    match call.command.as_str() {
        "product query" => query::cli(call),
        "product serve" | "platform serve" => query::serve(call),
        "validation cycles" => validation::run(call),
        name => {
            let (builder, keys): (&str, &[&str]) = match name {
                "workflow map" => (
                    "p1b__generate_workflow_mapping",
                    &[
                        "bundle",
                        "report",
                        "trust",
                        "out",
                        "rand_requirements",
                        "rand_audit",
                        "shipyard_worker_result",
                        "shipyard_run_system_packet",
                        "source_version",
                    ],
                ),
                "product readiness" => (
                    "p2p3__generate_product_readiness",
                    &["bundle", "trust", "workflow", "out", "source_version"],
                ),
                "product grade-reports" => (
                    "product_grade__generate_product_grade_reports",
                    &["docs_root", "out", "source_version", "repo_root"],
                ),
                "expansion run" => (
                    "expansion_runner__run_expansion_suite",
                    &["fixtures_root", "out", "area", "case_kind"],
                ),
                "release candidate" => (
                    "compat__v0_2__handlers__assemble_release_candidate",
                    &[
                        "readiness",
                        "out",
                        "release_id",
                        "source_version",
                        "dry_run",
                    ],
                ),
                "gap closure" => (
                    "gap_closure__generate_gap_closure_report",
                    &["repo_root", "out", "source_version"],
                ),
                _ => bail!("unknown downstream command {name}"),
            };
            let args = keys
                .iter()
                .map(|k| call.values.get(*k).cloned().unwrap_or_default())
                .collect();
            rule(builder, args)
        }
    }
}

fn opt<'a>(call: &'a Invocation, key: &str, default: &'a str) -> &'a str {
    call.values
        .get(key)
        .and_then(Value::as_str)
        .unwrap_or(default)
}

fn field<'a>(v: &'a Value, key: &str, fallback: &'a str) -> &'a str {
    v[key]
        .as_str()
        .filter(|s| !s.is_empty())
        .unwrap_or(fallback)
}

fn string_list(v: &Value) -> Vec<String> {
    crate::io::items(v)
        .iter()
        .map(crate::io::py_string)
        .filter(|s| !s.is_empty())
        .collect()
}

fn read_artifact(p: &Path, prefix: &str) -> Result<Value> {
    if !p.exists() {
        return Err(failure(
            2,
            format!(
                "{prefix}: required JSON artifact not found: {}",
                p.display()
            ),
        ));
    }
    let value = crate::io::read_json(p).map_err(|e| failure(1, format!("{prefix}: {e:#}")))?;
    if !value.is_object() {
        return Err(failure(
            1,
            format!(
                "{prefix}: {} must contain a JSON object",
                p.file_name().unwrap_or_default().to_string_lossy()
            ),
        ));
    }
    Ok(value)
}

fn obj() -> Value {
    json!({})
}
