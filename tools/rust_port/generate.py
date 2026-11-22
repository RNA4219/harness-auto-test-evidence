"""固定の互換帳票を Rust に再生成する開発ツール。

リポジトリの開発環境で python tools/rust_port/generate.py を実行する。
生成した Rust と catalog.json を Cargo が直接ビルドする。更新後の互換性は
python tools/check_rust_downstream.py target/debug/hate で検証する。
"""

import ast
import collections
import importlib
import inspect
import json
import re
import subprocess
import sys

from inspect_rules import GROUPS, ident, resolve_name
from translate import Port, cache, dest, funcs, groups, is_ref, rs, slug, var

specials = {
    "scale__benchmark_catalog__escalate_fixture_budget_exceeded": 'if number(&input_data["duration_seconds"]).unwrap_or(0.0)>number(&input_data["budget_seconds"]).unwrap_or(0.0) && truth(&input_data["budget_seconds"]){if let Some(v)=report["findings"].as_array_mut().and_then(|a| a.iter_mut().find(|v|v["code"]=="performance_budget_exceeded")){v["readiness_effect"]=json!("hold");v["severity"]=json!("hold");}if report["readiness_effect"]!="hard_dq"{report["readiness_effect"]=json!("hold");}report["overall_status"]=json!("hold");}Ok(Value::Null)',
    "enterprise__audit__stable_hash": "Ok(json!(ascii_hash(&value)))",
    "tenant_isolation__hash_event": 'Ok(json!(format!("sha256:{}",ascii_hash(&event))))',
    "support_ops__diagnostics__proof_hash": "Ok(json!(ascii_hash(&values)))",
    "adapters__corpus_manifest__is_stale": "Ok(json!(stale(&family,&today)))",
    "adapters__family_packet__is_stale": "Ok(json!(stale(&packet,&today)))",
    "api__rate_limit__positive_int": "Ok(integer(&value).ok().filter(|n|*n>0).map_or(default,|n|json!(n)))",
    "api__rate_limit__non_negative_int": "Ok(integer(&value).map_or(default,|n|json!(n.max(0))))",
    "plugins__sandbox__stable_hash": 'Ok(json!(format!("sha256:{}",ascii_hash(&value))))',
    "policy_config__stable_hash": 'Ok(json!(format!("sha256:{}",ascii_hash(&value))))',
    "p1b__stable_ref": "Ok(json!(crate::io::stable_ref(&to_path(&path), true)?))",
    "p2p3_io__stable_ref": "Ok(json!(crate::io::stable_ref(&to_path(&path),true)?))",
    "p1b__read_json": 'read_artifact(&path, "HATE-E-WORKFLOW")',
    "p2p3_io__read_json": 'read_artifact(&path, "HATE-E-PRODUCT")',
    "p1b__write_jsonl": "let mut output=String::new();for record in sequence(&records)? {output.push_str(&json_spaced(&record));output.push('\\n');}std::fs::write(to_path(&path),output)?; Ok(Value::Null)",
    "p1b__write_json": "write_artifact(&path,&value)",
    "p2p3_io__write_json": "write_artifact(&path,&value)",
    "p2p3_io__stable_hash": 'Ok(json!(format!("sha256:{}",crate::io::digest(&value))))',
    "release__stable_hash": "Ok(json!(ascii_hash(&value)))",
    "p2p3_readiness__safe_int": "Ok(integer(&value).map_or(default,|n|json!(n)))",
    "p2p3_readiness__safe_float": "Ok(number(&value).map_or(default,|n|json!(n)))",
    "product_grade__write_json": "write_artifact(&path,&data)",
    "expansion_runner__write_json": "write_artifact(&path,&data)",
    "expansion_runner__load_json": "read_expansion_input(&path)",
    "analysis__historical_regression__calculate_window_days": "Ok(json!(window_days(&window)))",
    "expansion__adapter_marketplace__check_compatibility": "Ok(json!(compatibility_range.as_str().and_then(|s|s.strip_prefix(\">=\")).and_then(|s|s.split(',').next()).is_some_and(|min|host_version.as_str().is_some_and(|h|!h.is_empty()&&h>=min.trim()))))",
    "analysis__contradiction_detection__optional_float": "Ok(number(&value).map_or(Value::Null,|n|json!(n)))",
}


def emit_special(f, n, body):
    p = [a.arg for a in n.args.args + n.args.kwonlyargs] + ([n.args.vararg.arg] if n.args.vararg else [])
    return (
        "pub(super) fn "
        + ident(f)
        + "("
        + ",".join(var(v) + (": &mut Value" if is_ref(f, v) else ": Value") for v in p)
        + ")->Result<Value>{"
        + body
        + "}\n"
    )


class Custom(Port):
    def __init__(self, f, n):
        super().__init__(f, n)
        self.locals.update(x.name for x in ast.walk(n) if isinstance(x, ast.ExceptHandler) and x.name)

    def stmt(self, n):
        if isinstance(n, ast.Try):
            if self.f.__module__ == "hate.gap_closure":
                assignment = n.body[0]
                # Only decoding is caught here. Missing files retain normal I/O diagnostics.
                load = next(
                    a
                    for a in ast.walk(assignment.value)
                    if isinstance(a, ast.Call) and ast.unparse(a.func) == "json.loads"
                )
                target = load.args[0].func.value
                loaded = "crate::io::read_json(&to_path(&" + self.expr(target) + "))"
                then = self.stmts(n.body).replace(self.expr(load), "parsed.clone()")
                errname = n.handlers[0].name
                handler = (("let " + errname + "=json!(error.to_string());") if errname else "") + self.stmts(
                    n.handlers[0].body
                )
                return (
                    "match "
                    + loaded
                    + "{Ok(parsed)=>{"
                    + then
                    + "},Err(error) if error.chain().any(|c|c.is::<serde_json::Error>())=>{"
                    + handler
                    + "},Err(error)=>return Err(error)}"
                )
            if self.f.__name__ == "_assemble_release_candidate":
                return (
                    'match crate::io::read_json(&to_path(&report_path)) {Ok(report_data)=>edit(&mut reports,"append",report_data)?,Err(e) if e.chain().any(|c|c.is::<serde_json::Error>())=>{'
                    + self.stmts(n.handlers[0].body)
                    + "},Err(e)=>return Err(e)}"
                )
            if self.f.__name__ == "_metric_regressed":
                return "let Ok(parsed)=number(&baseline) else{return Ok(json!(false))};baseline_value=json!(parsed);"
        if self.f.__name__ == "_write_uat_reports" and isinstance(n, ast.For):
            if ast.unparse(n.target) == "report_name" and ast.unparse(n.iter) == "gap['uat_reports']":
                assign = n.body[0]
                args = assign.value.args
                body = self.forloop(
                    n.target,
                    n.iter,
                    "let mut uat=default_mut(&mut uat_reports,&"
                    + self.expr(args[0])
                    + ","
                    + self.expr(args[1])
                    + ")?.clone();"
                    + self.stmts(n.body[1:])
                    + "set_index(&mut uat_reports,&report_name,uat)?;",
                )
                return body
        return super().stmt(n)


failed = []
files = collections.defaultdict(list)
for f, n in sorted(funcs.items(), key=lambda x: ident(x[0])):
    key = ident(f)
    try:
        code = emit_special(f, n, specials[key]) if key in specials else Custom(f, n).emit()
    except Exception as ex:
        failed.append((key, str(ex)))
        continue
    code = re.sub(r"&((?:r#)?\w+)\.clone\(\)", r"&\1", code)
    files[slug(f.__module__)].append(code)
if failed:
    for name, why in failed:
        print(name, why)
    sys.exit(1)
for mod, code in files.items():
    (dest / (mod + ".rs")).write_text(
        "// Generated by tools/rust_port/generate.py.\nuse super::*;\n" + "\n".join(code), encoding="utf8"
    )
main = "// Generated by tools/rust_port/generate.py.\n#![allow(unused_mut, unused_assignments, unused_variables, unused_parens, non_snake_case)]\nuse super::failure;\nuse anyhow::{Result,Context};\nuse serde_json::{json,Value};\nmod values;\nuse values::*;\n"
for mod in files:
    main += f"mod {mod};\nuse {mod}::*;\n"
main += "\npub(super) fn execute(name: &str, args: Vec<Value>)->Result<Value> {invoke(&json!(name),&args)}\n"
main += "fn invoke(name:&Value,args:&[Value])->Result<Value>{match text(name).as_str(){\n"
needed = {resolve_name(n) for g in groups for n in GROUPS[g]}
if "expansion" in groups:
    for spec in importlib.import_module("hate.expansion_runner").EXPANSION_REPORT_SPECS:
        needed.add(spec.builder)
for f in sorted(needed, key=ident):
    num = len(inspect.signature(f).parameters)
    main += (
        f"{rs(ident(f))} if args.len()=={num} => "
        + ident(f)
        + "("
        + ",".join(f"args[{i}].clone()" for i in range(num))
        + "),\n"
    )
main += 'name=>anyhow::bail!("unknown report builder or arguments: {name}")}}\n'
(dest / "mod.rs").write_text(main, encoding="utf8")
(dest / "catalog.json").write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
subprocess.run(["rustfmt", "--edition", "2024", str(dest / "mod.rs")], check=True)
print(len(funcs), "functions,", len(files), "modules")
