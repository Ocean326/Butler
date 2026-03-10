from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
import re
from typing import Callable

from butler_paths import TASK_LEDGER_REL, TASK_WORKSPACES_DIR_REL, resolve_butler_root


class TaskLedgerService:
    def __init__(self, workspace: str, now_factory: Callable[[], datetime] | None = None) -> None:
        self._workspace = workspace
        self._now_factory = now_factory or datetime.now

    @property
    def path(self) -> Path:
        return resolve_butler_root(self._workspace) / TASK_LEDGER_REL

    @property
    def task_workspaces_dir(self) -> Path:
        return resolve_butler_root(self._workspace) / TASK_WORKSPACES_DIR_REL

    def load(self) -> dict:
        path = self.path
        if not path.exists():
            return self._default_payload()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return self._default_payload()

    def save(self, payload: dict) -> dict:
        normalized = dict(payload or {})
        normalized["schema_version"] = 2
        normalized["updated_at"] = self._now_text()
        normalized["items"] = [item for item in normalized.get("items") or [] if isinstance(item, dict)]
        normalized["runs"] = [item for item in normalized.get("runs") or [] if isinstance(item, dict)][-30:]
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
        self._sync_task_workspaces(normalized)
        return normalized

    def ensure_bootstrapped(self, short_tasks: list[dict] | None = None, long_tasks: list[dict] | None = None) -> dict:
        payload = self.load()
        items = [item for item in payload.get("items") or [] if isinstance(item, dict)]
        existing_ids = {str(item.get("task_id") or "").strip() for item in items}

        for raw in short_tasks or []:
            item = self._short_item_from_legacy(raw)
            if not item:
                continue
            task_id = str(item.get("task_id") or "").strip()
            if task_id in existing_ids:
                continue
            items.append(item)
            existing_ids.add(task_id)

        for raw in long_tasks or []:
            item = self._long_item_from_legacy(raw)
            if not item:
                continue
            task_id = str(item.get("task_id") or "").strip()
            if task_id in existing_ids:
                continue
            items.append(item)
            existing_ids.add(task_id)

        payload["items"] = items
        return self.save(payload)

    def apply_heartbeat_result(self, plan: dict, execution_result: str, branch_results: list[dict]) -> dict:
        payload = self.load()
        items = [item for item in payload.get("items") or [] if isinstance(item, dict)]
        now_text = self._now_text()

        complete_ids = set(self._sanitize_ids((plan.get("updates") or {}).get("complete_task_ids")))
        defer_ids = set(self._sanitize_ids(plan.get("deferred_task_ids")))
        defer_ids.update(self._sanitize_ids((plan.get("updates") or {}).get("defer_task_ids")))
        touched_long_ids = set(self._sanitize_ids((plan.get("updates") or {}).get("touch_long_task_ids")))
        successful_branch_ids: list[str] = []

        for branch in branch_results or []:
            branch_id = str(branch.get("branch_id") or "").strip()
            if branch.get("ok"):
                successful_branch_ids.append(branch_id)
                branch_complete_ids = self._sanitize_ids(branch.get("complete_task_ids"))
                if branch_complete_ids:
                    complete_ids.update(branch_complete_ids)
                else:
                    complete_ids.update(self._sanitize_ids(branch.get("selected_task_ids")))
                touched_long_ids.update(self._sanitize_ids(branch.get("touch_long_task_ids")))
            defer_ids.update(self._sanitize_ids(branch.get("defer_task_ids")))

        result_preview = str(execution_result or "").strip()[:200]
        for item in items:
            task_id = str(item.get("task_id") or "").strip()
            task_type = str(item.get("task_type") or "short").strip()
            if not task_id:
                continue
            if task_type == "short":
                if task_id in complete_ids:
                    item["status"] = "done"
                    item["updated_at"] = now_text
                    if result_preview:
                        item["last_result"] = result_preview
                elif task_id in defer_ids and str(item.get("status") or "") != "done":
                    item["status"] = "deferred"
                    item["updated_at"] = now_text
            elif task_type == "long" and task_id in touched_long_ids:
                item["last_run_at"] = now_text
                item["updated_at"] = now_text
                item["next_due_at"] = self._compute_next_due_at(
                    str(item.get("schedule_type") or "").strip(),
                    str(item.get("schedule_value") or "").strip(),
                )
                if result_preview:
                    item["last_result"] = result_preview

        runs = [item for item in payload.get("runs") or [] if isinstance(item, dict)]
        runs.append(
            {
                "run_id": str(plan.get("run_id") or self._now_factory().strftime("%Y%m%d%H%M%S")),
                "applied_at": now_text,
                "chosen_mode": str(plan.get("chosen_mode") or "status").strip(),
                "execution_mode": str(plan.get("execution_mode") or "single").strip(),
                "reason": str(plan.get("reason") or "").strip()[:200],
                "deferred_task_ids": sorted(defer_ids),
                "completed_task_ids": sorted(complete_ids),
                "touched_long_task_ids": sorted(touched_long_ids),
                "successful_branch_ids": successful_branch_ids[:10],
                "execution_result_preview": result_preview,
            }
        )

        payload["items"] = items
        payload["runs"] = runs[-30:]
        saved = self.save(payload)
        self._record_task_workspace_run(saved, plan, execution_result, branch_results)
        return saved

    def render_task_workspaces_context(self, limit: int = 6, recent_note_limit: int = 3) -> str:
        workspace_dir = self.task_workspaces_dir
        if not workspace_dir.exists():
            return ""

        records: list[dict] = []
        for path in sorted(workspace_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(payload, dict):
                records.append(payload)

        active_records = [record for record in records if self._workspace_record_is_active(record)]
        chosen = active_records[:limit] if active_records else records[:limit]
        blocks: list[str] = []
        for record in chosen:
            title = str(record.get("title") or record.get("task_id") or "未命名任务").strip()
            task_id = str(record.get("task_id") or "").strip()
            status = str(record.get("status") or "pending").strip() or "pending"
            task_type = str(record.get("task_type") or "short").strip() or "short"
            summary = str(record.get("working_summary") or record.get("latest_result") or record.get("detail") or "").strip()
            plan_reason = str(record.get("latest_plan_reason") or "").strip()
            notes = record.get("recent_notes") if isinstance(record.get("recent_notes"), list) else []
            lines = [f"### {title}"]
            if task_id:
                lines.append(f"- task_id: {task_id}")
            lines.append(f"- status: {status} | type: {task_type}")
            if summary:
                lines.append(f"- 当前工作状态: {summary[:220]}")
            if plan_reason:
                lines.append(f"- 本轮规划关注点: {plan_reason[:220]}")
            if notes:
                lines.append("- 最近动作:")
                for note in notes[-recent_note_limit:]:
                    if not isinstance(note, dict):
                        continue
                    timestamp = str(note.get("timestamp") or "").strip()
                    phase = str(note.get("phase") or "note").strip() or "note"
                    note_summary = str(note.get("summary") or "").strip()
                    if note_summary:
                        prefix = f"  - [{timestamp}] {phase}: " if timestamp else f"  - {phase}: "
                        lines.append(prefix + note_summary[:220])
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks).strip()

    def export_legacy_payloads(self, payload: dict | None = None) -> tuple[dict, dict]:
        data = payload or self.load()
        short_tasks: list[dict] = []
        long_tasks: list[dict] = []
        for item in data.get("items") or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("task_type") or "") == "long":
                long_tasks.append(
                    {
                        "task_id": str(item.get("task_id") or "").strip(),
                        "kind": str(item.get("kind") or "reminder").strip() or "reminder",
                        "schedule_type": str(item.get("schedule_type") or "daily").strip() or "daily",
                        "schedule_value": str(item.get("schedule_value") or "").strip(),
                        "time_window": str(item.get("time_window") or "").strip(),
                        "timezone": str(item.get("timezone") or "Asia/Shanghai").strip() or "Asia/Shanghai",
                        "enabled": bool(item.get("enabled", True)),
                        "title": str(item.get("title") or "").strip(),
                        "detail": str(item.get("detail") or "").strip(),
                        "created_at": str(item.get("created_at") or "").strip(),
                        "updated_at": str(item.get("updated_at") or "").strip(),
                        "last_run_at": str(item.get("last_run_at") or "").strip(),
                        "next_due_at": str(item.get("next_due_at") or "").strip(),
                        "last_result": str(item.get("last_result") or "").strip()[:200],
                    }
                )
            else:
                short_tasks.append(
                    {
                        "task_id": str(item.get("task_id") or "").strip(),
                        "source": str(item.get("source") or "conversation").strip() or "conversation",
                        "source_memory_id": str(item.get("source_memory_id") or "").strip(),
                        "created_at": str(item.get("created_at") or "").strip(),
                        "updated_at": str(item.get("updated_at") or "").strip(),
                        "status": str(item.get("status") or "pending").strip() or "pending",
                        "priority": str(item.get("priority") or "medium").strip() or "medium",
                        "title": str(item.get("title") or "").strip(),
                        "detail": str(item.get("detail") or "").strip(),
                        "trigger_hint": str(item.get("trigger_hint") or "conversation").strip() or "conversation",
                        "due_at": str(item.get("due_at") or "").strip(),
                        "tags": [str(x).strip() for x in item.get("tags") or [] if str(x).strip()][:6],
                        "last_result": str(item.get("last_result") or "").strip()[:200],
                    }
                )
        return (
            {"version": 1, "updated_at": self._now_text(), "tasks": short_tasks, "notes": []},
            {"version": 1, "updated_at": self._now_text(), "tasks": long_tasks},
        )

    def _default_payload(self) -> dict:
        return {"schema_version": 2, "updated_at": "", "items": [], "runs": []}

    def _task_workspace_file(self, task_id: str) -> Path:
        safe_id = re.sub(r"[^0-9A-Za-z._-]+", "_", str(task_id or "").strip()).strip("._") or "task"
        return self.task_workspaces_dir / f"{safe_id[:80]}.json"

    def _workspace_record_is_active(self, record: dict) -> bool:
        status = str(record.get("status") or "").strip().lower()
        task_type = str(record.get("task_type") or "short").strip().lower()
        if task_type == "long":
            return True
        if status in {"pending", "in_progress", "deferred", "failed"}:
            return True
        notes = record.get("recent_notes") if isinstance(record.get("recent_notes"), list) else []
        return bool(notes)

    def _workspace_status_from_item(self, item: dict) -> str:
        task_type = str(item.get("task_type") or "short").strip().lower()
        if task_type == "long":
            return "active" if bool(item.get("enabled", True)) else "disabled"
        return str(item.get("status") or "pending").strip() or "pending"

    def _build_workspace_record(self, item: dict, current: dict | None = None) -> dict:
        existing = dict(current or {})
        title = str(item.get("title") or item.get("detail") or existing.get("title") or "").strip()
        detail = str(item.get("detail") or existing.get("detail") or title).strip()
        latest_result = str(item.get("last_result") or existing.get("latest_result") or "").strip()[:1000]
        working_summary = str(existing.get("working_summary") or latest_result or detail).strip()[:1000]
        return {
            "schema_version": 1,
            "task_id": str(item.get("task_id") or existing.get("task_id") or "").strip(),
            "task_type": str(item.get("task_type") or existing.get("task_type") or "short").strip() or "short",
            "title": title,
            "detail": detail,
            "status": self._workspace_status_from_item(item),
            "priority": str(item.get("priority") or existing.get("priority") or "").strip(),
            "updated_at": str(item.get("updated_at") or existing.get("updated_at") or self._now_text()).strip(),
            "created_at": str(item.get("created_at") or existing.get("created_at") or self._now_text()).strip(),
            "latest_plan_reason": str(existing.get("latest_plan_reason") or "").strip()[:1000],
            "latest_result": latest_result,
            "working_summary": working_summary,
            "recent_notes": [note for note in existing.get("recent_notes") or [] if isinstance(note, dict)][-10:],
        }

    def _load_task_workspace(self, task_id: str) -> dict:
        path = self._task_workspace_file(task_id)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _save_task_workspace(self, task_id: str, payload: dict) -> None:
        path = self._task_workspace_file(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = dict(payload or {})
        normalized["schema_version"] = 1
        normalized["task_id"] = str(task_id or normalized.get("task_id") or "").strip()
        normalized["recent_notes"] = [note for note in normalized.get("recent_notes") or [] if isinstance(note, dict)][-10:]
        normalized["updated_at"] = str(normalized.get("updated_at") or self._now_text()).strip() or self._now_text()
        path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    def _sync_task_workspaces(self, payload: dict) -> None:
        items = [item for item in payload.get("items") or [] if isinstance(item, dict)]
        if not items:
            return
        self.task_workspaces_dir.mkdir(parents=True, exist_ok=True)
        for item in items:
            task_id = str(item.get("task_id") or "").strip()
            if not task_id:
                continue
            current = self._load_task_workspace(task_id)
            record = self._build_workspace_record(item, current=current)
            self._save_task_workspace(task_id, record)

    def _compact_text(self, text: str, limit: int = 240) -> str:
        compact = re.sub(r"\s+", " ", str(text or "")).strip()
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "…"

    def _record_task_workspace_run(self, payload: dict, plan: dict, execution_result: str, branch_results: list[dict]) -> None:
        items = {str(item.get("task_id") or "").strip(): item for item in payload.get("items") or [] if isinstance(item, dict)}
        if not items:
            return

        complete_ids = set(self._sanitize_ids((plan.get("updates") or {}).get("complete_task_ids")))
        defer_ids = set(self._sanitize_ids(plan.get("deferred_task_ids")))
        defer_ids.update(self._sanitize_ids((plan.get("updates") or {}).get("defer_task_ids")))
        touched_long_ids = set(self._sanitize_ids((plan.get("updates") or {}).get("touch_long_task_ids")))
        selected_ids = set(self._sanitize_ids(plan.get("selected_task_ids")))
        run_id = str(plan.get("run_id") or self._now_factory().strftime("%Y%m%d%H%M%S")).strip()
        plan_reason = self._compact_text(str(plan.get("reason") or plan.get("user_message") or ""), limit=280)
        result_preview = self._compact_text(execution_result, limit=320)
        per_task_notes: dict[str, list[str]] = {}
        failed_task_ids: set[str] = set()

        for branch in branch_results or []:
            if not isinstance(branch, dict):
                continue
            branch_id = str(branch.get("branch_id") or "branch").strip() or "branch"
            branch_targets = set(self._sanitize_ids(branch.get("selected_task_ids")))
            branch_targets.update(self._sanitize_ids(branch.get("complete_task_ids")))
            branch_targets.update(self._sanitize_ids(branch.get("touch_long_task_ids")))
            if not branch_targets:
                continue
            branch_preview = self._compact_text(str(branch.get("output") or branch.get("error") or ""), limit=260)
            if not branch.get("ok"):
                failed_task_ids.update(branch_targets)
            for task_id in branch_targets:
                note = f"{branch_id}: {branch_preview}" if branch_preview else branch_id
                per_task_notes.setdefault(task_id, []).append(note)
                selected_ids.add(task_id)
                complete_ids.update(self._sanitize_ids(branch.get("complete_task_ids")))
                defer_ids.update(self._sanitize_ids(branch.get("defer_task_ids")))
                touched_long_ids.update(self._sanitize_ids(branch.get("touch_long_task_ids")))

        touched_ids = selected_ids | complete_ids | defer_ids | touched_long_ids
        for task_id in touched_ids:
            item = items.get(task_id)
            if not item:
                continue
            current = self._load_task_workspace(task_id)
            record = self._build_workspace_record(item, current=current)
            record["latest_plan_reason"] = plan_reason
            if result_preview:
                record["latest_result"] = result_preview
            phase = "continued"
            summary = plan_reason or result_preview or str(item.get("detail") or item.get("title") or "").strip()
            if task_id in complete_ids:
                phase = "completed"
                summary = f"本轮已完成。{result_preview or summary}".strip()
            elif task_id in defer_ids:
                phase = "deferred"
                defer_reason = str(plan.get("defer_reason") or "").strip()
                summary = f"本轮已延后。{defer_reason or summary}".strip()
            elif task_id in failed_task_ids:
                phase = "failed"
                summary = f"本轮推进失败。{summary}".strip()
            elif task_id in touched_long_ids:
                phase = "long-progress"
                summary = f"本轮推进长期任务。{result_preview or summary}".strip()
            branch_notes = per_task_notes.get(task_id) or []
            if branch_notes:
                summary = self._compact_text(f"{summary} {' | '.join(branch_notes[:2])}", limit=320)
            record["working_summary"] = summary
            notes = [note for note in record.get("recent_notes") or [] if isinstance(note, dict)]
            notes.append(
                {
                    "timestamp": self._now_text(),
                    "run_id": run_id,
                    "phase": phase,
                    "summary": summary,
                    "detail": "\n".join(branch_notes[:3])[:1200],
                }
            )
            record["recent_notes"] = notes[-10:]
            record["updated_at"] = self._now_text()
            self._save_task_workspace(task_id, record)

    def _sanitize_ids(self, values: list | tuple | set | None) -> list[str]:
        items: list[str] = []
        for value in values or []:
            text = str(value or "").strip()
            if text:
                items.append(text)
        return items

    def _short_item_from_legacy(self, raw: dict | None) -> dict | None:
        item = dict(raw or {})
        task_id = str(item.get("task_id") or "").strip()
        title = str(item.get("title") or item.get("detail") or "").strip()
        if not task_id or not title:
            return None
        return {
            "task_id": task_id,
            "task_type": "short",
            "source": str(item.get("source") or "conversation").strip() or "conversation",
            "source_memory_id": str(item.get("source_memory_id") or "").strip(),
            "created_at": str(item.get("created_at") or self._now_text()).strip(),
            "updated_at": str(item.get("updated_at") or self._now_text()).strip(),
            "status": str(item.get("status") or "pending").strip() or "pending",
            "priority": str(item.get("priority") or "medium").strip() or "medium",
            "title": title,
            "detail": str(item.get("detail") or title).strip(),
            "trigger_hint": str(item.get("trigger_hint") or "conversation").strip() or "conversation",
            "due_at": str(item.get("due_at") or "").strip(),
            "tags": [str(x).strip() for x in item.get("tags") or [] if str(x).strip()][:6],
            "last_result": str(item.get("last_result") or "").strip()[:200],
        }

    def _long_item_from_legacy(self, raw: dict | None) -> dict | None:
        item = dict(raw or {})
        task_id = str(item.get("task_id") or "").strip()
        title = str(item.get("title") or item.get("detail") or "").strip()
        if not task_id or not title:
            return None
        return {
            "task_id": task_id,
            "task_type": "long",
            "kind": str(item.get("kind") or "reminder").strip() or "reminder",
            "schedule_type": str(item.get("schedule_type") or "daily").strip() or "daily",
            "schedule_value": str(item.get("schedule_value") or "").strip(),
            "time_window": str(item.get("time_window") or "").strip(),
            "timezone": str(item.get("timezone") or "Asia/Shanghai").strip() or "Asia/Shanghai",
            "enabled": bool(item.get("enabled", True)),
            "title": title,
            "detail": str(item.get("detail") or title).strip(),
            "created_at": str(item.get("created_at") or self._now_text()).strip(),
            "updated_at": str(item.get("updated_at") or self._now_text()).strip(),
            "last_run_at": str(item.get("last_run_at") or "").strip(),
            "next_due_at": str(item.get("next_due_at") or "").strip(),
            "last_result": str(item.get("last_result") or "").strip()[:200],
        }

    def _compute_next_due_at(self, schedule_type: str, schedule_value: str) -> str:
        if schedule_type != "daily" or not schedule_value:
            return ""
        try:
            hour, minute = [int(part) for part in schedule_value.split(":", 1)]
        except Exception:
            return ""
        now = self._now_factory()
        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if due <= now:
            due = due + timedelta(days=1)
        return due.strftime("%Y-%m-%d %H:%M:%S")

    def _now_text(self) -> str:
        return self._now_factory().strftime("%Y-%m-%d %H:%M:%S")
