from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener, urlopen

import qrcode
from Crypto.Cipher import AES

from ..pathing import resolve_butler_root
from .dispatcher import WeixinConversationDispatcher, WeixinDispatchResult
from .official import DEFAULT_BRIDGE_BASE_URL
from .bridge import process_weixin_webhook_event
from .input import WeixinInputAdapter
from .session_registry import WeixinSessionRegistry
from .status import set_weixin_runtime_status


DEFAULT_LOGIN_TIMEOUT_MS = 8 * 60_000
DEFAULT_POLL_TIMEOUT_MS = 35_000
DEFAULT_HTTP_TIMEOUT_GRACE_MS = 5_000
DEFAULT_DISPATCHER_WORKERS = 4
DEFAULT_LOGIN_RETRY_BACKOFF_MS = 1_000
DEFAULT_LOGIN_QR_PAGE_AUTO_REFRESH_SECONDS = 15
DEFAULT_STATE_FILE_NAME = "weixin.json"
LEGACY_STATE_FILE_NAME = "openclaw.json"
DEFAULT_SESSION_FILE_NAME = "weixin_session.json"
DEFAULT_LOGIN_QR_PAGE_NAME = "weixin_login_qr.html"
_CHANNEL_CONFIG_KEYS = ("weixin", "wechat", "openclaw-weixin")
_NO_PROXY_OPENER = build_opener(ProxyHandler({}))
_WEIXIN_INPUT_ADAPTER = WeixinInputAdapter()
_AES_BLOCK_SIZE = 16
_UPLOAD_MEDIA_TYPE_IMAGE = 1
_UPLOAD_MEDIA_TYPE_VIDEO = 2
_UPLOAD_MEDIA_TYPE_FILE = 3


@dataclass(slots=True, frozen=True)
class WeixinBridgeConfig:
    bridge_base_url: str
    cdn_base_url: str
    state_dir: str = ""
    state_file: str = ""
    session_file: str = ""


@dataclass(slots=True, frozen=True)
class WeixinLoginTicket:
    qrcode: str
    qrcode_url: str
    qrcode_page_url: str = ""


@dataclass(slots=True)
class WeixinBridgeSession:
    bridge_base_url: str
    cdn_base_url: str
    bot_token: str
    account_id: str
    user_id: str = ""
    cursor: str = ""
    longpoll_timeout_ms: int = DEFAULT_POLL_TIMEOUT_MS

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
        *,
        bridge_base_url: str,
        cdn_base_url: str,
    ) -> WeixinBridgeSession:
        return cls(
            bridge_base_url=_normalize_base_url(str(payload.get("baseurl") or bridge_base_url)),
            cdn_base_url=_normalize_base_url(cdn_base_url or payload.get("baseurl") or bridge_base_url),
            bot_token=str(payload.get("bot_token") or "").strip(),
            account_id=str(payload.get("ilink_bot_id") or "").strip(),
            user_id=str(payload.get("ilink_user_id") or "").strip(),
        )

    @classmethod
    def load(cls, path: str | Path) -> WeixinBridgeSession | None:
        target = Path(path)
        if not target.is_file():
            return None
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        try:
            return cls(
                bridge_base_url=_normalize_base_url(str(payload.get("bridge_base_url") or "")),
                cdn_base_url=_normalize_base_url(str(payload.get("cdn_base_url") or payload.get("bridge_base_url") or "")),
                bot_token=str(payload.get("bot_token") or "").strip(),
                account_id=str(payload.get("account_id") or "").strip(),
                user_id=str(payload.get("user_id") or "").strip(),
                cursor=str(payload.get("cursor") or "").strip(),
                longpoll_timeout_ms=max(int(payload.get("longpoll_timeout_ms") or DEFAULT_POLL_TIMEOUT_MS), 1),
            )
        except (TypeError, ValueError):
            return None

    def is_ready(self) -> bool:
        return bool(self.bridge_base_url and self.bot_token and self.account_id)

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return target


@dataclass(slots=True, frozen=True)
class WeixinPollResult:
    cursor: str
    received_count: int
    delivered_count: int


def resolve_weixin_bridge_config(
    *,
    bridge_base_url: str = "",
    cdn_base_url: str = "",
    state_dir: str = "",
    session_file: str = "",
) -> WeixinBridgeConfig:
    resolved_state_dir = str(
        state_dir
        or os.environ.get("WEIXIN_STATE_DIR")
        or os.environ.get("BUTLER_WEIXIN_STATE_DIR")
        or os.environ.get("OPENCLAW_STATE_DIR")
        or ""
    ).strip()
    state_file = ""
    state_payload: dict[str, Any] = {}
    if resolved_state_dir:
        candidate = _resolve_state_file(Path(resolved_state_dir))
        state_file = str(candidate) if candidate is not None else str(Path(resolved_state_dir) / DEFAULT_STATE_FILE_NAME)
        try:
            if candidate is not None and candidate.is_file():
                loaded = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    state_payload = loaded
        except (OSError, json.JSONDecodeError):
            state_payload = {}
    channel_config = _resolve_channel_config(state_payload)
    resolved_base_url = _normalize_base_url(
        bridge_base_url or str(channel_config.get("baseUrl") or "") or DEFAULT_BRIDGE_BASE_URL
    )
    resolved_cdn_url = _normalize_base_url(
        cdn_base_url or str(channel_config.get("cdnBaseUrl") or "") or resolved_base_url
    )
    resolved_session_file = str(session_file or "").strip()
    if not resolved_session_file and resolved_state_dir:
        resolved_session_file = str(Path(resolved_state_dir) / DEFAULT_SESSION_FILE_NAME)
    return WeixinBridgeConfig(
        bridge_base_url=resolved_base_url,
        cdn_base_url=resolved_cdn_url,
        state_dir=resolved_state_dir,
        state_file=state_file,
        session_file=resolved_session_file,
    )


def start_weixin_bridge_login(
    config: WeixinBridgeConfig,
    *,
    bot_type: str = "3",
    timeout_ms: int = 5_000,
) -> WeixinLoginTicket:
    request_url = (
        f"{config.bridge_base_url}ilink/bot/get_bot_qrcode?bot_type={quote(str(bot_type or '3').strip())}"
    )
    payload = _read_json(request_url, timeout_ms=timeout_ms)
    return WeixinLoginTicket(
        qrcode=str(payload.get("qrcode") or "").strip(),
        qrcode_url=str(payload.get("qrcode_img_content") or "").strip(),
        qrcode_page_url=_resolve_login_qr_page_url(
            bridge_base_url=config.bridge_base_url,
            qrcode=str(payload.get("qrcode") or "").strip(),
            qrcode_url=str(payload.get("qrcode_img_content") or "").strip(),
            qrcode_page_url=str(payload.get("qrcode_page_url") or "").strip(),
        ),
    )


def wait_for_weixin_bridge_login(
    config: WeixinBridgeConfig,
    *,
    ticket: WeixinLoginTicket,
    timeout_ms: int = DEFAULT_LOGIN_TIMEOUT_MS,
    poll_interval_ms: int = 1_000,
) -> WeixinBridgeSession:
    qrcode = str(ticket.qrcode or "").strip()
    if not qrcode:
        raise ValueError("missing qrcode for weixin bridge login")
    deadline = time.monotonic() + (max(int(timeout_ms), 1) / 1000.0)
    while time.monotonic() < deadline:
        request_url = f"{config.bridge_base_url}ilink/bot/get_qrcode_status?qrcode={quote(qrcode)}"
        try:
            payload = _read_json(
                request_url,
                timeout_ms=max(DEFAULT_POLL_TIMEOUT_MS + 5_000, poll_interval_ms, 1_000),
            )
        except TimeoutError:
            payload = {"status": "wait"}
        status = str(payload.get("status") or "").strip().lower()
        if status == "confirmed":
            session = WeixinBridgeSession.from_payload(
                payload,
                bridge_base_url=config.bridge_base_url,
                cdn_base_url=config.cdn_base_url,
            )
            if not session.is_ready():
                raise RuntimeError("weixin bridge login confirmed without usable session payload")
            return session
        if status == "expired":
            raise RuntimeError("weixin bridge login expired")
        time.sleep(max(int(poll_interval_ms), 100) / 1000.0)
    raise TimeoutError(f"weixin bridge login timed out after {int(timeout_ms)} ms")


def poll_weixin_bridge_once(
    session: WeixinBridgeSession,
    *,
    run_agent_fn,
    timeout_ms: int | None = None,
    dispatcher: WeixinConversationDispatcher | None = None,
    session_registry: WeixinSessionRegistry | None = None,
    on_reply_sent: Callable[[str, str], None] | None = None,
) -> WeixinPollResult:
    body = {"get_updates_buf": str(session.cursor or "")}
    payload = _post_json(
        f"{session.bridge_base_url}ilink/bot/getupdates",
        body,
        token=session.bot_token,
        timeout_ms=max(int(timeout_ms or session.longpoll_timeout_ms or DEFAULT_POLL_TIMEOUT_MS), 1)
        + DEFAULT_HTTP_TIMEOUT_GRACE_MS,
    )
    session.longpoll_timeout_ms = max(int(payload.get("longpolling_timeout_ms") or session.longpoll_timeout_ms), 1)
    next_cursor = str(payload.get("get_updates_buf") or session.cursor or "").strip()
    delivered = 0
    messages = [item for item in (payload.get("msgs") if isinstance(payload.get("msgs"), list) else []) if isinstance(item, dict)]
    prepared_messages = [_prepare_inbound_message(session, message) for message in messages]
    for prepared in prepared_messages:
        _record_inbound_session(session_registry, prepared)
    if dispatcher is None:
        for prepared in prepared_messages:
            delivered += _process_inbound_message(
                session,
                prepared,
                run_agent_fn=run_agent_fn,
                on_reply_sent=on_reply_sent,
            ).delivered_count
    else:
        futures = [
            dispatcher.submit(
                prepared["conversation_key"],
                prepared["message_id"],
                lambda prepared=prepared: _process_inbound_message(
                    session,
                    prepared,
                    run_agent_fn=run_agent_fn,
                    on_reply_sent=on_reply_sent,
                ),
            )
            for prepared in prepared_messages
        ]
        for future in futures:
            delivered += future.result().delivered_count
    session.cursor = next_cursor
    return WeixinPollResult(
        cursor=next_cursor,
        received_count=len(messages),
        delivered_count=delivered,
    )


def run_weixin_bridge_client(
    *,
    run_agent_fn,
    binding_id: str = "",
    bridge_base_url: str = "",
    cdn_base_url: str = "",
    state_dir: str = "",
    session_file: str = "",
    login_timeout_ms: int = DEFAULT_LOGIN_TIMEOUT_MS,
    reuse_session: bool = True,
    on_reply_sent: Callable[[str, str], None] | None = None,
) -> int:
    config = resolve_weixin_bridge_config(
        bridge_base_url=bridge_base_url,
        cdn_base_url=cdn_base_url,
        state_dir=state_dir,
        session_file=session_file,
    )
    session_registry = WeixinSessionRegistry()
    dispatcher = WeixinConversationDispatcher(
        registry=session_registry,
        max_workers=DEFAULT_DISPATCHER_WORKERS,
    )
    resolved_binding_id = str(binding_id or "").strip()
    session = None
    _publish_weixin_runtime_status(
        binding_id=resolved_binding_id,
        session=session,
        session_registry=session_registry,
        connected=False,
        login_state="starting",
    )
    session = _ensure_logged_in_bridge_session(
        config,
        login_timeout_ms=login_timeout_ms,
        reuse_session=reuse_session,
        session_registry=session_registry,
        publish_status_fn=lambda **kwargs: _publish_weixin_runtime_status(binding_id=resolved_binding_id, **kwargs),
    )
    _publish_weixin_runtime_status(
        binding_id=resolved_binding_id,
        session=session,
        session_registry=session_registry,
        connected=True,
        login_state="ready",
    )
    try:
        while True:
            result = poll_weixin_bridge_once(
                session,
                run_agent_fn=run_agent_fn,
                dispatcher=dispatcher,
                session_registry=session_registry,
                on_reply_sent=on_reply_sent,
            )
            if config.session_file:
                session.save(config.session_file)
            _publish_weixin_runtime_status(
                binding_id=resolved_binding_id,
                session=session,
                session_registry=session_registry,
                connected=True,
                login_state="ready",
                last_received_count=result.received_count,
                last_delivered_count=result.delivered_count,
            )
            if result.received_count > 0:
                print(
                    f"[weixin-client] received={result.received_count} delivered={result.delivered_count} cursor={result.cursor or '(empty)'}",
                    flush=True,
                )
    except KeyboardInterrupt:
        if config.session_file:
            session.save(config.session_file)
        _publish_weixin_runtime_status(
            binding_id=resolved_binding_id,
            session=session,
            session_registry=session_registry,
            connected=False,
            login_state="stopped",
        )
        return 130
    except Exception as exc:
        _publish_weixin_runtime_status(
            binding_id=resolved_binding_id,
            session=session,
            session_registry=session_registry,
            connected=False,
            login_state="error",
            last_error=f"{type(exc).__name__}: {exc}",
        )
        raise
    finally:
        dispatcher.shutdown(wait=False)


def _ensure_logged_in_bridge_session(
    config: WeixinBridgeConfig,
    *,
    login_timeout_ms: int,
    reuse_session: bool,
    session_registry: WeixinSessionRegistry | None,
    publish_status_fn: Callable[..., None],
) -> WeixinBridgeSession:
    session = None
    if reuse_session and config.session_file:
        session = WeixinBridgeSession.load(config.session_file)
        if session is not None and not session.is_ready():
            session = None
    if session is not None:
        return session

    deadline = time.monotonic() + (max(int(login_timeout_ms or DEFAULT_LOGIN_TIMEOUT_MS), 1) / 1000.0)
    last_error = ""
    while True:
        remaining_ms = max(int((deadline - time.monotonic()) * 1000), 0)
        if remaining_ms <= 0:
            if last_error:
                raise TimeoutError(f"weixin bridge login timed out after {int(login_timeout_ms)} ms ({last_error})")
            raise TimeoutError(f"weixin bridge login timed out after {int(login_timeout_ms)} ms")

        ticket = start_weixin_bridge_login(config)
        if not ticket.qrcode_url:
            raise RuntimeError("weixin bridge did not return a login link")
        local_qr_page = _write_local_login_qr_page(config=config, ticket=ticket)
        publish_status_fn(
            session=None,
            session_registry=session_registry,
            connected=False,
            login_state="waiting_login",
        )
        if local_qr_page:
            print(f"[weixin-client] local qr page: {local_qr_page}", flush=True)
        if ticket.qrcode_page_url:
            print(f"[weixin-client] qr page: {ticket.qrcode_page_url}", flush=True)
        print(f"[weixin-client] login link: {ticket.qrcode_url}", flush=True)
        try:
            session = wait_for_weixin_bridge_login(
                config,
                ticket=ticket,
                timeout_ms=remaining_ms,
            )
        except RuntimeError as exc:
            if _is_login_expired_error(exc) and time.monotonic() < deadline:
                last_error = str(exc)
                print("[weixin-client] login QR expired; requesting a new QR code...", flush=True)
                time.sleep(DEFAULT_LOGIN_RETRY_BACKOFF_MS / 1000.0)
                continue
            raise
        if config.session_file:
            session.save(config.session_file)
            print(f"[weixin-client] session saved: {config.session_file}", flush=True)
        print(
            f"[weixin-client] connected account={session.account_id} user={session.user_id or '(unknown)'}",
            flush=True,
        )
        return session


def _is_login_expired_error(exc: Exception) -> bool:
    message = str(exc or "").strip().lower()
    return "login expired" in message or message.endswith("expired")


def _resolve_channel_config(state_payload: dict[str, Any]) -> dict[str, Any]:
    channels = state_payload.get("channels") if isinstance(state_payload.get("channels"), dict) else {}
    for key in _CHANNEL_CONFIG_KEYS:
        entry = channels.get(key)
        if isinstance(entry, dict):
            return entry
    return {}


def _resolve_state_file(state_dir: Path) -> Path | None:
    preferred = state_dir / DEFAULT_STATE_FILE_NAME
    legacy = state_dir / LEGACY_STATE_FILE_NAME
    if preferred.is_file():
        return preferred
    if legacy.is_file():
        return legacy
    return preferred


def _normalize_base_url(raw: str) -> str:
    value = str(raw or "").strip() or DEFAULT_BRIDGE_BASE_URL
    return value.rstrip("/") + "/"


def _prepare_inbound_message(session: WeixinBridgeSession, message: dict[str, Any]) -> dict[str, Any]:
    event_payload = dict(message or {})
    if session.account_id and not str(event_payload.get("account_id") or "").strip():
        event_payload["account_id"] = session.account_id
    normalized = _WEIXIN_INPUT_ADAPTER.normalize_event(event_payload)
    metadata = dict(normalized.get("metadata") or {})
    return {
        "event": event_payload,
        "normalized": normalized,
        "conversation_key": str(metadata.get("weixin.conversation_key") or normalized.get("session_id") or "").strip(),
        "message_id": str(metadata.get("weixin.message_id") or normalized.get("source_event_id") or "").strip(),
        "user_text": str(normalized.get("user_text") or "").strip(),
    }


def _record_inbound_session(
    session_registry: WeixinSessionRegistry | None,
    prepared: dict[str, Any],
) -> None:
    if session_registry is None:
        return
    normalized = prepared.get("normalized") if isinstance(prepared.get("normalized"), dict) else {}
    metadata = dict(normalized.get("metadata") or {})
    session_registry.record_inbound(
        conversation_key=str(prepared.get("conversation_key") or "").strip(),
        account_id=str(metadata.get("weixin.account_id") or "").strip(),
        actor_id=str(normalized.get("actor_id") or "").strip(),
        receive_id=str(metadata.get("weixin.receive_id") or "").strip(),
        receive_id_type=str(metadata.get("weixin.receive_id_type") or "open_id").strip() or "open_id",
        chat_type=str(metadata.get("weixin.chat_type") or "dm").strip() or "dm",
        raw_session_ref=str(metadata.get("weixin.raw_session_ref") or "").strip(),
        session_id=str(normalized.get("session_id") or "").strip(),
        message_id=str(prepared.get("message_id") or "").strip(),
        metadata=metadata,
    )


def _process_inbound_message(
    session: WeixinBridgeSession,
    prepared: dict[str, Any],
    *,
    run_agent_fn,
    on_reply_sent: Callable[[str, str], None] | None = None,
) -> WeixinDispatchResult:
    event_payload = prepared.get("event") if isinstance(prepared.get("event"), dict) else {}
    normalized = prepared.get("normalized") if isinstance(prepared.get("normalized"), dict) else {}
    conversation_key = str(prepared.get("conversation_key") or "").strip()
    message_id = str(prepared.get("message_id") or "").strip()
    print(
        f"[weixin-client] dispatch conversation={conversation_key or '(unknown)'} message_id={message_id or '(unknown)'}",
        flush=True,
    )
    result = process_weixin_webhook_event(event_payload, run_agent_fn=run_agent_fn)
    protocol_payload = result.get("weixin_protocol") if isinstance(result.get("weixin_protocol"), dict) else {}
    request_list = protocol_payload.get("sendmessage_requests")
    if not isinstance(request_list, list):
        legacy_payload = result.get("openclaw_official") if isinstance(result.get("openclaw_official"), dict) else {}
        request_list = legacy_payload.get("sendmessage_requests")
    if not isinstance(request_list, list):
        request_list = []
    delivered_count = 0
    for request in request_list:
        if not isinstance(request, dict):
            continue
        outbound_request = _prepare_outbound_sendmessage_request(session, request)
        _post_json(
            f"{session.bridge_base_url}ilink/bot/sendmessage",
            outbound_request,
            token=session.bot_token,
            timeout_ms=10_000,
        )
        delivered_count += 1
    reply_text = str(result.get("reply") or "").strip()
    if callable(on_reply_sent) and reply_text:
        on_reply_sent(str(prepared.get("user_text") or normalized.get("user_text") or "").strip(), reply_text)
    return WeixinDispatchResult(
        conversation_key=conversation_key,
        message_id=message_id,
        delivered_count=delivered_count,
        metadata={"reply": reply_text},
    )


def _publish_weixin_runtime_status(
    *,
    binding_id: str = "",
    session: WeixinBridgeSession | None,
    session_registry: WeixinSessionRegistry | None,
    connected: bool,
    login_state: str,
    last_received_count: int = 0,
    last_delivered_count: int = 0,
    last_error: str = "",
) -> None:
    registry_snapshot = session_registry.snapshot() if session_registry is not None else {}
    set_weixin_runtime_status(
        {
            "connected": bool(connected),
            "login_state": str(login_state or "idle").strip() or "idle",
            "account_id": str(session.account_id if session is not None else "").strip(),
            "user_id": str(session.user_id if session is not None else "").strip(),
            "cursor": str(session.cursor if session is not None else "").strip(),
            "longpoll_timeout_ms": int(session.longpoll_timeout_ms if session is not None else DEFAULT_POLL_TIMEOUT_MS),
            "last_poll_at": time.time(),
            "last_received_count": max(int(last_received_count or 0), 0),
            "last_delivered_count": max(int(last_delivered_count or 0), 0),
            "active_conversation_count": int(registry_snapshot.get("active_conversation_count") or 0),
            "running_conversation_count": int(registry_snapshot.get("running_conversation_count") or 0),
            "recent_conversations": list(registry_snapshot.get("recent_conversations") or []),
            "last_error": str(last_error or "").strip(),
        },
        binding_id=binding_id,
    )


def _auth_headers(token: str = "") -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json; charset=utf-8"}
    if str(token or "").strip():
        headers["AuthorizationType"] = "ilink_bot_token"
        headers["Authorization"] = f"Bearer {str(token).strip()}"
    return headers


def _resolve_login_qr_page_url(
    *,
    bridge_base_url: str,
    qrcode: str,
    qrcode_url: str,
    qrcode_page_url: str,
) -> str:
    explicit_page_url = str(qrcode_page_url or "").strip()
    if explicit_page_url:
        return explicit_page_url
    normalized_qrcode = str(qrcode or "").strip()
    normalized_qrcode_url = str(qrcode_url or "").strip()
    normalized_base_url = _normalize_base_url(bridge_base_url)
    if (
        normalized_qrcode
        and normalized_qrcode_url
        and normalized_qrcode_url.startswith(normalized_base_url)
        and "/weixin/bridge/login/confirm" in normalized_qrcode_url
    ):
        return f"{normalized_base_url}weixin/bridge/login/qr?qrcode={quote(normalized_qrcode)}"
    return normalized_qrcode_url


def _write_local_login_qr_page(*, config: WeixinBridgeConfig, ticket: WeixinLoginTicket) -> str:
    login_link = str(ticket.qrcode_url or "").strip()
    if not login_link:
        return ""
    output_dir = Path(config.state_dir) if str(config.state_dir or "").strip() else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / DEFAULT_LOGIN_QR_PAGE_NAME
    image_data = base64.b64encode(_render_qr_png(login_link)).decode("ascii")
    title = "Butler Weixin Login QR"
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    target.write_text(
        _render_local_login_qr_page(
            title=title,
            qrcode=str(ticket.qrcode or "").strip(),
            login_link=login_link,
            image_data=image_data,
            bridge_base_url=config.bridge_base_url,
            generated_at=generated_at,
            auto_refresh_seconds=DEFAULT_LOGIN_QR_PAGE_AUTO_REFRESH_SECONDS,
        ),
        encoding="utf-8",
    )
    return str(target)


def _render_local_login_qr_page(
    *,
    title: str,
    qrcode: str,
    login_link: str,
    image_data: str,
    bridge_base_url: str,
    generated_at: str,
    auto_refresh_seconds: int,
) -> str:
    escaped_title = escape(title)
    escaped_qrcode = escape(qrcode)
    escaped_login_link = escape(login_link)
    escaped_bridge_base_url = escape(bridge_base_url)
    escaped_generated_at = escape(generated_at)
    refresh_seconds = max(int(auto_refresh_seconds or 0), 5)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escaped_title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --ink: #132238;
      --muted: #5f728c;
      --line: #d8e0eb;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: radial-gradient(circle at top, #ffffff 0%, var(--bg) 60%);
      color: var(--ink);
    }}
    main {{
      max-width: 920px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: 0 16px 40px rgba(19, 34, 56, 0.08);
      padding: 28px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(280px, 360px) 1fr;
      gap: 28px;
      align-items: start;
    }}
    .qr-box {{
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 18px;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 320px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 28px;
      line-height: 1.2;
    }}
    p {{
      margin: 0 0 12px;
      line-height: 1.6;
    }}
    .muted {{
      color: var(--muted);
    }}
    .mono {{
      font-family: Consolas, "Courier New", monospace;
      word-break: break-all;
      background: #f7f9fc;
      border-radius: 12px;
      padding: 10px 12px;
      border: 1px solid var(--line);
    }}
    .status-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin: 16px 0;
      color: var(--muted);
    }}
    .status-chip {{
      background: #eef5ff;
      border: 1px solid #c9defe;
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 14px;
    }}
    button {{
      appearance: none;
      border: 0;
      border-radius: 12px;
      padding: 12px 16px;
      background: #132238;
      color: #fff;
      font: inherit;
      cursor: pointer;
    }}
    button:hover {{
      background: #1f3552;
    }}
    @media (max-width: 760px) {{
      .grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
  <script>
    const autoRefreshSeconds = {refresh_seconds};

    function refreshNow() {{
      const nextUrl = new URL(window.location.href);
      nextUrl.searchParams.set("_ts", Date.now().toString());
      window.location.replace(nextUrl.toString());
    }}

    function startRefreshLoop() {{
      const countdownNode = document.getElementById("countdown");
      let remaining = autoRefreshSeconds;
      const tick = () => {{
        if (countdownNode) {{
          countdownNode.textContent = remaining + "s";
        }}
        if (remaining <= 0) {{
          refreshNow();
          return;
        }}
        remaining -= 1;
        window.setTimeout(tick, 1000);
      }};
      tick();
    }}

    window.addEventListener("DOMContentLoaded", startRefreshLoop);
  </script>
</head>
<body>
  <main>
    <div class="panel">
      <div class="grid">
        <div>
          <div class="qr-box"><img src="data:image/png;base64,{image_data}" alt="{escaped_title}" style="width:320px;height:320px;" /></div>
        </div>
        <div>
          <h1>Butler 微信登录二维码</h1>
          <p>在电脑上打开这个页面，然后用手机微信扫一扫左侧二维码。</p>
          <p class="muted">这张二维码编码的是微信官方登录链接，不依赖本地 mock bridge。二维码过期后，后台会自动申请新票，这个页面也会自动刷新。</p>
          <div class="status-row">
            <div class="status-chip">生成时间：<span id="generatedAt">{escaped_generated_at}</span></div>
            <div class="status-chip">自动刷新倒计时：<span id="countdown">{refresh_seconds}s</span></div>
          </div>
          <p><button type="button" onclick="refreshNow()">立即刷新二维码</button></p>
          <p><strong>登录 token</strong></p>
          <div class="mono">{escaped_qrcode}</div>
          <p style="margin-top:14px;"><strong>扫码目标链接</strong></p>
          <div class="mono">{escaped_login_link}</div>
          <p class="muted" style="margin-top:14px;">当前配置基址：{escaped_bridge_base_url}</p>
        </div>
      </div>
    </div>
  </main>
</body>
</html>"""


def _render_qr_png(text: str) -> bytes:
    image = qrcode.make(text)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _read_json(url: str, *, timeout_ms: int) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    with _NO_PROXY_OPENER.open(request, timeout=max(int(timeout_ms), 1) / 1000.0) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object from {url}")
    return payload


def _post_json(url: str, payload: dict[str, Any], *, token: str = "", timeout_ms: int) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=_auth_headers(token),
        method="POST",
    )
    with _NO_PROXY_OPENER.open(request, timeout=max(int(timeout_ms), 1) / 1000.0) as response:
        raw = response.read().decode("utf-8") or "{}"
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise TypeError(f"expected JSON object from {url}")
    return parsed


def _prepare_outbound_sendmessage_request(
    session: WeixinBridgeSession,
    request: dict[str, Any],
) -> dict[str, Any]:
    body = dict(request or {})
    message = body.get("msg") if isinstance(body.get("msg"), dict) else {}
    normalized_message = dict(message or {})
    item_list = normalized_message.get("item_list") if isinstance(normalized_message.get("item_list"), list) else []
    if not item_list:
        return body
    normalized_message["item_list"] = [
        _prepare_outbound_item(session, normalized_message, item)
        for item in item_list
        if isinstance(item, dict)
    ]
    body["msg"] = normalized_message
    return body


def _prepare_outbound_item(
    session: WeixinBridgeSession,
    message: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(item or {})
    item_type = int(normalized.get("type") or 0)
    if item_type == 2:
        image_item = normalized.get("image_item") if isinstance(normalized.get("image_item"), dict) else {}
        local_path = str(image_item.get("local_path") or "").strip()
        if local_path:
            return _build_uploaded_media_item(
                session=session,
                to_user_id=str(message.get("to_user_id") or "").strip(),
                item_type=item_type,
                local_path=local_path,
                file_name=Path(local_path).name,
            )
    if item_type == 5:
        video_item = normalized.get("video_item") if isinstance(normalized.get("video_item"), dict) else {}
        local_path = str(video_item.get("local_path") or "").strip()
        if local_path:
            return _build_uploaded_media_item(
                session=session,
                to_user_id=str(message.get("to_user_id") or "").strip(),
                item_type=item_type,
                local_path=local_path,
                file_name=Path(local_path).name,
            )
    if item_type == 4:
        file_item = normalized.get("file_item") if isinstance(normalized.get("file_item"), dict) else {}
        local_path = str(file_item.get("local_path") or "").strip()
        if local_path:
            return _build_uploaded_media_item(
                session=session,
                to_user_id=str(message.get("to_user_id") or "").strip(),
                item_type=item_type,
                local_path=local_path,
                file_name=str(file_item.get("file_name") or Path(local_path).name).strip() or Path(local_path).name,
            )
    return normalized


def _resolve_outbound_media_path(local_path: str) -> Path:
    candidate = Path(str(local_path or "").strip())
    if not str(candidate):
        return candidate
    try:
        if candidate.is_absolute():
            return candidate.resolve()
    except OSError:
        return candidate
    try:
        resolved = candidate.resolve()
    except OSError:
        resolved = candidate
    if resolved.is_file():
        return resolved
    roots = (
        resolve_butler_root(os.getcwd()),
        resolve_butler_root(__file__),
    )
    seen: set[str] = set()
    for root in roots:
        key = os.path.normcase(str(root))
        if key in seen:
            continue
        seen.add(key)
        try:
            joined = (root / candidate).resolve()
        except OSError:
            joined = root / candidate
        if joined.is_file():
            return joined
    return resolved


def _build_uploaded_media_item(
    *,
    session: WeixinBridgeSession,
    to_user_id: str,
    item_type: int,
    local_path: str,
    file_name: str,
) -> dict[str, Any]:
    target_path = _resolve_outbound_media_path(local_path)
    if not target_path.is_file():
        raise FileNotFoundError(f"weixin outbound media not found: {local_path} -> {target_path}")
    plaintext = target_path.read_bytes()
    rawsize = len(plaintext)
    aeskey = os.urandom(_AES_BLOCK_SIZE)
    ciphertext = _encrypt_aes_ecb(plaintext, aeskey)
    filekey = os.urandom(_AES_BLOCK_SIZE).hex()
    upload_payload = {
        "filekey": filekey,
        "media_type": _resolve_upload_media_type(item_type),
        "to_user_id": str(to_user_id or "").strip(),
        "rawsize": rawsize,
        "rawfilemd5": hashlib.md5(plaintext).hexdigest(),
        "filesize": len(ciphertext),
        "no_need_thumb": True,
        "aeskey": aeskey.hex(),
    }
    upload_ticket = _post_json(
        f"{session.bridge_base_url}ilink/bot/getuploadurl",
        upload_payload,
        token=session.bot_token,
        timeout_ms=10_000,
    )
    upload_param = str(upload_ticket.get("upload_param") or "").strip()
    if not upload_param:
        raise RuntimeError(f"weixin getuploadurl returned no upload_param: {upload_ticket}")
    download_param = _upload_ciphertext_to_cdn(
        ciphertext=ciphertext,
        upload_param=upload_param,
        filekey=filekey,
        cdn_base_url=session.cdn_base_url,
        timeout_ms=10_000,
    )
    media_ref = {
        "encrypt_query_param": download_param,
        "aes_key": base64.b64encode(aeskey).decode("ascii"),
        "encrypt_type": 1,
    }
    if item_type == 2:
        return {"type": 2, "image_item": {"media": media_ref, "mid_size": len(ciphertext)}}
    if item_type == 5:
        return {"type": 5, "video_item": {"media": media_ref, "video_size": len(ciphertext)}}
    return {
        "type": 4,
        "file_item": {
            "media": media_ref,
            "file_name": str(file_name or target_path.name).strip() or target_path.name,
            "len": str(rawsize),
        },
    }


def _resolve_upload_media_type(item_type: int) -> int:
    if int(item_type) == 2:
        return _UPLOAD_MEDIA_TYPE_IMAGE
    if int(item_type) == 5:
        return _UPLOAD_MEDIA_TYPE_VIDEO
    return _UPLOAD_MEDIA_TYPE_FILE


def _encrypt_aes_ecb(plaintext: bytes, key: bytes) -> bytes:
    pad_size = _AES_BLOCK_SIZE - (len(plaintext) % _AES_BLOCK_SIZE)
    if pad_size <= 0:
        pad_size = _AES_BLOCK_SIZE
    padded = bytes(plaintext) + bytes([pad_size]) * pad_size
    cipher = AES.new(bytes(key), AES.MODE_ECB)
    return cipher.encrypt(padded)


def _upload_ciphertext_to_cdn(
    *,
    ciphertext: bytes,
    upload_param: str,
    filekey: str,
    cdn_base_url: str,
    timeout_ms: int,
) -> str:
    upload_url = (
        f"{str(cdn_base_url or '').rstrip('/')}/upload"
        f"?encrypted_query_param={quote(str(upload_param or '').strip())}"
        f"&filekey={quote(str(filekey or '').strip())}"
    )
    request = Request(
        upload_url,
        data=bytes(ciphertext or b""),
        headers={"Content-Type": "application/octet-stream"},
        method="POST",
    )
    with _NO_PROXY_OPENER.open(request, timeout=max(int(timeout_ms), 1) / 1000.0) as response:
        download_param = str(response.headers.get("x-encrypted-param") or "").strip()
    if not download_param:
        raise RuntimeError("weixin CDN upload response missing x-encrypted-param")
    return download_param


__all__ = [
    "DEFAULT_LOGIN_TIMEOUT_MS",
    "DEFAULT_STATE_FILE_NAME",
    "WeixinBridgeConfig",
    "WeixinBridgeSession",
    "WeixinLoginTicket",
    "WeixinPollResult",
    "poll_weixin_bridge_once",
    "resolve_weixin_bridge_config",
    "run_weixin_bridge_client",
    "start_weixin_bridge_login",
    "wait_for_weixin_bridge_login",
]
