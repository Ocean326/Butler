from __future__ import annotations

from datetime import datetime


class DeliveryFlowService:
    def __init__(self, manager) -> None:
        self._manager = manager

    def format_heartbeat_interval(self, heartbeat_cfg: dict) -> str:
        cfg = heartbeat_cfg or {}
        every_seconds = cfg.get("every_seconds")
        if every_seconds is not None:
            sec = max(1, int(every_seconds))
            if sec < 60:
                return f"每{sec}秒"
            return f"每{sec // 60}分{sec % 60}秒" if sec % 60 else f"每{sec // 60}分钟"
        every_minutes = max(1, int(cfg.get("every_minutes", 180)))
        return f"每{every_minutes}分钟"

    def send_heartbeat_start_notification(
        self,
        cfg: dict,
        heartbeat_cfg: dict,
        *,
        heartbeat_receive_id_key: str,
        heartbeat_receive_id_type_key: str,
    ) -> None:
        manager = self._manager
        interval_text = self.format_heartbeat_interval(heartbeat_cfg)
        msg = f"** heartbeat 开始跳动 **\n\n跳动频率：{interval_text}\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        receive_id = str((heartbeat_cfg or {}).get(heartbeat_receive_id_key) or "").strip()
        receive_id_type = str((heartbeat_cfg or {}).get(heartbeat_receive_id_type_key) or "open_id").strip() or "open_id"
        ok = manager._send_private_message(
            cfg,
            msg,
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            fallback_to_startup_target=True,
            heartbeat_cfg=heartbeat_cfg,
        )
        if ok:
            print(f"[心跳服务] 已发送「开始跳动」初始化消息（{interval_text}）", flush=True)
        else:
            print("[心跳服务] 初始化消息发送失败（不影响后续跳动）", flush=True)

    def send_heartbeat_upgrade_request_notification(self, cfg: dict, request: dict) -> bool:
        manager = self._manager
        return manager._send_private_message(
            cfg,
            manager._format_heartbeat_upgrade_request_message(request),
            receive_id="",
            receive_id_type="open_id",
            fallback_to_startup_target=True,
            heartbeat_cfg=None,
        )

    def emit_self_mind_cycle_receipt(
        self,
        workspace: str,
        cfg: dict,
        proposal: dict,
        *,
        heartbeat_receive_id_key: str,
        heartbeat_receive_id_type_key: str,
    ) -> bool:
        manager = self._manager
        if not manager._debug_receipts_enabled(cfg, scope="self_mind"):
            return False
        heartbeat_cfg = (cfg or {}).get("heartbeat") or {}
        if not isinstance(heartbeat_cfg, dict):
            return False
        receive_id = str((heartbeat_cfg or {}).get(heartbeat_receive_id_key) or "").strip()
        if not bool(heartbeat_cfg.get("enabled")) and not receive_id:
            return False
        receive_id_type = str((heartbeat_cfg or {}).get(heartbeat_receive_id_type_key) or "open_id").strip() or "open_id"
        text = manager._build_self_mind_cycle_receipt_text(proposal)
        if not text:
            return False
        sent = manager._send_private_message(
            cfg,
            text,
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            fallback_to_startup_target=True,
            heartbeat_cfg=heartbeat_cfg,
        )
        print(f"[self-mind·handoff] 发往 heartbeat 窗口: {'成功' if sent else '失败/跳过'}", flush=True)
        return sent
