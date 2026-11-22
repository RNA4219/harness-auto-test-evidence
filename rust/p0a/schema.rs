use super::dq;
use anyhow::Result;
use jsonschema::{
    ValidationError,
    error::{TypeKind, ValidationErrorKind as Kind},
    paths::LocationSegment,
};
use serde_json::Value;
use std::collections::HashSet;
const COMMON: &str = include_str!("../../schemas/HATE/v1/common-envelope.schema.json");

fn schema(file: &str) -> Option<&'static str> {
    Some(match file {
        "HATE-run.json" => include_str!("../../schemas/HATE/v1/run.schema.json"),
        "HATE-test-results.ndjson" => include_str!("../../schemas/HATE/v1/test-result.schema.json"),
        "HATE-coverage.ndjson" => include_str!("../../schemas/HATE/v1/coverage-slice.schema.json"),
        "HATE-mutation.ndjson" => {
            include_str!("../../schemas/HATE/v1/mutation-evidence.schema.json")
        }
        "HATE-evidence-strength.ndjson" => {
            include_str!("../../schemas/HATE/v1/evidence-strength.schema.json")
        }
        "precheck-decision.json" => {
            include_str!("../../schemas/HATE/v1/precheck-decision.schema.json")
        }
        "record.json" => include_str!("../../schemas/HATE/v1/audit-record.schema.json"),
        _ => return None,
    })
}
fn repr(v: &Value) -> String {
    match v {
        Value::String(s) => format!("'{}'", s.replace('\\', "\\\\").replace('\'', "\\'")),
        Value::Array(a) => format!("[{}]", a.iter().map(repr).collect::<Vec<_>>().join(", ")),
        _ => super::numbers::stringify(v),
    }
}
pub(crate) fn message(e: &ValidationError) -> String {
    let mut loc = "$".to_owned();
    for part in e.instance_path().iter() {
        match part {
            LocationSegment::Property(p) => {
                loc.push('.');
                loc.push_str(&p)
            }
            LocationSegment::Index(i) => loc.push_str(&format!("[{i}]")),
        }
    }
    match e.kind() {
        Kind::Required { property } => format!("{loc}.{} is required", super::s(property)),
        Kind::Pattern { pattern } => format!("{loc} must match {pattern}"),
        Kind::Enum { options } => format!("{loc} must be one of {}", repr(options)),
        Kind::Constant { expected_value } => format!("{loc} must equal {}", repr(expected_value)),
        Kind::Type {
            kind: TypeKind::Single(t),
        } => format!("{loc} must be {t}"),
        Kind::Minimum { limit } => format!("{loc} must be >= {limit}"),
        Kind::Maximum { limit } => format!("{loc} must be <= {limit}"),
        Kind::MinLength { limit: 1 } => {
            format!("{loc}: {} should be non-empty", repr(e.instance()))
        }
        Kind::Format { format } => format!("{loc}: {} is not a '{format}'", repr(e.instance())),
        _ => format!("{loc}: {e}"),
    }
}
pub fn validate(outputs: &[(&str, Value)]) -> Result<Vec<Value>> {
    let root: Value = serde_json::from_str(COMMON)?;
    let registry = jsonschema::Registry::new()
        .add(
            "https://quality-harness.dev/schemas/hate/v1/common-envelope.schema.json",
            root,
        )?
        .prepare()?;
    let mut hits = Vec::new();
    let mut seen = HashSet::new();
    for &(file, ref data) in outputs {
        let Some(definition) = schema(file) else {
            continue;
        };
        let spec: Value = serde_json::from_str(definition)?;
        let validator = jsonschema::draft202012::options()
            .with_registry(&registry)
            .should_validate_formats(true)
            .build(&spec)?;
        let records = data
            .as_array()
            .map(Vec::as_slice)
            .unwrap_or(std::slice::from_ref(data));
        for record in records {
            let mut errors: Vec<_> = validator
                .iter_errors(record)
                .map(|e| (e.instance_path().to_string(), message(&e)))
                .collect();
            errors.sort();
            for (_, msg) in errors {
                if seen.insert((file, msg.clone())) {
                    hits.push(dq(
                        "HATE-DQ-015",
                        &format!("schema validation failed: {msg}"),
                        file,
                    ));
                }
            }
        }
    }
    Ok(hits)
}
