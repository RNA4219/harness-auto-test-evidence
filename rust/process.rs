use anyhow::{Context, Result};
use command_group::CommandGroup;
use serde_json::{Value, json};
#[cfg(unix)]
use std::os::fd::OwnedFd as OwnedPipe;
#[cfg(windows)]
use std::os::windows::io::OwnedHandle as OwnedPipe;
use std::{
    collections::BTreeMap,
    fs::File,
    io::{self, Read, Seek, SeekFrom, Write},
    path::Path,
    process::{Command, Stdio},
    time::{Duration, Instant},
};

const POLL_INTERVAL: Duration = Duration::from_millis(10);

// ロスターはパイプの EOF、プラグインは一時ファイルへの出力サイズを監視する。
struct Capture {
    spool: File,
    reader: Option<File>,
}

impl Capture {
    fn new() -> io::Result<Self> {
        Ok(Self {
            spool: tempfile::tempfile()?,
            reader: None,
        })
    }

    fn stdio(&self, piped: bool) -> io::Result<Stdio> {
        Ok(if piped {
            Stdio::piped()
        } else {
            self.spool.try_clone()?.into()
        })
    }

    fn attach(&mut self, pipe: Option<impl Into<OwnedPipe>>) -> io::Result<()> {
        self.reader = pipe.map(|pipe| File::from(pipe.into()));
        #[cfg(unix)]
        if let Some(reader) = &self.reader {
            use rustix::fs::{OFlags, fcntl_getfl, fcntl_setfl};
            fcntl_setfl(reader, fcntl_getfl(reader)? | OFlags::NONBLOCK)?;
        }
        Ok(())
    }

    fn pump(&mut self, buffer: &mut [u8]) -> io::Result<bool> {
        let Some(reader) = &mut self.reader else {
            return Ok(false);
        };
        match read_available(reader, buffer) {
            Ok(0) => self.reader = None,
            Ok(n) => {
                self.spool.write_all(&buffer[..n])?;
                return Ok(true);
            }
            Err(err)
                if matches!(
                    err.kind(),
                    io::ErrorKind::WouldBlock | io::ErrorKind::Interrupted
                ) => {}
            Err(err) => return Err(err),
        }
        Ok(false)
    }
}

#[cfg(unix)]
fn read_available(pipe: &mut File, buffer: &mut [u8]) -> io::Result<usize> {
    pipe.read(buffer)
}

#[cfg(windows)]
fn read_available(pipe: &mut File, buffer: &mut [u8]) -> io::Result<usize> {
    use std::{os::windows::io::AsRawHandle, ptr};
    use windows_sys::Win32::System::Pipes::PeekNamedPipe;
    let mut available = 0;
    // pipe はこの関数の呼出中に有効で、読み手はこのスレッドだけ。
    let success = unsafe {
        PeekNamedPipe(
            pipe.as_raw_handle(),
            ptr::null_mut(),
            0,
            ptr::null_mut(),
            &mut available,
            ptr::null_mut(),
        )
    };
    if success == 0 {
        let err = io::Error::last_os_error();
        return if err.kind() == io::ErrorKind::BrokenPipe {
            Ok(0)
        } else {
            Err(err)
        };
    }
    if available == 0 {
        return Err(io::ErrorKind::WouldBlock.into());
    }
    let count = buffer.len().min(available as usize);
    pipe.read(&mut buffer[..count])
}

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
    let piped = max_output.is_none();
    let mut out = Capture::new()?;
    let mut err = Capture::new()?;
    let mut cmd = Command::new(exe);
    cmd.args(&command[1..])
        .current_dir(cwd)
        .env_clear()
        .envs(env)
        .stdin(Stdio::null())
        .stdout(out.stdio(piped)?)
        .stderr(err.stdio(piped)?);
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
    let mut buffer = [0; 16 * 1024];
    let timeout = Duration::from_millis(timeout_ms);
    let monitor = (|| -> Result<i32> {
        out.attach(child.inner().stdout.take())?;
        err.attach(child.inner().stderr.take())?;
        loop {
            let read_out = out.pump(&mut buffer)?;
            let read_err = err.pump(&mut buffer)?;
            if let Some(status) = child.inner().try_wait()?
                && out.reader.is_none()
                && err.reader.is_none()
            {
                return Ok(status.code().unwrap_or(1));
            }
            if let Some(limit) = max_output {
                over_limit = out.spool.metadata()?.len() + err.spool.metadata()?.len() > limit;
            }
            timed_out = !over_limit && started.elapsed() >= timeout;
            if timed_out || over_limit {
                let killed = child.kill();
                if killed.is_err() {
                    child.inner().kill()?;
                }
                child.inner().wait()?;
                cleanup = json!({"cleanup_attempted":true,"cleanup_method":if killed.is_err(){"process_kill_fallback"}else if cfg!(windows){"windows_job_object"}else{"killpg"},
                "cleanup_completed":true,"fallback_kill_used":killed.is_err()});
                // 終了直前に書き込まれたデータも回収する。グループ外に複製された
                // 書き込み側ハンドルがあっても、ここで無期限には待たない。
                let drain_start = Instant::now();
                while out.reader.is_some() || err.reader.is_some() {
                    let read_out = out.pump(&mut buffer)?;
                    let read_err = err.pump(&mut buffer)?;
                    if drain_start.elapsed() >= Duration::from_millis(100) {
                        break;
                    }
                    if !read_out && !read_err && (out.reader.is_some() || err.reader.is_some()) {
                        std::thread::sleep(POLL_INTERVAL);
                    }
                }
                return Ok(if over_limit { 125 } else { 124 });
            }
            if !read_out && !read_err {
                std::thread::sleep(POLL_INTERVAL.min(timeout.saturating_sub(started.elapsed())));
            }
        }
    })();
    if monitor.is_err() {
        let _ = child.kill().or_else(|_| child.inner().kill());
        let _ = child.inner().wait();
    }
    let exit_code = monitor?;
    drop(child);
    let bytes = out.spool.metadata()?.len() + err.spool.metadata()?.len();
    over_limit |= !timed_out && max_output.is_some_and(|n| bytes > n);
    Ok(ProcessResult {
        exit_code: if over_limit { 125 } else { exit_code },
        stdout: read(&mut out.spool, max_output)?,
        stderr: read(&mut err.spool, max_output)?,
        output_bytes: bytes,
        timed_out,
        over_limit,
        launch_failed: false,
        cleanup,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{env, fs, thread};

    fn helper() -> Vec<String> {
        vec![
            env::current_exe().unwrap().to_str().unwrap().to_owned(),
            "--ignored".into(),
            "--exact".into(),
            "process::tests::inherited_output_helper".into(),
            "--nocapture".into(),
        ]
    }

    #[test]
    #[ignore = "子プロセスとして起動するテスト用コマンド"]
    fn inherited_output_helper() {
        let Ok(role) = env::var("HATE_CAPTURE_TEST_ROLE") else {
            return;
        };
        if role == "plugin" {
            io::stderr().write_all(&[b'x'; 4096]).unwrap();
            thread::sleep(Duration::from_secs(10));
            return;
        }
        if role == "launcher" {
            let cmd = helper();
            let _child = Command::new(&cmd[0])
                .args(&cmd[1..])
                .env("HATE_CAPTURE_TEST_ROLE", "writer")
                .spawn()
                .unwrap();
            let deadline = Instant::now() + Duration::from_secs(5);
            while !Path::new("writer-ready").exists() {
                assert!(Instant::now() < deadline);
                thread::sleep(POLL_INTERVAL);
            }
            fs::write("launcher-exited", []).unwrap();
            std::process::exit(9);
        }

        let lock = File::create("writer-lock").unwrap();
        lock.lock().unwrap();
        io::stderr().write_all(b"writer ready\n").unwrap();
        fs::write("writer-ready", []).unwrap();
        if env::var_os("HATE_CAPTURE_TEST_HANG").is_some() {
            thread::sleep(Duration::from_secs(10));
        } else {
            while !Path::new("launcher-exited").exists() {
                thread::sleep(POLL_INTERVAL);
            }
            thread::sleep(Duration::from_millis(80));
            io::stdout().write_all(&[b'x'; 128 * 1024]).unwrap();
            io::stderr().write_all(b"late stderr\n").unwrap();
            io::stdout().write_all(b"late stdout\xff\n").unwrap();
        }
    }

    fn run_helper(
        dir: &Path,
        role: &str,
        hang: bool,
        timeout: u64,
        limit: Option<u64>,
    ) -> ProcessResult {
        let mut env: BTreeMap<_, _> = env::vars().collect();
        env.insert("HATE_CAPTURE_TEST_ROLE".into(), role.into());
        if hang {
            env.insert("HATE_CAPTURE_TEST_HANG".into(), "1".into());
        }
        execute(&helper(), dir, &env, timeout, limit).unwrap()
    }

    #[test]
    fn captures_output_after_the_launcher_exits() {
        let dir = tempfile::tempdir().unwrap();
        let result = run_helper(dir.path(), "launcher", false, 5_000, None);
        assert_eq!(result.exit_code, 9);
        assert!(result.stdout.contains(&"x".repeat(128 * 1024)));
        assert!(result.stdout.contains("late stdout�"));
        assert!(result.stderr.contains("late stderr"));
        assert!(!result.timed_out && !result.over_limit);
        assert_eq!(result.cleanup["cleanup_attempted"], false);
    }

    #[test]
    fn inherited_output_times_out_and_terminates_its_writer() {
        let dir = tempfile::tempdir().unwrap();
        let started = Instant::now();
        let result = run_helper(dir.path(), "launcher", true, 1_000, None);
        assert!(started.elapsed() < Duration::from_secs(5));
        assert!(dir.path().join("launcher-exited").exists());
        assert_eq!(result.exit_code, 124);
        assert!(result.timed_out && !result.over_limit);
        assert!(result.stderr.contains("writer ready"));
        assert_eq!(result.cleanup["cleanup_completed"], true);
        let lock = File::open(dir.path().join("writer-lock")).unwrap();
        lock.try_lock()
            .expect("終了した子プロセスのロックが解放されたこと");
    }

    #[test]
    fn plugin_output_limit_preserves_truncation_and_cleanup() {
        let dir = tempfile::tempdir().unwrap();
        let result = run_helper(dir.path(), "plugin", false, 5_000, Some(100));
        assert_eq!(result.exit_code, 125);
        assert!(!result.timed_out && result.over_limit);
        assert_eq!(result.stderr, "x".repeat(100));
        assert!(result.output_bytes >= 4096);
        assert_eq!(result.cleanup["cleanup_completed"], true);
    }
}
