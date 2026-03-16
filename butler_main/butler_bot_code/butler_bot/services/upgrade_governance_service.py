from __future__ import annotations

import uuid
from datetime import datetime

from governor import GovernedAction


class UpgradeGovernanceService:
    def __init__(self, manager, *, governor, body_root_text: str) -> None:
        self._manager = manager
        self._governor = governor
        self._body_root_text = body_root_text

    def normalize_heartbeat_upgrade_request(self, payload: dict | None) -> dict:
        data = dict(payload or {})
        action = str(data.get("action") or "execute_prompt").strip() or "execute_prompt"
        execute_prompt = str(data.get("execute_prompt") or "").strip()
        requires_restart = bool(data.get("requires_restart"))
        maintainer_agent_role = str(data.get("maintainer_agent_role") or "update-agent").strip() or "update-agent"
        target_paths = [str(item).strip() for item in (data.get("target_paths") or []) if str(item).strip()]
        if action == "execute_prompt" and not execute_prompt and requires_restart:
            action = "restart"
        if action == "restart":
            requires_restart = True
        return {
            "version": 1,
            "request_id": str(data.get("request_id") or uuid.uuid4()),
            "created_at": str(data.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "status": str(data.get("status") or "pending").strip() or "pending",
            "source": str(data.get("source") or "heartbeat").strip() or "heartbeat",
            "action": action,
            "reason": str(data.get("reason") or "心跳提出升级申请").strip() or "心跳提出升级申请",
            "summary": str(data.get("summary") or data.get("reason") or "").strip(),
            "execute_prompt": execute_prompt,
            "maintainer_agent_role": maintainer_agent_role,
            "target_paths": target_paths,
            "requires_restart": requires_restart,
            "approved_at": str(data.get("approved_at") or "").strip(),
            "rejected_at": str(data.get("rejected_at") or "").strip(),
            "user_notified_at": str(data.get("user_notified_at") or "").strip(),
        }

    def read_heartbeat_upgrade_request(self, workspace: str) -> dict:
        manager = self._manager
        return manager._load_json_store(manager._heartbeat_upgrade_request_path(workspace), lambda: {})

    def write_heartbeat_upgrade_request(self, workspace: str, payload: dict) -> dict:
        manager = self._manager
        normalized = self.normalize_heartbeat_upgrade_request(payload)
        manager._save_json_store(manager._heartbeat_upgrade_request_path(workspace), normalized)
        try:
            manager._file_guardian_upgrade_request(workspace, normalized)
        except Exception as e:
            print(f"[guardian-request] 升级申请备案失败: {e}", flush=True)
        return normalized

    def clear_heartbeat_upgrade_request(self, workspace: str) -> None:
        manager = self._manager
        try:
            manager._heartbeat_upgrade_request_path(workspace).unlink(missing_ok=True)
        except Exception:
            pass

    def format_heartbeat_upgrade_request_message(self, request: dict) -> str:
        request_id = str(request.get("request_id") or "").strip()
        action = str(request.get("action") or "execute_prompt").strip() or "execute_prompt"
        reason = str(request.get("reason") or "").strip()
        summary = str(request.get("summary") or reason or "").strip()
        execute_prompt = str(request.get("execute_prompt") or "").strip()
        maintainer_agent_role = str(request.get("maintainer_agent_role") or "update-agent").strip() or "update-agent"
        target_paths = [str(item).strip() for item in (request.get("target_paths") or []) if str(item).strip()]
        lines = [
            "**心跳升级申请，等待用户批准**",
            "",
            f"申请ID：`{request_id}`",
            f"类型：{'重启主进程' if action == 'restart' else '执行升级方案'}",
            f"维护入口：`{maintainer_agent_role}`",
        ]
        if reason:
            lines.append(f"原因：{reason}")
        if summary:
            lines.append(f"摘要：{summary}")
        if target_paths:
            lines.append(f"目标路径：{', '.join(target_paths[:6])}")
        if execute_prompt:
            lines.extend(["", "计划说明：", execute_prompt[:1200]])
        lines.extend(
            [
                "",
                f"心跳线程没有执行身体目录 {self._body_root_text} 改动/重启的权限。",
                "请直接回复以下任一指令：",
                f"- `批准升级 {request_id}` / `同意按计划执行 {request_id}`",
                f"- `批准重启 {request_id}` / `可以重启 {request_id}`",
                f"- `拒绝升级 {request_id}` / `先别动 {request_id}`",
                f"- `查看升级申请 {request_id}`",
            ]
        )
        return "\n".join(lines).strip()

    def inspect_pending_upgrade_request_prompt(self, workspace: str, user_prompt: str) -> dict | None:
        manager = self._manager
        request = self.read_heartbeat_upgrade_request(workspace)
        if not isinstance(request, dict) or str(request.get("status") or "") != "pending":
            return None

        text = str(user_prompt or "").strip()
        if not text:
            return None
        lowered = text.lower()
        request_id = str(request.get("request_id") or "").strip()
        mentions_request = (request_id and request_id.lower() in lowered) or any(
            hint in text for hint in ("升级", "重启", "按计划", "申请", "方案")
        ) or lowered in {"可以", "同意", "批准", "确认", "行", "好", "ok", "yes"}
        if not mentions_request:
            return None

        if any(hint in text for hint in ("查看升级申请", "看看申请", "什么计划", "查看方案", "看下方案")):
            return {"decision": "view", "request": request, "reply": self.format_heartbeat_upgrade_request_message(request)}

        if any(hint in text for hint in ("拒绝", "取消", "先别", "不要", "不重启", "不执行")):
            self.clear_heartbeat_upgrade_request(workspace)
            manager._clear_restart_markers(workspace)
            return {
                "decision": "reject",
                "request": request,
                "reply": f"已取消心跳升级申请 `{request_id}`。聊天主进程不会执行本次改动或重启。",
            }

        if any(hint in text for hint in ("批准", "同意", "确认", "可以", "执行", "按计划", "重启吧", "可以重启", "批准重启")):
            approved = dict(request)
            approved["status"] = "approved"
            approved["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.write_heartbeat_upgrade_request(workspace, approved)

            action = str(approved.get("action") or "execute_prompt").strip() or "execute_prompt"
            if action == "restart":
                return {
                    "decision": "approve-restart",
                    "request": approved,
                    "reply": f"已收到你对心跳升级申请 `{request_id}` 的批准。聊天主进程将代为执行重启。",
                }

            execute_prompt = str(approved.get("execute_prompt") or "").strip()
            if execute_prompt:
                maintainer_agent_role = str(approved.get("maintainer_agent_role") or "update-agent").strip() or "update-agent"
                return {
                    "decision": "approve-execute",
                    "request": approved,
                    "execute_prompt": (
                        f"【用户已批准心跳升级申请 {request_id}】\n"
                        f"申请原因：{str(approved.get('reason') or '').strip()}\n"
                        f"统一维护入口：请优先按 {maintainer_agent_role} 的维护协议执行以下已批准方案。\n"
                        f"请在主对话进程中执行以下已批准方案：\n{execute_prompt}"
                    ).strip(),
                }
            return {"decision": "view", "request": approved, "reply": self.format_heartbeat_upgrade_request_message(approved)}

        return None

    def execute_approved_upgrade_request(self, workspace: str, request: dict) -> bool:
        manager = self._manager
        action = str((request or {}).get("action") or "").strip() or "execute_prompt"
        if action != "restart":
            return False
        reason = str((request or {}).get("reason") or (request or {}).get("summary") or "心跳升级申请已获批准").strip()
        manager._clear_restart_markers(workspace)
        self.clear_heartbeat_upgrade_request(workspace)
        handoff_request = dict(request or {})
        handoff_request["source"] = "butler"
        handoff_request["status"] = "pending"
        handoff_request["requires_restart"] = True
        handoff_request["reason"] = reason
        handoff_request["summary"] = str(handoff_request.get("summary") or "用户已批准重启申请，移交 guardian 执行").strip()
        manager._file_guardian_upgrade_request(workspace, handoff_request)
        return True

    def govern_memory_write(self, target_path: str, action_type: str, summary: str) -> bool:
        manager = self._manager
        cfg = manager._config_provider() or {}
        features = cfg.get("features") if isinstance(cfg.get("features"), dict) else {}
        if not bool(features.get("governor", False)):
            return True
        decision = self._governor.evaluate(GovernedAction(action_type=action_type, target_path=target_path, summary=summary))
        if not decision.allowed:
            print(f"[governor] 拦截写入: action={action_type} | target={target_path} | rationale={decision.rationale}", flush=True)
        return bool(decision.allowed)
