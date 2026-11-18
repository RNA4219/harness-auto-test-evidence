use super::{failure, obj, opt, read_artifact, required_dir};
use crate::{
    cli::Invocation,
    io::{items, py_string},
};
use anyhow::{Context, Result};
use serde_json::{Value, json};
use std::{collections::BTreeMap, path::Path, sync::Arc};
use tiny_http::{Header, Method, Response, Server, StatusCode};

fn artifact(resource: &str) -> Option<&'static str> {
    Some(match resource {
        "runs" | "bundles" | "evidence" | "product-readiness" => "product-readiness-report.json",
        "artifacts" => "artifact-budget-report.json",
        "risk-debt" => "enterprise-risk-debt-register.json",
        "profiles" => "hosted-read-model-index.json",
        "adapters" => "enterprise-metrics-report.json",
        "audit-events" => "audit-event-log.json",
        _ => return None,
    })
}

fn allowed(role: &str, resource: &str) -> bool {
    match role.to_ascii_lowercase().as_str() {
        "admin" | "auditor" | "maintainer" => true,
        "viewer" => matches!(
            resource,
            "runs" | "bundles" | "evidence" | "product-readiness"
        ),
        "developer" => !matches!(resource, "artifacts" | "audit-events"),
        "security_reviewer" => !matches!(resource, "profiles" | "adapters" | "artifacts"),
        "service_account" => matches!(
            resource,
            "runs" | "bundles" | "evidence" | "product-readiness" | "risk-debt"
        ),
        _ => false,
    }
}

struct Query<'a> {
    resource: &'a str,
    request_id: &'a str,
    role: &'a str,
    filters: BTreeMap<String, String>,
    stale_cache: bool,
    cursor: Option<&'a str>,
}

impl Query<'_> {
    fn read(&self, dir: &Path) -> Result<Value> {
        let resource = self.resource;
        let role = self.role;
        let err = |status, category, message: String, remediation| {
            json!({
            "schema_version":"HATE/v1","request_id":self.request_id,"data":{},"pagination":{"next_cursor":null},
            "source":{"bundle_id":"","record_id":"","generated_at":""},
            "errors":[{"code":format!("HATE-E-PRODUCT-QUERY-{status}"),"http_status":status,"category":category,
            "message":message,"remediation":remediation}]})
        };
        let Some(file) = artifact(resource) else {
            return Ok(err(
                404,
                "SYS",
                format!("unknown read model resource: {resource}"),
                "Use one of the hosted read model resource names.",
            ));
        };
        if !allowed(role, resource) {
            return Ok(err(
                403,
                "SEC",
                format!("role {role} cannot read resource: {resource}"),
                "Use a role with read permission or query a less sensitive resource.",
            ));
        }
        let path = dir.join(file);
        let mut data = read_artifact(&path, "HATE-E-PRODUCT")?;
        if let Some(status) = self.filters.get("status") {
            if resource == "risk-debt" && (data["items"].is_array() || data.get("items").is_none())
            {
                let selected: Vec<_> = items(&data["items"])
                    .iter()
                    .filter(|item| {
                        item.is_object()
                            && item
                                .get("status")
                                .map_or_else(|| "open".to_string(), py_string)
                                == *status
                    })
                    .cloned()
                    .collect();
                let count = selected.len();
                data["items"] = json!(selected);
                let summary = data
                    .as_object_mut()
                    .unwrap()
                    .entry("summary")
                    .or_insert_with(obj);
                if summary.is_object() {
                    summary["filtered_count"] = json!(count);
                    summary["filter_status"] = json!(status);
                }
            } else if resource == "product-readiness" {
                let summary = data
                    .as_object_mut()
                    .unwrap()
                    .entry("summary")
                    .or_insert_with(obj);
                if summary.is_object() {
                    summary["filter_status"] = json!(status);
                    summary["filter_match"] = json!(summary["overall_status"] == *status);
                }
            }
        }
        Ok(
            json!({"schema_version":"HATE/v1","request_id":self.request_id,
            "source":{"bundle_id":data.get("run_id").map_or_else(||"local-bundle".to_owned(),py_string),"record_id":data.get("record_type").map_or_else(||resource.to_owned(),py_string),"generated_at":"fixture-time"},
            "pagination":{"next_cursor":self.cursor},"errors":[],
            "data":{"resource":resource,"path":format!("/v1/{resource}"),"attributes":data,"filters":self.filters,"role":role,"stale_cache":self.stale_cache,
            "canonical_source_preserved":true,"release_gate_override":false,"publish_gate_override":false}}),
        )
    }
}

pub fn cli(call: &Invocation) -> Result<Value> {
    let dir = call.path("readiness");
    required_dir(dir, "HATE-E-PRODUCT", "product readiness directory")?;
    let mut filters = BTreeMap::new();
    for item in items(&call.values["filter"]) {
        let arg = item.as_str().context("invalid filter")?;
        let (key, value) = arg.split_once('=').ok_or_else(|| {
            failure(
                1,
                format!("invalid --filter value, expected key=value: {arg}"),
            )
        })?;
        filters.insert(key.to_owned(), value.to_owned());
    }
    Query {
        resource: opt(call, "resource", ""),
        request_id: opt(call, "request_id", "req_local"),
        role: opt(call, "role", "developer"),
        filters,
        stale_cache: call.values["stale_cache"] == true,
        cursor: call.values["cursor"].as_str(),
    }
    .read(dir)
}

pub fn serve(call: &Invocation) -> Result<Value> {
    let dir = call.path("readiness");
    required_dir(dir, "HATE-E-PRODUCT", "product readiness directory")?;
    let port = u16::try_from(
        call.values["port"]
            .as_i64()
            .context("port must be an integer")?,
    )?;
    let server = Arc::new(
        Server::http((opt(call, "host", "127.0.0.1"), port)).map_err(anyhow::Error::from_boxed)?,
    );
    let workers: Vec<_> = (0..4)
        .map(|_| {
            let server = server.clone();
            let dir = dir.to_owned();
            std::thread::spawn(move || {
                for request in server.incoming_requests() {
                    if request.method() != &Method::Get {
                        let _ = request.respond(Response::empty(StatusCode(501)));
                        continue;
                    }
                    let (path, qs) = request.url().split_once('?').unwrap_or((request.url(), ""));
                    let path = path.strip_prefix("/v1/").unwrap_or(path).trim_matches('/');
                    let mut params = BTreeMap::new();
                    for (k, v) in
                        url::form_urlencoded::parse(qs.as_bytes()).filter(|(_, v)| !v.is_empty())
                    {
                        params.entry(k).or_insert(v);
                    }
                    let get = |name: &str| params.get(name).map(|v| v.as_ref());
                    let filters = params
                        .iter()
                        .filter_map(|(k, v)| {
                            Some((k.strip_prefix("filter.")?.to_owned(), v.to_string()))
                        })
                        .collect();
                    let query = Query {
                        resource: if path.is_empty() {
                            "product-readiness"
                        } else {
                            path
                        },
                        request_id: get("request_id").unwrap_or("req_http"),
                        role: get("role").unwrap_or("developer"),
                        filters,
                        stale_cache: get("stale_cache")
                            .is_some_and(|s| s.eq_ignore_ascii_case("true")),
                        cursor: get("cursor"),
                    };
                    match query.read(&dir) {
                        Ok(body) => {
                            let status =
                                body["errors"][0]["http_status"].as_u64().unwrap_or(200) as u16;
                            let response = Response::from_string(body.to_string())
                                .with_status_code(StatusCode(status))
                                .with_header(
                                    Header::from_bytes(
                                        "Content-Type",
                                        "application/json; charset=utf-8",
                                    )
                                    .unwrap(),
                                );
                            let _ = request.respond(response);
                        }
                        Err(_) => {
                            let _ = request.respond(Response::empty(StatusCode(500)));
                        }
                    }
                }
            })
        })
        .collect();
    for worker in workers {
        worker
            .join()
            .map_err(|_| anyhow::anyhow!("read-model worker failed"))?;
    }
    Ok(Value::Null)
}
