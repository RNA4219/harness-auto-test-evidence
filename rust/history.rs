use crate::{
    cli::Invocation,
    io::{file_digest, write_json},
};
use anyhow::{Context, Result, ensure};
use chrono::{SecondsFormat, Utc};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    io::{BufRead, BufReader, Write},
    path::Path,
};

const VERSION: &str = "real-repo-history-store/v1";

fn entries(path: &Path, source: bool) -> Result<Vec<Value>> {
    let mut entries = Vec::new();
    for (i, line) in BufReader::new(fs::File::open(path)?).lines().enumerate() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        let v: Value = serde_json::from_str(&line).with_context(|| {
            format!(
                "invalid {} JSONL at line {}",
                if source { "history" } else { "store" },
                i + 1
            )
        })?;
        ensure!(
            !source || v["record_type"] == "real-repo-run-history-entry",
            "invalid history entry at line {}",
            i + 1
        );
        if v.is_object() {
            entries.push(v);
        }
    }
    Ok(entries)
}

fn timestamp() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Secs, true)
}

pub fn ingest(call: &Invocation) -> Result<Value> {
    let source = call.path("history");
    ensure!(
        source.is_file(),
        "history file not found: {}",
        source.display()
    );
    let incoming = entries(source, true)?;
    let total = incoming.len();
    let hash = format!("sha256:{}", hex::encode(file_digest(source)?));
    let store = call.path("store");
    fs::create_dir_all(store)?;
    let path = store.join("run_history.jsonl");
    let lock = fs::File::options()
        .create(true)
        .truncate(false)
        .read(true)
        .write(true)
        .open(store.join(".history.lock"))?;
    lock.lock()?;
    let mut stored = if path.try_exists()? {
        entries(&path, false)?
    } else {
        Vec::new()
    };
    let seq = stored
        .iter()
        .filter_map(|v| {
            v["store_sequence"]
                .as_i64()
                .or_else(|| v["store_sequence"].as_str()?.parse().ok())
        })
        .max()
        .unwrap_or(0);
    let now = timestamp();
    let mut stage = tempfile::NamedTempFile::new_in(store)?;
    if path.exists() {
        std::io::copy(&mut fs::File::open(&path)?, &mut stage)?;
    }
    for (i, mut v) in incoming.into_iter().enumerate() {
        v["store_version"] = json!(VERSION);
        v["store_sequence"] = json!(seq + i as i64 + 1);
        v["source_history_hash"] = json!(hash);
        v["ingested_at"] = json!(now);
        writeln!(stage, "{v}")?;
        stored.push(v);
    }
    stage.persist(&path)?;
    let values = |field: &str| -> BTreeSet<&str> {
        stored
            .iter()
            .filter_map(|v| v[field].as_str().filter(|s| !s.is_empty()))
            .collect()
    };
    let repos = values("repo_id");
    let statuses = values("status");
    let index = store.join("history-index.json");
    write_json(
        &index,
        &json!({"schema_version":"HATE/v1","record_type":"real-repo-history-index","store_version":VERSION,
        "updated_at":timestamp(),"summary":{"stored_count":stored.len(),"repo_count":repos.len(),"status_count":statuses.len(),
        "latest_started_at":values("started_at").last().copied().unwrap_or("")},"indexes":["idx_run_repo_time","idx_run_source_version","idx_suite_status"],
        "repos":repos,"statuses":statuses}),
    )?;
    Ok(
        json!({"schema_version":"HATE/v1","record_type":"real-repo-history-ingest-report","report_id":"real-repo-history-ingest",
    "store_version":VERSION,"history_path":source,"store_path":path,"source_history_hash":hash,"ingested_count":total,
    "stored_count":stored.len(),"repo_count":repos.len(),"sourceRefs":[source,path,index]}),
    )
}

fn public(entry: &Value) -> Value {
    let mut out = json!({});
    for key in [
        "run_id",
        "repo_id",
        "suite_id",
        "ownership_scope",
        "source_version",
        "roster_hash",
        "policy_hash",
        "started_at",
        "finished_at",
        "status",
        "failure_kind",
    ] {
        out[key] = entry
            .get(key)
            .cloned()
            .unwrap_or_else(|| json!(if key == "suite_id" { "default" } else { "" }));
    }
    for key in ["record_count", "duration_ms", "store_sequence"] {
        out[key] = entry[key].clone();
    }
    out["timeout_recorded"] = json!(crate::io::is_truthy(&entry["timeout_recorded"]));
    out["sourceRefs"] = entry
        .get("sourceRefs")
        .filter(|v| !v.is_null())
        .cloned()
        .unwrap_or(json!([]));
    out
}

pub fn query(call: &Invocation) -> Result<Value> {
    let path = call.path("store").join("run_history.jsonl");
    ensure!(
        path.is_file(),
        "history store not found: {}",
        path.display()
    );
    let limit = call.integer("limit")?;
    ensure!(limit > 0.into(), "limit must be greater than zero");
    let filters: BTreeMap<_, _> = [
        "repo_id",
        "suite_id",
        "source_version",
        "status",
        "since",
        "until",
    ]
    .into_iter()
    .filter_map(|key| Some((key, call.values[key].as_str()?)))
    .collect();
    let mut selected: Vec<_> = entries(&path, false)?
        .iter()
        .filter(|row| {
            filters.iter().all(|(&key, &expected)| match key {
                "since" => row["started_at"].as_str().unwrap_or("") >= expected,
                "until" => row["started_at"].as_str().unwrap_or("") <= expected,
                _ => row.get(key).map(crate::io::py_string).unwrap_or_default() == expected,
            })
        })
        .map(public)
        .collect();
    selected.sort_by(|a, b| {
        ["started_at", "run_id", "suite_id"]
            .map(|k| a[k].as_str())
            .cmp(&["started_at", "run_id", "suite_id"].map(|k| b[k].as_str()))
    });
    let count = selected.len();
    selected.truncate(usize::try_from(limit).unwrap_or(usize::MAX));
    Ok(
        json!({"schema_version":"HATE/v1","record_type":"real-repo-history-query-report","report_id":"real-repo-history-query",
        "store_version":VERSION,"store_path":path,"filters":filters,"matched_count":count,"returned_count":selected.len(),"entries":selected,"sourceRefs":[path]}),
    )
}
