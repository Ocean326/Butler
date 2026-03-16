from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

from butler_paths import resolve_butler_root


class ApprovalRequestService:
    def __init__(
        self,
        manager,
        *,
        schema_version: int,
        guardian_requests_dir_rel: str,
    ) -> None:
        self._manager = manager
        self._schema_version = int(schema_version)
        self._guardian_requests_dir_rel = str(guardian_requests_dir_rel)

    def guardian_requests_dir(self, workspace: str) -> Path:
        root = resolve_butler_root(workspace or os.getcwd())
        return root / self._guardian_requests_dir_rel

    def guardian_request_file_path(self, workspace: str, request_id: str) -> Path:
        request_dir = self.guardian_requests_dir(workspace)
        request_dir.mkdir(parents=True, exist_ok=True)
        safe_request_id = re.sub(r"[^0-9A-Za-z._-]+", "-", str(request_id or uuid.uuid4()).strip())
        existing = sorted(request_dir.glob(f"*_{safe_request_id}.json"))
        if existing:
            return existing[-1]
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return request_dir / f"{stamp}_{safe_request_id}.json"

    def save_guardian_request(self, workspace: str, payload: dict) -> dict:
        data = dict(payload or {})
        request_id = str(data.get("request_id") or uuid.uuid4()).strip() or str(uuid.uuid4())
        data["schema_version"] = self._schema_version
        data["request_id"] = request_id
        data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        path = self.guardian_request_file_path(workspace, request_id)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    def file_guardian_record_only_request(
        self,
        workspace: str,
        *,
        source: str,
        title: str,
        reason: str,
        planned_actions: list[str] | None = None,
        verification: list[str] | None = None,
        rollback: list[str] | None = None,
        scope_files: list[str] | None = None,
        scope_modules: list[str] | None = None,
        scope_runtime_objects: list[str] | None = None,
        execution_notes: list[str] | None = None,
    ) -> dict:
        payload = {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": str(source or "heartbeat").strip() or "heartbeat",
            "request_type": "record-only",
            "title": str(title or "heartbeat 轻量修复备案").strip() or "heartbeat 轻量修复备案",
            "reason": str(reason or "heartbeat 执行了轻量修复动作").strip() or "heartbeat 执行了轻量修复动作",
            "scope": {
                "files": [str(x) for x in (scope_files or []) if str(x or "").strip()],
                "modules": [str(x) for x in (scope_modules or []) if str(x or "").strip()],
                "runtime_objects": [str(x) for x in (scope_runtime_objects or []) if str(x or "").strip()],
            },
            "planned_actions": [str(x) for x in (planned_actions or []) if str(x or "").strip()],
            "requires_code_change": False,
            "requires_restart": False,
            "verification": [str(x) for x in (verification or []) if str(x or "").strip()],
            "rollback": [str(x) for x in (rollback or []) if str(x or "").strip()],
            "risk_level": "low",
            "review_status": "pending",
            "review_notes": [],
            "execution_notes": [str(x) for x in (execution_notes or []) if str(x or "").strip()],
            "requested_tests": [],
            "patch_plan": None,
        }
        return self.save_guardian_request(workspace, payload)

    def file_guardian_upgrade_request(self, workspace: str, request: dict) -> dict:
        manager = self._manager
        normalized = manager._normalize_heartbeat_upgrade_request(request)
        execute_prompt = str(normalized.get("execute_prompt") or "").strip()
        payload = {
            "request_id": str(normalized.get("request_id") or uuid.uuid4()).strip() or str(uuid.uuid4()),
            "created_at": str(normalized.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")).strip(),
            "source": str(normalized.get("source") or "heartbeat").strip() or "heartbeat",
            "request_type": "restart" if bool(normalized.get("requires_restart")) else "code-fix",
            "title": "heartbeat 升级申请",
            "reason": str(normalized.get("reason") or "heartbeat 提出升级申请").strip() or "heartbeat 提出升级申请",
            "scope": {
                "files": [],
                "modules": ["memory_manager", "heartbeat_orchestration"],
                "runtime_objects": ["heartbeat", "upgrade-request"],
            },
            "planned_actions": [execute_prompt] if execute_prompt else [str(normalized.get("summary") or normalized.get("reason") or "执行升级方案").strip()],
            "requires_code_change": True,
            "requires_restart": bool(normalized.get("requires_restart")),
            "verification": ["guardian 审阅通过后执行升级方案", "执行后按改动范围运行动态测试"],
            "rollback": ["若升级失败则回滚本次代码或配置变更", "若上线失败则恢复到升级前运行状态"],
            "risk_level": "high" if bool(normalized.get("requires_restart")) else "medium",
            "review_status": str(normalized.get("status") or "pending").strip() or "pending",
            "review_notes": [],
            "execution_notes": [str(normalized.get("summary") or "").strip()] if str(normalized.get("summary") or "").strip() else [],
            "requested_tests": [],
            "patch_plan": {
                "required": True,
                "status": "pending",
                "summary": "guardian 执行代码修改前必须先生成 patch 预案",
            },
        }
        return self.save_guardian_request(workspace, payload)
