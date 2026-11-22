use super::integers::{integer, json_integer};
use super::*;
use bigdecimal::{Zero, num_bigint::BigInt};
use inputs::Input;

fn components(d: &V) -> (V, String) {
    let id = s(d, "canonical_test_id");
    let (prefix, rest) = id.split_once(':').unwrap_or(("", id));
    let parts: Vec<_> = rest.split("::").collect();
    let select = |k: &str, default: &str| {
        d[k].as_str()
            .filter(|s| !s.is_empty())
            .unwrap_or(default)
            .to_owned()
    };
    let framework = select("framework", prefix);
    let raw = select("file", parts[0]);
    let file = if raw.starts_with("fixture:/") {
        raw
    } else {
        raw.replace('\\', "/")
    };
    let classname = select(
        "classname",
        &select("class_name", if parts.len() >= 3 { parts[1] } else { "" }),
    );
    let name = select(
        "name",
        &parts[if parts.len() >= 3 {
            2
        } else if parts.len() >= 2 {
            1
        } else {
            0
        }..]
            .join("::"),
    );
    let mapping = |k: &str, alias: &str| {
        [&d[k], &d[alias]]
            .into_iter()
            .find(|v| v.is_object() && nonempty(v))
            .cloned()
            .unwrap_or(json!({}))
    };
    let params = mapping("parameters", "params");
    let mut canonical = format!("{framework}:{file}::{classname}::{name}");
    if nonempty(&params) {
        canonical += &format!("::{}", &digest(&params)[..12]);
    }
    (
        json!({
            "framework": framework,
            "package": s(d,"package"),
            "file": file,
            "classname": classname,
            "name": name,
            "parameters": params,
            "matrix": mapping("matrix","matrix_values"),
        }),
        canonical,
    )
}
pub(super) fn identity(x: &Input) -> V {
    let mut seen = BTreeSet::new();
    let mut duplicates = BTreeSet::new();
    let mut rows = vec![];
    for n in items(&x.b["nodes"]).iter().filter(|n| n["kind"] == "test") {
        let d = &n["data"];
        let (components, canonical) = components(d);
        let old = s(d, "canonical_test_id");
        if !seen.insert(canonical.clone()) {
            duplicates.insert(canonical.clone());
        }
        let alias = if !old.is_empty() && old != canonical {
            json!([{"previous_id":old,"reason":"path_normalization","valid_from":x.id}])
        } else {
            json!([])
        };
        rows.push(json!({
            "identity_id": format!("identity:{}",&digest(&json!(canonical))[..16]),
            "test_node_id": s(n,"id"),
            "canonical_test_id": old,
            "normalized_canonical_test_id": canonical,
            "identity_components": components,
            "aliases": alias,
            "source_refs": n.get("sourceRefs").cloned().unwrap_or(json!([])),
        }));
    }
    json!({
        "schema_version": "HATE/v1",
        "record_type": "canonical_identity_index",
        "run_id": x.id,
        "summary": {
            "identity_count": rows.len(),
            "duplicate_normalized_ids": duplicates,
            "has_duplicates": !duplicates.is_empty(),
        },
        "identities": rows,
    })
}
#[derive(Default)]
struct Group<'a> {
    matrix: V,
    tests: BTreeSet<&'a str>,
    exec: BTreeMap<&'a str, &'a V>,
}

pub(super) fn retry(x: &Input) -> V {
    let nodes = items(&x.b["nodes"]);
    let mut counts = BTreeMap::new();
    for n in nodes {
        *counts.entry(s(n, "id")).or_insert(0) += 1;
    }
    let unique: BTreeMap<_, _> = nodes
        .iter()
        .filter(|n| !s(n, "id").trim().is_empty() && counts[s(n, "id")] == 1)
        .map(|n| (s(n, "id"), n))
        .collect();
    let mut links: BTreeMap<&str, BTreeSet<&str>> = BTreeMap::new();
    for e in items(&x.b["edges"]) {
        let a = s(e, "from");
        let b = s(e, "to");
        if e["kind"] == "evidenced_by"
            && unique.get(a).is_some_and(|n| n["kind"] == "test")
            && unique
                .get(b)
                .is_some_and(|n| n["kind"] == "execution_evidence")
        {
            links.entry(a).or_default().insert(b);
        }
    }
    let mut groups = BTreeMap::<(String, String), Group>::new();
    for (&id, &n) in unique.iter().filter(|(_, n)| n["kind"] == "test") {
        let (c, mut canon) = components(&n["data"]);
        if ["framework", "file", "name"]
            .iter()
            .any(|k| s(&c, k).is_empty())
        {
            canon = format!("test-node:{id}");
        }
        let linked = links.get(id);
        let executions: Vec<_> = linked
            .map(|list| list.iter().map(|id| Some(unique[id])).collect())
            .unwrap_or_else(|| vec![None]);
        for e in executions {
            let matrix = e.map_or_else(
                || c["matrix"].clone(),
                |e| overlay(c["matrix"].clone(), &e["data"]["matrix"]),
            );
            let group_id = if nonempty(&matrix) {
                format!("matrix:{}", &digest(&matrix)[..12])
            } else {
                "matrix:default".into()
            };
            let g = groups.entry((canon.clone(), group_id)).or_default();
            g.matrix = matrix;
            g.tests.insert(id);
            if let Some(e) = e {
                g.exec.insert(s(e, "id"), e);
            }
        }
    }
    let rows: Vec<_> = groups
        .into_iter()
        .map(|((canonical, mid), g)| aggregate(x, canonical, mid, g))
        .collect();
    let mut issues = vec![];
    for row in &rows {
        for issue in items(&row["issues"]) {
            issues.push(overlay(issue.clone(),&json!({"aggregation_key":row["aggregation_key"],"test_node_ids":row["test_node_ids"]})));
        }
    }
    let count = |p: fn(&V) -> bool| rows.iter().filter(|v| p(v)).count();
    json!({
        "schema_version": "HATE/v1",
        "record_type": "retry_aggregation",
        "run_id": x.id,
        "run_attempt": x.attempt,
        "aggregates": rows,
        "issues": issues,
        "summary": {
            "aggregate_count": rows.len(),
            "flaky_count": count(|v|s(v,"aggregate_status").starts_with("flaky")),
            "declared_flaky_count": count(|v|v["declared_flaky"]==true),
            "inconclusive_count": count(|v|v["aggregate_status"]=="inconclusive"),
            "matrix_group_count": rows.iter().map(|v|s(v,"matrix_group")).collect::<BTreeSet<_>>().len(),
            "missing_shard_count": count(|v|v["shards"]["missing"]==true),
            "issue_count": issues.len(),
        },
    })
}

fn aggregate(x: &Input, canonical: String, mid: String, g: Group) -> V {
    let mut es: Vec<_> = g.exec.into_values().collect();
    let idx = |v: &V| integer(&v["data"]["retry_index"]).unwrap_or_default();
    es.sort_by(|a, b| (idx(a), s(a, "id")).cmp(&(idx(b), s(b, "id"))));
    let totals: BTreeSet<_> = es
        .iter()
        .filter_map(|v| integer(&v["data"]["shard_total"]))
        .collect();
    let total = if totals.len() == 1 {
        totals.first().unwrap().clone()
    } else {
        BigInt::zero()
    };
    let sharded = !totals.is_empty() || es.iter().any(|v| v["data"].get("shard_index").is_some());
    let mut issues = vec![];
    let issue = |k: &str, msg: &str| json!({"issue":k,"message":msg});
    if es.is_empty() {
        issues.push(issue(
            "missing_execution_evidence",
            "test has no unambiguous linked execution evidence",
        ));
    }
    if totals.len() > 1 {
        issues.push(issue(
            "conflicting_shard_totals",
            "execution records disagree on the expected shard count",
        ));
    } else if sharded && totals.is_empty() {
        issues.push(issue(
            "unknown_shard_total",
            "shard indices do not declare the expected shard count",
        ));
    }
    let mut attempts = BTreeMap::<BigInt, Vec<&V>>::new();
    for e in &es {
        attempts.entry(idx(e)).or_default().push(e)
    }
    let max = attempts
        .keys()
        .next_back()
        .cloned()
        .unwrap_or_else(|| BigInt::from(-1));
    if !attempts.is_empty()
        && (attempts.keys().next().is_some_and(|n| !n.is_zero())
            || max != BigInt::from(attempts.len() - 1))
    {
        issues.push(issue(
            "retry_sequence_gap",
            "retry history must cover every index from zero to the final attempt",
        ));
    }
    let count = es
        .iter()
        .filter_map(|e| integer(&e["data"]["retry_count"]))
        .max()
        .unwrap_or_default();
    if !count.is_zero() && count > max {
        issues.push(overlay(
            issue(
                "reported_retry_history_missing",
                "reported retries are not fully represented by execution history",
            ),
            &json!({"retry_count":json_integer(&count)}),
        ));
    }
    let mut results = vec![];
    for (i, set) in attempts {
        let shards: Vec<_> = set
            .iter()
            .map(|e| integer(&e["data"]["shard_index"]))
            .collect();
        let observed: BTreeSet<_> = shards.iter().cloned().collect();
        let retry_index = json_integer(&i);
        let prev = issues.len();
        let mut add = |k: &str, msg: &str, detail: V| {
            issues.push(overlay(
                overlay(issue(k, msg), &json!({"retry_index":retry_index})),
                &detail,
            ))
        };
        if observed.len() != shards.len() {
            add(
                "duplicate_retry_shard",
                "multiple execution nodes occupy the same retry and shard",
                V::Null,
            )
        }
        if sharded && observed.contains(&None) {
            add(
                "missing_shard_index",
                "sharded execution has no shard index",
                V::Null,
            )
        }
        if !total.is_zero() && observed.iter().flatten().any(|j| j >= &total) {
            add(
                "shard_index_out_of_range",
                "shard index must be between zero and expected count minus one",
                V::Null,
            )
        }
        let valid = observed.iter().flatten().filter(|j| *j < &total).count();
        let missing = BigInt::from(valid) < total;
        if missing {
            add(
                "missing_shards",
                "retry attempt does not contain all expected shards",
                json!({"missing_count":json_integer(&(&total-valid))}),
            );
        }
        let unexecuted: Vec<_> = set
            .iter()
            .filter(|e| e["data"]["wouldRun"] == true)
            .map(|e| s(e, "id"))
            .collect();
        let statuses: Vec<_> = set
            .iter()
            .map(|e| s(&e["data"], "status").to_lowercase())
            .collect();
        if !unexecuted.is_empty() {
            add(
                "test_not_executed",
                "test was collected as runnable but was not executed",
                json!({"execution_node_ids":unexecuted}),
            );
        } else if statuses
            .iter()
            .any(|s| !matches!(s.as_str(), "passed" | "failed" | "error"))
        {
            add(
                "incomplete_execution_status",
                "execution status does not establish pass or failure",
                V::Null,
            );
        }
        let status = if issues.len() > prev {
            "inconclusive"
        } else if statuses.iter().any(|s| s != "passed") {
            "failed"
        } else {
            "passed"
        };
        results.push(json!({
            "retry_index": retry_index,
            "status": status,
            "missing_shard": missing,
            "execution_node_ids": set.iter().map(|e|s(e,"id")).collect::<Vec<_>>(),
        }));
    }
    let mut status = if !issues.is_empty() || results.is_empty() {
        "inconclusive"
    } else if results.iter().all(|v| v["status"] == "passed") {
        "stable_passed"
    } else if results.iter().all(|v| v["status"] == "failed") {
        "failed"
    } else if results.last().unwrap()["status"] == "passed" {
        "flaky_passed"
    } else {
        "flaky_failed"
    };
    let flaky = es.iter().any(|e| e["data"]["flaky"] == true);
    if flaky && !status.starts_with("flaky") {
        issues.push(issue("declared_flaky_without_mixed_history","input declares flaky but available history does not establish both failure and success"));
        status = "inconclusive";
    }
    if status.starts_with("flaky") {
        issues.push(issue(
            "flaky_execution",
            "complete retry history contains both failure and success",
        ));
    }
    let observed: BTreeSet<_> = es
        .iter()
        .filter_map(|e| integer(&e["data"]["shard_index"]))
        .collect();
    let raw: Vec<_> = es
        .iter()
        .map(|e| e["data"]["status"].as_str().unwrap_or("unknown"))
        .collect();
    let tries: Vec<_> = es
        .iter()
        .zip(&raw)
        .map(|(e, status)| {
            let mut v = json!({
                "execution_node_id": e["id"],
                "retry_index": json_integer(&idx(e)),
                "shard_index": e["data"]["shard_index"],
                "status": status,
            });
            for k in [
                "flaky",
                "retry_count",
                "source_status",
                "wouldRun",
                "xfail",
                "xpass",
                "todo",
                "only",
            ] {
                if let Some(x) = e["data"].get(k) {
                    v[k] = x.clone()
                }
            }
            v
        })
        .collect();
    json!({
        "aggregation_key": format!("{canonical}:{mid}:{}",x.attempt),
        "test_node_id": g.tests.first(),
        "test_node_ids": g.tests,
        "normalized_canonical_test_id": canonical,
        "matrix": g.matrix,
        "matrix_group": mid,
        "run_id": x.id,
        "run_attempt": x.attempt,
        "declared_flaky": flaky,
        "declared_retry_count": json_integer(&count),
        "retry_attempts": tries,
        "attempt_results": results,
        "shards": {
            "observed": observed.iter().map(ToString::to_string).collect::<Vec<_>>(),
            "expected_count": json_integer(&total),
            "missing": results.iter().any(|v|v["missing_shard"]==true),
        },
        "raw_statuses": raw,
        "aggregate_status": status,
        "issues": issues,
        "source_refs": ["qeg-bundle.json"],
    })
}
