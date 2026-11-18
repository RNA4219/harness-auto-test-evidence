use super::*;
use crate::p0a::Document;
use bigdecimal::BigDecimal;
use std::{fs, str::FromStr};

pub(super) struct Input {
    pub b: V,
    pub r: V,
    pub id: String,
    pub attempt: V,
    pub bundle_ref: String,
    pub report_ref: String,
}

const COUNTS: [&str; 6] = [
    "retry_index",
    "attempt_index",
    "retry_count",
    "shard_index",
    "shard_total",
    "shard_count",
];

fn exact_field(
    doc: &Document,
    obj: &mut V,
    base: &str,
    field: &str,
    normalize: bool,
) -> Result<()> {
    let location = format!("{base}.{field}");
    let Some(raw) = doc.token(&location) else {
        return Ok(());
    };
    if normalize {
        obj[field] = crate::p0a::exact_uint(raw)
            .with_context(|| format!("{location}: must be a non-negative JSON integer"))?;
    } else {
        let number = BigDecimal::from_str(raw)?;
        ensure!(
            number.is_integer(),
            "{location}: must be a JSON integer; fractional values are invalid"
        );
    }
    Ok(())
}

pub(crate) fn strict_value(text: &str, kind: &str) -> Result<V> {
    let mut doc = Document::from_text(text, "$", true)?;
    let mut root = std::mem::take(&mut doc.value);
    if kind == "bundle" {
        if let Some(meta) = root.get_mut("metadata") {
            exact_field(&doc, meta, "$.metadata", "runAttempt", true)?;
        }
        if let Some(nodes) = root.get_mut("nodes").and_then(V::as_array_mut) {
            for (i, n) in nodes.iter_mut().enumerate() {
                let node_kind = s(n, "kind").to_owned();
                let gate = node_kind == "gate_verdict" && s(n, "id").starts_with("hate_precheck:");
                let Some(data) = n.get_mut("data") else {
                    continue;
                };
                let base = format!("$.nodes[{i}].data");
                if scoped(&node_kind) {
                    exact_field(&doc, data, &base, "run_attempt", true)?;
                }
                if node_kind == "run"
                    && let Some(ci) = data.get_mut("ci")
                {
                    exact_field(&doc, ci, &format!("{base}.ci"), "run_attempt", true)?;
                }
                if node_kind == "execution_evidence" {
                    for key in COUNTS {
                        exact_field(&doc, data, &base, key, true)?;
                    }
                }
                if gate {
                    exact_field(&doc, data, &base, "exit_code", false)?;
                }
            }
        }
    } else {
        if kind != "risk-debt-lifecycle.json" {
            exact_field(&doc, &mut root, "$", "run_attempt", true)?;
        }
        if let Some(payload) = root.get_mut("payload") {
            match kind {
                "precheck-decision.json" => {
                    exact_field(&doc, payload, "$.payload", "exit_code", false)?
                }
                "HATE-test-results.ndjson" => {
                    for key in COUNTS {
                        exact_field(&doc, payload, "$.payload", key, true)?;
                    }
                }
                "HATE-run.json" => {
                    if let Some(ci) = payload.get_mut("ci") {
                        exact_field(&doc, ci, "$.payload.ci", "run_attempt", true)?;
                    }
                }
                _ => (),
            }
        }
        if kind == "risk-debt-lifecycle.json"
            && let Some(items) = root.get_mut("items").and_then(V::as_array_mut)
        {
            for (i, item) in items.iter_mut().enumerate() {
                exact_field(&doc, item, &format!("$.items[{i}]"), "age_days", true)?;
            }
        }
    }
    Ok(root)
}
pub(crate) fn strict_json(p: &Path, kind: &str) -> Result<V> {
    let text =
        fs::read_to_string(p).with_context(|| format!("cannot read JSON input {}", p.display()))?;
    let v = strict_value(&text, kind)
        .with_context(|| format!("cannot read JSON input {}", p.display()))?;
    ensure!(v.is_object(), "{} must contain a JSON object", p.display());
    Ok(v)
}

// The reader has already normalized numeric count fields to plain decimal integers.
pub(crate) fn count(v: &V, positive: bool) -> Option<&V> {
    let digits = v.as_number()?.as_str();
    (digits.bytes().all(|c| c.is_ascii_digit()) && (!positive || digits != "0")).then_some(v)
}
pub(crate) fn commit(v: &V) -> bool {
    v.as_str()
        .is_some_and(|v| (7..=64).contains(&v.len()) && v.bytes().all(|c| c.is_ascii_hexdigit()))
}
pub(super) fn scoped(kind: &str) -> bool {
    matches!(
        kind,
        "run"
            | "gate_verdict"
            | "test"
            | "execution_evidence"
            | "coverage"
            | "contract_evidence"
            | "mutation_evidence"
            | "evidence_strength"
            | "evidence_artifact"
    )
}
pub(crate) fn normalize_fields(data: &mut V, execution: bool) -> Result<()> {
    for k in ["matrix", "matrix_values"] {
        if let Some(v) = data.get(k) {
            ensure!(v.is_object(), "{k} must be a JSON object")
        }
    }
    for k in ["flaky", "wouldRun"] {
        if let Some(v) = data.get(k) {
            ensure!(v.is_boolean(), "{k} must be a boolean")
        }
    }
    for k in ["status", "source_status"] {
        if let Some(v) = data.get(k) {
            ensure!(
                v.as_str().is_some_and(|s| !s.trim().is_empty()),
                "{k} must be a non-empty string"
            )
        }
    }
    if execution {
        for k in [
            "retry_index",
            "attempt_index",
            "retry_count",
            "shard_index",
            "shard_total",
            "shard_count",
        ] {
            if let Some(value) = data.get(k) {
                let positive = matches!(k, "shard_total" | "shard_count");
                ensure!(
                    count(value, positive).is_some(),
                    "{k} must be a JSON integer >= {}",
                    u8::from(positive)
                );
            }
        }
    }
    for (key, alias) in [
        ("matrix", "matrix_values"),
        ("retry_index", "attempt_index"),
        ("shard_total", "shard_count"),
    ] {
        if !execution && key != "matrix" {
            continue;
        }
        if let Some(v) = data.get(alias) {
            ensure!(
                data.get(key).is_none_or(|n| n == v),
                "conflicting {key} and {alias} declarations"
            );
            data[key] = v.clone();
        }
    }
    Ok(())
}

pub(super) fn read(call: &Invocation) -> Result<Input> {
    let bp = call.path("bundle");
    let rp = call.path("report");
    let mut b = strict_json(bp, "bundle")?;
    let r = strict_json(rp, "report")?;
    if let Some(meta) = b.get("metadata") {
        ensure!(
            meta.is_object(),
            "{}: metadata must be a JSON object",
            bp.display()
        );
        for key in ["createdAt", "profile"] {
            ensure!(
                meta.get(key).is_none_or(V::is_string),
                "{}: metadata.{key} must be a string",
                bp.display()
            );
        }
    }
    let mut id: Option<String> = None;
    let mut attempt = None;
    for (data, ik, ak) in [
        (&b["metadata"], "runId", "runAttempt"),
        (&r, "run_id", "run_attempt"),
    ] {
        if let Some(raw) = data.get(ik) {
            let v = raw
                .as_str()
                .filter(|v| !v.trim().is_empty())
                .context("must be a non-empty run identifier")?;
            ensure!(id.as_deref().is_none_or(|old| old == v), "run_id mismatch");
            id = Some(v.to_owned())
        }
        if let Some(raw) = data.get(ak) {
            let v = count(raw, true).context("run_attempt must be a positive integer")?;
            ensure!(
                attempt.as_ref().is_none_or(|old| old == v),
                "run_attempt mismatch"
            );
            attempt = Some(v.clone());
        }
    }
    let id = id.context("run_id is missing from both inputs")?;
    let attempt = attempt.context("run_attempt is missing from both inputs")?;
    for (field, kind) in [
        ("export_status", "string"),
        ("created_at", "string"),
        ("commit_sha", "string"),
        ("completeness", "object"),
        ("qeg_schema_compatibility", "object"),
        ("source_refs", "strings"),
        ("missing_execution", "objects"),
        ("unsupportedClaims", "objects"),
        ("excludedArtifacts", "objects"),
    ] {
        if let Some(v) = r.get(field) {
            let ok = match kind {
                "string" => v.is_string(),
                "object" => v.is_object(),
                "strings" => v.as_array().is_some_and(|a| a.iter().all(V::is_string)),
                _ => v.as_array().is_some_and(|a| {
                    a.iter().all(|o| {
                        o.is_object()
                            && ["reason", "risk_id", "expected_test_ref", "artifact_id"]
                                .iter()
                                .all(|k| o.get(*k).is_none_or(V::is_string))
                    })
                }),
            };
            ensure!(ok, "invalid input structure: {}: {field}", rp.display());
        }
    }
    for (key, kind) in [("schema", "string"), ("valid", "bool"), ("errors", "array")] {
        if let Some(v) = r["qeg_schema_compatibility"].get(key) {
            ensure!(
                match kind {
                    "string" => v.is_string(),
                    "bool" => v.is_boolean(),
                    _ => v.is_array(),
                },
                "invalid input structure: qeg_schema_compatibility.{key}"
            );
        }
    }
    let schema = analysis::validator();
    for error in schema.iter_errors(&b) {
        if matches!(
            error.kind(),
            jsonschema::error::ValidationErrorKind::Type { .. }
        ) {
            anyhow::bail!("invalid input structure: {}: {error}", bp.display());
        }
    }
    let mut anchor = None;
    let mut inspect_commit = |v: &V| -> Result<()> {
        ensure!(v.is_string(), "commit_sha must be a string");
        if commit(v) {
            let n = v.as_str().unwrap().to_ascii_lowercase();
            ensure!(
                anchor.as_ref().is_none_or(|a| a == &n),
                "commit_sha mismatch"
            );
            anchor = Some(n)
        }
        Ok(())
    };
    if let Some(v) = r.get("commit_sha") {
        inspect_commit(v)?;
    }
    if let Some(v) = b["metadata"].get("commitSha") {
        inspect_commit(v)?;
    }
    let scope = |data: &mut V| -> Result<()> {
        if let Some(v) = data.get("run_id") {
            ensure!(v == id.as_str(), "run_id mismatch with resolved run_id");
        }
        if let Some(v) = data.get("run_attempt") {
            ensure!(
                count(v, true) == Some(&attempt),
                "run_attempt mismatch with resolved run_attempt"
            );
        }
        Ok(())
    };
    if let Some(nodes) = b.get_mut("nodes").and_then(V::as_array_mut) {
        for (index, n) in nodes.iter_mut().enumerate() {
            let kind = s(n, "kind").to_owned();
            let gate = kind == "gate_verdict" && s(n, "id").starts_with("hate_precheck:");
            if n.get("data").is_none() {
                continue;
            }
            let data = &mut n["data"];
            let location = format!("{}: nodes[{index}].data", bp.display());
            if scoped(&kind) {
                scope(data).with_context(|| location.clone())?;
                if let Some(v) = data.get("commit_sha") {
                    inspect_commit(v).with_context(|| format!("{location}.commit_sha"))?;
                }
            }
            if kind == "run"
                && let Some(ci) = data.get_mut("ci")
            {
                ensure!(ci.is_object(), "{location}.ci must be a JSON object");
                scope(ci).with_context(|| format!("{location}.ci"))?;
                if let Some(v) = ci.get("commit_sha") {
                    inspect_commit(v)?;
                }
            }
            if matches!(kind.as_str(), "test" | "execution_evidence") {
                normalize_fields(data, kind == "execution_evidence")
                    .with_context(|| location.clone())?;
            }
            if gate {
                for (k, kind) in [
                    ("decision", "str"),
                    ("qeg_export_allowed", "bool"),
                    ("exit_code", "int"),
                    ("reasons", "strings"),
                    ("dq_hits", "objects"),
                    ("soft_gaps", "objects"),
                ] {
                    if let Some(v) = data.get(k) {
                        ensure!(
                            match kind {
                                "str" => v.is_string(),
                                "bool" => v.is_boolean(),
                                "int" => v.is_number(),
                                "strings" =>
                                    v.as_array().is_some_and(|a| a.iter().all(V::is_string)),
                                _ => v.as_array().is_some_and(|a| a.iter().all(V::is_object)),
                            },
                            "{location}.{k}: invalid precheck field"
                        );
                    }
                }
            }
        }
    }
    Ok(Input {
        b,
        r,
        id,
        attempt,
        bundle_ref: stable_ref(bp, true)?,
        report_ref: stable_ref(rp, true)?,
    })
}
