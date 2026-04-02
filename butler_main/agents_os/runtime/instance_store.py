from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

try:
    from runtime_os.fs_retention import DEFAULT_RETENTION_DAYS, prune_path_children
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from butler_main.runtime_os.fs_retention import DEFAULT_RETENTION_DAYS, prune_path_children

from .instance import AgentRuntimeInstance, build_instance_roots


INSTANCE_LAYOUT_DIRS: tuple[str, ...] = (
    "session",
    "session/checkpoints",
    "session/overlays",
    "workflow",
    "workflow/checkpoints",
    "context",
    "traces",
    "artifacts",
    "artifacts/drafts",
    "artifacts/handoff",
    "artifacts/published",
    "approvals",
    "approvals/tickets",
    "approvals/decisions",
    "recovery",
    "recovery/directives",
    "recovery/replay",
    "workspace",
    "inbox",
    "outbox",
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp-{uuid4().hex[:8]}")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def _write_json(path: Path, payload: Any) -> None:
    _write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


class FileInstanceStore:
    def __init__(self, root_dir: str | Path | None = None, *, retention_days: int = DEFAULT_RETENTION_DAYS) -> None:
        default_root = Path(__file__).resolve().parents[1] / "run" / "instances"
        self.root_dir = Path(root_dir or default_root).resolve()
        self.retention_days = max(1, int(retention_days or DEFAULT_RETENTION_DAYS))
        self.root_dir.mkdir(parents=True, exist_ok=True)
        prune_path_children(
            self.root_dir,
            retention_days=self.retention_days,
            include_files=False,
            include_dirs=True,
        )

    def instance_root(self, instance_id: str) -> Path:
        return self.root_dir / str(instance_id or "").strip()

    def instance_file(self, instance_id: str) -> Path:
        return self.instance_root(instance_id) / "instance.json"

    def list_instances(self) -> list[AgentRuntimeInstance]:
        result: list[AgentRuntimeInstance] = []
        for path in sorted(self.root_dir.glob("*/instance.json")):
            payload = _read_json(path)
            if payload:
                result.append(AgentRuntimeInstance.from_dict(payload))
        return result

    def create(self, instance: AgentRuntimeInstance | None = None, *, data: Mapping[str, Any] | None = None) -> AgentRuntimeInstance:
        record = instance or AgentRuntimeInstance.from_dict(data)
        record.ensure_roots(self.instance_root(record.instance_id))
        self.save(record)
        return record

    def load(self, instance_id: str) -> AgentRuntimeInstance:
        payload = _read_json(self.instance_file(instance_id))
        if not payload:
            raise FileNotFoundError(f"instance not found: {instance_id}")
        instance = AgentRuntimeInstance.from_dict(payload)
        instance.ensure_roots(self.instance_root(instance.instance_id))
        return instance

    def save(self, instance: AgentRuntimeInstance) -> AgentRuntimeInstance:
        root = self.instance_root(instance.instance_id)
        instance.ensure_roots(root)
        for relative in INSTANCE_LAYOUT_DIRS:
            (root / relative).mkdir(parents=True, exist_ok=True)

        trace_root = Path(instance.roots["trace_root"])
        context_root = Path(instance.roots["context_root"])
        session_root = Path(instance.roots["session_root"])
        workflow_root = Path(instance.roots["workflow_root"])
        artifacts_root = Path(instance.roots["artifact_root"])

        _write_json(root / "instance.json", instance.to_dict())
        _write_json(root / "profile.json", instance.profile_snapshot())
        _write_json(root / "status.json", instance.status_snapshot())
        _write_json(session_root / "session.json", instance.session_snapshot())
        _write_json(workflow_root / "workflow.json", instance.workflow_snapshot())
        _write_json(context_root / "recent_refs.json", {"recent_context_refs": list(instance.recent_context_refs or [])})
        _write_json(context_root / "memory_refs.json", {"memory_refs": list(instance.memory_refs or [])})
        _write_json(context_root / "overlay_refs.json", {"overlay_refs": list(instance.overlay_refs or [])})
        _write_text_atomic(context_root / "working_summary.md", str(instance.working_summary or ""))
        if not Path(instance.trace_path).exists():
            _write_json(Path(instance.trace_path), {})
        if not Path(instance.metrics_path).exists():
            _write_json(Path(instance.metrics_path), {})
        if not (artifacts_root / "manifest.json").exists():
            _write_json(artifacts_root / "manifest.json", {"last_artifact_ids": list(instance.last_artifact_ids or [])})
        if not (trace_root / "events.jsonl").exists():
            (trace_root / "events.jsonl").write_text("", encoding="utf-8")
        return instance

    def update(self, instance_id: str, patch: Mapping[str, Any]) -> AgentRuntimeInstance:
        instance = self.load(instance_id)
        for key, value in dict(patch or {}).items():
            if not hasattr(instance, key):
                continue
            current = getattr(instance, key)
            if isinstance(current, dict) and isinstance(value, Mapping):
                merged = dict(current)
                merged.update(dict(value))
                setattr(instance, key, merged)
            else:
                setattr(instance, key, value)
        instance.updated_at = _utc_now_iso()
        self.save(instance)
        return instance

    def retire(self, instance_id: str) -> AgentRuntimeInstance:
        return self.update(instance_id, {"status": "retired"})

    def append_event(self, instance_id: str, *, kind: str, payload: Mapping[str, Any] | None = None, message: str = "") -> dict[str, Any]:
        instance = self.load(instance_id)
        event = {
            "event_id": f"instance_event_{uuid4().hex[:12]}",
            "kind": str(kind or "").strip(),
            "message": str(message or "").strip(),
            "payload": dict(payload or {}),
            "created_at": _utc_now_iso(),
        }
        event_path = Path(instance.event_stream_path)
        event_path.parent.mkdir(parents=True, exist_ok=True)
        with event_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        _write_json(Path(instance.trace_path), event)
        return event

    def seed_instance_root(self, instance_id: str) -> dict[str, str]:
        root = self.instance_root(instance_id)
        roots = build_instance_roots(root)
        for relative in INSTANCE_LAYOUT_DIRS:
            (root / relative).mkdir(parents=True, exist_ok=True)
        return roots
