"""Guardian 飞书客户端：发送私聊消息。"""

from __future__ import annotations

import json
from typing import Any

import requests


def _markdown_to_interactive_card(md: str) -> dict[str, Any]:
    content = (md or "").strip() or "(空)"
    if len(content) > 28000:
        content = content[:28000] + "\n..."
    return {
        "schema": "2.0",
        "config": {"wide_screen_mode": True},
        "body": {
            "direction": "vertical",
            "padding": "12px 12px 12px 12px",
            "elements": [{"tag": "markdown", "content": content}],
        },
    }


def _markdown_to_feishu_post(md: str) -> dict[str, Any]:
    content = (md or "").strip() or "(空)"
    if len(content) > 28000:
        content = content[:28000] + "\n..."
    return {"zh_cn": {"title": "回复", "content": [[{"tag": "md", "text": content}]]}}


def send_private_message(
    app_id: str,
    app_secret: str,
    text: str,
    receive_id: str,
    receive_id_type: str = "open_id",
) -> bool:
    """发送飞书私聊消息。"""
    app_id = str(app_id or "").strip()
    app_secret = str(app_secret or "").strip()
    receive_id = str(receive_id or "").strip()
    receive_id_type = str(receive_id_type or "open_id").strip() or "open_id"
    if not app_id or not app_secret or not receive_id:
        print("[guardian/feishu] 缺少 app_id/app_secret/receive_id，跳过发送", flush=True)
        return False
    try:
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        token_resp = requests.post(
            token_url,
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=12,
        )
        token_data = token_resp.json()
        if token_data.get("code") != 0:
            print(f"[guardian/feishu] 获取 token 失败: {token_data}", flush=True)
            return False
        token = token_data.get("tenant_access_token")
        msg_url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        plain = (text or "").strip()[:4000]
        sent = False
        last_data: dict[str, Any] = {}
        if plain:
            card = _markdown_to_interactive_card(plain)
            body = {"receive_id": receive_id, "msg_type": "interactive", "content": json.dumps(card, ensure_ascii=False)}
            resp = requests.post(msg_url, headers=headers, json=body, timeout=15)
            last_data = resp.json()
            if last_data.get("code") == 0:
                sent = True
            else:
                post_content = _markdown_to_feishu_post(plain)
                body = {"receive_id": receive_id, "msg_type": "post", "content": json.dumps(post_content, ensure_ascii=False)}
                resp = requests.post(msg_url, headers=headers, json=body, timeout=15)
                last_data = resp.json()
                if last_data.get("code") == 0:
                    sent = True
            if not sent:
                body = {"receive_id": receive_id, "msg_type": "text", "content": json.dumps({"text": plain or "(空)"}, ensure_ascii=False)}
                resp = requests.post(msg_url, headers=headers, json=body, timeout=15)
                last_data = resp.json()
                sent = last_data.get("code") == 0
        if not sent:
            print(f"[guardian/feishu] 发送失败: {last_data}", flush=True)
        return sent
    except Exception as e:
        print(f"[guardian/feishu] 异常: {e}", flush=True)
        return False
