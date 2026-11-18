use super::*;
pub(super) fn debts(x: &Inputs, missing: &[V]) -> V {
    let mut rows = vec![];
    let mut seen = BTreeSet::new();
    let life = items(&x.life["items"]);
    let created = &x.run["created_at"];
    for m in missing {
        let risk = s(m, "risk_id");
        let expected = s(m, "expected_test_ref");
        let id = format!("risk-debt:{risk}:{}", hash(expected));
        let l = life
            .iter()
            .find(|v| {
                alt(v, &["debt_id", "risk_debt_id"], "") == id
                    || (v["risk_id"] == risk
                        && v["debt_type"].as_str().unwrap_or("missing_execution")
                            == "missing_execution")
            })
            .unwrap_or(&V::Null);
        let mut row = project(
            l,
            json!({
                "owner": "unassigned",
                "created_at": created,
                "age_days": 0,
                "evidence_refs": [],
                "recommended_actions": ["Add or restore execution evidence for the required high-risk test."],
                "blocking_profile": ["release"],
                "qeg_refs": [],
                "manual_bridge_refs": ["manual-bb-bridge-requests.jsonl"],
            }),
        );
        for (k, v) in [
            ("debt_id", json!(id)),
            ("risk_debt_id", json!(id)),
            ("risk_id", json!(risk)),
            ("debt_type", json!("missing_execution")),
            ("severity", get(m, "severity", json!("high"))),
            ("expected_test_ref", json!(expected)),
            ("status", json!(alt(l, &["status"], "open"))),
            ("last_seen_at", created.clone()),
            ("sourceRefs", json!(["qeg-export-report.json"])),
            ("source_refs", json!(["qeg-export-report.json"])),
        ] {
            row[k] = v;
        }
        rows.push(row);
        seen.insert(id);
    }
    for l in life {
        let id = alt(l, &["debt_id", "risk_debt_id"], "");
        if id.is_empty() || seen.contains(id) {
            continue;
        }
        let mut v = project(
            l,
            json!({
                "risk_id": "",
                "debt_type": "missing_execution",
                "severity": "medium",
                "expected_test_ref": "",
                "status": "open",
                "owner": "unassigned",
                "created_at": created,
                "last_seen_at": created,
                "age_days": 0,
                "evidence_refs": [],
                "recommended_actions": [],
                "blocking_profile": [],
                "qeg_refs": [],
                "manual_bridge_refs": [],
            }),
        );
        v["debt_id"] = json!(id);
        v["risk_debt_id"] = json!(id);
        v["sourceRefs"] = get(
            l,
            "sourceRefs",
            get(l, "source_refs", json!(["risk-debt-lifecycle.json"])),
        );
        v["source_refs"] = get(l, "source_refs", v["sourceRefs"].clone());
        rows.push(v);
    }
    let mut statuses = BTreeMap::new();
    for row in &rows {
        *statuses.entry(s(row, "status")).or_insert(0) += 1;
    }
    json!({
        "schema_version": "HATE/v1",
        "run_id": x.id(),
        "run_attempt": x.attempt(),
        "profile_version": "HATE/v1",
        "summary": {
            "total_count": rows.len(),
            "open_count": statuses.get("open").unwrap_or(&0),
            "acknowledged_count": statuses.get("acknowledged").unwrap_or(&0),
            "mitigated_count": statuses.get("mitigated").unwrap_or(&0),
            "stale_count": statuses.get("stale").unwrap_or(&0),
            "by_status": statuses,
        },
        "items": rows,
        "debts": rows,
    })
}

pub(super) fn manual(x: &Inputs, m: &V) -> V {
    let risk = s(m, "risk_id");
    let expected = s(m, "expected_test_ref");
    let title = s(m, "risk_title");
    let req = format!(
        "manual-bb:{}:{}:{risk}:{}",
        x.id(),
        x.attempt(),
        hash(expected)
    );
    let sev = m["severity"].as_str().unwrap_or("high");
    let mut refs = vec![
        json!({"id":"qeg-export-report.json","kind":"auto_test","excerpt":"missing_execution"}),
        json!({"id":"risk-debt-register.json","kind":"ops","excerpt":"risk debt for unresolved execution gap"}),
    ];
    let mut seen = BTreeSet::new();
    let mut oracle = BTreeSet::new();
    for r in items(&m["risk_source_refs"]).iter().filter_map(V::as_str) {
        if seen.insert(r.to_owned()) {
            refs.push(json!({"id":r,"kind":"code_review","excerpt":title}));
        }
        if !r.is_empty() {
            oracle.insert(r);
        }
    }
    let mut entities = items(&m["changed_entities"]).to_vec();
    for e in &mut entities {
        let path = s(e, "path").replace('\\', "/");
        if !path.is_empty() && seen.insert(path.clone()) {
            refs.push(json!({"id":path,"kind":"code_review","excerpt":s(e,"entity_id")}));
        }
        e["path"] = json!(path);
    }
    if !expected.is_empty() {
        oracle.insert(expected);
    }
    let mut src = vec!["risk-debt-register.json", "qeg-export-report.json"];
    src.extend(refs.iter().map(|r| s(r, "id")));
    let seed = json!({
        "tc_id": format!("TC-{}",&hash(&req)[..8]),
        "title": format!("Manual confirmation for {}",if title.is_empty(){risk}else{title}),
        "priority": if matches!(sev,"high"|"critical"){"P1"}else{"P2"},
        "primary_view": "black",
        "techniques": ["regression","risk_based"],
        "preconditions": [format!("Changed risk is in scope: {risk}"),format!("Automated execution is missing: {expected}")],
        "steps": ["Exercise the user-visible behavior covered by the missing automated test obligation.","Capture expected and actual results with enough evidence for QEG ingestion."],
        "expected_results": ["Behavior satisfies the referenced risk source and acceptance evidence.","No regression is observed on the changed high-risk path."],
        "oracle": {"type":if oracle.is_empty(){"derived"}else{"specified"},"refs":oracle},
        "estimate_minutes": 10,
        "trace_to": [risk,req,expected],
        "source_refs": refs,
    });
    json!({
        "schema_version": "HATE/v1",
        "record_type": "manual_bb_bridge_request",
        "contract_type": "manual_supplement_request",
        "request_id": req,
        "run_id": x.id(),
        "run_attempt": x.attempt(),
        "source_run_id": x.id(),
        "risk_id": risk,
        "risk_title": title,
        "severity": sev,
        "request_type": "missing_execution_review",
        "gap_type": "no_execution",
        "status": "open",
        "recommended_manual_layer": "manual-scripted",
        "changed_entity_id": entities.first().map(|v|s(v,"entity_id")).unwrap_or(""),
        "changed_entity_ids": entities.iter().map(|v|s(v,"entity_id")).collect::<Vec<_>>(),
        "changed_entities": entities,
        "obligation_id": s(m,"obligation_id"),
        "expected_test_ref": expected,
        "required_test_layers": m["required_test_layers"],
        "required_evidence_kinds": m["required_evidence_kinds"],
        "required_oracle_refs": oracle,
        "evidence_refs": ["qeg-export-report.json","risk-debt-register.json"],
        "sourceRefs": src,
        "source_refs": refs,
        "manual_case_seed": seed,
        "assumptions": [{"id":"ASM-MANUAL-BRIDGE-001","text":"Automated execution evidence is absent, so manual scripted review is required until execution evidence is restored.","severity":"high","impact_on_coverage":"Release evidence remains partial and must not be treated as a waiver."}],
        "confidence": "medium",
        "reason": s(m,"reason"),
        "handoff_policy": {
            "target_suite_id": "manual-bb-harness",
            "primary_view": "black",
            "does_not_override_qeg_verdict": true,
            "manual_execution_evidence_required_for_mitigation": true,
        },
    })
}
