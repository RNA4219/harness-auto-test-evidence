use super::{assess::truth, *};
use crate::{downstream, process};
fn sandbox(input: &Value, id: &str) -> Result<Value> {
    downstream::rule(
        "plugins__sandbox__build_plugin_sandbox_report",
        vec![input.clone(), json!(id)],
    )
}
fn denials(
    manifest: &Value,
    command: &Value,
    consent: bool,
    checked: &Value,
) -> BTreeSet<&'static str> {
    let plugin = &manifest["plugin"];
    let limits = &manifest["limits"];
    let mut reasons = BTreeSet::new();
    for (deny, reason) in [
        (
            plugin["execution_mode"] != "subprocess_local",
            "plugin_execution_mode_not_runnable",
        ),
        (
            matches!(
                field(manifest, "profile", "default"),
                "release" | "regulated"
            ) && plugin["execution_mode"] == "subprocess_local",
            "plugin_local_exec_denied_in_strict_profile",
        ),
        (!consent, "plugin_local_exec_consent_required"),
        (
            !truth(&plugin["signed"]),
            "plugin_signature_evidence_missing",
        ),
        (!truth(&plugin["trusted"]), "plugin_trust_evidence_missing"),
        (truth(&plugin["revoked"]), "plugin_revoked"),
        (
            field(plugin, "compatibility_status", "compatible") != "compatible",
            "plugin_api_migration_required",
        ),
        (command.is_null(), "plugin_command_missing"),
        (
            ["timeout_ms", "max_output_bytes", "max_input_bytes"]
                .iter()
                .any(|k| limits[*k].as_u64().unwrap_or(0) == 0),
            "plugin_resource_limit_missing",
        ),
        (
            checked["mode_decision"]["allowed"] == false,
            "plugin_trust_denied",
        ),
    ] {
        if deny {
            reasons.insert(reason);
        }
    }
    if let Some(env) = manifest["execution"]["env"].as_object()
        && env
            .keys()
            .any(|k| !items(&limits["env_allowlist"]).iter().any(|v| v == k))
    {
        reasons.insert("plugin_environment_not_allowlisted");
    }
    reasons
}
pub(super) fn run(call: &Invocation) -> Result<Value> {
    let path = call.path("manifest");
    let mut input = object(path)?;
    let plugin = input.get("plugin").cloned().unwrap_or(json!({}));
    let id = field(&plugin, "plugin_id", "platform-plugin-run");
    let mut exec = input
        .get("execution")
        .filter(|v| !v.is_null())
        .cloned()
        .unwrap_or(json!({}));
    let command = exec
        .as_object_mut()
        .context("execution must be an object")?
        .remove("command")
        .unwrap_or(Value::Null);
    ensure!(
        command.is_null()
            || command
                .as_array()
                .is_some_and(|a| !a.is_empty()
                    && a.iter().all(|x| x.as_str().is_some_and(|s| !s.is_empty()))),
        "plugin execution.command must be a non-empty string list"
    );
    let consent = call.values["allow_local_exec"] == true;
    input["execution"] = exec.clone();
    let mut checked = sandbox(&input, id)?;
    let reasons = denials(&input, &command, consent, &checked);
    let limits = input.get("limits").cloned().unwrap_or(json!({}));
    let mut process_value = Value::Null;
    if reasons.is_empty() {
        let env_keys = [
            "COMSPEC",
            "LANG",
            "LC_ALL",
            "PATH",
            "PATHEXT",
            "SYSTEMROOT",
            "TEMP",
            "TMP",
        ];
        let mut env: BTreeMap<_, _> = std::env::vars()
            .filter(|(k, _)| env_keys.contains(&k.to_uppercase().as_str()))
            .collect();
        if let Some(overrides) = exec["env"].as_object() {
            for (k, v) in overrides {
                env.insert(k.clone(), super::operating::text(v));
            }
        }
        let args: Vec<_> = items(&command)
            .iter()
            .map(|v| v.as_str().unwrap().to_owned())
            .collect();
        let dir = tempfile::Builder::new().prefix("hate-plugin-").tempdir()?;
        let result = process::execute(
            &args,
            dir.path(),
            &env,
            limits["timeout_ms"].as_u64().unwrap(),
            limits["max_output_bytes"].as_u64(),
        )?;
        let output = serde_json::from_str::<Value>(&result.stdout)
            .ok()
            .filter(|v| v.is_object())
            .unwrap_or(json!({}));
        process_value = json!({"exit_code":result.exit_code,"output_bytes":result.output_bytes,"timed_out":result.timed_out,"output_limit_exceeded":result.over_limit,"cleanup":result.cleanup});
        super::operating::merge(
            &mut exec,
            json!({"exit_code":result.exit_code,"output":output,"output_bytes":result.output_bytes,"timed_out":result.timed_out,
           "crashed":result.exit_code!=0&&!result.timed_out,"output_limit_exceeded":result.over_limit,"timeout_cleanup":result.cleanup}),
        );
        input["execution"] = exec;
        checked = sandbox(&input, id)?;
    }
    let mut findings = items(&checked["findings"]).to_vec();
    for code in &reasons {
        findings.push(json!({"code":code,"severity":"high","readiness_effect":"hold","message":"Plugin process was not started because execution authorization failed.","sourceRefs":[]}));
    }
    let status = if checked["overall_status"] == "blocked" {
        "blocked"
    } else if findings.is_empty() {
        "pass"
    } else {
        "hold"
    };
    let mut unenforced = vec!["filesystem_isolation", "network_isolation"];
    if truth(&limits["max_memory_mb"]) {
        unenforced.push("memory_limit");
    }
    let mut sources: BTreeSet<_> = items(&checked["sourceRefs"])
        .iter()
        .filter_map(Value::as_str)
        .map(str::to_owned)
        .collect();
    sources.insert(path.to_string_lossy().into_owned());
    Ok(
        json!({"schema_version":"HATE/v1","record_type":"platform-plugin-run-report","overall_status":status,"readiness_effect":if status=="pass"{"none"}else{status},
      "plugin_id":checked["plugin_id"],"detector_id":checked["detector_id"],"execution_attempted":!process_value.is_null(),"execution_authorized":reasons.is_empty(),
      "authorization_source":if consent{"cli_allow_local_exec"}else{"default_deny"},"denial_reasons":reasons,
      "enforced_controls":["explicit_local_execution_consent","minimal_environment","output_byte_limit","process_tree_cleanup","temporary_working_directory","timeout"],
      "unenforced_controls":unenforced,"signature_verification":{"mode":"external_evidence","cryptographically_verified_by_hate":false},
      "process_result":process_value,"sandbox_report":checked,"findings":findings,"sourceRefs":sources}),
    )
}
