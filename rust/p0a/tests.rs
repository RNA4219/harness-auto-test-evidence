use super::{
    Run, name,
    numbers::{self, Document},
    slug,
};
use anyhow::{Context, Result, bail, ensure};
use bigdecimal::{BigDecimal, Zero};
use serde_json::{Value, json};
use std::{collections::HashMap, fs, path::Path};

pub fn parse(run: &Run, path: &Path, family: &str) -> Result<Vec<Value>> {
    if family == "junit" {
        return junit(run, &fs::read_to_string(path)?);
    }
    let doc = Document::read(path, false)?;
    let key = if family == "pytest" {
        "tests"
    } else {
        "testResults"
    };
    ensure!(
        doc.value.get(key).is_some(),
        "{family} report requires {key} array"
    );
    let groups = doc.value[key]
        .as_array()
        .with_context(|| format!("{family} {key} must be a list"))?;
    let mut records = Vec::new();
    let mut counts = HashMap::new();
    let mut push = |p: Value| {
        let digest = numbers::hash(&p);
        let count = counts.entry(digest.clone()).or_insert(0);
        *count += 1;
        records.push(run.record(
            "test_result",
            "test-result",
            &format!("{family}-{digest}-{count}"),
            p,
        ));
    };
    for (i, group) in groups.iter().enumerate() {
        let loc = format!("{}.{key}[{i}]", name(path));
        if family == "pytest" {
            ensure!(group.is_object(), "pytest test entry must be an object");
            let id = identity(&group["nodeid"], &format!("{loc}.nodeid"), false)?;
            let file = if id.contains("::") {
                id.split("::").next().unwrap()
            } else {
                "unknown.py"
            };
            let mut p = json!({"canonical_test_id":format!("pytest:{id}"),"framework":family,"file":file.replace('\\',"/"),
                "identity_components":{"framework":family,"suite":file,"name":id.rsplit("::").next()},"artifacts":[]});
            extend(&mut p, outcome(&doc, group, family, &loc)?);
            extend(&mut p, metadata(Some(&doc), group, &loc, "reruns", false)?);
            push(p);
            continue;
        }
        ensure!(group.is_object(), "{family} suite entry must be an object");
        let empty = json!([]);
        let rows = group
            .get("assertionResults")
            .unwrap_or(&empty)
            .as_array()
            .with_context(|| format!("{family} assertionResults must be a list"))?;
        if rows.is_empty() {
            continue;
        }
        let file = identity(&group["name"], &format!("{loc}.name"), false)?;
        for (j, row) in rows.iter().enumerate() {
            let loc = format!("{loc}.assertionResults[{j}]");
            ensure!(
                row.is_object(),
                "{family} assertion entry must be an object"
            );
            let full = identity(
                row.get("fullName").unwrap_or(&row["title"]),
                &format!("{loc}.fullName"),
                false,
            )?;
            let title = if let Some(title) = row.get("title") {
                identity(title, &format!("{loc}.title"), true)?
            } else {
                full
            };
            let ancestors = row
                .get("ancestorTitles")
                .unwrap_or(&empty)
                .as_array()
                .with_context(|| format!("{loc}.ancestorTitles must be an array of strings"))?;
            for (k, a) in ancestors.iter().enumerate() {
                identity(a, &format!("{loc}.ancestorTitles[{k}]"), true)?;
            }
            let mut p = json!({"canonical_test_id":format!("{family}:{file}::{full}"),"framework":family,"file":file.replace('\\',"/"),"identity_components":{"framework":family,"suite":file,"name":title,"ancestors":ancestors},"artifacts":[]});
            extend(&mut p, outcome(&doc, row, family, &loc)?);
            if family == "jest"
                && super::items(&row["failureMessages"])
                    .iter()
                    .any(|v| numbers::stringify(v).to_lowercase().contains("snapshot"))
            {
                p["failure_type"] = json!("snapshot_mismatch");
            }
            let mut fields = metadata(Some(&doc), row, &loc, "retryCount", false)?;
            if let Some(meta) = row.get("meta") {
                ensure!(
                    meta.is_object(),
                    "{family} assertion meta must be an object"
                );
                merge(
                    &mut fields,
                    metadata(
                        Some(&doc),
                        meta,
                        &format!("{loc}.meta"),
                        "retryCount",
                        false,
                    )?,
                    &loc,
                )?;
            }
            extend(&mut p, fields);
            push(p);
        }
    }
    Ok(records)
}

fn identity<'a>(v: &'a Value, loc: &str, allow_empty: bool) -> Result<&'a str> {
    v.as_str()
        .filter(|s| allow_empty || !s.trim().is_empty())
        .with_context(|| {
            format!(
                "{loc} must be a {}",
                if allow_empty {
                    "string"
                } else {
                    "non-empty string"
                }
            )
        })
}

fn extend(dest: &mut Value, more: Value) {
    if let Value::Object(m) = more {
        dest.as_object_mut().unwrap().extend(m);
    }
}

fn diagnostic(code: &str, loc: &str, message: &str) -> Value {
    json!({"code":code,"severity":"warning","sourceRef":loc,"message":message})
}

fn outcome(doc: &Document, row: &Value, family: &str, loc: &str) -> Result<Value> {
    let pytest = family == "pytest";
    let field = if pytest { "outcome" } else { "status" };
    let declared = match row.get(field) {
        Some(v) => identity(v, &format!("{loc}.{field}"), false)?,
        None => "unknown",
    };
    let mut diagnostics = Vec::new();
    let status = match declared {
        "passed" | "failed" | "skipped" | "error" => declared,
        "xfail" | "xfailed" if pytest => "skipped",
        "xpass" | "xpassed" if pytest => "passed",
        "pending" | "todo" | "disabled" if !pytest => "skipped",
        "focused" if !pytest => "inconclusive",
        status => {
            diagnostics.push(diagnostic(
                "unsupported_test_status",
                &format!("{loc}.{field}"),
                &format!("Reported status '{status}' does not establish pass or failure."),
            ));
            "inconclusive"
        }
    };
    let mut v = json!({"source_status":declared,"status":status});
    if pytest && matches!(declared, "xfail" | "xfailed" | "xpass" | "xpassed") {
        v["xfail"] = json!(true);
        if matches!(declared, "xpass" | "xpassed") {
            v["xpass"] = json!(true);
        }
    }
    if declared == "todo" {
        v["todo"] = json!(true);
    }
    if declared == "focused" {
        v["only"] = json!(true);
    }
    if let Some(w) = row.get("wouldRun") {
        ensure!(w.is_boolean(), "{loc}.wouldRun must be a boolean");
        v["wouldRun"] = w.clone();
        if w == true {
            v["status"] = json!("inconclusive");
            diagnostics.push(diagnostic(
                "test_not_executed",
                &format!("{loc}.wouldRun"),
                "Test was collected as runnable but was not executed.",
            ));
        }
    }
    let number = |k: &str| -> Result<BigDecimal> {
        let key = format!("{loc}.{k}");
        let raw = doc.token(&key).with_context(|| {
            format!("{key} must be a finite non-negative number; booleans and strings are invalid")
        })?;
        numbers::duration(raw, &key)
    };
    let mut total = BigDecimal::zero();
    if pytest {
        for stage in ["setup", "call", "teardown"] {
            if let Some(v) = row.get(stage) {
                ensure!(v.is_object(), "{loc}.{stage} must be an object");
                if v.get("duration").is_some() {
                    total += number(&format!("{stage}.duration"))?;
                }
            }
        }
    }
    if let Some(d) = row.get("duration") {
        if d.is_null() && !pytest {
            diagnostics.push(diagnostic(
                "duration_not_reported",
                &format!("{loc}.duration"),
                "Duration was not reported; duration_ms=0 is a compatibility placeholder.",
            ));
        } else {
            total = number("duration")?;
        }
    }
    v["duration_ms"] = numbers::millis(total, pytest)?;
    if !diagnostics.is_empty() {
        v["parser_diagnostics"] = json!(diagnostics);
    }
    Ok(v)
}

const FIELDS: [&str; 9] = [
    "retry_index",
    "attempt_index",
    "retry_count",
    "matrix",
    "matrix_values",
    "shard_index",
    "shard_total",
    "shard_count",
    "flaky",
];
fn merge(v: &mut Value, other: Value, loc: &str) -> Result<()> {
    for (k, b) in other.as_object().unwrap() {
        ensure!(
            v.get(k).is_none_or(|a| a == b),
            "{loc}: conflicting {k} declarations"
        );
        v[k] = b.clone();
    }
    aliases(v, loc)
}
fn aliases(v: &mut Value, loc: &str) -> Result<()> {
    for (c, a) in [
        ("matrix", "matrix_values"),
        ("retry_index", "attempt_index"),
        ("shard_total", "shard_count"),
    ] {
        if let Some(other) = v.get(a) {
            ensure!(
                v.get(c).is_none_or(|x| x == other),
                "{loc}: conflicting {c} and {a} declarations"
            );
            v[c] = other.clone();
        }
    }
    Ok(())
}
fn metadata(
    doc: Option<&Document>,
    row: &Value,
    loc: &str,
    native: &str,
    xml: bool,
) -> Result<Value> {
    let mut result = json!({});
    for field in FIELDS.into_iter().chain([native]) {
        let Some(value) = row.get(field) else {
            continue;
        };
        let raw = value.as_str().unwrap_or("").trim();
        let key = if field == "retry" {
            "retry_index"
        } else if field == native {
            "retry_count"
        } else {
            field
        };
        let parsed = match key {
            "matrix" | "matrix_values" => {
                let v = if xml {
                    serde_json::from_str(raw)?
                } else {
                    value.clone()
                };
                ensure!(v.is_object(), "{loc}.{key} must be a JSON object");
                v
            }
            "flaky" if xml => match raw.to_lowercase().as_str() {
                "true" | "1" | "yes" | "on" | "y" => json!(true),
                "false" | "0" | "no" | "off" | "n" => json!(false),
                _ => bail!("{loc}.flaky must be a boolean declaration"),
            },
            "flaky" => {
                ensure!(value.is_boolean(), "{loc}.flaky must be a boolean");
                value.clone()
            }
            _ => {
                let token = if xml {
                    raw
                } else {
                    doc.and_then(|doc| doc.token(&format!("{loc}.{field}")))
                        .unwrap_or("")
                };
                let min = u64::from(matches!(key, "shard_count" | "shard_total"));
                let integer = numbers::exact_uint(token)
                    .ok()
                    .filter(|x| min == 0 || *x != json!(0))
                    .with_context(|| format!("{loc}.{field} must be a JSON integer >= {min}"))?;
                integer
            }
        };
        if let Some(prev) = result.get(key) {
            ensure!(*prev == parsed, "{loc}: conflicting {key} and {field}");
        }
        result[key] = parsed;
    }
    aliases(&mut result, loc)?;
    Ok(result)
}

fn junit(run: &Run, text: &str) -> Result<Vec<Value>> {
    let xml = roxmltree::Document::parse_with_options(
        text,
        roxmltree::ParsingOptions {
            allow_dtd: true,
            ..Default::default()
        },
    )
    .map_err(|e| anyhow::anyhow!("malformed_xml: {}", super::xml_error(&e, text)))?;
    let root = xml.root_element();
    let suites: Vec<_> = if root.has_tag_name("testsuite") {
        vec![root]
    } else if root.has_tag_name("testsuites") {
        root.descendants()
            .filter(|n| n.has_tag_name("testsuite"))
            .collect()
    } else {
        bail!("missing_testsuite_root: {}", root.tag_name().name())
    };
    ensure!(!suites.is_empty(), "missing_testsuite");
    let mut rows = Vec::new();
    let mut groups = HashMap::<String, Vec<usize>>::new();
    for suite in suites {
        let suite_name = suite.attribute("name").unwrap_or("junit");
        for (i, case) in suite
            .children()
            .filter(|n| n.has_tag_name("testcase"))
            .enumerate()
        {
            let loc = format!("junit.xml#/testsuite/{suite_name}/testcase/{}", i + 1);
            let test = case
                .attribute("name")
                .filter(|n| !n.trim().is_empty())
                .with_context(|| format!("{loc}.name must be a non-empty string"))?;
            let ms = numbers::millis(
                numbers::duration(
                    case.attribute("time").unwrap_or("0"),
                    &format!("{loc}.time"),
                )?,
                true,
            )?;
            let class = case.attribute("classname").unwrap_or("");
            let file = case
                .attribute("file")
                .filter(|s| !s.is_empty())
                .map(str::to_owned)
                .unwrap_or_else(|| {
                    if !class.is_empty() {
                        return format!(
                            "{}{}",
                            class.replace('.', "/"),
                            if class.starts_with("Test") && !class.contains('.') {
                                ".go"
                            } else {
                                ".py"
                            }
                        );
                    }
                    if [".js", ".ts", ".py", ".go"]
                        .iter()
                        .any(|suffix| suite_name.ends_with(suffix))
                    {
                        suite_name.into()
                    } else {
                        "unknown.py".into()
                    }
                })
                .replace('\\', "/");
            let child = |tag: &str| case.children().find(|n| n.has_tag_name(tag));
            let (status, message) = [
                ("failure", "failed"),
                ("error", "error"),
                ("skipped", "skipped"),
            ]
            .iter()
            .find_map(|(tag, status)| {
                let n = child(tag)?;
                Some((
                    *status,
                    n.attribute("message")
                        .filter(|s| !s.is_empty())
                        .unwrap_or_else(|| n.text().unwrap_or("").trim()),
                ))
            })
            .unwrap_or(("passed", ""));
            let id = format!("junit:{file}::{test}");
            let mut p = json!({"canonical_test_id":id,"framework":"junit","status":status,"duration_ms":ms,"file":file,
                "identity_components":{"framework":"junit","suite":suite_name,"classname":class,"name":test},"artifacts":[],"sourceRef":loc});
            if !message.is_empty() {
                p["message"] = json!(message);
                p["failure_text_hash"] = json!(&numbers::hash(&json!(message))[..16]);
            }
            let mut props = json!({});
            for prop in case
                .children()
                .filter(|n| n.has_tag_name("properties"))
                .flat_map(|n| n.children())
                .filter(|n| n.has_tag_name("property"))
            {
                if let Some(key) = prop.attribute("name") {
                    props[key.to_lowercase()] = json!(prop.attribute("value").unwrap_or("true"));
                }
            }
            let mut attrs = json!({});
            for a in case.attributes() {
                attrs[a.name()] = json!(a.value());
            }
            let blob = format!(
                "{message} {test} {class} {} {}",
                child("system-out").and_then(|v| v.text()).unwrap_or(""),
                child("system-err").and_then(|v| v.text()).unwrap_or("")
            )
            .to_lowercase();
            for marker in ["xfail", "todo", "only"] {
                if blob.contains(marker)
                    || [&props[marker], &attrs[marker]].iter().any(|v| {
                        matches!(
                            super::s(v).to_lowercase().as_str(),
                            "1" | "true" | "yes" | "y" | "on"
                        )
                    })
                {
                    p[marker] = json!(true);
                }
            }
            let mut fields = metadata(None, &props, &loc, "retry", true)?;
            merge(
                &mut fields,
                metadata(None, &attrs, &loc, "retry", true)?,
                &loc,
            )?;
            extend(&mut p, fields);
            if status == "skipped" && message.is_empty() {
                p["parser_diagnostics"] =
                    json!([{"code":"skipped_without_reason","severity":"warning"}]);
            }
            let key = json!([
                id,
                p.get("matrix").cloned().unwrap_or(json!({})),
                p.get("retry_index").cloned().unwrap_or(json!(0)),
                p["shard_index"]
            ])
            .to_string();
            groups.entry(key).or_default().push(rows.len());
            rows.push(p);
        }
    }
    for indices in groups.values().filter(|v| v.len() > 1) {
        for &i in indices {
            let p = &mut rows[i];
            if p.get("parser_diagnostics").is_none() {
                p["parser_diagnostics"] = json!([]);
            }
            p["parser_diagnostics"]
                .as_array_mut()
                .unwrap()
                .push(json!({"code":"duplicate_testcase_id","severity":"error"}));
        }
    }
    Ok(rows
        .into_iter()
        .enumerate()
        .map(|(i, p)| {
            let suffix = slug(&format!(
                "{}-{}",
                i + 1,
                super::s(&p["identity_components"]["name"])
            ));
            run.record("test_result", "test-result", &suffix, p)
        })
        .collect())
}
