from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import urlopen
from uuid import uuid4

from agents_os.contracts import DeliverySession, OutputBundle


WEIXIN_MESSAGE_TYPE_BOT = 2
WEIXIN_MESSAGE_STATE_FINISH = 2

WEIXIN_ITEM_TYPE_TEXT = 1
WEIXIN_ITEM_TYPE_IMAGE = 2
WEIXIN_ITEM_TYPE_FILE = 4
WEIXIN_ITEM_TYPE_VIDEO = 5

DEFAULT_LONGPOLL_TIMEOUT_MS = 35_000
DEFAULT_CONTROL_URL = "http://127.0.0.1:18789/"
DEFAULT_LOGIN_COMMAND = "butler-core"
DEFAULT_BRIDGE_BASE_URL = "http://127.0.0.1:8789/"


@dataclass(slots=True, frozen=True)
class OfficialQrLink:
    control_url: str = DEFAULT_CONTROL_URL
    login_command: str = DEFAULT_LOGIN_COMMAND

    def render_markdown(self) -> str:
        return (
            "# Butler Weixin Login\n\n"
            f"- 控制台: {self.control_url}\n"
            f"- 登录命令: `{self.login_command}`\n"
        )


@dataclass(slots=True, frozen=True)
class OfficialBridgeQrLink:
    bridge_base_url: str = DEFAULT_BRIDGE_BASE_URL
    cdn_base_url: str = DEFAULT_BRIDGE_BASE_URL
    login_command: str = DEFAULT_LOGIN_COMMAND
    qrcode: str = ""
    qrcode_url: str = ""
    qrcode_page_url: str = ""

    def render_markdown(self) -> str:
        bridge_url = str(self.bridge_base_url or DEFAULT_BRIDGE_BASE_URL).rstrip("/") + "/"
        cdn_url = str(self.cdn_base_url or bridge_url).rstrip("/") + "/"
        qrcode = str(self.qrcode or "").strip()
        qrcode_url = str(self.qrcode_url or "").strip()
        qrcode_page_url = str(self.qrcode_page_url or "").strip()
        lines = [
            "# Butler Weixin Bridge Login",
            "",
            f"- Bridge API: {bridge_url}",
            f"- Bridge CDN: {cdn_url}",
            f"- 登录命令: `{self.login_command}`",
            "- 如需兼容外部状态目录，请把对应渠道配置里的 `baseUrl` 和 `cdnBaseUrl` 都指向这套本地 bridge。",
        ]
        if qrcode_page_url:
            lines.append(f"- 当前二维码网页: {qrcode_page_url}")
        if qrcode_url:
            lines.append(f"- 当前扫码目标链接: {qrcode_url}")
        if qrcode:
            lines.append(f"- 当前二维码 token: `{qrcode}`")
        lines.extend(
            [
                "",
                "```json",
                json.dumps(
                    {
                        "channels": {
                            "weixin": {
                                "baseUrl": bridge_url,
                                "cdnBaseUrl": cdn_url,
                            }
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
                "",
                f"- 二维码获取接口: {bridge_url}ilink/bot/get_bot_qrcode?bot_type=3",
            ]
        )
        return "\n".join(lines) + "\n"


def new_client_id(prefix: str = "butler-weixin") -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def bundle_to_text(bundle: OutputBundle) -> str:
    lines: list[str] = []
    for block in bundle.text_blocks:
        text = str(block.text or "").strip()
        if text:
            lines.append(text)
    for card in bundle.cards:
        title = str(card.title or "").strip()
        body = str(card.body or "").strip()
        if title and body:
            lines.append(f"【{title}】\n{body}")
        elif title:
            lines.append(f"【{title}】")
        elif body:
            lines.append(body)
    for link in bundle.doc_links:
        title = str(link.title or "").strip()
        url = str(link.url or "").strip()
        if title and url:
            lines.append(f"【{title}】\n{url}")
        elif url:
            lines.append(url)
    return "\n\n".join(lines).strip()


def build_text_item(text: str) -> dict[str, Any]:
    return {
        "type": WEIXIN_ITEM_TYPE_TEXT,
        "text_item": {"text": str(text or "")},
    }


def build_sendmessage_request(
    *,
    session: DeliverySession,
    text: str,
    context_token: str = "",
    client_id: str = "",
) -> dict[str, Any]:
    request_client_id = str(client_id or new_client_id()).strip()
    body = {
        "msg": {
            "from_user_id": "",
            "to_user_id": str(session.target or "").strip(),
            "client_id": request_client_id,
            "message_type": WEIXIN_MESSAGE_TYPE_BOT,
            "message_state": WEIXIN_MESSAGE_STATE_FINISH,
            "item_list": [build_text_item(text)],
        }
    }
    if str(context_token or "").strip():
        body["msg"]["context_token"] = str(context_token).strip()
    return body


def build_media_sendmessage_request(
    *,
    session: DeliverySession,
    item_type: int,
    local_path: str,
    context_token: str = "",
    client_id: str = "",
    caption: str = "",
) -> dict[str, Any]:
    request_client_id = str(client_id or new_client_id()).strip()
    resolved_path = str(local_path or "").strip()
    if item_type == WEIXIN_ITEM_TYPE_IMAGE:
        item = {"type": item_type, "image_item": {"local_path": resolved_path}}
    elif item_type == WEIXIN_ITEM_TYPE_VIDEO:
        item = {"type": item_type, "video_item": {"local_path": resolved_path}}
    else:
        item = {
            "type": WEIXIN_ITEM_TYPE_FILE,
            "file_item": {"local_path": resolved_path, "file_name": Path(resolved_path).name},
        }
    item_list = [item]
    caption_text = str(caption or "").strip()
    if caption_text:
        item_list.insert(0, build_text_item(caption_text))
    body = {
        "msg": {
            "from_user_id": "",
            "to_user_id": str(session.target or "").strip(),
            "client_id": request_client_id,
            "message_type": WEIXIN_MESSAGE_TYPE_BOT,
            "message_state": WEIXIN_MESSAGE_STATE_FINISH,
            "item_list": item_list,
        }
    }
    if str(context_token or "").strip():
        body["msg"]["context_token"] = str(context_token).strip()
    return body


def build_getupdates_response(
    *,
    messages: Iterable[dict[str, Any]] | None = None,
    cursor: str = "",
    longpolling_timeout_ms: int = DEFAULT_LONGPOLL_TIMEOUT_MS,
    ret: int = 0,
    errcode: int | None = None,
    errmsg: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ret": int(ret),
        "msgs": list(messages or []),
        "get_updates_buf": str(cursor or ""),
        "longpolling_timeout_ms": int(longpolling_timeout_ms),
    }
    if errcode is not None:
        payload["errcode"] = int(errcode)
    if str(errmsg or "").strip():
        payload["errmsg"] = str(errmsg).strip()
    return payload


def build_getconfig_response(*, typing_ticket: str = "", ret: int = 0, errmsg: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"ret": int(ret)}
    if str(typing_ticket or "").strip():
        payload["typing_ticket"] = str(typing_ticket).strip()
    if str(errmsg or "").strip():
        payload["errmsg"] = str(errmsg).strip()
    return payload


def build_sendtyping_response(*, ret: int = 0, errmsg: str = "") -> dict[str, Any]:
    payload = {"ret": int(ret)}
    if str(errmsg or "").strip():
        payload["errmsg"] = str(errmsg).strip()
    return payload


def build_sendmessage_response() -> dict[str, Any]:
    return {}


def fetch_bridge_qr_link(
    bridge_base_url: str,
    *,
    bot_type: str = "3",
    timeout_ms: int = 5_000,
    cdn_base_url: str = "",
    login_command: str = DEFAULT_LOGIN_COMMAND,
) -> OfficialBridgeQrLink:
    base_url = str(bridge_base_url or DEFAULT_BRIDGE_BASE_URL).strip().rstrip("/") + "/"
    request_url = f"{base_url}ilink/bot/get_bot_qrcode?bot_type={quote(str(bot_type or '3').strip())}"
    with urlopen(request_url, timeout=max(timeout_ms, 1) / 1000.0) as response:
        payload = json.loads(response.read().decode("utf-8"))
    qrcode = str(payload.get("qrcode") or "").strip()
    qrcode_url = str(payload.get("qrcode_img_content") or "").strip()
    qrcode_page_url = str(payload.get("qrcode_page_url") or "").strip()
    if not qrcode_page_url:
        if qrcode and qrcode_url.startswith(base_url) and "/weixin/bridge/login/confirm" in qrcode_url:
            qrcode_page_url = f"{base_url}weixin/bridge/login/qr?qrcode={quote(qrcode)}"
        else:
            qrcode_page_url = qrcode_url
    return OfficialBridgeQrLink(
        bridge_base_url=base_url,
        cdn_base_url=str(cdn_base_url or base_url).strip().rstrip("/") + "/",
        login_command=str(login_command or DEFAULT_LOGIN_COMMAND),
        qrcode=qrcode,
        qrcode_url=qrcode_url,
        qrcode_page_url=qrcode_page_url,
    )


def write_qr_link_markdown(
    path: str | Path,
    *,
    control_url: str = DEFAULT_CONTROL_URL,
    login_command: str = DEFAULT_LOGIN_COMMAND,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    qr_link = OfficialQrLink(control_url=str(control_url), login_command=str(login_command))
    target.write_text(qr_link.render_markdown(), encoding="utf-8")
    return target


def write_bridge_qr_link_markdown(
    path: str | Path,
    *,
    bridge_base_url: str = DEFAULT_BRIDGE_BASE_URL,
    bot_type: str = "3",
    timeout_ms: int = 5_000,
    cdn_base_url: str = "",
    login_command: str = DEFAULT_LOGIN_COMMAND,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    qr_link = fetch_bridge_qr_link(
        bridge_base_url,
        bot_type=bot_type,
        timeout_ms=timeout_ms,
        cdn_base_url=cdn_base_url,
        login_command=login_command,
    )
    target.write_text(qr_link.render_markdown(), encoding="utf-8")
    return target


__all__ = [
    "DEFAULT_CONTROL_URL",
    "DEFAULT_LOGIN_COMMAND",
    "DEFAULT_LONGPOLL_TIMEOUT_MS",
    "OfficialQrLink",
    "OfficialBridgeQrLink",
    "WEIXIN_ITEM_TYPE_FILE",
    "WEIXIN_ITEM_TYPE_IMAGE",
    "WEIXIN_ITEM_TYPE_TEXT",
    "WEIXIN_ITEM_TYPE_VIDEO",
    "WEIXIN_MESSAGE_STATE_FINISH",
    "WEIXIN_MESSAGE_TYPE_BOT",
    "build_getconfig_response",
    "build_getupdates_response",
    "build_media_sendmessage_request",
    "build_sendmessage_request",
    "build_sendmessage_response",
    "build_sendtyping_response",
    "bundle_to_text",
    "fetch_bridge_qr_link",
    "new_client_id",
    "write_bridge_qr_link_markdown",
    "write_qr_link_markdown",
]
