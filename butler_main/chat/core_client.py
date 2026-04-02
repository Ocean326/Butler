from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from butler_main.chat.config_runtime import resolve_default_config_path
from butler_main.chat.core_defaults import DEFAULT_CORE_HOST, DEFAULT_CORE_PORT
from butler_main.chat.pathing import resolve_butler_root
from butler_main.runtime_os.fs_retention import DEFAULT_RETENTION_DAYS, prune_path_children


def _base_url(host: str, port: int) -> str:
    return f"http://{str(host or DEFAULT_CORE_HOST).strip() or DEFAULT_CORE_HOST}:{int(port or DEFAULT_CORE_PORT)}"


def _read_json(url: str, *, payload: dict | None = None, timeout_seconds: float = 5.0) -> dict:
    if payload is None:
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
    else:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            url,
            data=raw,
            headers={"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"},
            method="POST",
        )
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def _is_core_running(host: str, port: int) -> bool:
    try:
        payload = _read_json(f"{_base_url(host, port)}/health", timeout_seconds=1.5)
    except Exception:
        return False
    return bool(payload.get("ok"))


def _runtime_dir() -> Path:
    runtime_dir = resolve_butler_root(Path(__file__).resolve().parents[2]) / "工作区" / "temp" / "chat_core"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    prune_path_children(
        runtime_dir,
        retention_days=DEFAULT_RETENTION_DAYS,
        include_files=True,
        include_dirs=True,
    )
    return runtime_dir


def _launch_detached_core(*, config_path: str, host: str, port: int, channels: str) -> None:
    root = resolve_butler_root(Path(__file__).resolve().parents[2])
    runtime_dir = _runtime_dir()
    stdout_path = runtime_dir / "chat_core.out.log"
    stderr_path = runtime_dir / "chat_core.err.log"
    pid_path = runtime_dir / "chat_core.pid"
    launcher = root / "butler_main" / "butler_bot_code" / "scripts" / "launch_detached.py"
    python_path = root / ".venv" / "Scripts" / "python.exe"
    if not python_path.is_file():
        python_path = Path(sys.executable).resolve()
    command = [
        str(python_path),
        str(launcher),
        "--cwd",
        str(root),
        "--stdout",
        str(stdout_path),
        "--stderr",
        str(stderr_path),
        "--pid-file",
        str(pid_path),
        "--",
        str(python_path),
        "-m",
        "butler_main.chat.core",
        "--config",
        str(config_path),
        "--host",
        str(host),
        "--port",
        str(int(port)),
        "--channels",
        str(channels or "cli,feishu,weixin"),
    ]
    subprocess.run(command, check=True)


def _ensure_core_running(*, config_path: str, host: str, port: int, autostart: bool, channels: str) -> None:
    if _is_core_running(host, port):
        return
    if not autostart:
        raise RuntimeError("chat core is not running")
    _launch_detached_core(config_path=config_path, host=host, port=port, channels=channels)
    deadline = time.time() + 20.0
    while time.time() < deadline:
        if _is_core_running(host, port):
            return
        time.sleep(0.5)
    raise TimeoutError("chat core did not become ready in time")


def _chat_once(*, prompt: str, session_id: str, host: str, port: int) -> dict:
    return _read_json(
        f"{_base_url(host, port)}/v1/chat",
        payload={
            "prompt": str(prompt or ""),
            "session_id": str(session_id or "").strip(),
            "actor_id": "cli_user",
        },
        timeout_seconds=300.0,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Butler local client")
    parser.add_argument("--config", "-c", default="", help="配置文件路径；默认加载 butler_bot.json")
    parser.add_argument("--host", default=DEFAULT_CORE_HOST, help="core host")
    parser.add_argument("--port", type=int, default=DEFAULT_CORE_PORT, help="core port")
    parser.add_argument("--prompt", "-p", default="", help="单轮 prompt")
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读取单轮 prompt")
    parser.add_argument("--session", default="", help="会话 id；默认自动生成")
    parser.add_argument("--no-autostart", action="store_true", help="若 core 未运行则直接失败")
    parser.add_argument("--core-channels", default=os.environ.get("BUTLER_CORE_CHANNELS", "cli,feishu,weixin"), help="自动拉起 core 时启用的入口")
    args = parser.parse_args(argv)

    config_path = str(args.config or "").strip() or resolve_default_config_path("butler_bot")
    host = str(args.host or DEFAULT_CORE_HOST).strip() or DEFAULT_CORE_HOST
    port = int(args.port or DEFAULT_CORE_PORT)
    try:
        _ensure_core_running(
            config_path=config_path,
            host=host,
            port=port,
            autostart=not bool(args.no_autostart),
            channels=str(args.core_channels or "cli,feishu,weixin"),
        )
    except Exception as exc:
        print(f"[butler] core unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    session_id = str(args.session or f"cli_{uuid4().hex[:10]}").strip()
    prompt = str(args.prompt or "").strip()
    if not prompt and bool(args.stdin):
        prompt = sys.stdin.read().strip()
    if prompt:
        try:
            payload = _chat_once(prompt=prompt, session_id=session_id, host=host, port=port)
        except (URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"[butler] request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        print(str(payload.get("reply") or "").strip(), flush=True)
        return 0

    print(f"Butler CLI 已连接 core：{_base_url(host, port)}", flush=True)
    print("输入消息后回车发送 | exit / quit 退出", flush=True)
    while True:
        try:
            user_input = input("你> ").strip()
        except EOFError:
            break
        except KeyboardInterrupt:
            print("")
            break
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "/exit", "/quit"}:
            break
        try:
            payload = _chat_once(prompt=user_input, session_id=session_id, host=host, port=port)
        except (URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"[butler] request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        print(str(payload.get("reply") or "").strip(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
