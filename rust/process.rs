use anyhow::{Context, Result};
use command_group::CommandGroup;
use serde_json::{Value, json};
use std::{
    collections::BTreeMap,
    fs::File,
    io::{Read, Seek, SeekFrom},
    path::Path,
    process::{Command, Stdio},
    time::{Duration, Instant},
};

pub struct ProcessResult {
    pub exit_code: i32,
    pub stdout: String,
    pub stderr: String,
    pub timed_out: bool,
    pub launch_failed: bool,
    pub cleanup: Value,
    pub output_bytes: u64,
    pub over_limit: bool,
}
fn read(file: &mut File, limit: Option<u64>) -> Result<String> {
    file.seek(SeekFrom::Start(0))?;
    let mut bytes = Vec::new();
    file.take(limit.unwrap_or(u64::MAX))
        .read_to_end(&mut bytes)?;
    Ok(String::from_utf8_lossy(&bytes).into_owned())
}
pub fn execute(
    command: &[String],
    cwd: &Path,
    env: &BTreeMap<String, String>,
    timeout_ms: u64,
    max_output: Option<u64>,
) -> Result<ProcessResult> {
    let exe = command.first().context("command requires an executable")?;
    let mut out = tempfile::tempfile()?;
    let mut err = tempfile::tempfile()?;
    let mut cmd = Command::new(exe);
    cmd.args(&command[1..])
        .current_dir(cwd)
        .env_clear()
        .envs(env)
        .stdin(Stdio::null())
        .stdout(out.try_clone()?)
        .stderr(err.try_clone()?);
    let mut builder = cmd.group();
    #[cfg(windows)]
    builder.kill_on_drop(true).creation_flags(0x08000000);
    let mut cleanup = json!({"cleanup_attempted":false,"cleanup_method":"none","cleanup_completed":null,"fallback_kill_used":false});
    let started = Instant::now();
    let mut child = match builder.spawn() {
        Ok(c) => c,
        Err(e) => {
            return Ok(ProcessResult {
                exit_code: 127,
                stdout: String::new(),
                stderr: e.to_string(),
                output_bytes: 0,
                timed_out: false,
                over_limit: false,
                launch_failed: true,
                cleanup,
            });
        }
    };
    let mut timed_out = false;
    let mut over_limit = false;
    let exit_code = loop {
        if let Some(status) = child.inner().try_wait()? {
            break status.code().unwrap_or(1);
        }
        let bytes = out.metadata()?.len() + err.metadata()?.len();
        over_limit = max_output.is_some_and(|n| bytes > n);
        timed_out = !over_limit && started.elapsed() >= Duration::from_millis(timeout_ms);
        if timed_out || over_limit {
            let killed = child.kill();
            if killed.is_err() {
                child.inner().kill()?;
            }
            child.inner().wait()?;
            cleanup = json!({"cleanup_attempted":true,"cleanup_method":if killed.is_err(){"process_kill_fallback"}else if cfg!(windows){"windows_job_object"}else{"killpg"},
                "cleanup_completed":true,"fallback_kill_used":killed.is_err()});
            break if over_limit { 125 } else { 124 };
        }
        std::thread::sleep(Duration::from_millis(10));
    };
    drop(child);
    let bytes = out.metadata()?.len() + err.metadata()?.len();
    over_limit |= !timed_out && max_output.is_some_and(|n| bytes > n);
    Ok(ProcessResult {
        exit_code: if over_limit { 125 } else { exit_code },
        stdout: read(&mut out, max_output)?,
        stderr: read(&mut err, max_output)?,
        output_bytes: bytes,
        timed_out,
        over_limit,
        launch_failed: false,
        cleanup,
    })
}
