use super::{command, items, merge, text};
use crate::{
    io::parent,
    process::{self, ProcessResult},
    runner,
};
use anyhow::{Context, Result};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, HashSet},
    env,
    path::{Path, PathBuf},
    time::Instant,
};

fn cleanup() -> Value {
    json!({"timeout_reason":"none","cleanup_attempted":false,"cleanup_method":"none","cleanup_completed":null,"fallback_kill_used":false})
}
fn no_split() -> Value {
    json!({"status":"not_configured","mode":"single","configured":false,"split_count":0,"completed_count":0,"skipped_count":0,"resume_required":false,"resume_token":"","splits":[]})
}
fn boolean(v: &Value) -> bool {
    match v {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::String(s) => !s.is_empty(),
        Value::Number(n) => n.as_f64() != Some(0.),
        Value::Array(a) => !a.is_empty(),
        Value::Object(m) => !m.is_empty(),
    }
}
fn timeout(entry: &Value) -> Result<u64> {
    if !entry["timeout_ms"].is_null() {
        return uint(&entry["timeout_ms"]).context("invalid timeout_ms");
    }
    let budgets = |s: &str| match s {
        "small" => Some(900000),
        "medium" => Some(1800000),
        "large" => Some(2700000),
        "xlarge" | "monorepo" => Some(3600000),
        _ => None,
    };
    Ok(budgets(text(&entry["timeout_profile"], ""))
        .or_else(|| budgets(&text(&entry["repo_class"], "").to_lowercase()))
        .unwrap_or(900000))
}
fn uint(v: &Value) -> Option<u64> {
    v.as_u64().or_else(|| v.as_str()?.parse().ok())
}
fn budget(v: &Value, default: u64) -> u64 {
    uint(v).filter(|n| *n != 0).unwrap_or(default)
}
fn normalize(cmd: &[String]) -> Vec<String> {
    if cfg!(windows)
        && let Some(exe) = cmd.first()
        && Path::new(exe).extension().is_none()
        && let Some(path) = env::var_os("PATH")
    {
        let name = format!("{exe}.cmd");
        if let Some(shim) = env::split_paths(&path)
            .map(|p| p.join(&name))
            .find(|p| p.is_file())
        {
            let mut out = cmd.to_vec();
            out[0] = shim.to_string_lossy().into_owned();
            return out;
        }
    }
    cmd.to_vec()
}
struct Runtime {
    cwd: PathBuf,
    env: BTreeMap<String, String>,
}
impl Runtime {
    fn new(entry: &Value, roster: &Path) -> Self {
        let mut vars: BTreeMap<_, _> = env::vars_os()
            .filter_map(|(k, v)| Some((k.into_string().ok()?, v.into_string().ok()?)))
            .collect();
        vars.retain(|key, _| {
            ![
                "PYTHONHOME",
                "PYTHONPATH",
                "PYTEST_CURRENT_TEST",
                "UV_PROJECT_ENVIRONMENT",
                "VIRTUAL_ENV",
            ]
            .iter()
            .any(|k| {
                if cfg!(windows) {
                    k.eq_ignore_ascii_case(key)
                } else {
                    *k == key
                }
            })
        });
        if let Some(overrides) = entry["env"].as_object() {
            for (k, v) in overrides {
                if let Some(s) = v.as_str() {
                    vars.insert(k.clone(), s.into());
                }
            }
        }
        Self {
            cwd: parent(roster).join(text(&entry["path"], ".")),
            env: vars,
        }
    }
    fn execute(&self, cmd: &[String], timeout: u64) -> Result<ProcessResult> {
        let mut result = process::execute(&normalize(cmd), &self.cwd, &self.env, timeout, None)?;
        if result.launch_failed {
            result.stdout.clear();
            result.stderr.clear();
        } else {
            result.stdout = result.stdout.replace("\r\n", "\n").replace('\r', "\n");
            result.stderr = result.stderr.replace("\r\n", "\n").replace('\r', "\n");
        }
        result.cleanup["timeout_reason"] = json!(if result.timed_out {
            "command_timeout_exceeded"
        } else {
            "none"
        });
        Ok(result)
    }
    fn bootstrap(&self, e: &Value) -> Result<Value> {
        let cmd = if let Some(values) = e["bootstrap"]["command"].as_array() {
            values
                .iter()
                .filter_map(|v| v.as_str().map(str::to_owned))
                .collect()
        } else {
            command(&e["bootstrap_command"])
                .or_else(|| command(&e["dependency_bootstrap_command"]))
                .unwrap_or_default()
        };
        if cmd.is_empty() {
            return Ok(
                json!({"status":"not_configured","command_configured":false,"exit_code":null,"runtime_ms":0,"timeout_recorded":false,"command_excerpt":"","output_safety":{},"timeout_cleanup":cleanup()}),
            );
        }
        let ms = budget(
            &e["bootstrap_timeout_ms"],
            budget(&e["bootstrap"]["timeout_ms"], 300000),
        );
        let started = Instant::now();
        let p = self.execute(&cmd, ms)?;
        let duration = started.elapsed().as_millis() as u64;
        let output = runner::safe_output(&p.stdout, &p.stderr);
        Ok(
            json!({"status":if p.timed_out||p.launch_failed||p.exit_code!=0{"hold"}else{"pass"},"command_configured":true,"command":cmd,
            "exit_code":p.exit_code,"runtime_ms":duration,"timeout_ms":ms,"timeout_recorded":p.timed_out,"command_excerpt":output["excerpt"],"output_safety":output["metadata"],"timeout_cleanup":p.cleanup}),
        )
    }
}

fn failure(p: &ProcessResult) -> &'static str {
    if p.timed_out {
        return "timeout";
    }
    if p.launch_failed {
        return "command_launch_failed";
    }
    if p.exit_code == 0 {
        return "";
    }
    let text = format!("{}\n{}", p.stdout, p.stderr).to_lowercase();
    let has = |patterns: &[&str]| patterns.iter().any(|s| text.contains(s));
    if has(&[
        "is not recognized as an internal or external command",
        "cannot find module",
        "modulenotfounderror: no module named",
        "no module named ",
    ]) {
        return "missing_test_dependency";
    }
    if text.contains("minversion")
        && text.contains("requires pytest")
        && text.contains("actual pytest")
    {
        return "runner_config_mismatch";
    }
    if has(&[
        "failed to fetch",
        "pypi.org/simple",
        "tcp connect error",
        "network",
        "dns",
        "socket",
    ]) && has(&[
        "failed to resolve requirements",
        "failed to build",
        "no solution found",
        "build-system.requires",
    ]) {
        return "dependency_network_blocked";
    }
    if has(&[" failures ", " failed", " errors ", " error collecting "]) {
        return "test_failure";
    }
    ""
}
struct SplitPlan {
    commands: Vec<Vec<String>>,
    completed: HashSet<String>,
    resume: String,
}
impl SplitPlan {
    fn read(e: &Value) -> Self {
        let opts = if boolean(&e["split_execution"]) {
            &e["split_execution"]
        } else {
            &e["timeout_strategy"]
        };
        let commands = [
            &opts["commands"],
            &opts["split_commands"],
            &e["split_commands"],
        ]
        .into_iter()
        .find(|v| boolean(v))
        .map(items)
        .unwrap_or_default()
        .iter()
        .filter_map(command)
        .collect();
        let done = if boolean(&opts["completed_splits"]) {
            &opts["completed_splits"]
        } else {
            &e["completed_splits"]
        };
        let completed = items(done)
            .iter()
            .filter_map(|v| {
                v.as_str()
                    .map(str::to_owned)
                    .or_else(|| v.as_i64().map(|n| n.to_string()))
            })
            .collect();
        Self {
            commands,
            completed,
            resume: text(&opts["resume_token"], text(&e["resume_token"], "")).into(),
        }
    }
    fn run(
        &self,
        rt: &Runtime,
        e: &Value,
        original: &[String],
        ms: u64,
        bootstrap: &Value,
    ) -> Result<Value> {
        let start = Instant::now();
        let mut records = Vec::new();
        let mut totals = BTreeMap::<String, i64>::new();
        let mut stdout = Vec::new();
        let mut stderr = Vec::new();
        let mut timeouts = false;
        let mut failed = false;
        let mut skipped = 0;
        let mut passed = 0;
        for (i, cmd) in self.commands.iter().enumerate() {
            let id = (i + 1).to_string();
            if self.completed.contains(&id) {
                skipped += 1;
                records.push(json!({"split_id":id,"status":"skipped_completed","exit_code":0,"record_count":0,"timeout_recorded":false}));
                continue;
            }
            let p = rt.execute(cmd, ms)?;
            let hold = p.timed_out || p.exit_code != 0 || p.launch_failed;
            timeouts |= p.timed_out;
            failed |= hold;
            passed += usize::from(!hold);
            let parser = runner::parse(&p.stdout, &p.stderr);
            let summary = &parser["summary"];
            if let Some(counts) = summary.as_object() {
                for (k, v) in counts {
                    if let Some(n) = v.as_i64() {
                        *totals.entry(k.clone()).or_default() += n;
                    }
                }
            }
            records.push(json!({"split_id":id,"status":if hold{"hold"}else{"pass"},"exit_code":p.exit_code,
                "record_count":summary["total_tests"].as_i64().filter(|n|*n!=0).unwrap_or(i64::from(p.exit_code==0)),"timeout_recorded":p.timed_out,
                "runner_dialect":parser["dialect"],"runner_parser":{"parser_status":parser["parser_status"],"ignored_noise":parser["ignored_noise"]},"timeout_cleanup":p.cleanup}));
            stdout.push(p.stdout);
            stderr.push(p.stderr);
        }
        let duration =
            start.elapsed().as_millis() as u64 + uint(&bootstrap["runtime_ms"]).unwrap_or(0);
        let total = *totals.entry("total_tests".into()).or_insert_with(|| {
            records
                .iter()
                .filter_map(|r| r["record_count"].as_i64())
                .sum()
        });
        let safe = runner::safe_output(&stdout.join("\n"), &stderr.join("\n"));
        let status = if failed { "hold" } else { "pass" };
        let cleanup = if timeouts {
            json!({"timeout_reason":"split_timeout_recorded","cleanup_attempted":true,"cleanup_method":"per_split","cleanup_completed":true,"fallback_kill_used":false})
        } else {
            cleanup()
        };
        Ok(
            json!({"current_decision":status,"current_record_count":e.get("current_record_count").cloned().unwrap_or(json!(total)),
            "parser_status":"passed","runtime_ms":duration,"runtime_budget_ms":budget(&e["runtime_budget_ms"],ms.saturating_mul(self.commands.len() as u64)),
            "timed_out":timeouts,"timeout_recorded":timeouts,"timeout_cleanup":cleanup,"command_exit_code":i32::from(failed),
            "failure_kind":if timeouts{"timeout"}else if failed{"test_failure"}else{""},"command_summary":totals,"runner_dialect":"split",
            "runner_parser":{"parser_status":if total!=0{"parsed"}else{"unparsed"},"ignored_noise":[]},
            "split_execution":{"status":status,"mode":"split","configured":true,"split_count":self.commands.len(),"completed_count":passed,
            "skipped_count":skipped,"resume_required":skipped>0||timeouts,"resume_token":self.resume,"splits":records,"original_command":normalize(original)},
            "command_excerpt":safe["excerpt"],"output_safety":safe["metadata"]}),
        )
    }
}

pub fn run(e: &Value, roster: &Path, command: Option<Vec<String>>) -> Result<Value> {
    let ms = timeout(e)?;
    let rt = Runtime::new(e, roster);
    let mut out = json!({"timeout_ms":ms,"runtime_budget_ms":ms,"subset":boolean(&e["subset"])||boolean(&e["subset_command"])});
    let Some(cmd) = command else {
        merge(
            &mut out,
            json!({"current_decision":"hold","parser_status":"failed","runtime_ms":0,"command_exit_code":127,"timeout_cleanup":cleanup()}),
        );
        return Ok(out);
    };
    let bootstrap = rt.bootstrap(e)?;
    let budget = budget(&e["runtime_budget_ms"], ms);
    let plan = SplitPlan::read(e);
    let result = if bootstrap["status"] == "hold" {
        json!({"current_decision":"hold","current_record_count":0,"parser_status":"passed","runtime_ms":bootstrap["runtime_ms"],"runtime_budget_ms":budget,
            "timed_out":bootstrap["timeout_recorded"],"timeout_recorded":bootstrap["timeout_recorded"],"timeout_cleanup":bootstrap["timeout_cleanup"],
            "command_exit_code":bootstrap["exit_code"].as_i64().filter(|n|*n!=0).unwrap_or(1),"failure_kind":"bootstrap_failed","command_summary":{},"runner_dialect":"unknown",
            "runner_parser":{"parser_status":"unparsed","ignored_noise":[]},"split_execution":no_split(),"command_excerpt":bootstrap["command_excerpt"],"output_safety":bootstrap["output_safety"]})
    } else if !plan.commands.is_empty() {
        plan.run(&rt, e, &cmd, ms, &bootstrap)?
    } else {
        let started = Instant::now();
        let p = rt.execute(&cmd, ms)?;
        let duration = started.elapsed().as_millis() as u64;
        let hold = p.timed_out || p.exit_code != 0 || p.launch_failed;
        let parser = runner::parse(&p.stdout, &p.stderr);
        let summary = &parser["summary"];
        let count = summary["total_tests"]
            .as_i64()
            .filter(|n| *n != 0)
            .unwrap_or(i64::from(p.exit_code == 0));
        let safe = runner::safe_output(&p.stdout, &p.stderr);
        json!({"current_decision":if hold{"hold"}else{"pass"},"current_record_count":e.get("current_record_count").cloned().unwrap_or(json!(count)),
          "parser_status":if p.launch_failed{"failed"}else{"passed"},"runtime_ms":duration,"runtime_budget_ms":budget,"timed_out":p.timed_out,
          "timeout_recorded":p.timed_out,"timeout_cleanup":p.cleanup,"command_exit_code":p.exit_code,"failure_kind":failure(&p),"command_summary":summary,
          "runner_dialect":parser["dialect"],"runner_parser":{"parser_status":parser["parser_status"],"ignored_noise":parser["ignored_noise"]},
          "split_execution":no_split(),"command_excerpt":safe["excerpt"],"output_safety":safe["metadata"]})
    };
    merge(&mut out, result);
    out["bootstrap"] = bootstrap;
    out["subset_label"] = json!(text(&e["subset_label"], ""));
    Ok(out)
}
