from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import uuid

from .models import RunTraceSummary


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp-{uuid.uuid4().hex[:8]}")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


class FileTraceStore:
    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def trace_path(self, run_id: str) -> Path:
        return self.root_dir / f"{run_id}.json"

    def summary_path(self, run_id: str) -> Path:
        return self.root_dir / f"{run_id}.summary.json"

    def load(self, run_id: str) -> dict:
        path = self.trace_path(run_id)
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def save(self, run_id: str, payload: dict) -> None:
        _write_text_atomic(self.trace_path(run_id), json.dumps(payload, ensure_ascii=False, indent=2))

    def start_run(self, *, metadata: dict | None = None, parent_run_id: str = "") -> str:
        run_id = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
        payload = {
            "run_id": run_id,
            "parent_run_id": str(parent_run_id or "").strip(),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "metadata": dict(metadata or {}),
            "events": [],
            "progress_counter": 0,
            "selected_task_ids": [],
            "rejected_task_ids": [],
            "fallback_count": 0,
            "retry_count": 0,
            "timeout_count": 0,
            "degrade_count": 0,
        }
        self.save(run_id, payload)
        return run_id

    def append_event(self, run_id: str, *, phase: str, event_type: str, payload: dict | None = None) -> dict:
        trace = self.load(run_id)
        events = trace.get("events") if isinstance(trace.get("events"), list) else []
        events.append(
            {
                "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "phase": str(phase or "").strip() or "unknown",
                "event_type": str(event_type or "").strip() or "event",
                "payload": dict(payload or {}),
            }
        )
        trace["events"] = events
        trace["progress_counter"] = max(0, int(trace.get("progress_counter") or 0)) + 1
        if str(event_type).startswith("fallback"):
            trace["fallback_count"] = max(0, int(trace.get("fallback_count") or 0)) + 1
        if str(event_type).startswith("retry"):
            trace["retry_count"] = max(0, int(trace.get("retry_count") or 0)) + 1
        if str(event_type).startswith("timeout"):
            trace["timeout_count"] = max(0, int(trace.get("timeout_count") or 0)) + 1
        if str(event_type).startswith("degrade"):
            trace["degrade_count"] = max(0, int(trace.get("degrade_count") or 0)) + 1
        self.save(run_id, trace)
        return trace

    def record_tasks(self, run_id: str, *, selected: list[str] | None = None, rejected: list[str] | None = None) -> dict:
        trace = self.load(run_id)
        trace["selected_task_ids"] = [str(item).strip() for item in (selected or []) if str(item).strip()][:20]
        trace["rejected_task_ids"] = [str(item).strip() for item in (rejected or []) if str(item).strip()][:50]
        self.save(run_id, trace)
        return trace

    def summarize(self, run_id: str) -> RunTraceSummary:
        trace = self.load(run_id)
        return RunTraceSummary(
            run_id=run_id,
            selected_task_ids=[str(item).strip() for item in (trace.get("selected_task_ids") or []) if str(item).strip()],
            rejected_task_ids=[str(item).strip() for item in (trace.get("rejected_task_ids") or []) if str(item).strip()],
            fallback_count=max(0, int(trace.get("fallback_count") or 0)),
            retry_count=max(0, int(trace.get("retry_count") or 0)),
            timeout_count=max(0, int(trace.get("timeout_count") or 0)),
            degrade_count=max(0, int(trace.get("degrade_count") or 0)),
            progress_counter=max(0, int(trace.get("progress_counter") or 0)),
        )

    def compact_run(self, run_id: str, *, keep_recent_events: int = 6) -> dict:
        trace = self.load(run_id)
        summary = self.summarize(run_id)
        events = trace.get("events") if isinstance(trace.get("events"), list) else []
        compacted = {
            "run_id": run_id,
            "created_at": trace.get("created_at") or "",
            "selected_task_ids": summary.selected_task_ids,
            "rejected_task_ids": summary.rejected_task_ids,
            "fallback_count": summary.fallback_count,
            "retry_count": summary.retry_count,
            "timeout_count": summary.timeout_count,
            "degrade_count": summary.degrade_count,
            "progress_counter": summary.progress_counter,
            "last_phase": str(events[-1].get("phase") or "").strip() if events else "",
            "last_event_type": str(events[-1].get("event_type") or "").strip() if events else "",
            "event_count_before_compact": len(events),
        }
        _write_text_atomic(self.summary_path(run_id), json.dumps(compacted, ensure_ascii=False, indent=2))
        trace["events"] = events[-max(1, int(keep_recent_events or 1)):]
        trace["compacted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save(run_id, trace)
        compacted["event_count_after_compact"] = len(trace["events"])
        return compacted
