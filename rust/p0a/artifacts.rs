use super::{Run, name, opt_object, s, slug};
use crate::io::file_digest;
use anyhow::{Context, Result, ensure};
use regex::Regex;
use serde_json::{Value, json};
use std::{fs, path::Path, sync::LazyLock};
use walkdir::WalkDir;

static SECRET: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r#"AKIA[0-9A-Z]{16}|(?i:(?:api[_-]?key|token|secret)\s*[:=]\s*['"]?[A-Za-z0-9_\-]{16,})|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"#).unwrap()
});

pub fn build(run: &Run, root: &Path, prefix: Option<&str>) -> Result<(Value, Value)> {
    let mut artifacts = Vec::new();
    let dir = root.join("artifacts");
    if dir.try_exists()? {
        let mut paths = Vec::new();
        for e in WalkDir::new(&dir) {
            let p = e?.into_path();
            if p.is_file() {
                paths.push(p);
            }
        }
        paths.sort_by_cached_key(|p| {
            p.components()
                .map(|s| {
                    if cfg!(windows) {
                        s.as_os_str().to_string_lossy().to_lowercase()
                    } else {
                        s.as_os_str().to_string_lossy().into_owned()
                    }
                })
                .collect::<Vec<_>>()
        });
        for path in paths {
            let rel = path
                .strip_prefix(&dir)?
                .to_string_lossy()
                .replace('\\', "/");
            let output = prefix
                .filter(|s| !s.is_empty())
                .map(|p| prefixed(p, format!("artifacts/{rel}")))
                .unwrap_or_else(|| rel.clone());
            artifacts.push(artifact(&path, &rel, &output, &json!({}), false)?);
        }
    }
    let references = opt_object(&root.join("artifact-refs.json"))?;
    if let Some(list) = references.get("artifacts") {
        for reference in list
            .as_array()
            .context("artifact-refs.json artifacts must be a list")?
        {
            ensure!(
                reference.is_object(),
                "artifact-refs.json artifact entries must be objects"
            );
            let raw = reference["path"]
                .as_str()
                .filter(|v| !v.is_empty())
                .context("artifact-refs.json artifact path is required")?;
            let normalized = raw.replace('\\', "/");
            let external = external(&normalized);
            let kind = if external {
                Some("external-url")
            } else if traversal(&normalized) {
                Some("path-traversal")
            } else if reference["symlink"] == true {
                Some("symlink")
            } else {
                None
            };
            let mut output = if let Some(kind) = kind {
                let fallback = if external {
                    "artifact"
                } else {
                    Path::new(&normalized)
                        .file_stem()
                        .and_then(|s| s.to_str())
                        .unwrap_or("artifact")
                };
                format!(
                    "redacted/{kind}/{}",
                    slug(
                        reference["artifact_id"]
                            .as_str()
                            .filter(|s| !s.is_empty())
                            .unwrap_or(fallback)
                    )
                )
            } else {
                normalized
            };
            if let Some(p) = prefix.filter(|s| !s.is_empty()) {
                output = prefixed(p, output);
            }
            let path = if external {
                root.join("__external_url__")
            } else {
                root.join(raw)
            };
            artifacts.push(artifact(&path, raw, &output, reference, true)?);
        }
    }
    let mut quarantined = Vec::new();
    for a in &artifacts {
        let checks = &a["security_checks"];
        let mut reasons = Vec::new();
        for (check, reason) in [
            ("path_exists", "missing"),
            ("secret_scan", "secret"),
            ("archive_scan", "unsafe_archive"),
            ("path_traversal_scan", "path_traversal"),
            ("symlink_scan", "symlink"),
            ("external_url_scan", "external_url"),
        ] {
            if checks[check] == "fail" {
                reasons.push(reason);
            }
        }
        if matches!(s(&a["classification"]), "secret" | "pii" | "restricted") {
            reasons.push("restricted_classification");
        }
        if a["safe_for_summary"] == false && reasons.is_empty() {
            reasons.push("unsafe_for_summary");
        }
        if !reasons.is_empty() {
            quarantined.push(json!({"artifact_id":a["artifact_id"],"kind":a["kind"],"path":a["path"],"reasons":reasons,"safe_for_summary":false,"public_exposure":"none"}));
        }
    }
    let mut manifest = run.base();
    manifest["artifacts"] = json!(artifacts);
    let mut quarantine = run.base();
    quarantine["source_tool"] = json!("harness-auto-test-evidence");
    quarantine["source_version"] = json!(run.version);
    quarantine["quarantined_artifacts"] = json!(quarantined);
    Ok((manifest, quarantine))
}
fn prefixed(prefix: &str, path: String) -> String {
    let prefix = prefix.trim_matches('/');
    if prefix.is_empty() {
        path
    } else {
        format!("{prefix}/{path}")
    }
}
fn external(raw: &str) -> bool {
    let s = raw.to_ascii_lowercase();
    s.starts_with("https://") || s.starts_with("http://")
}
fn traversal(raw: &str) -> bool {
    !external(raw)
        && (raw.starts_with('/')
            || raw.starts_with("..")
            || raw.contains("../")
            || raw.split('/').any(|p| p == "..")
            || (raw.as_bytes().first().is_some_and(u8::is_ascii_alphabetic)
                && raw.get(1..3) == Some(":/")))
}
fn check(failed: bool) -> &'static str {
    if failed { "fail" } else { "pass" }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn explicit_references_resolve_before_hashing() -> Result<()> {
        let workspace = tempfile::tempdir()?;
        let root = workspace.path().join("input");
        fs::create_dir_all(root.join("nested"))?;
        fs::write(root.join("evidence.txt"), "inside")?;
        fs::write(workspace.path().join("outside.txt"), "outside")?;
        let root = crate::io::resolve(&root)?;
        let absolute = root.join("evidence.txt").to_string_lossy().into_owned();
        for reference in ["evidence.txt", &absolute, "nested/../evidence.txt"] {
            let data = artifact(
                &root.join(reference),
                reference,
                "redacted",
                &json!({}),
                true,
            )?;
            assert_eq!(data["size_bytes"], 6);
            assert_eq!(data["security_checks"]["path_exists"], "pass");
            assert_eq!(
                data["security_checks"]["path_traversal_scan"],
                if reference.contains("..") {
                    "fail"
                } else {
                    "pass"
                }
            );
        }
        let reference = "../outside.txt";
        let data = artifact(
            &root.join(reference),
            reference,
            "redacted",
            &json!({}),
            true,
        )?;
        assert_eq!(data["security_checks"]["path_exists"], "pass");
        assert_eq!(data["security_checks"]["path_traversal_scan"], "fail");
        assert_eq!(data["size_bytes"], 7);
        assert_eq!(data["safe_for_summary"], false);
        Ok(())
    }

    #[cfg(unix)]
    #[test]
    fn symlink_hashes_its_target_and_is_quarantined() -> Result<()> {
        let workspace = tempfile::tempdir()?;
        let target = workspace.path().join("source.txt");
        let link = workspace.path().join("alias.txt");
        fs::write(&target, "payload")?;
        std::os::unix::fs::symlink(&target, &link)?;
        let data = artifact(&link, "alias.txt", "alias.txt", &json!({}), true)?;
        assert_eq!(
            data["sha256"],
            format!("sha256:{}", hex::encode(file_digest(&target)?))
        );
        assert_eq!(data["size_bytes"], 7);
        assert_eq!(data["security_checks"]["path_exists"], "pass");
        assert_eq!(data["security_checks"]["symlink_scan"], "fail");
        assert_eq!(data["security_checks"]["path_traversal_scan"], "fail");
        assert_eq!(data["public_exposure"], "none");
        fs::remove_file(&target)?;
        let missing = artifact(&link, "alias.txt", "alias.txt", &json!({}), true)?;
        assert_eq!(missing["size_bytes"], 0);
        assert_eq!(missing["security_checks"]["path_exists"], "fail");
        Ok(())
    }
}

fn artifact(
    path: &Path,
    rel: &str,
    output: &str,
    reference: &Value,
    is_ref: bool,
) -> Result<Value> {
    let raw = rel.replace('\\', "/");
    let external = external(&raw);
    let traversal = traversal(&raw);
    let symlink = path.is_symlink();
    let declared_link = reference["symlink"] == true;
    let archive = name(Path::new(&raw))
        .trim_start_matches('.')
        .split('.')
        .skip(1)
        .any(|s| {
            matches!(
                s.to_ascii_lowercase().as_str(),
                "zip" | "tar" | "gz" | "7z" | "tgz"
            )
        });
    let exists = !external && path.is_file();
    let checks = if exists {
        let bytes = if fs::metadata(path)?.len() <= 1024 * 1024 {
            fs::read(path).unwrap_or_default()
        } else {
            Vec::new()
        };
        let text = bytes
            .utf8_chunks()
            .map(|chunk| chunk.valid())
            .collect::<String>();
        let ext = path
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_ascii_lowercase();
        let known = mime_guess::from_path(path).first().is_some()
            || matches!(
                ext.as_str(),
                "txt" | "trace" | "sarif" | "json" | "xml" | "info"
            );
        json!({"path_exists":"pass","secret_scan":check(SECRET.is_match(&text)),"pii_scan":"not_run","mime_extension_scan":if known{"pass"}else{"unknown"},
            "archive_scan":if archive{"fail"}else{"not_applicable"},"path_traversal_scan":check(symlink||Path::new(rel).components().any(|p| p == std::path::Component::ParentDir)),"symlink_scan":check(symlink||declared_link),
            "external_url_scan":check(text.contains("http://")||text.contains("https://"))})
    } else {
        json!({"path_exists":if external||traversal{"blocked"}else{"fail"},"secret_scan":"not_run","pii_scan":"not_run","mime_extension_scan":"not_run",
        "archive_scan":if archive{"fail"}else{"not_applicable"},"path_traversal_scan":check(traversal),"symlink_scan":if declared_link{"fail"}else{"not_run"},"external_url_scan":check(external)})
    };
    let failed = checks.as_object().unwrap().values().any(|v| v == "fail");
    let stem = Path::new(&raw)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("");
    let id = reference["artifact_id"]
        .as_str()
        .filter(|s| !s.is_empty())
        .map(str::to_owned)
        .unwrap_or_else(|| format!("artifact-{}", slug(stem)));
    let ext = path
        .extension()
        .and_then(|s| s.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    let fallback =
        if name(path).to_lowercase().contains("trace") || matches!(ext.as_str(), "zip" | "trace") {
            "trace"
        } else {
            match ext.as_str() {
                "html" | "md" => "report",
                "png" | "jpg" | "jpeg" => "screenshot",
                "webm" | "mp4" => "video",
                _ => "other",
            }
        };
    let hash = if exists {
        hex::encode(file_digest(path)?)
    } else {
        "0".repeat(64)
    };
    let size = if exists { fs::metadata(path)?.len() } else { 0 };
    Ok(
        json!({"artifact_id":id,"kind":reference["kind"].as_str().filter(|s|!s.is_empty()).unwrap_or(fallback),"path":output,
        "sha256":format!("sha256:{hash}"),"size_bytes":size,"classification":reference["classification"].as_str().filter(|s|!s.is_empty()).unwrap_or("public"),
        "redaction_status":"not_required","redaction_rule_version":"none","safe_for_summary":!failed && (!is_ref || reference["safe_for_summary"].as_bool().unwrap_or(exists)),
        "public_exposure":if failed{"none"}else{reference["public_exposure"].as_str().filter(|s|!s.is_empty()).unwrap_or("summary")},"retention":{"policy":"fixture","delete_after_days":null},"security_checks":checks}),
    )
}
