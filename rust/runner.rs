use regex::Regex;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;

fn re(pattern: &str) -> Regex {
    Regex::new(pattern).expect("valid runner pattern")
}
type Counts = BTreeMap<String, u64>;
fn count(counts: &mut Counts, label: &str, n: &str) {
    let key = match label.to_ascii_lowercase().as_str() {
        "pass" | "passing" => "passed",
        "fail" | "failing" => "failed",
        "skip" | "pending" | "ignored" | "filtered out" => "skipped",
        "error" => "errors",
        _ => label,
    };
    *counts.entry(key.to_ascii_lowercase()).or_default() += n.parse::<u64>().unwrap_or(0);
}
fn summary(mut counts: Counts) -> Value {
    counts.retain(|_, v| *v != 0);
    json!(counts)
}

fn test_counts(text: &str) -> Option<(&'static str, Value)> {
    let outcomes = re(r"(?i)(\d+)\s+(passed|failed|skipped|errors?)");
    let test_header = re(r"^\s*Tests\b");
    for line in text.lines().filter(|line| test_header.is_match(line)) {
        let mut c = Counts::new();
        for cap in outcomes.captures_iter(line) {
            count(&mut c, &cap[2], &cap[1]);
        }
        let total = re(r"\((\d+)\)")
            .captures(line)
            .and_then(|v| v[1].parse().ok())
            .unwrap_or_else(|| c.values().sum());
        if total > 0 {
            c.insert("total_tests".into(), total);
            return Some(("vitest", summary(c)));
        }
    }
    let mut c = Counts::new();
    let bun = re(r"(?i)^(\d+)\s+(pass|fail|skip|error)s?$");
    let ran = re(r"(?i)Ran\s+(\d+)\s+tests?\s+across\b");
    for line in text.lines() {
        if let Some(cap) = bun.captures(line.trim()) {
            count(&mut c, &cap[2], &cap[1]);
        } else if let Some(cap) = ran.captures(line)
            && cap[1].parse::<u64>().unwrap_or(0) > 0
        {
            count(&mut c, "total_tests", &cap[1]);
            return Some(("bun", summary(c)));
        }
    }
    let mut c = Counts::new();
    for cap in re(r"(?im)^\s*(\d+)\s+(passing|failing|pending)(?:\s|\()").captures_iter(text) {
        count(&mut c, &cap[2], &cap[1]);
    }
    let n = c.values().sum();
    if n > 0 {
        c.insert("total_tests".into(), n);
        return Some(("mocha", summary(c)));
    }
    let mut c = Counts::new();
    for cap in re(r"(?i)PASS:\s*(\d+)\s+FAIL:\s*(\d+)\s+TOTAL:\s*(\d+)").captures_iter(text) {
        for (i, k) in ["passed", "failed", "total_tests"].iter().enumerate() {
            count(&mut c, k, &cap[i + 1]);
        }
    }
    if c.values().any(|n| *n > 0) {
        return Some(("lodash-test", summary(c)));
    }
    let mut c = Counts::new();
    let cargo = re(r"(?i)(\d+)\s+(passed|failed|ignored|filtered out)");
    for line in text.lines().filter(|l| {
        l.trim_start()
            .to_ascii_lowercase()
            .starts_with("test result:")
    }) {
        for cap in cargo.captures_iter(line) {
            count(&mut c, &cap[2], &cap[1]);
        }
    }
    let n = c.values().sum();
    if n > 0 {
        c.insert("total_tests".into(), n);
        return Some(("cargo-test", summary(c)));
    }
    None
}
pub fn parse(stdout: &str, stderr: &str) -> Value {
    let text = format!("{stdout}\n{stderr}").replace("\\n", "\n");
    let ansi = re(r"\x1b\[[0-9;]*m");
    let plain = ansi.replace_all(&text, "");
    let lower = text.to_lowercase();
    let noise: Vec<_> = [
        "semantic_error",
        "handler emitted",
        "failed to fetch",
        "expected failure",
        "non-summary",
    ]
    .into_iter()
    .filter(|s| lower.contains(s))
    .collect();
    let mut status = "parsed";
    let (dialect, counts) = if let Some(result) = test_counts(&plain) {
        result
    } else if (plain.contains("next build") || plain.contains("Next.js"))
        && plain.contains("Compiled successfully")
    {
        let mut v = json!({"build_passed":1,"total_checks":1});
        if plain.contains("checking validity of types") {
            v["typecheck_passed"] = json!(1);
        }
        if let Some(n) = re(r"Generating static pages\s+\((\d+)/(\d+)\)")
            .captures(&plain)
            .and_then(|v| v[2].parse::<u64>().ok())
            .filter(|n| *n != 0)
        {
            v["static_pages"] = json!(n);
        }
        ("nextjs-build", v)
    } else if plain.contains("[build] Complete!") {
        let pages = re(r"\[build\]\s+(\d+)\s+page\(s\)\s+built")
            .captures(&plain)
            .and_then(|v| v[1].parse::<u64>().ok())
            .unwrap_or(0);
        (
            "astro-build",
            json!({"build_passed":1,"static_pages":pages,"total_checks":1}),
        )
    } else if plain.contains("tsc --noEmit") && !re(r"\berror TS\d+:").is_match(&plain) {
        (
            "typescript-typecheck",
            json!({"typecheck_passed":1,"total_checks":1}),
        )
    } else if let n = re(r"(?m)^(?:Listing|Compiling)\s+'[^']+'\.\.\.")
        .find_iter(&plain)
        .count()
        && n > 0
    {
        (
            "python-compileall",
            json!({"compiled_paths":n,"total_checks":1}),
        )
    } else {
        let mut c = Counts::new();
        let outcomes = re(r"(?i)(\d+)\s+(passed|failed|skipped|xfailed|xpassed|errors?)");
        let elapsed = re(r"(?i)\bin\s+\d+(\.\d+)?s\b");
        for line in text.lines() {
            let l = line.trim_matches(['=', ' ', '\t', '\r', '\n']);
            if !l.to_lowercase().contains("test files")
                && (elapsed.is_match(l)
                    || l.contains(',')
                    || l.contains(" passed")
                    || l.contains(" failed"))
            {
                for cap in outcomes.captures_iter(l) {
                    count(&mut c, &cap[2], &cap[1]);
                }
            }
        }
        let n = c.values().sum();
        if n > 0 {
            c.insert("total_tests".into(), n);
            ("pytest", summary(c))
        } else if let Some(percent) = re(r"\[\s*(\d{1,3})%\]")
            .captures_iter(&plain)
            .filter_map(|v| v[1].parse::<u32>().ok().filter(|n| *n <= 100))
            .max()
        {
            status = "partial";
            (
                "pytest",
                json!({"partial_progress_percent":percent,"partial_progress_observed":1}),
            )
        } else {
            status = "unparsed";
            ("unknown", json!({}))
        }
    };
    json!({"dialect":dialect,"summary":counts,"ignored_noise":noise,"parser_status":status})
}

pub fn safe_output(stdout: &str, stderr: &str) -> Value {
    let raw = format!("{stdout}\n{stderr}");
    let raw = raw.trim();
    let ansi = re(r"\x1b\[[0-9;?]*[ -/]*[@-~]");
    let control = re(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]");
    let clean = raw.replace("\r\n", "\n").replace('\r', "\n");
    let mut s = control
        .replace_all(&ansi.replace_all(&clean, ""), "")
        .into_owned();
    let mut redactions = Vec::new();
    let mut replace = |pattern: Regex, kind: &str, preserve_prefix: bool| {
        let marker = format!("[REDACTED_{}]", kind.to_uppercase());
        let n = pattern.find_iter(&s).count();
        if n == 0 {
            return;
        }
        s = pattern
            .replace_all(&s, |cap: &regex::Captures| {
                format!(
                    "{}{}",
                    if preserve_prefix {
                        cap.get(1).map_or("", |m| m.as_str())
                    } else {
                        ""
                    },
                    marker
                )
            })
            .into_owned();
        redactions.push(json!({"kind":kind,"count":n,"marker":marker}));
    };
    for pat in [
        r#"(?i)(?:api[_-]?key|access[_-]?key|secret[_-]?key|token|password)\s*[:=]\s*['"]?([A-Za-z0-9_\-./+=]{16,})['"]?"#,
        r#"(?i)(?:api[_-]?key|access[_-]?key|secret[_-]?key|token|password)=[^\s"']{12,}"#,
        r"\bAKIA[0-9A-Z]{16}\b",
        r"gh[pousr]_[A-Za-z0-9_]{20,}",
    ] {
        replace(re(pat), "secret", false);
    }
    replace(
        re(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "pii",
        false,
    );
    replace(
        re(r"\b[A-Za-z]:\\(?:[^\\\r\n\t ]+\\)*[^\\\r\n\t ]+"),
        "path",
        false,
    );
    replace(
        re(r#"(^|[^\w:/.\-])/(?:Users|home|tmp|var|private|mnt|workspace)/[^\s"']+"#),
        "path",
        true,
    );
    for dir in [std::env::home_dir(), std::env::current_dir().ok()]
        .into_iter()
        .flatten()
    {
        replace(
            re(&format!(
                r#"{}[^\s"']*"#,
                regex::escape(&dir.to_string_lossy())
            )),
            "path",
            false,
        );
    }
    let truncated = s.chars().count() > 2000;
    if truncated {
        let marker = "\n...[truncated:real-repo-output-safety/v1]";
        s = s.chars().take(2000 - marker.len()).collect::<String>() + marker;
    }
    json!({"excerpt":s,"metadata":{"redaction_status":if redactions.is_empty(){"not_required"}else{"redacted"},"redaction_rule_version":"real-repo-output-safety/v1",
      "redactions":redactions,"redaction_count":redactions.len(),"line_endings_normalized":raw.contains('\r'),"control_characters_removed":control.is_match(raw),
      "ansi_removed":ansi.is_match(raw),"truncated":truncated,"limit":2000,"raw_output_sha256":hex::encode(Sha256::digest(raw.as_bytes())),
      "raw_access":if redactions.is_empty(){"not_required"}else{"quarantined_required"},"safe_for_read_model":true}})
}
