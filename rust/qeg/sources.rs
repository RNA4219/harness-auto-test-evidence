use super::*;
use crate::trust::{coerced_integer, json_integer};
use bigdecimal::{Signed, Zero};
type DefectInput = (Vec<V>, Vec<V>, Option<String>);
pub(super) fn defects(dir: &Path) -> Result<DefectInput> {
    let Some(file) = ["escaped-defects.json", "escaped-defects.csv"]
        .into_iter()
        .find(|p| dir.join(p).is_file())
    else {
        return Ok((vec![], vec![], None));
    };
    let path = dir.join(file);
    let raw: Vec<V> = if file.ends_with(".csv") {
        let mut reader = csv::Reader::from_path(path)?;
        reader
            .deserialize::<BTreeMap<String, String>>()
            .map(|r| r.map(|v| json!(v)))
            .collect::<std::result::Result<_, _>>()?
    } else {
        let value = crate::io::read_json(&path)?;
        if value.is_object() {
            let list = ["defects", "escaped_defects"]
                .iter()
                .map(|k| &value[k])
                .find(|v| v.as_array().is_some_and(|a| !a.is_empty()))
                .or_else(|| value.get("items"));
            list.and_then(V::as_array)
                .cloned()
                .unwrap_or_else(|| vec![value])
        } else {
            items(&value).to_vec()
        }
    };
    let mut rows = vec![];
    let mut issues = vec![];
    let valid = |s: &str| {
        ["rand:", "ctg:", "mbb:", "hate:", "qeg:"]
            .iter()
            .any(|p| s.starts_with(p))
    };
    for (i, r) in raw.iter().filter(|v| v.is_object()).enumerate() {
        let fallback = format!("defect-{}", i + 1);
        let raw_id = alt(r, &["defect_id", "id", "key"], &fallback).trim();
        let id = if valid(raw_id) {
            raw_id.to_owned()
        } else {
            format!("hate:defect/{raw_id}")
        };
        let refs = |keys: &[&str]| -> Vec<String> {
            let Some(v) = keys.iter().map(|k| &r[k]).find(|v| {
                v.as_str().is_some_and(|s| !s.is_empty())
                    || v.as_array().is_some_and(|a| !a.is_empty())
            }) else {
                return vec![];
            };
            match v {
                V::String(s) => s
                    .split([',', ';'])
                    .map(str::trim)
                    .filter(|s| !s.is_empty())
                    .map(str::to_owned)
                    .collect(),
                _ => items(v)
                    .iter()
                    .map(|v| text(v).trim().to_owned())
                    .filter(|v| !v.is_empty())
                    .collect(),
            }
        };
        let req = refs(&[
            "affected_requirement_ids",
            "requirement_ids",
            "requirements",
        ]);
        let risks = refs(&["affected_risk_ids", "risk_ids", "risks"]);
        let release = alt(r, &["release_ref", "release", "verdict_ref"], "").trim();
        rows.push(json!({
            "defect_id": id,
            "detected_at": alt(r,&["detected_at","created_at","detected"],"").trim(),
            "severity": alt(r,&["severity","priority"],"unknown").trim().to_lowercase(),
            "affected_requirement_ids": req,
            "affected_risk_ids": risks,
            "release_ref": release,
        }));
        let bad: Vec<_> = req
            .iter()
            .chain(&risks)
            .map(String::as_str)
            .chain([release])
            .filter(|v| !v.is_empty() && !valid(v))
            .collect();
        if !bad.is_empty() {
            issues.push(
                json!({"defect_id":id,"refs":bad,"reason":"escaped defect id resolution failed"}),
            );
        }
        if release.is_empty() {
            issues.push(json!({"defect_id":id,"reason":"escaped defect release_ref missing"}));
        }
    }
    Ok((rows, issues, Some(file.into())))
}
pub(super) fn extra_nodes(x: &Inputs, g: &mut Graph) -> Result<()> {
    for r in &x.contract {
        let p = &r["payload"];
        let id = alt(p, &["contract_id", "pact_id", "verification_id"], "");
        if id.is_empty() {
            continue;
        }
        let raw = alt(p, &["status", "result", "verification_status"], "unknown")
            .trim()
            .to_lowercase();
        let status = match raw.as_str() {
            "pass" | "passed" | "success" | "verified" | "ok" => "passed",
            "fail" | "failed" | "failure" | "error" => "failed",
            _ => &raw,
        };
        let mut d = project(
            p,
            json!({
                "provider": "",
                "consumer": "",
                "interaction": "",
                "required": false,
                "verification_id": "",
                "pact_url": "",
                "message": "",
            }),
        );
        d["contract_id"] = json!(id);
        d["status"] = json!(status);
        let fallback = format!(
            "{} -> {}",
            p["consumer"].as_str().unwrap_or("consumer"),
            p["provider"].as_str().unwrap_or("provider")
        );
        g.nodes.push(node(
            "contract_evidence",
            &format!("contract:{id}"),
            alt(p, &["name"], &fallback),
            d,
            CONTRACT,
        ));
    }
    for r in &x.mutation {
        let p = &r["payload"];
        let id = alt(p, &["mutation_id", "mutant_id", "id"], "");
        if id.is_empty() {
            continue;
        }
        let raw = alt(p, &["status", "result", "mutant_status"], "unknown")
            .trim()
            .to_lowercase()
            .replace([' ', '-'], "_");
        let status = match raw.as_str() {
            "killed_by_timeout" => "timeout",
            "nocoverage" | "not_covered" => "no_coverage",
            _ => &raw,
        };
        let tests = |k: &str, alias: &str| {
            [&p[k], &p[alias]]
                .into_iter()
                .find(|v| v.as_array().is_some_and(|a| !a.is_empty()))
                .cloned()
                .unwrap_or(json!([]))
        };
        let mutation_line = |field: &str| {
            let line = coerced_integer(&p[field])
                .filter(|n| !n.is_zero())
                .or_else(|| coerced_integer(&p["line"]))
                .unwrap_or_default();
            json_integer(&line)
        };
        let fallback = format!("{} {id}", p["mutator"].as_str().unwrap_or("mutant"));
        g.nodes.push(node(
            "mutation_evidence",
            &format!("mutation:{id}"),
            alt(p, &["name"], &fallback),
            json!({
                "mutation_id": id,
                "status": status,
                "mutator": s(p,"mutator"),
                "file": alt(p,&["file","source_file"],"").replace('\\',"/"),
                "start_line": mutation_line("start_line"),
                "end_line": mutation_line("end_line"),
                "covered_by": tests("covered_by","covered_by_tests"),
                "killed_by": tests("killed_by","killed_by_tests"),
                "message": s(p,"message"),
            }),
            MUT,
        ));
    }
    for (i, run) in items(&x.sarif["runs"]).iter().enumerate() {
        for (j, r) in items(&run["results"])
            .iter()
            .enumerate()
            .filter(|(_, r)| r.is_object())
        {
            let id = r["ruleId"].as_str().unwrap_or("unknown-rule");
            let rule = items(&run["tool"]["driver"]["rules"])
                .iter()
                .rev()
                .find(|v| v["id"] == id)
                .unwrap_or(&V::Null);
            let location = items(&r["locations"])
                .first()
                .filter(|v| v.is_object())
                .map(|v| v.get("physicalLocation").cloned().unwrap_or(json!({})))
                .filter(V::is_object);
            let loc = if let Some(v) = location {
                let a = &v["artifactLocation"];
                let region = &v["region"];
                json!({
                    "path": s(a,"uri").replace('\\',"/"),
                    "start_line": get(region,"startLine",json!(0)),
                    "end_line": get(region,"endLine",get(region,"startLine",json!(0))),
                    "start_column": get(region,"startColumn",json!(0)),
                    "end_column": get(region,"endColumn",json!(0)),
                    "uri_base_id": s(a,"uriBaseId"),
                })
            } else {
                json!({"path":"","start_line":0})
            };
            let path = s(&loc, "path");
            let start = coerced_integer(&loc["start_line"]).unwrap_or_default();
            let end = coerced_integer(&loc["end_line"]).unwrap_or_else(|| start.clone());
            let finding = format!("finding:{}", hash(&format!("{i}:{j}:{id}:{path}:{start}")));
            let mut fp = r["partialFingerprints"]
                .as_object()
                .cloned()
                .unwrap_or_default();
            if let Some(m) = r["fingerprints"].as_object() {
                fp.extend(m.clone());
            }
            let level = r["level"].as_str().unwrap_or("warning");
            let props = &r["properties"];
            let name = alt(rule, &["name"], id);
            let message = r["message"].as_str().unwrap_or(s(&r["message"], "text"));
            let data = json!({
                "rule_id": id,
                "rule_name": name,
                "rule_short_description": alt(&rule["shortDescription"],&["text","markdown"],""),
                "rule_full_description": alt(&rule["fullDescription"],&["text","markdown"],""),
                "help_uri": s(rule,"helpUri"),
                "level": level,
                "severity": alt(props,&["security-severity","severity"],level),
                "path": path,
                "start_line": json_integer(&start),
                "end_line": json_integer(&end),
                "start_column": get(&loc,"start_column",json!(0)),
                "end_column": get(&loc,"end_column",json!(0)),
                "location": loc,
                "fingerprints": fp,
                "message": message,
            });
            g.nodes.push(node("finding", &finding, name, data, SARIF));
            for n in g.nodes.iter().filter(|n| {
                n["kind"] == "changed_code" && s(&n["data"], "path").replace('\\', "/") == path
            }) {
                let a = coerced_integer(&n["data"]["start_line"]).unwrap_or_default();
                let z = coerced_integer(&n["data"]["end_line"])
                    .filter(|n| !n.is_zero())
                    .unwrap_or_else(|| a.clone());
                let right = if end.is_zero() { &start } else { &end };
                if !a.is_positive() || !start.is_positive() || (&a <= right && start <= z) {
                    g.edges
                        .push(edge("touches", s(n, "id"), &finding, &[SARIF], "high", &[]));
                }
            }
        }
    }
    g.claims.extend(x.defect_claims.clone());
    if let Some(file) = &x.defect_file {
        for d in &x.defects {
            let id = s(d, "defect_id");
            let nid = format!("escaped_defect:{}", hash(&id.replace('\\', "/")));
            let mut data = d.clone();
            data["adapter"] = json!("escaped_defect");
            g.nodes.push(node(
                "escaped_defect",
                &nid,
                &format!("Escaped defect {id}"),
                data,
                file,
            ));
            for (k, kind) in [
                ("affected_requirement_ids", "relates_to_requirement"),
                ("affected_risk_ids", "relates_to_risk"),
                ("release_ref", "escaped_after"),
            ] {
                let refs = if k == "release_ref" {
                    d[k].as_str()
                        .filter(|v| !v.is_empty())
                        .into_iter()
                        .collect()
                } else {
                    items(&d[k])
                        .iter()
                        .filter_map(V::as_str)
                        .collect::<Vec<_>>()
                };
                for r in refs {
                    let mut e = edge(
                        kind,
                        &nid,
                        r,
                        &[file],
                        "medium",
                        &[
                            "Escaped defect tracker export maps the defect to this cross-repo reference.",
                        ],
                    );
                    e["traceability"]["adapter"] = json!("escaped_defect");
                    g.edges.push(e);
                }
            }
        }
    }
    Ok(())
}
