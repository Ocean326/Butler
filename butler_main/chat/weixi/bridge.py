from __future__ import annotations

import base64
import io
import json
import time
from html import escape
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Condition
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import qrcode
from agents_os.contracts import DeliverySession, OutputBundle, TextBlock

from .delivery import WeixinDeliveryAdapter, WeixinDeliveryPlan
from .input import WeixinInputAdapter
from .official import (
    DEFAULT_LONGPOLL_TIMEOUT_MS,
    build_getconfig_response,
    build_getupdates_response,
    build_sendmessage_response,
    build_sendtyping_response,
)


WEIXIN_MESSAGE_TYPE_USER = 1
WEIXIN_MESSAGE_TYPE_BOT = 2
WEIXIN_MESSAGE_STATE_NEW = 0
WEIXIN_TYPING_STATUS_TYPING = 1
WEIXIN_TYPING_STATUS_CANCEL = 2
LOGIN_TICKET_TTL_MS = 30 * 60_000
_WEIXIN_INPUT_ADAPTER = WeixinInputAdapter()


def build_bridge_url(*, host: str = "127.0.0.1", port: int = 8789, path: str = "/weixin/webhook") -> str:
    normalized_path = "/" + str(path or "/weixin/webhook").strip().lstrip("/")
    return f"http://{host}:{int(port)}{normalized_path}"


@dataclass(slots=True, frozen=True)
class QueuedWeixinMessage:
    seq: int
    payload: dict[str, Any]
    event: dict[str, Any]


@dataclass(slots=True, frozen=True)
class RecordedOutboundMessage:
    request_body: dict[str, Any]
    recorded_at_ms: int


@dataclass(slots=True, frozen=True)
class RecordedTypingEvent:
    request_body: dict[str, Any]
    recorded_at_ms: int


@dataclass(slots=True)
class LoginTicket:
    qrcode: str
    qrcode_url: str
    base_url: str
    account_id: str
    user_id: str
    created_at_ms: int
    bot_type: str = "3"
    bot_token: str = field(default_factory=lambda: f"bridge-bot-token-{uuid4().hex[:12]}")
    status: str = "wait"
    expires_at_ms: int = 0


@dataclass(slots=True)
class UploadTicket:
    upload_param: str
    filekey: str
    created_at_ms: int


class WeixinOfficialBridgeService:
    """In-memory Weixin bridge backend emulator for local transport bridging."""

    def __init__(self, *, longpoll_timeout_ms: int = DEFAULT_LONGPOLL_TIMEOUT_MS) -> None:
        self.longpoll_timeout_ms = int(longpoll_timeout_ms or DEFAULT_LONGPOLL_TIMEOUT_MS)
        self._condition = Condition()
        self._queued_messages: list[QueuedWeixinMessage] = []
        self._next_seq = 1
        self._outbox: list[RecordedOutboundMessage] = []
        self._typing_events: list[RecordedTypingEvent] = []
        self._uploads: dict[str, bytes] = {}
        self._upload_tickets: dict[str, UploadTicket] = {}
        self._login_tickets: dict[str, LoginTicket] = {}

    def enqueue_webhook_event(self, event: Mapping[str, Any] | None) -> dict[str, Any]:
        raw_event = dict(event or {})
        with self._condition:
            queued = self._to_official_message(raw_event, seq=self._next_seq)
            self._next_seq += 1
            self._queued_messages.append(QueuedWeixinMessage(seq=int(queued["seq"]), payload=queued, event=raw_event))
            self._condition.notify_all()
        return queued

    def get_updates(self, *, cursor: str = "", wait_ms: int | None = None) -> dict[str, Any]:
        cursor_seq = _cursor_to_seq(cursor)
        timeout_ms = self.longpoll_timeout_ms if wait_ms is None else max(int(wait_ms), 0)
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        with self._condition:
            while True:
                messages = [item.payload for item in self._queued_messages if item.seq > cursor_seq]
                if messages:
                    new_cursor = str(max(int(item["seq"]) for item in messages))
                    return build_getupdates_response(
                        messages=messages,
                        cursor=new_cursor,
                        longpolling_timeout_ms=self.longpoll_timeout_ms,
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return build_getupdates_response(
                        messages=[],
                        cursor=str(cursor_seq) if cursor_seq > 0 else "",
                        longpolling_timeout_ms=self.longpoll_timeout_ms,
                    )
                self._condition.wait(timeout=remaining)

    def record_sendmessage(self, body: Mapping[str, Any] | None) -> dict[str, Any]:
        payload = dict(body or {})
        with self._condition:
            self._outbox.append(
                RecordedOutboundMessage(
                    request_body=payload,
                    recorded_at_ms=_now_ms(),
                )
            )
        return build_sendmessage_response()

    def record_typing(self, body: Mapping[str, Any] | None) -> dict[str, Any]:
        payload = dict(body or {})
        with self._condition:
            self._typing_events.append(
                RecordedTypingEvent(
                    request_body=payload,
                    recorded_at_ms=_now_ms(),
                )
            )
        return build_sendtyping_response()

    def get_config(self, *, context_token: str = "") -> dict[str, Any]:
        token_source = str(context_token or f"typing:{uuid4().hex[:12]}")
        typing_ticket = base64.b64encode(token_source.encode("utf-8")).decode("ascii")
        return build_getconfig_response(typing_ticket=typing_ticket)

    def issue_upload_ticket(self, *, filekey: str = "") -> dict[str, Any]:
        upload_param = f"upload-{uuid4().hex[:18]}"
        ticket = UploadTicket(
            upload_param=upload_param,
            filekey=str(filekey or "").strip(),
            created_at_ms=_now_ms(),
        )
        with self._condition:
            self._upload_tickets[upload_param] = ticket
        return {
            "upload_param": upload_param,
            "thumb_upload_param": "",
        }

    def accept_upload(self, *, upload_param: str, ciphertext: bytes) -> str | None:
        download_param = f"download-{uuid4().hex[:18]}"
        with self._condition:
            ticket = self._upload_tickets.get(str(upload_param or "").strip())
            if ticket is None:
                return None
            self._uploads[download_param] = bytes(ciphertext or b"")
        return download_param

    def download_upload(self, *, download_param: str) -> bytes | None:
        with self._condition:
            return self._uploads.get(download_param)

    def start_login(self, *, base_url: str, bot_type: str = "3") -> dict[str, Any]:
        qrcode = f"bridge-login-{uuid4().hex[:12]}"
        qrcode_url = f"{base_url.rstrip('/')}/weixin/bridge/login/confirm?qrcode={qrcode}"
        qrcode_page_url = f"{base_url.rstrip('/')}/weixin/bridge/login/qr?qrcode={qrcode}"
        qrcode_png_url = f"{base_url.rstrip('/')}/weixin/bridge/login/qr.png?qrcode={qrcode}"
        ticket = LoginTicket(
            qrcode=qrcode,
            qrcode_url=qrcode_url,
            base_url=base_url.rstrip("/"),
            account_id="bridge-bot@im.bot",
            user_id="bridge-user@im.wechat",
            created_at_ms=_now_ms(),
            bot_type=str(bot_type or "3").strip() or "3",
            expires_at_ms=_now_ms() + LOGIN_TICKET_TTL_MS,
        )
        with self._condition:
            self._purge_expired_logins_locked()
            self._login_tickets[qrcode] = ticket
        return {
            "qrcode": qrcode,
            "qrcode_img_content": qrcode_url,
            "qrcode_page_url": qrcode_page_url,
            "qrcode_png_url": qrcode_png_url,
        }

    def confirm_login(
        self,
        *,
        qrcode: str,
        status: str = "confirmed",
        account_id: str = "",
        user_id: str = "",
    ) -> LoginTicket | None:
        with self._condition:
            self._purge_expired_logins_locked()
            ticket = self._login_tickets.get(str(qrcode or "").strip())
            if ticket is None:
                ticket = self._resolve_single_waiting_login_locked()
            if ticket is None:
                return None
            ticket.status = _normalize_login_status(status)
            if str(account_id or "").strip():
                ticket.account_id = str(account_id).strip()
            if str(user_id or "").strip():
                ticket.user_id = str(user_id).strip()
            if ticket.status == "confirmed":
                ticket.expires_at_ms = max(ticket.expires_at_ms, _now_ms() + LOGIN_TICKET_TTL_MS)
            self._condition.notify_all()
            return ticket

    def get_login_status(self, *, qrcode: str, wait_ms: int | None = None) -> dict[str, Any]:
        timeout_ms = self.longpoll_timeout_ms if wait_ms is None else max(int(wait_ms), 0)
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        with self._condition:
            lookup = str(qrcode or "").strip()
            while True:
                self._purge_expired_logins_locked()
                ticket = self._login_tickets.get(lookup)
                if ticket is None:
                    return {"status": "expired"}
                if ticket.status != "wait":
                    return self._serialize_login_ticket(ticket)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return {"status": "wait"}
                self._condition.wait(timeout=remaining)

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            self._purge_expired_logins_locked()
            return {
                "queued_messages": [item.payload for item in self._queued_messages],
                "outbox": [entry.request_body for entry in self._outbox],
                "typing_events": [entry.request_body for entry in self._typing_events],
                "upload_count": len(self._uploads),
                "login_count": len(self._login_tickets),
                "login_tickets": {
                    qrcode: {
                        "status": ticket.status,
                        "account_id": ticket.account_id,
                        "user_id": ticket.user_id,
                        "expires_at_ms": ticket.expires_at_ms,
                    }
                    for qrcode, ticket in self._login_tickets.items()
                },
                "next_seq": self._next_seq,
            }

    def _to_official_message(self, event: Mapping[str, Any], *, seq: int) -> dict[str, Any]:
        payload = dict(event or {})
        message = payload.get("message") if isinstance(payload.get("message"), Mapping) else payload
        message = dict(message or {})
        sender = payload.get("sender") if isinstance(payload.get("sender"), Mapping) else {}
        actor_id = str(
            message.get("from_user_id")
            or sender.get("open_id")
            or sender.get("user_id")
            or payload.get("from_user_id")
            or payload.get("open_id")
            or "bridge-user@im.wechat"
        ).strip()
        to_user_id = str(message.get("to_user_id") or payload.get("to_user_id") or "bridge-bot@im.bot").strip()
        message_id = _stable_message_id(
            message.get("message_id")
            or payload.get("message_id")
            or payload.get("event_id")
            or f"bridge-{seq}"
        )
        official_message = {
            "seq": seq,
            "message_id": message_id,
            "from_user_id": actor_id,
            "to_user_id": to_user_id,
            "create_time_ms": _stable_timestamp_ms(
                message.get("create_time_ms") or payload.get("create_time_ms") or payload.get("timestamp")
            ),
            "session_id": str(
                message.get("session_id")
                or message.get("conversation_id")
                or payload.get("session_id")
                or payload.get("conversation_id")
                or f"session-{actor_id}"
            ).strip(),
            "message_type": WEIXIN_MESSAGE_TYPE_USER,
            "message_state": WEIXIN_MESSAGE_STATE_NEW,
            "item_list": _extract_official_item_list(payload),
            "context_token": str(message.get("context_token") or payload.get("context_token") or f"ctx-{message_id}").strip(),
        }
        return official_message

    def _purge_expired_logins_locked(self) -> None:
        now_ms = _now_ms()
        for qrcode, ticket in list(self._login_tickets.items()):
            if ticket.expires_at_ms and ticket.expires_at_ms < now_ms and ticket.status != "confirmed":
                self._login_tickets.pop(qrcode, None)

    def _serialize_login_ticket(self, ticket: LoginTicket) -> dict[str, Any]:
        if ticket.status != "confirmed":
            return {"status": ticket.status}
        return {
            "status": "confirmed",
            "bot_token": ticket.bot_token,
            "ilink_bot_id": ticket.account_id,
            "baseurl": ticket.base_url,
            "ilink_user_id": ticket.user_id,
        }

    def _resolve_single_waiting_login_locked(self) -> LoginTicket | None:
        waiting = [ticket for ticket in self._login_tickets.values() if ticket.status == "wait"]
        if len(waiting) != 1:
            return None
        return waiting[0]


def process_weixin_webhook_event(
    event: Mapping[str, Any] | None,
    *,
    run_agent_fn: Callable[..., str],
) -> dict[str, Any]:
    payload = dict(event or {})
    message = payload.get("message") if isinstance(payload.get("message"), Mapping) else payload
    message = dict(message or {})
    prompt = _extract_prompt_from_event(payload)
    reply_text = str(
        run_agent_fn(
            prompt,
            invocation_metadata={"channel": "weixin", "weixin_event": payload},
        )
        or ""
    ).strip()

    output_bundle = _safe_get_output_bundle(run_agent_fn, fallback_text=reply_text)
    delivery_session = _safe_get_delivery_session(run_agent_fn, payload)
    delivery_plan = _safe_get_delivery_plan(run_agent_fn)
    if not isinstance(delivery_plan, WeixinDeliveryPlan) and isinstance(delivery_session, DeliverySession):
        delivery_plan = WeixinDeliveryAdapter().create(delivery_session, output_bundle)

    official_requests = list(getattr(delivery_plan, "official_requests", []) or [])
    return {
        "ok": True,
        "channel": "weixin",
        "reply": reply_text,
        "message_id": str(message.get("message_id") or "").strip(),
        "output_bundle": {
            "text_blocks": [str(block.text or "") for block in output_bundle.text_blocks],
            "card_count": len(output_bundle.cards),
            "image_count": len(output_bundle.images),
            "file_count": len(output_bundle.files),
        },
        "delivery_session": _serialize_delivery_session(delivery_session),
        "delivery_plan": _serialize_delivery_plan(delivery_plan),
        "weixin_protocol": {
            "sendmessage_requests": official_requests,
        },
        "openclaw_official": {
            "sendmessage_requests": official_requests,
        },
        "source_event": payload,
    }


def create_weixin_bridge_http_server(
    *,
    run_agent_fn: Callable[..., str],
    bridge_state: WeixinOfficialBridgeService | None = None,
    host: str = "127.0.0.1",
    port: int = 8789,
    path: str = "/weixin/webhook",
    public_base_url: str = "",
) -> ThreadingHTTPServer:
    normalized_path = "/" + str(path or "/weixin/webhook").strip().lstrip("/")
    state = bridge_state or WeixinOfficialBridgeService()
    public_base = str(public_base_url or "").strip().rstrip("/")

    class _BridgeHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            request_base_url = _request_base_url(self)
            base_url = public_base or request_base_url

            if parsed.path == "/":
                return self._json(
                    200,
                    {
                        "ok": True,
                        "service": "weixin-bridge",
                        "webhook": f"{base_url}{normalized_path}",
                        "public_base_url": base_url,
                        "official_endpoints": [
                            "/ilink/bot/get_bot_qrcode",
                            "/ilink/bot/get_qrcode_status",
                            "/ilink/bot/getupdates",
                            "/ilink/bot/sendmessage",
                            "/ilink/bot/getconfig",
                            "/ilink/bot/sendtyping",
                            "/ilink/bot/getuploadurl",
                            "/upload",
                            "/download",
                        ],
                    },
                )
            if parsed.path == "/weixin/bridge/state":
                return self._json(200, state.snapshot())
            if parsed.path == "/weixin/bridge/login/qr.png":
                qrcode_value = str((query.get("qrcode") or [""])[0]).strip()
                if not qrcode_value:
                    return self._html(400, "<h1>Missing qrcode</h1>")
                confirm_url = f"{base_url}/weixin/bridge/login/confirm?qrcode={qrcode_value}"
                return self._bytes(200, _render_qr_png(confirm_url), {"Content-Type": "image/png"})
            if parsed.path == "/weixin/bridge/login/qr":
                qrcode = str((query.get("qrcode") or [""])[0]).strip()
                if not qrcode:
                    return self._html(400, "<h1>Missing qrcode</h1>")
                confirm_url = f"{base_url}/weixin/bridge/login/confirm?qrcode={qrcode}"
                image_url = f"{request_base_url}/weixin/bridge/login/qr.png?qrcode={qrcode}"
                return self._html(
                    200,
                    _render_login_qr_page(
                        qrcode=qrcode,
                        confirm_url=confirm_url,
                        image_url=image_url,
                        base_url=base_url,
                    ),
                )
            if parsed.path == "/weixin/bridge/login/confirm":
                requested_qrcode = str((query.get("qrcode") or [""])[0]).strip()
                ticket = state.confirm_login(
                    qrcode=requested_qrcode,
                    status=str((query.get("status") or ["confirmed"])[0]).strip(),
                    account_id=str((query.get("account_id") or [""])[0]).strip(),
                    user_id=str((query.get("user_id") or [""])[0]).strip(),
                )
                if ticket is None:
                    return self._html(404, "<h1>Unknown login token</h1>")
                resolved_note = ""
                if requested_qrcode and requested_qrcode != ticket.qrcode:
                    resolved_note = (
                        f"<p>requestedQrcode={escape(requested_qrcode)}</p>"
                        f"<p>resolvedQrcode={escape(ticket.qrcode)}</p>"
                    )
                return self._html(
                    200,
                    (
                        "<h1>Bridge Login Confirmed</h1>"
                        f"<p>qrcode={ticket.qrcode}</p>"
                        f"{resolved_note}"
                        f"<p>status={ticket.status}</p>"
                        f"<p>baseUrl={ticket.base_url}</p>"
                    ),
                )
            if parsed.path == "/ilink/bot/get_bot_qrcode":
                return self._json(
                    200,
                    state.start_login(
                        base_url=base_url,
                        bot_type=str((query.get("bot_type") or ["3"])[0]).strip() or "3",
                    ),
                )
            if parsed.path == "/ilink/bot/get_qrcode_status":
                qrcode = str((query.get("qrcode") or [""])[0]).strip()
                return self._json(200, state.get_login_status(qrcode=qrcode, wait_ms=state.longpoll_timeout_ms))
            if parsed.path == "/download":
                encrypted_query_param = str((query.get("encrypted_query_param") or [""])[0]).strip()
                content = state.download_upload(download_param=encrypted_query_param)
                if content is None:
                    return self._bytes(404, b"", {"x-error-message": "download_not_found"})
                return self._bytes(200, content, {"Content-Type": "application/octet-stream"})
            return self._json(404, {"ok": False, "error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == "/upload":
                encrypted_query_param = str((query.get("encrypted_query_param") or [""])[0]).strip()
                if not encrypted_query_param:
                    return self._bytes(400, b"", {"x-error-message": "missing_encrypted_query_param"})
                ciphertext = self._read_binary_body()
                download_param = state.accept_upload(
                    upload_param=encrypted_query_param,
                    ciphertext=ciphertext,
                )
                if not download_param:
                    return self._bytes(404, b"", {"x-error-message": "upload_ticket_not_found"})
                return self._bytes(200, b"", {"x-encrypted-param": download_param})
            body = self._read_json_body()
            if body is None:
                return
            if parsed.path == normalized_path:
                response_payload = process_weixin_webhook_event(body, run_agent_fn=run_agent_fn)
                return self._json(200, response_payload)
            if parsed.path == "/weixin/bridge/ingress":
                queued_message = state.enqueue_webhook_event(body)
                return self._json(
                    200,
                    {
                        "ok": True,
                        "queued": True,
                        "message": queued_message,
                        "cursor": str(queued_message["seq"]),
                    },
                )
            if parsed.path == "/ilink/bot/getupdates":
                cursor = str(body.get("get_updates_buf") or "").strip()
                wait_ms = state.longpoll_timeout_ms
                return self._json(200, state.get_updates(cursor=cursor, wait_ms=wait_ms))
            if parsed.path == "/ilink/bot/sendmessage":
                return self._json(200, state.record_sendmessage(body))
            if parsed.path == "/ilink/bot/getconfig":
                return self._json(200, state.get_config(context_token=str(body.get("context_token") or "").strip()))
            if parsed.path == "/ilink/bot/sendtyping":
                return self._json(200, state.record_typing(body))
            if parsed.path == "/ilink/bot/getuploadurl":
                return self._json(200, state.issue_upload_ticket(filekey=str(body.get("filekey") or "").strip()))
            return self._json(404, {"ok": False, "error": "not_found"})

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return None

        def _read_json_body(self) -> dict[str, Any] | None:
            content_length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
            try:
                parsed = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError as exc:
                self._json(400, {"ok": False, "error": f"invalid_json:{exc.msg}"})
                return None
            if not isinstance(parsed, dict):
                self._json(400, {"ok": False, "error": "json_body_must_be_object"})
                return None
            return parsed

        def _read_binary_body(self) -> bytes:
            content_length = int(self.headers.get("Content-Length") or "0")
            return self.rfile.read(content_length) if content_length > 0 else b""

        def _json(self, status: int, payload: Mapping[str, Any]) -> None:
            body = json.dumps(dict(payload), ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _html(self, status: int, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _bytes(self, status: int, payload: bytes, headers: Mapping[str, str] | None = None) -> None:
            body = bytes(payload or b"")
            self.send_response(status)
            for key, value in dict(headers or {}).items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

    return ThreadingHTTPServer((host, int(port)), _BridgeHandler)


def serve_weixin_bridge(
    *,
    run_agent_fn: Callable[..., str],
    host: str = "127.0.0.1",
    port: int = 8789,
    path: str = "/weixin/webhook",
    bridge_state: WeixinOfficialBridgeService | None = None,
    public_base_url: str = "",
) -> int:
    server = create_weixin_bridge_http_server(
        run_agent_fn=run_agent_fn,
        bridge_state=bridge_state,
        host=host,
        port=port,
        path=path,
        public_base_url=public_base_url,
    )
    exposed_base_url = str(public_base_url or f"http://{host}:{int(port)}").rstrip("/")
    print(f"[weixin-bridge] listening on {build_bridge_url(host=host, port=port, path=path)}", flush=True)
    print(f"[weixin-bridge] public base URL: {exposed_base_url}", flush=True)
    print(f"[weixin-bridge] official login endpoint: {exposed_base_url}/ilink/bot/get_bot_qrcode", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0


def _extract_prompt_from_event(payload: Mapping[str, Any]) -> str:
    message = payload.get("message") if isinstance(payload.get("message"), Mapping) else payload
    message = dict(message or {})
    content = message.get("content") if isinstance(message.get("content"), Mapping) else {}
    text = str(content.get("text") or "").strip()
    if text:
        return text
    for item in list(message.get("item_list") or []):
        if not isinstance(item, Mapping):
            continue
        if int(item.get("type") or 0) == 1:
            text_item = item.get("text_item") if isinstance(item.get("text_item"), Mapping) else {}
            text = str(text_item.get("text") or "").strip()
            if text:
                return text
    return ""


def _safe_get_output_bundle(run_agent_fn: Callable[..., str], *, fallback_text: str) -> OutputBundle:
    getter = getattr(run_agent_fn, "get_turn_output_bundle", None)
    if callable(getter):
        try:
            bundle = getter()
        except Exception:
            bundle = None
        if isinstance(bundle, OutputBundle):
            return bundle
    text = str(fallback_text or "").strip()
    return OutputBundle(text_blocks=[TextBlock(text=text)] if text else [])


def _safe_get_delivery_session(run_agent_fn: Callable[..., str], payload: Mapping[str, Any]) -> DeliverySession:
    getter = getattr(run_agent_fn, "get_turn_delivery_session", None)
    if callable(getter):
        try:
            session = getter()
        except Exception:
            session = None
        if isinstance(session, DeliverySession):
            return session
    normalized = _WEIXIN_INPUT_ADAPTER.normalize_event(payload)
    metadata = dict(normalized.get("metadata") or {})
    target = str(metadata.get("weixin.receive_id") or normalized.get("actor_id") or "").strip()
    session_ref = str(metadata.get("weixin.raw_session_ref") or normalized.get("source_event_id") or "").strip()
    metadata = {
        "weixin.chat_type": str(metadata.get("weixin.chat_type") or "").strip(),
        "weixin.conversation_key": str(metadata.get("weixin.conversation_key") or normalized.get("session_id") or "").strip(),
        "weixin.context_token": str(metadata.get("weixin.context_token") or "").strip(),
        "weixin.message_id": str(metadata.get("weixin.message_id") or normalized.get("source_event_id") or "").strip(),
        "weixin.raw_session_ref": session_ref,
    }
    return DeliverySession(
        platform="weixin",
        mode="reply",
        target=target,
        target_type="open_id",
        thread_id=session_ref,
        metadata={key: value for key, value in metadata.items() if value},
    )


def _safe_get_delivery_plan(run_agent_fn: Callable[..., str]) -> WeixinDeliveryPlan | None:
    getter = getattr(run_agent_fn, "get_turn_delivery_plan", None)
    if not callable(getter):
        return None
    try:
        plan = getter()
    except Exception:
        return None
    return plan if isinstance(plan, WeixinDeliveryPlan) else None


def _serialize_delivery_session(session: DeliverySession | None) -> dict[str, Any] | None:
    if not isinstance(session, DeliverySession):
        return None
    return {
        "platform": session.platform,
        "mode": session.mode,
        "target": session.target,
        "target_type": session.target_type,
        "thread_id": session.thread_id,
        "metadata": dict(session.metadata or {}),
    }


def _serialize_delivery_plan(plan: WeixinDeliveryPlan | None) -> dict[str, Any] | None:
    if not isinstance(plan, WeixinDeliveryPlan):
        return None
    return {
        "rendered_text": plan.rendered_text,
        "operation_count": len(plan.operations),
        "operations": [
            {
                "action": operation.action,
                "delivery_mode": operation.delivery_mode,
                "endpoint": operation.endpoint,
                "request_body": operation.request_body,
                "summary": operation.summary,
                "metadata": dict(operation.metadata or {}),
            }
            for operation in plan.operations
        ],
    }


def _request_base_url(handler: BaseHTTPRequestHandler) -> str:
    host = str(handler.headers.get("Host") or "127.0.0.1").strip()
    return f"http://{host}"


def _cursor_to_seq(cursor: str) -> int:
    text = str(cursor or "").strip()
    if not text:
        return 0
    try:
        return max(int(text), 0)
    except ValueError:
        return 0


def _stable_message_id(raw: Any) -> int:
    text = str(raw or "").strip()
    if text.isdigit():
        return int(text)
    return abs(hash(text)) % 2_147_483_647 or 1


def _stable_timestamp_ms(raw: Any) -> int:
    text = str(raw or "").strip()
    if text.isdigit():
        return int(text)
    return _now_ms()


def _extract_official_item_list(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    message = payload.get("message") if isinstance(payload.get("message"), Mapping) else payload
    message = dict(message or {})
    item_list = message.get("item_list") if isinstance(message.get("item_list"), list) else None
    if item_list:
        normalized = [dict(item) for item in item_list if isinstance(item, Mapping)]
        if normalized:
            return normalized
    text = _extract_prompt_from_event(payload)
    return [{"type": 1, "text_item": {"text": text}}]


def _now_ms() -> int:
    return int(time.time() * 1000)


def _normalize_login_status(raw: Any) -> str:
    status = str(raw or "").strip().lower()
    if status in {"wait", "scaned", "confirmed", "expired"}:
        return status
    return "confirmed"


def _render_login_qr_page(*, qrcode: str, confirm_url: str, image_url: str, base_url: str) -> str:
    escaped_qrcode = escape(qrcode)
    escaped_confirm_url = escape(confirm_url)
    escaped_image_url = escape(image_url)
    escaped_base_url = escape(base_url)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Butler Weixin Login QR</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --ink: #132238;
      --muted: #5f728c;
      --line: #d8e0eb;
      --accent: #1177ff;
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
    .hint {{
      margin-top: 18px;
      padding: 14px 16px;
      border-radius: 14px;
      background: #eef5ff;
      border: 1px solid #c9defe;
    }}
    @media (max-width: 760px) {{
      .grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <div class="panel">
      <div class="grid">
        <div>
          <div class="qr-box"><img src="{escaped_image_url}" alt="Butler Weixin Login QR" style="width:320px;height:320px;" /></div>
        </div>
        <div>
          <h1>Butler 微信登录二维码</h1>
          <p>在电脑上打开这个页面，然后用手机微信扫一扫左侧二维码。</p>
          <p class="muted">扫码后，手机会访问你的本地 bridge 确认地址；确认完成后，Butler 客户端会从长轮询里接住登录结果。</p>
          <p><strong>登录 token</strong></p>
          <div class="mono">{escaped_qrcode}</div>
          <p style="margin-top:14px;"><strong>扫码后访问的确认地址</strong></p>
          <div class="mono">{escaped_confirm_url}</div>
          <div class="hint">
            <p><strong>注意</strong></p>
            <p class="muted">这个二维码编码的是你电脑上的 bridge 地址，不是微信官方网页。要让手机扫成功，地址必须能从手机访问到。</p>
            <p class="muted">当前 bridge 基址：{escaped_base_url}</p>
          </div>
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


__all__ = [
    "QueuedWeixinMessage",
    "RecordedOutboundMessage",
    "RecordedTypingEvent",
    "WeixinOfficialBridgeService",
    "build_bridge_url",
    "create_weixin_bridge_http_server",
    "process_weixin_webhook_event",
    "serve_weixin_bridge",
]
