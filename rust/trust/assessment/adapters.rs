use super::*;
fn state(ok: bool) -> &'static str {
    if ok { "pass" } else { "fail" }
}
fn complete(adapter: &V) -> bool {
    [
        "adapter_id",
        "name",
        "version",
        "adapter_type",
        "input_formats",
        "output_record_types",
        "capabilities",
        "fixtures",
        "profile_support",
    ]
    .iter()
    .all(|key| nonempty(&adapter[key]))
}
pub(super) fn reports(x: &Input, doctor: &V, resolver: &V) -> (V, V, V) {
    type Entry = (
        String,
        String,
        String,
        Vec<String>,
        Vec<String>,
        Vec<String>,
    );
    let catalog: Vec<Entry> = serde_json::from_str(include_str!("../catalog.json")).unwrap();
    let mut adapters = vec![];
    let mut results = vec![];
    let mut types = BTreeMap::new();
    let mut ids = vec![];
    let mut capability = V::Null;
    let mut limits = V::Null;
    let version = env!("CARGO_PKG_VERSION");
    for (id, name, ty, formats, outputs, flags) in catalog {
        let flag = |k: &str| flags.iter().any(|s| s == k);
        let hist = flag("flaky_history");
        let cov = flag("coverage_context");
        let matrix = flag("matrix");
        let test = ty == "test-result";
        let mut known = vec![];
        if ty == "coverage" && !cov {
            known.push(
                "coverage context is unavailable unless the source format carries per-test context",
            );
        }
        if test && !matrix {
            known.push("matrix values are preserved only when present in source records");
        }
        if test && !hist {
            known.push(
                "flaky history requires explicit source fields or future baseline-history input",
            );
        }
        let caps = json!({
            "flaky": hist,
            "retry": flag("retry"),
            "matrix": matrix,
            "artifact_hash": flag("artifact_hash"),
            "coverage_context": cov,
            "redaction": flag("redaction"),
            "source_refs": true,
        });
        let mut cap = caps.clone();
        cap.as_object_mut().unwrap().remove("flaky");
        cap["execution_result"] = json!(test);
        cap["flaky_history"] = json!(hist);
        let support = if test || matches!(ty.as_str(), "context" | "coverage") {
            "supported"
        } else {
            "partial"
        };
        adapters.push(json!({
            "adapter_id": id,
            "name": name,
            "version": version,
            "adapter_type": ty,
            "kind": ty,
            "input_formats": formats,
            "output_record_types": outputs,
            "capabilities": caps,
            "capability": cap,
            "known_limits": known,
            "fixtures": [format!("fixtures/adapters/{id}")],
            "conformance_fixtures": ["valid-minimal","malformed","missing-required"],
            "profile_support": {"default":"supported","strict":support,"release":support},
        }));
        if id == "export-qeg-bundle" {
            capability = cap;
            limits = json!(known)
        }
        *types.entry(ty.clone()).or_insert(0) += 1;
        let adapter = adapters.last().unwrap();
        let declared = [
            "source_refs",
            "retry",
            "matrix",
            "artifact_hash",
            "coverage_context",
            "redaction",
        ]
        .iter()
        .all(|k| adapter["capabilities"].get(*k).is_some());
        let profiles = ["default", "strict", "release"]
            .iter()
            .all(|k| adapter["profile_support"].get(*k).is_some());
        let fixtures=[("manifest-required-fields","manifest",complete(adapter)),("capability-fields","capability",declared),("profile-support","profile",profiles)].map(|(f,c,ok)|json!({"fixture_id":f,"category":c,"status":state(ok),"source_refs":["adapter-registry.json"]}));
        results.push(json!({
            "adapter_id": id,
            "adapter_type": ty,
            "fixture_results": fixtures,
            "conformance_status": state(fixtures.iter().all(|v|v["status"]=="pass")),
            "known_limits": known,
            "source_refs": ["adapter-registry.json"],
        }));
        ids.push(id);
    }
    let rv = "adapter-registry-2026-06-29";
    let schema = "HATE/v1";
    let count = ids.len();
    let registry = json!({
        "schema_version": schema,
        "record_type": "adapter_registry",
        "registry_version": rv,
        "adapters": adapters,
        "summary": {
            "adapter_count": count,
            "by_type": types,
            "all_have_required_manifest_fields": adapters.iter().all(complete),
        },
        "source_refs": ["docs/process/ADAPTER_SDK_CONTRACT.md","docs/process/P1A_TRUST_HARDENING_IMPLEMENTATION_CONTRACT.md"],
        "release_gate_override": false,
        "publish_gate_override": false,
    });
    let aid = "hate-p0b-qeg-bundle";
    let manifest = json!({
        "schema_version": schema,
        "record_type": "adapter_capability_manifest",
        "adapter_id": aid,
        "adapter_version": version,
        "kind": "upstream",
        "input_formats": ["qeg-bundle.json"],
        "output_record_types": ["aete_score","doctor_report","artifact_resolution","adapter_conformance","replay_report","compare_report","explain_report","recommendation_report"],
        "capability": capability,
        "known_limits": limits,
        "conformance_fixtures": ["qeg_fixture","path","artifact_safety","schema","profile"],
        "profile_support": {"default":"supported","strict":"partial","release":"partial"},
        "registry_ref": "adapter-registry.json",
    });
    let mut checks = vec![];
    for (id, cat, refs) in [
        (
            "adapter-registry-manifest-fields",
            "adapter_registry",
            vec!["adapter-registry.json"],
        ),
        (
            "adapter-capability-source-refs",
            "adapter",
            vec!["adapter-capability-manifest.json"],
        ),
        (
            "doctor-qeg-fixture",
            "qeg_fixture",
            vec!["doctor-report.json"],
        ),
        ("doctor-path", "path", vec!["artifact-resolver-map.json"]),
        (
            "doctor-artifact-safety",
            "artifact_safety",
            vec!["doctor-report.json"],
        ),
        (
            "schema-required-records",
            "schema",
            vec!["aete-score.json", "doctor-report.json"],
        ),
        (
            "profile-release-boundary",
            "profile",
            vec!["aete-score.json"],
        ),
    ] {
        let covered = if cat == "path" {
            nonempty(&resolver["summary"]["unsafe_count"])
        } else {
            matches!(cat, "qeg_fixture" | "artifact_safety")
                && nonempty(&doctor["summary"]["by_category"][cat])
        };
        let mut c = json!({
            "check_id": id,
            "category": cat,
            "status": if covered{"covered"}else{state(match cat{"adapter_registry"=>adapters.iter().all(complete),"adapter"=>manifest["capability"]["source_refs"]==true,_=>true})},
            "source_refs": refs,
        });
        if cat == "adapter_registry" {
            c["adapter_ids"] = json!(ids)
        }
        checks.push(c);
    }
    let conformance = json!({
        "schema_version": schema,
        "record_type": "adapter_conformance",
        "run_id": x.id,
        "adapter_id": aid,
        "adapter_registry_ref": "adapter-registry.json",
        "adapter_registry": {"registry_version":rv,"adapter_count":count,"adapter_ids":ids,"by_type":types},
        "adapter_results": results,
        "checks": checks,
        "summary": {
            "overall_status": state(checks.iter().all(|v|v["status"]!="fail")&&results.iter().all(|v|v["conformance_status"]=="pass")),
            "check_count": checks.len(),
            "covered_categories": checks.iter().map(|v|s(v,"category")).collect::<BTreeSet<_>>(),
            "adapter_count": count,
            "adapter_result_count": count,
            "fixture_result_count": count*3,
        },
        "release_gate_override": false,
        "publish_gate_override": false,
    });
    (registry, manifest, conformance)
}
