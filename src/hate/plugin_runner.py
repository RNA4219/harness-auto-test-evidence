"""Fail-closed local plugin execution for the platform CLI."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from hate.plugins.sandbox import RELEASE_PROFILES, build_plugin_sandbox_report

_MINIMAL_ENV_KEYS = {
    "COMSPEC",
    "LANG",
    "LC_ALL",
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
}


@dataclass(frozen=True)
class PluginProcessResult:
    exit_code: int
    stdout: str
    stderr: str
    output_bytes: int
    timed_out: bool
    output_limit_exceeded: bool
    cleanup: dict[str, Any]


def run_platform_plugin(
    manifest_path: Path,
    out_path: Path | None = None,
    *,
    allow_local_exec: bool = False,
) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    plugin = dict(manifest.get("plugin") or {})
    execution = dict(manifest.get("execution") or {})
    limits = dict(manifest.get("limits") or {})
    command = execution.get("command")
    if command is not None and (
        not isinstance(command, list)
        or not command
        or not all(isinstance(item, str) and item for item in command)
    ):
        raise ValueError("plugin execution.command must be a non-empty string list")
    validated_command = cast(list[str] | None, command)

    preflight = build_plugin_sandbox_report(
        {**manifest, "plugin": plugin, "execution": {key: value for key, value in execution.items() if key != "command"}},
        report_id=str(plugin.get("plugin_id") or "platform-plugin-run"),
    )
    denial_reasons = _preflight_denial_reasons(
        manifest,
        plugin,
        limits,
        validated_command,
        allow_local_exec=allow_local_exec,
        sandbox_report=preflight,
    )
    process_result: PluginProcessResult | None = None

    if not denial_reasons:
        process_result = _run_local_process(cast(list[str], validated_command), limits=limits, execution=execution)
        output = _json_or_empty(process_result.stdout)
        execution = {
            **execution,
            "exit_code": process_result.exit_code,
            "output": output,
            "output_bytes": process_result.output_bytes,
            "timed_out": process_result.timed_out,
            "crashed": process_result.exit_code != 0 and not process_result.timed_out,
            "output_limit_exceeded": process_result.output_limit_exceeded,
            "timeout_cleanup": process_result.cleanup,
        }
        sandbox = build_plugin_sandbox_report(
            {**manifest, "plugin": plugin, "execution": execution},
            report_id=str(plugin.get("plugin_id") or "platform-plugin-run"),
        )
    else:
        sandbox = preflight

    authorization_findings = [
        _finding(reason, "Plugin process was not started because execution authorization failed.")
        for reason in denial_reasons
    ]
    findings = [*sandbox["findings"], *authorization_findings]
    status = "blocked" if sandbox["overall_status"] == "blocked" else "hold" if findings else "pass"
    unenforced_controls = ["filesystem_isolation", "network_isolation"]
    if limits.get("max_memory_mb"):
        unenforced_controls.append("memory_limit")

    report = {
        "schema_version": "HATE/v1",
        "record_type": "platform-plugin-run-report",
        "overall_status": status,
        "readiness_effect": "blocked" if status == "blocked" else "hold" if findings else "none",
        "plugin_id": sandbox["plugin_id"],
        "detector_id": sandbox["detector_id"],
        "execution_attempted": process_result is not None,
        "execution_authorized": not denial_reasons,
        "authorization_source": "cli_allow_local_exec" if allow_local_exec else "default_deny",
        "denial_reasons": denial_reasons,
        "enforced_controls": [
            "explicit_local_execution_consent",
            "minimal_environment",
            "output_byte_limit",
            "process_tree_cleanup",
            "temporary_working_directory",
            "timeout",
        ],
        "unenforced_controls": unenforced_controls,
        "signature_verification": {
            "mode": "external_evidence",
            "cryptographically_verified_by_hate": False,
        },
        "process_result": (
            {
                "exit_code": process_result.exit_code,
                "output_bytes": process_result.output_bytes,
                "timed_out": process_result.timed_out,
                "output_limit_exceeded": process_result.output_limit_exceeded,
                "cleanup": process_result.cleanup,
            }
            if process_result
            else None
        ),
        "sandbox_report": sandbox,
        "findings": findings,
        "sourceRefs": sorted({str(manifest_path), *sandbox.get("sourceRefs", [])}),
    }
    if out_path is not None:
        _write_json(out_path, report)
    return report


def _preflight_denial_reasons(
    manifest: dict[str, Any],
    plugin: dict[str, Any],
    limits: dict[str, Any],
    command: Any,
    *,
    allow_local_exec: bool,
    sandbox_report: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    profile = str(manifest.get("profile") or "default")
    mode = str(plugin.get("execution_mode") or "disabled")
    if mode != "subprocess_local":
        reasons.append("plugin_execution_mode_not_runnable")
    if profile in RELEASE_PROFILES and mode == "subprocess_local":
        reasons.append("plugin_local_exec_denied_in_strict_profile")
    if not allow_local_exec:
        reasons.append("plugin_local_exec_consent_required")
    if not bool(plugin.get("signed", False)):
        reasons.append("plugin_signature_evidence_missing")
    if not bool(plugin.get("trusted", False)):
        reasons.append("plugin_trust_evidence_missing")
    if bool(plugin.get("revoked", False)):
        reasons.append("plugin_revoked")
    if str(plugin.get("compatibility_status") or "compatible") != "compatible":
        reasons.append("plugin_api_migration_required")
    if command is None:
        reasons.append("plugin_command_missing")
    if not all(_positive_int(limits.get(key)) for key in ("timeout_ms", "max_output_bytes", "max_input_bytes")):
        reasons.append("plugin_resource_limit_missing")
    if sandbox_report["mode_decision"]["allowed"] is False:
        reasons.append("plugin_trust_denied")
    configured_env = dict((manifest.get("execution") or {}).get("env") or {})
    allowlist = {str(item) for item in limits.get("env_allowlist", [])}
    if set(configured_env).difference(allowlist):
        reasons.append("plugin_environment_not_allowlisted")
    return sorted(set(reasons))


def _run_local_process(command: list[str], *, limits: dict[str, Any], execution: dict[str, Any]) -> PluginProcessResult:
    timeout_ms = int(limits["timeout_ms"])
    max_output_bytes = int(limits["max_output_bytes"])
    env = _minimal_environment(execution, limits)
    subprocess_module: Any = subprocess
    creationflags = subprocess_module.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    started = time.monotonic()
    timed_out = False
    output_limit_exceeded = False
    cleanup = _no_cleanup()

    with tempfile.TemporaryDirectory(prefix="hate-plugin-") as workdir:
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            try:
                process = subprocess.Popen(
                    command,
                    cwd=workdir,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    creationflags=creationflags,
                    start_new_session=os.name != "nt",
                )
            except OSError as exc:
                return PluginProcessResult(
                    exit_code=127,
                    stdout="",
                    stderr=str(exc),
                    output_bytes=0,
                    timed_out=False,
                    output_limit_exceeded=False,
                    cleanup=_no_cleanup(),
                )

            job_handle = _create_windows_job(process)

            while process.poll() is None:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                output_size = os.fstat(stdout_file.fileno()).st_size + os.fstat(stderr_file.fileno()).st_size
                if output_size > max_output_bytes:
                    output_limit_exceeded = True
                    cleanup = _terminate_process_tree(process, job_handle=job_handle)
                    job_handle = None
                    break
                if elapsed_ms >= timeout_ms:
                    timed_out = True
                    cleanup = _terminate_process_tree(process, job_handle=job_handle)
                    job_handle = None
                    break
                time.sleep(0.01)

            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cleanup = _terminate_process_tree(process, job_handle=job_handle, fallback=True)
                job_handle = None
                process.wait()

            if job_handle is not None:
                _close_windows_job(job_handle)

            final_output_size = os.fstat(stdout_file.fileno()).st_size + os.fstat(stderr_file.fileno()).st_size
            if final_output_size > max_output_bytes and not timed_out:
                output_limit_exceeded = True

            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout = stdout_file.read(max_output_bytes).decode("utf-8", errors="replace")
            stderr = stderr_file.read(max_output_bytes).decode("utf-8", errors="replace")
            exit_code = 124 if timed_out else 125 if output_limit_exceeded else int(process.returncode or 0)
            return PluginProcessResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                output_bytes=final_output_size,
                timed_out=timed_out,
                output_limit_exceeded=output_limit_exceeded,
                cleanup=cleanup,
            )


def _minimal_environment(execution: dict[str, Any], limits: dict[str, Any]) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key.upper() in _MINIMAL_ENV_KEYS}
    allowlist = {str(item) for item in limits.get("env_allowlist", [])}
    for key, value in dict(execution.get("env") or {}).items():
        if key in allowlist:
            env[str(key)] = str(value)
    return env



def _create_windows_job(process: subprocess.Popen[Any]) -> Any | None:
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimitInformation),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    ctypes_module: Any = ctypes
    kernel32 = ctypes_module.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        return None
    info = ExtendedLimitInformation()
    info.BasicLimitInformation.LimitFlags = 0x00002000
    configured = kernel32.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info))
    assigned = configured and kernel32.AssignProcessToJobObject(handle, int(process._handle))  # type: ignore[attr-defined]  # noqa: SLF001
    if not assigned:
        kernel32.CloseHandle(handle)
        return None
    return handle


def _close_windows_job(handle: Any) -> bool:
    if handle is None or os.name != "nt":
        return False
    import ctypes

    ctypes_module: Any = ctypes
    kernel32 = ctypes_module.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    return bool(kernel32.CloseHandle(handle))

def _terminate_process_tree(
    process: subprocess.Popen[Any],
    *,
    job_handle: Any | None = None,
    fallback: bool = False,
) -> dict[str, Any]:
    method = "windows_job_object" if job_handle is not None else "taskkill_tree" if os.name == "nt" else "killpg"
    if job_handle is not None:
        completed = _close_windows_job(job_handle)
        process.wait(timeout=5)
        time.sleep(0.1)
        return {
            "cleanup_attempted": True,
            "cleanup_method": method,
            "cleanup_completed": completed,
            "fallback_kill_used": False,
        }
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                fallback = True
            # Windows can retain descendant cwd handles briefly after taskkill /T returns.
            time.sleep(0.1)
            completed = result.returncode == 0 or process.poll() is not None
        else:
            os_module: Any = os
            signal_module: Any = signal
            os_module.killpg(process.pid, signal_module.SIGKILL)
            completed = True
    except OSError:
        process.kill()
        completed = process.poll() is not None
        method = "process_kill_fallback"
        fallback = True
    return {
        "cleanup_attempted": True,
        "cleanup_method": method,
        "cleanup_completed": completed,
        "fallback_kill_used": fallback,
    }


def _no_cleanup() -> dict[str, Any]:
    return {
        "cleanup_attempted": False,
        "cleanup_method": "none",
        "cleanup_completed": None,
        "fallback_kill_used": False,
    }


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _json_or_empty(value: str) -> dict[str, Any]:
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _finding(code: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "high",
        "readiness_effect": "hold",
        "message": message,
        "sourceRefs": [],
    }


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
