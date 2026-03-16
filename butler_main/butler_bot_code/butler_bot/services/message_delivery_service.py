from __future__ import annotations

import json


class MessageDeliveryService:
    def __init__(self, manager, *, requests_module) -> None:
        self._manager = manager
        self._requests = requests_module

    @staticmethod
    def markdown_to_interactive_card(md: str) -> dict:
        content = (md or "").strip()
        if not content:
            content = "(空)"
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

    @staticmethod
    def markdown_to_feishu_post(md: str) -> dict:
        content = (md or "").strip()
        if not content:
            content = "(空)"
        if len(content) > 28000:
            content = content[:28000] + "\n..."
        return {"zh_cn": {"title": "回复", "content": [[{"tag": "md", "text": content}]]}}

    def send_private_message(
        self,
        cfg: dict,
        text: str,
        *,
        receive_id: str = "",
        receive_id_type: str = "open_id",
        fallback_to_startup_target: bool = False,
        heartbeat_cfg: dict | None = None,
    ) -> bool:
        manager = self._manager
        target_id = str(receive_id or "").strip()
        target_type = str(receive_id_type or "open_id").strip() or "open_id"
        if fallback_to_startup_target:
            target_id, target_type = manager._heartbeat_target(cfg, target_id, target_type)
        if not target_id:
            print("[私聊发送] 未配置 receive_id，跳过发送", flush=True)
            return False
        hb = heartbeat_cfg or {}
        app_id = str((hb.get("app_id") or (cfg or {}).get("app_id")) or "").strip()
        app_secret = str((hb.get("app_secret") or (cfg or {}).get("app_secret")) or "").strip()
        if not app_id or not app_secret:
            print("[私聊发送] 缺少 app_id/app_secret，跳过发送", flush=True)
            return False
        try:
            session = self._requests.Session()
            session.trust_env = False
            token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            token_resp = session.post(token_url, json={"app_id": app_id, "app_secret": app_secret}, timeout=12)
            token_data = token_resp.json()
            if token_data.get("code") != 0:
                print(f"[私聊发送] 获取token失败: {token_data}", flush=True)
                return False
            token = token_data.get("tenant_access_token")
            msg_url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={target_type}"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            plain = (text or "").strip()[:4000]
            sent = False
            data = {}
            if plain:
                card = self.markdown_to_interactive_card(plain)
                body = {"receive_id": target_id, "msg_type": "interactive", "content": json.dumps(card, ensure_ascii=False)}
                resp = session.post(msg_url, headers=headers, json=body, timeout=15)
                data = resp.json()
                if data.get("code") == 0:
                    sent = True
                else:
                    post_content = self.markdown_to_feishu_post(plain)
                    body = {"receive_id": target_id, "msg_type": "post", "content": json.dumps(post_content, ensure_ascii=False)}
                    resp = session.post(msg_url, headers=headers, json=body, timeout=15)
                    data = resp.json()
                    if data.get("code") == 0:
                        sent = True
            if not sent:
                body = {"receive_id": target_id, "msg_type": "text", "content": json.dumps({"text": plain or "(空)"}, ensure_ascii=False)}
                resp = session.post(msg_url, headers=headers, json=body, timeout=15)
                data = resp.json()
                sent = data.get("code") == 0
            if not sent:
                print(f"[私聊发送] 发送失败: {data}", flush=True)
            return sent
        except Exception as e:
            print(f"[私聊发送] 异常: {e}", flush=True)
            return False

    def send_startup_private_notification(
        self,
        cfg: dict,
        text: str,
        *,
        startup_notify_open_id_key: str,
        startup_notify_receive_id_type_key: str,
    ) -> bool:
        receive_id = str((cfg or {}).get(startup_notify_open_id_key) or "").strip()
        if not receive_id:
            print("[启动通知] 未配置 startup_notify_open_id，跳过私聊通知", flush=True)
            return False
        receive_id_type = str((cfg or {}).get(startup_notify_receive_id_type_key) or "open_id").strip() or "open_id"
        return self.send_private_message(cfg, text, receive_id=receive_id, receive_id_type=receive_id_type)
