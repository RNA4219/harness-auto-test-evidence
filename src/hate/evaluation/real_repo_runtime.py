"""Runtime command helpers for real repository evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any

from hate.evaluation.output_safety import safe_command_output


@dataclass(frozen=True)
class CommandRunResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    parser_status: str
    timeout_cleanup: dict[str, Any]


def run_command(command: list[str], cwd: Path, env: dict[str, str], timeout_ms: int) -> CommandRunResult:
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return CommandRunResult(
            exit_code=127,
            stdout="",
            stderr="",
            timed_out=False,
            parser_status="failed",
            timeout_cleanup=no_timeout_cleanup(),
        )

    try:
        stdout, stderr = process.communicate(timeout=timeout_ms / 1000)
        return CommandRunResult(
            exit_code=int(process.returncode),
            stdout=stdout or "",
            stderr=stderr or "",
            timed_out=False,
            parser_status="passed",
            timeout_cleanup=no_timeout_cleanup(),
        )
    except subprocess.TimeoutExpired:
        cleanup = _terminate_process_tree(process.pid)
        try:
            stdout, stderr = process.communicate(timeout=5)
            cleanup["cleanup_completed"] = process.poll() is not None
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            cleanup["cleanup_completed"] = process.poll() is not None
            cleanup["fallback_kill_used"] = True
        return CommandRunResult(
            exit_code=124,
            stdout=_decode_timeout_output(stdout),
            stderr=_decode_timeout_output(stderr),
            timed_out=True,
            parser_status="passed",
            timeout_cleanup={"timeout_reason": "command_timeout_exceeded", **cleanup},
        )


def run_bootstrap_if_configured(entry: dict[str, Any], repo_path: Path, env: dict[str, str]) -> dict[str, Any]:
    command = bootstrap_command_for_entry(entry)
    if not command:
        return {
            "status": "not_configured",
            "command_configured": False,
            "exit_code": None,
            "runtime_ms": 0,
            "timeout_recorded": False,
            "command_excerpt": "",
            "output_safety": {},
            "timeout_cleanup": no_timeout_cleanup(),
        }
    timeout_ms = int(entry.get("bootstrap_timeout_ms") or (entry.get("bootstrap") or {}).get("timeout_ms") or 300_000)
    started = time.perf_counter()
    result = run_command(normalize_command(command), repo_path, env, timeout_ms)
    runtime_ms = int((time.perf_counter() - started) * 1000)
    safe_output = safe_command_output(result.stdout, result.stderr)
    return {
        "status": "hold" if result.timed_out or result.exit_code != 0 or result.parser_status == "failed" else "pass",
        "command_configured": True,
        "command": command,
        "exit_code": result.exit_code,
        "runtime_ms": runtime_ms,
        "timeout_ms": timeout_ms,
        "timeout_recorded": result.timed_out,
        "command_excerpt": safe_output["excerpt"],
        "output_safety": safe_output["metadata"],
        "timeout_cleanup": result.timeout_cleanup,
    }


def bootstrap_command_for_entry(entry: dict[str, Any]) -> list[str]:
    bootstrap = entry.get("bootstrap")
    if isinstance(bootstrap, dict) and isinstance(bootstrap.get("command"), list):
        return [str(item) for item in bootstrap["command"] if isinstance(item, str)]
    for key in ("bootstrap_command", "dependency_bootstrap_command"):
        value = entry.get(key)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return list(value)
    return []


def split_plan_for_entry(entry: dict[str, Any]) -> dict[str, Any]:
    raw = entry.get("split_execution") or entry.get("timeout_strategy") or {}
    if isinstance(raw, dict):
        commands = raw.get("commands") or raw.get("split_commands") or entry.get("split_commands")
        completed = raw.get("completed_splits") or entry.get("completed_splits") or []
        resume_token = str(raw.get("resume_token") or entry.get("resume_token") or "")
    else:
        commands = entry.get("split_commands")
        completed = entry.get("completed_splits") or []
        resume_token = str(entry.get("resume_token") or "")
    valid_commands = [
        [str(part) for part in command]
        for command in commands or []
        if isinstance(command, list) and all(isinstance(part, str) for part in command)
    ]
    completed_ids = {str(item) for item in completed if isinstance(item, (str, int))}
    return {
        "configured": bool(valid_commands),
        "commands": valid_commands,
        "completed_splits": completed_ids,
        "resume_token": resume_token,
    }


def merge_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for key, value in source.items():
        if isinstance(value, int):
            target[key] = int(target.get(key, 0)) + value


def no_split_execution() -> dict[str, Any]:
    return {
        "status": "not_configured",
        "mode": "single",
        "configured": False,
        "split_count": 0,
        "completed_count": 0,
        "skipped_count": 0,
        "resume_required": False,
        "resume_token": "",
        "splits": [],
    }


def no_timeout_cleanup() -> dict[str, Any]:
    return {
        "timeout_reason": "none",
        "cleanup_attempted": False,
        "cleanup_method": "none",
        "cleanup_completed": None,
        "fallback_kill_used": False,
    }


def normalize_command(command: list[str], os_name: str | None = None) -> list[str]:
    """Resolve Windows command shims without forcing roster authors to use .cmd."""
    current_os = os.name if os_name is None else os_name
    if not command or current_os != "nt":
        return command
    executable = command[0]
    if Path(executable).suffix:
        return command
    shim = shutil.which(f"{executable}.cmd")
    if shim:
        return [shim, *command[1:]]
    return command


def _terminate_process_tree(pid: int) -> dict[str, Any]:
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return {
            "cleanup_attempted": True,
            "cleanup_method": "taskkill_tree",
            "cleanup_completed": result.returncode == 0,
            "fallback_kill_used": False,
        }
    try:
        os.kill(pid, 9)
    except OSError:
        return {
            "cleanup_attempted": True,
            "cleanup_method": "os_kill",
            "cleanup_completed": True,
            "fallback_kill_used": False,
        }
    return {
        "cleanup_attempted": True,
        "cleanup_method": "os_kill",
        "cleanup_completed": True,
        "fallback_kill_used": False,
    }


def _decode_timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
