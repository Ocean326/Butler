from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4

from butler_main.chat.config_runtime import load_active_config, resolve_default_config_path
from butler_main.chat.core_defaults import (
    DEFAULT_CORE_CHANNELS,
    DEFAULT_CORE_HOST,
    DEFAULT_CORE_PORT,
    DEFAULT_WEIXIN_OFFICIAL_BRIDGE_BASE_URL,
    DEFAULT_WEIXIN_OFFICIAL_CDN_BASE_URL,
)
from butler_main.chat.pathing import resolve_butler_root


@dataclass(slots=True, frozen=True)
class WeixinBindingConfig:
    binding_id: str
    state_dir: str
    bridge_base_url: str
    cdn_base_url: str
    session_file: str = ""
    login_timeout_ms: int = 0
    reuse_session: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "state_dir": self.state_dir,
            "bridge_base_url": self.bridge_base_url,
            "cdn_base_url": self.cdn_base_url,
            "session_file": self.session_file,
            "login_timeout_ms": self.login_timeout_ms,
            "reuse_session": self.reuse_session,
        }


@dataclass(slots=True)
class ChannelRuntimeStatus:
    name: str
    enabled: bool
    started: bool = False
    healthy: bool = False
    last_error: str = ""
    last_started_at: float = 0.0
    thread_name: str = ""

    def mark_started(self, *, thread_name: str) -> None:
        self.started = True
        self.healthy = True
        self.last_error = ""
        self.last_started_at = time.time()
        self.thread_name = thread_name

    def mark_failed(self, error: str) -> None:
        self.healthy = False
        self.last_error = str(error or "").strip()

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "started": self.started,
            "healthy": self.healthy,
            "last_error": self.last_error,
            "last_started_at": self.last_started_at,
            "thread_name": self.thread_name,
        }


@dataclass(slots=True)
class ChatCoreService:
    run_agent_fn: Any
    after_reply_fn: Any
    config_path: str
    channels: tuple[str, ...]
    weixin_state_dir: str
    weixin_official_bridge_base_url: str
    weixin_official_cdn_base_url: str
    weixin_bindings: tuple[WeixinBindingConfig, ...] = ()
    weixin_status_provider: Any = None
    statuses: dict[str, ChannelRuntimeStatus] = field(default_factory=dict)
    _status_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        normalized_channels = tuple(dict.fromkeys(str(item or "").strip().lower() for item in self.channels if str(item or "").strip()))
        self.channels = normalized_channels or DEFAULT_CORE_CHANNELS
        if not self.weixin_bindings:
            self.weixin_bindings = (
                WeixinBindingConfig(
                    binding_id="default",
                    state_dir=str(self.weixin_state_dir or "").strip(),
                    bridge_base_url=str(self.weixin_official_bridge_base_url or "").strip(),
                    cdn_base_url=str(self.weixin_official_cdn_base_url or "").strip(),
                ),
            )
        self.weixin_state_dir = str(self.weixin_bindings[0].state_dir if self.weixin_bindings else self.weixin_state_dir).strip()
        self.statuses = {
            "cli": ChannelRuntimeStatus(name="cli", enabled="cli" in self.channels),
            "feishu": ChannelRuntimeStatus(name="feishu", enabled="feishu" in self.channels),
            "weixin": ChannelRuntimeStatus(name="weixin", enabled="weixin" in self.channels),
        }

    def start_background_services(self) -> None:
        from butler_main.chat import engine as chat_engine

        chat_engine.MEMORY_PROVIDER.start_background_services()

    def execute_cli_turn(self, prompt: str, *, session_id: str = "", actor_id: str = "cli_user") -> dict[str, Any]:
        clean_prompt = str(prompt or "").strip()
        if not clean_prompt:
            raise ValueError("missing prompt")
        effective_session_id = str(session_id or f"core_cli_{uuid4().hex[:10]}").strip()
        invocation_metadata = {
            "channel": "cli",
            "session_id": effective_session_id,
            "actor_id": str(actor_id or "cli_user").strip() or "cli_user",
        }
        reply = str(
            self.run_agent_fn(
                clean_prompt,
                invocation_metadata=invocation_metadata,
            )
            or ""
        ).strip()
        if reply:
            self.after_reply_fn(clean_prompt, reply)
        return {
            "reply": reply,
            "session_id": effective_session_id,
            "status": self.status_snapshot(),
        }

    def status_snapshot(self) -> dict[str, Any]:
        with self._status_lock:
            channels = {name: status.as_dict() for name, status in self.statuses.items()}
        weixin_runtime = self._load_weixin_runtime_status()
        return {
            "ok": True,
            "config_path": self.config_path,
            "channels": channels,
            "weixin_state_dir": self.weixin_state_dir,
            "weixin_bindings": [binding.as_dict() for binding in self.weixin_bindings],
            "weixin_runtime": weixin_runtime,
            "pid": os.getpid(),
        }

    def mark_started(self, channel: str, *, thread_name: str) -> None:
        with self._status_lock:
            status = self.statuses.get(channel)
            if status is not None:
                status.mark_started(thread_name=thread_name)

    def mark_failed(self, channel: str, error: str) -> None:
        with self._status_lock:
            status = self.statuses.get(channel)
            if status is not None:
                status.mark_failed(error)

    def _load_weixin_runtime_status(self) -> dict[str, Any]:
        provider = self.weixin_status_provider or _default_weixin_status_provider
        if not callable(provider):
            return {}
        try:
            snapshot = provider()
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        return dict(snapshot) if isinstance(snapshot, dict) else {}


def create_chat_core_http_server(
    service: ChatCoreService,
    *,
    host: str = DEFAULT_CORE_HOST,
    port: int = DEFAULT_CORE_PORT,
) -> ThreadingHTTPServer:
    class _Handler(BaseHTTPRequestHandler):
        server_version = "ButlerChatCore/1.0"

        def do_GET(self) -> None:
            if self.path in {"/", ""}:
                body = _render_index_html(service)
                payload = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if self.path == "/health":
                self._write_json(200, service.status_snapshot())
                return
            self._write_json(404, {"ok": False, "error": "not_found"})

        def do_POST(self) -> None:
            if self.path != "/v1/chat":
                self._write_json(404, {"ok": False, "error": "not_found"})
                return
            try:
                content_length = int(self.headers.get("Content-Length") or "0")
            except ValueError:
                content_length = 0
            raw = self.rfile.read(max(content_length, 0)).decode("utf-8") if content_length > 0 else "{}"
            try:
                payload = json.loads(raw or "{}")
            except json.JSONDecodeError:
                self._write_json(400, {"ok": False, "error": "invalid_json"})
                return
            if not isinstance(payload, dict):
                self._write_json(400, {"ok": False, "error": "invalid_payload"})
                return
            try:
                result = service.execute_cli_turn(
                    str(payload.get("prompt") or ""),
                    session_id=str(payload.get("session_id") or ""),
                    actor_id=str(payload.get("actor_id") or "cli_user"),
                )
            except ValueError as exc:
                self._write_json(400, {"ok": False, "error": str(exc)})
                return
            except Exception as exc:
                self._write_json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
                return
            self._write_json(200, {"ok": True, **result})

        def log_message(self, format: str, *args) -> None:
            del format, args

        def _write_json(self, status_code: int, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return ThreadingHTTPServer((host, int(port)), _Handler)


def _render_index_html(service: ChatCoreService) -> str:
    snapshot = service.status_snapshot()
    channel_lines = []
    for item in snapshot.get("channels", {}).values():
        channel_lines.append(
            f"<li><strong>{item.get('name')}</strong> enabled={item.get('enabled')} started={item.get('started')} healthy={item.get('healthy')}"
            + (f" error={item.get('last_error')}" if item.get("last_error") else "")
            + "</li>"
        )
    qr_hints: list[str] = []
    for binding in list(snapshot.get("weixin_bindings") or []):
        if not isinstance(binding, dict):
            continue
        binding_id = str(binding.get("binding_id") or "").strip()
        state_dir = str(binding.get("state_dir") or "").strip()
        if not state_dir:
            continue
        local_qr_page = Path(state_dir) / "weixin_login_qr.html"
        if local_qr_page.is_file():
            label = f"{binding_id}: " if binding_id else ""
            qr_hints.append(f"<p>微信登录页已生成：{label}<code>{local_qr_page}</code></p>")
    qr_hint = "".join(qr_hints)
    weixin_runtime = snapshot.get("weixin_runtime") if isinstance(snapshot.get("weixin_runtime"), dict) else {}
    weixin_section = ""
    if weixin_runtime:
        conversation_lines = []
        for item in list(weixin_runtime.get("recent_conversations") or [])[:6]:
            if not isinstance(item, dict):
                continue
            binding_id = str(item.get("binding_id") or "").strip()
            conversation_lines.append(
                "<li><code>"
                + str(item.get("conversation_key") or "")
                + "</code>"
                + (f" binding={binding_id}" if binding_id else "")
                + f" in_flight={item.get('in_flight')} last_error={item.get('last_error') or '-'}"
                + "</li>"
            )
        binding_lines = []
        for item in list(weixin_runtime.get("bindings") or []):
            if not isinstance(item, dict):
                continue
            binding_lines.append(
                "<li><strong>"
                + str(item.get("binding_id") or "(default)")
                + "</strong>"
                + f" connected={item.get('connected')} account=<code>{item.get('account_id') or ''}</code>"
                + f" active={item.get('active_conversation_count') or 0}"
                + f" running={item.get('running_conversation_count') or 0}"
                + (f" error={item.get('last_error')}" if item.get("last_error") else "")
                + "</li>"
            )
        weixin_section = (
            "<h2>Weixin Runtime</h2>"
            f"<p>登录状态：{weixin_runtime.get('login_state') or 'idle'} | 已连接：{weixin_runtime.get('connected')} | 绑定数：{weixin_runtime.get('binding_count') or 0}</p>"
            f"<p>微信活跃会话：{weixin_runtime.get('active_conversation_count') or 0} | 执行中：{weixin_runtime.get('running_conversation_count') or 0}</p>"
            + (
                "<ul>" + "".join(binding_lines) + "</ul>"
                if binding_lines
                else ""
            )
            + (
                "<ul>" + "".join(conversation_lines) + "</ul>"
                if conversation_lines
                else "<p>暂无活跃微信会话</p>"
            )
        )
    return (
        "<html><head><meta charset='utf-8'><title>Butler Core</title></head><body>"
        "<h1>Butler Core</h1>"
        f"<p>PID: {snapshot.get('pid')}</p>"
        f"<p>Config: <code>{snapshot.get('config_path')}</code></p>"
        "<h2>Channels</h2><ul>"
        + "".join(channel_lines)
        + "</ul>"
        + weixin_section
        + qr_hint
        + "<p>CLI API: <code>POST /v1/chat</code></p>"
        + "</body></html>"
    )


def _start_listener_thread(
    service: ChatCoreService,
    channel: str,
    target,
    *,
    name: str,
    report_channel_failure: bool = True,
) -> threading.Thread:
    def _runner() -> None:
        service.mark_started(channel, thread_name=name)
        try:
            target()
        except Exception as exc:
            if report_channel_failure:
                service.mark_failed(channel, f"{type(exc).__name__}: {exc}")
            print(f"[chat-core] {channel} listener stopped: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        else:
            if report_channel_failure:
                service.mark_failed(channel, "listener exited")
            print(f"[chat-core] {channel} listener exited", file=sys.stderr, flush=True)

    thread = threading.Thread(target=_runner, name=name, daemon=True)
    thread.start()
    return thread


def _default_weixin_state_dir() -> str:
    root = resolve_butler_root(__file__)
    return str(root / "工作区" / "temp" / "weixin_runtime" / "weixin_state_official")


def _parse_channels(raw: str) -> tuple[str, ...]:
    values = [str(item or "").strip().lower() for item in str(raw or "").split(",")]
    return tuple(item for item in values if item)


def _run_feishu_core_listener(config: dict, chat_engine) -> int:
    from butler_main.chat.feishu_bot.transport import run_feishu_bot_with_loaded_config

    return run_feishu_bot_with_loaded_config(
        config,
        bot_name="管家bot",
        run_agent_fn=chat_engine.run_agent,
        supports_images=True,
        supports_stream_segment=True,
        send_output_files=True,
        on_bot_started=None,
        on_reply_sent=chat_engine._after_reply_persist_memory_async,
        immediate_receipt_text="处理中，{cli} {model} 模型调用中…",
    )


def _run_weixin_core_listener(binding: WeixinBindingConfig, chat_engine) -> int:
    from butler_main.chat.weixi.client import run_weixin_bridge_client

    return run_weixin_bridge_client(
        run_agent_fn=chat_engine.run_agent,
        binding_id=binding.binding_id,
        bridge_base_url=binding.bridge_base_url,
        cdn_base_url=binding.cdn_base_url,
        state_dir=binding.state_dir,
        session_file=binding.session_file,
        login_timeout_ms=binding.login_timeout_ms or 8 * 60_000,
        reuse_session=binding.reuse_session,
        on_reply_sent=chat_engine._after_reply_persist_memory_async,
    )


def _default_weixin_status_provider() -> dict[str, Any]:
    from butler_main.chat.weixi.status import get_weixin_runtime_status_snapshot

    return dict(get_weixin_runtime_status_snapshot() or {})


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _normalize_weixin_binding(
    payload: dict[str, Any],
    *,
    fallback_binding_id: str,
    default_state_dir: str,
    default_bridge_base_url: str,
    default_cdn_base_url: str,
) -> WeixinBindingConfig:
    binding_id = str(payload.get("binding_id") or fallback_binding_id).strip() or fallback_binding_id
    state_dir = str(payload.get("state_dir") or payload.get("weixin_state_dir") or default_state_dir).strip()
    bridge_base_url = str(payload.get("bridge_base_url") or payload.get("base_url") or default_bridge_base_url).strip()
    cdn_base_url = str(payload.get("cdn_base_url") or payload.get("cdn_url") or default_cdn_base_url).strip()
    return WeixinBindingConfig(
        binding_id=binding_id,
        state_dir=state_dir,
        bridge_base_url=bridge_base_url,
        cdn_base_url=cdn_base_url,
        session_file=str(payload.get("session_file") or "").strip(),
        login_timeout_ms=max(int(payload.get("login_timeout_ms") or 0), 0),
        reuse_session=_coerce_bool(payload.get("reuse_session"), default=True),
    )


def _resolve_weixin_bindings(
    *,
    config: dict[str, Any],
    default_state_dir: str,
    default_bridge_base_url: str,
    default_cdn_base_url: str,
) -> tuple[WeixinBindingConfig, ...]:
    weixin_cfg = config.get("weixin") if isinstance(config.get("weixin"), dict) else {}
    raw_bindings = weixin_cfg.get("bindings") if isinstance(weixin_cfg.get("bindings"), list) else []
    bindings: list[WeixinBindingConfig] = []
    for index, item in enumerate(raw_bindings, start=1):
        if not isinstance(item, dict):
            continue
        if not _coerce_bool(item.get("enabled"), default=True):
            continue
        bindings.append(
            _normalize_weixin_binding(
                item,
                fallback_binding_id=f"binding_{index}",
                default_state_dir=default_state_dir,
                default_bridge_base_url=default_bridge_base_url,
                default_cdn_base_url=default_cdn_base_url,
            )
        )
    if bindings:
        return tuple(bindings)
    return (
        _normalize_weixin_binding(
            {},
            fallback_binding_id="default",
            default_state_dir=default_state_dir,
            default_bridge_base_url=default_bridge_base_url,
            default_cdn_base_url=default_cdn_base_url,
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Butler chat core service")
    parser.add_argument("--config", "-c", default="", help="配置文件路径；默认加载 butler_bot.json")
    parser.add_argument("--host", default=DEFAULT_CORE_HOST, help="core HTTP host")
    parser.add_argument("--port", type=int, default=DEFAULT_CORE_PORT, help="core HTTP port")
    parser.add_argument("--channels", default="cli,feishu,weixin", help="启用入口，逗号分隔：cli,feishu,weixin")
    parser.add_argument("--weixin-state-dir", default=_default_weixin_state_dir(), help="微信官方监听状态目录")
    parser.add_argument("--weixin-official-bridge-base-url", default=DEFAULT_WEIXIN_OFFICIAL_BRIDGE_BASE_URL, help="微信官方 bridge API 根地址")
    parser.add_argument("--weixin-official-cdn-base-url", default=DEFAULT_WEIXIN_OFFICIAL_CDN_BASE_URL, help="微信官方 CDN 根地址")
    args = parser.parse_args(argv)

    config_path = str(args.config or "").strip() or resolve_default_config_path("butler_bot")
    if not os.path.isfile(config_path):
        print(f"[chat-core] config not found: {config_path}", file=sys.stderr, flush=True)
        return 1
    config = load_active_config(config_path)

    from butler_main.chat import engine as chat_engine

    channels = _parse_channels(args.channels)
    service = ChatCoreService(
        run_agent_fn=chat_engine.run_agent,
        after_reply_fn=chat_engine._after_reply_persist_memory_async,
        config_path=config_path,
        channels=channels,
        weixin_state_dir=str(args.weixin_state_dir or "").strip(),
        weixin_official_bridge_base_url=str(args.weixin_official_bridge_base_url or "").strip(),
        weixin_official_cdn_base_url=str(args.weixin_official_cdn_base_url or "").strip(),
        weixin_bindings=_resolve_weixin_bindings(
            config=config,
            default_state_dir=str(args.weixin_state_dir or "").strip(),
            default_bridge_base_url=str(args.weixin_official_bridge_base_url or "").strip(),
            default_cdn_base_url=str(args.weixin_official_cdn_base_url or "").strip(),
        ),
    )
    service.start_background_services()

    if "feishu" in channels:
        _start_listener_thread(
            service,
            "feishu",
            lambda: _run_feishu_core_listener(config, chat_engine),
            name="butler-feishu-listener",
        )

    if "weixin" in channels:
        for binding in service.weixin_bindings:
            _start_listener_thread(
                service,
                "weixin",
                lambda binding=binding: _run_weixin_core_listener(binding, chat_engine),
                name=f"butler-weixin-listener-{binding.binding_id}",
                report_channel_failure=False,
            )

    server = create_chat_core_http_server(
        service,
        host=str(args.host or DEFAULT_CORE_HOST).strip() or DEFAULT_CORE_HOST,
        port=int(args.port or DEFAULT_CORE_PORT),
    )
    service.mark_started("cli", thread_name=threading.current_thread().name)
    print(
        f"[chat-core] listening on http://{str(args.host or DEFAULT_CORE_HOST).strip() or DEFAULT_CORE_HOST}:{int(args.port or DEFAULT_CORE_PORT)}",
        flush=True,
    )
    print(f"[chat-core] channels={','.join(channels or DEFAULT_CORE_CHANNELS)}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    finally:
        with contextlib.suppress(Exception):
            server.shutdown()
        with contextlib.suppress(Exception):
            server.server_close()


__all__ = [
    "ChatCoreService",
    "DEFAULT_CORE_HOST",
    "DEFAULT_CORE_PORT",
    "create_chat_core_http_server",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
