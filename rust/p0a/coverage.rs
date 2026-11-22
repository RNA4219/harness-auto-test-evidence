use super::{Run, numbers::Document, slug};
use anyhow::{Context, Result, ensure};
use roxmltree::Node;
use serde_json::{Value, json};
use std::{collections::HashSet, fs, path::Path};

pub fn parse(run: &Run, path: &Path, format: &str, tests: &[Value]) -> Result<Vec<Value>> {
    let contexts = json!(
        tests
            .iter()
            .map(|v| json!({"test_id":v["payload"]["canonical_test_id"]}))
            .collect::<Vec<_>>()
    );
    if format == "coverage.py" {
        return coverage_py(run, path);
    }
    let text = fs::read_to_string(path)?;
    if format == "lcov" {
        return lcov(run, &text, &contexts);
    }
    let xml = roxmltree::Document::parse_with_options(
        &text,
        roxmltree::ParsingOptions {
            allow_dtd: true,
            ..Default::default()
        },
    )
    .map_err(|e| anyhow::anyhow!("{}", super::xml_error(&e, &text)))?;
    let root = xml.root_element();
    let mut records = Vec::new();
    if format == "jacoco" {
        for package in root.descendants().filter(|n| n.has_tag_name("package")) {
            let pkg = package.attribute("name").unwrap_or("");
            for source in package.children().filter(|n| n.has_tag_name("sourcefile")) {
                let Some(file) = source.attribute("name").filter(|s| !s.is_empty()) else {
                    continue;
                };
                let file = normalized(file, pkg);
                let mut hits = json!({});
                let mut branches = Vec::new();
                for (i, line) in source
                    .children()
                    .filter(|n| n.has_tag_name("line"))
                    .enumerate()
                {
                    if let Some(nr) = line.attribute("nr").filter(|s| !s.is_empty()) {
                        let nr = integer(nr)?;
                        hits[nr.to_string()] = json!(int_attr(line, "ci")?);
                    }
                    let cb = int_attr(line, "cb")?;
                    if cb + int_attr(line, "mb")? > 0 {
                        branches.push(
                            json!({"line":int_attr(line,"nr")?,"block":0,"branch":i,"hits":cb}),
                        );
                    }
                }
                if !hits.as_object().unwrap().is_empty() {
                    records.push(record(run, format, &file, hits, json!(branches), &contexts));
                }
            }
        }
    } else {
        let mut classes = Vec::new();
        for pkg in root.descendants().filter(|n| n.has_tag_name("package")) {
            for class in pkg.descendants().filter(|n| n.has_tag_name("class")) {
                classes.push((pkg.attribute("name").unwrap_or(""), class));
            }
        }
        if classes.is_empty() {
            classes.extend(
                root.descendants()
                    .filter(|n| n.has_tag_name("class"))
                    .map(|n| ("", n)),
            );
        }
        for (i, (pkg, class)) in classes.into_iter().enumerate() {
            let path = if let Some(filename) = class.attribute("filename").filter(|s| !s.is_empty())
            {
                filename.to_owned()
            } else {
                let mut name = class
                    .attribute("name")
                    .map(|s| s.replace('.', "/"))
                    .unwrap_or_else(|| format!("cobertura-{}", i + 1));
                let pkg = pkg.replace('.', "/");
                if !pkg.is_empty() && !name.starts_with(&pkg) {
                    name = format!("{pkg}/{name}");
                }
                name
            };
            let mut hits = json!({});
            for line in class.descendants().filter(|n| n.has_tag_name("line")) {
                if let Some(nr) = line.attribute("number").filter(|s| !s.is_empty()) {
                    hits[integer(nr)?.to_string()] = json!(int_attr(line, "hits")?);
                }
            }
            if !hits.as_object().unwrap().is_empty() {
                records.push(record(
                    run,
                    format,
                    &normalized(&path, pkg),
                    hits,
                    json!([]),
                    &contexts,
                ));
            }
        }
    }
    Ok(records)
}
fn integer(raw: &str) -> Result<i64> {
    raw.trim()
        .parse()
        .with_context(|| format!("invalid literal for int() with base 10: '{raw}'"))
}
fn int_attr(n: Node, key: &str) -> Result<i64> {
    integer(n.attribute(key).unwrap_or("0"))
}
fn normalized(raw: &str, package: &str) -> String {
    let raw = raw.replace('\\', "/");
    let mut text = raw.trim();
    if text.is_empty() {
        return if package.is_empty() {
            "unknown".into()
        } else {
            package.replace('.', "/")
        };
    }
    if text.as_bytes().get(1) == Some(&b':')
        && text.get(2..3) == Some("/")
        && text.as_bytes()[0].is_ascii_alphabetic()
    {
        text = &text[2..];
    }
    let path = text
        .split('/')
        .filter(|s| !s.is_empty())
        .collect::<Vec<_>>()
        .join("/");
    let path = if let Some(i) = [
        "src/",
        "tests/",
        "test/",
        "packages/",
        "pkg/",
        "app/",
        "lib/",
    ]
    .iter()
    .find_map(|m| path.find(m))
    {
        path[i..].to_owned()
    } else if !package.is_empty() && !path.contains('/') {
        format!("{}/{path}", package.replace('.', "/"))
    } else {
        path
    };
    let mut parts = Vec::new();
    for p in path.split('/') {
        match p {
            "" | "." => {}
            ".." if parts.last().is_some_and(|p| *p != "..") => {
                parts.pop();
            }
            _ => parts.push(p),
        }
    }
    if parts.is_empty() {
        ".".into()
    } else {
        parts.join("/")
    }
}
fn record(
    run: &Run,
    format: &str,
    file: &str,
    hits: Value,
    branches: Value,
    contexts: &Value,
) -> Value {
    let file = file.replace('\\', "/");
    let suffix = if matches!(format, "coverage.py" | "lcov") {
        slug(
            Path::new(&file)
                .file_stem()
                .and_then(|v| v.to_str())
                .unwrap_or(""),
        )
    } else {
        format!("{format}-{}", slug(&file))
    };
    run.record("coverage_slice","coverage-slice",&suffix,json!({"format":format,"file":file,"line_hits":hits,"branch_hits":branches,"contexts":contexts}))
}
fn lcov(run: &Run, text: &str, contexts: &Value) -> Result<Vec<Value>> {
    let mut records = Vec::new();
    let mut file = None;
    let mut hits = json!({});
    let mut branches = Vec::new();
    for line in text.lines().map(str::trim).chain(["end_of_record"]) {
        if line.starts_with("SF:") || line == "end_of_record" {
            if let Some(path) = file.take() {
                records.push(record(
                    run,
                    "lcov",
                    path,
                    std::mem::replace(&mut hits, json!({})),
                    json!(std::mem::take(&mut branches)),
                    contexts,
                ));
            }
            file = line.strip_prefix("SF:");
        } else if let Some(raw) = line.strip_prefix("DA:") {
            let (n, h) = raw.split_once(',').context("invalid DA record")?;
            hits[integer(n)?.to_string()] = json!(integer(h)?);
        } else if let Some(raw) = line.strip_prefix("BRDA:") {
            let fields: Vec<_> = raw.splitn(4, ',').collect();
            ensure!(fields.len() == 4, "invalid BRDA record");
            branches.push(json!({"line":integer(fields[0])?,"block":integer(fields[1])?,"branch":integer(fields[2])?,"hits":if fields[3]=="-"{0}else{integer(fields[3])?}}));
        }
    }
    Ok(records)
}
fn coverage_py(run: &Run, path: &Path) -> Result<Vec<Value>> {
    let doc = Document::read(path, false)?;
    let v = &doc.value;
    ensure!(v.is_object(), "coverage.py JSON must be an object");
    ensure!(
        v.get("meta").is_none_or(Value::is_object),
        "coverage.py meta must be an object"
    );
    ensure!(
        v["meta"]["show_contexts"] == true,
        "coverage.py JSON must have show_contexts: true for context extraction"
    );
    ensure!(
        v.get("files").is_none_or(Value::is_object),
        "coverage.py files must be an object"
    );
    let mut records = Vec::new();
    for file in doc.keys("coverage.json.files") {
        let data = &v["files"][file];
        if !data.is_object() || data.get("executed_lines").is_some_and(|v| !v.is_array()) {
            continue;
        }
        let mut hits = json!({});
        for n in super::items(&data["executed_lines"]) {
            if n.is_i64() || n.is_u64() {
                hits[n.to_string()] = json!(1);
            }
        }
        let mut seen = HashSet::new();
        let mut contexts = Vec::new();
        for line in doc.keys(&format!(
            "{}.contexts",
            Document::field("coverage.json.files", file)
        )) {
            for id in super::items(&data["contexts"][line])
                .iter()
                .filter_map(Value::as_str)
                .filter(|s| !s.is_empty())
            {
                let line = integer(line)?;
                if seen.insert((id, line)) {
                    contexts.push(json!({"test_id":id,"line":line}));
                }
            }
        }
        records.push(record(
            run,
            "coverage.py",
            file,
            hits,
            json!([]),
            &json!(contexts),
        ));
    }
    Ok(records)
}
