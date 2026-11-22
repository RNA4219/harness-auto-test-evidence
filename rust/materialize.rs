use crate::{
    bridge::{REQUEST_SCHEMA, RESULT_SCHEMA},
    cli::Invocation,
    io::{file_digest, parent, read_json, resolve, validate, write_json},
};
use anyhow::{Context, Result, bail, ensure};
use serde_json::{Value, json};
use std::{collections::HashSet, fs};
use unicode_casefold::UnicodeCaseFold;

pub fn run(call: &Invocation) -> Result<Value> {
    let request = read_json(call.path("request"))?;
    let result_path = resolve(call.path("result"))?;
    let result = read_json(&result_path)?;
    validate(&request, REQUEST_SCHEMA, "bridge-request")?;
    validate(&result, RESULT_SCHEMA, "bridge-result")?;
    for name in ["bridge_id", "owner", "sourceRefs"] {
        ensure!(
            result[name] == request[name],
            "request/result {name} mismatch"
        );
    }
    ensure!(
        result["status"] == "completed",
        "only completed bridge results can be materialized"
    );
    let outputs = result["output_refs"]
        .as_array()
        .context("missing output_refs")?;
    for kind in request["expected_output_types"]
        .as_array()
        .context("missing expected types")?
    {
        ensure!(
            outputs.iter().any(|v| v["record_type"] == *kind),
            "bridge result is missing expected output types: {kind}"
        );
    }
    let out = call.path("out");
    ensure!(
        !out.try_exists()? || out.is_dir(),
        "output path is not a directory: {}",
        out.display()
    );
    let mut seen = HashSet::new();
    let mut sources = Vec::new();
    for item in outputs {
        let name = item["target_name"]
            .as_str()
            .context("invalid target name")?;
        ensure!(
            !name.is_empty()
                && !name.ends_with(['.', ' '])
                && !name.contains(['<', '>', ':', '"', '/', '\\', '|', '?', '*', '\0']),
            "unsafe target_name: {name}"
        );
        ensure!(
            seen.insert(name.case_fold().collect::<String>()),
            "duplicate target_name: {name}"
        );
        ensure!(
            !out.join(name).is_dir(),
            "target conflicts with a directory: {name}"
        );
        let source =
            parent(&result_path).join(item["path"].as_str().context("invalid source path")?);
        ensure!(
            source.is_file(),
            "bridge output does not exist: {}",
            source.display()
        );
        sources.push((source, name, &item["sha256"]));
    }
    fs::create_dir_all(parent(out))?;
    let stage = tempfile::Builder::new()
        .prefix(".hate-materialize-")
        .tempdir_in(parent(out))?;
    let files = stage.path().join("files");
    let backups = stage.path().join("backups");
    fs::create_dir(&files)?;
    fs::create_dir(&backups)?;
    let mut names = Vec::new();
    for (source, name, hash) in sources {
        let dest = files.join(name);
        fs::copy(&source, &dest)?;
        ensure!(
            *hash == hex::encode(file_digest(&dest)?),
            "bridge output hash mismatch: {}",
            source.display()
        );
        names.push(name);
    }
    let existed = out.try_exists()?;
    let targets: Vec<_> = names
        .iter()
        .map(|name| json!({"name":name,"existed":fs::symlink_metadata(out.join(name)).is_ok()}))
        .collect();
    write_json(
        &stage.path().join("recovery.json"),
        &json!({"out_dir":resolve(out)?,"directory_existed":existed,"targets":targets}),
    )?;
    let mut saved = Vec::new();
    let mut published = Vec::new();
    if !existed {
        fs::create_dir(out)?;
    }
    let publish = (|| -> Result<()> {
        for &name in &names {
            let target = out.join(name);
            ensure!(
                !target.is_dir(),
                "target conflicts with a directory: {name}"
            );
            if fs::symlink_metadata(&target).is_ok() {
                fs::rename(&target, backups.join(name))?;
                saved.push(name);
            }
            fs::rename(files.join(name), &target)?;
            published.push(name);
        }
        Ok(())
    })();
    if let Err(error) = publish {
        let mut failures = Vec::new();
        for name in names.iter().rev() {
            let res = if saved.contains(name) {
                fs::rename(backups.join(name), out.join(name))
            } else if published.contains(name) {
                fs::remove_file(out.join(name))
            } else {
                Ok(())
            };
            if let Err(e) = res {
                failures.push(format!("{name}: {e}"));
            }
        }
        if !existed
            && failures.is_empty()
            && let Err(e) = fs::remove_dir(out)
        {
            failures.push(e.to_string());
        }
        if !failures.is_empty() {
            bail!(
                "bridge publish failed ({error}); rollback incomplete: {}; recovery files retained at {}",
                failures.join("; "),
                stage.keep().display()
            );
        }
        bail!("bridge publish failed; previous outputs restored: {error}");
    }
    Ok(
        json!({"status":"materialized","bridge_id":request["bridge_id"],"canonical_owner":request["owner"],"generated":names,"out_dir":out}),
    )
}
