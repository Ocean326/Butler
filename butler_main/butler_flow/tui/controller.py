from __future__ import annotations

import argparse
import io
import json
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from butler_main.butler_flow.app import FlowApp
from butler_main.butler_flow.display import EventFlowDisplay
from butler_main.butler_flow.events import FlowLifecycleHook, FlowUiEvent, FlowUiEventCallback
from butler_main.butler_flow.models import PreparedFlowRun
from butler_main.butler_flow.surface import build_flow_summary, latest_handoff_summary
from butler_main.butler_flow.state import (
    append_jsonl,
    flow_actions_path,
    flow_artifacts_path,
    flow_events_path,
    flow_turns_path,
    handoffs_path,
    now_text,
    read_json,
    resolve_flow_dir,
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = str(line or "").strip()
        if not text:
            continue
        try:
            decoded = json.loads(text)
        except Exception:
            decoded = {}
        if isinstance(decoded, dict):
            rows.append(decoded)
    return rows


@dataclass(slots=True)
class SlashCommand:
    name: str
    args: list[str]
    raw: str


@dataclass(frozen=True, slots=True)
class CommandSpec:
    name: str
    usage: str
    summary: str
    aliases: tuple[str, ...] = ()
    requires_flow: bool = False
    action_type: str = ""
    allowed_statuses: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CommandAvailability:
    enabled: bool
    reason: str = ""
    flow_id: str = ""
    status: str = ""
    phase: str = ""


COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(name="help", usage="/help", summary="Show the command catalog."),
    CommandSpec(name="history", usage="/history", summary="Legacy alias for the workspace runtime browser."),
    CommandSpec(name="flows", usage="/flows", summary="Legacy alias for /manage; shows a migration hint."),
    CommandSpec(name="settings", usage="/settings", summary="Open the TUI settings screen."),
    CommandSpec(name="back", usage="/back", summary="Return to the workspace browser."),
    CommandSpec(name="list", usage="/list", summary="Open the shared flow asset center."),
    CommandSpec(name="preflight", usage="/preflight", summary="Show runtime paths and provider availability."),
    CommandSpec(name="focus", usage="/focus <flow_id>", summary="Switch focus to an existing flow."),
    CommandSpec(name="manage", usage="/manage [asset|instruction]", summary="Open the shared asset center or mutate a builtin/template asset."),
    CommandSpec(name="status", usage="/status [flow_id]", summary="Show a flow status payload.", requires_flow=True),
    CommandSpec(name="inspect", usage="/inspect [flow_id]", summary="Focus a flow and refresh the single-flow view.", requires_flow=True),
    CommandSpec(name="artifacts", usage="/artifacts [flow_id]", summary="Show registered artifacts for a flow.", requires_flow=True),
    CommandSpec(name="new", usage="/new", summary="Open the setup picker for a new flow."),
    CommandSpec(name="resume", usage="/resume [flow_id|last]", summary="Resume or attach to a persisted flow."),
    CommandSpec(name="follow", usage="/follow [on|off]", summary="Toggle transcript auto-follow."),
    CommandSpec(name="filter", usage="/filter <all|assistant|system|judge|operator|supervisor>", summary="Set transcript display filter."),
    CommandSpec(name="runtime-events", usage="/runtime-events [on|off]", summary="Toggle runtime event visibility."),
    CommandSpec(
        name="pause",
        usage="/pause",
        summary="Request a pause at the next safe boundary.",
        requires_flow=True,
        action_type="pause",
        allowed_statuses=("running",),
    ),
    CommandSpec(
        name="append",
        usage="/append <text>",
        summary="Queue an instruction for the next supervisor turn.",
        requires_flow=True,
        action_type="append_instruction",
        allowed_statuses=("running", "paused"),
    ),
    CommandSpec(
        name="resume-flow",
        usage="/resume-flow",
        summary="Resume a paused flow.",
        aliases=("resume-run",),
        requires_flow=True,
        action_type="resume",
        allowed_statuses=("paused",),
    ),
    CommandSpec(
        name="retry",
        usage="/retry",
        summary="Retry the current phase from a paused flow.",
        aliases=("retry-phase",),
        requires_flow=True,
        action_type="retry_current_phase",
        allowed_statuses=("paused",),
    ),
    CommandSpec(
        name="abort",
        usage="/abort",
        summary="Fail the flow immediately.",
        requires_flow=True,
        action_type="abort",
        allowed_statuses=("running", "paused"),
    ),
)


_COMMAND_BY_NAME = {spec.name: spec for spec in COMMAND_SPECS}
_COMMAND_BY_ALIAS = {alias: spec.name for spec in COMMAND_SPECS for alias in spec.aliases}
_OPERATOR_COMMANDS = tuple(spec.name for spec in COMMAND_SPECS if spec.action_type)
_SILENT_ALIAS_COMMANDS = {"history", "flows"}
_TIMELINE_KIND_ORDER = {
    "run_started": 10,
    "supervisor_input": 15,
    "supervisor_output": 18,
    "supervisor_decided": 20,
    "supervisor_decision_applied": 21,
    "operator_action_applied": 30,
    "codex_segment": 40,
    "codex_runtime_event": 50,
    "judge_result": 60,
    "approval_state_changed": 65,
    "artifact_registered": 70,
    "role_handoff_created": 72,
    "role_handoff_consumed": 73,
    "manage_handoff_ready": 74,
    "phase_transition": 80,
    "run_completed": 90,
    "run_failed": 90,
    "run_interrupted": 90,
}
_LANE_BY_KIND = {
    "supervisor_input": "supervisor",
    "supervisor_output": "supervisor",
    "supervisor_decided": "supervisor",
    "supervisor_decision_applied": "supervisor",
    "judge_result": "supervisor",
    "approval_state_changed": "supervisor",
    "operator_action_applied": "supervisor",
    "manage_handoff_ready": "supervisor",
    "role_handoff_created": "workflow",
    "role_handoff_consumed": "workflow",
    "artifact_registered": "workflow",
    "phase_transition": "workflow",
    "codex_segment": "workflow",
    "codex_runtime_event": "workflow",
    "run_started": "system",
    "run_completed": "system",
    "run_failed": "system",
    "run_interrupted": "system",
}
_FAMILY_BY_KIND = {
    "supervisor_input": "input",
    "supervisor_output": "output",
    "supervisor_decided": "decision",
    "supervisor_decision_applied": "decision",
    "judge_result": "decision",
    "approval_state_changed": "approval",
    "operator_action_applied": "action",
    "manage_handoff_ready": "handoff",
    "role_handoff_created": "handoff",
    "role_handoff_consumed": "handoff",
    "artifact_registered": "artifact",
    "phase_transition": "phase",
    "codex_segment": "raw_execution",
    "codex_runtime_event": "raw_execution",
    "run_started": "run",
    "run_completed": "run",
    "run_failed": "run",
    "run_interrupted": "run",
    "warning": "risk",
    "error": "error",
}


class FlowTuiController:
    def __init__(
        self,
        *,
        run_prompt_receipt_fn: Callable[..., Any],
        event_callback: FlowUiEventCallback,
        hook_callback: FlowLifecycleHook | None = None,
    ) -> None:
        self._run_prompt_receipt_fn = run_prompt_receipt_fn
        self._event_callback = event_callback
        self._hook_callback = hook_callback

    def _canonical_command_name(self, name: str) -> str:
        token = str(name or "").strip().lower()
        if not token:
            return ""
        return _COMMAND_BY_ALIAS.get(token, token)

    def command_spec(self, name: str) -> CommandSpec:
        canonical = self._canonical_command_name(name)
        spec = _COMMAND_BY_NAME.get(canonical)
        if spec is None:
            raise KeyError(f"unknown command: {name}")
        return spec

    def command_catalog(self) -> tuple[CommandSpec, ...]:
        return COMMAND_SPECS

    def command_suggestions(self) -> tuple[str, ...]:
        suggestions: list[str] = []
        seen: set[str] = set()

        def _add(value: str) -> None:
            text = str(value or "").strip()
            if not text or text in seen:
                return
            seen.add(text)
            suggestions.append(text)

        for spec in self.command_catalog():
            if spec.name in _SILENT_ALIAS_COMMANDS:
                continue
            command_token = spec.usage.split(" ", 1)[0]
            _add(command_token)
            _add(spec.usage)
            for alias in spec.aliases:
                alias_token = str(alias or "").strip()
                if not alias_token:
                    continue
                _add(f"/{alias_token}")

        return tuple(suggestions)

    def _normalize_status(self, status: str) -> str:
        token = str(status or "").strip().lower()
        if token in {"done", "complete"}:
            return "completed"
        return token

    def _infer_lane(self, entry: dict[str, Any]) -> str:
        explicit = str(entry.get("lane") or "").strip().lower()
        if explicit:
            return explicit
        kind = str(entry.get("kind") or "").strip()
        lane = _LANE_BY_KIND.get(kind)
        if lane:
            return lane
        payload = dict(entry.get("payload") or {})
        if kind in {"warning", "error"}:
            if any(key in payload for key in ("approval_state", "latest_supervisor_decision", "latest_operator_action")):
                return "supervisor"
        return "system"

    def _infer_family(self, entry: dict[str, Any]) -> str:
        explicit = str(entry.get("family") or "").strip().lower()
        if explicit:
            return explicit
        kind = str(entry.get("kind") or "").strip()
        family = _FAMILY_BY_KIND.get(kind)
        if family:
            return family
        payload = dict(entry.get("payload") or {})
        if "handoff_id" in payload or "from_role_id" in payload or "to_role_id" in payload:
            return "handoff"
        if "artifact_ref" in payload:
            return "artifact"
        if "decision" in payload:
            return "decision"
        return "system"

    def _normalize_event(self, entry: dict[str, Any]) -> dict[str, Any]:
        row = dict(entry or {})
        row["lane"] = self._infer_lane(row)
        row["family"] = self._infer_family(row)
        if row.get("lane") == "supervisor" and str(row.get("kind") or "").strip() == "codex_segment":
            row["family"] = "output"
        if "title" not in row or not str(row.get("title") or "").strip():
            row["title"] = str(row.get("message") or row.get("kind") or "").strip()
        if "raw_text" not in row or row.get("raw_text") is None:
            row["raw_text"] = ""
        return row

    def _read_optional_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _read_optional_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return _read_jsonl(path)

    def _format_supervisor_output(self, decision: dict[str, Any]) -> str:
        payload = dict(decision or {})
        if not payload:
            return ""

        def _add(parts: list[str], label: str, value: Any) -> None:
            token = str(value or "").strip()
            if token:
                parts.append(f"{label}={token}")

        parts: list[str] = []
        _add(parts, "decision", payload.get("decision"))
        _add(parts, "next_action", payload.get("next_action"))
        _add(parts, "turn_kind", payload.get("turn_kind"))
        _add(parts, "active_role", payload.get("active_role_id"))
        _add(parts, "session_mode", payload.get("session_mode"))
        _add(parts, "load_profile", payload.get("load_profile"))
        issue_kind = str(payload.get("issue_kind") or "").strip()
        if issue_kind and issue_kind != "none":
            parts.append(f"issue={issue_kind}")
        followup_kind = str(payload.get("followup_kind") or "").strip()
        if followup_kind and followup_kind != "none":
            parts.append(f"followup={followup_kind}")
        confidence = payload.get("confidence")
        if confidence is not None:
            try:
                parts.append(f"confidence={float(confidence):.2f}")
            except (TypeError, ValueError):
                _add(parts, "confidence", confidence)

        return " | ".join(parts) if parts else json.dumps(payload, ensure_ascii=False)

    def _timeline_event(
        self,
        *,
        flow_id: str,
        kind: str,
        created_at: str,
        phase: str = "",
        attempt_no: int = 0,
        message: str = "",
        payload: dict[str, Any] | None = None,
        event_id: str = "",
    ) -> dict[str, Any]:
        return {
            "event_id": str(event_id or f"flow_timeline_evt_{uuid4().hex[:12]}").strip(),
            "kind": str(kind or "").strip(),
            "flow_id": str(flow_id or "").strip(),
            "phase": str(phase or "").strip(),
            "attempt_no": int(attempt_no or 0),
            "created_at": str(created_at or now_text()).strip(),
            "message": str(message or ""),
            "payload": dict(payload or {}),
        }

    def _timeline_key(self, entry: dict[str, Any]) -> str:
        event_id = str(entry.get("event_id") or "").strip()
        if event_id:
            return f"id:{event_id}"
        return "|".join(
            [
                str(entry.get("kind") or "").strip(),
                str(entry.get("created_at") or "").strip(),
                str(entry.get("message") or "").strip(),
                str(entry.get("phase") or "").strip(),
                str(entry.get("attempt_no") or "").strip(),
            ]
        )

    def _merge_timeline(self, primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for source in (primary, secondary):
            for entry in source:
                row = dict(entry or {})
                key = self._timeline_key(row)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(row)
        merged.sort(
            key=lambda item: (
                str(item.get("created_at") or ""),
                int(item.get("attempt_no") or 0),
                _TIMELINE_KIND_ORDER.get(str(item.get("kind") or "").strip(), 999),
                str(item.get("event_id") or ""),
            )
        )
        return merged

    def _synthesized_timeline(self, *, flow_id: str, status_payload: dict[str, Any]) -> list[dict[str, Any]]:
        status = dict(status_payload.get("status") or {})
        flow_state = dict(status.get("flow_state") or {})
        turns = list(status_payload.get("turns") or [])
        actions = list(status_payload.get("actions") or [])
        artifacts = list(status_payload.get("artifacts") or [])
        handoffs = list(status_payload.get("handoffs") or [])
        timeline: list[dict[str, Any]] = []

        if turns:
            first_turn = dict(turns[0] or {})
            timeline.append(
                self._timeline_event(
                    flow_id=flow_id,
                    kind="run_started",
                    created_at=str(first_turn.get("started_at") or flow_state.get("created_at") or now_text()).strip(),
                    phase=str(first_turn.get("phase") or flow_state.get("current_phase") or "").strip(),
                    attempt_no=int(first_turn.get("attempt_no") or 0),
                    message="flow run started",
                    payload={"turn_id": str(first_turn.get("turn_id") or "").strip(), "synthetic": True},
                )
            )
        for turn in turns:
            row = dict(turn or {})
            phase = str(row.get("phase") or "").strip()
            attempt_no = int(row.get("attempt_no") or 0)
            supervisor = dict(row.get("supervisor_decision") or {})
            instruction = str(supervisor.get("instruction") or "").strip()
            if instruction:
                timeline.append(
                    self._timeline_event(
                        flow_id=flow_id,
                        kind="supervisor_input",
                        created_at=str(row.get("started_at") or flow_state.get("updated_at") or now_text()).strip(),
                        phase=phase,
                        attempt_no=attempt_no,
                        message=instruction,
                        payload={"instruction": instruction, "decision": supervisor, "synthetic": True},
                    )
                )
            output_summary = self._format_supervisor_output(supervisor)
            if output_summary:
                timeline.append(
                    self._timeline_event(
                        flow_id=flow_id,
                        kind="supervisor_output",
                        created_at=str(row.get("started_at") or flow_state.get("updated_at") or now_text()).strip(),
                        phase=phase,
                        attempt_no=attempt_no,
                        message=output_summary,
                        payload={"summary": output_summary, "decision": supervisor, "synthetic": True},
                    )
                )
            if supervisor:
                timeline.append(
                    self._timeline_event(
                        flow_id=flow_id,
                        kind="supervisor_decided",
                        created_at=str(row.get("started_at") or flow_state.get("updated_at") or now_text()).strip(),
                        phase=phase,
                        attempt_no=attempt_no,
                        message=str(supervisor.get("reason") or "").strip(),
                        payload={**supervisor, "synthetic": True},
                    )
                )
            decision = str(row.get("decision") or "").strip()
            if decision:
                timeline.append(
                    self._timeline_event(
                        flow_id=flow_id,
                        kind="judge_result",
                        created_at=str(row.get("completed_at") or row.get("started_at") or now_text()).strip(),
                        phase=phase,
                        attempt_no=attempt_no,
                        message=decision,
                        payload={
                            "decision": {
                                "decision": decision,
                                "reason": str(row.get("reason") or "").strip(),
                            },
                            "synthetic": True,
                        },
                    )
                )
        for action in actions:
            row = dict(action or {})
            timeline.append(
                self._timeline_event(
                    flow_id=flow_id,
                    kind="operator_action_applied",
                    created_at=str(row.get("created_at") or flow_state.get("updated_at") or now_text()).strip(),
                    phase=str((row.get("after_state") or {}).get("current_phase") or flow_state.get("current_phase") or "").strip(),
                    attempt_no=int(flow_state.get("attempt_count") or 0),
                    message=str(row.get("result_summary") or row.get("action_type") or "").strip(),
                    payload={**row, "synthetic": True},
                )
            )
        for artifact in artifacts:
            row = dict(artifact or {})
            timeline.append(
                self._timeline_event(
                    flow_id=flow_id,
                    kind="artifact_registered",
                    created_at=str(row.get("created_at") or flow_state.get("updated_at") or now_text()).strip(),
                    phase=str(row.get("phase") or flow_state.get("current_phase") or "").strip(),
                    attempt_no=int(row.get("attempt_no") or 0),
                    message=str(row.get("artifact_ref") or "").strip(),
                    payload={**row, "synthetic": True},
                )
            )
        for handoff in handoffs:
            row = dict(handoff or {})
            status_value = str(row.get("status") or "").strip()
            created_at = str(row.get("created_at") or now_text()).strip()
            kind = "role_handoff_created"
            if status_value == "consumed" and str(row.get("consumed_at") or "").strip():
                kind = "role_handoff_consumed"
                created_at = str(row.get("consumed_at") or created_at).strip()
            timeline.append(
                self._timeline_event(
                    flow_id=flow_id,
                    kind=kind,
                    created_at=created_at,
                    phase=str(row.get("target_phase") or row.get("source_phase") or flow_state.get("current_phase") or "").strip(),
                    attempt_no=int(flow_state.get("attempt_count") or 0),
                    message=str(row.get("summary") or row.get("next_action") or "").strip(),
                    payload={**row, "synthetic": True},
                )
            )

        final_status = self._normalize_status(status.get("effective_status") or flow_state.get("status") or "")
        final_message = str(flow_state.get("last_completion_summary") or "").strip()
        if final_status in {"completed", "failed", "interrupted"}:
            final_kind = {
                "completed": "run_completed",
                "failed": "run_failed",
                "interrupted": "run_interrupted",
            }[final_status]
            timeline.append(
                self._timeline_event(
                    flow_id=flow_id,
                    kind=final_kind,
                    created_at=str(flow_state.get("updated_at") or now_text()).strip(),
                    phase=str(status.get("effective_phase") or flow_state.get("current_phase") or "").strip(),
                    attempt_no=int(flow_state.get("attempt_count") or 0),
                    message=final_message or final_status,
                    payload={"synthetic": True},
                )
            )

        return self._merge_timeline(timeline, [])

    def timeline_payload(self, *, config: str | None, flow_id: str) -> list[dict[str, Any]]:
        status_payload = self.inspect_payload(config=config, flow_id=flow_id)
        flow_path = Path(status_payload["status"]["flow_dir"])
        events_path = flow_events_path(flow_path)
        events = _read_jsonl(events_path)
        synthesized = self._synthesized_timeline(flow_id=flow_id, status_payload=status_payload)
        unified = self._merge_timeline(events, synthesized)
        if synthesized and (not events_path.exists() or not events_path.read_text(encoding="utf-8").strip()):
            for row in synthesized:
                append_jsonl(events_path, row)
        return [self._normalize_event(row) for row in unified]

    def flow_context(self, *, config: str | None, flow_id: str) -> CommandAvailability:
        target = str(flow_id or "").strip()
        if not target:
            return CommandAvailability(enabled=False, reason="No flow selected.")
        try:
            payload = self.status_payload(config=config, flow_id=target)
        except Exception as exc:
            return CommandAvailability(enabled=False, reason=f"flow lookup failed: {type(exc).__name__}: {exc}", flow_id=target)
        flow_state = dict(payload.get("flow_state") or {})
        effective_status = self._normalize_status(payload.get("effective_status") or flow_state.get("status") or "")
        return CommandAvailability(
            enabled=True,
            flow_id=target,
            status=effective_status,
            phase=str(payload.get("effective_phase") or flow_state.get("current_phase") or "").strip(),
        )

    def command_availability(self, *, config: str | None, flow_id: str, command_name: str) -> CommandAvailability:
        spec = self.command_spec(command_name)
        if not spec.requires_flow:
            return CommandAvailability(enabled=True)
        context = self.flow_context(config=config, flow_id=flow_id)
        if not context.enabled:
            return context
        if spec.allowed_statuses and context.status not in spec.allowed_statuses:
            allowed = ", ".join(spec.allowed_statuses)
            return CommandAvailability(
                enabled=False,
                reason=f"/{spec.name} unavailable when flow status={context.status or 'unknown'}; allowed={allowed}",
                flow_id=context.flow_id,
                status=context.status,
                phase=context.phase,
            )
        return context

    def available_operator_commands(self, *, config: str | None, flow_id: str) -> list[CommandSpec]:
        available: list[CommandSpec] = []
        for name in _OPERATOR_COMMANDS:
            state = self.command_availability(config=config, flow_id=flow_id, command_name=name)
            if state.enabled:
                available.append(self.command_spec(name))
        return available

    def help_text(self, *, config: str | None, flow_id: str) -> str:
        lines: list[str] = []
        for spec in self.command_catalog():
            if spec.name in _SILENT_ALIAS_COMMANDS:
                continue
            availability = self.command_availability(config=config, flow_id=flow_id, command_name=spec.name)
            suffix = "" if availability.enabled else f" [disabled: {availability.reason}]"
            lines.append(f"{spec.usage}  {spec.summary}{suffix}")
        return "\n".join(lines)

    def action_bar_text(self, *, config: str | None, flow_id: str, enter_hint: str = "open") -> str:
        context = self.flow_context(config=config, flow_id=flow_id)
        available = " ".join(spec.usage.split(" ", 1)[0] for spec in self.available_operator_commands(config=config, flow_id=flow_id)) or "-"
        focus = context.flow_id or "-"
        status = context.status or "-"
        return f"q quit  r refresh  enter {enter_hint}  focus={focus} status={status}  actions={available}"

    def _new_event_app(self) -> FlowApp:
        return FlowApp(
            run_prompt_receipt_fn=self._run_prompt_receipt_fn,
            input_fn=lambda prompt: "",
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            display=EventFlowDisplay(event_callback=self._event_callback),
            event_callback=self._event_callback,
            hook_callback=self._hook_callback,
        )

    def _new_plain_app(self) -> FlowApp:
        return FlowApp(
            run_prompt_receipt_fn=self._run_prompt_receipt_fn,
            input_fn=lambda prompt: "",
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )

    def parse_command(self, raw: str) -> SlashCommand:
        text = str(raw or "").strip()
        if not text.startswith("/"):
            raise ValueError("slash commands must start with '/'")
        parts = shlex.split(text[1:])
        if not parts:
            raise ValueError("empty slash command")
        name = self._canonical_command_name(parts[0])
        if name not in _COMMAND_BY_NAME:
            raise ValueError(f"unknown command: /{parts[0]}")
        return SlashCommand(name=name, args=parts[1:], raw=text)

    def launcher_snapshot(self, *, config: str | None) -> dict[str, Any]:
        app = self._new_plain_app()
        preflight = app.build_preflight_payload(argparse.Namespace(config=config, json=False))
        flows = app.build_flows_payload(argparse.Namespace(config=config, limit=10, json=False, manage="", goal="", guard_condition="", instruction=""))
        return {"preflight": preflight, "flows": flows}

    def manage_center_payload(self, *, config: str | None, limit: int = 20) -> dict[str, Any]:
        app = self._new_plain_app()
        preflight = app.build_preflight_payload(argparse.Namespace(config=config, json=False))
        assets = app.build_manage_payload(argparse.Namespace(config=config, limit=limit, json=False, manage="", goal="", guard_condition="", instruction=""))
        return {"preflight": preflight, "assets": assets}

    def history_payload(self, *, config: str | None) -> dict[str, Any]:
        return self.launcher_snapshot(config=config)

    def flows_payload(self, *, config: str | None) -> dict[str, Any]:
        return self.manage_center_payload(config=config)

    def status_payload(self, *, config: str | None, flow_id: str) -> dict[str, Any]:
        app = self._new_plain_app()
        return app.build_status_payload(argparse.Namespace(config=config, flow_id=flow_id, workflow_id="", last=False, json=False))

    def inspect_payload(self, *, config: str | None, flow_id: str) -> dict[str, Any]:
        payload = self.status_payload(config=config, flow_id=flow_id)
        flow_path = Path(payload["flow_dir"])
        if not flow_path.exists():
            flow_path = resolve_flow_dir(payload["flow_state"].get("workspace_root") or "", flow_id)
        return {
            "status": payload,
            "turns": _read_jsonl(flow_turns_path(flow_path)),
            "actions": _read_jsonl(flow_actions_path(flow_path)),
            "artifacts": read_json(flow_artifacts_path(flow_path)).get("items") or [],
            "handoffs": _read_jsonl(handoffs_path(flow_path)),
        }

    def _normalized_handoffs(self, handoffs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in handoffs:
            row = dict(item or {})
            if not row:
                continue
            normalized.append(
                {
                    "handoff_id": str(row.get("handoff_id") or "").strip(),
                    "from_role_id": str(row.get("from_role_id") or row.get("source_role_id") or "").strip(),
                    "to_role_id": str(row.get("to_role_id") or row.get("target_role_id") or "").strip(),
                    "status": str(row.get("status") or "").strip(),
                    "summary": str(row.get("summary") or "").strip(),
                    "created_at": str(row.get("created_at") or "").strip(),
                    "consumed_at": str(row.get("consumed_at") or "").strip(),
                    "source_phase": str(row.get("source_phase") or "").strip(),
                    "target_phase": str(row.get("target_phase") or "").strip(),
                    "next_action": str(row.get("next_action") or "").strip(),
                }
            )
        return normalized

    def _sort_handoffs(self, handoffs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def _sort_key(row: dict[str, Any]) -> str:
            return str(row.get("consumed_at") or row.get("created_at") or "")
        return sorted(self._normalized_handoffs(handoffs), key=_sort_key)

    def _latest_handoff_summary(self, handoffs: list[dict[str, Any]]) -> dict[str, Any]:
        return latest_handoff_summary(handoffs)

    def _recent_handoffs(self, handoffs: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
        normalized = self._sort_handoffs(handoffs)
        if not normalized:
            return []
        return list(reversed(normalized[-max(1, int(limit or 5)) :]))

    def _pending_handoffs(self, handoffs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = self._sort_handoffs(handoffs)
        pending = [row for row in normalized if str(row.get("status") or "").strip() == "pending"]
        return list(reversed(pending))

    def _role_chips(self, *, flow_state: dict[str, Any], handoffs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        role_sessions = dict(flow_state.get("role_sessions") or {})
        active_role_id = str(flow_state.get("active_role_id") or "").strip()
        pending_handoffs = self._pending_handoffs(handoffs)
        pending_targets = {str(item.get("to_role_id") or "").strip() for item in pending_handoffs if str(item.get("to_role_id") or "").strip()}
        pending_sources = {str(item.get("from_role_id") or "").strip() for item in pending_handoffs if str(item.get("from_role_id") or "").strip()}
        role_order: list[str] = []

        def _add_role(role_id: str) -> None:
            token = str(role_id or "").strip()
            if token and token not in role_order:
                role_order.append(token)

        for role_id in role_sessions:
            _add_role(str(role_id))
        _add_role(active_role_id)
        for handoff in self._sort_handoffs(handoffs):
            _add_role(str(handoff.get("from_role_id") or ""))
            _add_role(str(handoff.get("to_role_id") or ""))

        chips: list[dict[str, Any]] = []
        for role_id in role_order:
            session_payload = dict(role_sessions.get(role_id) or {})
            state = "idle"
            if role_id and role_id == active_role_id:
                state = "active"
            elif role_id in pending_targets:
                state = "receiving_handoff"
            elif role_id in pending_sources:
                state = "handoff_source"
            chips.append(
                {
                    "role_id": role_id,
                    "state": state,
                    "is_active": bool(role_id and role_id == active_role_id),
                    "session_id": str(session_payload.get("session_id") or "").strip(),
                }
            )
        return chips

    def _flow_summary(self, *, status_payload: dict[str, Any], handoffs: list[dict[str, Any]]) -> dict[str, Any]:
        return build_flow_summary(status_payload=status_payload, handoffs=handoffs).to_dict()

    def _resolve_flow_path(self, *, status_payload: dict[str, Any], flow_id: str) -> Path:
        flow_dir_value = str(status_payload.get("flow_dir") or "").strip()
        if flow_dir_value:
            flow_path = Path(flow_dir_value)
            if flow_path.exists():
                return flow_path
        return resolve_flow_dir(status_payload.get("workspace_root") or "", flow_id)

    def _inspector_payload(self, *, flow_id: str, inspected: dict[str, Any]) -> dict[str, Any]:
        status = dict(inspected.get("status") or {})
        flow_state = dict(status.get("flow_state") or {})
        handoffs = list(inspected.get("handoffs") or [])
        flow_path = self._resolve_flow_path(status_payload=status, flow_id=flow_id)
        runtime_plan = self._read_optional_json(flow_path / "runtime_plan.json")
        strategy_trace = self._read_optional_jsonl(flow_path / "strategy_trace.jsonl")
        mutations = self._read_optional_jsonl(flow_path / "mutations.jsonl")
        prompt_packets = self._read_optional_jsonl(flow_path / "prompt_packets.jsonl")
        return {
            "selected_event": {},
            "roles": {
                "role_sessions": dict(flow_state.get("role_sessions") or {}),
                "latest_role_handoffs": dict(flow_state.get("latest_role_handoffs") or {}),
                "pending_handoffs": self._pending_handoffs(handoffs),
                "recent_handoffs": self._recent_handoffs(handoffs),
                "latest_handoff_summary": self._latest_handoff_summary(handoffs),
            },
            "handoffs": handoffs,
            "artifacts": list(inspected.get("artifacts") or []),
            "plan": {
                "phase_plan": list(flow_state.get("phase_plan") or []),
                "flow_definition": dict(status.get("flow_definition") or {}),
            },
            "runtime": {
                "runtime_snapshot": dict(status.get("runtime_snapshot") or {}),
                "trace_summary": dict(status.get("trace_summary") or {}),
                "runtime_plan": runtime_plan,
                "strategy_trace": strategy_trace,
                "mutations": mutations,
                "prompt_packets": prompt_packets,
            },
        }

    def _supervisor_view_payload(
        self,
        *,
        flow_id: str,
        summary: dict[str, Any],
        flow_state: dict[str, Any],
        timeline: list[dict[str, Any]],
        runtime_plan: dict[str, Any],
    ) -> dict[str, Any]:
        header = {
            "flow_id": flow_id,
            "workflow_kind": summary.get("workflow_kind"),
            "status": summary.get("effective_status"),
            "phase": summary.get("effective_phase"),
            "goal": summary.get("goal"),
            "guard_condition": summary.get("guard_condition"),
            "active_role_id": summary.get("active_role_id"),
            "approval_state": summary.get("approval_state"),
            "execution_mode": summary.get("execution_mode"),
            "session_strategy": summary.get("session_strategy"),
            "supervisor_thread_id": str(flow_state.get("supervisor_thread_id") or "").strip(),
        }
        supervisor_events = [row for row in timeline if str(row.get("lane") or "").strip() == "supervisor"]
        latest_supervisor = dict(flow_state.get("latest_supervisor_decision") or {})
        return {
            "header": header,
            "events": supervisor_events,
            "pointers": {
                "approval_state": summary.get("approval_state"),
                "pending_codex_prompt": str(flow_state.get("pending_codex_prompt") or "").strip(),
                "queued_operator_updates": list(flow_state.get("queued_operator_updates") or []),
                "latest_supervisor_decision": latest_supervisor,
                "latest_judge_decision": dict(flow_state.get("latest_judge_decision") or flow_state.get("last_cursor_decision") or {}),
                "latest_operator_action": dict(flow_state.get("last_operator_action") or {}),
                "latest_handoff_summary": summary.get("latest_handoff_summary"),
                "max_runtime_seconds": int(flow_state.get("max_runtime_seconds") or 0),
                "runtime_elapsed_seconds": int(flow_state.get("runtime_elapsed_seconds") or 0),
                "latest_token_usage": dict(flow_state.get("latest_token_usage") or {}),
                "context_governor": dict(flow_state.get("context_governor") or {}),
                "risk_level": str(runtime_plan.get("risk_level") or flow_state.get("risk_level") or "").strip(),
                "autonomy_profile": str(runtime_plan.get("autonomy_profile") or flow_state.get("autonomy_profile") or "").strip(),
                "supervisor_session_mode": str(latest_supervisor.get("session_mode") or "").strip(),
                "supervisor_load_profile": str(latest_supervisor.get("load_profile") or "").strip(),
                "latest_mutation": dict(runtime_plan.get("latest_mutation") or flow_state.get("latest_mutation") or {}),
            },
        }

    def _workflow_view_payload(self, *, timeline: list[dict[str, Any]]) -> dict[str, Any]:
        workflow_events = [row for row in timeline if str(row.get("lane") or "").strip() == "workflow"]
        return {"events": workflow_events}

    def role_strip_payload(self, *, config: str | None, flow_id: str) -> dict[str, Any]:
        inspected = self.inspect_payload(config=config, flow_id=flow_id)
        status = dict(inspected.get("status") or {})
        flow_state = dict(status.get("flow_state") or {})
        role_sessions = dict(flow_state.get("role_sessions") or {})
        handoffs = list(inspected.get("handoffs") or [])
        roles: list[dict[str, Any]] = []
        for chip in self._role_chips(flow_state=flow_state, handoffs=handoffs):
            role_id = str(chip.get("role_id") or "").strip()
            item = dict(role_sessions.get(role_id) or {})
            payload = dict(item or {})
            if not isinstance(payload, dict):
                payload = {"role_id": str(role_id or "").strip(), "session_id": str(payload)}
            payload["role_id"] = str(payload.get("role_id") or role_id or "").strip()
            payload["state"] = str(chip.get("state") or "").strip()
            payload["is_active"] = bool(chip.get("is_active"))
            roles.append(payload)
        return {
            "execution_mode": str(flow_state.get("execution_mode") or "").strip(),
            "session_strategy": str(flow_state.get("session_strategy") or "").strip(),
            "active_role_id": str(flow_state.get("active_role_id") or "").strip(),
            "role_pack_id": str(flow_state.get("role_pack_id") or "").strip(),
            "roles": roles,
            "role_chips": self._role_chips(flow_state=flow_state, handoffs=handoffs),
            "latest_role_handoffs": dict(flow_state.get("latest_role_handoffs") or {}),
            "latest_handoff_summary": self._latest_handoff_summary(handoffs),
        }

    def operator_rail_payload(self, *, config: str | None, flow_id: str) -> dict[str, Any]:
        inspected = self.inspect_payload(config=config, flow_id=flow_id)
        status = dict(inspected.get("status") or {})
        flow_state = dict(status.get("flow_state") or {})
        timeline = self.timeline_payload(config=config, flow_id=flow_id)
        promoted_kinds = {"warning", "error", "phase_transition", "role_handoff_created", "role_handoff_consumed", "manage_handoff_ready"}
        promoted = [row for row in timeline if str(row.get("kind") or "") in promoted_kinds]
        return {
            "approval_state": str(flow_state.get("approval_state") or "").strip() or "not_required",
            "pending_codex_prompt": str(flow_state.get("pending_codex_prompt") or "").strip(),
            "latest_judge_decision": dict(flow_state.get("latest_judge_decision") or {}),
            "latest_operator_action": dict(flow_state.get("last_operator_action") or {}),
            "latest_supervisor_decision": dict(flow_state.get("latest_supervisor_decision") or {}),
            "latest_handoff_summary": self._latest_handoff_summary(list(inspected.get("handoffs") or [])),
            "manage_handoff": dict(flow_state.get("manage_handoff") or {}),
            "role_strip": self.role_strip_payload(config=config, flow_id=flow_id),
            "promoted_events": promoted,
        }

    def flow_console_payload(self, *, config: str | None, flow_id: str) -> dict[str, Any]:
        inspected = self.inspect_payload(config=config, flow_id=flow_id)
        summary = self._flow_summary(status_payload=inspected.get("status") or {}, handoffs=list(inspected.get("handoffs") or []))
        steps = self._step_history(payload=inspected)
        return {
            "flow_id": flow_id,
            "summary": summary,
            "recent_steps": steps[-3:] if steps else [],
            "step_history": steps,
        }

    def detail_payload(self, *, config: str | None, flow_id: str) -> dict[str, Any]:
        inspected = self.inspect_payload(config=config, flow_id=flow_id)
        status = dict(inspected.get("status") or {})
        flow_state = dict(status.get("flow_state") or {})
        handoffs = list(inspected.get("handoffs") or [])
        role_strip = self.role_strip_payload(config=config, flow_id=flow_id)
        return {
            "flow_id": flow_id,
            "status": status,
            "approval": {
                "approval_state": str(flow_state.get("approval_state") or "").strip() or "not_required",
                "pending_codex_prompt": str(flow_state.get("pending_codex_prompt") or "").strip(),
                "latest_supervisor_decision": dict(flow_state.get("latest_supervisor_decision") or {}),
                "latest_operator_action": dict(flow_state.get("last_operator_action") or {}),
            },
            "receipts": {
                "operator_actions": list(inspected.get("actions") or []),
                "turns": list(inspected.get("turns") or []),
            },
            "timeline": self.timeline_payload(config=config, flow_id=flow_id),
            "roles": {
                "role_sessions": dict(flow_state.get("role_sessions") or {}),
                "latest_role_handoffs": dict(flow_state.get("latest_role_handoffs") or {}),
                "handoffs": handoffs,
            },
            "multi_agent": {
                "active_role_id": str(flow_state.get("active_role_id") or "").strip(),
                "role_chips": list(role_strip.get("role_chips") or []),
                "role_sessions": dict(flow_state.get("role_sessions") or {}),
                "pending_handoffs": self._pending_handoffs(handoffs),
                "recent_handoffs": self._recent_handoffs(handoffs),
                "latest_handoff_summary": self._latest_handoff_summary(handoffs),
            },
            "artifacts": list(inspected.get("artifacts") or []),
            "plan": {
                "phase_plan": list(flow_state.get("phase_plan") or []),
                "flow_definition": dict(status.get("flow_definition") or {}),
            },
            "runtime": {
                "runtime_snapshot": dict(status.get("runtime_snapshot") or {}),
                "trace_summary": dict(status.get("trace_summary") or {}),
            },
        }

    def workspace_payload(self, *, config: str | None, limit: int = 10) -> dict[str, Any]:
        snapshot = self.launcher_snapshot(config=config)
        flows = dict(snapshot.get("flows") or {})
        rows = list(flows.get("items") or [])
        enriched = []
        for row in rows[: max(1, int(limit or 10))]:
            entry = dict(row or {})
            flow_id = str(entry.get("flow_id") or "").strip()
            if not flow_id:
                enriched.append(entry)
                continue
            try:
                status_payload = self.status_payload(config=config, flow_id=flow_id)
                flow_state = dict(status_payload.get("flow_state") or {})
                flow_dir_value = str(status_payload.get("flow_dir") or "").strip()
                handoffs = list(_read_jsonl(handoffs_path(Path(flow_dir_value)))) if flow_dir_value else []
                summary = self._flow_summary(status_payload=status_payload, handoffs=handoffs)
                entry.update(
                    {
                        "approval_state": summary.get("approval_state"),
                        "execution_mode": summary.get("execution_mode"),
                        "session_strategy": summary.get("session_strategy"),
                        "active_role_id": summary.get("active_role_id"),
                        "latest_judge_decision": summary.get("latest_judge_decision"),
                        "latest_operator_action": summary.get("latest_operator_action"),
                        "latest_handoff_summary": summary.get("latest_handoff_summary"),
                        "role_pack_id": summary.get("role_pack_id"),
                        "flow_state": flow_state,
                    }
                )
            except Exception:
                enriched.append(entry)
                continue
            enriched.append(entry)
        flows["items"] = enriched
        return {"preflight": snapshot.get("preflight"), "flows": flows}

    def _step_history(self, *, payload: dict[str, Any]) -> list[dict[str, Any]]:
        status = dict(payload.get("status") or {})
        flow_state = dict(status.get("flow_state") or {})
        phase_history = list(flow_state.get("phase_history") or [])
        steps: list[dict[str, Any]] = []
        for row in phase_history:
            entry = dict(row or {})
            decision = dict(entry.get("decision") or {})
            phase = str(entry.get("phase") or status.get("effective_phase") or flow_state.get("current_phase") or "").strip()
            steps.append(
                {
                    "step_id": f"phase:{len(steps)+1}:{phase or 'unknown'}",
                    "phase": phase,
                    "attempt_no": int(entry.get("attempt_no") or 0),
                    "decision": str(decision.get("decision") or "").strip(),
                    "summary": str(decision.get("completion_summary") or decision.get("reason") or "").strip(),
                    "created_at": str(entry.get("at") or "").strip(),
                }
            )
        if steps:
            return steps
        for row in list(payload.get("turns") or []):
            entry = dict(row or {})
            steps.append(
                {
                    "step_id": str(entry.get("turn_id") or f"turn:{len(steps)+1}").strip(),
                    "phase": str(entry.get("phase") or "").strip(),
                    "attempt_no": int(entry.get("attempt_no") or 0),
                    "decision": str(entry.get("decision") or "").strip(),
                    "summary": str(entry.get("reason") or "").strip(),
                    "created_at": str(entry.get("completed_at") or entry.get("started_at") or "").strip(),
                }
            )
        return steps

    def single_flow_payload(self, *, config: str | None, flow_id: str) -> dict[str, Any]:
        inspected = self.inspect_payload(config=config, flow_id=flow_id)
        status = dict(inspected.get("status") or {})
        flow_state = dict(status.get("flow_state") or {})
        flow_path = self._resolve_flow_path(status_payload=status, flow_id=flow_id)
        summary = self._flow_summary(status_payload=inspected.get("status") or {}, handoffs=list(inspected.get("handoffs") or []))
        timeline = self.timeline_payload(config=config, flow_id=flow_id)
        runtime_plan = self._read_optional_json(flow_path / "runtime_plan.json")
        return {
            "flow_id": flow_id,
            "status": status,
            "summary": summary,
            "step_history": self._step_history(payload=inspected),
            "timeline": timeline,
            "artifacts": list(inspected.get("artifacts") or []),
            "turns": list(inspected.get("turns") or []),
            "actions": list(inspected.get("actions") or []),
            "handoffs": list(inspected.get("handoffs") or []),
            "navigator_summary": summary,
            "supervisor_view": self._supervisor_view_payload(
                flow_id=flow_id,
                summary=summary,
                flow_state=flow_state,
                timeline=timeline,
                runtime_plan=runtime_plan,
            ),
            "workflow_view": self._workflow_view_payload(timeline=timeline),
            "inspector": self._inspector_payload(flow_id=flow_id, inspected=inspected),
            # Legacy compatibility projections; the current flow page reads the
            # view-specific payloads above rather than rendering a fixed rail.
            "role_strip": self.role_strip_payload(config=config, flow_id=flow_id),
            "operator_rail": self.operator_rail_payload(config=config, flow_id=flow_id),
            "flow_console": self.flow_console_payload(config=config, flow_id=flow_id),
        }

    def artifacts_payload(self, *, config: str | None, flow_id: str) -> list[dict[str, Any]]:
        inspected = self.inspect_payload(config=config, flow_id=flow_id)
        return list(inspected.get("artifacts") or [])

    def prepare_run(
        self,
        *,
        config: str | None,
        kind: str,
        catalog_flow_id: str = "",
        goal: str,
        guard_condition: str,
        execution_mode: str | None = None,
        role_pack: str | None = None,
        max_attempts: int | None = None,
        max_phase_attempts: int | None = None,
    ) -> PreparedFlowRun:
        app = self._new_event_app()
        args = argparse.Namespace(
            command="run",
            config=config,
            kind=kind,
            catalog_flow_id=catalog_flow_id,
            goal=goal,
            guard_condition=guard_condition,
            execution_mode=execution_mode,
            role_pack=role_pack,
            max_attempts=max_attempts,
            max_phase_attempts=max_phase_attempts,
            no_stream=False,
            plain=False,
        )
        return app.prepare_new_flow(args)

    def prepare_resume(
        self,
        *,
        config: str | None,
        flow_id: str = "",
        use_last: bool = False,
        codex_session_id: str = "",
        kind: str = "single_goal",
        goal: str = "",
        guard_condition: str = "",
        execution_mode: str | None = None,
        role_pack: str | None = None,
        max_attempts: int | None = None,
        max_phase_attempts: int | None = None,
    ) -> PreparedFlowRun:
        app = self._new_event_app()
        args = argparse.Namespace(
            command="resume",
            config=config,
            flow_id=flow_id,
            workflow_id="",
            last=use_last,
            codex_session_id=codex_session_id,
            kind=kind,
            goal=goal,
            guard_condition=guard_condition,
            execution_mode=execution_mode,
            role_pack=role_pack,
            max_attempts=max_attempts,
            max_phase_attempts=max_phase_attempts,
            no_stream=False,
            plain=False,
        )
        return app.prepare_resume_flow(args)

    def execute_prepared_flow(self, prepared: PreparedFlowRun, *, stream_enabled: bool = True) -> int:
        app = self._new_event_app()
        return app.execute_prepared_flow(prepared, stream_enabled=stream_enabled)

    def manage_flow(
        self,
        *,
        config: str | None,
        manage_target: str,
        goal: str = "",
        guard_condition: str = "",
        instruction: str = "",
        stage: str = "",
        builtin_mode: str = "",
        draft_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        app = self._new_plain_app()
        args = argparse.Namespace(
            command="manage",
            config=config,
            limit=10,
            json=True,
            manage=manage_target,
            goal=goal,
            guard_condition=guard_condition,
            instruction=instruction,
            stage=stage,
            builtin_mode=builtin_mode,
            draft_payload=dict(draft_payload or {}),
        )
        app.manage_flow(args)
        text = str(getattr(app, "_stdout", io.StringIO()).getvalue()).strip()
        return json.loads(text) if text else {}

    def manage_chat(
        self,
        *,
        config: str | None,
        instruction: str,
        manage_target: str = "",
        manager_session_id: str = "",
    ) -> dict[str, Any]:
        app = self._new_plain_app()
        args = argparse.Namespace(
            command="manage-chat",
            config=config,
            json=True,
            manage=manage_target,
            instruction=instruction,
            manager_session_id=manager_session_id,
        )
        app.manage_chat(args)
        text = str(getattr(app, "_stdout", io.StringIO()).getvalue()).strip()
        return json.loads(text) if text else {}

    def apply_action(
        self,
        *,
        config: str | None,
        flow_id: str,
        action_type: str,
        instruction: str = "",
    ) -> dict[str, Any]:
        app = self._new_plain_app()
        receipt = app.apply_action_payload(
            argparse.Namespace(
                command="action",
                config=config,
                flow_id=flow_id,
                workflow_id="",
                last=False,
                type=action_type,
                instruction=instruction,
            )
        )
        return dict(receipt or {})
