use crate::{
    cli::{Invocation, Route},
    io::{file_digest, parent, resolve, validate, write_json},
};
use anyhow::{Context, Result, bail, ensure};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    env, fs,
    path::{Path, PathBuf},
};
use walkdir::WalkDir;

pub const REQUEST_SCHEMA: &str =
    include_str!("../schemas/HATE-bridge/v1/bridge-request.schema.json");
pub const RESULT_SCHEMA: &str = include_str!("../schemas/HATE-bridge/v1/bridge-result.schema.json");

struct Exclusion {
    path: PathBuf,
    kind: &'static str,
}

impl Exclusion {
    fn matches(&self, path: &Path) -> bool {
        match self.kind {
            "directory" => path.starts_with(&self.path),
            "file" => path == self.path,
            _ => {
                path.parent() == Some(&self.path)
                    && path
                        .file_name()
                        .and_then(|s| s.to_str())
                        .is_some_and(|n| n.starts_with(".hate-bridge-") && n.ends_with(".tmp"))
            }
        }
    }
}

fn relative(root: &Path, child: &Path) -> Result<String> {
    let rel = child
        .strip_prefix(root)?
        .to_str()
        .context("non-UTF-8 input path")?;
    Ok(if rel.is_empty() {
        ".".into()
    } else {
        rel.replace(std::path::MAIN_SEPARATOR, "/")
    })
}

fn reference(name: &str, path: &Path, excluded: &[Exclusion]) -> Result<Value> {
    if path.is_file() {
        return Ok(
            json!({"argument":name,"path":path,"kind":"file","sha256":hex::encode(file_digest(path)?)}),
        );
    }
    ensure!(
        path.is_dir(),
        "bridge input is not a file or directory: {name}"
    );
    let applicable: Vec<_> = excluded
        .iter()
        .filter(|e| e.path.starts_with(path))
        .collect();
    let mut files = Vec::new();
    for entry in WalkDir::new(path)
        .into_iter()
        .filter_entry(|e| !applicable.iter().any(|x| x.matches(e.path())))
    {
        let child = entry?.into_path();
        if child.is_file() {
            files.push(child);
        }
    }
    // pathlib は各パス要素を比較し、Windows では大文字小文字を区別しない。
    files.sort_by_cached_key(|p| {
        p.components()
            .map(|c| {
                let s = c.as_os_str().to_string_lossy();
                if cfg!(windows) {
                    s.to_lowercase()
                } else {
                    s.into_owned()
                }
            })
            .collect::<Vec<_>>()
    });
    let mut hash = Sha256::new();
    for file in files {
        hash.update(relative(path, &file)?.as_bytes());
        hash.update([0]);
        hash.update(file_digest(&file)?);
    }
    let mut result = json!({"argument":name,"path":path,"kind":"directory","sha256":hex::encode(hash.finalize())});
    if !applicable.is_empty() {
        let items: Result<Vec<_>> = applicable
            .iter()
            .map(|e| Ok(json!({"path":relative(path,&e.path)?,"kind":e.kind})))
            .collect();
        result["excluded_paths"] = json!(items?);
    }
    Ok(result)
}

pub fn handoff(call: &Invocation, route: &Route) -> Result<Value> {
    let base = match call.optional_path("out") {
        Some(path) if route.directory_output => Some(path),
        Some(path) => Some(parent(&path).to_owned()),
        None => call
            .optional_path("manifest_out")
            .map(|p| parent(&p).to_owned()),
    };
    let root = resolve(base.as_deref().unwrap_or(Path::new(".hate/bridge")))?;
    let excluded = if base.is_some() {
        vec![
            Exclusion {
                path: root.join("bridge-request.json"),
                kind: "file",
            },
            Exclusion {
                path: root.clone(),
                kind: "temporary-files",
            },
        ]
    } else {
        vec![Exclusion {
            path: root.clone(),
            kind: "directory",
        }]
    };
    let mut refs = Vec::new();
    let mut paths = BTreeMap::new();
    let mut sources = Vec::new();
    for (name, role) in &route.paths {
        let Some(input) = call.optional_path(name) else {
            continue;
        };
        let path = resolve(&input)?;
        let exists = path.try_exists()?;
        ensure!(
            role != "input" || exists,
            "bridge input not found: {name}: {}",
            path.display()
        );
        ensure!(
            !excluded.iter().any(|e| e.matches(&path)),
            "bridge input overlaps generated handoff artifacts: {name}"
        );
        ensure!(
            exists || !root.starts_with(&path),
            "handoff output would create missing path argument: {name}"
        );
        ensure!(
            role != "destination" || !exists || path.is_dir(),
            "bridge destination must be a directory: {name}: {}",
            path.display()
        );
        paths.insert(name, json!({"path":path,"role":role,"exists":exists}));
        if exists {
            refs.push(reference(name, &path, &excluded)?);
            let uri = file_uri(&path)?;
            if !sources.contains(&uri) {
                sources.push(uri);
            }
        }
    }
    let options: BTreeMap<_, _> = call
        .values
        .iter()
        .filter(|(name, _)| {
            !matches!(name.as_str(), "out" | "manifest_out" | "bridge_provider")
                && !route.paths.contains_key(*name)
        })
        .collect();
    let types = [format!("legacy:{}", call.command.replace(' ', "-"))];
    let identity = json!({"command":call.command,"owner":route.owner,"canonical_contract":route.contract,
        "command_options":options,"input_refs":refs,"path_arguments":paths,"expected_output_types":types});
    let hash = hex::encode(Sha256::digest(serde_json::to_vec(&identity)?));
    let id = format!("hate-bridge-{}", &hash[..24]);
    let request = json!({"schema_version":"HATE-bridge/v1","record_type":"bridge_request","bridge_id":id,
        "original_command":call.command,"owner":route.owner,"canonical_contract":route.contract,
        "command_options":options,"status":"handoff_required","input_refs":refs,"path_arguments":paths,
        "expected_output_types":types,"sourceRefs":sources});
    validate(&request, REQUEST_SCHEMA, "bridge-request")?;
    let dir = match base {
        Some(base) => base,
        None => env::current_dir()?.join(".hate").join("bridge").join(id),
    };
    fs::create_dir_all(&dir)?;
    let destination = if dir == Path::new(".") {
        PathBuf::from("bridge-request.json")
    } else {
        dir.join("bridge-request.json")
    };
    write_json(&destination, &request)?;
    Ok(
        json!({"status":"handoff_required","bridge_provider":"handoff","bridge_request":destination,"canonical_owner":route.owner}),
    )
}

// pathlib.as_uri quotes all non-unreserved filename bytes except path separators.
fn file_uri(path: &Path) -> Result<String> {
    let url = url::Url::from_file_path(path)
        .map_err(|_| anyhow::anyhow!("invalid file URI: {}", path.display()))?;
    let raw = path
        .to_str()
        .context("non-UTF-8 input path")?
        .replace(std::path::MAIN_SEPARATOR, "/");
    let (prefix, suffix) = if cfg!(windows) && raw.as_bytes().get(1) == Some(&b':') {
        (format!("file:///{}", &raw[..2]), &raw[2..])
    } else if cfg!(windows) && raw.starts_with("//") {
        ("file:".into(), raw.as_str())
    } else if raw.starts_with('/') {
        ("file://".into(), raw.as_str())
    } else {
        return Ok(url.to_string());
    };
    let mut uri = prefix;
    for byte in suffix.bytes() {
        if byte.is_ascii_alphanumeric() || b"-._~/".contains(&byte) {
            uri.push(byte as char);
        } else {
            use std::fmt::Write;
            write!(uri, "%{byte:02X}")?;
        }
    }
    Ok(uri)
}

pub fn provider(call: &Invocation) -> Result<String> {
    let selected = call.values["bridge_provider"]
        .as_str()
        .map(str::to_owned)
        .or_else(|| {
            env::var("HATE_BRIDGE_PROVIDER")
                .ok()
                .filter(|s| !s.is_empty())
        })
        .unwrap_or_else(|| "compat-v0.2".to_owned());
    if !matches!(selected.as_str(), "compat-v0.2" | "handoff") {
        bail!("unknown bridge provider: {selected}");
    }
    Ok(selected)
}
