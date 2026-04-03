from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from butler_main.agents_os.execution.cli_runner import cli_provider_available, run_prompt_receipt
from butler_main.chat.config_runtime import load_active_config, resolve_default_config_path
from butler_main.chat.pathing import resolve_butler_root

from .constants import (
    DEFAULT_CATALOG_FLOW_ID,
    DEFAULT_EXECUTION_LEVEL,
    DEFAULT_LAUNCH_MODE,
    DEFAULT_FLOW_LAUNCHER_RECENT_LIMIT,
    DEFAULT_FLOW_LIST_LIMIT,
    DEFAULT_PROJECT_LOOP_MAX_ATTEMPTS,
    DEFAULT_PROJECT_PHASE_MAX_ATTEMPTS,
    DEFAULT_SINGLE_GOAL_MAX_ATTEMPTS,
    EXECUTION_LEVEL_HIGH,
    EXECUTION_LEVEL_MEDIUM,
    EXECUTION_LEVEL_SIMPLE,
    EXECUTION_MODE_MEDIUM,
    EXECUTION_MODE_SIMPLE,
    MANAGED_FLOW_KIND,
    PROJECT_LOOP_KIND,
    PROJECT_LOOP_CATALOG_FLOW_ID,
    FREE_CATALOG_FLOW_ID,
    LAUNCH_MODE_FLOW,
    LAUNCH_MODE_SINGLE,
    SINGLE_GOAL_KIND,
    normalize_execution_context,
)
from .display import FlowDisplay, JsonlFlowDisplay, RichFlowDisplay
from .events import FlowLifecycleHook, FlowUiEvent, FlowUiEventCallback
from .flow_catalog import builtin_flow_catalog, catalog_entry
from .flow_definition import coerce_workflow_kind, first_phase_id, normalize_phase_plan, phase_ids, resolve_phase_plan
from .manage_agent import (
    normalize_manage_chat_draft_payload,
    normalize_manage_stage,
    normalize_role_guidance_payload,
    run_design_stage,
    run_manage_agent,
    run_manage_chat_agent,
)
from .models import FlowExecReceiptV1, PreparedFlowRun
from .role_runtime import (
    default_execution_mode,
    default_role_pack_id,
    extract_role_runtime_summary,
    normalize_execution_mode,
    normalize_role_pack_id,
    normalize_session_strategy,
    session_strategy_for_mode,
)
from .runtime import FlowRuntime, flow_disabled_mcp_servers, flow_timeout_seconds, judge_timeout_seconds, sync_project_phase_attempt_count
from .state import (
    FileRuntimeStateStore,
    FileTraceStore,
    append_jsonl,
    asset_bundle_manifest,
    asset_bundle_root,
    build_flow_root,
    builtin_asset_root,
    design_draft_path,
    design_session_path,
    design_turns_path,
    ensure_asset_bundle_files,
    flow_dir,
    flow_asset_audit_path,
    flow_asset_root,
    flow_definition_path,
    flow_state_path,
    instance_asset_root,
    legacy_flow_dir,
    legacy_flow_state_path,
    legacy_flow_root,
    new_flow_id,
    new_flow_state,
    normalize_control_profile_payload,
    normalize_source_items,
    normalize_supervisor_profile_payload,
    normalize_doctor_policy_payload,
    now_text,
    read_manage_draft,
    read_manage_pending_action,
    read_manage_session,
    read_flow_state,
    read_json,
    resolve_flow_dir,
    safe_int,
    template_asset_root,
    write_bundle_sources,
    write_compiled_supervisor_knowledge,
    write_manage_draft,
    write_manage_pending_action,
    write_manage_session,
    append_manage_turn,
    clear_manage_pending_action,
    write_json_atomic,
)
from .version import BUTLER_FLOW_VERSION


def _truncate(value: str, *, limit: int = 88) -> str:
    return FlowDisplay.truncate(value, limit=limit)


def _sanitize_asset_topic(value: str, *, limit: int = 48) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"_+", "_", text).strip("._-")
    return text[:limit].strip("._-")


class FlowApp:
    def __init__(
        self,
        *,
        run_prompt_receipt_fn: Callable[..., Any],
        input_fn: Callable[[str], str],
        stdout=None,
        stderr=None,
        display: FlowDisplay | None = None,
        event_callback: FlowUiEventCallback | None = None,
        hook_callback: FlowLifecycleHook | None = None,
    ) -> None:
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr
        self._run_prompt_receipt_fn = run_prompt_receipt_fn
        is_tty = bool(getattr(self._stdout, "isatty", lambda: False)())
        self._display = display or (RichFlowDisplay(self._stdout, self._stderr) if is_tty else FlowDisplay(self._stdout, self._stderr))
        self._input_fn = input_fn
        self._runtime = FlowRuntime(
            run_prompt_receipt_fn=run_prompt_receipt_fn,
            display=self._display,
            event_callback=event_callback,
            hook_callback=hook_callback,
        )

    def _new_exec_app(self) -> tuple["FlowApp", JsonlFlowDisplay]:
        display = JsonlFlowDisplay(self._stdout, self._stderr)

        def _event_callback(event: FlowUiEvent) -> None:
            display.write_jsonl(event.to_dict())

        app = FlowApp(
            run_prompt_receipt_fn=self._run_prompt_receipt_fn,
            input_fn=self._input_fn,
            stdout=self._stdout,
            stderr=self._stderr,
            display=display,
            event_callback=_event_callback,
        )
        return app, display

    @staticmethod
    def _exec_return_code_for_status(status: str) -> int:
        normalized = str(status or "").strip().lower()
        if normalized == "completed":
            return 0
        if normalized == "interrupted":
            return 130
        return 1

    def _build_exec_receipt(self, *, flow_path: Path, flow_state: dict[str, Any], return_code: int) -> FlowExecReceiptV1:
        last_codex_metadata = dict(dict(flow_state.get("last_codex_receipt") or {}).get("metadata") or {})
        return {
            "receipt_id": f"flow_exec_receipt_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}",
            "kind": "flow_exec_receipt",
            "flow_id": str(flow_state.get("workflow_id") or "").strip(),
            "workflow_kind": str(flow_state.get("workflow_kind") or "").strip(),
            "status": str(flow_state.get("status") or "failed").strip() or "failed",
            "terminal": True,
            "return_code": int(return_code),
            "flow_dir": str(flow_path),
            "current_phase": str(flow_state.get("current_phase") or "").strip(),
            "active_role_id": str(flow_state.get("active_role_id") or "").strip(),
            "launch_mode": str(flow_state.get("launch_mode") or "").strip(),
            "catalog_flow_id": str(flow_state.get("catalog_flow_id") or "").strip(),
            "execution_mode": str(flow_state.get("execution_mode") or "").strip(),
            "session_strategy": str(flow_state.get("session_strategy") or "").strip(),
            "role_pack_id": str(flow_state.get("role_pack_id") or "").strip(),
            "execution_context": str(flow_state.get("execution_context") or "").strip(),
            "execution_workspace_root": str(last_codex_metadata.get("execution_workspace_root") or "").strip(),
            "attempt_count": safe_int(flow_state.get("attempt_count"), 0),
            "codex_session_id": str(flow_state.get("codex_session_id") or "").strip(),
            "summary": str(flow_state.get("last_completion_summary") or "").strip(),
            "last_judge_decision": dict(
                flow_state.get("latest_judge_decision")
                or flow_state.get("last_cursor_decision")
                or {}
            ),
            "latest_supervisor_decision": dict(flow_state.get("latest_supervisor_decision") or {}),
            "last_codex_receipt": dict(flow_state.get("last_codex_receipt") or {}),
            "last_cursor_receipt": dict(flow_state.get("last_cursor_receipt") or {}),
            "trace_refs": [str(item or "").strip() for item in list(flow_state.get("trace_refs") or []) if str(item or "").strip()],
            "receipt_refs": [str(item or "").strip() for item in list(flow_state.get("receipt_refs") or []) if str(item or "").strip()],
            "created_at": now_text(),
        }

    def _emit_exec_receipt(self, display: JsonlFlowDisplay, *, flow_path: Path, flow_state: dict[str, Any], return_code: int) -> int:
        receipt = self._build_exec_receipt(flow_path=flow_path, flow_state=flow_state, return_code=return_code)
        display.write_jsonl(dict(receipt))
        return int(return_code)

    def _exec_prepared_flow(self, prepared: PreparedFlowRun, *, stream_enabled: bool) -> int:
        exec_app, display = self._new_exec_app()
        flow_state = prepared.flow_state
        terminal_status = str(flow_state.get("status") or "").strip().lower()
        if terminal_status in {"completed", "failed", "interrupted"}:
            return self._emit_exec_receipt(
                display,
                flow_path=prepared.flow_path,
                flow_state=flow_state,
                return_code=self._exec_return_code_for_status(terminal_status),
            )
        return_code = exec_app.execute_prepared_flow(prepared, stream_enabled=stream_enabled)
        final_status = str(flow_state.get("status") or "").strip().lower() or "failed"
        normalized_return_code = self._exec_return_code_for_status(final_status)
        if int(return_code) == 130 and final_status == "interrupted":
            normalized_return_code = 130
        return self._emit_exec_receipt(
            display,
            flow_path=prepared.flow_path,
            flow_state=flow_state,
            return_code=normalized_return_code,
        )

    def _prompt_value(self, prompt: str, current: str = "") -> str:
        if str(current or "").strip():
            return str(current).strip()
        return str(self._input_fn(prompt)).strip()

    def _choice_prompt(self, prompt: str, options: list[tuple[str, str]], *, default_value: str = "") -> str:
        normalized_default = str(default_value or "").strip().lower()
        labels = " / ".join(f"{index}. {label}" for index, (label, _) in enumerate(options, start=1))
        raw = str(self._input_fn(f"{prompt} [{labels}] ")).strip().lower()
        if not raw:
            return normalized_default or str(options[0][1]).strip()
        if raw.isdigit():
            index = int(raw) - 1
            if 0 <= index < len(options):
                return str(options[index][1]).strip()
        for label, value in options:
            if raw in {str(label).strip().lower(), str(value).strip().lower()}:
                return str(value).strip()
        return normalized_default or str(options[0][1]).strip()

    def _flow_catalog_rows(self) -> list[dict[str, Any]]:
        return list(builtin_flow_catalog())

    @staticmethod
    def _parse_manage_target(manage_target: str) -> tuple[str, str]:
        token = str(manage_target or "").strip()
        if not token or token == "new":
            return "instance", "new"
        if ":" in token:
            asset_kind, asset_id = token.split(":", 1)
            asset_kind = str(asset_kind or "").strip().lower()
            asset_id = str(asset_id or "").strip()
            if asset_kind in {"builtin", "template", "instance"} and asset_id:
                return asset_kind, asset_id
        return "instance", token

    @staticmethod
    def _manage_target_key(asset_kind: str, asset_id: str) -> str:
        return f"{str(asset_kind or 'instance').strip()}:{str(asset_id or '').strip()}"

    @staticmethod
    def _asset_file_path(*, workspace_root: str, asset_kind: str, asset_id: str) -> Path:
        normalized_kind = str(asset_kind or "").strip().lower()
        normalized_id = str(asset_id or "").strip()
        if normalized_kind == "builtin":
            return builtin_asset_root(workspace_root) / f"{normalized_id}.json"
        if normalized_kind == "template":
            return template_asset_root(workspace_root) / f"{normalized_id}.json"
        return flow_definition_path(flow_dir(workspace_root, normalized_id))

    def _next_readable_asset_id(
        self,
        *,
        workspace_root: str,
        asset_kind: str,
        label: str = "",
        goal: str = "",
        instruction: str = "",
    ) -> str:
        stamp = datetime.now().strftime("%Y%m%d")
        topic = _sanitize_asset_topic(label) or _sanitize_asset_topic(goal) or _sanitize_asset_topic(instruction) or str(asset_kind or "asset").strip()
        base = f"{stamp}_{topic}"
        candidate = base
        suffix = 2
        while (
            self._asset_file_path(workspace_root=workspace_root, asset_kind=asset_kind, asset_id=candidate).exists()
            or asset_bundle_root(workspace_root, asset_kind=asset_kind, asset_id=candidate).exists()
        ):
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    @staticmethod
    def _runtime_bundle_manifest(*, workspace_root: str, asset_kind: str, asset_id: str, definition: dict[str, Any] | None = None) -> dict[str, Any]:
        base = dict(definition or {})
        manifest = dict(base.get("bundle_manifest") or asset_bundle_manifest(asset_kind=asset_kind, asset_id=asset_id))
        root = asset_bundle_root(workspace_root, asset_kind=asset_kind, asset_id=asset_id)
        if root == Path(""):
            return manifest
        manifest["bundle_root"] = str(root.resolve())
        manifest["manager_ref"] = str((root / "manager.md").resolve())
        manifest["supervisor_ref"] = str((root / "supervisor.md").resolve())
        manifest["doctor_ref"] = str((root / "doctor.md").resolve())
        manifest["doctor_skill_ref"] = str((root / "skills" / "doctor" / "SKILL.md").resolve())
        manifest["sources_ref"] = str((root / "sources.json").resolve())
        manifest["references_root"] = str((root / "references").resolve())
        manifest["doctor_references_root"] = str((root / "references" / "doctor").resolve())
        manifest["assets_root"] = str((root / "assets").resolve())
        manifest["derived_root"] = str((root / "derived").resolve())
        manifest["derived"] = {
            "supervisor_compiled": str((root / "derived" / "supervisor_knowledge.json").resolve()),
        }
        return manifest

    @staticmethod
    def _contains_asset_token(text: str) -> bool:
        return bool(re.search(r"(^|\s)\$?(?:template|builtin|instance):[A-Za-z0-9_.-]+", str(text or "")))

    def _is_pure_manage_confirmation(self, instruction: str, *, pending_action: dict[str, Any] | None = None) -> bool:
        if not dict(pending_action or {}):
            return False
        stripped = str(instruction or "").strip()
        if not stripped or "\n" in stripped or len(stripped) > 24:
            return False
        if self._contains_asset_token(stripped):
            return False
        token = stripped.casefold()
        return token in {
            "confirm",
            "confirmed",
            "go ahead",
            "proceed",
            "yes",
            "ok",
            "okay",
            "确认",
            "同意",
            "按这个",
            "就这样",
            "可以",
            "可以了",
            "继续",
            "创建吧",
            "好",
            "行",
        }

    def _manage_draft_seed(
        self,
        *,
        manage_target: str,
        asset_kind: str,
        flow_state: dict[str, Any] | None,
        asset_definition: dict[str, Any] | None,
    ) -> dict[str, Any]:
        base = dict(asset_definition or flow_state or {})
        seed = normalize_manage_chat_draft_payload(
            {
                "manage_target": manage_target,
                "asset_kind": asset_kind,
                "label": base.get("label"),
                "description": base.get("description"),
                "workflow_kind": base.get("workflow_kind"),
                "goal": base.get("goal"),
                "guard_condition": base.get("guard_condition"),
                "phase_plan": base.get("phase_plan"),
                "review_checklist": base.get("review_checklist"),
                "role_guidance": base.get("role_guidance"),
                "control_profile": base.get("control_profile"),
                "doctor_policy": base.get("doctor_policy"),
                "supervisor_profile": base.get("supervisor_profile"),
                "run_brief": base.get("run_brief"),
                "source_bindings": base.get("source_bindings") or base.get("source_items"),
            }
        )
        if manage_target and not str(seed.get("manage_target") or "").strip():
            seed["manage_target"] = manage_target
        if asset_kind and not str(seed.get("asset_kind") or "").strip():
            seed["asset_kind"] = asset_kind
        return seed

    def _merge_manage_chat_draft(
        self,
        *,
        manage_target: str,
        asset_kind: str,
        current_draft: dict[str, Any] | None,
        result_draft: dict[str, Any] | None,
        flow_state: dict[str, Any] | None,
        asset_definition: dict[str, Any] | None,
    ) -> dict[str, Any]:
        seed = self._manage_draft_seed(
            manage_target=manage_target,
            asset_kind=asset_kind,
            flow_state=flow_state,
            asset_definition=asset_definition,
        )
        merged = normalize_manage_chat_draft_payload(current_draft, current=seed)
        merged = normalize_manage_chat_draft_payload(result_draft, current=merged)
        if not str(merged.get("manage_target") or "").strip():
            merged["manage_target"] = manage_target
        merged_target_kind, _ = self._parse_manage_target(str(merged.get("manage_target") or "").strip())
        if merged_target_kind in {"template", "builtin", "instance"}:
            merged["asset_kind"] = merged_target_kind
        elif not str(merged.get("asset_kind") or "").strip():
            merged["asset_kind"] = asset_kind or "instance"
        return merged

    @staticmethod
    def _draft_summary(draft: dict[str, Any]) -> str:
        payload = dict(draft or {})
        target = str(payload.get("manage_target") or "").strip() or str(payload.get("asset_kind") or "instance").strip()
        label = str(payload.get("label") or "").strip()
        workflow_kind = str(payload.get("workflow_kind") or "").strip()
        goal = str(payload.get("goal") or "").strip()
        control_profile = dict(payload.get("control_profile") or {})
        posture = str(dict(payload.get("supervisor_profile") or {}).get("archetype") or "").strip()
        parts = [target]
        if label:
            parts.append(label)
        if workflow_kind:
            parts.append(workflow_kind)
        if control_profile:
            control_summary = "/".join(
                token
                for token in (
                    str(control_profile.get("task_archetype") or "").strip(),
                    str(control_profile.get("packet_size") or "").strip(),
                    str(control_profile.get("evidence_level") or "").strip(),
                )
                if token
            )
            if control_summary:
                parts.append(f"control={control_summary}")
        if posture:
            parts.append(f"supervisor={posture}")
        summary = " · ".join(parts)
        if goal:
            summary = f"{summary}\n目标: {goal}"
        return summary.strip()

    def _build_manage_pending_action(
        self,
        *,
        resolved_target: str,
        result: dict[str, Any],
        draft: dict[str, Any],
        fallback_stage: str,
    ) -> dict[str, Any]:
        target = str(result.get("action_manage_target") or resolved_target or draft.get("manage_target") or "").strip()
        return {
            "manage_target": target,
            "stage": str(result.get("action_stage") or fallback_stage or "commit").strip() or "commit",
            "builtin_mode": str(result.get("action_builtin_mode") or draft.get("builtin_mode") or "").strip(),
            "instruction": str(result.get("action_instruction") or result.get("summary") or "").strip(),
            "draft": dict(draft or {}),
            "draft_summary": self._draft_summary(draft),
            "preview": str(result.get("pending_action_preview") or result.get("confirmation_prompt") or "").strip(),
            "confirmation_scope": str(result.get("confirmation_scope") or "none").strip(),
            "created_at": now_text(),
            "status": "pending_confirmation",
        }

    def _canonical_manage_summary(self, *, asset_kind: str, asset_id: str, definition: dict[str, Any]) -> str:
        workflow_kind = str(definition.get("workflow_kind") or "").strip() or "managed_flow"
        goal = str(definition.get("goal") or "").strip()
        target = f"{asset_kind}:{asset_id}"
        summary = f"{target} {workflow_kind}"
        if goal:
            summary = f"{summary} · {goal}"
        return summary

    def _manage_result_from_draft(
        self,
        *,
        draft_payload: dict[str, Any],
        flow_state: dict[str, Any] | None,
        asset_kind: str,
        manage_target: str,
        requested_goal: str,
        requested_guard: str,
        manage_stage: str,
    ) -> dict[str, Any]:
        draft = normalize_manage_chat_draft_payload(
            draft_payload,
            current=self._manage_draft_seed(
                manage_target=manage_target,
                asset_kind=asset_kind,
                flow_state=flow_state,
                asset_definition=None,
            ),
        )
        result = {
            "summary": str(draft.get("summary") or "").strip(),
            "label": str(draft.get("label") or "").strip(),
            "description": str(draft.get("description") or "").strip(),
            "goal": str(draft.get("goal") or requested_goal or (flow_state or {}).get("goal") or "").strip(),
            "guard_condition": str(draft.get("guard_condition") or requested_guard or (flow_state or {}).get("guard_condition") or "").strip(),
            "workflow_kind": str(draft.get("workflow_kind") or (flow_state or {}).get("workflow_kind") or MANAGED_FLOW_KIND).strip(),
            "asset_kind": str(draft.get("asset_kind") or asset_kind or "instance").strip(),
            "mutation": "create" if str(manage_target or "").strip().endswith(":new") or str(manage_target or "").strip() == "new" else "update",
            "phase_plan": list(draft.get("phase_plan") or (flow_state or {}).get("phase_plan") or []),
            "review_checklist": list(draft.get("review_checklist") or []),
            "role_guidance": dict(draft.get("role_guidance") or {}),
            "control_profile": dict(draft.get("control_profile") or {}),
            "doctor_policy": dict(draft.get("doctor_policy") or {}),
            "supervisor_profile": dict(draft.get("supervisor_profile") or {}),
            "run_brief": str(draft.get("run_brief") or "").strip(),
            "source_bindings": list(draft.get("source_bindings") or []),
            "manage_stage": manage_stage,
        }
        if not str(result["summary"] or "").strip():
            result["summary"] = self._draft_summary(draft) or "managed flow updated"
        return result

    @staticmethod
    def _normalize_asset_definition(payload: dict[str, Any], *, asset_kind: str, asset_id: str) -> dict[str, Any]:
        raw = dict(payload or {})
        flow_id = str(raw.get("flow_id") or raw.get("definition_id") or asset_id).strip() or asset_id
        workflow_kind = coerce_workflow_kind(str(raw.get("workflow_kind") or MANAGED_FLOW_KIND))
        manager_handoff = dict(raw.get("manager_handoff") or raw.get("manage_handoff") or {})
        asset_state = dict(raw.get("asset_state") or {})
        if not str(asset_state.get("status") or "").strip():
            asset_state["status"] = "active"
        if not str(asset_state.get("stage") or "").strip():
            asset_state["stage"] = str(raw.get("manage_stage") or "committed").strip() or "committed"
        lineage = dict(raw.get("lineage") or {})
        instance_defaults = dict(raw.get("instance_defaults") or {})
        if not instance_defaults:
            instance_defaults = {
                "execution_mode": str(raw.get("execution_mode") or "").strip(),
                "session_strategy": str(raw.get("session_strategy") or "").strip(),
                "role_pack_id": str(raw.get("role_pack_id") or raw.get("default_role_pack") or "").strip(),
                "execution_context": str(raw.get("execution_context") or "").strip(),
                "launch_mode": str(raw.get("launch_mode") or "").strip(),
            }
        normalized_role_pack_id = normalize_role_pack_id(
            raw.get("role_pack_id") or raw.get("default_role_pack"),
            workflow_kind=workflow_kind,
        )
        execution_context = normalize_execution_context(
            raw.get("execution_context") or instance_defaults.get("execution_context"),
            role_pack_id=normalized_role_pack_id,
            workflow_kind=workflow_kind,
        )
        instance_defaults["execution_context"] = normalize_execution_context(
            instance_defaults.get("execution_context"),
            role_pack_id=str(instance_defaults.get("role_pack_id") or normalized_role_pack_id).strip(),
            workflow_kind=workflow_kind,
        )
        review_checklist = [
            str(item or "").strip()
            for item in list(raw.get("review_checklist") or [])
            if str(item or "").strip()
        ]
        bundle_manifest = dict(raw.get("bundle_manifest") or {})
        role_guidance = normalize_role_guidance_payload(
            raw.get("role_guidance") or manager_handoff.get("role_guidance") or {},
        )
        doctor_policy = normalize_doctor_policy_payload(
            raw.get("doctor_policy"),
            current=dict(manager_handoff.get("doctor_policy") or {}),
        )
        control_profile = normalize_control_profile_payload(
            raw.get("control_profile"),
            current=dict(manager_handoff.get("control_profile") or {}),
            workflow_kind=workflow_kind,
            role_pack_id=normalized_role_pack_id,
            execution_mode=str(raw.get("execution_mode") or instance_defaults.get("execution_mode") or "").strip(),
            execution_context=execution_context,
        )
        supervisor_profile = normalize_supervisor_profile_payload(
            raw.get("supervisor_profile"),
            current=dict(manager_handoff.get("supervisor_profile") or {}),
        )
        run_brief = str(raw.get("run_brief") or manager_handoff.get("run_brief") or "").strip()
        source_bindings = normalize_source_items(
            raw.get("source_bindings") or raw.get("source_items") or [],
        )
        return {
            "flow_id": flow_id,
            "definition_id": str(raw.get("definition_id") or flow_id).strip() or flow_id,
            "asset_kind": str(asset_kind or "instance").strip() or "instance",
            "label": str(raw.get("label") or flow_id).strip() or flow_id,
            "description": str(raw.get("description") or "").strip(),
            "workflow_kind": workflow_kind,
            "goal": str(raw.get("goal") or "").strip(),
            "guard_condition": str(raw.get("guard_condition") or "").strip(),
            "phase_plan": normalize_phase_plan(
                raw.get("phase_plan") if isinstance(raw.get("phase_plan"), list) else None,
                workflow_kind=workflow_kind,
            ),
            "default_role_pack": str(raw.get("default_role_pack") or normalized_role_pack_id or "coding_flow").strip() or "coding_flow",
            "allowed_execution_modes": [
                str(item or "").strip()
                for item in list(raw.get("allowed_execution_modes") or [])
                if str(item or "").strip()
            ] or [EXECUTION_LEVEL_SIMPLE, EXECUTION_LEVEL_MEDIUM],
            "launch_mode": str(raw.get("launch_mode") or LAUNCH_MODE_FLOW).strip() or LAUNCH_MODE_FLOW,
            "catalog_flow_id": str(raw.get("catalog_flow_id") or "").strip(),
            "execution_mode": str(raw.get("execution_mode") or "").strip(),
            "session_strategy": str(raw.get("session_strategy") or "").strip(),
            "role_pack_id": normalized_role_pack_id,
            "execution_context": execution_context,
            "risk_level": str(raw.get("risk_level") or "normal").strip() or "normal",
            "autonomy_profile": str(raw.get("autonomy_profile") or "default").strip() or "default",
            "manager_handoff": manager_handoff,
            "asset_state": asset_state,
            "lineage": lineage,
            "instance_defaults": instance_defaults,
            "review_checklist": review_checklist,
            "role_guidance": role_guidance,
            "control_profile": control_profile,
            "doctor_policy": doctor_policy,
            "supervisor_profile": supervisor_profile,
            "run_brief": run_brief,
            "source_bindings": source_bindings,
            "bundle_manifest": bundle_manifest,
            "source_asset_key": str(raw.get("source_asset_key") or "").strip(),
            "source_asset_kind": str(raw.get("source_asset_kind") or "").strip(),
            "source_asset_version": str(raw.get("source_asset_version") or "").strip(),
            "version": str(raw.get("version") or raw.get("flow_version") or BUTLER_FLOW_VERSION).strip() or BUTLER_FLOW_VERSION,
            "created_at": str(raw.get("created_at") or "").strip(),
            "updated_at": str(raw.get("updated_at") or raw.get("managed_at") or "").strip(),
        }

    def _definition_to_manage_row(
        self,
        *,
        workspace_root: str,
        asset_kind: str,
        asset_id: str,
        payload: dict[str, Any],
        path: Path,
    ) -> dict[str, Any]:
        definition = self._normalize_asset_definition(payload, asset_kind=asset_kind, asset_id=asset_id)
        bundle_manifest = dict(definition.get("bundle_manifest") or {})
        if asset_kind in {"builtin", "template"} and not bundle_manifest:
            bundle_manifest = asset_bundle_manifest(asset_kind=asset_kind, asset_id=asset_id)
            definition["bundle_manifest"] = dict(bundle_manifest)
        sort_value = 0.0
        for field in ("updated_at", "created_at"):
            stamp = str(definition.get(field) or "").strip()
            if not stamp:
                continue
            try:
                sort_value = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").timestamp()
                break
            except Exception:
                continue
        if sort_value <= 0:
            try:
                sort_value = path.stat().st_mtime
            except Exception:
                sort_value = 0.0
        row = {
            "asset_key": self._manage_target_key(asset_kind, asset_id),
            "asset_kind": asset_kind,
            "asset_id": asset_id,
            "flow_id": definition.get("flow_id"),
            "label": definition.get("label"),
            "description": definition.get("description"),
            "workflow_kind": definition.get("workflow_kind"),
            "goal": definition.get("goal"),
            "guard_condition": definition.get("guard_condition"),
            "execution_mode": definition.get("execution_mode"),
            "session_strategy": definition.get("session_strategy"),
            "role_pack_id": definition.get("role_pack_id"),
            "updated_at": definition.get("updated_at"),
            "created_at": definition.get("created_at"),
            "asset_path": str(path),
            "asset_state": dict(definition.get("asset_state") or {}),
            "lineage": dict(definition.get("lineage") or {}),
            "review_checklist": list(definition.get("review_checklist") or []),
            "role_guidance": dict(definition.get("role_guidance") or {}),
            "control_profile": dict(definition.get("control_profile") or {}),
            "supervisor_profile": dict(definition.get("supervisor_profile") or {}),
            "run_brief": str(definition.get("run_brief") or "").strip(),
            "bundle_manifest": dict(bundle_manifest),
            "definition": definition,
            "_sort_value": sort_value,
        }
        if asset_kind == "instance":
            resolved_flow_dir = resolve_flow_dir(workspace_root, asset_id)
            flow_state = read_flow_state(resolved_flow_dir)
            if flow_state:
                row.update(
                    {
                        "status": str(flow_state.get("status") or "").strip(),
                        "current_phase": str(flow_state.get("current_phase") or "").strip(),
                        "active_role_id": str(flow_state.get("active_role_id") or "").strip(),
                        "approval_state": str(flow_state.get("approval_state") or "").strip(),
                        "latest_judge_decision": dict(flow_state.get("latest_judge_decision") or {}),
                        "latest_operator_action": dict(flow_state.get("last_operator_action") or {}),
                    }
                )
        return row

    def _builtin_manage_rows(self, *, workspace_root: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for entry in builtin_flow_catalog():
            if bool(entry.get("synthetic")):
                continue
            asset_id = str(entry.get("flow_id") or "").strip()
            if not asset_id:
                continue
            path = self._asset_file_path(workspace_root=workspace_root, asset_kind="builtin", asset_id=asset_id)
            rows.append(
                self._definition_to_manage_row(
                    workspace_root=workspace_root,
                    asset_kind="builtin",
                    asset_id=asset_id,
                    payload=entry,
                    path=path,
                )
            )
        return rows

    def _template_manage_rows(self, *, workspace_root: str) -> list[dict[str, Any]]:
        root = template_asset_root(workspace_root)
        if not root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(root.glob("*.json")):
            payload = read_json(path)
            if not payload:
                continue
            asset_id = str(payload.get("flow_id") or payload.get("definition_id") or path.stem).strip() or path.stem
            rows.append(
                self._definition_to_manage_row(
                    workspace_root=workspace_root,
                    asset_kind="template",
                    asset_id=asset_id,
                    payload=payload,
                    path=path,
                )
            )
        return rows

    def build_catalog_payload(self) -> dict[str, Any]:
        return {"version": BUTLER_FLOW_VERSION, "items": self._flow_catalog_rows()}

    def build_new_setup_payload(self, args: argparse.Namespace) -> dict[str, Any]:
        draft = self._build_launch_draft_from_args(args, interactive_setup=False)
        return {
            "version": BUTLER_FLOW_VERSION,
            "launch_mode": str(draft.get("launch_mode") or DEFAULT_LAUNCH_MODE).strip(),
            "execution_level": str(draft.get("execution_level") or DEFAULT_EXECUTION_LEVEL).strip(),
            "catalog_flow_id": str(draft.get("catalog_flow_id") or DEFAULT_CATALOG_FLOW_ID).strip(),
            "goal": str(draft.get("goal") or "").strip(),
            "guard_condition": str(draft.get("guard_condition") or "").strip(),
            "catalog": self.build_catalog_payload(),
        }

    def _load_config(self, raw_config: str | None) -> tuple[dict[str, Any], str, str]:
        config_path = str(raw_config or "").strip() or resolve_default_config_path("butler_bot")
        cfg = load_active_config(config_path)
        workspace_root = str(cfg.get("workspace_root") or resolve_butler_root(Path.cwd())).strip() or str(resolve_butler_root(Path.cwd()))
        return cfg, config_path, workspace_root

    def _normalize_launch_mode(self, raw: Any) -> str:
        token = str(raw or "").strip().lower()
        if token in {LAUNCH_MODE_SINGLE, LAUNCH_MODE_FLOW}:
            return token
        return DEFAULT_LAUNCH_MODE

    def _normalize_execution_level(self, raw: Any) -> str:
        token = str(raw or "").strip().lower()
        if token in {EXECUTION_LEVEL_SIMPLE, EXECUTION_LEVEL_MEDIUM, EXECUTION_LEVEL_HIGH}:
            return token
        return DEFAULT_EXECUTION_LEVEL

    def _non_tty_launch_defaults(self, args: argparse.Namespace) -> tuple[str, str, str]:
        raw_launch_mode = str(getattr(args, "launch_mode", "") or "").strip()
        raw_execution_level = str(getattr(args, "execution_level", "") or "").strip()
        launch_mode = self._normalize_launch_mode(raw_launch_mode)
        execution_level = self._normalize_execution_level(raw_execution_level) if raw_execution_level else ""
        catalog_flow_id = str(getattr(args, "catalog_flow_id", "") or "").strip() or DEFAULT_CATALOG_FLOW_ID
        legacy_kind = str(getattr(args, "kind", "") or "").strip()
        if launch_mode == LAUNCH_MODE_FLOW:
            pass
        elif legacy_kind in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND}:
            launch_mode = LAUNCH_MODE_FLOW
            # Legacy `kind`-driven flow launches should still honor runtime defaults
            # when no new-style level picker choice was made.
            execution_level = ""
        elif legacy_kind == SINGLE_GOAL_KIND:
            launch_mode = LAUNCH_MODE_SINGLE
            execution_level = EXECUTION_LEVEL_SIMPLE
            catalog_flow_id = ""
        if launch_mode == LAUNCH_MODE_SINGLE:
            catalog_flow_id = ""
        elif not catalog_flow_id:
            catalog_flow_id = PROJECT_LOOP_CATALOG_FLOW_ID if legacy_kind == PROJECT_LOOP_KIND else DEFAULT_CATALOG_FLOW_ID
        legacy_mode = str(getattr(args, "execution_mode", "") or "").strip()
        if legacy_mode in {EXECUTION_LEVEL_SIMPLE, EXECUTION_LEVEL_MEDIUM, EXECUTION_LEVEL_HIGH}:
            execution_level = legacy_mode
        return launch_mode, execution_level, catalog_flow_id

    def _build_launch_draft_from_args(self, args: argparse.Namespace, *, interactive_setup: bool) -> dict[str, Any]:
        launch_mode, execution_level, catalog_flow_id = self._non_tty_launch_defaults(args)
        if interactive_setup:
            goal = str(getattr(args, "goal", "") or "").strip()
            guard_condition = str(getattr(args, "guard_condition", "") or "").strip()
            goal = self._prompt_value("goal: ", goal)
            launch_mode = self._choice_prompt(
                "mode",
                [("single", LAUNCH_MODE_SINGLE), ("flow", LAUNCH_MODE_FLOW)],
                default_value=launch_mode,
            )
            if launch_mode == LAUNCH_MODE_FLOW:
                execution_level = self._choice_prompt(
                    "level",
                    [("simple", EXECUTION_LEVEL_SIMPLE), ("medium", EXECUTION_LEVEL_MEDIUM), ("high (disabled)", EXECUTION_LEVEL_HIGH)],
                    default_value=execution_level,
                )
                catalog_flow_id = self._choice_prompt(
                    "flow",
                    [(str(row.get("label") or row.get("flow_id") or ""), str(row.get("flow_id") or "").strip()) for row in self._flow_catalog_rows()],
                    default_value=catalog_flow_id or DEFAULT_CATALOG_FLOW_ID,
                )
            else:
                execution_level = EXECUTION_LEVEL_SIMPLE
                catalog_flow_id = ""
            guard_default = (
                "If Codex is interrupted, continue until the goal is satisfied."
                if launch_mode == LAUNCH_MODE_SINGLE
                else "If Codex is interrupted, continue; advance until review passes."
            )
            guard_condition = self._prompt_value("guard condition: ", guard_condition or guard_default)
        else:
            goal = str(getattr(args, "goal", "") or "").strip()
            guard_condition = str(getattr(args, "guard_condition", "") or "").strip()
            if not launch_mode:
                launch_mode = DEFAULT_LAUNCH_MODE
            if launch_mode == LAUNCH_MODE_SINGLE:
                execution_level = EXECUTION_LEVEL_SIMPLE
                catalog_flow_id = ""
            elif not catalog_flow_id:
                catalog_flow_id = DEFAULT_CATALOG_FLOW_ID
            if not guard_condition:
                guard_condition = (
                    "If Codex is interrupted, continue until the goal is satisfied."
                    if launch_mode == LAUNCH_MODE_SINGLE
                    else "If Codex is interrupted, continue; advance until review passes."
                )
        return {
            "launch_mode": launch_mode,
            "execution_level": execution_level,
            "catalog_flow_id": catalog_flow_id,
            "goal": goal,
            "guard_condition": guard_condition,
            "max_attempts": getattr(args, "max_attempts", None),
            "max_phase_attempts": getattr(args, "max_phase_attempts", None),
            "role_pack_id": str(getattr(args, "role_pack", "") or "").strip(),
        }

    def _apply_role_runtime_args(
        self,
        flow_state: dict[str, Any],
        *,
        cfg: dict[str, Any],
        args: argparse.Namespace,
        prefer_existing: bool,
    ) -> None:
        workflow_kind = str(flow_state.get("workflow_kind") or "").strip()
        raw_execution_mode = str(getattr(args, "execution_mode", "") or "").strip()
        raw_role_pack = str(getattr(args, "role_pack", "") or "").strip()
        if raw_execution_mode:
            execution_mode = normalize_execution_mode(raw_execution_mode)
        elif prefer_existing and str(flow_state.get("execution_mode") or "").strip():
            execution_mode = normalize_execution_mode(flow_state.get("execution_mode"))
        else:
            execution_mode = default_execution_mode(cfg, workflow_kind=workflow_kind)
        if raw_role_pack:
            role_pack_id = normalize_role_pack_id(raw_role_pack, workflow_kind=workflow_kind)
        elif prefer_existing and str(flow_state.get("role_pack_id") or "").strip():
            role_pack_id = normalize_role_pack_id(flow_state.get("role_pack_id"), workflow_kind=workflow_kind)
        else:
            role_pack_id = default_role_pack_id(cfg, workflow_kind=workflow_kind)
        flow_state["execution_mode"] = execution_mode
        flow_state["session_strategy"] = normalize_session_strategy(
            flow_state.get("session_strategy"),
            execution_mode=execution_mode,
        )
        flow_state["role_pack_id"] = role_pack_id
        existing_execution_context = str(flow_state.get("execution_context") or "").strip()
        flow_state["execution_context"] = normalize_execution_context(
            "" if raw_role_pack or not existing_execution_context else existing_execution_context,
            role_pack_id=role_pack_id,
            workflow_kind=workflow_kind,
        )

    def _save_design_session(self, flow_path: Path, payload: dict[str, Any]) -> None:
        write_json_atomic(design_session_path(flow_path), dict(payload or {}))

    def _emit_manage_handoff_ready(self, *, flow_path: Path, flow_state: dict[str, Any], payload: dict[str, Any]) -> None:
        summary = str(dict(payload or {}).get("summary") or "managed flow ready").strip()
        self._runtime._emit_ui_event(
            kind="manage_handoff_ready",
            flow_dir_path=flow_path,
            flow_id=str(flow_state.get("workflow_id") or flow_path.name).strip(),
            phase=str(flow_state.get("current_phase") or "").strip(),
            attempt_no=safe_int(flow_state.get("attempt_count"), 0),
            message=summary,
            payload=dict(payload or {}),
            hook_name="on_manage_handoff",
        )

    def _save_design_draft(self, flow_path: Path, payload: dict[str, Any]) -> None:
        write_json_atomic(design_draft_path(flow_path), dict(payload or {}))

    def _append_design_turn(self, flow_path: Path, payload: dict[str, Any]) -> None:
        append_jsonl(design_turns_path(flow_path), dict(payload or {}))

    def _apply_launch_draft_to_flow_state(self, flow_state: dict[str, Any], *, cfg: dict[str, Any], draft: dict[str, Any]) -> None:
        launch_mode = self._normalize_launch_mode(draft.get("launch_mode"))
        raw_execution_level = str(draft.get("execution_level") or "").strip().lower()
        execution_level = self._normalize_execution_level(raw_execution_level) if raw_execution_level else ""
        catalog_flow_id = str(draft.get("catalog_flow_id") or "").strip()
        flow_state["launch_mode"] = launch_mode
        flow_state["catalog_flow_id"] = catalog_flow_id
        flow_state["goal"] = str(draft.get("goal") or flow_state.get("goal") or "").strip()
        flow_state["guard_condition"] = str(draft.get("guard_condition") or flow_state.get("guard_condition") or "").strip()
        raw_role_pack = str(draft.get("role_pack_id") or "").strip()
        flow_state["role_guidance"] = {}
        if launch_mode == LAUNCH_MODE_SINGLE:
            flow_state["workflow_kind"] = SINGLE_GOAL_KIND
            flow_state["phase_plan"] = resolve_phase_plan({"workflow_kind": SINGLE_GOAL_KIND})
            flow_state["current_phase"] = first_phase_id(list(flow_state.get("phase_plan") or []), workflow_kind=SINGLE_GOAL_KIND)
            flow_state["execution_mode"] = EXECUTION_MODE_SIMPLE
            flow_state["session_strategy"] = session_strategy_for_mode(EXECUTION_MODE_SIMPLE)
            flow_state["role_pack_id"] = normalize_role_pack_id(raw_role_pack or default_role_pack_id(cfg, workflow_kind=SINGLE_GOAL_KIND), workflow_kind=SINGLE_GOAL_KIND)
            flow_state["execution_context"] = normalize_execution_context(
                "",
                role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
                workflow_kind=SINGLE_GOAL_KIND,
            )
            return
        if execution_level == EXECUTION_LEVEL_HIGH:
            raise ValueError("execution level `high` is coming soon and cannot be launched yet")
        if catalog_flow_id == FREE_CATALOG_FLOW_ID:
            flow_state["workflow_kind"] = MANAGED_FLOW_KIND
            flow_state["phase_plan"] = normalize_phase_plan(
                draft.get("phase_plan") if isinstance(draft.get("phase_plan"), list) else None,
                workflow_kind=MANAGED_FLOW_KIND,
            )
            flow_state["source_asset_key"] = ""
            flow_state["source_asset_kind"] = ""
            flow_state["source_asset_version"] = ""
            flow_state["review_checklist"] = []
            flow_state["role_guidance"] = {}
            flow_state["bundle_manifest"] = {}
        elif catalog_flow_id.startswith("template:"):
            template_id = str(catalog_flow_id.split(":", 1)[1] or "").strip()
            if not template_id:
                raise ValueError("template launch requires a template asset id")
            template_definition = read_json(
                self._asset_file_path(
                    workspace_root=str(flow_state.get("workspace_root") or "").strip(),
                    asset_kind="template",
                    asset_id=template_id,
                )
            )
            if not template_definition:
                raise ValueError(f"unknown template flow: {template_id}")
            template_definition = self._normalize_asset_definition(
                template_definition,
                asset_kind="template",
                asset_id=template_id,
            )
            flow_state["workflow_kind"] = coerce_workflow_kind(str(template_definition.get("workflow_kind") or MANAGED_FLOW_KIND))
            flow_state["phase_plan"] = normalize_phase_plan(
                template_definition.get("phase_plan") if isinstance(template_definition.get("phase_plan"), list) else None,
                workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
            )
            raw_role_pack = raw_role_pack or str(
                template_definition.get("role_pack_id") or template_definition.get("default_role_pack") or ""
            ).strip()
            if not flow_state.get("goal"):
                flow_state["goal"] = str(template_definition.get("goal") or "").strip()
            if not flow_state.get("guard_condition"):
                flow_state["guard_condition"] = str(template_definition.get("guard_condition") or "").strip()
            flow_state["source_asset_key"] = self._manage_target_key("template", template_id)
            flow_state["source_asset_kind"] = "template"
            flow_state["source_asset_version"] = str(template_definition.get("version") or "").strip()
            flow_state["review_checklist"] = list(template_definition.get("review_checklist") or [])
            flow_state["role_guidance"] = dict(template_definition.get("role_guidance") or {})
            flow_state["bundle_manifest"] = self._runtime_bundle_manifest(
                workspace_root=str(flow_state.get("workspace_root") or "").strip(),
                asset_kind="template",
                asset_id=template_id,
                definition=template_definition,
            )
        else:
            entry = catalog_entry(catalog_flow_id or PROJECT_LOOP_CATALOG_FLOW_ID)
            if not entry:
                raise ValueError(f"unknown catalog flow: {catalog_flow_id or PROJECT_LOOP_CATALOG_FLOW_ID}")
            flow_state["workflow_kind"] = coerce_workflow_kind(str(entry.get("workflow_kind") or PROJECT_LOOP_KIND))
            flow_state["phase_plan"] = normalize_phase_plan(
                entry.get("phase_plan") if isinstance(entry.get("phase_plan"), list) else None,
                workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
            )
            raw_role_pack = raw_role_pack or str(entry.get("default_role_pack") or "").strip()
            builtin_id = str(entry.get("flow_id") or catalog_flow_id or PROJECT_LOOP_CATALOG_FLOW_ID).strip()
            flow_state["source_asset_key"] = self._manage_target_key("builtin", builtin_id)
            flow_state["source_asset_kind"] = "builtin"
            flow_state["source_asset_version"] = str(entry.get("version") or "").strip()
            flow_state["review_checklist"] = list(entry.get("review_checklist") or [])
            flow_state["role_guidance"] = normalize_role_guidance_payload(entry.get("role_guidance") or {})
            flow_state["bundle_manifest"] = self._runtime_bundle_manifest(
                workspace_root=str(flow_state.get("workspace_root") or "").strip(),
                asset_kind="builtin",
                asset_id=builtin_id,
                definition=entry,
            )
        flow_state["current_phase"] = first_phase_id(
            list(flow_state.get("phase_plan") or []),
            workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
        )
        flow_state["execution_mode"] = (
            default_execution_mode(cfg, workflow_kind=str(flow_state.get("workflow_kind") or "").strip())
            if not execution_level
            else (EXECUTION_MODE_MEDIUM if execution_level == EXECUTION_LEVEL_MEDIUM else EXECUTION_MODE_SIMPLE)
        )
        flow_state["session_strategy"] = session_strategy_for_mode(str(flow_state.get("execution_mode") or "").strip())
        flow_state["role_pack_id"] = normalize_role_pack_id(
            raw_role_pack or default_role_pack_id(cfg, workflow_kind=str(flow_state.get("workflow_kind") or "").strip()),
            workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
        )
        flow_state["execution_context"] = normalize_execution_context(
            "",
            role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
            workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
        )

    def _design_session_seed(self, flow_state: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any]:
        return {
            "flow_id": str(flow_state.get("workflow_id") or "").strip(),
            "designer_session_id": "",
            "design_stage": "proposal",
            "design_status": "drafting",
            "selected_mode": str(draft.get("launch_mode") or "").strip(),
            "selected_level": str(draft.get("execution_level") or "").strip(),
            "source_kind": str(draft.get("catalog_flow_id") or "").strip(),
            "active_draft_ref": design_draft_path(Path(".")).name,
            "last_review_summary": "",
            "created_at": str(flow_state.get("created_at") or now_text()).strip(),
            "updated_at": now_text(),
        }

    def _run_free_design_loop(
        self,
        *,
        cfg: dict[str, Any],
        workspace_root: str,
        flow_path: Path,
        flow_state: dict[str, Any],
        draft: dict[str, Any],
        interactive: bool,
    ) -> dict[str, Any]:
        session = self._design_session_seed(flow_state, draft)
        session["active_draft_ref"] = design_draft_path(flow_path).name
        self._save_design_session(flow_path, session)
        review_issues: list[str] = []
        proposal_instruction = str(draft.get("goal") or "").strip()
        proposal: dict[str, Any] = {}
        while True:
            proposal = run_design_stage(
                cfg=cfg,
                workspace_root=workspace_root,
                run_prompt_receipt_fn=self._run_prompt_receipt_fn,
                flow_state=flow_state,
                stage="proposal",
                goal=str(draft.get("goal") or "").strip(),
                guard_condition=str(draft.get("guard_condition") or "").strip(),
                instruction=proposal_instruction,
            )
            session["designer_session_id"] = str(proposal.get("designer_session_id") or session.get("designer_session_id") or "").strip()
            session["design_stage"] = "proposal"
            session["design_status"] = "waiting_user"
            session["updated_at"] = now_text()
            self._save_design_session(flow_path, session)
            self._append_design_turn(flow_path, {"stage": "proposal", "payload": proposal, "created_at": now_text()})
            if not interactive:
                break
            self._display.write(f"[butler-flow design:proposal] {proposal.get('summary') or '-'}")
            proposal_action = self._choice_prompt(
                "proposal action",
                [("confirm", "confirm"), ("revise", "revise")],
                default_value="confirm",
            )
            if proposal_action == "confirm":
                break
            proposal_instruction = str(self._input_fn("proposal revision: ")).strip() or proposal_instruction
        build_instruction = str(draft.get("goal") or "").strip()
        build_round = 0
        while True:
            build_round += 1
            built = run_design_stage(
                cfg=cfg,
                workspace_root=workspace_root,
                run_prompt_receipt_fn=self._run_prompt_receipt_fn,
                flow_state=flow_state,
                stage="build",
                goal=str(proposal.get("goal") or draft.get("goal") or "").strip(),
                guard_condition=str(proposal.get("guard_condition") or draft.get("guard_condition") or "").strip(),
                instruction=build_instruction,
                proposal=proposal,
                draft=read_json(design_draft_path(flow_path)),
                review_issues=review_issues,
            )
            session["designer_session_id"] = str(built.get("designer_session_id") or session.get("designer_session_id") or "").strip()
            session["design_stage"] = "build"
            session["design_status"] = "waiting_user"
            session["updated_at"] = now_text()
            self._save_design_session(flow_path, session)
            self._save_design_draft(flow_path, dict(built))
            self._append_design_turn(flow_path, {"stage": "build", "payload": built, "created_at": now_text(), "round": build_round})
            if interactive:
                self._display.write(f"[butler-flow design:build] {built.get('summary') or '-'}")
                build_action = self._choice_prompt(
                    "build action",
                    [("confirm", "confirm"), ("revise", "revise")],
                    default_value="confirm",
                )
                if build_action == "revise":
                    build_instruction = str(self._input_fn("build revision: ")).strip() or build_instruction
                    review_issues = []
                    continue
            review = run_design_stage(
                cfg=cfg,
                workspace_root=workspace_root,
                run_prompt_receipt_fn=self._run_prompt_receipt_fn,
                flow_state=flow_state,
                stage="review",
                goal=str(built.get("goal") or proposal.get("goal") or draft.get("goal") or "").strip(),
                guard_condition=str(built.get("guard_condition") or proposal.get("guard_condition") or draft.get("guard_condition") or "").strip(),
                instruction=build_instruction,
                proposal=proposal,
                draft=built,
                review_issues=review_issues,
            )
            session["designer_session_id"] = str(review.get("designer_session_id") or session.get("designer_session_id") or "").strip()
            session["design_stage"] = "review"
            session["last_review_summary"] = str(review.get("summary") or "").strip()
            session["updated_at"] = now_text()
            self._append_design_turn(flow_path, {"stage": "review", "payload": review, "created_at": now_text(), "round": build_round})
            if bool(review.get("approved")):
                session["design_stage"] = "approved"
                session["design_status"] = "approved"
                self._save_design_session(flow_path, session)
                return built
            review_issues = [str(item or "").strip() for item in list(review.get("issues") or []) if str(item or "").strip()]
            if not review_issues:
                review_issues = [str(review.get("summary") or "review requested another build pass").strip()]
            session["design_status"] = "needs_build_revision"
            self._save_design_session(flow_path, session)
            if not interactive and build_round >= 2:
                raise RuntimeError(str(review.get("summary") or "free flow review did not approve the generated draft"))
            if interactive:
                self._display.write(f"[butler-flow design:review] {review.get('summary') or '-'}")
                extra = str(self._input_fn("build follow-up (optional): ")).strip()
                if extra:
                    review_issues.append(extra)

    @staticmethod
    def _normalize_flow_status(status: str) -> str:
        token = str(status or "").strip().lower()
        if token in {"done", "complete"}:
            return "completed"
        return token

    def _effective_runtime_view(
        self,
        *,
        flow_state: dict[str, Any],
        runtime_snapshot: dict[str, Any],
    ) -> tuple[str, str]:
        raw_status = self._normalize_flow_status(flow_state.get("status") or "")
        raw_phase = str(flow_state.get("current_phase") or "").strip()
        process_state = str(runtime_snapshot.get("process_state") or "").strip().lower()
        watchdog_state = str(runtime_snapshot.get("watchdog_state") or "").strip().lower()
        run_state = self._normalize_flow_status(runtime_snapshot.get("run_state") or "")
        runtime_phase = str(runtime_snapshot.get("phase") or "").strip()

        if raw_status in {"completed", "failed", "interrupted", "paused"}:
            return raw_status or "pending", raw_phase
        if process_state == "stale":
            return "stale", runtime_phase or raw_phase
        if process_state == "stopped":
            if run_state in {"completed", "failed", "interrupted"} and raw_status in {"", "pending", "running"}:
                return run_state, runtime_phase or raw_phase
            if raw_status in {"running"} or run_state == "running" or watchdog_state == "foreground":
                return "stopped", runtime_phase or raw_phase
        if process_state == "running":
            return "running", runtime_phase or raw_phase
        if run_state in {"completed", "failed", "interrupted"} and raw_status in {"", "pending", "running"}:
            return run_state, runtime_phase or raw_phase
        if run_state == "running" or watchdog_state == "foreground":
            return "running", runtime_phase or raw_phase
        return raw_status or "pending", runtime_phase or raw_phase

    def _flow_rows(self, *, workspace_root: str, limit: int = DEFAULT_FLOW_LIST_LIMIT) -> list[dict[str, Any]]:
        roots = [build_flow_root(workspace_root), legacy_flow_root(workspace_root)]
        rows: list[dict[str, Any]] = []
        seen_flow_ids: set[str] = set()
        for shell_root in roots:
            if not shell_root.exists():
                continue
            for flow_path in sorted(shell_root.iterdir()):
                if not flow_path.is_dir():
                    continue
                state_path = flow_state_path(flow_path)
                if not state_path.exists():
                    state_path = legacy_flow_state_path(flow_path)
                flow_state = read_flow_state(flow_path)
                if not flow_state:
                    continue
                flow_id = str(flow_state.get("workflow_id") or flow_path.name).strip()
                if not flow_id or flow_id in seen_flow_ids:
                    continue
                seen_flow_ids.add(flow_id)
                state_store = FileRuntimeStateStore(flow_path)
                snapshot = state_store.status_snapshot(enabled=True, stale_seconds=600, tracked_pid=state_store.read_pid())
                runtime_snapshot = {
                    "config_state": snapshot.config_state,
                    "process_state": snapshot.process_state,
                    "watchdog_state": snapshot.watchdog_state,
                    "run_state": snapshot.run_state,
                    "progress_state": snapshot.progress_state,
                    "pid": snapshot.pid,
                    "run_id": snapshot.run_id,
                    "phase": snapshot.phase,
                    "updated_at": snapshot.updated_at,
                    "note": snapshot.note,
                }
                effective_status, effective_phase = self._effective_runtime_view(flow_state=flow_state, runtime_snapshot=runtime_snapshot)
                sort_value = 0.0
                for field in ("updated_at", "created_at"):
                    stamp = str(flow_state.get(field) or "").strip()
                    if not stamp:
                        continue
                    try:
                        sort_value = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").timestamp()
                        break
                    except Exception:
                        continue
                if sort_value <= 0:
                    try:
                        sort_value = state_path.stat().st_mtime
                    except Exception:
                        sort_value = 0.0
                rows.append(
                    {
                        "flow_id": flow_id,
                        "flow_dir": str(flow_path),
                        "flow_kind": str(flow_state.get("workflow_kind") or "").strip(),
                        "status": str(flow_state.get("status") or "").strip(),
                        "effective_status": effective_status,
                        "current_phase": str(flow_state.get("current_phase") or "").strip(),
                        "effective_phase": effective_phase,
                        "active_role_id": str(flow_state.get("active_role_id") or "").strip(),
                        "execution_mode": str(flow_state.get("execution_mode") or "").strip(),
                        "session_strategy": str(flow_state.get("session_strategy") or "").strip(),
                        "role_pack_id": str(flow_state.get("role_pack_id") or "").strip(),
                        "attempt_count": safe_int(flow_state.get("attempt_count"), 0),
                        "max_attempts": safe_int(flow_state.get("max_attempts"), 0),
                        "codex_session_id": str(flow_state.get("codex_session_id") or "").strip(),
                        "updated_at": str(flow_state.get("updated_at") or flow_state.get("created_at") or "").strip(),
                        "goal": str(flow_state.get("goal") or "").strip(),
                        "runtime_snapshot": runtime_snapshot,
                        "_sort_value": float(sort_value),
                    }
                )
        rows.sort(key=lambda item: item.get("_sort_value") or 0.0, reverse=True)
        return rows[: max(1, int(limit or DEFAULT_FLOW_LIST_LIMIT))]

    def _resolve_recent_flow_id(self, *, workspace_root: str) -> str:
        rows = self._flow_rows(workspace_root=workspace_root, limit=1)
        if not rows:
            raise FileNotFoundError("no local butler-flow state found")
        return str(rows[0].get("flow_id") or "").strip()

    def _flow_identity_from_args(self, *, workspace_root: str, args: argparse.Namespace) -> str:
        flow_id = str(getattr(args, "flow_id", "") or "").strip()
        if not flow_id:
            flow_id = str(getattr(args, "workflow_id", "") or "").strip()
        if flow_id:
            return flow_id
        if bool(getattr(args, "last", False)):
            return self._resolve_recent_flow_id(workspace_root=workspace_root)
        return ""

    def _flow_status_payload(self, *, workspace_root: str, flow_id: str) -> dict[str, Any]:
        flow_path = resolve_flow_dir(workspace_root, flow_id)
        state_path = flow_state_path(flow_path)
        flow_state = read_flow_state(flow_path)
        if not flow_state:
            raise FileNotFoundError(f"flow not found: {flow_id}")
        if not state_path.exists():
            self._save_flow_state(flow_path, flow_state)
        state_store = FileRuntimeStateStore(flow_path)
        trace_store = FileTraceStore(state_store.traces_dir())
        trace_summary = trace_store.summarize(flow_id)
        snapshot = state_store.status_snapshot(enabled=True, stale_seconds=600, tracked_pid=state_store.read_pid())
        effective_status, effective_phase = self._effective_runtime_view(
            flow_state=flow_state,
            runtime_snapshot={
                "process_state": snapshot.process_state,
                "watchdog_state": snapshot.watchdog_state,
                "run_state": snapshot.run_state,
                "phase": snapshot.phase,
            },
        )
        return {
            "flow_id": flow_id,
            "flow_dir": str(flow_path),
            "flow_state": flow_state,
            "role_runtime": extract_role_runtime_summary(flow_state),
            "runtime_snapshot": {
                "config_state": snapshot.config_state,
                "process_state": snapshot.process_state,
                "watchdog_state": snapshot.watchdog_state,
                "run_state": snapshot.run_state,
                "progress_state": snapshot.progress_state,
                "pid": snapshot.pid,
                "run_id": snapshot.run_id,
                "phase": snapshot.phase,
                "updated_at": snapshot.updated_at,
                "note": snapshot.note,
            },
            "effective_status": effective_status,
            "effective_phase": effective_phase,
            "trace_summary": {
                "progress_counter": trace_summary.progress_counter,
                "retry_count": trace_summary.retry_count,
                "fallback_count": trace_summary.fallback_count,
                "timeout_count": trace_summary.timeout_count,
                "degrade_count": trace_summary.degrade_count,
            },
        }

    def _normalize_flow_state_payload(self, flow_state: dict[str, Any]) -> dict[str, Any]:
        raw_workflow_kind = str(flow_state.get("workflow_kind") or "").strip() or SINGLE_GOAL_KIND
        workflow_kind = coerce_workflow_kind(raw_workflow_kind)
        flow_state["workflow_kind"] = workflow_kind
        if workflow_kind == SINGLE_GOAL_KIND:
            phase_plan = resolve_phase_plan({"workflow_kind": workflow_kind})
        else:
            phase_plan = normalize_phase_plan(flow_state.get("phase_plan") if isinstance(flow_state.get("phase_plan"), list) else None, workflow_kind=workflow_kind)
        flow_state["phase_plan"] = phase_plan
        valid_phase_ids = set(phase_ids(phase_plan))
        current_phase = str(flow_state.get("current_phase") or "").strip()
        if current_phase not in valid_phase_ids:
            flow_state["current_phase"] = first_phase_id(phase_plan, workflow_kind=workflow_kind)
        flow_state["entry_mode"] = str(flow_state.get("entry_mode") or workflow_kind).strip() or workflow_kind
        flow_state["execution_mode"] = normalize_execution_mode(flow_state.get("execution_mode"))
        flow_state["session_strategy"] = normalize_session_strategy(
            flow_state.get("session_strategy"),
            execution_mode=str(flow_state.get("execution_mode") or "").strip(),
        )
        flow_state["role_pack_id"] = normalize_role_pack_id(
            flow_state.get("role_pack_id"),
            workflow_kind=workflow_kind,
        )
        flow_state["execution_context"] = normalize_execution_context(
            flow_state.get("execution_context"),
            role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
            workflow_kind=workflow_kind,
        )
        flow_state["control_profile"] = normalize_control_profile_payload(
            flow_state.get("control_profile"),
            current={},
            workflow_kind=workflow_kind,
            role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
            execution_mode=str(flow_state.get("execution_mode") or "").strip(),
            execution_context=str(flow_state.get("execution_context") or "").strip(),
        )
        flow_state["role_guidance"] = normalize_role_guidance_payload(flow_state.get("role_guidance") or {})
        flow_state["doctor_policy"] = normalize_doctor_policy_payload(flow_state.get("doctor_policy"), current={})
        flow_state["supervisor_profile"] = normalize_supervisor_profile_payload(
            flow_state.get("supervisor_profile"),
            current={},
        )
        flow_state["run_brief"] = str(flow_state.get("run_brief") or "").strip()
        flow_state["source_bindings"] = normalize_source_items(flow_state.get("source_bindings") or [])
        flow_state["flow_version"] = str(flow_state.get("flow_version") or BUTLER_FLOW_VERSION).strip() or BUTLER_FLOW_VERSION
        return flow_state

    def _save_flow_definition(self, flow_path: Path, flow_state: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "definition_id": str(flow_state.get("workflow_id") or flow_path.name).strip(),
            "flow_id": str(flow_state.get("workflow_id") or flow_path.name).strip(),
            "label": str(flow_state.get("label") or flow_state.get("workflow_id") or flow_path.name).strip(),
            "description": str(flow_state.get("description") or "").strip(),
            "workflow_kind": str(flow_state.get("workflow_kind") or "").strip(),
            "entry_mode": str(flow_state.get("entry_mode") or flow_state.get("workflow_kind") or "").strip(),
            "launch_mode": str(flow_state.get("launch_mode") or "").strip(),
            "catalog_flow_id": str(flow_state.get("catalog_flow_id") or "").strip(),
            "execution_mode": str(flow_state.get("execution_mode") or "").strip(),
            "session_strategy": str(flow_state.get("session_strategy") or "").strip(),
            "role_pack_id": str(flow_state.get("role_pack_id") or "").strip(),
            "execution_context": str(flow_state.get("execution_context") or "").strip(),
            "goal": str(flow_state.get("goal") or "").strip(),
            "guard_condition": str(flow_state.get("guard_condition") or "").strip(),
            "phase_plan": list(flow_state.get("phase_plan") or []),
            "risk_level": str(flow_state.get("risk_level") or "normal").strip() or "normal",
            "autonomy_profile": str(flow_state.get("autonomy_profile") or "default").strip() or "default",
            "manager_handoff": dict(flow_state.get("manage_handoff") or {}),
            "control_profile": dict(flow_state.get("control_profile") or {}),
            "review_checklist": list(flow_state.get("review_checklist") or []),
            "role_guidance": dict(flow_state.get("role_guidance") or {}),
            "doctor_policy": dict(flow_state.get("doctor_policy") or {}),
            "supervisor_profile": dict(flow_state.get("supervisor_profile") or {}),
            "run_brief": str(flow_state.get("run_brief") or "").strip(),
            "source_bindings": list(flow_state.get("source_bindings") or []),
            "bundle_manifest": dict(flow_state.get("bundle_manifest") or {}),
            "source_asset_key": str(flow_state.get("source_asset_key") or "").strip(),
            "source_asset_kind": str(flow_state.get("source_asset_kind") or "").strip(),
            "source_asset_version": str(flow_state.get("source_asset_version") or "").strip(),
            "version": str(flow_state.get("flow_version") or BUTLER_FLOW_VERSION).strip() or BUTLER_FLOW_VERSION,
            "created_at": str(flow_state.get("created_at") or now_text()).strip(),
            "updated_at": now_text(),
        }
        write_json_atomic(flow_definition_path(flow_path), payload)
        return payload

    def _save_flow_state(self, flow_path: Path, flow_state: dict[str, Any]) -> None:
        self._normalize_flow_state_payload(flow_state)
        workflow_id = str(flow_state.get("workflow_id") or flow_path.name).strip() or flow_path.name
        bundle_manifest = self._runtime_bundle_manifest(
            workspace_root=str(flow_state.get("workspace_root") or "").strip(),
            asset_kind="instance",
            asset_id=workflow_id,
            definition=flow_state,
        )
        ensure_asset_bundle_files(
            str(flow_state.get("workspace_root") or "").strip(),
            asset_kind="instance",
            asset_id=workflow_id,
            definition={**flow_state, "bundle_manifest": bundle_manifest},
        )
        write_bundle_sources(
            str(flow_state.get("workspace_root") or "").strip(),
            asset_kind="instance",
            asset_id=workflow_id,
            items=list(flow_state.get("source_bindings") or []),
            metadata={"source_asset_key": str(flow_state.get("source_asset_key") or "").strip()},
        )
        write_compiled_supervisor_knowledge(
            str(flow_state.get("workspace_root") or "").strip(),
            asset_kind="instance",
            asset_id=workflow_id,
            definition=flow_state,
        )
        flow_state["bundle_manifest"] = bundle_manifest
        flow_state["updated_at"] = now_text()
        write_json_atomic(flow_state_path(flow_path), flow_state)
        self._save_flow_definition(flow_path, flow_state)

    def _append_manage_audit(
        self,
        *,
        workspace_root: str,
        asset_kind: str,
        asset_id: str,
        mutation: str,
        summary: str,
    ) -> None:
        append_jsonl(
            flow_asset_audit_path(workspace_root),
            {
                "created_at": now_text(),
                "asset_kind": str(asset_kind or "").strip(),
                "asset_id": str(asset_id or "").strip(),
                "mutation": str(mutation or "").strip(),
                "summary": str(summary or "").strip(),
            },
        )

    def _asset_definition_to_flow_state(
        self,
        *,
        workspace_root: str,
        asset_id: str,
        definition: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = self._normalize_asset_definition(definition, asset_kind="instance", asset_id=asset_id)
        flow_state = new_flow_state(
            workflow_id=asset_id,
            workflow_kind=str(normalized.get("workflow_kind") or MANAGED_FLOW_KIND).strip(),
            workspace_root=workspace_root,
            goal=str(normalized.get("goal") or "").strip(),
            guard_condition=str(normalized.get("guard_condition") or "").strip(),
            max_attempts=DEFAULT_PROJECT_LOOP_MAX_ATTEMPTS,
            max_phase_attempts=DEFAULT_PROJECT_PHASE_MAX_ATTEMPTS,
            launch_mode=str(normalized.get("launch_mode") or LAUNCH_MODE_FLOW).strip() or LAUNCH_MODE_FLOW,
            catalog_flow_id=str(normalized.get("catalog_flow_id") or FREE_CATALOG_FLOW_ID).strip() or FREE_CATALOG_FLOW_ID,
        )
        flow_state["phase_plan"] = list(normalized.get("phase_plan") or flow_state.get("phase_plan") or [])
        flow_state["current_phase"] = first_phase_id(
            list(flow_state.get("phase_plan") or []),
            workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
        )
        flow_state["execution_mode"] = str(normalized.get("execution_mode") or flow_state.get("execution_mode") or "").strip()
        flow_state["session_strategy"] = str(normalized.get("session_strategy") or flow_state.get("session_strategy") or "").strip()
        flow_state["role_pack_id"] = str(normalized.get("role_pack_id") or flow_state.get("role_pack_id") or "").strip()
        flow_state["execution_context"] = str(normalized.get("execution_context") or flow_state.get("execution_context") or "").strip()
        flow_state["risk_level"] = str(normalized.get("risk_level") or "normal").strip() or "normal"
        flow_state["autonomy_profile"] = str(normalized.get("autonomy_profile") or "default").strip() or "default"
        flow_state["manage_handoff"] = dict(normalized.get("manager_handoff") or {})
        flow_state["review_checklist"] = list(normalized.get("review_checklist") or [])
        flow_state["role_guidance"] = dict(normalized.get("role_guidance") or {})
        flow_state["control_profile"] = dict(normalized.get("control_profile") or {})
        flow_state["doctor_policy"] = dict(normalized.get("doctor_policy") or {})
        flow_state["supervisor_profile"] = dict(normalized.get("supervisor_profile") or {})
        flow_state["run_brief"] = str(normalized.get("run_brief") or "").strip()
        flow_state["source_bindings"] = list(normalized.get("source_bindings") or [])
        flow_state["bundle_manifest"] = dict(normalized.get("bundle_manifest") or {})
        flow_state["source_asset_key"] = str(normalized.get("source_asset_key") or "").strip()
        flow_state["source_asset_kind"] = str(normalized.get("source_asset_kind") or "").strip()
        flow_state["source_asset_version"] = str(normalized.get("source_asset_version") or "").strip()
        flow_state["entry_mode"] = "manage"
        flow_state["flow_version"] = str(normalized.get("version") or BUTLER_FLOW_VERSION).strip() or BUTLER_FLOW_VERSION
        return flow_state

    def _save_managed_asset_definition(
        self,
        *,
        workspace_root: str,
        asset_kind: str,
        asset_id: str,
        existing: dict[str, Any],
        result: dict[str, Any],
        flow_state: dict[str, Any] | None = None,
        lineage: dict[str, Any] | None = None,
        asset_state: dict[str, Any] | None = None,
    ) -> tuple[Path, dict[str, Any]]:
        existing = dict(existing or {})
        path = self._asset_file_path(workspace_root=workspace_root, asset_kind=asset_kind, asset_id=asset_id)
        merged_lineage = dict(existing.get("lineage") or {})
        if lineage:
            merged_lineage.update(dict(lineage))
        merged_asset_state = dict(existing.get("asset_state") or {})
        if asset_state:
            merged_asset_state.update(dict(asset_state))
        if not str(merged_asset_state.get("status") or "").strip():
            merged_asset_state["status"] = "active"
        if not str(merged_asset_state.get("stage") or "").strip():
            merged_asset_state["stage"] = str(result.get("manage_stage") or "committed").strip() or "committed"
        review_checklist = [
            str(item or "").strip()
            for item in list(result.get("review_checklist") or existing.get("review_checklist") or [])
            if str(item or "").strip()
        ]
        role_guidance = normalize_role_guidance_payload(
            result.get("role_guidance") or {},
            current=dict(existing.get("role_guidance") or dict(existing.get("manager_handoff") or {}).get("role_guidance") or {}),
        )
        doctor_policy = normalize_doctor_policy_payload(
            result.get("doctor_policy"),
            current=dict(existing.get("doctor_policy") or dict(existing.get("manager_handoff") or {}).get("doctor_policy") or {}),
        )
        supervisor_profile = normalize_supervisor_profile_payload(
            result.get("supervisor_profile"),
            current=dict(existing.get("supervisor_profile") or dict(existing.get("manager_handoff") or {}).get("supervisor_profile") or {}),
        )
        control_profile = normalize_control_profile_payload(
            result.get("control_profile"),
            current=dict(existing.get("control_profile") or dict(existing.get("manager_handoff") or {}).get("control_profile") or {}),
            workflow_kind=str(result.get("workflow_kind") or existing.get("workflow_kind") or MANAGED_FLOW_KIND).strip(),
            role_pack_id=str((flow_state or {}).get("role_pack_id") or existing.get("role_pack_id") or existing.get("default_role_pack") or "coding_flow").strip(),
            execution_mode=str((flow_state or {}).get("execution_mode") or existing.get("execution_mode") or "").strip(),
            execution_context=str((flow_state or {}).get("execution_context") or existing.get("execution_context") or "").strip(),
        )
        run_brief = str(result.get("run_brief") or existing.get("run_brief") or "").strip()
        source_bindings = normalize_source_items(
            result.get("source_bindings") or result.get("source_items") or [],
            current=list(existing.get("source_bindings") or []),
        )
        bundle_manifest = dict(existing.get("bundle_manifest") or {})
        if asset_kind in {"builtin", "template", "instance"}:
            bundle_manifest = self._runtime_bundle_manifest(
                workspace_root=workspace_root,
                asset_kind=asset_kind,
                asset_id=asset_id,
                definition={**existing, "bundle_manifest": bundle_manifest},
            )
        instance_defaults = dict(result.get("instance_defaults") or existing.get("instance_defaults") or {})
        if not instance_defaults:
            instance_defaults = {
                "execution_mode": str((flow_state or {}).get("execution_mode") or existing.get("execution_mode") or "").strip(),
                "session_strategy": str((flow_state or {}).get("session_strategy") or existing.get("session_strategy") or "").strip(),
                "role_pack_id": str((flow_state or {}).get("role_pack_id") or existing.get("role_pack_id") or existing.get("default_role_pack") or "").strip(),
                "execution_context": str((flow_state or {}).get("execution_context") or existing.get("execution_context") or "").strip(),
                "launch_mode": str(existing.get("launch_mode") or LAUNCH_MODE_FLOW).strip(),
            }
        payload = self._normalize_asset_definition(
            {
                **existing,
                **{
                    "flow_id": asset_id,
                    "definition_id": asset_id,
                    "label": str(result.get("label") or existing.get("label") or asset_id).strip() or asset_id,
                    "description": str(result.get("description") or existing.get("description") or "").strip(),
                    "workflow_kind": str(result.get("workflow_kind") or existing.get("workflow_kind") or MANAGED_FLOW_KIND).strip(),
                    "goal": str(result.get("goal") or existing.get("goal") or "").strip(),
                    "guard_condition": str(result.get("guard_condition") or existing.get("guard_condition") or "").strip(),
                    "phase_plan": list(result.get("phase_plan") or existing.get("phase_plan") or []),
                    "default_role_pack": str(
                        (flow_state or {}).get("role_pack_id")
                        or existing.get("default_role_pack")
                        or existing.get("role_pack_id")
                        or "coding_flow"
                    ).strip(),
                    "allowed_execution_modes": list(existing.get("allowed_execution_modes") or [EXECUTION_LEVEL_SIMPLE, EXECUTION_LEVEL_MEDIUM]),
                    "launch_mode": LAUNCH_MODE_FLOW,
                    "catalog_flow_id": FREE_CATALOG_FLOW_ID if asset_kind == "instance" else str(existing.get("catalog_flow_id") or "").strip(),
                    "execution_mode": str((flow_state or {}).get("execution_mode") or existing.get("execution_mode") or "").strip(),
                    "session_strategy": str((flow_state or {}).get("session_strategy") or existing.get("session_strategy") or "").strip(),
                    "role_pack_id": str((flow_state or {}).get("role_pack_id") or existing.get("role_pack_id") or existing.get("default_role_pack") or "coding_flow").strip(),
                    "execution_context": str((flow_state or {}).get("execution_context") or existing.get("execution_context") or "").strip(),
                    "risk_level": str(result.get("risk_level") or existing.get("risk_level") or "normal").strip() or "normal",
                    "autonomy_profile": str(result.get("autonomy_profile") or existing.get("autonomy_profile") or "default").strip() or "default",
                    "manager_handoff": dict(result or {}),
                    "asset_state": merged_asset_state,
                    "lineage": merged_lineage,
                    "instance_defaults": instance_defaults,
                    "review_checklist": review_checklist,
                    "role_guidance": role_guidance,
                    "control_profile": control_profile,
                    "doctor_policy": doctor_policy,
                    "supervisor_profile": supervisor_profile,
                    "run_brief": run_brief,
                    "source_bindings": source_bindings,
                    "bundle_manifest": bundle_manifest,
                    "source_asset_key": str((flow_state or {}).get("source_asset_key") or existing.get("source_asset_key") or "").strip(),
                    "source_asset_kind": str((flow_state or {}).get("source_asset_kind") or existing.get("source_asset_kind") or "").strip(),
                    "source_asset_version": str((flow_state or {}).get("source_asset_version") or existing.get("source_asset_version") or "").strip(),
                    "version": str((flow_state or {}).get("flow_version") or existing.get("version") or BUTLER_FLOW_VERSION).strip() or BUTLER_FLOW_VERSION,
                    "created_at": str(existing.get("created_at") or now_text()).strip(),
                    "updated_at": now_text(),
                },
            },
            asset_kind=asset_kind,
            asset_id=asset_id,
        )
        write_json_atomic(path, payload)
        if asset_kind in {"builtin", "template", "instance"}:
            ensure_asset_bundle_files(
                workspace_root,
                asset_kind=asset_kind,
                asset_id=asset_id,
                definition=payload,
            )
            write_bundle_sources(
                workspace_root,
                asset_kind=asset_kind,
                asset_id=asset_id,
                items=list(payload.get("source_bindings") or []),
                metadata={"source_asset_key": str(payload.get("source_asset_key") or "").strip()},
            )
            write_compiled_supervisor_knowledge(
                workspace_root,
                asset_kind=asset_kind,
                asset_id=asset_id,
                definition=payload,
            )
            payload["bundle_manifest"] = self._runtime_bundle_manifest(
                workspace_root=workspace_root,
                asset_kind=asset_kind,
                asset_id=asset_id,
                definition=payload,
            )
            write_json_atomic(path, payload)
        return path, payload

    def _maybe_render_header(self, flow_state: dict[str, Any]) -> None:
        block = getattr(self._display, "write_status_block", None)
        if not callable(block):
            return
        block(
            title="butler-flow",
            rows=[
                f"flow_id={flow_state.get('workflow_id') or '-'}",
                f"kind={flow_state.get('workflow_kind') or '-'} status={flow_state.get('status') or '-'} phase={flow_state.get('current_phase') or '-'}",
                f"goal={_truncate(str(flow_state.get('goal') or '-'), limit=80)}",
            ],
        )

    def _apply_operator_action(self, cfg: dict[str, Any], flow_path: Path, flow_state: dict[str, Any], action: str) -> None:
        action_name = str(action or "").strip().lower()
        payload: dict[str, Any] = {}
        if action_name == "append_instruction":
            payload["instruction"] = str(self._input_fn("append instruction: ")).strip()
        elif action_name == "bind_repo_contract":
            payload["repo_contract_path"] = str(self._input_fn("repo contract path [AGENTS.md]: ")).strip() or "AGENTS.md"
        receipt = self._runtime.apply_operator_action(
            cfg=cfg,
            flow_dir_path=flow_path,
            flow_state=flow_state,
            action_type=action_name,
            payload=payload,
        )
        self._save_flow_state(flow_path, flow_state)
        self._display.write(f"[butler-flow] action={receipt.get('action_type')} summary={receipt.get('result_summary')}")

    def build_preflight_payload(self, args: argparse.Namespace) -> dict[str, Any]:
        cfg, config_path, workspace_root = self._load_config(getattr(args, "config", None))
        disabled = flow_disabled_mcp_servers(cfg)
        return {
            "version": BUTLER_FLOW_VERSION,
            "config_path": config_path,
            "workspace_root": workspace_root,
            "flow_root": str(build_flow_root(workspace_root)),
            "codex_available": bool(cli_provider_available("codex", cfg)),
            "cursor_available": bool(cli_provider_available("cursor", cfg)),
            "execution_mode_default": default_execution_mode(cfg, workflow_kind=PROJECT_LOOP_KIND),
            "role_pack_default": default_role_pack_id(cfg),
            "flow_codex_disabled_mcp_servers": disabled,
            "timeouts": {
                "flow": flow_timeout_seconds(cfg),
                "judge": judge_timeout_seconds(cfg),
            },
            "runtime_governance": {
                "project_default_max_attempts": DEFAULT_PROJECT_LOOP_MAX_ATTEMPTS,
                "project_default_max_phase_attempts": DEFAULT_PROJECT_PHASE_MAX_ATTEMPTS,
            },
            "catalog": self.build_catalog_payload(),
        }

    def preflight(self, args: argparse.Namespace) -> int:
        payload = self.build_preflight_payload(args)
        if bool(getattr(args, "json", False)):
            self._display.write_json(payload)
            return 0
        self._display.write("[butler-flow preflight]")
        self._display.write(f"version={payload['version']}")
        self._display.write(f"config={payload['config_path']}")
        self._display.write(f"workspace_root={payload['workspace_root']}")
        self._display.write(f"flow_root={payload['flow_root']}")
        self._display.write(f"codex_available={'yes' if payload['codex_available'] else 'no'}")
        self._display.write(f"cursor_available={'yes' if payload['cursor_available'] else 'no'}")
        self._display.write(f"execution_mode_default={payload['execution_mode_default']}")
        self._display.write(f"role_pack_default={payload['role_pack_default']}")
        disabled = list(payload.get("flow_codex_disabled_mcp_servers") or [])
        self._display.write(f"codex_mcp_guard={', '.join(disabled) if disabled else '-'}")
        self._display.write("next=butler-flow new")
        return 0

    def build_flows_payload(self, args: argparse.Namespace) -> dict[str, Any]:
        _, _, workspace_root = self._load_config(getattr(args, "config", None))
        rows = self._flow_rows(workspace_root=workspace_root, limit=safe_int(getattr(args, "limit", DEFAULT_FLOW_LIST_LIMIT), DEFAULT_FLOW_LIST_LIMIT))
        return {"version": BUTLER_FLOW_VERSION, "flow_root": str(build_flow_root(workspace_root)), "items": rows}

    def build_manage_payload(self, args: argparse.Namespace) -> dict[str, Any]:
        _, _, workspace_root = self._load_config(getattr(args, "config", None))
        manage_rows: list[dict[str, Any]] = []
        manage_rows.extend(self._builtin_manage_rows(workspace_root=workspace_root))
        manage_rows.extend(self._template_manage_rows(workspace_root=workspace_root))
        asset_kind_rank = {"template": 0, "builtin": 1}
        manage_rows.sort(
            key=lambda item: (
                asset_kind_rank.get(str(item.get("asset_kind") or "").strip(), 9),
                -float(item.get("_sort_value") or 0.0),
            )
        )
        counts = {
            "builtin": len([row for row in manage_rows if str(row.get("asset_kind") or "") == "builtin"]),
            "template": len([row for row in manage_rows if str(row.get("asset_kind") or "") == "template"]),
        }
        return {
            "version": BUTLER_FLOW_VERSION,
            "asset_root": str(flow_asset_root(workspace_root)),
            "builtin_root": str(builtin_asset_root(workspace_root)),
            "template_root": str(template_asset_root(workspace_root)),
            "instance_root": str(instance_asset_root(workspace_root)),
            "legacy_instance_root": str(legacy_flow_root(workspace_root)),
            "counts": counts,
            "items": manage_rows[: max(1, int(getattr(args, "limit", DEFAULT_FLOW_LIST_LIMIT) or DEFAULT_FLOW_LIST_LIMIT))],
        }

    def build_list_payload(self, args: argparse.Namespace) -> dict[str, Any]:
        return self.build_manage_payload(args)

    def list_flows(self, args: argparse.Namespace) -> int:
        payload = self.build_manage_payload(args)
        rows = list(payload.get("items") or [])
        if bool(getattr(args, "json", False)):
            self._display.write_json(payload)
            return 0
        self._display.write(f"asset_root={payload['asset_root']}")
        if not rows:
            self._display.write("no managed flow assets found")
            return 0
        for row in rows:
            prefix = f"{row.get('asset_kind') or '-'}:{row.get('asset_id') or row.get('flow_id') or '-'}"
            line = f"{prefix}  kind={row.get('workflow_kind') or '-'}  label={row.get('label') or '-'}"
            if str(row.get("asset_kind") or "") == "instance":
                line = (
                    f"{prefix}  status={row.get('effective_status') or row.get('status') or '-'}  "
                    f"phase={row.get('effective_phase') or row.get('current_phase') or '-'}  "
                    f"role={row.get('active_role_id') or '-'}  kind={row.get('workflow_kind') or '-'}"
                )
            self._display.write(line)
            self._display.write(
                f"  updated_at={row.get('updated_at') or '-'}  role_pack={row.get('role_pack_id') or '-'}  "
                f"path={row.get('asset_path') or '-'}"
            )
            self._display.write(f"  goal={_truncate(str(row.get('goal') or '-'), limit=96)}")
        return 0

    def flows(self, args: argparse.Namespace) -> int:
        if str(getattr(args, "manage", "") or "").strip():
            return self.manage_flow(args)
        return self.list_flows(args)

    def launcher(self, args: argparse.Namespace) -> int:
        cfg, config_path, workspace_root = self._load_config(getattr(args, "config", None))
        while True:
            rows = self._flow_rows(workspace_root=workspace_root, limit=DEFAULT_FLOW_LAUNCHER_RECENT_LIMIT)
            last_row = rows[0] if rows else {}
            last_status = str(last_row.get("status") or "").strip().lower()
            default_action = "2" if last_row and last_status != "completed" else "1"
            self._display.write("[butler-flow launcher]")
            self._display.write(f"config={config_path}")
            self._display.write(f"workspace={workspace_root}")
            self._display.write(f"flow_root={build_flow_root(workspace_root)}")
            self._display.write(f"codex_available={'yes' if cli_provider_available('codex', cfg) else 'no'}")
            self._display.write(f"cursor_available={'yes' if cli_provider_available('cursor', cfg) else 'no'}")
            if last_row:
                self._display.write(
                    f"last={last_row['flow_id']} status={last_row.get('effective_status') or last_row['status'] or '-'} "
                    f"phase={last_row.get('effective_phase') or last_row['current_phase'] or '-'} "
                    f"kind={last_row['flow_kind'] or '-'}"
                )
            if rows:
                self._display.write("recent_flows:")
                for index, row in enumerate(rows, start=1):
                    self._display.write(
                        f"  {index}. {row['flow_id']}  status={row.get('effective_status') or row['status'] or '-'}  "
                        f"phase={row.get('effective_phase') or row['current_phase'] or '-'}  "
                        f"kind={row['flow_kind'] or '-'}"
                    )
                    self._display.write(f"     updated_at={row['updated_at'] or '-'}  goal={_truncate(str(row.get('goal') or '-'), limit=96)}")
            else:
                self._display.write("recent_flows=none")
            self._display.write("actions: [1] new  [2] resume  [q] quit")
            choice = str(self._input_fn(f"select action [{default_action}]: ")).strip().lower()
            if not choice:
                choice = default_action
            if choice in {"q", "quit", "exit"}:
                return 0
            if choice in {"2", "resume"}:
                try:
                    flow_id, use_last = self._prompt_flow_selection(rows, action_label="resume")
                except FileNotFoundError as exc:
                    self._display.write(f"[butler-flow] error: {exc}", err=True)
                    continue
                return self.resume(
                    argparse.Namespace(
                        command="resume",
                        config=config_path,
                        flow_id=flow_id,
                        last=use_last,
                        codex_session_id="",
                        kind=PROJECT_LOOP_KIND,
                        launch_mode=DEFAULT_LAUNCH_MODE,
                        execution_level=DEFAULT_EXECUTION_LEVEL,
                        catalog_flow_id=DEFAULT_CATALOG_FLOW_ID,
                        execution_mode=default_execution_mode(cfg, workflow_kind=PROJECT_LOOP_KIND),
                        role_pack=default_role_pack_id(cfg, workflow_kind=PROJECT_LOOP_KIND),
                        goal="",
                        guard_condition="",
                        max_attempts=0,
                        max_phase_attempts=0,
                        no_stream=False,
                    )
                )
            if choice not in {"1", "new", "run"}:
                self._display.write(f"[butler-flow] error: unsupported selection `{choice}`", err=True)
                continue
            return self.new(
                argparse.Namespace(
                    command="new",
                    config=config_path,
                    kind=PROJECT_LOOP_KIND,
                    launch_mode=DEFAULT_LAUNCH_MODE,
                    execution_level=DEFAULT_EXECUTION_LEVEL,
                    catalog_flow_id=DEFAULT_CATALOG_FLOW_ID,
                    execution_mode=default_execution_mode(cfg, workflow_kind=PROJECT_LOOP_KIND),
                    role_pack=default_role_pack_id(cfg, workflow_kind=PROJECT_LOOP_KIND),
                    goal="",
                    guard_condition="",
                    max_attempts=None,
                    max_phase_attempts=None,
                    no_stream=False,
                    plain=True,
                )
            )

    def _prompt_flow_selection(self, rows: list[dict[str, Any]], *, action_label: str) -> tuple[str, bool]:
        if not rows:
            raise FileNotFoundError("no local butler-flow state found")
        raw = str(self._input_fn(f"{action_label} flow [enter=last, number, or flow_id]: ")).strip()
        if not raw:
            return "", True
        if raw.isdigit():
            index = int(raw) - 1
            if 0 <= index < len(rows):
                return str(rows[index].get("flow_id") or "").strip(), False
        return raw, False

    def prepare_new_flow(self, args: argparse.Namespace, *, interactive_setup: bool = False) -> PreparedFlowRun:
        cfg, config_path, workspace_root = self._load_config(getattr(args, "config", None))
        self._runtime.ensure_flow_runtime(cfg)
        launch_draft = self._build_launch_draft_from_args(args, interactive_setup=interactive_setup)
        goal = str(launch_draft.get("goal") or "").strip()
        guard_condition = str(launch_draft.get("guard_condition") or "").strip()
        if not goal:
            raise ValueError("goal is required")
        launch_mode = self._normalize_launch_mode(launch_draft.get("launch_mode"))
        if interactive_setup:
            summary = (
                f"mode={launch_draft.get('launch_mode') or '-'} "
                f"level={launch_draft.get('execution_level') or '-'} "
                f"flow={launch_draft.get('catalog_flow_id') or '-'} "
                f"goal={_truncate(goal, limit=64)}"
            )
            self._display.write(f"[butler-flow new] {summary}")
            confirm = self._choice_prompt(
                "confirm",
                [("run now", "run"), ("cancel", "cancel")],
                default_value="run",
            )
            if confirm != "run":
                raise KeyboardInterrupt()
        catalog_flow_id = str(launch_draft.get("catalog_flow_id") or "").strip()
        flow_id = new_flow_id()
        flow_path = flow_dir(workspace_root, flow_id)
        flow_kind = SINGLE_GOAL_KIND if launch_mode == LAUNCH_MODE_SINGLE else MANAGED_FLOW_KIND
        flow_state = new_flow_state(
            workflow_id=flow_id,
            workflow_kind=flow_kind,
            workspace_root=workspace_root,
            goal=goal,
            guard_condition=guard_condition,
            max_attempts=safe_int(
                launch_draft.get("max_attempts"),
                DEFAULT_PROJECT_LOOP_MAX_ATTEMPTS if launch_mode == LAUNCH_MODE_FLOW else DEFAULT_SINGLE_GOAL_MAX_ATTEMPTS,
            ),
            max_phase_attempts=safe_int(launch_draft.get("max_phase_attempts"), DEFAULT_PROJECT_PHASE_MAX_ATTEMPTS),
            launch_mode=launch_mode,
            catalog_flow_id=catalog_flow_id,
        )
        flow_state["entry_mode"] = "new"
        if catalog_flow_id == FREE_CATALOG_FLOW_ID:
            built = self._run_free_design_loop(
                cfg=cfg,
                workspace_root=workspace_root,
                flow_path=flow_path,
                flow_state=flow_state,
                draft=launch_draft,
                interactive=interactive_setup,
            )
            launch_draft["goal"] = str(built.get("goal") or goal).strip()
            launch_draft["guard_condition"] = str(built.get("guard_condition") or guard_condition).strip()
            launch_draft["phase_plan"] = list(built.get("phase_plan") or [])
            flow_state["manage_handoff"] = dict(built)
        self._apply_launch_draft_to_flow_state(flow_state, cfg=cfg, draft=launch_draft)
        args.role_pack = str(launch_draft.get("role_pack_id") or getattr(args, "role_pack", "") or "").strip()
        self._normalize_flow_state_payload(flow_state)
        self._save_flow_state(flow_path, flow_state)
        if catalog_flow_id == FREE_CATALOG_FLOW_ID and flow_state.get("manage_handoff"):
            self._emit_manage_handoff_ready(flow_path=flow_path, flow_state=flow_state, payload=dict(flow_state.get("manage_handoff") or {}))
        return PreparedFlowRun(
            cfg=cfg,
            config_path=config_path,
            workspace_root=workspace_root,
            flow_path=flow_path,
            flow_state=flow_state,
        )

    def execute_prepared_flow(self, prepared: PreparedFlowRun, *, stream_enabled: bool) -> int:
        return self._runtime.run_flow_loop(prepared.cfg, prepared.flow_path, prepared.flow_state, stream_enabled=stream_enabled)

    def new(self, args: argparse.Namespace) -> int:
        interactive_setup = bool(getattr(args, "plain", False)) and _stdin_is_interactive()
        prepared = self.prepare_new_flow(args, interactive_setup=interactive_setup)
        flow_state = prepared.flow_state
        self._display.write(f"[butler-flow] config={prepared.config_path}")
        self._display.write(f"[butler-flow] workspace={prepared.workspace_root}")
        self._display.write(f"[butler-flow] flow_id={flow_state.get('workflow_id')}")
        self._display.write(f"[butler-flow] flow_dir={prepared.flow_path}")
        self._display.write(f"[butler-flow] kind={flow_state.get('workflow_kind')}")
        self._display.write(
            f"[butler-flow] launch_mode={flow_state.get('launch_mode') or '-'} "
            f"catalog_flow={flow_state.get('catalog_flow_id') or '-'} "
            f"mode={flow_state.get('execution_mode') or '-'}"
        )
        self._display.write(f"[butler-flow] goal={_truncate(str(flow_state.get('goal') or ''), limit=120)}")
        self._display.write(f"[butler-flow] guard={_truncate(str(flow_state.get('guard_condition') or ''), limit=120)}")
        return self.execute_prepared_flow(prepared, stream_enabled=not bool(getattr(args, "no_stream", False)))

    def run_new(self, args: argparse.Namespace) -> int:
        return self.new(args)

    def exec_new(self, args: argparse.Namespace) -> int:
        prepared = self.prepare_new_flow(args, interactive_setup=False)
        return self._exec_prepared_flow(prepared, stream_enabled=not bool(getattr(args, "no_stream", False)))

    def exec_run(self, args: argparse.Namespace) -> int:
        return self.exec_new(args)

    def prepare_resume_flow(self, args: argparse.Namespace) -> PreparedFlowRun:
        cfg, config_path, workspace_root = self._load_config(getattr(args, "config", None))
        self._runtime.ensure_flow_runtime(cfg)
        flow_id = self._flow_identity_from_args(workspace_root=workspace_root, args=args)
        if flow_id:
            flow_path = flow_dir(workspace_root, flow_id)
            flow_state = read_flow_state(flow_path)
            if not flow_state:
                raise FileNotFoundError(f"flow not found: {flow_id}")
            self._normalize_flow_state_payload(flow_state)
            if str(flow_state.get("workflow_kind") or "").strip() in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND}:
                sync_project_phase_attempt_count(flow_state)
            if str(getattr(args, "goal", "") or "").strip():
                flow_state["goal"] = str(args.goal).strip()
            if str(getattr(args, "guard_condition", "") or "").strip():
                flow_state["guard_condition"] = str(args.guard_condition).strip()
            if getattr(args, "max_attempts", None):
                flow_state["max_attempts"] = safe_int(args.max_attempts, flow_state.get("max_attempts", DEFAULT_SINGLE_GOAL_MAX_ATTEMPTS))
            if getattr(args, "max_phase_attempts", None):
                flow_state["max_phase_attempts"] = safe_int(args.max_phase_attempts, flow_state.get("max_phase_attempts", DEFAULT_PROJECT_PHASE_MAX_ATTEMPTS))
            self._apply_role_runtime_args(flow_state, cfg=cfg, args=args, prefer_existing=True)
            if str(flow_state.get("status") or "").strip() == "completed":
                return PreparedFlowRun(cfg=cfg, config_path=config_path, workspace_root=workspace_root, flow_path=flow_path, flow_state=flow_state)
            self._save_flow_state(flow_path, flow_state)
            return PreparedFlowRun(cfg=cfg, config_path=config_path, workspace_root=workspace_root, flow_path=flow_path, flow_state=flow_state)

        codex_session_id = str(getattr(args, "codex_session_id", "") or "").strip()
        if not codex_session_id:
            raise ValueError("resume requires --flow-id, --last, or --codex-session-id")
        goal = self._prompt_value("Codex task: ", getattr(args, "goal", ""))
        guard_condition = self._prompt_value("Cursor guard condition: ", getattr(args, "guard_condition", ""))
        launch_mode, execution_level, catalog_flow_id = self._non_tty_launch_defaults(args)
        flow_kind = SINGLE_GOAL_KIND if launch_mode == LAUNCH_MODE_SINGLE else PROJECT_LOOP_KIND
        flow_id = new_flow_id()
        flow_path = flow_dir(workspace_root, flow_id)
        flow_state = new_flow_state(
            workflow_id=flow_id,
            workflow_kind=flow_kind,
            workspace_root=workspace_root,
            goal=goal,
            guard_condition=guard_condition,
            max_attempts=safe_int(
                getattr(args, "max_attempts", 0),
                DEFAULT_PROJECT_LOOP_MAX_ATTEMPTS if flow_kind in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND} else DEFAULT_SINGLE_GOAL_MAX_ATTEMPTS,
            ),
            max_phase_attempts=safe_int(getattr(args, "max_phase_attempts", 0), DEFAULT_PROJECT_PHASE_MAX_ATTEMPTS),
            launch_mode=launch_mode,
            catalog_flow_id=catalog_flow_id,
            codex_session_id=codex_session_id,
            pending_codex_prompt="Resume the provided Codex session, assess whether the goal is already satisfied, and continue until the guard condition is met.",
            resume_source="codex_session_id",
        )
        flow_state["entry_mode"] = "resume"
        self._apply_role_runtime_args(flow_state, cfg=cfg, args=args, prefer_existing=False)
        self._normalize_flow_state_payload(flow_state)
        self._save_flow_state(flow_path, flow_state)
        return PreparedFlowRun(cfg=cfg, config_path=config_path, workspace_root=workspace_root, flow_path=flow_path, flow_state=flow_state)

    def resume(self, args: argparse.Namespace) -> int:
        prepared = self.prepare_resume_flow(args)
        flow_state = prepared.flow_state
        if str(flow_state.get("status") or "").strip() == "completed":
            self._display.write(f"[butler-flow] already completed: {flow_state.get('workflow_id')}")
            return 0
        self._display.write(f"[butler-flow] config={prepared.config_path}")
        if str(flow_state.get("resume_source") or "").strip() == "codex_session_id":
            self._display.write(f"[butler-flow] derived flow_id={flow_state.get('workflow_id')}")
            self._display.write(f"[butler-flow] resuming codex_session_id={flow_state.get('codex_session_id')}")
        else:
            self._display.write(f"[butler-flow] resuming flow_id={flow_state.get('workflow_id')}")
        self._display.write(f"[butler-flow] kind={flow_state.get('workflow_kind')}")
        self._display.write(f"[butler-flow] goal={_truncate(str(flow_state.get('goal') or ''), limit=120)}")
        return self.execute_prepared_flow(prepared, stream_enabled=not bool(getattr(args, "no_stream", False)))

    def exec_resume(self, args: argparse.Namespace) -> int:
        prepared = self.prepare_resume_flow(args)
        return self._exec_prepared_flow(prepared, stream_enabled=not bool(getattr(args, "no_stream", False)))

    def status(self, args: argparse.Namespace) -> int:
        payload = self.build_status_payload(args)
        if bool(getattr(args, "json", False)):
            self._display.write_json(payload)
            return 0
        flow_state = dict(payload.get("flow_state") or {})
        flow_definition = dict(payload.get("flow_definition") or {})
        runtime = dict(payload.get("runtime_snapshot") or {})
        self._display.write(f"workflow_id={payload['flow_id']}")
        self._display.write(f"flow_dir={payload['flow_dir']}")
        self._display.write(f"kind={flow_state.get('workflow_kind')}")
        self._display.write(f"version={flow_definition.get('version') or flow_state.get('flow_version') or '-'}")
        self._display.write(
            f"status={payload.get('effective_status') or flow_state.get('status')} "
            f"(stored={flow_state.get('status') or '-'})"
        )
        self._display.write(
            f"phase={payload.get('effective_phase') or flow_state.get('current_phase')} "
            f"(stored={flow_state.get('current_phase') or '-'})"
        )
        self._display.write(
            f"execution_mode={flow_state.get('execution_mode') or '-'} "
            f"session_strategy={flow_state.get('session_strategy') or '-'} "
            f"launch_mode={flow_state.get('launch_mode') or '-'} "
            f"catalog_flow={flow_state.get('catalog_flow_id') or '-'} "
            f"active_role={flow_state.get('active_role_id') or '-'} "
            f"role_pack={flow_state.get('role_pack_id') or '-'}"
        )
        self._display.write(f"attempt_count={flow_state.get('attempt_count')}/{flow_state.get('max_attempts')}")
        self._display.write(
            f"phase_attempt_count={flow_state.get('phase_attempt_count')}/{flow_state.get('max_phase_attempts')}  "
            f"runtime_elapsed={flow_state.get('runtime_elapsed_seconds') or 0}s/{flow_state.get('max_runtime_seconds') or 0}s"
        )
        self._display.write(f"codex_session_id={flow_state.get('codex_session_id') or '-'}")
        self._display.write(f"process_state={runtime.get('process_state')} pid={runtime.get('pid') or 0}")
        self._display.write(f"last_decision={dict(flow_state.get('last_cursor_decision') or {}).get('decision') or '-'}")
        self._display.write(f"last_summary={flow_state.get('last_completion_summary') or '-'}")
        return 0

    def build_status_payload(self, args: argparse.Namespace) -> dict[str, Any]:
        _, _, workspace_root = self._load_config(getattr(args, "config", None))
        flow_id = self._flow_identity_from_args(workspace_root=workspace_root, args=args)
        if not flow_id:
            raise ValueError("status requires --flow-id or --last")
        payload = self._flow_status_payload(workspace_root=workspace_root, flow_id=flow_id)
        payload["flow_definition"] = read_json(flow_definition_path(Path(payload["flow_dir"])))
        return payload

    def manage_flow(self, args: argparse.Namespace) -> int:
        cfg, config_path, workspace_root = self._load_config(getattr(args, "config", None))
        manage_target = str(getattr(args, "manage", "") or "new").strip() or "new"
        manage_stage = normalize_manage_stage(str(getattr(args, "stage", "") or "commit"))
        builtin_mode = str(getattr(args, "builtin_mode", "") or "").strip().lower()
        requested_goal = str(getattr(args, "goal", "") or "").strip()
        requested_guard = str(getattr(args, "guard_condition", "") or "").strip()
        requested_instruction = str(getattr(args, "instruction", "") or "").strip()
        raw_draft_payload = getattr(args, "draft_payload", None)
        if isinstance(raw_draft_payload, str):
            try:
                draft_payload = dict(json.loads(raw_draft_payload))
            except Exception:
                draft_payload = {}
        else:
            draft_payload = dict(raw_draft_payload or {}) if isinstance(raw_draft_payload, dict) else {}

        if manage_target == "last":
            manage_target = self._manage_target_key("instance", self._resolve_recent_flow_id(workspace_root=workspace_root))

        asset_kind, raw_asset_id = self._parse_manage_target(manage_target)
        original_asset_kind = asset_kind
        original_asset_id = str(raw_asset_id or "").strip()
        creating_new_instance = asset_kind == "instance" and raw_asset_id == "new"
        creating_new_asset = raw_asset_id == "new"
        builtin_source_key = ""
        lineage: dict[str, Any] = {}
        asset_state: dict[str, Any] = {
            "status": "active" if manage_stage == "commit" else "draft",
            "stage": manage_stage,
        }

        if asset_kind == "builtin" and not creating_new_asset and original_asset_id:
            lowered_instruction = requested_instruction.lower()
            if builtin_mode not in {"clone", "edit", "edit_in_place", "in_place"}:
                if any(token in lowered_instruction for token in (" clone ", "克隆", "复制")) or lowered_instruction.startswith("clone"):
                    builtin_mode = "clone"
                elif any(token in lowered_instruction for token in ("in place", "in-place", "原地", "直接修改")) or lowered_instruction.startswith("edit"):
                    builtin_mode = "edit"
            if builtin_mode in {"edit_in_place", "in_place"}:
                builtin_mode = "edit"
            if builtin_mode not in {"clone", "edit"}:
                raise ValueError("builtin assets require explicit mode: use `clone ...` or `edit ...` when targeting $builtin:<id>.")
            builtin_source_key = self._manage_target_key("builtin", original_asset_id)
            if builtin_mode == "clone":
                asset_kind = "template"
                creating_new_asset = True
                manage_target = "template:new"
                requested_instruction = requested_instruction or "clone builtin to editable template"
                lineage["cloned_from_asset_key"] = builtin_source_key
            else:
                lineage["editing_asset_key"] = builtin_source_key

        asset_id = new_flow_id() if creating_new_instance else (f"{asset_kind}_{new_flow_id()}" if creating_new_asset else str(raw_asset_id or "").strip())
        if not asset_id:
            raise ValueError("manage target is required")

        flow_path: Path | None = None
        flow_state: dict[str, Any] | None = None
        existing_definition: dict[str, Any] = {}
        if asset_kind == "instance":
            flow_path = flow_dir(workspace_root, asset_id) if creating_new_instance else resolve_flow_dir(workspace_root, asset_id)
            flow_state = {} if creating_new_instance else read_flow_state(flow_path)
            if not flow_state:
                existing_definition = read_json(flow_definition_path(flow_path))
                if not creating_new_instance and not existing_definition:
                    raise FileNotFoundError(f"flow not found: {asset_id}")
                flow_state = (
                    self._asset_definition_to_flow_state(
                        workspace_root=workspace_root,
                        asset_id=asset_id,
                        definition=existing_definition,
                    )
                    if existing_definition
                    else new_flow_state(
                        workflow_id=asset_id,
                        workflow_kind=MANAGED_FLOW_KIND,
                        workspace_root=workspace_root,
                        goal=requested_goal,
                        guard_condition=requested_guard,
                        max_attempts=DEFAULT_PROJECT_LOOP_MAX_ATTEMPTS,
                        max_phase_attempts=DEFAULT_PROJECT_PHASE_MAX_ATTEMPTS,
                        launch_mode=LAUNCH_MODE_FLOW,
                        catalog_flow_id=FREE_CATALOG_FLOW_ID,
                    )
                )
            flow_state["entry_mode"] = "manage"
            self._apply_role_runtime_args(flow_state, cfg=cfg, args=args, prefer_existing=not creating_new_instance)
            self._normalize_flow_state_payload(flow_state)
        else:
            definition_path = self._asset_file_path(workspace_root=workspace_root, asset_kind=asset_kind, asset_id=asset_id)
            if builtin_source_key and builtin_mode == "clone":
                existing_definition = read_json(
                    self._asset_file_path(
                        workspace_root=workspace_root,
                        asset_kind="builtin",
                        asset_id=original_asset_id,
                    )
                )
                asset_state["mode"] = "clone"
            else:
                existing_definition = read_json(definition_path)
                if asset_kind == "builtin" and builtin_source_key:
                    asset_state["mode"] = "edit_in_place"
            flow_state = self._asset_definition_to_flow_state(
                workspace_root=workspace_root,
                asset_id=asset_id,
                definition=existing_definition
                or {
                    "flow_id": asset_id,
                    "workflow_kind": MANAGED_FLOW_KIND,
                    "goal": requested_goal,
                    "guard_condition": requested_guard,
                },
            )
            flow_state["label"] = str(existing_definition.get("label") or asset_id).strip() or asset_id
            flow_state["description"] = str(existing_definition.get("description") or "").strip()
            if builtin_source_key and builtin_mode == "clone":
                flow_state["source_asset_key"] = builtin_source_key
                flow_state["source_asset_kind"] = "builtin"
                flow_state["source_asset_version"] = str(existing_definition.get("version") or "").strip()
                flow_state["bundle_manifest"] = self._runtime_bundle_manifest(
                    workspace_root=workspace_root,
                    asset_kind="builtin",
                    asset_id=original_asset_id,
                    definition=existing_definition,
                )

        if builtin_source_key and not lineage.get("cloned_from_asset_key"):
            lineage["source_asset_key"] = builtin_source_key

        if draft_payload:
            result = self._manage_result_from_draft(
                draft_payload=draft_payload,
                flow_state=flow_state,
                asset_kind=asset_kind,
                manage_target=manage_target,
                requested_goal=requested_goal,
                requested_guard=requested_guard,
                manage_stage=manage_stage,
            )
        else:
            result = run_manage_agent(
                cfg=cfg,
                workspace_root=workspace_root,
                run_prompt_receipt_fn=self._run_prompt_receipt_fn,
                flow_state=flow_state,
                manage_target=manage_target,
                asset_kind=asset_kind,
                goal=requested_goal or str(flow_state.get("goal") or "").strip(),
                guard_condition=requested_guard or str(flow_state.get("guard_condition") or "").strip(),
                instruction=requested_instruction,
                stage=manage_stage,
            )
        if asset_kind == "template" and creating_new_asset:
            asset_id = self._next_readable_asset_id(
                workspace_root=workspace_root,
                asset_kind=asset_kind,
                label=str(result.get("label") or "").strip(),
                goal=str(result.get("goal") or flow_state.get("goal") or requested_goal).strip(),
                instruction=requested_instruction,
            )
        mutation = str(result.get("mutation") or ("create" if creating_new_asset or not existing_definition else "update")).strip() or "update"
        summary = str(result.get("summary") or "managed flow updated").strip()
        asset_path = self._asset_file_path(workspace_root=workspace_root, asset_kind=asset_kind, asset_id=asset_id)
        asset_definition: dict[str, Any]

        flow_state["workflow_id"] = asset_id
        flow_state["flow_id"] = asset_id
        flow_state["label"] = str(result.get("label") or flow_state.get("label") or asset_id).strip() or asset_id
        flow_state["description"] = str(result.get("description") or flow_state.get("description") or "").strip()
        flow_state["workflow_kind"] = str(result.get("workflow_kind") or MANAGED_FLOW_KIND).strip()
        flow_state["goal"] = str(result.get("goal") or flow_state.get("goal") or "").strip()
        flow_state["guard_condition"] = str(result.get("guard_condition") or flow_state.get("guard_condition") or "").strip()
        flow_state["risk_level"] = str(result.get("risk_level") or flow_state.get("risk_level") or "normal").strip() or "normal"
        flow_state["autonomy_profile"] = str(result.get("autonomy_profile") or flow_state.get("autonomy_profile") or "default").strip() or "default"
        flow_state["phase_plan"] = list(result.get("phase_plan") or flow_state.get("phase_plan") or [])
        flow_state["manage_handoff"] = dict(result or {})
        flow_state["review_checklist"] = list(result.get("review_checklist") or flow_state.get("review_checklist") or [])
        flow_state["role_guidance"] = dict(result.get("role_guidance") or flow_state.get("role_guidance") or {})
        flow_state["control_profile"] = normalize_control_profile_payload(
            result.get("control_profile"),
            current=dict(flow_state.get("control_profile") or {}),
            workflow_kind=str(flow_state.get("workflow_kind") or "").strip(),
            role_pack_id=str(flow_state.get("role_pack_id") or "").strip(),
            execution_mode=str(flow_state.get("execution_mode") or "").strip(),
            execution_context=str(flow_state.get("execution_context") or "").strip(),
        )
        flow_state["doctor_policy"] = dict(result.get("doctor_policy") or flow_state.get("doctor_policy") or {})
        flow_state["supervisor_profile"] = dict(result.get("supervisor_profile") or flow_state.get("supervisor_profile") or {})
        flow_state["run_brief"] = str(result.get("run_brief") or flow_state.get("run_brief") or "").strip()
        flow_state["source_bindings"] = list(result.get("source_bindings") or flow_state.get("source_bindings") or [])
        flow_state["bundle_manifest"] = dict(result.get("bundle_manifest") or flow_state.get("bundle_manifest") or {})
        flow_state["entry_mode"] = "manage"
        flow_state["launch_mode"] = LAUNCH_MODE_FLOW
        flow_state["catalog_flow_id"] = FREE_CATALOG_FLOW_ID
        flow_state["flow_version"] = BUTLER_FLOW_VERSION
        if builtin_source_key and not str(flow_state.get("source_asset_key") or "").strip():
            flow_state["source_asset_key"] = builtin_source_key
            flow_state["source_asset_kind"] = "builtin"
            flow_state["source_asset_version"] = str(existing_definition.get("version") or "").strip()
        self._normalize_flow_state_payload(flow_state)
        flow_state["current_phase"] = first_phase_id(list(flow_state.get("phase_plan") or []), workflow_kind=str(flow_state.get("workflow_kind") or "").strip())

        if asset_kind == "instance":
            if str(flow_state.get("status") or "").strip() not in {"running", "completed"}:
                flow_state["status"] = "pending"
            self._save_flow_state(flow_path, flow_state)
            asset_path, asset_definition = self._save_managed_asset_definition(
                workspace_root=workspace_root,
                asset_kind=asset_kind,
                asset_id=asset_id,
                existing=existing_definition or read_json(flow_definition_path(flow_path)),
                result=result,
                flow_state=flow_state,
                lineage=lineage,
                asset_state=asset_state,
            )
        else:
            asset_path, asset_definition = self._save_managed_asset_definition(
                workspace_root=workspace_root,
                asset_kind=asset_kind,
                asset_id=asset_id,
                existing=existing_definition,
                result=result,
                flow_state=flow_state,
                lineage=lineage,
                asset_state=asset_state,
            )

        summary = self._canonical_manage_summary(asset_kind=asset_kind, asset_id=asset_id, definition=asset_definition)
        canonical_manage_handoff = dict(result or {})
        canonical_manage_handoff["summary"] = summary
        asset_definition["manager_handoff"] = canonical_manage_handoff
        write_json_atomic(asset_path, asset_definition)
        if asset_kind == "instance":
            flow_state["manage_handoff"] = canonical_manage_handoff
            self._save_flow_state(flow_path, flow_state)
            self._emit_manage_handoff_ready(flow_path=flow_path, flow_state=flow_state, payload=canonical_manage_handoff)
        self._append_manage_audit(
            workspace_root=workspace_root,
            asset_kind=asset_kind,
            asset_id=asset_id,
            mutation=mutation,
            summary=summary,
        )

        payload = {
            "version": BUTLER_FLOW_VERSION,
            "config_path": config_path,
            "asset_key": self._manage_target_key(asset_kind, asset_id),
            "asset_kind": asset_kind,
            "asset_id": asset_id,
            "flow_id": asset_id if asset_kind == "instance" else "",
            "flow_dir": str(flow_path) if flow_path is not None else "",
            "asset_path": str(asset_path),
            "workflow_kind": str(result.get("workflow_kind") or flow_state.get("workflow_kind") or "").strip(),
            "execution_mode": str(flow_state.get("execution_mode") or "").strip(),
            "role_pack_id": str(flow_state.get("role_pack_id") or "").strip(),
            "goal": str(result.get("goal") or flow_state.get("goal") or "").strip(),
            "guard_condition": str(result.get("guard_condition") or flow_state.get("guard_condition") or "").strip(),
            "manage_stage": manage_stage,
            "builtin_mode": builtin_mode,
            "manage_handoff": canonical_manage_handoff,
            "flow_definition": asset_definition,
            "summary": summary,
        }
        if bool(getattr(args, "json", False)):
            self._display.write_json(payload)
            return 0
        self._display.write(
            f"[butler-flow manage] asset={payload['asset_key']} kind={payload['workflow_kind']} "
            f"mode={payload['execution_mode'] or '-'} role_pack={payload['role_pack_id'] or '-'}"
        )
        self._display.write(f"[butler-flow manage] summary={summary}")
        self._display.write(f"[butler-flow manage] goal={_truncate(payload['goal'], limit=120)}")
        return 0

    def manage_chat(self, args: argparse.Namespace) -> int:
        cfg, config_path, workspace_root = self._load_config(getattr(args, "config", None))
        requested_manage = str(getattr(args, "manage", "") or "").strip()
        requested_instruction = str(getattr(args, "instruction", "") or "").strip()
        manager_session_id = str(getattr(args, "manager_session_id", "") or "").strip()
        persisted_session = read_manage_session(workspace_root, manager_session_id) if manager_session_id else {}
        persisted_draft = read_manage_draft(workspace_root, manager_session_id) if manager_session_id else {}
        persisted_pending_action = read_manage_pending_action(workspace_root, manager_session_id) if manager_session_id else {}
        manage_target = requested_manage
        asset_kind = ""
        asset_id = ""
        asset_definition: dict[str, Any] = {}
        flow_state: dict[str, Any] = {}

        if manage_target == "last":
            manage_target = self._manage_target_key("instance", self._resolve_recent_flow_id(workspace_root=workspace_root))
        if not manage_target:
            manage_target = str(
                persisted_pending_action.get("manage_target")
                or persisted_session.get("active_manage_target")
                or persisted_draft.get("manage_target")
                or ""
            ).strip()

        if manage_target:
            asset_kind, asset_id = self._parse_manage_target(manage_target)
            if asset_id and asset_id != "new":
                if asset_kind == "instance":
                    flow_path = resolve_flow_dir(workspace_root, asset_id)
                    flow_state = read_flow_state(flow_path)
                    if not flow_state:
                        asset_definition = read_json(flow_definition_path(flow_path))
                        if not asset_definition:
                            raise FileNotFoundError(f"flow not found: {asset_id}")
                        flow_state = self._asset_definition_to_flow_state(
                            workspace_root=workspace_root,
                            asset_id=asset_id,
                            definition=asset_definition,
                        )
                else:
                    asset_definition = read_json(
                        self._asset_file_path(
                            workspace_root=workspace_root,
                            asset_kind=asset_kind,
                            asset_id=asset_id,
                        )
                    )
                    if not asset_definition:
                        raise FileNotFoundError(f"asset not found: {manage_target}")
                    flow_state = self._asset_definition_to_flow_state(
                        workspace_root=workspace_root,
                        asset_id=asset_id,
                        definition=asset_definition,
                    )
                self._normalize_flow_state_payload(flow_state)

        asset_rows = list(
            (
                self.build_manage_payload(
                    argparse.Namespace(
                        config=getattr(args, "config", None),
                        limit=20,
                        json=False,
                        manage="",
                        goal="",
                        guard_condition="",
                        instruction="",
                    )
                ).get("items")
                or []
            )
        )
        result = run_manage_chat_agent(
            cfg=cfg,
            workspace_root=workspace_root,
            run_prompt_receipt_fn=self._run_prompt_receipt_fn,
            manage_target=manage_target,
            asset_kind=asset_kind or "workspace",
            instruction=requested_instruction,
            flow_state=flow_state or None,
            asset_definition=asset_definition or None,
            asset_rows=asset_rows,
            manager_session=persisted_session or None,
            current_draft=persisted_draft or None,
            pending_action=persisted_pending_action or None,
            manager_session_id=manager_session_id,
        )
        parse_status = str(result.get("parse_status") or "").strip().lower()
        parse_failed = parse_status not in {"", "ok"}
        resolved_session_id = str(result.get("manager_session_id") or manager_session_id).strip()
        resolved_manage_target = str(
            result.get("manage_target")
            or manage_target
            or persisted_pending_action.get("manage_target")
            or persisted_session.get("active_manage_target")
            or ""
        ).strip()
        resolved_asset_kind, resolved_asset_id = self._parse_manage_target(resolved_manage_target) if resolved_manage_target else (asset_kind, asset_id)
        if parse_failed and persisted_draft:
            merged_draft = normalize_manage_chat_draft_payload(
                persisted_draft,
                current=self._manage_draft_seed(
                    manage_target=resolved_manage_target,
                    asset_kind=resolved_asset_kind or asset_kind or "instance",
                    flow_state=flow_state or None,
                    asset_definition=asset_definition or None,
                ),
            )
        else:
            merged_draft = self._merge_manage_chat_draft(
                manage_target=resolved_manage_target,
                asset_kind=resolved_asset_kind or asset_kind or "instance",
                current_draft=persisted_draft or dict(persisted_pending_action.get("draft") or {}),
                result_draft=result.get("draft"),
                flow_state=flow_state or None,
                asset_definition=asset_definition or None,
            )
        pending_action = dict(persisted_pending_action or {})
        pure_confirm = self._is_pure_manage_confirmation(requested_instruction, pending_action=pending_action)
        action = "none"
        action_ready = False
        action_manage_target = ""
        action_instruction = ""
        action_stage = ""
        action_builtin_mode = ""
        action_draft: dict[str, Any] = {}
        pending_action_preview = str(result.get("pending_action_preview") or "").strip()
        if pure_confirm and pending_action:
            action = "manage_flow"
            action_ready = True
            action_manage_target = str(pending_action.get("manage_target") or "").strip()
            action_instruction = str(pending_action.get("instruction") or result.get("summary") or "").strip()
            action_stage = str(pending_action.get("stage") or "commit").strip()
            action_builtin_mode = str(pending_action.get("builtin_mode") or "").strip()
            action_draft = dict(pending_action.get("draft") or merged_draft)
            pending_action_preview = str(pending_action.get("preview") or pending_action.get("draft_summary") or "").strip()
        else:
            candidate_pending_action: dict[str, Any] = {}
            candidate_target = str(result.get("action_manage_target") or resolved_manage_target or merged_draft.get("manage_target") or "").strip()
            if str(result.get("action") or "").strip().lower() == "manage_flow" and candidate_target:
                merged_draft["manage_target"] = candidate_target
                candidate_pending_action = self._build_manage_pending_action(
                    resolved_target=candidate_target,
                    result=result,
                    draft=merged_draft,
                    fallback_stage=str(result.get("manager_stage") or "commit").strip(),
                )
            if candidate_pending_action:
                pending_action = candidate_pending_action
                pending_action_preview = str(
                    pending_action.get("preview") or pending_action.get("draft_summary") or pending_action_preview
                ).strip()
            elif requested_instruction.strip() and not parse_failed:
                pending_action = {}
        if resolved_session_id:
            write_manage_session(
                workspace_root,
                resolved_session_id,
                {
                    "manager_session_id": resolved_session_id,
                    "active_manage_target": resolved_manage_target,
                    "manager_stage": str(result.get("manager_stage") or "").strip(),
                    "confirmation_scope": str(result.get("confirmation_scope") or "").strip(),
                    "updated_at": now_text(),
                },
            )
            write_manage_draft(workspace_root, resolved_session_id, merged_draft)
            if pending_action:
                write_manage_pending_action(workspace_root, resolved_session_id, pending_action)
            else:
                clear_manage_pending_action(workspace_root, resolved_session_id)
            append_manage_turn(
                workspace_root,
                resolved_session_id,
                {
                    "created_at": now_text(),
                    "manage_target": resolved_manage_target,
                    "instruction": requested_instruction,
                    "response": str(result.get("response") or "").strip(),
                    "parse_status": parse_status or "ok",
                    "raw_reply": str(result.get("raw_reply") or "").strip(),
                    "error_text": str(result.get("error_text") or "").strip(),
                    "manager_stage": str(result.get("manager_stage") or "").strip(),
                    "draft": merged_draft,
                    "pending_action": pending_action,
                    "action_ready": action_ready,
                },
            )
        payload = {
            "version": BUTLER_FLOW_VERSION,
            "config_path": config_path,
            "manage_target": resolved_manage_target,
            "asset_kind": resolved_asset_kind or asset_kind,
            "asset_id": resolved_asset_id or asset_id,
            "response": str(result.get("response") or "").strip(),
            "parse_status": parse_status or "ok",
            "raw_reply": str(result.get("raw_reply") or "").strip(),
            "error_text": str(result.get("error_text") or "").strip(),
            "summary": str(result.get("summary") or "").strip(),
            "manager_stage": str(result.get("manager_stage") or "").strip(),
            "active_skill": str(result.get("active_skill") or "").strip(),
            "confirmation_scope": str(result.get("confirmation_scope") or "").strip(),
            "confirmation_prompt": str(result.get("confirmation_prompt") or "").strip(),
            "suggested_next_action": str(result.get("suggested_next_action") or "").strip(),
            "reuse_decision": str(result.get("reuse_decision") or "").strip(),
            "should_edit_asset": bool(result.get("should_edit_asset")),
            "edit_hint": str(result.get("edit_hint") or "").strip(),
            "draft": merged_draft,
            "draft_summary": self._draft_summary(merged_draft),
            "pending_action_preview": pending_action_preview,
            "supervisor_profile_preview": str(result.get("supervisor_profile_preview") or "").strip(),
            "action": action,
            "action_ready": action_ready,
            "action_manage_target": action_manage_target,
            "action_instruction": action_instruction,
            "action_stage": action_stage,
            "action_builtin_mode": action_builtin_mode,
            "action_draft": action_draft,
            "action_goal": str(dict(action_draft or merged_draft).get("goal") or "").strip(),
            "action_guard_condition": str(dict(action_draft or merged_draft).get("guard_condition") or "").strip(),
            "manager_session_id": resolved_session_id,
        }
        if bool(getattr(args, "json", False)):
            self._display.write_json(payload)
            return 0
        self._display.write(f"[butler-flow manage-chat] target={manage_target or '-'}")
        self._display.write(str(payload.get("response") or payload.get("summary") or "").strip())
        return 0

    def apply_action_payload(self, args: argparse.Namespace) -> dict[str, Any]:
        cfg, _, workspace_root = self._load_config(getattr(args, "config", None))
        flow_id = self._flow_identity_from_args(workspace_root=workspace_root, args=args)
        if not flow_id:
            raise ValueError("action requires --flow-id or --last")
        flow_path = flow_dir(workspace_root, flow_id)
        flow_state = read_flow_state(flow_path)
        if not flow_state:
            raise FileNotFoundError(f"flow not found: {flow_id}")
        action_name = str(getattr(args, "type", "") or "").strip()
        payload = {
            "instruction": str(getattr(args, "instruction", "") or "").strip(),
            "repo_contract_path": str(getattr(args, "repo_contract_path", "") or "").strip(),
        }
        receipt = self._runtime.apply_operator_action(
            cfg=cfg,
            flow_dir_path=flow_path,
            flow_state=flow_state,
            action_type=action_name,
            payload=payload,
        )
        self._save_flow_state(flow_path, flow_state)
        return dict(receipt)

    def action(self, args: argparse.Namespace) -> int:
        self._display.write_json(self.apply_action_payload(args))
        return 0


ButlerFlowApp = FlowApp
WorkflowShellApp = FlowApp
build_butler_flow_root = build_flow_root
build_workflow_shell_root = build_flow_root
_new_flow_state = new_flow_state
_write_json_atomic = write_json_atomic


def build_arg_parser():
    from .cli import build_arg_parser as _build_arg_parser

    return _build_arg_parser()


def _stdin_is_interactive() -> bool:
    from .cli import _stdin_is_interactive as _is_interactive

    return _is_interactive()


def main(argv: list[str] | None = None) -> int:
    from .cli import main as _main

    return _main(argv)
