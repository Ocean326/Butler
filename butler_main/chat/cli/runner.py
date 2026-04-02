from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from butler_main.chat.config_runtime import set_active_config
from butler_main.chat.pathing import resolve_butler_root
from butler_main.runtime_os.agent_runtime import cli_runner as cli_runtime_service, set_runtime_log_config

_CONFIG: dict = {}
_LEADING_PROCESS_ORDINAL_RE = re.compile(
    r"^\s*(?:(?:step|步骤)\s*)?(?:第\s*)?\d{1,2}(?:\s*[.:：、]\s*|\s*\)\s*)",
    re.IGNORECASE,
)


def _coerce_text(value: str | None) -> str:
    return str(value or "").strip()


def _copy_extra_actions(parser: argparse.ArgumentParser, base: argparse.ArgumentParser | None) -> None:
    if base is None:
        return
    skip_dests = {"config", "prompt", "stdin", "session", "stream", "no_stream", "preflight", "help"}
    for action in getattr(base, "_actions", []):
        if getattr(action, "dest", "") in skip_dests:
            continue
        parser._add_action(action)


def _load_cli_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    _CONFIG.clear()
    _CONFIG.update(dict(loaded or {}))
    _CONFIG["__config_path"] = os.path.abspath(config_path)
    workspace_root = _CONFIG.get("workspace_root")
    if workspace_root:
        _CONFIG["workspace_root"] = str(resolve_butler_root(workspace_root))
    else:
        _CONFIG["workspace_root"] = str(resolve_butler_root(Path(__file__).resolve().parents[3]))
    set_runtime_log_config(
        _CONFIG.get("__config_path"),
        (_CONFIG.get("logging") or {}).get("level") if isinstance(_CONFIG.get("logging"), dict) else None,
    )
    set_active_config(_CONFIG, config_path=_CONFIG.get("__config_path"))
    return dict(_CONFIG)


def _candidate_config_paths(default_config_name: str) -> list[str]:
    config_name = f"{default_config_name}.json"
    chat_root = Path(__file__).resolve().parents[1]
    return [
        str((chat_root / "configs" / config_name).resolve()),
        str((chat_root.parent / "butler_bot_code" / "configs" / config_name).resolve()),
    ]


def _resolve_default_config_path(default_config_name: str) -> str:
    for path in _candidate_config_paths(default_config_name):
        if os.path.isfile(path):
            return path
    return _candidate_config_paths(default_config_name)[-1]


def _resolve_session_id(raw_session: str | None) -> str:
    text = _coerce_text(raw_session)
    if text:
        return text
    return f"cli_session_{uuid4().hex[:10]}"


def _build_invocation_metadata(*, session_id: str, terminal_event_callback: Callable[[dict], None] | None = None) -> dict[str, object]:
    metadata: dict[str, object] = {
        "channel": "cli",
        "session_id": session_id,
        "actor_id": "cli_user",
    }
    if callable(terminal_event_callback):
        metadata["terminal_event_callback"] = terminal_event_callback
    return metadata


def _runtime_summary(run_agent_fn: Callable[..., str], prompt: str, invocation_metadata: dict[str, object]) -> dict[str, str]:
    describe_runtime = getattr(run_agent_fn, "describe_runtime_target", None)
    if not callable(describe_runtime):
        return {"kind": "run", "cli": "unknown", "model": "unknown"}
    try:
        payload = dict(describe_runtime(prompt, invocation_metadata=invocation_metadata) or {})
    except TypeError:
        payload = dict(describe_runtime(prompt) or {})
    except Exception:
        payload = {}
    return {
        "kind": _coerce_text(payload.get("kind")) or "run",
        "cli": _coerce_text(payload.get("cli")) or "unknown",
        "model": _coerce_text(payload.get("model")) or "unknown",
    }


def _write_text(stream, text: str) -> None:
    if not text:
        return
    stream.write(text)
    stream.flush()


def _stream_supports_color(stream) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    isatty = getattr(stream, "isatty", None)
    try:
        return bool(callable(isatty) and isatty())
    except Exception:
        return False


def _apply_color(text: str, color: str, *, enabled: bool) -> str:
    if not enabled or not color or not text:
        return text
    return f"{color}{text}\033[0m"


def _truncate_middle(text: str, limit: int = 140) -> str:
    raw = str(text or "").strip()
    if len(raw) <= limit:
        return raw
    half = max(16, (limit - 3) // 2)
    return f"{raw[:half]}...{raw[-half:]}"


def _classify_log_line(text: str, source: str) -> str:
    stripped = str(text or "").strip()
    if not stripped:
        return "plain"
    if source == "stderr":
        return "error"
    if stripped.startswith("[chat-runtime-total]") or stripped.startswith("[chat-runtime-timing]"):
        return "timing"
    if stripped.startswith("[codex usage]"):
        return "timing"
    if stripped.startswith("[chat-runtime") or stripped.startswith("[recent-") or stripped.startswith("[记忆]"):
        return "system"
    if stripped.startswith("[route=") or stripped.startswith("[chat-cli"):
        return "meta"
    return "plain"


def _strip_process_ordinal(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    return _LEADING_PROCESS_ORDINAL_RE.sub("", normalized).strip()


def _overlap_suffix_prefix(left: str, right: str) -> int:
    limit = min(len(left), len(right))
    for width in range(limit, 0, -1):
        if left[-width:] == right[:width]:
            return width
    return 0


@dataclass(slots=True)
class TerminalConsole:
    stream: object
    color_enabled: bool = False
    assistant_line_open: bool = False
    status_window_enabled: bool = False
    status_window_active: bool = False
    status_window_height: int = 3
    status_lines: deque[tuple[str, str]] = field(default_factory=lambda: deque(maxlen=3))

    COLOR_META = "\033[36m"
    COLOR_SYSTEM = "\033[38;5;110m"
    COLOR_TIMING = "\033[38;5;244m"
    COLOR_EVENT = "\033[38;5;221m"
    COLOR_ERROR = "\033[31m"

    def __post_init__(self) -> None:
        self.color_enabled = _stream_supports_color(self.stream)
        self.status_window_enabled = self.color_enabled and os.environ.get("BUTLER_CLI_STATUS_WINDOW", "1") != "0"

    def _clear_status_window(self) -> None:
        if not self.status_window_enabled or not self.status_window_active:
            return
        _write_text(self.stream, "\r")
        if self.status_window_height > 1:
            _write_text(self.stream, f"\033[{self.status_window_height - 1}A")
        for _ in range(self.status_window_height):
            _write_text(self.stream, "\033[2K\r\033[M")
        self.status_window_active = False
        self.status_lines.clear()

    def _render_status_window(self) -> None:
        if not self.status_window_enabled:
            return
        padded = list(self.status_lines)[-self.status_window_height :]
        while len(padded) < self.status_window_height:
            padded.insert(0, ("", ""))
        if self.status_window_active:
            _write_text(self.stream, "\r")
            if self.status_window_height > 1:
                _write_text(self.stream, f"\033[{self.status_window_height - 1}A")
        else:
            self.ensure_line_break()
        for index, (line, color) in enumerate(padded):
            _write_text(self.stream, "\033[2K\r")
            if line:
                _write_text(self.stream, _apply_color(line, color, enabled=self.color_enabled))
            if index < self.status_window_height - 1:
                _write_text(self.stream, "\n")
        self.status_window_active = True

    def _push_status_line(self, text: str, *, color: str) -> bool:
        if not self.status_window_enabled or self.assistant_line_open:
            return False
        line = _truncate_middle(text.rstrip("\n"), limit=180)
        self.status_lines.append((line, color))
        self._render_status_window()
        return True

    def write_plain(self, text: str) -> None:
        self._clear_status_window()
        _write_text(self.stream, text)
        if text.endswith("\n"):
            self.assistant_line_open = False

    def ensure_line_break(self) -> None:
        if self.assistant_line_open:
            _write_text(self.stream, "\n")
            self.assistant_line_open = False

    def write_assistant_prefix(self, prefix: str) -> None:
        self._clear_status_window()
        self.ensure_line_break()
        _write_text(self.stream, prefix)
        self.assistant_line_open = True

    def write_assistant_text(self, text: str) -> None:
        if not text:
            return
        self._clear_status_window()
        _write_text(self.stream, text)
        self.assistant_line_open = not text.endswith("\n")

    def write_assistant_final_marker(self) -> None:
        self._clear_status_window()
        self.ensure_line_break()
        marker = _apply_color("[final]\n", self.COLOR_META, enabled=self.color_enabled)
        _write_text(self.stream, marker)
        self.assistant_line_open = False

    def write_meta(self, text: str) -> None:
        self._clear_status_window()
        self.ensure_line_break()
        _write_text(self.stream, _apply_color(text, self.COLOR_META, enabled=self.color_enabled))
        if text.endswith("\n"):
            self.assistant_line_open = False

    def emit_log_line(self, text: str, *, source: str = "stdout") -> None:
        category = _classify_log_line(text, source)
        if category == "plain":
            self.write_plain(text)
            return
        self.ensure_line_break()
        color = {
            "meta": self.COLOR_META,
            "system": self.COLOR_SYSTEM,
            "timing": self.COLOR_TIMING,
            "error": self.COLOR_ERROR,
        }.get(category, self.COLOR_SYSTEM)
        if category in {"system", "timing"} and self._push_status_line(text, color=color):
            self.assistant_line_open = False
            return
        _write_text(self.stream, _apply_color(text, color, enabled=self.color_enabled))
        if text.endswith("\n"):
            self.assistant_line_open = False

    def emit_runtime_event(self, event: dict) -> None:
        kind = str(event.get("kind") or "").strip()
        text = _strip_process_ordinal(str(event.get("text") or ""))
        if not text:
            return
        if kind == "command":
            status = str(event.get("status") or "").strip().lower() or "update"
            label = {
                "in_progress": "running",
                "started": "running",
                "completed": "completed",
                "failed": "failed",
            }.get(status, status)
            line = f"[codex {label}] {_truncate_middle(text)}\n"
            if self._push_status_line(line, color=self.COLOR_EVENT):
                self.assistant_line_open = False
                return
            self.ensure_line_break()
            _write_text(self.stream, _apply_color(line, self.COLOR_EVENT, enabled=self.color_enabled))
            self.assistant_line_open = False
            return
        if kind == "usage":
            self.emit_log_line(f"[codex usage] {text}\n")
            return
        if kind in {"stderr", "error"}:
            self.emit_log_line(f"[codex stderr] {text}\n", source="stderr")


@dataclass(slots=True)
class _CapturedTerminalStream:
    console: TerminalConsole
    source: str
    buffer: str = ""

    def write(self, text: str) -> int:
        value = str(text or "")
        if not value:
            return 0
        self.buffer += value
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            self.console.emit_log_line(line + "\n", source=self.source)
        if self.buffer and not self.buffer.lstrip().startswith("["):
            fragment = self.buffer
            self.buffer = ""
            self.console.write_plain(fragment)
        return len(value)

    def flush(self) -> None:
        if self.buffer:
            self.console.emit_log_line(self.buffer, source=self.source)
            self.buffer = ""
        flush = getattr(self.console.stream, "flush", None)
        if callable(flush):
            flush()

    def isatty(self) -> bool:
        isatty = getattr(self.console.stream, "isatty", None)
        try:
            return bool(callable(isatty) and isatty())
        except Exception:
            return False


@contextlib.contextmanager
def _install_terminal_capture(console: TerminalConsole):
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = _CapturedTerminalStream(console=console, source="stdout")
    sys.stderr = _CapturedTerminalStream(console=console, source="stderr")
    try:
        yield
    finally:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        sys.stdout = original_stdout
        sys.stderr = original_stderr


@dataclass(slots=True)
class TerminalStreamPrinter:
    console: TerminalConsole
    prefix: str = "管家> "
    emitted_text: str = ""
    latest_snapshot: str = ""
    started: bool = False
    unstable: bool = False

    def start(self) -> None:
        if self.started:
            return
        self.console.write_assistant_prefix(self.prefix)
        self.started = True

    def on_segment(self, segment: str) -> None:
        text = str(segment or "")
        if not text:
            return
        self.start()
        self.latest_snapshot = text
        if not self.emitted_text:
            self.console.write_assistant_text(text)
            self.emitted_text = text
            return
        if text == self.emitted_text or text in self.emitted_text:
            return
        if text.startswith(self.emitted_text):
            delta = text[len(self.emitted_text):]
            self.console.write_assistant_text(delta)
            self.emitted_text = text
            return
        overlap = _overlap_suffix_prefix(self.emitted_text, text)
        if overlap > 0 and overlap < len(text):
            delta = text[overlap:]
            self.console.write_assistant_text(delta)
            self.emitted_text += delta
            return
        self.unstable = True

    def finalize(self, final_text: str) -> None:
        text = str(final_text or "")
        if not text:
            if self.started:
                self.console.write_plain("\n")
            return
        if not self.started:
            self.start()
        if text.startswith(self.emitted_text):
            delta = text[len(self.emitted_text):]
            if delta:
                self.console.write_assistant_text(delta)
        elif text != self.emitted_text:
            if self.emitted_text:
                self.console.write_assistant_final_marker()
            self.console.write_assistant_text(text)
        self.console.write_plain("\n")
        self.emitted_text = text
        self.latest_snapshot = text


def _invoke_run_agent(
    run_agent_fn: Callable[..., str],
    prompt: str,
    *,
    stream_enabled: bool,
    invocation_metadata: dict[str, object],
    printer: TerminalStreamPrinter | None = None,
) -> str:
    kwargs = {"invocation_metadata": invocation_metadata}
    if stream_enabled and printer is not None:
        kwargs["stream_output"] = True
        kwargs["stream_callback"] = printer.on_segment
    return run_agent_fn(prompt, **kwargs)


def _call_on_reply_sent(on_reply_sent: Callable[[str, str], None] | None, prompt: str, result: str) -> None:
    if on_reply_sent is None or not _coerce_text(result):
        return
    on_reply_sent(prompt, result)


def _print_banner(*, stream, bot_name: str, config_path: str, cfg: dict, session_id: str, run_agent_fn: Callable[..., str]) -> None:
    workspace = str(cfg.get("workspace_root") or ".").strip() or "."
    runtime = _runtime_summary(run_agent_fn, "", _build_invocation_metadata(session_id=session_id))
    lines = [
        "=" * 58,
        f"  {bot_name} · Chat CLI",
        f"  session={session_id}",
        f"  config={config_path}",
        f"  workspace={workspace}",
        f"  runtime={runtime['cli']} | model={runtime['model']}",
        "  回车发送 | exit / quit / /exit 退出",
        "=" * 58,
        "",
    ]
    _write_text(stream, "\n".join(lines))


def _print_preflight(*, stream, config_path: str, cfg: dict) -> int:
    available = cli_runtime_service.available_cli_modes(cfg)
    active = str(cli_runtime_service.get_cli_runtime_settings(cfg).get("active") or "unknown").strip() or "unknown"
    workspace = str(cfg.get("workspace_root") or ".").strip() or "."
    lines = [
        "[chat-cli preflight]",
        f"config={config_path}",
        f"workspace_root={workspace}",
        f"active_cli={active}",
        f"available_clis={', '.join(available) if available else '-'}",
    ]
    _write_text(stream, "\n".join(lines) + "\n")
    return 0


def _build_cli_arg_parser(base: argparse.ArgumentParser | None, bot_name: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"{bot_name} Chat CLI")
    parser.add_argument("--config", "-c", help="配置文件路径")
    parser.add_argument("--prompt", "-p", help="单轮对话 prompt")
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读取单轮 prompt")
    parser.add_argument("--session", help="指定稳定会话 id，用于持续上下文")
    parser.add_argument("--stream", action="store_true", help="显式启用流式终端输出")
    parser.add_argument("--no-stream", action="store_true", help="关闭流式终端输出")
    parser.add_argument("--preflight", action="store_true", help="仅加载配置并打印 CLI 运行摘要")
    _copy_extra_actions(parser, base)
    return parser


def _read_prompt_from_args(args: argparse.Namespace) -> str | None:
    prompt = _coerce_text(getattr(args, "prompt", None))
    if prompt:
        return prompt
    if getattr(args, "stdin", False):
        text = sys.stdin.read()
        return text.strip() if text else ""
    return None


def _print_turn_header(*, stream, runtime: dict[str, str], session_id: str, stream_enabled: bool) -> None:
    header = (
        f"[route=chat cli={runtime['cli']} model={runtime['model']} "
        f"session={session_id} stream={'on' if stream_enabled else 'off'}]"
    )
    _write_text(stream, header + "\n")


def _run_single_turn(
    *,
    prompt: str,
    run_agent_fn: Callable[..., str],
    session_id: str,
    stream_enabled: bool,
    on_reply_sent: Callable[[str, str], None] | None,
    console: TerminalConsole,
) -> int:
    printer = TerminalStreamPrinter(console=console) if stream_enabled else None
    invocation_metadata = _build_invocation_metadata(
        session_id=session_id,
        terminal_event_callback=console.emit_runtime_event if stream_enabled else None,
    )
    runtime = _runtime_summary(run_agent_fn, prompt, invocation_metadata)
    _print_turn_header(stream=console.stream, runtime=runtime, session_id=session_id, stream_enabled=stream_enabled)
    try:
        with _install_terminal_capture(console):
            result = _invoke_run_agent(
                run_agent_fn,
                prompt,
                stream_enabled=stream_enabled,
                invocation_metadata=invocation_metadata,
                printer=printer,
            )
    except Exception as exc:
        console.emit_log_line(f"[chat-cli] turn failed: {type(exc).__name__}: {exc}\n", source="stderr")
        return 1
    if printer is not None:
        printer.finalize(result)
    else:
        console.write_plain(f"管家> {result}\n")
    with _install_terminal_capture(console):
        _call_on_reply_sent(on_reply_sent, prompt, result)
    return 0


def _run_repl(
    *,
    bot_name: str,
    run_agent_fn: Callable[..., str],
    session_id: str,
    stream_enabled: bool,
    on_reply_sent: Callable[[str, str], None] | None,
    console: TerminalConsole,
) -> int:
    del bot_name
    while True:
        try:
            with _install_terminal_capture(console):
                user_input = input("你> ").strip()
        except EOFError:
            console.write_plain("\n")
            return 0
        except KeyboardInterrupt:
            console.write_meta("\n[chat-cli] 已退出。\n")
            return 0
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "/exit", "/quit"}:
            console.write_meta("[chat-cli] 已退出。\n")
            return 0
        rc = _run_single_turn(
            prompt=user_input,
            run_agent_fn=run_agent_fn,
            session_id=session_id,
            stream_enabled=stream_enabled,
            on_reply_sent=on_reply_sent,
            console=console,
        )
        if rc != 0:
            return rc


def run_chat_cli(
    *,
    default_config_name: str,
    bot_name: str,
    run_agent_fn: Callable[..., str],
    supports_images: bool = True,
    supports_stream_segment: bool = True,
    send_output_files: bool = True,
    args_extra: argparse.ArgumentParser | None = None,
    local_test_fn: Callable[[str, argparse.Namespace], str] | Callable[[str], str] | None = None,
    on_bot_started: Callable[[], None] | None = None,
    on_reply_sent: Callable[[str, str], None] | None = None,
    immediate_receipt_text: str | None = None,
    argv: list[str] | None = None,
) -> int:
    del supports_images, supports_stream_segment, send_output_files, local_test_fn, immediate_receipt_text
    base_stdout = sys.stdout
    parser = _build_cli_arg_parser(args_extra, bot_name)
    args = parser.parse_args(argv)
    config_path = args.config or _resolve_default_config_path(default_config_name)
    if not os.path.isfile(config_path):
        print(f"请指定 --config 或确保存在 {config_path}", file=sys.stderr)
        return 1
    cfg = _load_cli_config(config_path)
    if getattr(args, "preflight", False):
        return _print_preflight(stream=base_stdout, config_path=config_path, cfg=cfg)

    stream_enabled = False if getattr(args, "no_stream", False) else True
    if getattr(args, "stream", False):
        stream_enabled = True
    session_id = _resolve_session_id(getattr(args, "session", None))
    console = TerminalConsole(stream=base_stdout)
    prompt = _read_prompt_from_args(args)
    with _install_terminal_capture(console):
        if prompt is not None:
            return _run_single_turn(
                prompt=prompt,
                run_agent_fn=run_agent_fn,
                session_id=session_id,
                stream_enabled=stream_enabled,
                on_reply_sent=on_reply_sent,
                console=console,
            )
        _print_banner(
            stream=base_stdout,
            bot_name=bot_name,
            config_path=config_path,
            cfg=cfg,
            session_id=session_id,
            run_agent_fn=run_agent_fn,
        )
        if on_bot_started is not None:
            def _boot_background_services() -> None:
                try:
                    on_bot_started()
                except Exception as exc:
                    print(f"on_bot_started 执行异常: {exc}", file=sys.stderr)

            threading.Thread(target=_boot_background_services, name="butler-cli-startup", daemon=True).start()
        return _run_repl(
            bot_name=bot_name,
            run_agent_fn=run_agent_fn,
            session_id=session_id,
            stream_enabled=stream_enabled,
            on_reply_sent=on_reply_sent,
            console=console,
        )


__all__ = [
    "TerminalConsole",
    "TerminalStreamPrinter",
    "run_chat_cli",
]
