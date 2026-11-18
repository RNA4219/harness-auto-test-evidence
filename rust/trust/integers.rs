use bigdecimal::{FromPrimitive, num_bigint::BigInt};
use serde_json::{Number, Value};

// Coordinates have already passed exact decimal validation in the input reader.
pub(super) fn integer(value: &Value) -> Option<BigInt> {
    value.as_number()?.as_str().parse().ok()
}

pub(crate) fn coerced_integer(value: &Value) -> Option<BigInt> {
    match value {
        Value::String(text) => text.trim().parse().ok(),
        Value::Bool(flag) => Some(BigInt::from(u8::from(*flag))),
        Value::Number(n) if n.is_f64() => BigInt::from_f64(n.as_f64()?),
        _ => integer(value),
    }
}

pub(crate) fn json_integer(integer: &BigInt) -> Value {
    let number = integer
        .to_string()
        .parse::<Number>()
        .expect("BigInt formats as a valid JSON integer");
    Value::Number(number)
}
