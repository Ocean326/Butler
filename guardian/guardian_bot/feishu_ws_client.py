"""Guardian 飞书长连接：建立 WebSocket 连接，并处理简单指令。"""

from __future__ import annotations

import asyncio
import json
import subprocess
import threading
import time
from pathlib import Path

from guardian_bot.butler_inspector import format_inspection_report, inspect_butler_main
from guardian_bot.feishu_client import send_private_message

try:
    import lark_oapi as lark
    from lark_oapi import ws
    import lark_oapi.ws.client as _ws_client_module
except ImportError:  # pragma: no cover - runtime optional dependency
    lark = None  # type: ignore[assignment]
    ws = None  # type: ignore[assignment]
    _ws_client_module = None  # type: ignore[assignment]

_seen_messages: dict[str, float] = {}
_seen_lock = threading.Lock()
_MESSAGE_TTL = 15 * 60
_last_repair_ts = 0.0
_repair_lock = threading.Lock()
_REPAIR_COOLDOWN_SECONDS = 180


def _claim_message(message_id: str) -> bool:
    """去重同一条飞书消息的处理，防止重复回复。"""
    if not message_id:
        return True
    now = time.time()
    with _seen_lock:
        expired = [k for k, ts in _seen_messages.items() if now - ts > _MESSAGE_TTL]
        for k in expired:
            _seen_messages.pop(k, None)
        if message_id in _seen_messages:
            return False
        _seen_messages[message_id] = now
        return True


def _needs_repair(inspection: dict) -> bool:
    return not bool(inspection.get("overall", {}).get("healthy"))


def _repair_needed_text(inspection: dict) -> list[str]:
    reasons: list[str] = []
    if not inspection.get("main", {}).get("healthy"):
        reasons.append("主进程状态不健康")
    if not inspection.get("heartbeat", {}).get("healthy"):
        reasons.append("心跳状态不健康")
    if not inspection.get("guardian_handover", {}).get("healthy"):
        reasons.append("守护进程不健康")
    return reasons


def _run_repair_action(butler_root: Path) -> tuple[bool, str]:
    guardian_manager = butler_root.parent / "guardian" / "manager.ps1"
    manager_script = butler_root / "butler_bot_code" / "manager.ps1"
    if guardian_manager.exists():
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(guardian_manager),
                    "restart-stack",
                ],
                cwd=str(guardian_manager.parent),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
            )
            out = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
            if len(out) > 1200:
                out = out[-1200:]
            if result.returncode != 0:
                return False, out or f"guardian 标准重启失败 (exit={result.returncode})"
            return True, out or "已触发 guardian 标准重启 (talk+heartbeat)"
        except subprocess.TimeoutExpired:
            return False, "guardian 标准重启超时（>120 秒）"
        except Exception as exc:
            return False, f"guardian 标准重启异常: {exc}"

    if not manager_script.exists():
        return False, f"未找到修复脚本：{manager_script}"
    try:
        result = subprocess.run(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(manager_script),
                "start",
                "butler_bot",
            ],
            cwd=str(butler_root / "butler_bot_code"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
        )
        out = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        if len(out) > 1200:
            out = out[-1200:]
        if result.returncode != 0:
            return False, out or f"自愈脚本失败 (exit={result.returncode})"
        return True, out or "已触发 manager.ps1 start butler_bot"
    except subprocess.TimeoutExpired:
        return False, "自愈脚本执行超时（>90 秒）"
    except Exception as exc:
        return False, f"自愈脚本执行异常: {exc}"


def _build_reply(
    before: dict,
    after: dict | None,
    repair_attempted: bool,
    repair_ok: bool,
    repair_log: str,
) -> str:
    lines: list[str] = ["## Guardian 巡检结果", "", before.get("summary") or "(无摘要)"]
    reasons = _repair_needed_text(before)
    if reasons:
        lines.append("")
        lines.append("**当前风险**")
        for reason in reasons:
            lines.append(f"- {reason}")

    if repair_attempted:
        lines.append("")
        lines.append("**自动抢救动作**")
        lines.append(f"- 动作: `manager.ps1 start butler_bot`")
        lines.append(f"- 结果: {'成功触发' if repair_ok else '触发失败'}")
        if repair_log:
            lines.append("- 输出摘要:")
            lines.append(f"```text\n{repair_log}\n```")
        if after is not None:
            lines.append("")
            lines.append("**抢救后复检**")
            lines.append(f"- {after.get('summary') or '(无摘要)'}")
    else:
        lines.append("")
        lines.append("**自动抢救动作**")
        lines.append("- 当前未触发（状态健康或处于冷却期）")

    lines.append("")
    lines.append(format_inspection_report(after or before))
    return "\n".join(lines)


def start_feishu_ws_in_background(app_id: str, app_secret: str, butler_root: Path | None) -> threading.Thread | None:
    """
    在后台线程启动飞书长连接。
    返回线程对象，若启动失败返回 None。
    """
    app_id = str(app_id or "").strip()
    app_secret = str(app_secret or "").strip()
    if not app_id or not app_secret:
        print("[guardian/feishu_ws] 缺少 app_id/app_secret，跳过长连接", flush=True)
        return None

    def _run_ws() -> None:
        if lark is None or ws is None or _ws_client_module is None:
            print("[guardian/feishu_ws] 请安装 lark-oapi: pip install lark-oapi", flush=True)
            return

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _ws_client_module.loop = loop

        def _on_message(data: "lark.im.v1.P2ImMessageReceiveV1") -> None:  # type: ignore[name-defined]
            try:
                global _last_repair_ts
                ev = getattr(data, "event", None)
                msg = getattr(ev, "message", None) if ev else None
                if not msg:
                    return
                message_id = str(getattr(msg, "message_id", "") or "").strip()
                if not _claim_message(message_id):
                    print(f"[guardian/feishu_ws] 跳过重复消息: message_id={message_id}", flush=True)
                    return
                content = getattr(msg, "content", None)
                chat_id = getattr(msg, "chat_id", "") or ""
                if not content or not chat_id:
                    return
                try:
                    body = json.loads(content)
                except Exception:
                    return
                text = str(body.get("text") or "").strip()
                if not text:
                    return
                print(f"[guardian/feishu_ws] 收到消息: id={message_id}, chat_id={chat_id}, text={text[:80]}", flush=True)
                root = Path(butler_root) if butler_root else None
                if not root or not root.exists():
                    reply = "Guardian 巡检失败：butler_root 未配置或不存在，无法执行巡检。"
                    ok = send_private_message(app_id, app_secret, reply, chat_id, "chat_id")
                    print(f"[guardian/feishu_ws] butler_root 不可用，已回复错误: {'OK' if ok else 'FAIL'}", flush=True)
                    return

                try:
                    inspection = inspect_butler_main(root)
                except Exception as exc:
                    reply = f"Guardian 巡检失败（本地探针异常）：{exc}"
                    ok = send_private_message(app_id, app_secret, reply, chat_id, "chat_id")
                    print(f"[guardian/feishu_ws] 本地探针异常，已回复错误: {'OK' if ok else 'FAIL'}", flush=True)
                    return

                repair_attempted = False
                repair_ok = False
                repair_log = ""
                inspection_after: dict | None = None
                if _needs_repair(inspection):
                    now = time.time()
                    with _repair_lock:
                        can_repair = now - _last_repair_ts >= _REPAIR_COOLDOWN_SECONDS
                        if can_repair:
                            _last_repair_ts = now
                    if can_repair:
                        repair_attempted = True
                        repair_ok, repair_log = _run_repair_action(root)
                        time.sleep(2.0)
                        try:
                            inspection_after = inspect_butler_main(root)
                        except Exception as exc:
                            repair_log = (repair_log + f"\n复检失败: {exc}").strip()
                    else:
                        wait_seconds = int(_REPAIR_COOLDOWN_SECONDS - (now - _last_repair_ts))
                        repair_log = f"处于冷却期，约 {max(1, wait_seconds)} 秒后可再次自动抢救"

                reply = _build_reply(
                    before=inspection,
                    after=inspection_after,
                    repair_attempted=repair_attempted,
                    repair_ok=repair_ok,
                    repair_log=repair_log,
                )
                ok = send_private_message(app_id, app_secret, reply, chat_id, "chat_id")
                print(
                    f"[guardian/feishu_ws] 已发送巡检与抢救结果: repaired={repair_attempted}, repair_ok={repair_ok}, send_ok={'OK' if ok else 'FAIL'}",
                    flush=True,
                )
            except Exception as e:
                print(f"[guardian/feishu_ws] 处理消息异常: {e}", flush=True)

        def _on_card_action(data):
            try:
                return lark.cardkit.v1.P2CardActionTriggerResponse(
                    {"toast": {"type": "info", "content": "Guardian 已收到"}}
                )
            except Exception:
                return None

        handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(_on_message)
            .register_p2_card_action_trigger(_on_card_action)
            .build()
        )
        cli = ws.Client(app_id, app_secret, event_handler=handler, log_level=lark.LogLevel.WARNING)
        print("[guardian/feishu_ws] 启动飞书长连接...", flush=True)
        try:
            cli.start()
        except Exception as e:
            print(f"[guardian/feishu_ws] 长连接异常: {e}", flush=True)

    t = threading.Thread(target=_run_ws, daemon=True)
    t.start()
    return t
