use super::{Context, Result, Value, json};
use anyhow::{bail, ensure};
use chrono::{DateTime, NaiveDate, SecondsFormat, Utc};
use std::{
    cmp::Ordering,
    path::{Path, PathBuf},
    sync::LazyLock,
};

pub(super) fn join_path(v: &Value, child: &Value) -> Value {
    let result = to_path(v).join(text(child));
    let normal: PathBuf = result
        .components()
        .filter(|c| *c != std::path::Component::CurDir)
        .collect();
    json!(if normal.as_os_str().is_empty() {
        Path::new(".")
    } else {
        &normal
    })
}
pub(super) fn ordered_members(v: &Value, op: &str, keys: &[&str]) -> Result<Value> {
    Ok(json!(
        keys.iter()
            .map(|k| match op {
                "items" => json!([k, v[*k]]),
                "values" => v[*k].clone(),
                _ => json!(k),
            })
            .collect::<Vec<_>>()
    ))
}
pub(super) fn extrema<F>(v: &Value, key: F, maximum: bool) -> Result<Value>
where
    F: Fn(&Value) -> Result<Value>,
{
    let mut selected: Option<(Value, Value)> = None;
    for item in sequence(v)? {
        let rank = key(&item)?;
        if selected.as_ref().is_none_or(|(prior, _)| {
            if maximum {
                compare(&rank, prior).is_gt()
            } else {
                compare(&rank, prior).is_lt()
            }
        }) {
            selected = Some((rank, item));
        }
    }
    selected.map(|(_, v)| v).context("empty extrema")
}
pub(super) fn budget_input(value: &Value) -> Result<Value> {
    let mut out = json!({"scenario_id":indexed(value,&json!("scenario_id"))?,"profile":value.get("profile").cloned().unwrap_or(json!("default"))});
    for key in [
        "dataset_shape",
        "observed_ms",
        "estimated_counters",
        "thresholds_ms",
        "sourceRefs",
    ] {
        out[key] = value.get(key).cloned().unwrap_or_else(|| {
            if key == "sourceRefs" {
                json!([])
            } else {
                json!({})
            }
        });
    }
    if let Some(shape) = out["dataset_shape"].as_object_mut() {
        for metric in shape.values_mut() {
            *metric = json!(integer(metric)?);
        }
    }
    Ok(out)
}
pub(super) fn stale(value: &Value, today: &Value) -> bool {
    let date = |v: &Value| {
        v.as_str()
            .and_then(|s| NaiveDate::parse_from_str(s, "%Y-%m-%d").ok())
    };
    !truth(&value["review_owner"])
        || date(today)
            .zip(date(&value["reviewed_at"]))
            .is_none_or(|(t, r)| {
                (t - r).num_days() > value["stale_after_days"].as_i64().unwrap_or(0)
            })
}

pub(super) use crate::io::{ascii_digest as ascii_hash, is_truthy as truth, py_string as text};

static CATALOG: LazyLock<Value> = LazyLock::new(|| {
    serde_json::from_str(include_str!("catalog.json")).expect("valid report catalog")
});
pub(super) fn catalog(key: &str) -> Value {
    CATALOG[key].clone()
}
pub(super) fn to_path(v: &Value) -> PathBuf {
    PathBuf::from(text(v))
}
pub(super) fn today() -> String {
    chrono::Local::now().date_naive().to_string()
}

pub(super) fn now() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Secs, true)
}
pub(super) fn attr(v: &Value, key: &str) -> Value {
    v.get(key).cloned().unwrap_or_default()
}
pub(super) fn get(v: &Value, k: &Value, default: Value) -> Value {
    v.get(text(k)).cloned().unwrap_or(default)
}
pub(super) fn number(v: &Value) -> Result<f64> {
    match v {
        Value::Bool(b) => Ok(f64::from(*b)),
        Value::String(s) => Ok(s.trim().parse()?),
        _ => v.as_f64().context("expected a number"),
    }
}
pub(super) fn integer(v: &Value) -> Result<i64> {
    if let Some(i) = v.as_i64() {
        return Ok(i);
    }
    if let Some(s) = v.as_str() {
        return Ok(s.trim().parse()?);
    }
    Ok(number(v)? as i64)
}
pub(super) fn equal(a: &Value, b: &Value) -> bool {
    if (a.is_number() || a.is_boolean()) && (b.is_number() || b.is_boolean()) {
        return number(a).ok() == number(b).ok();
    }
    a == b
}
pub(super) fn compare(a: &Value, b: &Value) -> Ordering {
    match (a, b) {
        (Value::Array(x), Value::Array(y)) => x
            .iter()
            .zip(y)
            .map(|(l, r)| compare(l, r))
            .find(|o| !o.is_eq())
            .unwrap_or(x.len().cmp(&y.len())),
        (Value::Number(_), Value::Number(_)) => a
            .as_f64()
            .partial_cmp(&b.as_f64())
            .unwrap_or(Ordering::Equal),
        (Value::String(x), Value::String(y)) => x.cmp(y),
        _ => text(a).cmp(&text(b)),
    }
}
pub(super) fn is_subset(left: &Value, right: &Value, strict: bool) -> Result<bool> {
    let left = sequence(left)?;
    Ok((!strict || left.len() < sequence(right)?.len())
        && left.iter().all(|item| contains(right, item)))
}
pub(super) fn contains(v: &Value, k: &Value) -> bool {
    match v {
        Value::Array(v) => v.iter().any(|x| equal(x, k)),
        Value::Object(m) => m.contains_key(&text(k)),
        Value::String(s) => s.contains(&text(k)),
        _ => false,
    }
}
pub(super) fn sequence(v: &Value) -> Result<Vec<Value>> {
    Ok(match v {
        Value::Array(a) => a.clone(),
        Value::Object(m) => m.keys().map(|k| json!(k)).collect(),
        Value::String(s) => s.chars().map(|c| json!(c)).collect(),
        _ => bail!("expected an array or object, got {}", v),
    })
}
pub(super) fn unique(values: Vec<Value>) -> Value {
    let mut seen = std::collections::BTreeSet::new();
    Value::Array(
        values
            .into_iter()
            .filter(|v| seen.insert(v.to_string()))
            .collect(),
    )
}
pub(super) fn strings(v: &Value) -> Result<Vec<String>> {
    Ok(sequence(v)?.iter().map(text).collect())
}
fn idx(n: i64, len: usize) -> usize {
    if n < 0 {
        (len as i64 + n).max(0) as usize
    } else {
        n as usize
    }
}
pub(super) fn indexed(v: &Value, k: &Value) -> Result<Value> {
    if let Some(a) = v.as_array() {
        return a
            .get(idx(integer(k)?, a.len()))
            .cloned()
            .with_context(|| format!("array index out of range: {k}"));
    }
    if let Some(s) = v.as_str() {
        return s
            .chars()
            .nth(idx(integer(k)?, s.chars().count()))
            .map(|c| json!(c))
            .context("string index out of range");
    }
    v.get(text(k))
        .cloned()
        .with_context(|| format!("missing report field {}", text(k)))
}
pub(super) fn slice(v: &Value, lo: Option<i64>, hi: Option<i64>) -> Value {
    let seq = sequence(v).unwrap_or_default();
    let len = seq.len();
    let begin = idx(lo.unwrap_or(0), len).min(len);
    let end = hi.map(|n| idx(n, len)).unwrap_or(len).min(len).max(begin);
    let sliced = &seq[begin..end];
    if v.is_string() {
        json!(sliced.iter().map(text).collect::<String>())
    } else {
        json!(sliced)
    }
}
pub(super) fn index_mut<'a>(v: &'a mut Value, k: &Value) -> Result<&'a mut Value> {
    if v.is_array() {
        let i = integer(k)?;
        let a = v.as_array_mut().unwrap();
        let n = idx(i, a.len());
        return a.get_mut(n).context("invalid array index");
    }
    v.as_object_mut()
        .context("expected an object")?
        .get_mut(&text(k))
        .context("missing object key")
}
pub(super) fn set_index(v: &mut Value, k: &Value, x: Value) -> Result<()> {
    if let Some(o) = v.as_object_mut() {
        o.insert(text(k), x);
    } else {
        *index_mut(v, k)? = x;
    }
    Ok(())
}
pub(super) fn default_mut<'a>(v: &'a mut Value, k: &Value, x: Value) -> Result<&'a mut Value> {
    Ok(v.as_object_mut()
        .context("expected an object")?
        .entry(text(k))
        .or_insert(x))
}
pub(super) fn merge(v: &mut Value, x: Value) -> Result<()> {
    v.as_object_mut()
        .context("expected an object")?
        .extend(x.as_object().context("expected an object")?.clone());
    Ok(())
}
pub(super) fn edit(v: &mut Value, op: &str, x: Value) -> Result<()> {
    if op == "update" && v.is_object() {
        return merge(v, x);
    }
    let vec = v.as_array_mut().context("expected an array")?;
    match op {
        "append" => vec.push(x),
        "extend" => vec.extend(sequence(&x)?),
        "add" => {
            if !vec.contains(&x) {
                vec.push(x)
            }
        }
        "update" => {
            for value in sequence(&x)? {
                if !vec.contains(&value) {
                    vec.push(value)
                }
            }
        }
        _ => bail!("unknown collection operation {op}"),
    }
    Ok(())
}
pub(super) fn sorted<F>(v: &Value, key: F, reverse: bool) -> Result<Value>
where
    F: Fn(&Value) -> Result<Value>,
{
    let mut values = Vec::new();
    for x in sequence(v)? {
        values.push((key(&x)?, x))
    }
    values.sort_by(|a, b| {
        let order = compare(&a.0, &b.0);
        if reverse { order.reverse() } else { order }
    });
    Ok(Value::Array(values.into_iter().map(|(_, v)| v).collect()))
}
pub(super) fn members(v: &Value, op: &str) -> Result<Value> {
    Ok(Value::Array(
        v.as_object()
            .context("expected object")?
            .iter()
            .map(|(k, x)| match op {
                "items" => json!([k, x]),
                "values" => x.clone(),
                _ => json!(k),
            })
            .collect(),
    ))
}
pub(super) fn fromkeys(v: &Value) -> Result<Value> {
    let mut result = json!({});
    for x in sequence(v)? {
        result[text(&x)] = Value::Null;
    }
    Ok(result)
}
pub(super) fn path_part(v: &Value, part: &str) -> Value {
    let p = to_path(v);
    match part {
        "parent" => json!(crate::io::parent(&p)),
        "stem" => json!(p.file_stem().unwrap_or_default().to_string_lossy()),
        _ => json!(p.file_name().unwrap_or_default().to_string_lossy()),
    }
}
pub(super) fn arithmetic(a: &Value, b: &Value, op: &str) -> Result<Value> {
    if op == "+" && a.is_string() && b.is_string() {
        return Ok(json!(text(a) + &text(b)));
    }
    if op == "+" && a.is_array() && b.is_array() {
        let mut x = sequence(a)?;
        x.extend(sequence(b)?);
        return Ok(json!(x));
    }
    if matches!(op, "&" | "|" | "-") && a.is_array() && b.is_array() {
        return Ok(match op {
            "&" => unique(
                sequence(a)?
                    .into_iter()
                    .filter(|v| contains(b, v))
                    .collect(),
            ),
            "-" => unique(
                sequence(a)?
                    .into_iter()
                    .filter(|v| !contains(b, v))
                    .collect(),
            ),
            _ => unique([sequence(a)?, sequence(b)?].concat()),
        });
    }
    if a.is_i64() && b.is_i64() && op != "/" {
        let (x, y) = (integer(a)?, integer(b)?);
        let res = match op {
            "+" => x.checked_add(y),
            "-" => x.checked_sub(y),
            "*" => x.checked_mul(y),
            "//" => x.checked_div(y),
            "%" => x.checked_rem(y),
            _ => None,
        };
        if let Some(n) = res {
            return Ok(json!(n));
        }
    }
    let (x, y) = (number(a)?, number(b)?);
    let n = match op {
        "+" => x + y,
        "-" => x - y,
        "*" => x * y,
        "/" => x / y,
        "//" => (x / y).floor(),
        "%" => x % y,
        _ => bail!("unknown arithmetic operation {op}"),
    };
    ensure!(n.is_finite(), "nonfinite arithmetic result");
    Ok(json!(n))
}
pub(super) fn builtin(name: &str, args: &[Value]) -> Result<Value> {
    let a = args.first().unwrap_or(&Value::Null);
    Ok(match name {
        "str" => json!(text(a)),
        "bool" => json!(truth(a)),
        "int" => json!(integer(a)?),
        "float" => json!(number(a)?),
        "len" => json!(match a {
            Value::Object(o) => o.len(),
            Value::Array(a) => a.len(),
            Value::String(s) => s.chars().count(),
            _ => bail!("expected collection"),
        }),
        "dict" => {
            if a.is_object() {
                a.clone()
            } else {
                let mut obj = json!({});
                for row in sequence(a)? {
                    let parts = sequence(&row)?;
                    ensure!(parts.len() == 2, "expected key and value");
                    obj[text(&parts[0])] = parts[1].clone()
                }
                obj
            }
        }
        "list" | "tuple" | "iter" => {
            if args.is_empty() {
                json!([])
            } else {
                json!(sequence(a)?)
            }
        }
        "set" => {
            if args.is_empty() {
                json!([])
            } else {
                unique(sequence(a)?)
            }
        }
        "all" => json!(sequence(a)?.iter().all(truth)),
        "any" => json!(sequence(a)?.iter().any(truth)),
        "sum" => {
            let mut v = json!(0);
            for x in sequence(a)? {
                v = arithmetic(&v, &x, "+")?;
            }
            v
        }
        "min" | "max" => {
            let values = if args.len() == 1 {
                sequence(a)?
            } else {
                args.to_vec()
            };
            let mut itr = values.into_iter();
            let mut v = itr.next().context("empty extrema")?;
            for x in itr {
                let ord = compare(&x, &v);
                if (name == "min" && ord.is_lt()) || (name == "max" && ord.is_gt()) {
                    v = x;
                }
            }
            v
        }
        "next" => sequence(a)?
            .into_iter()
            .next()
            .or_else(|| args.get(1).cloned())
            .context("empty iterator")?,
        "range" => {
            let end = integer(a)?;
            json!((0..end).collect::<Vec<_>>())
        }
        "enumerate" => {
            let first = args.get(1).map(integer).transpose()?.unwrap_or(0);
            json!(
                sequence(a)?
                    .into_iter()
                    .enumerate()
                    .map(|(i, v)| json!([first + i as i64, v]))
                    .collect::<Vec<_>>()
            )
        }
        "Path" => a.clone(),
        "round" => {
            let n = number(a)?;
            let digits = args
                .get(1)
                .map(integer)
                .transpose()?
                .unwrap_or(0)
                .clamp(0, 18) as usize;
            let rounded = format!("{n:.digits$}").parse::<f64>()?;
            if args.len() == 1 || a.is_i64() {
                json!(rounded as i64)
            } else {
                json!(rounded)
            }
        }
        _ => bail!("unknown operation {name}"),
    })
}
pub(super) fn unary_method(v: &Value, op: &str, arg: &Value) -> Result<Value> {
    let s = text(v);
    Ok(match op {
        "lower" => json!(s.to_lowercase()),
        "upper" => json!(s.to_uppercase()),
        "strip" | "rstrip" => {
            let set = arg.as_str();
            let matched =
                |c: char| set.map_or_else(|| c.is_whitespace(), |chars| chars.contains(c));
            json!(if op == "strip" {
                s.trim_matches(matched)
            } else {
                s.trim_end_matches(matched)
            })
        }
        "splitlines" => json!(s.lines().collect::<Vec<_>>()),
        "isdigit" => json!(!s.is_empty() && s.chars().all(|c| c.is_ascii_digit())),
        "bit_length" => json!(64 - integer(v)?.unsigned_abs().leading_zeros()),
        "date" | "isoformat" => v.clone(),
        _ => bail!("unknown method {op}"),
    })
}
pub(super) fn method(v: &Value, op: &str, a: &Value, b: &Value) -> Result<Value> {
    let s = text(v);
    let arg = text(a);
    Ok(match op {
        "startswith" | "endswith" => {
            let patterns = if a.is_array() { strings(a)? } else { vec![arg] };
            json!(patterns.iter().any(|p| if op == "startswith" {
                s.starts_with(p)
            } else {
                s.ends_with(p)
            }))
        }
        "split" => {
            if a.is_null() {
                json!(s.split_whitespace().collect::<Vec<_>>())
            } else if b.is_null() {
                json!(s.split(&arg).collect::<Vec<_>>())
            } else {
                json!(s.splitn(integer(b)? as usize + 1, &arg).collect::<Vec<_>>())
            }
        }
        "removeprefix" => json!(s.strip_prefix(&arg).unwrap_or(&s)),
        "removesuffix" => json!(s.strip_suffix(&arg).unwrap_or(&s)),
        "replace" => json!(s.replace(&arg, &text(b))),
        "count" => {
            if v.is_array() {
                json!(sequence(v)?.iter().filter(|x| equal(x, a)).count())
            } else {
                json!(s.matches(&arg).count())
            }
        }
        "issubset" => json!(sequence(v)?.iter().all(|x| contains(a, x))),
        "intersection" => unique(
            sequence(v)?
                .into_iter()
                .filter(|x| contains(a, x))
                .collect(),
        ),
        "glob" => {
            let mut paths = Vec::new();
            let base = to_path(v);
            if base.is_dir() {
                let pattern = regex::Regex::new(&format!(
                    "^{}$",
                    regex::escape(&arg).replace("\\*", "[^/]*")
                ))?;
                let depth = arg.split('/').count();
                for entry in walkdir::WalkDir::new(&base)
                    .min_depth(depth)
                    .max_depth(depth)
                {
                    let p = entry?.into_path();
                    let rel = p.strip_prefix(&base)?.to_string_lossy().replace('\\', "/");
                    if pattern.is_match(&rel) {
                        paths.push(p);
                    }
                }
            }
            json!(paths)
        }
        "group" => indexed(v, a)?,
        "match" | "search" => captures(&s, &arg, op == "match")?,
        _ => bail!("unknown method {op}"),
    })
}
pub(super) fn regex_findall(pattern: &Value, input: &Value) -> Result<Value> {
    let regex = regex::Regex::new(&text(pattern))?;
    let s = text(input);
    Ok(json!(
        regex
            .captures_iter(&s)
            .map(|m| if m.len() > 2 {
                json!(
                    m.iter()
                        .skip(1)
                        .map(|s| s.map_or("", |v| v.as_str()))
                        .collect::<Vec<_>>()
                )
            } else {
                json!(
                    m.get(if m.len() == 2 { 1 } else { 0 })
                        .map_or("", |v| v.as_str())
                )
            })
            .collect::<Vec<_>>()
    ))
}
fn captures(pattern: &str, s: &str, anchored: bool) -> Result<Value> {
    let regex = regex::Regex::new(pattern)?;
    Ok(
        if let Some(m) = regex
            .captures(s)
            .filter(|m| !anchored || m.get(0).unwrap().start() == 0)
        {
            json!(m.iter().map(|v| v.map(|v| v.as_str())).collect::<Vec<_>>())
        } else {
            Value::Null
        },
    )
}
pub(super) fn special(name: &str, args: &[Value]) -> Result<Value> {
    match name {
        "uuid.uuid5" => Ok(json!(
            uuid::Uuid::new_v5(&uuid::Uuid::NAMESPACE_URL, text(&args[1]).as_bytes())
                .simple()
                .to_string()
        )),
        "re.compile" => Ok(args[0].clone()),
        "re.search" => captures(&text(&args[0]), &text(&args[1]), false),
        _ => bail!("unknown conversion {name}"),
    }
}
pub(super) fn read_expansion_input(path: &Value) -> Result<Value> {
    let path = to_path(path);
    let input = std::fs::read_to_string(&path)?;
    serde_json::from_str(&input).map_err(|error| {
        super::failure(
            2,
            format!(
                "HATE-E-EXPANSION: malformed JSON fixture: {}: {error}",
                path.display()
            ),
        )
    })
}

pub(super) fn write_artifact(path: &Value, data: &Value) -> Result<Value> {
    crate::io::write_json(&to_path(path), data)?;
    Ok(Value::Null)
}
pub(super) fn read_artifact(path: &Value, prefix: &str) -> Result<Value> {
    super::super::read_artifact(&to_path(path), prefix)
}
pub(super) fn json_spaced(v: &Value) -> String {
    match v {
        Value::Array(a) => format!(
            "[{}]",
            a.iter().map(json_spaced).collect::<Vec<_>>().join(", ")
        ),
        Value::Object(o) => format!(
            "{{{}}}",
            o.iter()
                .map(|(k, v)| format!("{}: {}", json!(k), json_spaced(v)))
                .collect::<Vec<_>>()
                .join(", ")
        ),
        _ => v.to_string(),
    }
}
pub(super) fn window_days(v: &Value) -> i64 {
    fn date(s: &str) -> Option<i64> {
        DateTime::parse_from_rfc3339(s)
            .ok()
            .map(|d| d.timestamp())
            .or_else(|| {
                NaiveDate::parse_from_str(s, "%Y-%m-%d")
                    .ok()?
                    .and_hms_opt(0, 0, 0)
                    .map(|d| d.and_utc().timestamp())
            })
    }
    date(v["end_date"].as_str().unwrap_or(""))
        .zip(date(v["start_date"].as_str().unwrap_or("")))
        .map_or(0, |(e, s)| ((e - s) / 86400).max(0))
}
