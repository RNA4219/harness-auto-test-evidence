use super::*;
use inputs::{Input, commit, scoped};
use std::sync::LazyLock;

const SCHEMA: &str = include_str!("../../schemas/HATE/v1/qeg-bundle.schema.json");
static DEFINITION: LazyLock<V> = LazyLock::new(|| serde_json::from_str(SCHEMA).unwrap());
static VALIDATOR: LazyLock<jsonschema::Validator> =
    LazyLock::new(|| jsonschema::draft202012::new(&*DEFINITION).unwrap());
pub(crate) fn validator() -> &'static jsonschema::Validator {
    &VALIDATOR
}

fn repr(v: &V) -> String {
    match v {
        V::String(s) => format!("'{s}'"),
        V::Array(a) => format!("[{}]", a.iter().map(repr).collect::<Vec<_>>().join(", ")),
        _ => v.to_string(),
    }
}
pub(super) fn schema_issues(b: &V) -> Vec<V> {
    let mut result = vec![];
    for e in validator().iter_errors(b) {
        let ptr = e.instance_path().as_str();
        let mut path = vec![];
        let mut loc = "$".to_owned();
        for k in ptr.split('/').skip(1) {
            if let Ok(i) = k.parse::<usize>() {
                path.push(json!(i));
                loc.push_str(&format!("[{i}]"));
            } else {
                path.push(json!(k));
                loc.push('.');
                loc.push_str(k)
            }
        }
        let rule = e.kind().keyword();
        let detail = match e.kind() {
            jsonschema::error::ValidationErrorKind::Required { property } => {
                format!("{} is a required property", repr(property))
            }
            _ => format!(
                "expected {rule}={}",
                repr(
                    DEFINITION
                        .pointer(e.schema_path().as_str())
                        .unwrap_or(&V::Null)
                )
            ),
        };
        result.push((
            loc.clone(),
            rule.to_string(),
            json!({
                "issue": "bundle_schema_violation",
                "severity": "high",
                "message": format!("{loc}: {detail}"),
                "validation_path": path,
                "source_refs": ["qeg-bundle.json"],
            }),
        ));
    }
    result.sort_by(|a, b| (&a.0, &a.1).cmp(&(&b.0, &b.1)));
    result.into_iter().map(|(_, _, v)| v).collect()
}
pub(super) fn export_issues(x: &Input) -> Vec<V> {
    let mut result = vec![];
    if x.b["metadata"]["debugOnly"] == true {
        result.push(json!({
            "issue": "diagnostic_only_bundle",
            "severity": "high",
            "message": "The bundle is marked debugOnly and is not formal QEG evidence.",
            "reported_value": true,
            "validation_path": ["metadata","debugOnly"],
            "source_refs": ["qeg-bundle.json"],
        }));
    }
    if let Some(status) = x.r.get("export_status")
        && status != "success"
    {
        let partial = status == "partial";
        result.push(json!({
            "issue": if partial {"partial_export"} else {"invalid_export_status"},
            "severity": if partial {"medium"}else{"high"},
            "message": if partial {"The export report declares partial evidence."}else{"The export report does not declare a recognized export status."},
            "reported_value": status,
            "validation_path": ["export_status"],
            "source_refs": ["qeg-export-report.json"],
        }));
    }
    if let Some(c) = x.r.get("qeg_schema_compatibility") {
        let mut cond = vec![];
        let mut paths = vec![];
        if c.get("valid").is_none() || c["valid"] == false {
            cond.push(if c.get("valid").is_none() {
                "schema validity is missing"
            } else {
                "schema validity is false"
            });
            paths.push(["qeg_schema_compatibility", "valid"]);
        }
        if nonempty(&c["errors"]) {
            cond.push("schema errors are reported");
            paths.push(["qeg_schema_compatibility", "errors"]);
        }
        if !cond.is_empty() {
            result.push(json!({
                "issue": "export_schema_validation_failed",
                "severity": "high",
                "message": format!("The export report does not establish successful QEG schema validation: {}",cond.join("; ")),
                "reported_validation": c,
                "conditions": cond,
                "validation_path": ["qeg_schema_compatibility"],
                "validation_paths": paths,
                "source_refs": ["qeg-export-report.json"],
            }));
        }
    }
    result
}

pub(super) fn precheck(b: &V) -> (Vec<V>, Vec<V>) {
    let mut problems = vec![];
    let mut gaps = vec![];
    for (i, node) in items(&b["nodes"])
        .iter()
        .enumerate()
        .filter(|(_, n)| n["kind"] == "gate_verdict" && s(n, "id").starts_with("hate_precheck:"))
    {
        let d = &node["data"];
        let mut violations = vec![];
        let mut add = |field: &str, issue: &str, message: String| {
            violations.push(json!({"field":field,"issue":issue,"message":message,"validation_path":["nodes",i,"data",field]}))
        };
        for k in ["decision", "exit_code", "qeg_export_allowed"] {
            if d.get(k).is_none() {
                add(k, "precheck_permission_missing", format!("{k} is missing"));
            }
        }
        if let Some(v) = d.get("decision") {
            match v.as_str().unwrap_or("") {
                "ineligible" | "hard_dq" => add(
                    "decision",
                    "precheck_export_denied",
                    format!("decision is {}", v.as_str().unwrap()),
                ),
                "eligible" | "conditional" => (),
                _ => add(
                    "decision",
                    "invalid_precheck_decision",
                    "decision is not recognized".into(),
                ),
            }
        }
        if let Some(v) = d.get("exit_code") {
            match v.as_f64() {
                Some(2.) => add(
                    "exit_code",
                    "precheck_export_denied",
                    "exit_code is 2".into(),
                ),
                Some(0.) => (),
                _ => add(
                    "exit_code",
                    "invalid_precheck_exit_code",
                    "exit_code is neither 0 nor 2".into(),
                ),
            }
        }
        if d["qeg_export_allowed"] == false {
            add(
                "qeg_export_allowed",
                "precheck_export_denied",
                "qeg_export_allowed is false".into(),
            );
        }
        if nonempty(&d["dq_hits"]) {
            add(
                "dq_hits",
                "precheck_export_denied",
                "dq_hits is not empty".into(),
            );
        }
        let mut refs: BTreeSet<_> = sorted_refs(items(&node["sourceRefs"]).iter())
            .into_iter()
            .collect();
        refs.insert("qeg-bundle.json");
        let ctx = json!({
            "precheck_node_id": node["id"],
            "precheck_reasons": d.get("reasons").cloned().unwrap_or(json!([])),
            "source_refs": refs,
        });
        if !violations.is_empty() {
            problems.push(overlay(ctx.clone(),&json!({
                "issue": if violations.iter().any(|v|v["issue"]=="precheck_export_denied"){"precheck_export_not_allowed"}else{"precheck_permission_invalid"},
                "message": format!("HATE precheck does not establish QEG export permission: {}",violations.iter().map(|v|s(v,"message")).collect::<Vec<_>>().join("; ")),
                "violations": violations,
                "precheck_payload": d,
                "validation_path": ["nodes",i,"data"],
            })));
        }
        let declared = items(&d["soft_gaps"]);
        for (j, g) in declared.iter().enumerate() {
            gaps.push(overlay(ctx.clone(),&json!({
                "issue": "precheck_soft_gap",
                "message": g["message"].as_str().filter(|m|!m.trim().is_empty()).unwrap_or("Precheck declares a soft gap."),
                "gap": g,
                "validation_path": ["nodes",i,"data","soft_gaps",j],
            })));
        }
        if d["decision"] == "conditional" && declared.is_empty() {
            gaps.push(overlay(ctx,&json!({
                "issue": "precheck_soft_gap_details_missing",
                "message": "Precheck is conditional, but soft-gap details are missing from the bundle.",
                "gap": null,
                "validation_path": ["nodes",i,"data","soft_gaps"],
            })));
        }
    }
    (problems, gaps)
}

pub(super) fn executed(d: &V) -> bool {
    d["wouldRun"] != true
        && matches!(
            s(d, "status").to_lowercase().as_str(),
            "passed" | "failed" | "error" | "flaky"
        )
}
pub(super) struct Graph {
    pub issues: Vec<V>,
    pub risk_links: bool,
    pub all_executed: bool,
    pub changed_links: bool,
    pub unexecuted: BTreeSet<String>,
    pub refs_ok: bool,
    pub refs_any: bool,
}
pub(super) fn graph(x: &Input) -> Graph {
    let nodes = items(&x.b["nodes"]);
    let edges = items(&x.b["edges"]);
    let mut counts = BTreeMap::new();
    let mut issues = vec![];
    for n in nodes {
        *counts.entry(s(n, "id")).or_insert(0usize) += 1;
    }
    for (id, count) in &counts {
        if id.trim().is_empty() {
            issues.push(
                json!({"issue":"missing_node_id","node_id":id,"message":"node has no usable ID"}),
            );
        } else if *count > 1 {
            issues.push(json!({
                "issue": "duplicate_node_id",
                "node_id": id,
                "count": count,
                "message": format!("node ID is ambiguous: {id}"),
            }));
        }
    }
    let unique: BTreeMap<_, _> = nodes
        .iter()
        .filter(|n| !s(n, "id").trim().is_empty() && counts[s(n, "id")] == 1)
        .map(|n| (s(n, "id"), n))
        .collect();
    let mut tests = BTreeSet::new();
    let mut placements = BTreeSet::new();
    let mut ran = BTreeSet::new();
    let mut changed = false;
    let valid = |v: &V| {
        !items(v).is_empty()
            && items(v)
                .iter()
                .all(|r| r.as_str().is_some_and(|s| !s.trim().is_empty()))
    };
    let refs: Vec<&V> = nodes
        .iter()
        .map(|n| &n["sourceRefs"])
        .chain(edges.iter().map(|e| &e["traceability"]["sourceRefs"]))
        .collect();
    for (i, e) in edges.iter().enumerate() {
        let (k, a, b) = (s(e, "kind"), s(e, "from"), s(e, "to"));
        let src = unique.get(a).map(|n| s(n, "kind"));
        let dst = unique.get(b).map(|n| s(n, "kind"));
        let external =
            k == "decides" && src == Some("gate_verdict") && b == format!("qeg_export:{}", x.id);
        let mut missing = vec![];
        if src.is_none() {
            missing.push("from")
        }
        if dst.is_none() && !external {
            missing.push("to")
        }
        if !missing.is_empty() {
            issues.push(json!({
                "issue": "unresolved_edge_endpoint",
                "edge_index": i,
                "fields": missing,
                "from": a,
                "to": b,
                "message": format!("edge {i} has missing or ambiguous endpoints: {}",missing.join(", ")),
            }));
            continue;
        }
        let ok = match k {
            "touches" => src == Some("changed_code") && dst == Some("risk"),
            "requires_test" => {
                src == Some("risk") && matches!(dst, Some("test" | "test_placement"))
            }
            "evidenced_by" => matches!(
                (src, dst),
                (
                    Some("test"),
                    Some("execution_evidence" | "evidence_artifact")
                ) | (Some("execution_evidence"), Some("evidence_artifact"))
            ),
            "decides" => external,
            _ => true,
        };
        if !ok {
            issues.push(json!({
                "issue": "edge_kind_mismatch",
                "edge_index": i,
                "kind": k,
                "from": a,
                "to": b,
                "message": format!("edge {i} ({k}) connects incompatible node kinds"),
            }));
            continue;
        }
        if !valid(&e["traceability"]["sourceRefs"]) {
            continue;
        }
        match k {
            "requires_test" if dst == Some("test") => {
                tests.insert(b);
            }
            "requires_test" => {
                placements.insert(b);
            }
            "evidenced_by" if dst == Some("execution_evidence") && executed(&unique[b]["data"]) => {
                ran.insert(a);
            }
            "touches" => changed = true,
            _ => (),
        }
    }
    let unexecuted: BTreeSet<_> = tests
        .difference(&ran)
        .copied()
        .chain(placements)
        .map(str::to_owned)
        .collect();
    Graph {
        issues,
        risk_links: !tests.is_empty(),
        all_executed: !tests.is_empty() && unexecuted.is_empty(),
        changed_links: changed,
        unexecuted,
        refs_ok: !refs.is_empty() && refs.iter().all(|r| valid(r)),
        refs_any: refs.iter().any(|r| {
            items(r)
                .iter()
                .any(|v| v.as_str().is_some_and(|s| !s.trim().is_empty()))
        }),
    }
}

pub(super) fn provenance(x: &Input) -> (V, Vec<V>, i64) {
    let mut issues = vec![];
    let mut add = |issue: &str, msg: &str, path: V, source: &str| {
        issues.push(
            json!({"issue":issue,"message":msg,"validation_path":path,"source_refs":[source]}),
        )
    };
    let m = &x.b["metadata"];
    let id = !s(m, "runId").trim().is_empty();
    let timestamp = |v: &V| {
        v.as_str().is_some_and(|s| {
            matches!(s.as_bytes().get(10), Some(b'T' | b't'))
                && chrono::DateTime::parse_from_rfc3339(s).is_ok()
        })
    };
    let date = timestamp(&m["createdAt"]);
    let sha = commit(&x.r["commit_sha"]);
    let b = "qeg-bundle.json";
    let r = "qeg-export-report.json";
    if !id {
        add(
            "missing_run_id",
            "bundle metadata requires a nonblank runId",
            json!(["metadata", "runId"]),
            b,
        )
    }
    if !date {
        add(
            "invalid_created_at",
            "createdAt requires an RFC 3339 date-time with timezone",
            json!(["metadata", "createdAt"]),
            b,
        )
    }
    if let Some(v) = x.r.get("created_at")
        && !timestamp(v)
    {
        add(
            "invalid_created_at",
            "created_at requires an RFC 3339 date-time with timezone",
            json!(["created_at"]),
            r,
        )
    }
    if !sha {
        add(
            "invalid_commit_sha",
            "commit_sha requires a 7–64 character hexadecimal commit ID",
            json!(["commit_sha"]),
            r,
        )
    }
    if let Some(v) = m.get("commitSha")
        && !commit(v)
    {
        add(
            "invalid_commit_sha",
            "declared commit requires a 7–64 character hexadecimal commit ID",
            json!(["metadata", "commitSha"]),
            b,
        )
    }
    let nodes = items(&x.b["nodes"]);
    for (i, n) in nodes
        .iter()
        .enumerate()
        .filter(|(_, n)| scoped(s(n, "kind")))
    {
        for (d, p) in [
            (&n["data"], json!(["nodes", i, "data", "commit_sha"])),
            (
                &n["data"]["ci"],
                json!(["nodes", i, "data", "ci", "commit_sha"]),
            ),
        ] {
            if (p.as_array().unwrap().len() == 4 || n["kind"] == "run")
                && let Some(v) = d.get("commit_sha")
                && !commit(v)
            {
                add(
                    "invalid_commit_sha",
                    "declared commit requires a 7–64 character hexadecimal commit ID",
                    p,
                    b,
                )
            }
        }
    }
    let (mut count, mut hashes) = (0, 0);
    for (i, n) in nodes
        .iter()
        .enumerate()
        .filter(|(_, n)| n["kind"] == "evidence_artifact")
    {
        count += 1;
        let v = s(&n["data"], "sha256");
        let h = v.strip_prefix("sha256:").unwrap_or(v);
        if h.len() == 64 && h.bytes().all(|b| b.is_ascii_hexdigit()) {
            hashes += 1
        } else {
            add(
                "invalid_artifact_sha256",
                "artifact sha256 requires 64 hexadecimal characters with optional sha256: prefix",
                json!(["nodes", i, "data", "sha256"]),
                b,
            )
        }
    }
    let score = if !id {
        0
    } else if issues.is_empty() && count > 0 {
        3
    } else {
        1
    };
    (
        json!({
            "has_run_id": id,
            "has_created_at": date,
            "has_commit_sha": sha,
            "has_artifact_hash": hashes>0,
            "artifact_count": count,
            "valid_artifact_hash_count": hashes,
            "provenance_valid": issues.is_empty(),
            "artifact_content_verified": false,
            "tamper_resistance_verified": false,
        }),
        issues,
        score,
    )
}
