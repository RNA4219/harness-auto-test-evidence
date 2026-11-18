use anyhow::{Context, Result};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    fs::{self, File},
    io::{self, Write},
    path::{Path, PathBuf},
};

pub fn read_json(path: &Path) -> Result<Value> {
    serde_json::from_reader(
        File::open(path).with_context(|| format!("cannot open {}", path.display()))?,
    )
    .with_context(|| format!("cannot read JSON {}", path.display()))
}

pub fn parent(path: &Path) -> &Path {
    path.parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."))
}

pub fn write_json(path: &Path, value: &Value) -> Result<()> {
    fs::create_dir_all(parent(path))?;
    let mut file = tempfile::Builder::new()
        .prefix(".hate-bridge-")
        .suffix(".tmp")
        .tempfile_in(parent(path))?;
    serde_json::to_writer_pretty(&mut file, value)?;
    writeln!(&mut file)?;
    file.persist(path)?;
    Ok(())
}

pub fn file_digest(path: &Path) -> Result<[u8; 32]> {
    let mut hash = Sha256::new();
    io::copy(&mut File::open(path)?, &mut hash)?;
    Ok(hash.finalize().into())
}

// 入力パスと未作成の出力パスの両方を、実在する親までリンク解決する。
pub fn resolve(path: &Path) -> Result<PathBuf> {
    let absolute = std::path::absolute(path)?;
    match dunce::canonicalize(&absolute) {
        Ok(p) => Ok(p),
        Err(e) if e.kind() == io::ErrorKind::NotFound => {
            if let Some(std::path::Component::ParentDir) = absolute.components().next_back() {
                return Ok(parent(&resolve(parent(&absolute))?).to_owned());
            }
            let name = absolute.file_name().context("path has no file name")?;
            Ok(resolve(parent(&absolute))?.join(name))
        }
        Err(e) => Err(e.into()),
    }
}

pub fn validate(value: &Value, schema_text: &str, name: &str) -> Result<()> {
    let schema: Value = serde_json::from_str(schema_text)?;
    let validator = jsonschema::draft202012::options()
        .should_validate_formats(true)
        .build(&schema)?;
    if let Err(e) = validator.validate(value) {
        anyhow::bail!("{name} schema validation failed: {e}");
    }
    Ok(())
}

pub fn object(path: &Path) -> Result<Value> {
    let v = read_json(path)?;
    anyhow::ensure!(
        v.is_object(),
        "{} must contain a JSON object",
        path.display()
    );
    Ok(v)
}

pub fn stable_ref(path: &Path, prefer_fixture: bool) -> Result<String> {
    let path = resolve(path)?;
    let normalized = path.to_string_lossy().replace('\\', "/");
    if prefer_fixture && let Some((_, tail)) = normalized.split_once("/fixtures/golden/") {
        return Ok(format!("fixture:/{tail}"));
    }
    if let Ok(rel) = path.strip_prefix(resolve(Path::new("."))?) {
        let rel = rel.to_string_lossy().replace('\\', "/");
        return Ok(format!(
            "workspace:/{}",
            if rel.is_empty() { "." } else { &rel }
        ));
    }
    Ok(format!(
        "path:/{}",
        path.file_name().unwrap_or_default().to_string_lossy()
    ))
}

pub fn digest(value: &Value) -> String {
    crate::p0a::canonical_digest(value)
}

pub fn items(value: &Value) -> &[Value] {
    value.as_array().map(Vec::as_slice).unwrap_or_default()
}

pub fn is_truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(flag) => *flag,
        Value::Number(n) => n.as_f64() != Some(0.0),
        Value::String(text) => !text.is_empty(),
        Value::Array(list) => !list.is_empty(),
        Value::Object(map) => !map.is_empty(),
    }
}

pub fn py_string(value: &Value) -> String {
    match value {
        Value::String(s) => s.to_owned(),
        Value::Null => "None".to_owned(),
        Value::Bool(true) => "True".to_owned(),
        Value::Bool(false) => "False".to_owned(),
        other => other.to_string(),
    }
}

pub fn ascii_digest(value: &Value) -> String {
    use std::fmt::Write;
    let mut ascii = String::new();
    for c in crate::p0a::canonical_json(value).chars() {
        if c.is_ascii() && c != '\x7f' {
            ascii.push(c);
        } else {
            for unit in c.encode_utf16(&mut [0; 2]) {
                write!(ascii, "\\u{unit:04x}").expect("write into string");
            }
        }
    }
    hex::encode(Sha256::digest(ascii.as_bytes()))
}
