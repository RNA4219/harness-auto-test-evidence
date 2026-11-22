use crate::{
    cli::Invocation,
    error::CommandFailure,
    io::{digest, items, read_json, resolve, stable_ref, write_json},
};
use anyhow::{Context, Result, ensure};
use serde_json::{Value, json};
use std::{
    fs,
    path::{Component, Path, PathBuf},
};

const BUNDLE: &str = "qeg-bundle.json";
const READY: &str = "product-readiness-report.json";
const DEBT: &str = "enterprise-risk-debt-register.json";
const MANIFEST: &str = "store-manifest.json";

fn data_error(message: impl std::fmt::Display) -> anyhow::Error {
    CommandFailure {
        code: 1,
        diagnostic: format!("HATE-E-STORE: {message}"),
    }
    .into()
}

fn object(path: &Path) -> Result<Value> {
    ensure!(
        path.is_file(),
        "required store artifact not found: {}",
        path.display()
    );
    let value = read_json(path).map_err(data_error)?;
    if !value.is_object() {
        return Err(data_error(format!(
            "{} must contain a JSON object",
            path.file_name().unwrap_or_default().to_string_lossy()
        )));
    }
    Ok(value)
}

fn run_dir(root: &Path, id: &str) -> Result<PathBuf> {
    let mut components = Path::new(id).components();
    ensure!(
        matches!(components.next(), Some(Component::Normal(_)))
            && components.next().is_none()
            && !id.contains(['/', '\\', ':']),
        "invalid run id: {id}"
    );
    let runs = root.join("runs");
    let dest = runs.join(id);
    ensure!(
        resolve(&dest)?.starts_with(resolve(&runs)?),
        "run id points outside the store"
    );
    Ok(dest)
}

pub fn run(call: &Invocation) -> Result<Value> {
    let store = call.path("store");
    let index = store.join("history-index.json");
    if call.command == "store ingest" {
        return ingest(call, &index);
    }
    let lock = match fs::File::open(store.join(".store.lock")) {
        Ok(lock) => Some(lock),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => None,
        Err(error) => return Err(error.into()),
    };
    if let Some(lock) = &lock {
        lock.lock_shared()?;
    }
    ensure!(
        index.is_file(),
        "required store artifact not found: {}",
        index.display()
    );
    let history = object(&index)?;
    if call.command == "store history" || call.values.get("resource") == Some(&json!("history")) {
        return Ok(history);
    }
    let id = call.values["run_id"]
        .as_str()
        .filter(|s| !s.is_empty())
        .or_else(|| history["summary"]["latest_run_id"].as_str())
        .filter(|s| !s.is_empty())
        .context("no run id supplied and history has no latest run")?;
    let resource = call.values["resource"]
        .as_str()
        .context("missing resource")?;
    let name = match resource {
        "run" | "manifest" => MANIFEST,
        "bundle" => BUNDLE,
        "risk-debt" => DEBT,
        "product-readiness" => READY,
        _ => anyhow::bail!("unknown resource: {resource}"),
    };
    let path = run_dir(store, id)?.join(name);
    ensure!(
        path.is_file(),
        "required store artifact not found: {}",
        path.display()
    );
    Ok(
        json!({"schema_version":"HATE/v1","record_type":"local_store_query","resource":resource,"run_id":id,
        "data":object(&path)?,"source_refs":[stable_ref(&path,false)?],"stale_cache":false,
        "canonical_source_preserved":true,"publish_gate_override":false,"release_gate_override":false}),
    )
}

fn ingest(call: &Invocation, index: &Path) -> Result<Value> {
    let store = call.path("store");
    let bundle_path = call.path("bundle");
    let readiness_dir = call.path("readiness");
    ensure!(
        bundle_path.is_file(),
        "QEG bundle not found: {}",
        bundle_path.display()
    );
    ensure!(
        readiness_dir.is_dir(),
        "product readiness directory not found: {}",
        readiness_dir.display()
    );
    let ready_path = readiness_dir.join(READY);
    let debt_path = readiness_dir.join(DEBT);
    let bundle = object(bundle_path)?;
    let ready = object(&ready_path)?;
    let debt = object(&debt_path)?;
    let id_value = [&bundle["metadata"]["runId"], &ready["run_id"]]
        .into_iter()
        .find(|v| crate::io::is_truthy(v))
        .ok_or_else(|| data_error("cannot ingest store without run id"))?;
    let id = crate::io::py_string(id_value);
    let dir = run_dir(store, &id)?;
    let artifacts = [
        (BUNDLE, "qeg_bundle", bundle_path, &bundle),
        (READY, "product_readiness", &ready_path, &ready),
        (DEBT, "risk_debt", &debt_path, &debt),
    ];
    let mut descriptors = Vec::new();
    let mut refs = Vec::new();
    for (name, kind, path, data) in artifacts {
        let source = stable_ref(path, true)?;
        descriptors.push(json!({"artifact_ref":name,"kind":kind,"hash":format!("sha256:{}",digest(data)),"source_ref":source}));
        refs.push(source);
    }
    let version = call.values["source_version"]
        .as_str()
        .filter(|s| !s.is_empty())
        .unwrap_or(env!("CARGO_PKG_VERSION"));
    let status = ready["summary"]
        .get("overall_status")
        .cloned()
        .unwrap_or(json!(""));
    let open = debt["summary"]
        .get("open_count")
        .cloned()
        .unwrap_or(json!(0));
    let manifest = json!({"schema_version":"HATE/v1","record_type":"local_store_manifest","run_id":id,
        "source_tool":"harness-auto-test-evidence","source_version":version,"artifacts":descriptors,
        "summary":{"product_status":status,"risk_debt_open_count":open,"bundle_node_count":items(&bundle["nodes"]).len(),
        "bundle_edge_count":items(&bundle["edges"]).len()},"boundaries":{"canonical_source_preserved":true,"stale_cache":false,
        "publish_gate_override":false,"release_gate_override":false}});
    fs::create_dir_all(store)?;
    let lock = fs::File::options()
        .create(true)
        .truncate(false)
        .read(true)
        .write(true)
        .open(store.join(".store.lock"))?;
    lock.lock()?;
    let mut history = if index.try_exists()? {
        object(index)?
    } else {
        json!({"schema_version":"HATE/v1","record_type":"local_store_history_index","publish_gate_override":false,"release_gate_override":false})
    };
    let mut runs: Vec<_> = items(&history["runs"])
        .iter()
        .filter(|v| v["run_id"] != id)
        .cloned()
        .collect();
    runs.push(json!({"run_id":id,"manifest_ref":format!("runs/{id}/{MANIFEST}"),"product_status":status,"risk_debt_open_count":open,
        "artifact_count":artifacts.len(),"source_refs":refs}));
    runs.sort_by(|a, b| a["run_id"].as_str().cmp(&b["run_id"].as_str()));
    let count = runs.len();
    history["runs"] = json!(runs);
    history["publish_gate_override"] = json!(false);
    history["release_gate_override"] = json!(false);
    history["summary"] = json!({"run_count":count,"latest_run_id":id,"resources":["run","bundle","risk-debt","product-readiness","manifest","history"]});
    fs::create_dir_all(&dir)?;
    let mut updates: Vec<_> = artifacts
        .iter()
        .map(|(name, _, _, data)| (dir.join(name), *data))
        .collect();
    updates.push((dir.join(MANIFEST), &manifest));
    updates.push((index.to_owned(), &history));
    publish(store, &updates)?;
    let mut generated = vec!["history-index.json".to_owned()];
    generated.extend([BUNDLE, READY, DEBT, MANIFEST].map(|name| format!("runs/{id}/{name}")));
    Ok(
        json!({"store_status":"success","exit_code":0,"run_id":id,"store_dir":stable_ref(store,false)?,"history_count":count,
        "generated":generated,"publish_gate_override":false,"release_gate_override":false}),
    )
}

fn publish(store: &Path, updates: &[(PathBuf, &Value)]) -> Result<()> {
    let stage = tempfile::Builder::new()
        .prefix(".hate-store-")
        .tempdir_in(store)?;
    let mut saved = Vec::with_capacity(updates.len());
    for (i, (target, data)) in updates.iter().enumerate() {
        let backup = stage.path().join(format!("backup-{i}"));
        if target.try_exists()? {
            ensure!(
                target.is_file(),
                "store artifact is not a file: {}",
                target.display()
            );
            fs::copy(target, &backup)?;
        }
        saved.push(backup);
        write_json(&stage.path().join(i.to_string()), data)?;
    }
    for (i, (target, _)) in updates.iter().enumerate() {
        if let Err(error) = fs::rename(stage.path().join(i.to_string()), target) {
            for j in (0..i).rev() {
                let previous = if saved[j].is_file() {
                    fs::rename(&saved[j], &updates[j].0)
                } else {
                    fs::remove_file(&updates[j].0)
                };
                if let Err(recovery_error) = previous {
                    anyhow::bail!(
                        "store publish failed: {error}; restoring {} failed: {recovery_error}. Backups: {}",
                        updates[j].0.display(),
                        stage.keep().display()
                    );
                }
            }
            return Err(error.into());
        }
    }
    Ok(())
}
