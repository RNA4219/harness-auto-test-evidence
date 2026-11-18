use super::*;
use inputs::Input;
mod adapters;

fn resolver(x: &Input) -> V {
    let mut rows = vec![];
    let form = |v: &str| {
        let norm = v.replace('\\', "/");
        let url = v.starts_with("http://") || v.starts_with("https://");
        json!({
            "original": v,
            "normalized": if v.starts_with("fixture:/"){v}else{&norm},
            "root_kind": if v.starts_with("fixture:/"){"workspace"}else if url{"url"}else if v.chars().take(3).any(|c|c==':'){"windows"}else{"package"},
            "resolution_status": if norm.starts_with("http://")||norm.starts_with("https://")||norm.split('/').any(|p|p==".."){"unsafe"}else if v.is_empty(){"unresolved"}else{"resolved"},
        })
    };
    let nodes = items(&x.b["nodes"]);
    let refs = sorted_refs(
        items(&x.b["metadata"]["inputArtifacts"])
            .iter()
            .filter_map(|a| a.get("path").filter(|v| nonempty(v)))
            .chain(nodes.iter().flat_map(|n| items(&n["sourceRefs"])))
            .chain(
                items(&x.b["edges"])
                    .iter()
                    .flat_map(|e| items(&e["traceability"]["sourceRefs"])),
            ),
    );
    for r in refs {
        rows.push(overlay(
            form(r),
            &json!({"entry_type":"source_ref","source_refs":[r]}),
        ));
    }
    for n in nodes.iter().filter(|n| n["kind"] == "evidence_artifact") {
        let d = &n["data"];
        let path = s(d, "path");
        if path.is_empty() {
            continue;
        }
        rows.push(overlay(
            form(path),
            &json!({
                "entry_type": "artifact_path",
                "artifact_id": s(n,"id").trim_start_matches("artifact:"),
                "artifact_kind": s(d,"kind"),
                "artifact_role": s(d,"artifact_role"),
                "sha256": s(d,"sha256"),
                "source_refs": n.get("sourceRefs").cloned().unwrap_or(json!([])),
            }),
        ));
    }
    rows.sort_by(|a, b| {
        ["entry_type", "original", "artifact_id"]
            .map(|k| s(a, k))
            .cmp(&["entry_type", "original", "artifact_id"].map(|k| s(b, k)))
    });
    let count = |k: &str, v: &str| rows.iter().filter(|r| r[k] == v).count();
    json!({
        "schema_version": "HATE/v1",
        "record_type": "artifact_resolution",
        "run_id": x.id,
        "entries": rows,
        "summary": {
            "entry_count": rows.len(),
            "unsafe_count": count("resolution_status","unsafe"),
            "unresolved_count": count("resolution_status","unresolved"),
            "artifact_path_count": count("entry_type","artifact_path"),
            "source_ref_count": count("entry_type","source_ref"),
        },
    })
}
struct Checks {
    graph: analysis::Graph,
    prov: V,
    prov_issues: Vec<V>,
    prov_score: i64,
    export: Vec<V>,
    schema: Vec<V>,
    perm: Vec<V>,
    gaps: Vec<V>,
}
impl Checks {
    fn new(x: &Input) -> Self {
        let (prov, prov_issues, prov_score) = analysis::provenance(x);
        let (perm, gaps) = analysis::precheck(&x.b);
        Self {
            graph: analysis::graph(x),
            prov,
            prov_issues,
            prov_score,
            export: analysis::export_issues(x),
            schema: analysis::schema_issues(&x.b),
            perm,
            gaps,
        }
    }
}
fn doctor(x: &Input, c: &Checks, retry: &V, resolver: &V) -> V {
    let mut findings = vec![];
    let mut categories = BTreeMap::new();
    let mut severity_counts = BTreeMap::new();
    let mut blocking = BTreeSet::new();
    let mut add = |cat: &str, severity: &str, issue: &V| {
        let (code, fix) = match cat {
            "schema" => (
                "SCH",
                "Validate generated artifacts against the schema registry.",
            ),
            "qeg_fixture" => (
                "QEG",
                "Review QEG bundle/report sourceRefs and unsupported claims.",
            ),
            "artifact_safety" => (
                "ART",
                "Redact, quarantine, or replace unsafe artifact evidence.",
            ),
            "path" => (
                "PATH",
                "Normalize or remove unsafe path references before export.",
            ),
            "provenance" => (
                "PROV",
                "Restore valid run, commit, timestamp, and declared artifact SHA256 evidence.",
            ),
            "retry" => (
                "RETRY",
                "Review retry order, matrix grouping, and shard completeness using the original execution records.",
            ),
            "precheck" => (
                "PRE",
                "Review the original precheck reasons and permission conditions before regenerating the bundle from corrected evidence.",
            ),
            _ => (
                "EXP",
                "Review the original export status and schema validation report, then regenerate formal evidence from corrected source artifacts.",
            ),
        };
        let severity = issue["severity"].as_str().unwrap_or(severity);
        let high = matches!(severity, "critical" | "high");
        if high {
            blocking.insert(cat.to_owned());
        }
        *categories.entry(cat.to_owned()).or_insert(0) += 1;
        *severity_counts.entry(severity.to_owned()).or_insert(0) += 1;
        findings.push(overlay(
            json!({
                "finding_code": format!("HATE-DOC-{code}-001"),
                "taxonomy_version": "doctor-taxonomy-2026-06-29",
                "blocking": high,
                "remediation": fix,
                "finding_id": format!("doctor:{cat}:{}",findings.len()+1),
                "category": cat,
                "severity": severity,
            }),
            issue,
        ));
    };
    for (cat, sev, rows) in [
        ("schema", "high", c.schema.as_slice()),
        ("qeg_fixture", "high", c.graph.issues.as_slice()),
        ("provenance", "high", c.prov_issues.as_slice()),
        ("export", "high", c.export.as_slice()),
        ("retry", "medium", items(&retry["issues"])),
        ("precheck", "high", c.perm.as_slice()),
        ("precheck", "medium", c.gaps.as_slice()),
    ] {
        for r in rows {
            let mut issue = r.clone();
            if matches!(cat, "qeg_fixture" | "retry") {
                issue["source_refs"] = json!(["qeg-bundle.json"])
            }
            add(cat, sev, &issue);
        }
    }
    for (k, cat, sev, default) in [
        (
            "unsupportedClaims",
            "qeg_fixture",
            "high",
            "unsupported claim",
        ),
        (
            "excludedArtifacts",
            "artifact_safety",
            "critical",
            "artifact excluded",
        ),
    ] {
        for row in items(&x.r[k]) {
            add(
                cat,
                sev,
                &json!({"message":row["reason"].as_str().unwrap_or(default),"source_refs":["qeg-export-report.json"]}),
            );
        }
    }
    if !c.graph.refs_ok {
        add(
            "qeg_fixture",
            "high",
            &json!({
                "message": if nonempty(&x.b["nodes"])||nonempty(&x.b["edges"]){"node or edge has missing or blank sourceRefs"}else{"graph has no nodes or edges"},
                "source_refs": ["qeg-bundle.json"],
            }),
        );
    }
    for entry in items(&resolver["entries"])
        .iter()
        .filter(|e| e["resolution_status"] == "unsafe")
    {
        add(
            "path",
            "high",
            &json!({"message":"unsafe source reference path","source_refs":[entry["original"]]}),
        );
    }
    json!({
        "schema_version": "HATE/v1",
        "record_type": "doctor_report",
        "run_id": x.id,
        "run_attempt": x.attempt,
        "findings": findings,
        "summary": {
            "finding_count": findings.len(),
            "blocking_categories": blocking,
            "by_category": categories,
            "by_severity": severity_counts,
            "taxonomy_version": "doctor-taxonomy-2026-06-29",
        },
        "release_gate_override": false,
        "publish_gate_override": false,
    })
}

fn scores(x: &Input, c: &Checks, retry: &V) -> (V, Vec<V>, Vec<V>, f64, &'static str) {
    let nodes = items(&x.b["nodes"]);
    let edges = items(&x.b["edges"]);
    let has = |k: &str| nodes.iter().any(|n| n["kind"] == k);
    let tests = has("test");
    let exec = nodes
        .iter()
        .any(|n| n["kind"] == "execution_evidence" && analysis::executed(&n["data"]));
    let cov = has("coverage");
    let ctx = nodes.iter().any(|n| {
        n["kind"] == "coverage"
            && (nonempty(&n["data"]["contexts"]) || nonempty(&n["data"]["branch_hits"]))
    });
    let unsupported =
        nonempty(&x.b["completeness"]["unsupportedClaims"]) || nonempty(&x.r["unsupportedClaims"]);
    let missing = nonempty(&x.r["missing_execution"]);
    let rs = &retry["summary"];
    let aggs = items(&retry["aggregates"]);
    let flaky = nonempty(&rs["flaky_count"]) || nonempty(&rs["declared_flaky_count"]);
    let inconclusive = nonempty(&rs["inconclusive_count"]);
    let contracts = has("contract_evidence") || has("mutation_evidence");
    let kinds: BTreeSet<_> = nodes
        .iter()
        .map(|n| (s(n, "kind"), &n["data"]))
        .filter(|(k, d)| {
            matches!(
                *k,
                "execution_evidence"
                    | "coverage"
                    | "finding"
                    | "evidence_artifact"
                    | "contract_evidence"
                    | "mutation_evidence"
            ) && (*k != "execution_evidence" || analysis::executed(d))
        })
        .map(|(k, _)| k)
        .collect();
    let b = "qeg-bundle.json";
    let r = "qeg-export-report.json";
    let g = &c.graph;
    let source = |v: &[&str]| json!(v);
    let data = [
        (c.prov_score, c.prov.clone(), source(&[b, r])),
        (
            if !tests || flaky {
                0
            } else if missing || aggs.is_empty() || inconclusive {
                1
            } else if aggs.iter().all(|a| {
                a["aggregate_status"] == "stable_passed" && items(&a["attempt_results"]).len() >= 2
            }) {
                5
            } else {
                3
            },
            json!({
                "has_tests": tests,
                "has_execution": exec,
                "missing_execution": missing,
                "aggregate_statuses": aggs.iter().map(|a|&a["aggregate_status"]).collect::<Vec<_>>(),
                "flaky_count": rs["flaky_count"],
                "declared_flaky_count": rs["declared_flaky_count"],
                "inconclusive_count": rs["inconclusive_count"],
            }),
            source(&[b, r]),
        ),
        (
            if g.refs_ok && g.issues.is_empty() && g.risk_links {
                if g.all_executed { 5 } else { 3 }
            } else {
                i64::from(g.refs_any)
            },
            json!({
                "source_refs_complete": g.refs_ok,
                "has_risk_edges": edges.iter().any(|e|matches!(s(e,"kind"),"touches"|"requires_test")),
                "has_execution": exec,
                "graph_integrity_ok": g.issues.is_empty(),
                "has_risk_test_links": g.risk_links,
                "all_risk_tests_executed": g.all_executed,
                "unexecuted_risk_tests": g.unexecuted,
            }),
            source(&[b, "evidence-map.json"]),
        ),
        (
            if contracts {
                5
            } else if tests && exec {
                3
            } else {
                1
            },
            json!({"has_tests":tests,"has_execution":exec,"has_contract_or_mutation":contracts}),
            source(&[b]),
        ),
        (
            if g.changed_links { 5 } else { 1 },
            json!({
                "has_changed_code": has("changed_code"),
                "has_risk_edges": edges.iter().any(|e|matches!(s(e,"kind"),"touches"|"requires_test")),
                "has_changed_risk_links": g.changed_links,
            }),
            source(&[b]),
        ),
        (
            if ctx {
                5
            } else if cov {
                3
            } else {
                0
            },
            json!({"has_coverage":cov,"has_context_or_branch_coverage":ctx}),
            source(&[b]),
        ),
        (
            if kinds.len() >= 3 {
                5
            } else if exec && cov {
                3
            } else {
                i64::from(!kinds.is_empty())
            },
            json!({"signal_kinds":kinds,"signal_kind_count":kinds.len()}),
            source(&[b]),
        ),
        (
            if unsupported { 1 } else { 3 },
            json!({"has_unsupported_claims":unsupported,"export_status":s(&x.r,"export_status")}),
            source(&[r, "profile-report.json"]),
        ),
    ];
    let mut dims = json!({});
    let mut sum = 0;
    let mut reasons = vec![];
    let mut signals = vec![];
    for ((dimension, w), (score, observed, refs)) in WEIGHTS.into_iter().zip(data) {
        dims[dimension] = json!(score);
        sum += w * score;
        let id = format!("signal:{dimension}:{score}");
        let rationale = match score {
            0 => "required signal is absent",
            1 => "only weak or incomplete signal is present",
            3 => "required signal is present at the base trust level",
            _ => "strong corroborating signal is present",
        };
        reasons
            .push(json!({"dimension":dimension,"reason_ref":id,"score":score,"source_refs":refs}));
        signals.push(json!({
            "signal_id": id,
            "dimension": dimension,
            "score": score,
            "observed": observed,
            "rationale": format!("{dimension} score {score}: {rationale}"),
            "source_refs": refs,
        }));
    }
    let confidence = if !c.prov_issues.is_empty()
        || !c.perm.is_empty()
        || !c.schema.is_empty()
        || c.export.iter().any(|v| v["severity"] == "high")
    {
        "low"
    } else if !c.export.is_empty()
        || !c.gaps.is_empty()
        || inconclusive
        || missing
        || nonempty(&x.r["unsupportedClaims"])
        || nonempty(&x.r["excludedArtifacts"])
        || [&x.r["completeness"], &x.b["completeness"]]
            .iter()
            .any(|v| {
                [
                    "partial",
                    "unsupportedClaims",
                    "excludedArtifacts",
                    "parserFailures",
                ]
                .iter()
                .any(|k| nonempty(&v[k]))
            })
    {
        "medium"
    } else {
        "high"
    };
    (dims, reasons, signals, sum as f64 / 500., confidence)
}

pub(super) fn run(call: &Invocation, x: &Input) -> Result<V> {
    let checks = Checks::new(x);
    let retry = execution::retry(x);
    let resolver = resolver(x);
    let doc = doctor(x, &checks, &retry, &resolver);
    let (registry, manifest, conform) = adapters::reports(x, &doc, &resolver);
    let profile = call
        .values
        .get("profile")
        .and_then(V::as_str)
        .unwrap_or("default");
    let created = x.b["metadata"]["createdAt"]
        .as_str()
        .unwrap_or(s(&x.r, "created_at"));
    let prof = crate::p0a::build_profile_report(
        profile,
        &x.id,
        &x.attempt,
        s(&x.r, "commit_sha"),
        created,
    )?;
    let out = call.path("out");
    let write = |name: &str, v: &V| write_json(&out.join(name), v);
    if call.command == "doctor" {
        for (name, v) in [
            ("profile-report.json", &prof),
            ("doctor-report.json", &doc),
            ("adapter-registry.json", &registry),
            ("adapter-capability-manifest.json", &manifest),
            ("adapter-conformance-report.json", &conform),
        ] {
            write(name, v)?;
        }
        return Ok(json!({
            "doctor_status": if nonempty(&doc["findings"]){"partial"}else{"success"},
            "exit_code": 0,
            "generated": ["doctor-report.json","profile-report.json","adapter-registry.json","adapter-capability-manifest.json","adapter-conformance-report.json"],
            "doctor_findings": doc["summary"]["finding_count"],
            "conformance_status": conform["summary"]["overall_status"],
            "publish_gate_override": false,
        }));
    }
    let (dims, reason, signals, weighted, confidence) = scores(x, &checks, &retry);
    let common = json!({"schema_version":"HATE/v1","run_id":x.id,"run_attempt":x.attempt,"rubric_version":"aete-rubric-2026-06-28","profile_version":prof["profile_version"],"profile":profile,"dimensions":dims,"dimension_weights":WEIGHTS.into_iter().collect::<BTreeMap<_,_>>(),"aggregation_method":"weighted_mean","weighted_score":weighted,"reason_refs":reason,"release_gate_override":false,"publish_gate_override":false});
    let score = overlay(
        common.clone(),
        &json!({
            "record_type": "aete_score",
            "commit_sha": s(&x.r,"commit_sha"),
            "source_tool": "harness-auto-test-evidence",
            "source_version": call.values.get("source_version").and_then(V::as_str).filter(|v|!v.is_empty()).unwrap_or(env!("CARGO_PKG_VERSION")),
            "calibration_status": "uncalibrated",
            "score_confidence": confidence,
            "subject": {"subject_type":"run","subject_id":format!("run:{}:{}",x.id,x.attempt)},
            "dimension_signals": signals,
            "source_refs": [x.bundle_ref,x.report_ref],
        }),
    );
    let signal = overlay(
        common,
        &json!({
            "record_type": "aete_signal_report",
            "signals": signals,
            "deterministic": true,
            "source_refs": ["qeg-bundle.json","qeg-export-report.json","profile-report.json"],
        }),
    );
    let id = execution::identity(x);
    let mut generated = vec![];
    for (name, v) in [
        ("aete-score", &score),
        ("aete-signal-report", &signal),
        ("profile-report", &prof),
        ("artifact-resolver-map", &resolver),
        ("doctor-report", &doc),
        ("adapter-registry", &registry),
        ("adapter-capability-manifest", &manifest),
        ("adapter-conformance-report", &conform),
        ("canonical-identity-index", &id),
        ("retry-aggregation", &retry),
    ] {
        let filename = format!("{name}.json");
        write(&filename, v)?;
        generated.push(filename);
    }
    let summary = format!(
        "# P1a Trust Summary\n\n- Run: `{}` attempt `{}`\n- Weighted score: `{weighted:.3}`\n- Score confidence: `{confidence}`\n- Calibration: `uncalibrated`\n- Doctor findings: {}\n\nHATE trust hardening is advisory evidence only.\n`publish_gate_override=false` and `release_gate_override=false`.\n",
        x.id, x.attempt, doc["summary"]["finding_count"]
    );
    std::fs::write(out.join("trust-summary.md"), summary)?;
    generated.push("trust-summary.md".into());
    let mut result = json!({
        "trust_status": if nonempty(&doc["findings"]){"partial"}else{"success"},
        "exit_code": 0,
        "weighted_score": weighted,
        "score_confidence": confidence,
        "doctor_findings": doc["summary"]["finding_count"],
        "publish_gate_override": false,
    });
    if call.command == "replay" {
        let recalc = digest(&json!({
            "aete_score": score,
            "aete_signal_report": signal,
            "profile_report": prof,
            "resolver_summary": resolver["summary"],
            "doctor_summary": doc["summary"],
            "conformance_summary": conform["summary"],
            "identity_summary": id["summary"],
            "retry_summary": retry["summary"],
        }));
        let hashes: BTreeMap<_, _> = [
            ("aete_score", &score),
            ("aete_signal_report", &signal),
            ("profile_report", &prof),
            ("artifact_resolver_map", &resolver),
            ("doctor_report", &doc),
            ("adapter_conformance_report", &conform),
            ("canonical_identity_index", &id),
            ("retry_aggregation", &retry),
        ]
        .map(|(k, v)| (k, digest(v)))
        .into_iter()
        .collect();
        write(
            "replay-report.json",
            &json!({
                "schema_version": "HATE/v1",
                "record_type": "replay_report",
                "profile": profile,
                "bundle_ref": x.bundle_ref,
                "report_ref": x.report_ref,
                "recalculation_hash": recalc,
                "deterministic_inputs": hashes,
                "weighted_score": weighted,
                "doctor_findings": doc["summary"]["finding_count"],
                "retry_aggregate_count": retry["summary"]["aggregate_count"],
                "deterministic": true,
                "release_gate_override": false,
                "publish_gate_override": false,
            }),
        )?;
        generated.push("replay-report.json".into());
        result["recalculation_hash"] = json!(recalc);
    }
    result["generated"] = json!(generated);
    Ok(result)
}
