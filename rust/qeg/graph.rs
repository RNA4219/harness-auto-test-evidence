use super::*;
fn unsafe_art(v: &V) -> bool {
    v["safe_for_summary"] != true
        || matches!(s(v, "classification"), "secret" | "pii" | "restricted")
        || v["security_checks"]
            .as_object()
            .is_some_and(|m| m.values().any(|v| v == "fail"))
}
fn role(v: &V) -> String {
    let adapter = alt(v, &["adapter", "framework"], "").to_lowercase();
    let mut role = alt(v, &["artifact_role", "role"], "").to_lowercase();
    let kind = s(v, "kind").to_lowercase();
    let path = s(v, "path").to_lowercase();
    let id = s(v, "artifact_id").to_lowercase();
    if !matches!(role.as_str(), "trace" | "screenshot" | "video" | "log") {
        role = if matches!(kind.as_str(), "trace" | "screenshot" | "video") {
            kind
        } else if path.ends_with(".log") || id.contains("log") || path.contains("/logs/") {
            "log".into()
        } else {
            String::new()
        };
    }
    if matches!(adapter.as_str(), "playwright" | "pw")
        || id.contains("playwright")
        || path.contains("playwright")
        || matches!(role.as_str(), "trace" | "screenshot" | "video")
    {
        role
    } else {
        String::new()
    }
}
pub(super) fn build(x: &Inputs, g: &mut Graph) -> Result<()> {
    let pre = format!("hate_precheck:{}:{}", x.id(), x.attempt());
    let d = &x.pre["payload"];
    let mut payload = project(
        d,
        json!({"decision":"","exit_code":0,"qeg_export_allowed":false,"qeg_export_phase":"P0b"}),
    );
    merge_fields(&mut payload, d, &["dq_hits", "soft_gaps", "reasons"]);
    g.nodes.push(node(
        "gate_verdict",
        &pre,
        &format!("HATE P0a Precheck {}", x.id()),
        payload,
        PRE,
    ));
    g.nodes.push(node(
        "run",
        &format!("run:{}:{}", x.id(), x.attempt()),
        &format!("CI Run {}", x.id()),
        x.run["payload"].clone(),
        RUN,
    ));
    for ent in items(&x.diff["changed_entities"]) {
        let path = s(ent, "path");
        for range in items(&ent["ranges"]) {
            let start = get(range, "start_line", json!(0));
            let end = get(range, "end_line", json!(0));
            let coordinates = format!("L{}-L{}", text(&start), text(&end));
            let changed = format!("changed_code:{path}#{coordinates}");
            g.nodes.push(node(
                "changed_code",
                &changed,
                &format!("Changed: {path} {coordinates}"),
                json!({"path":path,"start_line":start,"end_line":end}),
                DIFF,
            ));
            for risk in items(&ent["risk_refs"]) {
                g.edges.push(edge(
                    "touches",
                    &changed,
                    &format!("risk:{}", text(risk)),
                    &[DIFF],
                    "high",
                    &[],
                ));
            }
        }
    }
    for risk in items(&x.diff["risks"]) {
        let id = s(risk, "risk_id");
        if items(&risk["source_refs"]).is_empty() {
            g.claims
                .push(json!({"risk_id":id,"reason":"risk source_refs missing"}));
        }
        g.nodes.push(json!({
            "id": format!("risk:{id}"),
            "kind": "risk",
            "label": get(risk,"title",json!(format!("Risk {id}"))),
            "data": project(risk,json!({"severity":"medium","required_test_layers":[]})),
            "sourceRefs": get(risk,"source_refs",json!([])),
        }));
    }
    sources::extra_nodes(x, g)?;
    let mut artifacts = BTreeMap::new();
    let mut order = vec![];
    for a in items(&x.art["artifacts"]) {
        let id = s(a, "artifact_id");
        if !id.is_empty() && artifacts.insert(id, a).is_none() {
            order.push(id);
        }
    }
    for id in order {
        let a = artifacts[id];
        if unsafe_art(a) {
            g.unsafe_artifacts.push(json!({"artifact_id":id,"path":s(a,"path"),"reason":"artifact is not safe for QEG export"}));
            continue;
        }
        let role = role(a);
        g.nodes.push(node(
            "evidence_artifact",
            &format!("artifact:{id}"),
            id,
            json!({
                "kind": get(a,"kind",json!("artifact")),
                "adapter": if !role.is_empty(){"playwright"}else{s(a,"adapter")},
                "artifact_role": role,
                "path": s(a,"path"),
                "sha256": s(a,"sha256"),
            }),
            ART,
        ));
    }
    let tests = test_nodes(x, g, &artifacts)?;
    for r in &x.strength {
        let p = &r["payload"];
        let id = s(p, "test_id");
        if id.is_empty() {
            continue;
        }
        let nid = format!("evidence_strength:{}", hash(id));
        g.nodes.push(node(
            "evidence_strength",
            &nid,
            &format!("Evidence strength: {id}"),
            project(
                p,
                json!({
                    "test_id": "",
                    "flake_score": "unknown",
                    "mutation_score": "unknown",
                    "sample_size": 0,
                    "computed_at": "",
                    "inputs": [],
                }),
            ),
            STRENGTH,
        ));
        if let Some(test) = tests.get(id) {
            g.edges.push(edge(
                "has_strength",
                test,
                &nid,
                &[STRENGTH],
                "medium",
                &["Evidence strength is computed by HATE and interpreted by QEG policy."],
            ));
        }
    }
    for r in &x.cov {
        let p = &r["payload"];
        let file = s(p, "file");
        if file.is_empty() {
            continue;
        }
        let nid = format!("coverage:{}", hash(&file.replace('\\', "/")));
        g.nodes.push(node(
            "coverage",
            &nid,
            &format!("Coverage: {file}"),
            project(
                p,
                json!({"file":"","format":"lcov","line_hits":{},"branch_hits":[],"contexts":[]}),
            ),
            COV,
        ));
        for ctx in items(&p["contexts"]) {
            if let Some(test) = tests.get(ctx.as_str().unwrap_or(s(ctx, "test_id"))) {
                g.edges.push(edge(
                    "supports",
                    &nid,
                    test,
                    &[COV],
                    "medium",
                    &["coverage context maps to test"],
                ));
            }
        }
    }
    obligations(x, g, &tests, &artifacts)?;
    g.edges.push(edge(
        "decides",
        &pre,
        &format!("qeg_export:{}", x.id()),
        &[PRE],
        "high",
        &[],
    ));
    Ok(())
}
fn outcome(p: &V) -> (String, V) {
    let declared = s(p, "status");
    let status = if p["wouldRun"] == true {
        "inconclusive".to_owned()
    } else {
        p["status"].as_str().unwrap_or("unknown").to_lowercase()
    };
    let mut fields = json!({});
    merge_fields(&mut fields, p, &OUTCOME);
    if fields.get("source_status").is_none()
        && p.get("status").is_some()
        && (p["wouldRun"] == true || status != declared)
    {
        fields["source_status"] = json!(declared);
    }
    (status, fields)
}
fn test_nodes(
    x: &Inputs,
    g: &mut Graph,
    artifacts: &BTreeMap<&str, &V>,
) -> Result<BTreeMap<String, String>> {
    let mut grouped = BTreeMap::<&str, BTreeMap<String, &V>>::new();
    for r in &x.tests {
        grouped
            .entry(s(&r["payload"], "canonical_test_id"))
            .or_default()
            .insert(crate::p0a::canonical_json(r), r);
    }
    let mut ids = BTreeMap::new();
    for (id, obs) in grouped {
        let test = format!("test:{}", hash(id));
        let mut data = json!({"canonical_test_id":id,"framework":"unknown","file":""});
        let mut statuses = BTreeSet::new();
        for field in ID_FIELDS {
            let mut vals = obs.values().filter_map(|r| r["payload"].get(field));
            if let Some(first) = vals.next() {
                ensure!(
                    vals.all(|v| v == first),
                    "conflicting payload.{field} for canonical test {id}"
                );
                data[field] = first.clone();
            }
        }
        for r in obs.values() {
            statuses.insert(outcome(&r["payload"]).0);
        }
        data["status"] = if statuses.len() == 1 {
            json!(statuses.first())
        } else {
            json!("inconclusive")
        };
        if obs.len() == 1 {
            let p = &obs.values().next().unwrap()["payload"];
            data["duration_ms"] = get(p, "duration_ms", json!(0));
            merge_fields(&mut data, &outcome(p).1, &OUTCOME);
            merge_fields(&mut data, p, &["parser_diagnostics"]);
        }
        let label = data["name"].as_str().unwrap_or(id).to_owned();
        g.nodes.push(node("test", &test, &label, data, TEST));
        ids.insert(id.to_owned(), test.clone());
        let multiple = obs.len() > 1;
        for r in obs.into_values() {
            let p = &r["payload"];
            let sha = digest(r);
            let mut exec = format!("execution:{}:{}", x.id(), hash(id));
            if multiple {
                exec += &format!(":{sha}");
            }
            let (status, mut ed) = outcome(p);
            ed["run_id"] = json!(x.id());
            ed["run_attempt"] = x.attempt().clone();
            ed["status"] = json!(status);
            ed["duration_ms"] = get(p, "duration_ms", json!(0));
            ed["source_record_sha256"] = json!(sha);
            merge_fields(&mut ed, r, &["commit_sha"]);
            merge_fields(&mut ed, p, &META);
            merge_fields(&mut ed, p, &["parser_diagnostics"]);
            if let Some(v) = r.get("record_id") {
                ed["source_record_id"] = v.clone();
            }
            g.nodes.push(node(
                "execution_evidence",
                &exec,
                &format!("Execution: {id}"),
                ed,
                TEST,
            ));
            g.edges
                .push(edge("evidenced_by", &test, &exec, &[TEST], "high", &[]));
            for a in items(&p["artifacts"]) {
                let Some(aid) = a.as_str().or_else(|| a["artifact_id"].as_str()) else {
                    continue;
                };
                let Some(artifact) = artifacts.get(aid) else {
                    g.claims.push(json!({
                        "test_id": id,
                        "artifact_id": aid,
                        "reason": "test artifact reference not found in artifact manifest",
                    }));
                    continue;
                };
                if unsafe_art(artifact) {
                    g.unsafe_artifacts.push(json!({
                        "test_id": id,
                        "artifact_id": aid,
                        "path": s(artifact,"path"),
                        "reason": "test requires unsafe artifact",
                    }));
                    continue;
                }
                let target = format!("artifact:{aid}");
                let role = role(artifact);
                let mut e = edge("evidenced_by", &exec, &target, &[TEST, ART], "high", &[]);
                if !role.is_empty() {
                    let mut t = edge(
                        "evidenced_by",
                        &test,
                        &target,
                        &[TEST, ART],
                        "medium",
                        &["Playwright artifact is attached to this test result"],
                    );
                    for row in [&mut t, &mut e] {
                        row["traceability"]["adapter"] = json!("playwright");
                        row["traceability"]["artifact_role"] = json!(role);
                    }
                    g.edges.push(t);
                }
                g.edges.push(e);
            }
        }
    }
    Ok(ids)
}
fn obligations(
    x: &Inputs,
    g: &mut Graph,
    tests: &BTreeMap<String, String>,
    art: &BTreeMap<&str, &V>,
) -> Result<()> {
    let exec: BTreeSet<_> = g
        .nodes
        .iter()
        .filter(|n| {
            n["kind"] == "execution_evidence"
                && n["data"]["wouldRun"] != true
                && matches!(
                    s(&n["data"], "status"),
                    "passed" | "failed" | "error" | "flaky"
                )
        })
        .map(|n| s(n, "id"))
        .collect();
    let ran: BTreeSet<_> = g
        .edges
        .iter()
        .filter(|e| e["kind"] == "evidenced_by" && exec.contains(s(e, "to")))
        .map(|e| s(e, "from").to_owned())
        .collect();
    for o in items(&x.diff["test_obligations"]) {
        let risk = s(o, "risk_id");
        let rid = format!("risk:{risk}");
        let r = items(&x.diff["risks"])
            .iter()
            .find(|r| r["risk_id"] == risk)
            .unwrap_or(&V::Null);
        let entities: Vec<_> = items(&x.diff["changed_entities"])
            .iter()
            .filter(|e| items(&e["risk_refs"]).iter().any(|v| v == risk))
            .map(|e| project(e, json!({"entity_id":"","path":"","ranges":[]})))
            .collect();
        for reference in items(&o["expected_test_refs"]) {
            let raw = reference
                .as_str()
                .context("expected_test_ref must be a string")?;
            let id = tests
                .get(raw)
                .or_else(|| tests.get(&format!("junit:{raw}")));
            if let Some(id) = id {
                g.edges
                    .push(edge("requires_test", &rid, id, &[DIFF], "high", &[]));
            }
            if !id.is_some_and(|id| ran.contains(id)) {
                let mut miss = json!({
                    "risk_id": risk,
                    "risk_title": s(r,"title"),
                    "severity": r["severity"].as_str().unwrap_or("high"),
                    "obligation_id": s(o,"obligation_id"),
                    "expected_test_ref": raw,
                    "required_evidence_kinds": get(o,"required_evidence_kinds",json!([])),
                    "required_test_layers": get(r,"required_test_layers",json!([])),
                    "risk_source_refs": get(r,"source_refs",json!([])),
                    "changed_entity_ids": entities.iter().map(|e|&e["entity_id"]).collect::<Vec<_>>(),
                    "changed_entities": entities,
                    "reason": if id.is_some(){"test result does not establish execution"}else{"test not found in execution results"},
                });
                if let Some(id) = id {
                    miss["test_node_id"] = json!(id);
                }
                g.missing.push(miss);
            }
        }
        let kinds = items(&o["required_evidence_kinds"]);
        if kinds.iter().any(|v| v == "artifact") {
            for a in items(&o["required_artifact_refs"]) {
                let id = a.as_str().context("invalid artifact reference")?;
                match art.get(id){None=>g.claims.push(json!({"risk_id":risk,"artifact_id":id,"reason":"required artifact not found in artifact manifest"})),Some(a)if unsafe_art(a)=>g.unsafe_artifacts.push(json!({
                    "risk_id": risk,
                    "artifact_id": id,
                    "path": s(a,"path"),
                    "reason": "required artifact is unsafe for export",
                })),_=>()}
            }
        }
        for (kind, file, adapter) in [("contract", CONTRACT, "pact"), ("mutation", MUT, "stryker")]
        {
            if !kinds.iter().any(|v| v == kind) {
                continue;
            }
            for value in items(&o[format!("required_{kind}_refs")]) {
                let id = text(value);
                let nid = format!("{kind}:{id}");
                let field = format!("{kind}_id");
                let Some(n) = g.nodes.iter().rev().find(|n| n["id"] == nid) else {
                    g.claims.push(json!({"risk_id":risk,field:id,"reason":format!("required {kind} evidence missing")}));
                    continue;
                };
                let status = s(&n["data"], "status");
                let ok = if kind == "contract" {
                    matches!(status, "passed" | "success" | "verified")
                } else {
                    matches!(status, "killed" | "timeout" | "covered")
                };
                if !ok {
                    g.claims.push(json!({
                        "risk_id": risk,
                        field: id,
                        "reason": if kind=="contract"{"required contract failed"}else{"required mutation survived"},
                        "status": status,
                    }));
                }
                let assume = if kind == "contract" {
                    vec![]
                } else if ok {
                    vec!["mutation evidence strengthens oracle adequacy"]
                } else {
                    vec!["survived or uncovered mutant weakens oracle adequacy"]
                };
                let mut e = edge(
                    if ok { "supports" } else { "contradicts" },
                    &nid,
                    &rid,
                    &[file, DIFF],
                    if kind == "contract" || !ok {
                        "high"
                    } else {
                        "medium"
                    },
                    &assume,
                );
                e["traceability"]["adapter"] = json!(adapter);
                g.edges.push(e);
            }
        }
    }
    Ok(())
}
