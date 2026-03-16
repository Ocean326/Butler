from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import shutil
from typing import Callable

from services.acceptance_service import AcceptanceService
from butler_paths import TASK_LEDGER_REL, TASK_WORKSPACES_DIR_REL, resolve_butler_root
from utils.atomic_files import atomic_write_text, backup_path_for, read_text_with_backup


TASK_SCHEMA_VERSION = 4
TASK_WORKSPACE_SCHEMA_VERSION = 3
TASK_WORKSPACE_BUCKETS = ("未进行", "进行中", "已完成")
TASK_STATUS_BUCKETS = {
    "queued": "未进行",
    "triaged": "未进行",
    "planned": "未进行",
    "pending": "未进行",
    "deferred": "未进行",
    "blocked": "未进行",
    "waiting_input": "未进行",
    "in_progress": "进行中",
    "active": "进行中",
    "running": "进行中",
    "reviewing": "进行中",
    "accepted": "已完成",
    "closed": "已完成",
    "done": "已完成",
    "completed": "已完成",
    "archived": "已完成",
    "disabled": "已完成",
}


class TaskLedgerService:
    def __init__(self, workspace: str, now_factory: Callable[[], datetime] | None = None) -> None:
        self._workspace = workspace
        self._now_factory = now_factory or datetime.now
        self._acceptance_service = AcceptanceService()

    @property
    def path(self) -> Path:
        return resolve_butler_root(self._workspace) / TASK_LEDGER_REL

    @property
    def task_workspaces_dir(self) -> Path:
        return resolve_butler_root(self._workspace) / TASK_WORKSPACES_DIR_REL

    def load(self) -> dict:
        if not self.path.exists():
            return self._default_payload()
        try:
            payload = json.loads(read_text_with_backup(self.path, encoding="utf-8"))
        except Exception:
            backup = backup_path_for(self.path)
            if not backup.exists():
                return self._default_payload()
            try:
                payload = json.loads(backup.read_text(encoding="utf-8"))
            except Exception:
                return self._default_payload()
        if not isinstance(payload, dict):
            return self._default_payload()
        payload.setdefault("schema_version", TASK_SCHEMA_VERSION)
        payload.setdefault("updated_at", "")
        payload["items"] = [item for item in payload.get("items") or [] if isinstance(item, dict)]
        payload["runs"] = [item for item in payload.get("runs") or [] if isinstance(item, dict)]
        return payload

    def save(self, payload: dict) -> dict:
        normalized = dict(payload or {})
        normalized["schema_version"] = TASK_SCHEMA_VERSION
        normalized["updated_at"] = self._now_text()
        normalized["items"] = [self._normalize_item(item) for item in normalized.get("items") or [] if isinstance(item, dict)]
        normalized["runs"] = [item for item in normalized.get("runs") or [] if isinstance(item, dict)][-50:]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.path, json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8", keep_backup=True)
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
            if item["task_id"] in existing_ids:
                continue
            items.append(item)
            existing_ids.add(item["task_id"])

        for raw in long_tasks or []:
            item = self._long_item_from_legacy(raw)
            if not item:
                continue
            if item["task_id"] in existing_ids:
                continue
            items.append(item)
            existing_ids.add(item["task_id"])

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
        selected_ids = set(self._sanitize_ids(plan.get("selected_task_ids")))
        successful_branch_ids: list[str] = []
        per_task_branch_notes: dict[str, list[str]] = {}

        for branch in branch_results or []:
            if not isinstance(branch, dict):
                continue
            branch_id = str(branch.get("branch_id") or "branch").strip() or "branch"
            branch_selected_ids = set(self._sanitize_ids(branch.get("selected_task_ids")))
            branch_complete_ids = set(self._sanitize_ids(branch.get("complete_task_ids")))
            branch_defer_ids = set(self._sanitize_ids(branch.get("defer_task_ids")))
            branch_touch_long_ids = set(self._sanitize_ids(branch.get("touch_long_task_ids")))
            branch_targets = set(branch_selected_ids)
            branch_targets.update(branch_complete_ids)
            branch_targets.update(branch_touch_long_ids)
            if branch.get("ok"):
                successful_branch_ids.append(branch_id)
                if branch_complete_ids:
                    complete_ids.update(branch_complete_ids)
                else:
                    complete_ids.update(branch_selected_ids - branch_defer_ids)
                touched_long_ids.update(branch_touch_long_ids)
            defer_ids.update(branch_defer_ids)
            preview = self._compact_text(str(branch.get("output") or branch.get("error") or ""), limit=280)
            for task_id in branch_targets:
                per_task_branch_notes.setdefault(task_id, []).append(f"{branch_id}: {preview}" if preview else branch_id)
                selected_ids.add(task_id)

        result_preview = self._compact_text(execution_result, limit=500)
        for item in items:
            task_id = str(item.get("task_id") or "").strip()
            if not task_id:
                continue
            task_type = str(item.get("task_type") or "short").strip()
            if task_type == "short":
                if task_id in complete_ids:
                    item["status"] = "done"
                    item["completed_at"] = now_text
                    item["updated_at"] = now_text
                    if result_preview:
                        item["last_result"] = result_preview
                elif task_id in defer_ids and str(item.get("status") or "").strip().lower() not in {"done", "accepted", "closed"}:
                    item["status"] = "waiting_input"
                    item["updated_at"] = now_text
                elif task_id in selected_ids:
                    item["status"] = "in_progress"
                    item["updated_at"] = now_text
            elif task_id in touched_long_ids:
                item["status"] = "in_progress"
                item["last_run_at"] = now_text
                item["updated_at"] = now_text
                item["next_due_at"] = self._compute_next_due_at(
                    str(item.get("schedule_type") or "").strip(),
                    str(item.get("schedule_value") or "").strip(),
                )
                if result_preview:
                    item["last_result"] = result_preview
            receipt = self._acceptance_service.build_task_receipt(
                task_id=task_id,
                item=item,
                plan=plan,
                execution_result=execution_result,
                branch_results=branch_results,
                selected_ids=selected_ids,
                complete_ids=complete_ids,
                defer_ids=defer_ids,
                touched_long_ids=touched_long_ids,
            )
            item["program_id"] = receipt.get("program_id") or str(item.get("program_id") or "").strip()
            item["manager_state"] = receipt.get("manager_state") or {}
            item["acceptance_status"] = str(receipt.get("acceptance_status") or item.get("acceptance_status") or "pending").strip() or "pending"
            item["acceptance_summary"] = str(receipt.get("acceptance_summary") or item.get("acceptance_summary") or "").strip()
            item["runtime_profile"] = receipt.get("runtime_profile") or (item.get("runtime_profile") if isinstance(item.get("runtime_profile"), dict) else {})
            item["process_roles"] = [str(x).strip() for x in receipt.get("process_roles") or [] if str(x).strip()][:6]
            item["last_branch_id"] = str(receipt.get("last_branch_id") or item.get("last_branch_id") or "").strip()
            item["last_branch_ids"] = [str(x).strip() for x in receipt.get("branch_ids") or [] if str(x).strip()][:12]

        runs = [item for item in payload.get("runs") or [] if isinstance(item, dict)]
        runs.append(
            {
                "run_id": str(plan.get("run_id") or self._now_factory().strftime("%Y%m%d%H%M%S")),
                "program_id": str(plan.get("program_id") or plan.get("run_id") or "").strip(),
                "applied_at": now_text,
                "chosen_mode": str(plan.get("chosen_mode") or "status").strip(),
                "execution_mode": str(plan.get("execution_mode") or "single").strip(),
                "reason": self._compact_text(str(plan.get("reason") or ""), limit=240),
                "deferred_task_ids": sorted(defer_ids),
                "completed_task_ids": sorted(complete_ids),
                "touched_long_task_ids": sorted(touched_long_ids),
                "successful_branch_ids": successful_branch_ids[:12],
                "execution_result_preview": result_preview,
                "branch_receipts": [
                    {
                        "branch_id": str(branch.get("branch_id") or "").strip(),
                        "process_role": str(branch.get("process_role") or "").strip(),
                        "runtime_profile": branch.get("runtime_profile") if isinstance(branch.get("runtime_profile"), dict) else {},
                        "ok": bool(branch.get("ok")),
                    }
                    for branch in (branch_results or [])[:20]
                    if isinstance(branch, dict)
                ],
            }
        )

        payload["items"] = items
        payload["runs"] = runs[-50:]
        saved = self.save(payload)
        self._record_task_workspace_run(
            saved,
            plan,
            execution_result,
            per_task_branch_notes,
            selected_ids,
            complete_ids,
            defer_ids,
            touched_long_ids,
        )
        return saved

    def render_task_workspaces_context(self, limit: int = 6, recent_note_limit: int = 3) -> str:
        if not self.task_workspaces_dir.exists():
            return ""
        records: list[dict] = []
        for bucket in ("进行中", "未进行", "已完成"):
            bucket_dir = self.task_workspaces_dir / bucket
            if not bucket_dir.exists():
                continue
            for path in sorted(bucket_dir.glob("*/task_meta.json"), key=lambda item: item.stat().st_mtime, reverse=True):
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
            status = str(record.get("status") or "pending").strip() or "pending"
            task_type = str(record.get("task_type") or "short").strip() or "short"
            summary = str(record.get("working_summary") or record.get("latest_result") or record.get("detail") or "").strip()
            lines = [f"### {title}"]
            lines.append(f"- task_id: {str(record.get('task_id') or '').strip()}")
            lines.append(f"- status: {status} | type: {task_type}")
            if record.get("urgency") or record.get("task_scale"):
                lines.append(
                    f"- urgency={str(record.get('urgency') or '').strip() or '(空)'} | scale={str(record.get('task_scale') or '').strip() or '(空)'}"
                )
            if summary:
                lines.append(f"- 当前工作状态: {summary[:220]}")
            plan_reason = str(record.get("latest_plan_reason") or "").strip()
            if plan_reason:
                lines.append(f"- 本轮规划关注点: {plan_reason[:220]}")
            notes = [note for note in record.get("recent_notes") or [] if isinstance(note, dict)]
            if notes:
                lines.append("- 最近动作:")
                for note in notes[-recent_note_limit:]:
                    timestamp = str(note.get("timestamp") or "").strip()
                    phase = str(note.get("phase") or "note").strip() or "note"
                    note_summary = str(note.get("summary") or "").strip()
                    if note_summary:
                        lines.append(f"  - [{timestamp}] {phase}: {note_summary[:220]}")
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
        return {"schema_version": TASK_SCHEMA_VERSION, "updated_at": "", "items": [], "runs": []}

    def _task_slug(self, task_id: str, title: str) -> str:
        safe_id = re.sub(r"[^0-9A-Za-z._-]+", "_", str(task_id or "").strip()).strip("._") or "task"
        safe_title = re.sub(r"[^0-9A-Za-z._\-\u4e00-\u9fff]+", "_", str(title or "").strip()).strip("._")
        safe_title = safe_title[:40] if safe_title else ""
        return f"{safe_id[:48]}_{safe_title}".strip("_") or safe_id[:48]

    def _task_bucket_dir(self, status: str) -> Path:
        raw_status = str(status or "").strip()
        if raw_status in TASK_WORKSPACE_BUCKETS:
            bucket = raw_status
        else:
            bucket = TASK_STATUS_BUCKETS.get(raw_status.lower(), "未进行")
        return self.task_workspaces_dir / bucket

    def _task_workspace_paths(self, task_id: str, title: str, status: str) -> dict[str, Path]:
        base = self._task_bucket_dir(status) / self._task_slug(task_id, title)
        return {
            "base": base,
            "meta": base / "task_meta.json",
            "detail": base / "task_detail.md",
            "progress": base / "progress.md",
            "final": base / "final_report.md",
        }

    def _workspace_record_is_active(self, record: dict) -> bool:
        if str(record.get("task_type") or "short").strip().lower() == "long":
            return True
        status = str(record.get("status") or "").strip().lower()
        return status in {"queued", "triaged", "planned", "pending", "deferred", "blocked", "waiting_input", "in_progress", "active", "running", "reviewing"}

    def _workspace_status_from_item(self, item: dict) -> str:
        task_type = str(item.get("task_type") or "short").strip().lower()
        if task_type == "long":
            if not bool(item.get("enabled", True)):
                return "disabled"
            status = str(item.get("status") or "in_progress").strip() or "in_progress"
            return status if status in {"queued", "triaged", "planned", "pending", "deferred", "blocked", "waiting_input", "in_progress", "active", "running", "reviewing", "accepted", "done"} else "in_progress"
        status = str(item.get("status") or "pending").strip() or "pending"
        return status if status in {"queued", "triaged", "planned", "pending", "deferred", "blocked", "waiting_input", "in_progress", "running", "reviewing", "accepted", "closed", "done"} else "pending"

    def _build_workspace_record(self, item: dict, current: dict | None = None) -> dict:
        current = dict(current or {})
        title = str(item.get("title") or item.get("detail") or current.get("title") or "未命名任务").strip() or "未命名任务"
        detail = str(item.get("detail") or current.get("detail") or title).strip() or title
        latest_result = str(item.get("last_result") or current.get("latest_result") or "").strip()[:1600]
        working_summary = str(current.get("working_summary") or latest_result or detail).strip()[:1200]
        return {
            "schema_version": TASK_WORKSPACE_SCHEMA_VERSION,
            "task_id": str(item.get("task_id") or current.get("task_id") or "").strip(),
            "task_type": str(item.get("task_type") or current.get("task_type") or "short").strip() or "short",
            "title": title,
            "detail": detail,
            "status": self._workspace_status_from_item(item),
            "priority": str(item.get("priority") or current.get("priority") or "").strip(),
            "updated_at": str(item.get("updated_at") or current.get("updated_at") or self._now_text()).strip() or self._now_text(),
            "created_at": str(item.get("created_at") or current.get("created_at") or self._now_text()).strip() or self._now_text(),
            "completed_at": str(item.get("completed_at") or current.get("completed_at") or "").strip(),
            "program_id": str(item.get("program_id") or current.get("program_id") or "").strip(),
            "latest_plan_reason": str(current.get("latest_plan_reason") or "").strip()[:1000],
            "latest_result": latest_result,
            "working_summary": working_summary,
            "acceptance_status": str(item.get("acceptance_status") or current.get("acceptance_status") or "pending").strip() or "pending",
            "acceptance_summary": str(item.get("acceptance_summary") or current.get("acceptance_summary") or "").strip()[:1200],
            "manager_state": dict(item.get("manager_state") or current.get("manager_state") or {}) if isinstance(item.get("manager_state") or current.get("manager_state"), dict) else {},
            "runtime_profile": dict(item.get("runtime_profile") or current.get("runtime_profile") or {}) if isinstance(item.get("runtime_profile") or current.get("runtime_profile"), dict) else {},
            "process_roles": [str(x).strip() for x in (item.get("process_roles") or current.get("process_roles") or []) if str(x).strip()][:6],
            "last_branch_id": str(item.get("last_branch_id") or current.get("last_branch_id") or "").strip(),
            "task_scale": str(item.get("task_scale") or current.get("task_scale") or self._infer_task_scale(item)).strip(),
            "urgency": str(item.get("urgency") or current.get("urgency") or self._infer_urgency(item)).strip(),
            "source_category": str(item.get("source_category") or current.get("source_category") or item.get("source") or "conversation").strip() or "conversation",
            "task_boundary": str(item.get("task_boundary") or current.get("task_boundary") or "").strip(),
            "acceptance_criteria": [str(x).strip() for x in (item.get("acceptance_criteria") or current.get("acceptance_criteria") or []) if str(x).strip()][:8],
            "hard_requirements": [str(x).strip() for x in (item.get("hard_requirements") or current.get("hard_requirements") or []) if str(x).strip()][:10],
            "soft_tags": [str(x).strip() for x in (item.get("soft_tags") or current.get("soft_tags") or item.get("tags") or []) if str(x).strip()][:12],
            "source_refs": [str(x).strip() for x in (item.get("source_refs") or current.get("source_refs") or []) if str(x).strip()][:8],
            "parent_task_id": str(item.get("parent_task_id") or current.get("parent_task_id") or "").strip(),
            "child_task_ids": [str(x).strip() for x in (item.get("child_task_ids") or current.get("child_task_ids") or []) if str(x).strip()][:20],
            "depends_on": [str(x).strip() for x in (item.get("depends_on") or current.get("depends_on") or []) if str(x).strip()][:20],
            "recent_notes": [note for note in current.get("recent_notes") or [] if isinstance(note, dict)][-20:],
        }

    def _load_task_workspace_by_item(self, item: dict) -> tuple[dict, dict[str, Path]]:
        task_id = str(item.get("task_id") or "").strip()
        title = str(item.get("title") or item.get("detail") or task_id).strip() or task_id
        target_paths = self._task_workspace_paths(task_id, title, self._workspace_status_from_item(item))
        for bucket in TASK_WORKSPACE_BUCKETS:
            paths = self._task_workspace_paths(task_id, title, bucket)
            if paths["meta"].exists():
                try:
                    payload = json.loads(paths["meta"].read_text(encoding="utf-8"))
                except Exception:
                    payload = {}
                return (payload if isinstance(payload, dict) else {}), target_paths
        return {}, target_paths

    def _save_task_workspace(self, record: dict, paths: dict[str, Path]) -> None:
        paths["base"].mkdir(parents=True, exist_ok=True)
        normalized = dict(record or {})
        normalized["schema_version"] = TASK_WORKSPACE_SCHEMA_VERSION
        normalized["recent_notes"] = [note for note in normalized.get("recent_notes") or [] if isinstance(note, dict)][-20:]
        atomic_write_text(paths["meta"], json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8", keep_backup=True)
        self._write_workspace_detail_markdown(normalized, paths["detail"])
        self._write_workspace_progress_markdown(normalized, paths["progress"])
        if str(normalized.get("status") or "").strip().lower() in {"done", "completed", "archived", "disabled"}:
            self._write_workspace_final_markdown(normalized, paths["final"])
        self._cleanup_workspace_duplicates(normalized, paths["base"])

    def _cleanup_workspace_duplicates(self, record: dict, keep_base: Path) -> None:
        task_id = str(record.get("task_id") or "").strip()
        title = str(record.get("title") or record.get("detail") or task_id).strip() or task_id
        slug = self._task_slug(task_id, title)
        keep_resolved = keep_base.resolve()
        for bucket in TASK_WORKSPACE_BUCKETS:
            candidate = self._task_bucket_dir(bucket) / slug
            try:
                if candidate.exists() and candidate.resolve() != keep_resolved:
                    shutil.rmtree(candidate, ignore_errors=True)
            except Exception:
                continue

    def _sync_task_workspaces(self, payload: dict) -> None:
        items = [item for item in payload.get("items") or [] if isinstance(item, dict)]
        self.task_workspaces_dir.mkdir(parents=True, exist_ok=True)
        for bucket in TASK_WORKSPACE_BUCKETS:
            bucket_dir = self.task_workspaces_dir / bucket
            bucket_dir.mkdir(parents=True, exist_ok=True)
            readme = bucket_dir / "README.md"
            if not readme.exists():
                atomic_write_text(readme, f"# {bucket}\n\n本目录存放该生命周期阶段的任务工作区。\n", encoding="utf-8")
        for item in items:
            current, paths = self._load_task_workspace_by_item(item)
            record = self._build_workspace_record(item, current=current)
            self._save_task_workspace(record, paths)

    def _record_task_workspace_run(
        self,
        payload: dict,
        plan: dict,
        execution_result: str,
        per_task_branch_notes: dict[str, list[str]],
        selected_ids: set[str],
        complete_ids: set[str],
        defer_ids: set[str],
        touched_long_ids: set[str],
    ) -> None:
        items = {str(item.get("task_id") or "").strip(): item for item in payload.get("items") or [] if isinstance(item, dict)}
        touched_ids = selected_ids | complete_ids | defer_ids | touched_long_ids
        run_id = str(plan.get("run_id") or self._now_factory().strftime("%Y%m%d%H%M%S")).strip()
        plan_reason = self._compact_text(str(plan.get("reason") or plan.get("user_message") or ""), limit=320)
        result_preview = self._compact_text(execution_result, limit=500)

        for task_id in touched_ids:
            item = items.get(task_id)
            if not item:
                continue
            current, paths = self._load_task_workspace_by_item(item)
            record = self._build_workspace_record(item, current=current)
            record["latest_plan_reason"] = plan_reason
            if result_preview:
                record["latest_result"] = result_preview
            record["acceptance_status"] = str(item.get("acceptance_status") or record.get("acceptance_status") or "pending").strip() or "pending"
            record["acceptance_summary"] = str(item.get("acceptance_summary") or record.get("acceptance_summary") or "").strip()[:1200]
            record["manager_state"] = dict(item.get("manager_state") or record.get("manager_state") or {}) if isinstance(item.get("manager_state") or record.get("manager_state"), dict) else {}
            record["runtime_profile"] = dict(item.get("runtime_profile") or record.get("runtime_profile") or {}) if isinstance(item.get("runtime_profile") or record.get("runtime_profile"), dict) else {}
            record["process_roles"] = [str(x).strip() for x in (item.get("process_roles") or record.get("process_roles") or []) if str(x).strip()][:6]
            record["last_branch_id"] = str(item.get("last_branch_id") or record.get("last_branch_id") or "").strip()
            phase = "continued"
            summary = plan_reason or result_preview or str(item.get("detail") or item.get("title") or "").strip()
            if task_id in complete_ids:
                phase = "accepted"
                summary = f"本轮已完成。{result_preview or summary}".strip()
            elif task_id in defer_ids:
                phase = "deferred"
                summary = f"本轮已延后。{summary}".strip()
            elif task_id in touched_long_ids:
                phase = "long-progress"
                summary = f"本轮推进长期任务。{result_preview or summary}".strip()
            branch_notes = per_task_branch_notes.get(task_id) or []
            if branch_notes:
                summary = self._compact_text(f"{summary} {' | '.join(branch_notes[:2])}", limit=420)
            record["working_summary"] = summary
            notes = [note for note in record.get("recent_notes") or [] if isinstance(note, dict)]
            notes.append(
                {
                    "timestamp": self._now_text(),
                    "run_id": run_id,
                    "phase": phase,
                    "summary": summary,
                    "detail": "\n".join(branch_notes[:4])[:1600],
                }
            )
            record["recent_notes"] = notes[-20:]
            record["updated_at"] = self._now_text()
            self._save_task_workspace(record, paths)

    def _write_workspace_detail_markdown(self, record: dict, path: Path) -> None:
        lines = [
            f"# 任务详情 | {str(record.get('title') or record.get('task_id') or '未命名任务').strip()}",
            "",
            "## 任务基本信息",
            "",
            f"- task_id: {str(record.get('task_id') or '').strip()}",
            f"- 状态: {str(record.get('status') or '').strip()}",
            f"- program_id: {str(record.get('program_id') or '').strip() or '(空)'}",
            f"- 类型: {str(record.get('task_type') or '').strip()}",
            f"- 优先级: {str(record.get('priority') or '').strip() or '(空)'}",
            f"- 紧急程度: {str(record.get('urgency') or '').strip() or '(空)'}",
            f"- 任务规模: {str(record.get('task_scale') or '').strip() or '(空)'}",
            f"- 来源分类: {str(record.get('source_category') or '').strip() or '(空)'}",
            f"- 验收状态: {str(record.get('acceptance_status') or '').strip() or '(空)'}",
            f"- 创建时间: {str(record.get('created_at') or '').strip() or '(空)'}",
            f"- 更新时间: {str(record.get('updated_at') or '').strip() or '(空)'}",
            "",
            "## 任务描述",
            "",
            str(record.get("detail") or "(空)").strip() or "(空)",
            "",
            "## 边界与结束标准",
            "",
            f"- 任务边界: {str(record.get('task_boundary') or '').strip() or '(空)'}",
            f"- 验收标准: {self._join_inline_list(record.get('acceptance_criteria')) or '(空)'}",
            f"- 硬性要求: {self._join_inline_list(record.get('hard_requirements')) or '(空)'}",
            f"- 软标签: {self._join_inline_list(record.get('soft_tags')) or '(空)'}",
            f"- 来源引用: {self._join_inline_list(record.get('source_refs')) or '(空)'}",
            f"- 依赖任务: {self._join_inline_list(record.get('depends_on')) or '(空)'}",
            f"- 父任务: {str(record.get('parent_task_id') or '').strip() or '(空)'}",
            f"- 子任务: {self._join_inline_list(record.get('child_task_ids')) or '(空)'}",
            "",
            "## 当前工作摘要",
            "",
            str(record.get("working_summary") or "(空)").strip() or "(空)",
            "",
            "## 规划关注点",
            "",
            str(record.get("latest_plan_reason") or "(空)").strip() or "(空)",
            "",
            "## 经理与运行时回执",
            "",
            f"- 经理决策: {str((record.get('manager_state') or {}).get('decision') or '').strip() or '(空)'}",
            f"- 调度模式: {str((record.get('manager_state') or {}).get('mode') or '').strip() or '(空)'} / {str((record.get('manager_state') or {}).get('execution_mode') or '').strip() or '(空)'}",
            f"- 过程角色: {self._join_inline_list(record.get('process_roles')) or '(空)'}",
            f"- 最近 branch: {str(record.get('last_branch_id') or '').strip() or '(空)'}",
            f"- runtime_profile: {json.dumps(record.get('runtime_profile') or {}, ensure_ascii=False)}",
            "",
        ]
        atomic_write_text(path, "\n".join(lines).rstrip() + "\n", encoding="utf-8", keep_backup=True)

    def _write_workspace_progress_markdown(self, record: dict, path: Path) -> None:
        notes = [note for note in record.get("recent_notes") or [] if isinstance(note, dict)]
        lines = [
            f"# 任务进展 | {str(record.get('title') or record.get('task_id') or '未命名任务').strip()}",
            "",
            "## 最近推进步骤与时间",
            "",
        ]
        if not notes:
            lines.append("- （当前暂无进展记录）")
        else:
            for note in notes[-20:]:
                lines.append(f"- [{str(note.get('timestamp') or '').strip()}] {str(note.get('phase') or 'note').strip() or 'note'}: {str(note.get('summary') or '').strip() or '(空)'}")
                detail = str(note.get("detail") or "").strip()
                if detail:
                    lines.append(f"  细节: {detail[:800]}")
        atomic_write_text(path, "\n".join(lines).rstrip() + "\n", encoding="utf-8", keep_backup=True)

    def _write_workspace_final_markdown(self, record: dict, path: Path) -> None:
        notes = [note for note in record.get("recent_notes") or [] if isinstance(note, dict)]
        lines = [
            f"# 最终完成文档 | {str(record.get('title') or record.get('task_id') or '未命名任务').strip()}",
            "",
            "## 任务基本信息",
            "",
            f"- task_id: {str(record.get('task_id') or '').strip()}",
            f"- 完成时间: {str(record.get('completed_at') or record.get('updated_at') or '').strip() or '(空)'}",
            f"- 类型: {str(record.get('task_type') or '').strip() or '(空)'}",
            f"- 来源分类: {str(record.get('source_category') or '').strip() or '(空)'}",
            f"- 任务规模: {str(record.get('task_scale') or '').strip() or '(空)'}",
            f"- 紧急程度: {str(record.get('urgency') or '').strip() or '(空)'}",
            f"- 验收状态: {str(record.get('acceptance_status') or '').strip() or '(空)'}",
            "",
            "## 完成过程步骤和时间信息",
            "",
        ]
        if not notes:
            lines.append("- （当前暂无过程记录）")
        else:
            for note in notes:
                lines.append(f"- [{str(note.get('timestamp') or '').strip()}] {str(note.get('phase') or 'note').strip() or 'note'}: {str(note.get('summary') or '').strip() or '(空)'}")
        lines.extend(
            [
                "",
                "## 完成详情汇总",
                "",
                str(record.get("latest_result") or record.get("working_summary") or "(空)").strip() or "(空)",
                "",
                "## 验收",
                "",
                f"- 验收标准回顾: {self._join_inline_list(record.get('acceptance_criteria')) or '(空)'}",
                f"- 经理结论: {str((record.get('manager_state') or {}).get('decision') or '').strip() or '(空)'}",
                f"- 验收摘要: {str(record.get('acceptance_summary') or '').strip() or '(空)'}",
                f"- 运行时: {json.dumps(record.get('runtime_profile') or {}, ensure_ascii=False)}",
                f"- 最终结论: {str(record.get('latest_result') or record.get('working_summary') or '(空)').strip() or '(空)'}",
                "",
            ]
        )
        atomic_write_text(path, "\n".join(lines).rstrip() + "\n", encoding="utf-8", keep_backup=True)

    def _join_inline_list(self, values) -> str:
        items = [str(value).strip() for value in (values or []) if str(value).strip()]
        return " / ".join(items[:12])

    def _sanitize_ids(self, values) -> list[str]:
        result: list[str] = []
        for value in values or []:
            text = str(value or "").strip()
            if text:
                result.append(text)
        return result

    def _short_item_from_legacy(self, raw: dict | None) -> dict | None:
        item = dict(raw or {})
        task_id = str(item.get("task_id") or "").strip()
        title = str(item.get("title") or item.get("detail") or "").strip()
        if not task_id or not title:
            return None
        return self._normalize_item(
            {
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
                "tags": [str(x).strip() for x in item.get("tags") or [] if str(x).strip()][:8],
                "last_result": str(item.get("last_result") or "").strip()[:400],
            }
        )

    def _long_item_from_legacy(self, raw: dict | None) -> dict | None:
        item = dict(raw or {})
        task_id = str(item.get("task_id") or "").strip()
        title = str(item.get("title") or item.get("detail") or "").strip()
        if not task_id or not title:
            return None
        return self._normalize_item(
            {
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
                "last_result": str(item.get("last_result") or "").strip()[:400],
            }
        )

    def _normalize_item(self, raw: dict) -> dict:
        item = dict(raw or {})
        task_type = str(item.get("task_type") or "short").strip() or "short"
        now_text = self._now_text()
        normalized = {
            "task_id": str(item.get("task_id") or "").strip(),
            "task_type": task_type,
            "title": str(item.get("title") or item.get("detail") or "未命名任务").strip() or "未命名任务",
            "detail": str(item.get("detail") or item.get("title") or "未命名任务").strip() or "未命名任务",
            "created_at": str(item.get("created_at") or now_text).strip() or now_text,
            "updated_at": str(item.get("updated_at") or now_text).strip() or now_text,
            "completed_at": str(item.get("completed_at") or "").strip(),
            "status": str(item.get("status") or ("in_progress" if task_type == "long" else "pending")).strip() or ("in_progress" if task_type == "long" else "pending"),
            "priority": str(item.get("priority") or ("scheduled" if task_type == "long" else "medium")).strip() or ("scheduled" if task_type == "long" else "medium"),
            "urgency": str(item.get("urgency") or self._infer_urgency(item)).strip(),
            "task_scale": str(item.get("task_scale") or self._infer_task_scale(item)).strip(),
            "task_boundary": str(item.get("task_boundary") or "").strip(),
            "acceptance_criteria": [str(x).strip() for x in item.get("acceptance_criteria") or [] if str(x).strip()][:8],
            "hard_requirements": [str(x).strip() for x in item.get("hard_requirements") or [] if str(x).strip()][:10],
            "soft_tags": [str(x).strip() for x in (item.get("soft_tags") or item.get("tags") or []) if str(x).strip()][:12],
            "source_category": str(item.get("source_category") or item.get("source") or item.get("trigger_hint") or "conversation").strip() or "conversation",
            "source": str(item.get("source") or item.get("trigger_hint") or "conversation").strip() or "conversation",
            "source_memory_id": str(item.get("source_memory_id") or "").strip(),
            "source_refs": [str(x).strip() for x in item.get("source_refs") or [] if str(x).strip()][:8],
            "due_at": str(item.get("due_at") or "").strip(),
            "tags": [str(x).strip() for x in item.get("tags") or [] if str(x).strip()][:8],
            "last_result": str(item.get("last_result") or "").strip()[:400],
            "parent_task_id": str(item.get("parent_task_id") or "").strip(),
            "child_task_ids": [str(x).strip() for x in item.get("child_task_ids") or [] if str(x).strip()][:20],
            "depends_on": [str(x).strip() for x in item.get("depends_on") or [] if str(x).strip()][:20],
            "decomposition_note": str(item.get("decomposition_note") or "").strip(),
            "program_id": str(item.get("program_id") or "").strip(),
            "acceptance_status": str(item.get("acceptance_status") or "pending").strip() or "pending",
            "acceptance_summary": str(item.get("acceptance_summary") or "").strip()[:400],
            "manager_state": dict(item.get("manager_state") or {}) if isinstance(item.get("manager_state"), dict) else {},
            "runtime_profile": dict(item.get("runtime_profile") or {}) if isinstance(item.get("runtime_profile"), dict) else {},
            "process_roles": [str(x).strip() for x in item.get("process_roles") or [] if str(x).strip()][:6],
            "last_branch_id": str(item.get("last_branch_id") or "").strip(),
            "last_branch_ids": [str(x).strip() for x in item.get("last_branch_ids") or [] if str(x).strip()][:12],
        }
        if task_type == "long":
            normalized.update(
                {
                    "kind": str(item.get("kind") or "reminder").strip() or "reminder",
                    "schedule_type": str(item.get("schedule_type") or "daily").strip() or "daily",
                    "schedule_value": str(item.get("schedule_value") or "").strip(),
                    "time_window": str(item.get("time_window") or "").strip(),
                    "timezone": str(item.get("timezone") or "Asia/Shanghai").strip() or "Asia/Shanghai",
                    "enabled": bool(item.get("enabled", True)),
                    "last_run_at": str(item.get("last_run_at") or "").strip(),
                    "next_due_at": str(item.get("next_due_at") or "").strip(),
                }
            )
        else:
            normalized["trigger_hint"] = str(item.get("trigger_hint") or "conversation").strip() or "conversation"
        return normalized

    def _compact_text(self, text: str, limit: int = 240) -> str:
        compact = re.sub(r"\s+", " ", str(text or "")).strip()
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "…"

    def _normalize_time_hint(self, text: str) -> str:
        raw = str(text or "").strip().replace("：", ":").replace("点", ":00")
        matched = re.search(r"(?P<h>\d{1,2})(?::(?P<m>\d{1,2}))?", raw)
        if not matched:
            return ""
        hour = int(matched.group("h"))
        minute = int(matched.group("m") or 0)
        if hour > 23 or minute > 59:
            return ""
        return f"{hour:02d}:{minute:02d}"

    def _compute_next_due_at(self, schedule_type: str, schedule_value: str) -> str:
        if schedule_type != "daily" or not schedule_value:
            return ""
        normalized = self._normalize_time_hint(schedule_value)
        if not normalized:
            return ""
        hour, minute = [int(part) for part in normalized.split(":", 1)]
        now = self._now_factory()
        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if due <= now:
            due = due + timedelta(days=1)
        return due.strftime("%Y-%m-%d %H:%M:%S")

    def _infer_task_scale(self, item: dict) -> str:
        lowered = f"{str(item.get('title') or '')} {str(item.get('detail') or '')}".lower()
        if any(keyword in lowered for keyword in ("重构", "体系", "多阶段", "大任务", "巨型")):
            return "large"
        if any(keyword in lowered for keyword in ("整理", "补充", "检查", "提醒", "记录", "汇总")):
            return "small"
        return "medium"

    def _infer_urgency(self, item: dict) -> str:
        priority = str(item.get("priority") or "").strip().lower()
        if priority in {"high", "urgent", "critical", "scheduled"}:
            return "high"
        if priority in {"low", "later"}:
            return "low"
        if str(item.get("due_at") or item.get("next_due_at") or "").strip():
            return "high"
        return "medium"

    def _now_text(self) -> str:
        return self._now_factory().strftime("%Y-%m-%d %H:%M:%S")

