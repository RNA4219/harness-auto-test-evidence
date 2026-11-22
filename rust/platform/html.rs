use super::*;
fn escaped(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#x27;")
}
fn cell(value: Option<&Value>, default: &str) -> String {
    match value {
        None => default.into(),
        Some(Value::String(s)) => s.clone(),
        Some(Value::Bool(b)) => {
            if *b {
                "True".into()
            } else {
                "False".into()
            }
        }
        Some(Value::Null) => "None".into(),
        Some(v) => v.to_string(),
    }
}
fn rows(values: &[Value], columns: &[&str]) -> String {
    values
        .iter()
        .map(|v| {
            let mut row = String::from("<tr>");
            for &column in columns {
                let s = match column {
                    "#findings" => items(&v["findings"]).len().to_string(),
                    "#refs" => refs(v, false).join(", "),
                    "overall_status" => cell(v.get(column).or(v.get("status")), "unknown"),
                    _ => cell(column.split('|').find_map(|k| v.get(k)), ""),
                };
                row.push_str(&format!("<td>{}</td>", escaped(&s)));
            }
            row.push_str("</tr>");
            row
        })
        .collect::<Vec<_>>()
        .join("\n")
}
pub(super) fn run(call: &Invocation) -> Result<Value> {
    let input = call.path("input");
    let out = call.path("out");
    let reports = reports(input, true)?;
    let find = project(&reports, "findings", input)?;
    let debt = project(&reports, "debt", input)?;
    let review = project(&reports, "review", input)?;
    let findings = items(&find["items"]);
    let debts = items(&debt["items"]);
    let reviews = items(&review["items"]);
    let critical: Vec<_> = findings
        .iter()
        .filter(|v| {
            matches!(
                field(v, "severity", "").to_lowercase().as_str(),
                "high" | "critical"
            )
        })
        .cloned()
        .collect();
    let hold = !critical.is_empty()
        || reports.iter().any(|v| {
            matches!(
                field(v, "overall_status", field(v, "status", ""))
                    .to_lowercase()
                    .as_str(),
                "hold" | "blocked" | "hard_dq" | "no_go"
            )
        });
    let doc = format!(
        include_str!("report.html"),
        report_count = reports.len(),
        finding_count = findings.len(),
        critical_count = critical.len(),
        debt_count = debts.len(),
        review_count = reviews.len(),
        reports = rows(
            &reports,
            &["record_type", "report_id", "overall_status", "#findings"]
        ),
        queue = rows(
            &critical,
            &["code", "severity", "owner", "due_date|dueDate", "#refs"]
        ),
        findings = rows(findings, &["code", "severity", "readiness_effect", "#refs"]),
        debts = rows(
            debts,
            &["debt_id|id", "owner", "expiry|expiry_date", "status"]
        ),
        reviews = rows(
            reviews,
            &[
                "request_id|id",
                "owner",
                "blocking",
                "required_decision|decision"
            ]
        )
    );
    fs::create_dir_all(parent(out))?;
    fs::write(out, doc)?;
    Ok(
        json!({"schema_version":"HATE/v1","record_type":"platform-html-report","overall_status":if hold{"hold"}else{"pass"},
        "html_path":out,"report_count":reports.len(),"finding_count":findings.len(),"debt_count":debts.len(),"review_count":reviews.len(),
        "critical_queue_count":critical.len(),"sourceRefs":[input]}),
    )
}
