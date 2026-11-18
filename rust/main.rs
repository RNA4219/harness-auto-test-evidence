mod bridge;
mod cli;
mod downstream;
mod error;
mod history;
mod io;
mod materialize;
mod p0a;
mod platform;
mod process;
mod qeg;
mod roster;
mod runner;
mod store;
mod trust;

use anyhow::{Result, bail};
use cli::{Invocation, Node};
use serde_json::Value;
use std::process::ExitCode;

fn run(call: &Invocation) -> Result<Value> {
    if let Some(route) = call.route {
        if bridge::provider(call)? == "handoff" {
            return bridge::handoff(call, route);
        }
        eprintln!(
            "HATE-W-BRIDGE-DEPRECATED: post-P1a compatibility behavior is frozen; canonical owner is {}; remove_after=1.0.0",
            route.owner
        );
    }
    let mut value = match call.command.as_str() {
        "bridge materialize" => materialize::run(call),
        "p0a" => p0a::run(call),
        "export qeg" => qeg::run(call),
        "trust evaluate" | "doctor" | "recommend" | "replay" | "compare" | "explain" => {
            trust::run(call)
        }
        "store ingest" | "store query" | "store history" => store::run(call),
        "real-repo history-ingest" => history::ingest(call),
        "platform run" | "real-repo run" => roster::run(call),
        "platform history" | "real-repo history-query" => history::query(call),
        "workflow map"
        | "product readiness"
        | "product query"
        | "product grade-reports"
        | "product serve"
        | "platform serve"
        | "release candidate"
        | "gap closure"
        | "expansion run"
        | "validation cycles" => downstream::run(call),
        cmd if cmd.starts_with("platform ") => platform::run(call),
        command => bail!("unknown command: {command}"),
    }?;
    if let Some(route) = call.route
        && value.is_object()
    {
        value["compatibility_provider"] = "compat-v0.2".into();
        value["canonical_owner"] = route.owner.as_str().into();
        value["deprecated_since"] = "0.3.0".into();
        value["remove_after"] = "1.0.0".into();
    }
    Ok(value)
}

fn main() -> ExitCode {
    let cli = Node::load();
    let matches = cli.parser().get_matches();
    let call = cli.parse(&matches).expect("CLI matches its contract");
    match run(&call) {
        Ok(value) => {
            if !value.is_null() {
                println!("{value}");
            }
            ExitCode::SUCCESS
        }
        Err(e) if e.is::<error::CommandFailure>() => {
            let failure = e.downcast_ref::<error::CommandFailure>().unwrap();
            eprintln!("{}", failure.diagnostic);
            ExitCode::from(failure.code)
        }
        Err(e) => {
            let (prefix, code) = if call.route.is_some()
                && bridge::provider(&call).as_deref().ok() != Some("compat-v0.2")
            {
                ("BRIDGE", 2)
            } else {
                match call.command.split_whitespace().next().unwrap_or("") {
                    "p0a" => ("CLI", 1),
                    "compare" => ("COMPARE", 1),
                    "replay" => ("REPLAY", 1),
                    "explain" => ("EXPLAIN", 1),
                    "doctor" => ("DOCTOR", 1),
                    "recommend" => ("RECOMMEND", 1),
                    "trust" => ("TRUST", 1),
                    "store" => ("STORE", 2),
                    "platform" => ("PLATFORM", 2),
                    "real-repo" if call.command.contains("history") => ("REAL-REPO-HISTORY", 2),
                    "real-repo" => ("REAL-REPO", 2),
                    "export" => ("EXPORT", 1),
                    "bridge" => ("BRIDGE", 2),
                    _ => ("CLI", 1),
                }
            };
            eprintln!("HATE-E-{prefix}: {e:#}");
            ExitCode::from(code)
        }
    }
}
