use anyhow::{Context, Result, bail, ensure};
use bigdecimal::{BigDecimal, RoundingMode, ToPrimitive, Zero};
use serde::{
    Deserialize, Deserializer,
    de::{MapAccess, Visitor},
};
use serde_json::{Value, json, value::RawValue};
use sha2::{Digest, Sha256};
use std::{collections::HashMap, fmt, fs, path::Path, str::FromStr};

struct Pairs(Vec<(String, Box<RawValue>)>);
impl<'de> Deserialize<'de> for Pairs {
    fn deserialize<D: Deserializer<'de>>(d: D) -> std::result::Result<Self, D::Error> {
        struct Entries;
        impl<'de> Visitor<'de> for Entries {
            type Value = Pairs;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                f.write_str("an object")
            }
            fn visit_map<A: MapAccess<'de>>(
                self,
                mut a: A,
            ) -> std::result::Result<Pairs, A::Error> {
                let mut pairs = Vec::new();
                while let Some(entry) = a.next_entry()? {
                    pairs.push(entry);
                }
                Ok(Pairs(pairs))
            }
        }
        d.deserialize_map(Entries)
    }
}

pub(crate) struct Document {
    pub value: Value,
    numbers: HashMap<String, String>,
    order: HashMap<String, Vec<String>>,
}
impl Document {
    pub fn read(path: &Path, unique: bool) -> Result<Self> {
        let data = fs::read_to_string(path)?;
        Self::from_text(&data, super::name(path), unique)
    }
    pub fn from_text(data: &str, root: &str, unique: bool) -> Result<Self> {
        let mut doc = Self {
            value: Value::Null,
            numbers: HashMap::new(),
            order: HashMap::new(),
        };
        let raw: Box<RawValue> = serde_json::from_str(data)?;
        doc.value = doc.parse(raw.get(), root, unique)?;
        Ok(doc)
    }
    fn parse(&mut self, raw: &str, loc: &str, unique: bool) -> Result<Value> {
        match raw.as_bytes().first() {
            Some(b'{') => {
                let pairs: Pairs = serde_json::from_str(raw)?;
                let mut value = json!({});
                let mut order = Vec::new();
                let mut latest = HashMap::new();
                for (key, item) in pairs.0 {
                    if latest.contains_key(&key) {
                        ensure!(!unique, "duplicate JSON object key: {key}");
                    } else {
                        order.push(key.clone());
                    }
                    latest.insert(key, item);
                }
                for key in &order {
                    value[key] = self.parse(latest[key].get(), &Self::field(loc, key), unique)?;
                }
                self.order.insert(loc.into(), order);
                Ok(value)
            }
            Some(b'[') => {
                let parts: Vec<Box<RawValue>> = serde_json::from_str(raw)?;
                let mut values = Vec::new();
                for (i, item) in parts.iter().enumerate() {
                    values.push(self.parse(item.get(), &format!("{loc}[{i}]"), unique)?);
                }
                Ok(Value::Array(values))
            }
            Some(b'-' | b'0'..=b'9') => {
                self.numbers.insert(loc.into(), raw.into());
                if raw.contains(['.', 'e', 'E']) {
                    let number = serde_json::Number::from_f64(raw.parse()?)
                        .context("JSON number exceeds the supported finite range")?;
                    Ok(Value::Number(number))
                } else if raw == "-0" {
                    Ok(json!(0))
                } else {
                    Ok(serde_json::from_str(raw)?)
                }
            }
            _ => Ok(serde_json::from_str(raw)?),
        }
    }
    pub fn token(&self, loc: &str) -> Option<&str> {
        self.numbers.get(loc).map(String::as_str)
    }
    pub fn field(parent: &str, key: &str) -> String {
        // An arbitrary JSON member may itself contain a dot or an array subscript.
        let key = key
            .replace('\\', "\\\\")
            .replace('.', "\\.")
            .replace('[', "\\[")
            .replace(']', "\\]");
        format!("{parent}.{key}")
    }
    pub fn keys(&self, loc: &str) -> &[String] {
        self.order.get(loc).map(Vec::as_slice).unwrap_or_default()
    }
}

pub fn stringify(v: &Value) -> String {
    match v {
        Value::Null => "None".into(),
        Value::Bool(true) => "True".into(),
        Value::Bool(false) => "False".into(),
        Value::String(s) => s.to_owned(),
        v => v.to_string(),
    }
}
fn encode(value: &Value, out: &mut String) {
    match value {
        Value::Array(v) => {
            out.push('[');
            for (i, item) in v.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                encode(item, out);
            }
            out.push(']');
        }
        Value::Object(v) => {
            out.push('{');
            let mut keys: Vec<_> = v.keys().collect();
            keys.sort();
            for (i, key) in keys.into_iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                out.push_str(&json!(key).to_string());
                out.push(':');
                encode(&v[key], out);
            }
            out.push('}');
        }
        Value::Number(n) if n.is_f64() => {
            let mut text = format!("{:?}", n.as_f64().unwrap());
            if let Some((base, exponent)) = text.split_once('e')
                && let Ok(e) = exponent.parse::<i32>()
            {
                text = format!("{base}e{e:+03}");
            }
            out.push_str(&text);
        }
        _ => out.push_str(&value.to_string()),
    }
}
pub(crate) fn canonical_json(v: &Value) -> String {
    let mut text = String::new();
    encode(v, &mut text);
    text
}
pub fn hash(v: &Value) -> String {
    hex::encode(Sha256::digest(canonical_json(v).as_bytes()))
}

#[cfg(test)]
mod document_tests {
    use super::*;

    #[test]
    fn literal_property_names_do_not_alias_nested_numeric_tokens() {
        let doc = Document::from_text(r#"{"tests":[{"duration":1.2,"duration":"old"}],"tests[0].duration":3.5,"source.rs":1e2}"#, "root", false).unwrap();
        assert_eq!(doc.token("root.tests[0].duration"), None);
        assert_eq!(
            doc.token(&Document::field("root", "tests[0].duration")),
            Some("3.5")
        );
        assert_eq!(
            doc.token(&Document::field("root", "source.rs")),
            Some("1e2")
        );
        assert!(
            Document::from_text(r#"{"context":{"attempt":1,"attempt":2}}"#, "root", true).is_err()
        );
    }

    #[test]
    fn large_integer_inputs_preserve_digits_and_normalize_decimal_tokens() {
        let expected: Value = serde_json::from_str("18446744073709551617").unwrap();
        for token in [
            "18446744073709551617",
            "18446744073709551617.000",
            "184467440737095516170e-1",
        ] {
            assert_eq!(exact_uint(token).unwrap(), expected);
        }
        assert!(exact_uint("18446744073709551617.1").is_err());
        let data = Document::from_text(
            r#"{"small":0.0000,"big":18446744073709551617}"#,
            "input",
            true,
        )
        .unwrap();
        assert_eq!(
            canonical_json(&data.value),
            r#"{"big":18446744073709551617,"small":0.0}"#
        );
        assert_eq!(data.token("input.small"), Some("0.0000"));
    }
}

pub(crate) fn exact_uint(text: &str) -> Result<Value> {
    ensure!(
        !text.is_empty()
            && text
                .bytes()
                .all(|c| c.is_ascii_digit() || b"+-.eE".contains(&c)),
        "invalid numeric token"
    );
    if !text.contains(['.', 'e', 'E']) {
        let digits = text.trim_start_matches(['-', '+']);
        ensure!(
            !digits.is_empty()
                && digits.bytes().all(|c| c.is_ascii_digit())
                && text.len() - digits.len() <= 1,
            "invalid integer"
        );
        let digits = digits.trim_start_matches('0');
        if digits.is_empty() {
            return Ok(json!(0));
        }
        ensure!(!text.starts_with('-'), "must be a non-negative integer");
        return Ok(serde_json::from_str(digits)?);
    }
    let approximate = text.parse::<f64>()?;
    ensure!(
        approximate.is_finite() && approximate >= 0.,
        "integer exceeds supported range"
    );
    let num = BigDecimal::from_str(text)?;
    if num.is_zero() {
        return Ok(json!(0));
    }
    ensure!(approximate >= 1., "must be an integer");
    ensure!(
        num.is_integer() && num >= BigDecimal::zero(),
        "must be a non-negative integer"
    );
    Ok(serde_json::from_str(&num.with_scale(0).to_plain_string())?)
}
pub fn run_attempt(value: &Value, token: Option<&str>) -> Result<Value> {
    let raw = if let Some(s) = value.as_str() {
        ensure!(
            !s.trim().is_empty() && s.trim().bytes().all(|c| c.is_ascii_digit()),
            "invalid decimal string"
        );
        s.trim()
    } else {
        token.context("expected a number")?
    };
    let n = exact_uint(raw)?;
    ensure!(n != json!(0), "must be a positive integer");
    Ok(n)
}
pub fn duration(raw: &str, loc: &str) -> Result<BigDecimal> {
    let invalid = || format!("{loc} must be a finite non-negative duration");
    let token = raw.trim();
    ensure!(
        !token.is_empty()
            && token
                .bytes()
                .all(|c| c.is_ascii_digit() || b"+-.eE".contains(&c)),
        "{}",
        invalid()
    );
    let value = BigDecimal::from_str(token).with_context(invalid)?;
    ensure!(value >= BigDecimal::zero(), "{}", invalid());
    let f = token.parse::<f64>().with_context(invalid)?;
    ensure!(
        f.is_finite() && (f != 0.0 || value.is_zero()),
        "{loc} exceeds the supported numeric range for duration"
    );
    Ok(value)
}
pub fn millis(value: BigDecimal, seconds: bool) -> Result<Value> {
    let scaled = if seconds {
        value * BigDecimal::from(1000)
    } else {
        value
    };
    let rounded = scaled.with_scale_round(0, RoundingMode::HalfEven);
    if let Some(i) = rounded.to_u64() {
        return Ok(json!(i));
    }
    serde_json::from_str(&rounded.to_plain_string())
        .or_else(|_| bail!("duration exceeds supported output range"))
}
