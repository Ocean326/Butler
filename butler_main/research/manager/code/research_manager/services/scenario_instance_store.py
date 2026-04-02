from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

try:
    from runtime_os.fs_retention import DEFAULT_RETENTION_DAYS, prune_path_children
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from butler_main.runtime_os.fs_retention import DEFAULT_RETENTION_DAYS, prune_path_children

from ..contracts import ResearchInvocation, ResearchUnitSpec
from .scenario_registry import get_research_scenario


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp-{uuid4().hex[:8]}")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


@dataclass(slots=True)
class ResearchScenarioInstance:
    scenario_instance_id: str = field(default_factory=lambda: _new_id("scenario_instance"))
    thread_key: str = ""
    unit_id: str = ""
    scenario_id: str = ""
    workflow_id: str = ""
    status: str = "pending"
    session_id: str = ""
    task_id: str = ""
    workspace: str = ""
    current_step_id: str = ""
    latest_decision: str = ""
    entrypoints_seen: list[str] = field(default_factory=list)
    workflow_cursor: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    active_step: dict[str, Any] = field(default_factory=dict)
    output_template: dict[str, Any] = field(default_factory=dict)
    last_step_receipt: dict[str, Any] = field(default_factory=dict)
    last_handoff_receipt: dict[str, Any] = field(default_factory=dict)
    last_decision_receipt: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = _utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "ResearchScenarioInstance":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


class FileResearchScenarioInstanceStore:
    def __init__(self, root_dir: str | Path | None = None, *, retention_days: int = DEFAULT_RETENTION_DAYS) -> None:
        default_root = Path(__file__).resolve().parents[6] / "butler_main" / "research" / "run" / "scenario_instances"
        self.root_dir = Path(root_dir or default_root).resolve()
        self.retention_days = max(1, int(retention_days or DEFAULT_RETENTION_DAYS))
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root_dir / "index.json"
        prune_path_children(
            self.root_dir,
            retention_days=self.retention_days,
            include_files=False,
            include_dirs=True,
        )
        self._prune_index_entries()

    def bind(self, invocation: ResearchInvocation, unit: ResearchUnitSpec) -> ResearchScenarioInstance | None:
        scenario = get_research_scenario(unit.unit_id)
        if scenario is None:
            return None
        explicit_id = self._resolve_explicit_instance_id(invocation)
        if explicit_id:
            instance = self.load(explicit_id)
            if instance is None:
                instance = self._create_instance(invocation, unit, scenario_id=scenario.scenario_id, workflow_id=scenario.workflow_id, explicit_id=explicit_id)
            return instance
        thread_key = self._build_thread_key(invocation, unit)
        index = self._load_index()
        if thread_key and thread_key in index:
            instance = self.load(index[thread_key])
            if instance is not None:
                return instance
        instance = self._create_instance(invocation, unit, scenario_id=scenario.scenario_id, workflow_id=scenario.workflow_id, thread_key=thread_key)
        if thread_key:
            index[thread_key] = instance.scenario_instance_id
            self._save_index(index)
        return instance

    def load(self, scenario_instance_id: str) -> ResearchScenarioInstance | None:
        instance_id = str(scenario_instance_id or "").strip()
        if not instance_id:
            return None
        payload = _read_json(self.instance_path(instance_id))
        if not payload:
            return None
        return ResearchScenarioInstance.from_dict(payload)

    def save(self, instance: ResearchScenarioInstance) -> ResearchScenarioInstance:
        instance.touch()
        instance_dir = self.instance_root(instance.scenario_instance_id)
        instance_dir.mkdir(parents=True, exist_ok=True)
        _write_text_atomic(self.instance_path(instance.scenario_instance_id), json.dumps(instance.to_dict(), ensure_ascii=False, indent=2))
        return instance

    def apply_dispatch(
        self,
        instance: ResearchScenarioInstance,
        invocation: ResearchInvocation,
        dispatch_payload: Mapping[str, Any] | None,
        *,
        summary: str = "",
    ) -> ResearchScenarioInstance:
        payload = dict(dispatch_payload or {})
        if invocation.session_id:
            instance.session_id = invocation.session_id
        if invocation.task_id:
            instance.task_id = invocation.task_id
        if invocation.workspace:
            instance.workspace = invocation.workspace
        if invocation.entrypoint and invocation.entrypoint not in instance.entrypoints_seen:
            instance.entrypoints_seen.append(invocation.entrypoint)
        instance.workflow_cursor = dict(payload.get("workflow_cursor") or instance.workflow_cursor or {})
        instance.active_step = dict(payload.get("active_step") or instance.active_step or {})
        instance.output_template = dict(payload.get("output_template") or instance.output_template or {})
        instance.last_step_receipt = dict(payload.get("step_receipt") or instance.last_step_receipt or {})
        instance.last_handoff_receipt = dict(payload.get("handoff_receipt") or instance.last_handoff_receipt or {})
        instance.last_decision_receipt = dict(payload.get("decision_receipt") or instance.last_decision_receipt or {})
        instance.current_step_id = str((instance.workflow_cursor.get("current_step_id") or instance.active_step.get("step_id") or instance.current_step_id or "")).strip()
        instance.latest_decision = str((instance.last_decision_receipt.get("decision") or instance.latest_decision or "")).strip()
        instance.status = "active"
        goal_state = {
            "goal": str(invocation.goal or "").strip(),
            "output_format": str((instance.output_template.get("output_format") or "")).strip(),
            "required_fields": [str(item).strip() for item in instance.output_template.get("required_fields") or [] if str(item).strip()],
            "step_output_fields": [str(item).strip() for item in instance.active_step.get("step_output_fields") or [] if str(item).strip()],
            "last_summary": str(summary or "").strip(),
        }
        instance.state.update({key: value for key, value in goal_state.items() if value})
        metadata_patch = {
            "unit_group": payload.get("unit_group"),
            "unit_root": payload.get("unit_root"),
            "scenario_action": (payload.get("metadata") or {}).get("scenario_action") if isinstance(payload.get("metadata"), Mapping) else "",
        }
        instance.metadata.update({str(key): value for key, value in metadata_patch.items() if value not in ("", None, [], {})})
        self.save(instance)
        self.append_event(
            instance.scenario_instance_id,
            kind="scenario_dispatch",
            payload={
                "entrypoint": invocation.entrypoint,
                "goal": invocation.goal,
                "current_step_id": instance.current_step_id,
                "latest_decision": instance.latest_decision,
                "summary": str(summary or "").strip(),
            },
        )
        return instance

    def append_event(self, scenario_instance_id: str, *, kind: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        instance_dir = self.instance_root(scenario_instance_id)
        instance_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "event_id": _new_id("scenario_event"),
            "kind": str(kind or "").strip(),
            "payload": dict(payload or {}),
            "created_at": _utc_now_iso(),
        }
        with (instance_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def instance_root(self, scenario_instance_id: str) -> Path:
        return self.root_dir / str(scenario_instance_id or "").strip()

    def instance_path(self, scenario_instance_id: str) -> Path:
        return self.instance_root(scenario_instance_id) / "instance.json"

    def _create_instance(
        self,
        invocation: ResearchInvocation,
        unit: ResearchUnitSpec,
        *,
        scenario_id: str,
        workflow_id: str,
        thread_key: str = "",
        explicit_id: str = "",
    ) -> ResearchScenarioInstance:
        instance = ResearchScenarioInstance(
            scenario_instance_id=str(explicit_id or "").strip() or _new_id("scenario_instance"),
            thread_key=thread_key,
            unit_id=unit.unit_id,
            scenario_id=scenario_id,
            workflow_id=workflow_id,
            session_id=invocation.session_id,
            task_id=invocation.task_id,
            workspace=invocation.workspace,
            entrypoints_seen=[invocation.entrypoint] if invocation.entrypoint else [],
            metadata={"created_by_entrypoint": invocation.entrypoint},
        )
        self.save(instance)
        self.append_event(
            instance.scenario_instance_id,
            kind="scenario_instance_created",
            payload={
                "unit_id": unit.unit_id,
                "scenario_id": scenario_id,
                "workflow_id": workflow_id,
                "thread_key": thread_key,
            },
        )
        return instance

    def _load_index(self) -> dict[str, str]:
        payload = _read_json(self.index_path)
        result: dict[str, str] = {}
        for key, value in payload.items():
            text_key = str(key or "").strip()
            text_value = str(value or "").strip()
            if text_key and text_value:
                result[text_key] = text_value
        return result

    def _save_index(self, index: Mapping[str, str]) -> None:
        cleaned = {
            str(key or "").strip(): str(value or "").strip()
            for key, value in dict(index or {}).items()
            if str(key or "").strip() and str(value or "").strip()
        }
        _write_text_atomic(self.index_path, json.dumps(cleaned, ensure_ascii=False, indent=2))

    def _prune_index_entries(self) -> None:
        index = self._load_index()
        if not index:
            return
        cleaned = {
            thread_key: instance_id
            for thread_key, instance_id in index.items()
            if self.instance_path(instance_id).exists()
        }
        if cleaned == index:
            return
        self._save_index(cleaned)

    def _resolve_explicit_instance_id(self, invocation: ResearchInvocation) -> str:
        metadata_id = str(invocation.metadata.get("scenario_instance_id") or "").strip()
        if metadata_id:
            return metadata_id
        payload_id = str(invocation.payload.get("scenario_instance_id") or "").strip()
        return payload_id

    def _build_thread_key(self, invocation: ResearchInvocation, unit: ResearchUnitSpec) -> str:
        if invocation.session_id:
            return f"session::{unit.unit_id}::{invocation.session_id}"
        if invocation.task_id:
            return f"task::{unit.unit_id}::{invocation.task_id}"
        if invocation.workspace:
            return f"workspace::{unit.unit_id}::{invocation.workspace}"
        return ""
