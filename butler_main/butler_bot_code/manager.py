from __future__ import annotations

import argparse
import contextlib
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from butler_main.chat.core_defaults import DEFAULT_CORE_HOST, DEFAULT_CORE_PORT
from butler_main.console.server import DEFAULT_CONSOLE_PORT


BODY_DIR = Path(__file__).resolve().parent
REPO_ROOT = BODY_DIR.parent.parent
REGISTRY_PATH = BODY_DIR / "registry.json"
RUN_DIR = BODY_DIR / "run"
LOG_DIR = BODY_DIR / "logs"
HEALTH_TIMEOUT_SECONDS = 1.5
STOP_TIMEOUT_SECONDS = 8.0
_MODULE_PART_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(slots=True, frozen=True)
class ServiceSpec:
    name: str
    script_path: Path
    config_path: str
    description: str
    health_url: str = ""


def load_registry(registry_path: Path = REGISTRY_PATH) -> dict[str, ServiceSpec]:
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid registry payload: {registry_path}")
    specs: dict[str, ServiceSpec] = {}
    for name, item in payload.items():
        if not isinstance(item, dict):
            continue
        normalized_name = str(name or "").strip()
        if not normalized_name:
            continue
        script_rel = str(item.get("script") or "").strip()
        if not script_rel:
            continue
        specs[normalized_name] = ServiceSpec(
            name=normalized_name,
            script_path=(registry_path.parent / script_rel).resolve(),
            config_path=str((registry_path.parent / str(item.get("config") or "").strip()).resolve()) if str(item.get("config") or "").strip() else "",
            description=str(item.get("description") or "").strip(),
            health_url=_default_health_url_for_service(normalized_name),
        )
    return specs


def status_service(
    spec: ServiceSpec,
    *,
    run_dir: Path = RUN_DIR,
    log_dir: Path = LOG_DIR,
) -> dict[str, Any]:
    pid_path = _pid_file_path(spec.name, run_dir=run_dir)
    state_path = _state_file_path(spec.name, run_dir=run_dir)
    pid = _read_pid_file(pid_path)
    running = _pid_is_running(pid)
    stale = bool(pid) and not running
    health = _probe_health_url(spec.health_url) if running and spec.health_url else {}
    return {
        "name": spec.name,
        "running": running,
        "stale_pid": stale,
        "pid": pid,
        "pid_path": str(pid_path),
        "state_path": str(state_path),
        "log_path": str(_log_file_path(spec.name, log_dir=log_dir)),
        "script_path": str(spec.script_path),
        "config_path": spec.config_path,
        "description": spec.description,
        "health": health,
    }


def start_service(
    spec: ServiceSpec,
    *,
    extra_args: list[str] | tuple[str, ...] = (),
    run_dir: Path = RUN_DIR,
    log_dir: Path = LOG_DIR,
    repo_root: Path = REPO_ROOT,
    python_executable: str | None = None,
) -> dict[str, Any]:
    current = status_service(spec, run_dir=run_dir, log_dir=log_dir)
    if current["running"]:
        return {"ok": True, "changed": False, **current}
    _ensure_runtime_dirs(run_dir=run_dir, log_dir=log_dir)
    pid_path = _pid_file_path(spec.name, run_dir=run_dir)
    state_path = _state_file_path(spec.name, run_dir=run_dir)
    log_path = _log_file_path(spec.name, log_dir=log_dir)
    command = _build_service_command(
        spec,
        python_executable=_resolve_service_python_executable(
            repo_root=repo_root,
            requested_python=python_executable,
        ),
        extra_args=_normalize_extra_args(extra_args),
    )
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("PYTEST_"):
            env.pop(key, None)
    env["PYTHONPATH"] = _prepend_pythonpath(str(repo_root), env.get("PYTHONPATH"))
    process, exit_code = _launch_service_process(
        command=command,
        repo_root=repo_root,
        env=env,
        log_path=log_path,
    )
    if exit_code is not None:
        process, exit_code = _launch_service_process(
            command=command,
            repo_root=repo_root,
            env=env,
            log_path=log_path,
        )
    if exit_code is not None:
        _cleanup_runtime_files(spec.name, run_dir=run_dir)
        return {
            "ok": False,
            "changed": False,
            "name": spec.name,
            "running": False,
            "exit_code": exit_code,
            "log_path": str(log_path),
            "command": command,
        }
    pid_path.write_text(str(process.pid), encoding="utf-8")
    state_path.write_text(
        json.dumps(
            {
                "name": spec.name,
                "pid": process.pid,
                "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "command": command,
                "script_path": str(spec.script_path),
                "config_path": spec.config_path,
                "log_path": str(log_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"ok": True, "changed": True, **status_service(spec, run_dir=run_dir, log_dir=log_dir)}


def stop_service(
    spec: ServiceSpec,
    *,
    run_dir: Path = RUN_DIR,
    log_dir: Path = LOG_DIR,
    timeout_seconds: float = STOP_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    current = status_service(spec, run_dir=run_dir, log_dir=log_dir)
    pid = int(current.get("pid") or 0)
    if not pid:
        _cleanup_runtime_files(spec.name, run_dir=run_dir)
        return {"ok": True, "changed": False, **current}
    _send_signal_to_service(pid, signal.SIGTERM)
    deadline = time.time() + max(float(timeout_seconds), 0.0)
    while time.time() < deadline:
        if not _pid_is_running(pid):
            _cleanup_runtime_files(spec.name, run_dir=run_dir)
            return {"ok": True, "changed": True, **status_service(spec, run_dir=run_dir, log_dir=log_dir)}
        time.sleep(0.1)
    _send_signal_to_service(pid, signal.SIGKILL)
    time.sleep(0.2)
    _cleanup_runtime_files(spec.name, run_dir=run_dir)
    return {"ok": not _pid_is_running(pid), "changed": True, **status_service(spec, run_dir=run_dir, log_dir=log_dir)}


def restart_service(
    spec: ServiceSpec,
    *,
    extra_args: list[str] | tuple[str, ...] = (),
    run_dir: Path = RUN_DIR,
    log_dir: Path = LOG_DIR,
    repo_root: Path = REPO_ROOT,
    python_executable: str | None = None,
) -> dict[str, Any]:
    stop_result = stop_service(spec, run_dir=run_dir, log_dir=log_dir)
    start_result = start_service(
        spec,
        extra_args=extra_args,
        run_dir=run_dir,
        log_dir=log_dir,
        repo_root=repo_root,
        python_executable=python_executable,
    )
    return {
        "ok": bool(stop_result.get("ok")) and bool(start_result.get("ok")),
        "changed": bool(stop_result.get("changed")) or bool(start_result.get("changed")),
        "stop": stop_result,
        "start": start_result,
        **{key: value for key, value in start_result.items() if key not in {"ok", "changed"}},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-platform Butler service manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List registered services")

    status_parser = subparsers.add_parser("status", help="Show service status")
    status_parser.add_argument("service", nargs="?", default="", help="Optional service name")

    start_parser = subparsers.add_parser("start", help="Start a service")
    start_parser.add_argument("service", help="Service name from registry")
    start_parser.add_argument("extra_args", nargs=argparse.REMAINDER, help="Extra args passed to the service script")

    stop_parser = subparsers.add_parser("stop", help="Stop a service")
    stop_parser.add_argument("service", help="Service name from registry")

    restart_parser = subparsers.add_parser("restart", help="Restart a service")
    restart_parser.add_argument("service", help="Service name from registry")
    restart_parser.add_argument("extra_args", nargs=argparse.REMAINDER, help="Extra args passed to the service script")

    args = parser.parse_args(argv)
    registry = load_registry()

    if args.command == "list":
        for spec in registry.values():
            print(f"{spec.name}\t{spec.script_path}\t{spec.description}")
        return 0

    target_specs = _select_specs(registry, service_name=str(getattr(args, "service", "") or "").strip())
    if not target_specs:
        print(f"unknown service: {getattr(args, 'service', '')}", file=sys.stderr)
        return 1

    if args.command == "status":
        for spec in target_specs:
            _print_status_line(status_service(spec))
        return 0

    if len(target_specs) != 1:
        print(f"{args.command} requires an explicit service name", file=sys.stderr)
        return 1
    spec = target_specs[0]

    if args.command == "start":
        result = start_service(spec, extra_args=getattr(args, "extra_args", ()) or ())
    elif args.command == "stop":
        result = stop_service(spec)
    else:
        result = restart_service(spec, extra_args=getattr(args, "extra_args", ()) or ())

    _print_operation_result(args.command, result)
    return 0 if bool(result.get("ok")) else 1


def _select_specs(registry: dict[str, ServiceSpec], *, service_name: str) -> list[ServiceSpec]:
    if service_name:
        spec = registry.get(service_name)
        return [spec] if spec is not None else []
    return list(registry.values())


def _print_status_line(payload: dict[str, Any]) -> None:
    health = dict(payload.get("health") or {})
    health_text = ""
    if health:
        health_text = f" health_ok={health.get('ok')}"
        if health.get("status_code"):
            health_text += f" health_status={health.get('status_code')}"
    print(
        f"{payload.get('name')}: running={payload.get('running')} stale_pid={payload.get('stale_pid')} pid={payload.get('pid') or '-'}"
        f"{health_text} log={payload.get('log_path')}",
    )


def _print_operation_result(command: str, payload: dict[str, Any]) -> None:
    if command == "restart":
        start_result = dict(payload.get("start") or {})
        print(
            f"restart {payload.get('name')}: ok={payload.get('ok')} changed={payload.get('changed')} "
            f"running={start_result.get('running')} pid={start_result.get('pid') or '-'} log={start_result.get('log_path')}",
        )
        return
    print(
        f"{command} {payload.get('name')}: ok={payload.get('ok')} changed={payload.get('changed')} "
        f"running={payload.get('running')} pid={payload.get('pid') or '-'} log={payload.get('log_path')}",
    )


def _build_service_command(
    spec: ServiceSpec,
    *,
    python_executable: str,
    extra_args: list[str],
) -> list[str]:
    if spec.script_path.suffix.lower() != ".py":
        raise ValueError(f"unsupported service script: {spec.script_path}")
    module_name = _module_name_for_script(spec.script_path)
    if module_name:
        command = [str(python_executable), "-m", module_name]
    else:
        command = [str(python_executable), str(spec.script_path)]
    if spec.config_path and "--config" not in extra_args and "-c" not in extra_args:
        command.extend(["--config", spec.config_path])
    command.extend(extra_args)
    return command


def _resolve_service_python_executable(
    *,
    repo_root: Path,
    requested_python: str | None,
) -> str:
    requested = str(requested_python or "").strip()
    if requested:
        return requested
    repo_root = Path(repo_root).resolve()
    venv_python = repo_root / ".venv" / "bin" / "python"
    if venv_python.is_file() and os.access(venv_python, os.X_OK):
        return str(venv_python)
    return sys.executable


def _normalize_extra_args(values: list[str] | tuple[str, ...]) -> list[str]:
    result = [str(item) for item in values if str(item)]
    if result[:1] == ["--"]:
        return result[1:]
    return result


def _launch_service_process(
    *,
    command: list[str],
    repo_root: Path,
    env: dict[str, str],
    log_path: Path,
) -> tuple[subprocess.Popen[bytes], int | None]:
    with log_path.open("ab") as stream:
        process = subprocess.Popen(
            command,
            cwd=str(repo_root),
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
    time.sleep(0.4)
    return process, process.poll()


def _module_name_for_script(script_path: Path) -> str:
    with contextlib.suppress(ValueError):
        relative = script_path.resolve().relative_to(REPO_ROOT.resolve())
        if relative.suffix.lower() != ".py":
            return ""
        if relative.name in {"__init__.py", "__main__.py"}:
            parts = relative.parts[:-1]
        else:
            parts = relative.with_suffix("").parts
        if not parts:
            return ""
        if not all(_MODULE_PART_PATTERN.match(str(part)) for part in parts):
            return ""
        return ".".join(parts)
    return ""


def _probe_health_url(url: str) -> dict[str, Any]:
    if not url:
        return {}
    try:
        with urlopen(url, timeout=HEALTH_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except URLError as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    try:
        payload = json.loads(body)
    except Exception:
        return {"ok": response.status == 200, "status_code": response.status, "raw": body[:200]}
    return {"ok": response.status == 200 and bool(payload.get("ok", True)), "status_code": response.status, "payload": payload}


def _default_health_url_for_service(name: str) -> str:
    normalized = str(name or "").strip()
    if normalized == "butler_bot":
        return f"http://{DEFAULT_CORE_HOST}:{DEFAULT_CORE_PORT}/health"
    if normalized == "console":
        return f"http://127.0.0.1:{DEFAULT_CONSOLE_PORT}/console/api/runtime"
    return ""


def _ensure_runtime_dirs(*, run_dir: Path, log_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)


def _prepend_pythonpath(root: str, existing: str | None) -> str:
    entries = [root]
    if existing:
        entries.extend(item for item in str(existing).split(os.pathsep) if item)
    normalized: list[str] = []
    for item in entries:
        if item and item not in normalized:
            normalized.append(item)
    return os.pathsep.join(normalized)


def _pid_file_path(service_name: str, *, run_dir: Path) -> Path:
    return run_dir / f"{service_name}.pid"


def _state_file_path(service_name: str, *, run_dir: Path) -> Path:
    return run_dir / f"{service_name}.json"


def _log_file_path(service_name: str, *, log_dir: Path) -> Path:
    return log_dir / f"{service_name}.log"


def _read_pid_file(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return 0


def _pid_is_running(pid: int) -> bool:
    if int(pid or 0) <= 0:
        return False
    proc_stat = Path("/proc") / str(int(pid)) / "stat"
    if proc_stat.is_file():
        try:
            parts = proc_stat.read_text(encoding="utf-8").split()
        except Exception:
            parts = []
        if len(parts) >= 3 and parts[2] == "Z":
            return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _send_signal_to_service(pid: int, sig: int) -> None:
    if int(pid or 0) <= 0:
        return
    with contextlib.suppress(ProcessLookupError):
        os.killpg(int(pid), sig)
        return
    with contextlib.suppress(ProcessLookupError):
        os.kill(int(pid), sig)


def _cleanup_runtime_files(service_name: str, *, run_dir: Path) -> None:
    for path in (_pid_file_path(service_name, run_dir=run_dir), _state_file_path(service_name, run_dir=run_dir)):
        if path.exists():
            path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
