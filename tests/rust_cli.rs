use serde_json::Value;
use std::{
    fs,
    path::Path,
    process::{Command, Output},
};

fn native(args: &[&str], cwd: &Path) -> Output {
    Command::new(env!("CARGO_BIN_EXE_hate"))
        .current_dir(cwd)
        .env("PATH", "")
        .env_remove("HATE_BRIDGE_PROVIDER")
        .args(args)
        .output()
        .expect("launch native CLI")
}

#[test]
fn all_public_commands_display_help_without_python() {
    fn visit(node: &Value, path: &mut Vec<String>, count: &mut usize) {
        if let Some(children) = node["children"].as_array() {
            for child in children {
                path.push(child["name"].as_str().unwrap().to_owned());
                visit(child, path, count);
                path.pop();
            }
            return;
        }
        let mut args: Vec<_> = path.iter().map(String::as_str).collect();
        args.push("--help");
        let result = native(&args, Path::new("."));
        assert!(result.status.success(), "{args:?}");
        let help = String::from_utf8(result.stdout).unwrap();
        assert!(help.contains(&path.join(" ")));
        for arg in node["args"].as_array().into_iter().flatten() {
            let flag = arg["flags"][0].as_str().unwrap();
            assert!(help.contains(&format!("--{flag}")), "{args:?} lacks {flag}");
        }
        *count += 1;
    }
    let mut count = 0;
    visit(
        &serde_json::from_str(include_str!("../rust/commands.json")).unwrap(),
        &mut Vec::new(),
        &mut count,
    );
    assert_eq!(count, 45);
}

#[test]
fn p0a_produces_evidence_from_a_standalone_binary() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let input = root.join("fixtures/golden/p0a-minimal/input");
    let temp = tempfile::tempdir().unwrap();
    let result = native(
        &[
            "p0a",
            "--input",
            input.to_str().unwrap(),
            "--out",
            "results",
            "--source-version",
            "0.1.0",
        ],
        temp.path(),
    );
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    let out = temp.path().join("results");
    for (name, hash) in [
        (
            "HATE-run.json",
            "sha256:be258e0edf8fe38f7e2797e1aa2646628d939a7fa8b007dcef27aa0353880c7a",
        ),
        (
            "precheck-decision.json",
            "sha256:97c8db766468cd9dc027d6479e1f763024042f1777199a5471bc15ca8736ceaf",
        ),
    ] {
        let read = |path| serde_json::from_slice::<Value>(&fs::read(path).unwrap()).unwrap();
        let actual = read(out.join(name));
        let expected = read(root.join("fixtures/golden/p0a-minimal/expected").join(name));
        assert_eq!(actual["run_id"], expected["run_id"]);
        assert_eq!(actual["commit_sha"], expected["commit_sha"]);
        assert_eq!(actual["sha256"], hash);
    }
    assert!(
        !fs::read(out.join("HATE-test-results.ndjson"))
            .unwrap()
            .is_empty()
    );
}

#[test]
fn missing_required_argument_is_a_usage_error() {
    let temp = tempfile::tempdir().unwrap();
    let result = native(&["p0a", "--out", "results"], temp.path());
    assert_eq!(result.status.code(), Some(2));
    assert!(!temp.path().join("results").exists());
}
