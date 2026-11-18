use super::*;

fn evidence(x: &Inputs, g: &Graph) -> V {
    let mut map = json!({
        "schema_version": "HATE/v1",
        "run_id": x.id(),
        "run_attempt": x.attempt(),
        "requirements": [],
        "risks": [],
        "tests": [],
        "evidence": [],
        "findings": [],
        "contracts": [],
        "mutations": [],
        "links": {
            "requires_test": [],
            "evidenced_by": [],
            "supports": [],
            "touches": [],
            "contradicts": [],
        },
        "gaps": {
            "unsupported_claims": g.claims,
            "missing_execution": g.missing,
            "missing_coverage": [],
            "unsafe_artifacts": g.unsafe_artifacts,
        },
    });
    let add = |m: &mut V, k: &str, v: V| {
        if !m[k].is_array() {
            m[k] = json!([])
        }
        m[k].as_array_mut().unwrap().push(v)
    };
    for n in &g.nodes {
        let d = &n["data"];
        let kind = s(n, "kind");
        let (group, mut row) = match kind {
            "risk" => (
                "risks",
                json!({"risk_id":n["id"],"label":n["label"],"severity":d["severity"]}),
            ),
            "test" => (
                "tests",
                json!({"test_id":n["id"],"canonical_test_id":d["canonical_test_id"],"status":d["status"]}),
            ),
            "finding" => (
                "findings",
                json!({
                    "finding_id": n["id"],
                    "rule_id": d["rule_id"],
                    "level": d["level"],
                    "severity": d["severity"],
                    "location": d["location"],
                }),
            ),
            "escaped_defect" => (
                "escaped_defects",
                project(
                    d,
                    json!({
                        "defect_id": "",
                        "detected_at": "",
                        "severity": "unknown",
                        "affected_requirement_ids": [],
                        "affected_risk_ids": [],
                        "release_ref": "",
                    }),
                ),
            ),
            "execution_evidence" | "coverage" | "evidence_artifact" | "contract_evidence"
            | "mutation_evidence" | "evidence_strength" => {
                let base = json!({
                    "evidence_id": n["id"],
                    "kind": kind,
                    "label": n["label"],
                    "artifact_kind": s(d,"kind"),
                    "adapter": s(d,"adapter"),
                    "artifact_role": s(d,"artifact_role"),
                    "path": s(d,"path"),
                    "sourceRefs": n["sourceRefs"],
                });
                add(&mut map, "evidence", base);
                match kind {
                    "contract_evidence" => (
                        "contracts",
                        project(
                            d,
                            json!({"contract_id":"","provider":"","consumer":"","interaction":"","status":"","required":false}),
                        ),
                    ),
                    "mutation_evidence" => (
                        "mutations",
                        project(
                            d,
                            json!({
                                "mutation_id": "",
                                "status": "",
                                "mutator": "",
                                "file": "",
                                "start_line": 0,
                                "end_line": 0,
                                "covered_by": [],
                                "killed_by": [],
                            }),
                        ),
                    ),
                    "evidence_strength" => ("evidence_strength", d.clone()),
                    _ => continue,
                }
            }
            _ => continue,
        };
        if !matches!(kind, "risk" | "test") {
            row["sourceRefs"] = n["sourceRefs"].clone();
        }
        add(&mut map, group, row);
    }
    if map.get("escaped_defects").is_some() {
        for k in ["escaped_after", "relates_to_requirement", "relates_to_risk"] {
            map["links"][k] = json!([]);
        }
    }
    if map.get("evidence_strength").is_some() {
        map["links"]["has_strength"] = json!([]);
    }
    for e in &g.edges {
        let k = s(e, "kind");
        if map["links"].get(k).is_none() {
            continue;
        }
        let t = &e["traceability"];
        let mut l = json!({"from":e["from"],"to":e["to"],"confidence":t["confidence"]});
        for key in ["adapter", "artifact_role"] {
            if !s(t, key).is_empty() {
                l[key] = t[key].clone();
            }
        }
        add(&mut map["links"], k, l);
    }
    map
}

pub(super) fn write(x: &Inputs, g: &mut Graph, out: &Path) -> Result<V> {
    for m in &g.missing {
        g.claims.push(json!({"risk_id":m["risk_id"],"expected_test":m["expected_test_ref"],"reason":m["reason"]}));
    }
    let mut seen = BTreeSet::new();
    g.unsafe_artifacts.retain(|v| seen.insert(v.to_string()));
    let map = evidence(x, g);
    let misses = g
        .missing
        .iter()
        .filter(|m| {
            items(&x.diff["risks"])
                .iter()
                .any(|r| r["risk_id"] == m["risk_id"] && r["severity"] == "high")
        })
        .count();
    let contract = |v: &&V| {
        matches!(
            s(v, "reason"),
            "required contract failed" | "required contract evidence missing"
        )
    };
    let mutation = |v: &&V| {
        matches!(
            s(v, "reason"),
            "required mutation survived" | "required mutation evidence missing"
        )
    };
    let contracts: Vec<_> = g.claims.iter().filter(contract).collect();
    let mutations: Vec<_> = g.claims.iter().filter(mutation).collect();
    let defects: Vec<_> = g
        .claims
        .iter()
        .filter(|v| s(v, "reason").starts_with("escaped defect"))
        .collect();
    let penalty = misses
        + usize::from(
            g.claims
                .iter()
                .any(|v| v["reason"] == "risk source_refs missing"),
        )
        + usize::from(!contracts.is_empty())
        + usize::from(!mutations.is_empty())
        + usize::from(!defects.is_empty())
        + usize::from(!g.unsafe_artifacts.is_empty());
    let score = (10i64 - penalty as i64).max(0) as f64 / 10.;
    let partial = !g.claims.is_empty() || !g.missing.is_empty() || !g.unsafe_artifacts.is_empty();
    let status = if partial { "partial" } else { "success" };
    let comp = json!({
        "score": score,
        "partial": partial,
        "parserFailures": [],
        "unsupportedClaims": g.claims,
        "excludedArtifacts": g.unsafe_artifacts,
    });
    let mut artifacts = vec![];
    for (name, kind, include) in [
        (RUN, "HATE-run", true),
        (TEST, "HATE-test-results", true),
        (COV, "HATE-coverage", true),
        (PRE, "precheck-decision", true),
        (
            SARIF,
            "HATE-static",
            x.sarif.as_object().is_some_and(|m| !m.is_empty()),
        ),
        (CONTRACT, "HATE-contract", !x.contract.is_empty()),
        (MUT, "HATE-mutation", !x.mutation.is_empty()),
        (STRENGTH, "HATE-evidence-strength", !x.strength.is_empty()),
    ] {
        if include {
            artifacts.push(json!({"kind":kind,"path":source(name)}));
        }
    }
    if let Some(name) = &x.defect_file {
        artifacts.push(json!({"kind":"escaped-defects","path":source(name)}));
    }
    let sha = s(&x.run, "commit_sha");
    let created = get(&x.run, "created_at", json!(""));
    let id = x.id();
    let attempt = x.attempt();
    let dec = s(&x.pre["payload"], "decision");
    let bundle = json!({
        "metadata": {
            "qegVersion": "HATE/v1",
            "runId": id,
            "runAttempt": attempt,
            "commitSha": sha,
            "createdAt": created,
            "profile": "lean",
            "inputArtifacts": artifacts,
            "debugOnly": dec=="hard_dq",
        },
        "nodes": g.nodes,
        "edges": g.edges,
        "completeness": comp,
    });
    let mut errors: Vec<_> = crate::trust::bundle_validator()
        .iter_errors(&bundle)
        .map(|e| {
            (
                e.instance_path().to_string(),
                crate::p0a::schema_message(&e),
            )
        })
        .collect();
    if !errors.is_empty() {
        errors.sort();
        let mut details = errors
            .iter()
            .take(8)
            .map(|(_, v)| v.as_str())
            .collect::<Vec<_>>()
            .join("; ");
        if errors.len() > 8 {
            details += &format!("; {} more schema errors", errors.len() - 8);
        }
        anyhow::bail!("Generated qeg-bundle.json failed schema validation: {details}");
    }
    let mut report = json!({
        "schema_version": "HATE/v1",
        "run_id": id,
        "run_attempt": attempt,
        "commit_sha": sha,
        "created_at": created,
        "export_status": status,
        "completeness": comp,
        "qeg_schema_compatibility": {"schema":"schemas/HATE/v1/qeg-bundle.schema.json","valid":true,"errors":[]},
        "unsupportedClaims": g.claims,
        "contract_failures": contracts,
        "mutation_gaps": mutations,
        "missing_execution": g.missing,
        "excludedArtifacts": g.unsafe_artifacts,
        "source_refs": [source(PRE),if x.has_diff{source(DIFF)}else{"none".into()}],
        "publish_gate_override": false,
    });
    let total = x.strength.len();
    let scores = |k: &str| {
        x.strength
            .iter()
            .filter_map(|r| r["payload"][k].as_f64())
            .collect::<Vec<_>>()
    };
    let flake = scores("flake_score");
    let mutation = scores("mutation_score");
    if total > 0 {
        report["evidence_strength_distribution"] = json!({
            "total": total,
            "flake_known": flake.len(),
            "flake_unknown": total-flake.len(),
            "flake_nonzero": flake.iter().filter(|v|**v>0.).count(),
            "mutation_known": mutation.len(),
            "mutation_unknown": total-mutation.len(),
            "mutation_zero": mutation.iter().filter(|v|**v==0.).count(),
        });
    }
    if !x.defects.is_empty() || !defects.is_empty() {
        report["escaped_defects"] = json!(x.defects);
        report["escaped_defect_gaps"] = json!(defects);
    }
    let n = g.nodes.len();
    let e = g.edges.len();
    let gaps = items(&x.pre["payload"]["soft_gaps"]).len();
    let gap_line = if dec == "conditional" || gaps > 0 {
        format!("- Precheck soft gaps: {gaps}\n")
    } else {
        String::new()
    };
    let summary = format!(
        "# P0b QEG Export Summary\n\n- Run: `{id}` attempt `{attempt}`\n- Commit: `{}`\n- Precheck: `{dec}`\n{gap_line}- Nodes: {n}\n- Edges: {e}\n- Completeness: `{score:.2}`\n- Missing execution gaps: {}\n- Evidence strength: {total} records, flake known {}/unknown {}, mutation known {}/unknown {}\n- Escaped defects: {}\n\nGenerated artifacts:\n- `qeg-bundle.json` ({n} nodes, {e} edges)\n- `evidence-map.json`\n- `qeg-export-report.json`\n\nThis export is advisory optional evidence for QEG.\nHATE does not approve release. `publish_gate_override=false`.\n",
        &sha[..sha.len().min(12)],
        g.missing.len(),
        flake.len(),
        total - flake.len(),
        mutation.len(),
        total - mutation.len(),
        x.defects.len()
    );
    let diff = if x.diff.as_object().is_none_or(|v| v.is_empty()) {
        json!({"schema_version":"HATE/v1","changed_entities":[],"risks":[],"test_obligations":[]})
    } else {
        x.diff.clone()
    };
    let mut outputs = vec![
        ("qeg-bundle.json", bundle),
        ("evidence-map.json", map),
        (DIFF, diff),
        ("qeg-export-report.json", report),
        ("qeg-export-summary.md", json!(summary)),
    ];
    let optional = ["risk-debt-register.json", "manual-bb-bridge-requests.jsonl"];
    if !g.missing.is_empty() {
        outputs.push((optional[0], gaps::debts(x, &g.missing)));
        outputs.push((
            optional[1],
            json!(
                g.missing
                    .iter()
                    .map(|m| gaps::manual(x, m))
                    .collect::<Vec<_>>()
            ),
        ));
    }
    fs::create_dir_all(out)?;
    for (name, v) in &outputs {
        let p = out.join(name);
        if name.ends_with(".md") {
            fs::write(p, v.as_str().unwrap())?;
        } else if name.ends_with(".jsonl") {
            let mut file = fs::File::create(p)?;
            use std::io::Write;
            for row in items(v) {
                writeln!(file, "{row}")?;
            }
        } else {
            write_json(&p, v)?;
        }
    }
    if g.missing.is_empty() {
        for name in optional {
            let path = out.join(name);
            if path.try_exists()? {
                fs::remove_file(path)?;
            }
        }
    }
    Ok(json!({
        "export_status": status,
        "exit_code": 0,
        "generated": outputs.iter().map(|(n,_)|n).collect::<Vec<_>>(),
        "completeness": comp,
        "missing_executions": g.missing.len(),
        "out_dir": out,
        "publish_gate_override": false,
    }))
}
