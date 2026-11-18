mod execution;
use crate::{
    cli::Invocation,
    downstream::rule,
    io::{digest, items, object, write_json},
};
use anyhow::{Context, Result, ensure};
use chrono::{SecondsFormat, Utc};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{env, fs, io::Write, path::Path};

fn text<'a>(v: &'a Value, default: &'a str) -> &'a str {
    v.as_str().filter(|s| !s.is_empty()).unwrap_or(default)
}
fn merge(dest: &mut Value, v: Value) {
    if let Value::Object(map) = v {
        dest.as_object_mut().expect("object").extend(map);
    }
}
fn now() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Secs, true)
}
fn stable_id(prefix: &str, parts: &[&str]) -> String {
    let hash = hex::encode(Sha256::digest(parts.join("\0").as_bytes()));
    format!("{prefix}-{}", &hash[..16])
}
fn safe_id(id: &str) -> String {
    let id: String = id
        .trim()
        .chars()
        .map(|c| {
            if c.is_alphanumeric() || c == '-' || c == '_' {
                c
            } else {
                '-'
            }
        })
        .collect();
    let id = id.trim_matches('-');
    if id.is_empty() {
        "repo".into()
    } else {
        id.into()
    }
}

#[cfg(any(windows, test))]
fn windows_release_name(version: (u32, u32, u32), product_type: u8) -> Option<&'static str> {
    // NT build numbers overlap between client and server editions.
    let releases: &[((u32, u32, u32), &str)] = match product_type {
        1 => &[
            ((10, 1, 0), "post11"),
            ((10, 0, 22000), "11"),
            ((6, 4, 0), "10"),
            ((6, 3, 0), "8.1"),
            ((6, 2, 0), "8"),
            ((6, 1, 0), "7"),
            ((6, 0, 0), "Vista"),
            ((5, 2, 3790), "XP64"),
            ((5, 2, 0), "XPMedia"),
            ((5, 1, 0), "XP"),
            ((5, 0, 0), "2000"),
        ],
        2 | 3 => &[
            ((10, 1, 0), "post2025Server"),
            ((10, 0, 26100), "2025Server"),
            ((10, 0, 20348), "2022Server"),
            ((10, 0, 17763), "2019Server"),
            ((6, 4, 0), "2016Server"),
            ((6, 3, 0), "2012ServerR2"),
            ((6, 2, 0), "2012Server"),
            ((6, 1, 0), "2008ServerR2"),
            ((6, 0, 0), "2008Server"),
            ((5, 2, 0), "2003Server"),
            ((5, 0, 0), "2000Server"),
        ],
        _ => return None,
    };
    releases
        .iter()
        .find_map(|&(minimum, release)| (version >= minimum).then_some(release))
}

#[cfg(windows)]
fn windows_release() -> Option<String> {
    #[repr(C)]
    struct Version {
        size: u32,
        major: u32,
        minor: u32,
        build: u32,
        platform: u32,
        service_pack: [u16; 128],
        service_pack_major: u16,
        service_pack_minor: u16,
        suite_mask: u16,
        product_type: u8,
        reserved: u8,
    }
    #[link(name = "ntdll")]
    unsafe extern "system" {
        fn RtlGetVersion(info: *mut Version) -> i32;
    }
    let mut version = Version {
        size: std::mem::size_of::<Version>() as u32,
        major: 0,
        minor: 0,
        build: 0,
        platform: 0,
        service_pack: [0; 128],
        service_pack_major: 0,
        service_pack_minor: 0,
        suite_mask: 0,
        product_type: 0,
        reserved: 0,
    };
    // The extended RTL_OSVERSIONINFOEXW layout requests wProductType as well as the build.
    let status = unsafe { RtlGetVersion(&mut version) };
    if status < 0 {
        return None;
    }
    windows_release_name(
        (version.major, version.minor, version.build),
        version.product_type,
    )
    .map(str::to_owned)
}
#[cfg(not(windows))]
fn windows_release() -> Option<String> {
    None
}

#[cfg(test)]
mod windows_tests {
    use super::windows_release_name;

    #[test]
    fn distinguishes_workstations_domain_controllers_and_servers_at_release_boundaries() {
        for (build, client, server) in [
            (17762, "10", "2016Server"),
            (17763, "10", "2019Server"),
            (20347, "10", "2019Server"),
            (20348, "10", "2022Server"),
            (21999, "10", "2022Server"),
            (22000, "11", "2022Server"),
            (26099, "11", "2022Server"),
            (26100, "11", "2025Server"),
        ] {
            assert_eq!(windows_release_name((10, 0, build), 1), Some(client));
            for product_type in [2, 3] {
                assert_eq!(
                    windows_release_name((10, 0, build), product_type),
                    Some(server)
                );
            }
        }
        assert_eq!(windows_release_name((10, 0, 26100), 0), None);
    }
}

fn fingerprint() -> Value {
    let os = match env::consts::OS {
        "windows" => "Windows",
        "linux" => "Linux",
        "macos" => "Darwin",
        "freebsd" => "FreeBSD",
        name => name,
    };
    let os_release = if cfg!(windows) {
        windows_release()
    } else if cfg!(target_os = "linux") {
        fs::read_to_string("/proc/sys/kernel/osrelease")
            .ok()
            .map(|s| s.trim().to_owned())
    } else {
        std::process::Command::new("uname")
            .arg("-r")
            .output()
            .ok()
            .filter(|o| o.status.success())
            .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_owned())
    };
    let shell = env::var_os("SHELL")
        .or_else(|| env::var_os("COMSPEC"))
        .unwrap_or_default();
    json!({"os":os,"os_release":os_release.unwrap_or_default(),"python":"","rust_binary_version":env!("CARGO_PKG_VERSION"),"shell":Path::new(&shell).file_name().unwrap_or_default().to_string_lossy()})
}

fn command(v: &Value) -> Option<Vec<String>> {
    v.as_array()?
        .iter()
        .map(|v| v.as_str().map(str::to_owned))
        .collect()
}
fn normalize(roster: &Value) -> Result<Vec<Value>> {
    let repos = roster["repositories"]
        .as_array()
        .context("real repo roster must contain repositories[]")?;
    if roster["record_type"] != "real-repo-roster-v2" {
        return Ok(repos.iter().filter(|e| e.is_object()).cloned().collect());
    }
    let mut all = Vec::new();
    for repo in repos.iter().filter(|v| v.is_object()) {
        let id = text(&repo["repo_id"], "");
        let scope = text(&repo["ownership_scope"], "");
        let class = text(&repo["repo_class"], "");
        ensure!(
            !id.is_empty(),
            "real-repo-roster-v2 repository requires repo_id"
        );
        ensure!(
            matches!(scope, "owned" | "external" | "third_party_sample"),
            "invalid ownership_scope for {id}: {scope}"
        );
        ensure!(
            matches!(class, "small" | "medium" | "large" | "xlarge" | "monorepo"),
            "invalid repo_class for {id}: {class}"
        );
        let suites = items(&repo["suites"]);
        ensure!(
            !suites.is_empty(),
            "real-repo-roster-v2 repository requires suites[]: {id}"
        );
        for suite in suites.iter().filter(|v| v.is_object()) {
            let sid = text(&suite["suite_id"], "");
            let kind = text(&suite["suite_kind"], "");
            ensure!(
                !sid.is_empty(),
                "real-repo-roster-v2 suite requires suite_id: {id}"
            );
            ensure!(
                matches!(
                    kind,
                    "unit"
                        | "integration"
                        | "e2e"
                        | "build"
                        | "typecheck"
                        | "lint"
                        | "security"
                        | "smoke"
                        | "package-split"
                ),
                "invalid suite_kind for {id}/{sid}: {kind}"
            );
            ensure!(
                command(&suite["command"]).is_some(),
                "real-repo-roster-v2 suite requires string command[]: {id}/{sid}"
            );
            let mut entry = repo.clone();
            merge(&mut entry, suite.clone());
            let mut vars = json!({});
            merge(&mut vars, repo["env"].clone());
            merge(&mut vars, suite["env"].clone());
            merge(
                &mut entry,
                json!({"repo_id":id,"suite_id":sid,"suite_kind":kind,"ownership_scope":scope,"repo_class":class,"path":repo["path"],"env":vars}),
            );
            all.push(entry);
        }
    }
    Ok(all)
}

pub fn run(call: &Invocation) -> Result<Value> {
    let roster_path = call.path("roster");
    let out = call.path("out");
    let roster = object(roster_path)?;
    let entries = normalize(&roster)?;
    let version = text(
        &call.values["source_version"],
        text(&roster["source_version"], "unknown"),
    );
    let roster_hash = format!("sha256:{}", digest(&roster));
    let policy_hash = stable_id(
        "policy",
        &[text(
            &roster["default_policy_ref"],
            text(&roster["policy_ref"], "default"),
        )],
    );
    let environment = fingerprint();
    let file_name = roster_path
        .file_name()
        .unwrap_or_default()
        .to_string_lossy();
    let mut reports = Vec::new();
    let mut generated = Vec::new();
    let mut history = Vec::new();
    fs::create_dir_all(out)?;
    for mut entry in entries {
        let repo = safe_id(text(&entry["repo_id"], text(&entry["name"], "repo")));
        let suite = safe_id(text(&entry["suite_id"], "default"));
        let command = command(&entry["command"]);
        let command_text = command
            .as_ref()
            .map(|argv| argv.join(" "))
            .unwrap_or_default();
        let id = stable_id(
            "real-repo-run",
            &[&repo, &suite, &command_text, &roster_hash, version],
        );
        let baseline = text(
            &entry["baseline_decision"],
            if text(&entry["ownership_scope"], "").eq_ignore_ascii_case("external") {
                ""
            } else {
                "pass"
            },
        )
        .to_owned();
        merge(
            &mut entry,
            json!({"repo_id":repo,"suite_id":suite,"run_id":id,"source_version":version,"roster_hash":roster_hash,"policy_hash":policy_hash,
            "environment_fingerprint":environment,"started_at":now(),"baseline_decision":baseline}),
        );
        let result = execution::run(&entry, roster_path, command)?;
        merge(&mut entry, result);
        entry["finished_at"] = json!(now());
        let stem = if suite == "default" {
            format!("real-repo-{repo}")
        } else {
            format!("real-repo-{repo}-{suite}")
        };
        let reference = format!("file:{file_name}#{repo}:{suite}");
        let report = rule(
            "evaluation__real_repo__build_real_repo_evaluation_report",
            vec![entry.clone(), json!(stem), json!([reference])],
        )?;
        ensure!(
            report["record_type"] == "real-repo-evaluation-report",
            "invalid real repository evaluation report"
        );
        let current = &report["current"];
        history.push(json!({"schema_version":"HATE/v1","record_type":"real-repo-run-history-entry","run_id":id,"repo_id":repo,"suite_id":suite,
            "ownership_scope":text(&entry["ownership_scope"],"owned"),"source_version":version,"roster_hash":roster_hash,"policy_hash":policy_hash,
            "environment_fingerprint":environment,"started_at":entry["started_at"],"finished_at":entry["finished_at"],"duration_ms":entry["runtime_ms"],
            "command_exit_code":entry["command_exit_code"],"status":report["overall_status"],"record_count":current["record_count"],
            "command_summary":current["command_summary"],"failure_kind":current["failure_kind"],"timeout_recorded":report["timeout_recorded"],
            "subset":report["subset"],"command_excerpt_ref":format!("{stem}.json#/current/command_excerpt"),"sourceRefs":[reference]}));
        generated.push(format!("{stem}.json"));
        reports.push(report);
    }
    let held: Vec<_> = reports
        .iter()
        .filter(|r| r["overall_status"] == "hold")
        .map(|r| &r["repo_id"])
        .collect();
    let count = reports.len();
    let manifest = json!({"schema_version":"HATE/v1","record_type":"real-repo-evaluation-run-report","report_id":"real-repo-evaluation-run","source_version":version,
        "run_id":stable_id("run",&[&roster_hash,version]),"roster_hash":roster_hash,"policy_hash":policy_hash,"environment_fingerprint":environment,
        "overall_status":if held.is_empty(){"pass"}else{"hold"},"roster_path":roster_path,"repo_count":count,"hold_count":held.len(),"generated_reports":generated,
        "history_path":"real-repo-run-history.jsonl","summary":{"passed":count-held.len(),"held":held.len(),"timeout_count":reports.iter().filter(|r|r["timeout_recorded"]==true).count(),
        "executed_record_count":reports.iter().filter_map(|r|r["current"]["record_count"].as_i64()).sum::<i64>(),"held_repos":held},"sourceRefs":[format!("file:{file_name}")]});
    let mut stream = tempfile::NamedTempFile::new_in(out)?;
    for item in history {
        writeln!(stream, "{item}")?;
    }
    for (file, report) in generated.iter().zip(&reports) {
        write_json(&out.join(file), report)?;
    }
    stream.persist(out.join("real-repo-run-history.jsonl"))?;
    write_json(&out.join("real-repo-evaluation-run-report.json"), &manifest)?;
    Ok(manifest)
}
