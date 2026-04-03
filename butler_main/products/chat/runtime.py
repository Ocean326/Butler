from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents_os.contracts import ArtifactRef, FileAsset, ImageAsset, OutputBundle, TextBlock
from butler_main.agents_os.skills import (
    normalize_skill_exposure_payload,
    render_skill_exposure_prompt,
    resolve_skill_collection_id,
    summarize_skill_exposure,
)
from butler_main.agents_os.runtime import safe_truncate_markdown, sanitize_markdown_structure
from butler_main.runtime_os.process_runtime.engine.conversation_turn import (
    ConversationPromptBuild,
    ConversationTurnEngine,
    ConversationTurnInput,
)
from .session_modes import (
    BACKGROUND_MAIN_MODE,
    BRAINSTORM_MAIN_MODE,
    PROJECT_MAIN_MODE,
    SHARE_MAIN_MODE,
    canonical_main_mode,
    canonical_project_phase,
)
from .channel_profiles import normalize_output_bundle_for_channel
from .prompt_purity import resolve_prompt_purity_policy, should_include_skills_for_purity
from .prompting import should_include_agent_capabilities_prompt
from .router_plan import canonical_capability_policy, canonical_injection_tier
from .routing import ChatRuntimeRequest


_LEADING_PROCESS_ORDINAL_RE = re.compile(
    r"^\s*(?:(?:step|步骤)\s*)?(?:第\s*)?\d{1,2}(?:\s*[.:：、]\s*|\s*\)\s*)",
    re.IGNORECASE,
)


@dataclass(slots=True, frozen=True)
class ChatRuntimeExecution:
    reply_text: str
    output_bundle: OutputBundle
    raw_reply_text: str = ""
    pending_memory_id: str = ""
    process_events: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ChatRuntimeService:
    """Encapsulate the chat-side runtime logic behind a stable service boundary."""

    def __init__(
        self,
        *,
        memory_provider=None,
        prompt_provider=None,
        memory_manager,
        request_intake_service,
        build_prompt_fn: Callable[..., str],
        render_skills_prompt_fn: Callable[[str], str],
        render_agent_capabilities_prompt_fn: Callable[[str], str],
        run_agent_via_cli_fn: Callable[[str, str, int, str], tuple[str, bool]],
        run_agent_streaming_fn: Callable[[str, str, int, str, Callable[[str], None] | None, Callable[[dict], None] | None], tuple[str, bool]],
        parse_decide_fn: Callable[[str], tuple[str, list[dict]]],
        conversation_turn_engine=None,
    ) -> None:
        self._memory_provider = memory_provider
        self._prompt_provider = prompt_provider
        self._memory_manager = memory_manager
        self._request_intake_service = request_intake_service
        self._build_prompt_fn = build_prompt_fn
        self._render_skills_prompt_fn = render_skills_prompt_fn
        self._render_agent_capabilities_prompt_fn = render_agent_capabilities_prompt_fn
        self._run_agent_via_cli_fn = run_agent_via_cli_fn
        self._run_agent_streaming_fn = run_agent_streaming_fn
        self._parse_decide_fn = parse_decide_fn
        self._conversation_turn_engine = conversation_turn_engine

    def execute(
        self,
        runtime_request: ChatRuntimeRequest,
        *,
        effective_prompt: str,
        image_paths: list[str] | None,
        workspace: str,
        timeout: int,
        effective_model: str,
        max_len: int,
        stream_callback: Callable[[str], None] | None = None,
    ) -> ChatRuntimeExecution:
        downstream_event_callback = runtime_request.invocation.metadata.get("terminal_event_callback")
        if not callable(downstream_event_callback):
            downstream_event_callback = None
        process_events: list[dict[str, Any]] = []

        def _capture_runtime_event(event: dict) -> None:
            normalized = self._normalize_process_event(event)
            if normalized:
                self._append_process_event(process_events, normalized)
            if downstream_event_callback is not None:
                downstream_event_callback({**dict(event or {}), **dict(normalized or {})})

        session_scope_id = self._resolve_session_scope_id(runtime_request)
        execution_capture: dict[str, Any] = {}
        turn_input = ConversationTurnInput(
            user_prompt=effective_prompt,
            workspace=workspace,
            image_paths=image_paths,
            timeout=timeout,
            model=effective_model,
            max_len=max_len,
            metadata={
                "event_callback": _capture_runtime_event,
                "session_scope_id": session_scope_id,
                "chat_main_mode": str((runtime_request.invocation.metadata or {}).get("chat_main_mode") or ""),
                "chat_recent_mode": str((runtime_request.invocation.metadata or {}).get("chat_recent_mode") or ""),
                "chat_project_phase": str((runtime_request.invocation.metadata or {}).get("chat_project_phase") or ""),
                "chat_mode_state_snapshot": dict((runtime_request.invocation.metadata or {}).get("chat_mode_state_snapshot") or {}),
                "chat_session_state_snapshot": dict((runtime_request.invocation.metadata or {}).get("chat_session_state_snapshot") or {}),
                "_execution_capture": execution_capture,
            },
            stream_callback=stream_callback,
        )
        engine = self._conversation_turn_engine or self._build_conversation_turn_engine(runtime_request=runtime_request)
        turn_output = engine.run_turn(turn_input)
        turn_state = turn_output.state
        if turn_state is None:
            raise ValueError("conversation turn engine returned no turn state")
        pending_memory_id = turn_output.pending_memory_id
        previous_pending = turn_state.previous_pending
        user_prompt_with_recent = turn_state.prepared_user_prompt
        timings = dict(turn_output.metadata.get("timings") or {})
        prompt_metadata = dict(turn_state.prompt_metadata or {})
        execution_metadata = dict(execution_capture.get("metadata") or {})
        self._append_receipt_process_events(process_events, execution_metadata)
        original_user_prompt = str(
            (runtime_request.invocation.metadata or {}).get("original_user_prompt") or effective_prompt or ""
        ).strip()
        print(
            f"[chat-runtime] pending_memory_id={pending_memory_id} | route={runtime_request.decision.route} | model={effective_model} | user={re.sub(r'\\s+', ' ', original_user_prompt)[:100]}"
            + (f" | previous_pending={str((previous_pending or {}).get('topic') or '')[:80]}" if previous_pending else ""),
            flush=True,
        )
        print(f"[chat-runtime-prompt] {re.sub(r'\\s+', ' ', user_prompt_with_recent)[:200]}", flush=True)
        print(
            f"[chat-runtime-prompt-stats] route={runtime_request.decision.route} | user_len={int(prompt_metadata.get('user_len') or len(original_user_prompt))} | recent_len={int(prompt_metadata.get('recent_len') or len(user_prompt_with_recent))} | skills_len={int(prompt_metadata.get('skills_len') or 0)} | capabilities_len={int(prompt_metadata.get('capabilities_len') or 0)} | full_len={int(prompt_metadata.get('full_len') or len(turn_state.built_prompt))}",
            flush=True,
        )
        for stat in list(prompt_metadata.get("prompt_block_stats") or []):
            print(
                "[chat-prompt-block-stats] "
                f"block_id={str(stat.get('block_id') or '')}"
                f" | char_count={int(stat.get('char_count') or 0)}"
                f" | budget_chars={int(stat.get('budget_chars') or 0)}"
                f" | over_budget={str(bool(stat.get('over_budget'))).lower()}"
                f" | mode={str(prompt_metadata.get('chat_main_mode') or '')}"
                f" | channel={str(prompt_metadata.get('channel') or runtime_request.invocation.channel or '')}"
                f" | purity_level={int(prompt_metadata.get('prompt_purity_level') or 0)}"
                f" | include_reason={str(stat.get('include_reason') or '')}"
                f" | suppressed_by={str(stat.get('suppressed_by') or '')}"
                f" | source_ref={str(stat.get('source_ref') or '')}",
                flush=True,
            )
        print(
            "[chat-runtime-timing] "
            f"route={runtime_request.decision.route}"
            f" | intake={float(timings.get('intake') or 0.0):.3f}s"
            f" | recent={float(timings.get('recent') or 0.0):.3f}s"
            f" | skills={float(prompt_metadata.get('skills_elapsed') or 0.0):.3f}s"
            f" | capabilities={float(prompt_metadata.get('capabilities_elapsed') or 0.0):.3f}s"
            f" | build_prompt={float(prompt_metadata.get('build_prompt_elapsed') or timings.get('build_prompt') or 0.0):.3f}s",
            flush=True,
        )
        reply_text = turn_output.reply_text
        clean_reply, decide_list = self._parse_decide_fn(reply_text)
        visible_reply = safe_truncate_markdown(sanitize_markdown_structure(clean_reply or reply_text), int(max_len))
        bundle = self._build_output_bundle(
            runtime_request=runtime_request,
            visible_reply=visible_reply,
            decide_list=decide_list,
        )
        bundle = normalize_output_bundle_for_channel(bundle, runtime_request.channel_profile)
        print(
            "[chat-runtime-total] "
            f"route={runtime_request.decision.route}"
            f" | model_exec={float(timings.get('model_exec') or 0.0):.3f}s"
            f" | total={float(timings.get('total') or 0.0):.3f}s"
            f" | decide_count={len(decide_list)}",
            flush=True,
        )
        return ChatRuntimeExecution(
            reply_text=visible_reply,
            raw_reply_text=str(reply_text or ""),
            output_bundle=bundle,
            pending_memory_id=pending_memory_id,
            process_events=process_events,
            metadata={
                "recent_mode": turn_state.recent_mode,
                "route": runtime_request.decision.route,
                "decide_count": len(decide_list),
                "session_scope_id": session_scope_id,
                "process_events": process_events,
                "runtime_request": dict(execution_metadata.get("runtime_request") or {}),
                "execution_metadata": execution_metadata,
                "external_session": dict(execution_metadata.get("external_session") or {}),
                "recovery_state": dict(execution_metadata.get("recovery_state") or {}),
                "vendor_capabilities": dict(execution_metadata.get("vendor_capabilities") or {}),
                "skill_exposure": dict(prompt_metadata.get("skill_exposure") or {}),
                "prompt_block_stats": list(prompt_metadata.get("prompt_block_stats") or []),
                "prompt_block_budgets": dict(prompt_metadata.get("prompt_block_budgets") or {}),
                "intake_reused": bool(prompt_metadata.get("intake_reused")),
            },
        )

    def _build_conversation_turn_engine(self, *, runtime_request: ChatRuntimeRequest) -> ConversationTurnEngine:
        prefilled_intake = dict((runtime_request.invocation.metadata or {}).get("prefilled_intake_decision") or {})
        return ConversationTurnEngine(
            memory_provider=self._memory_provider,
            begin_turn_fallback_fn=self._memory_manager.begin_pending_turn,
            prepare_turn_input_fallback_fn=self._memory_manager.prepare_user_prompt_with_recent,
            classify_turn_fn=(
                (lambda prompt: dict(prefilled_intake))
                if prefilled_intake
                else self._request_intake_service.classify
            ),
            prompt_builder_fn=lambda **kwargs: self._build_prompt_for_turn(runtime_request=runtime_request, **kwargs),
            reply_executor_fn=self._execute_prompt_for_turn,
        )

    def _build_prompt_for_turn(
        self,
        *,
        runtime_request: ChatRuntimeRequest,
        prepared_user_prompt: str,
        turn_input: ConversationTurnInput,
        intake_decision: dict[str, Any],
        recent_mode: str,
    ) -> ConversationPromptBuild:
        effective_cli = str((runtime_request.invocation.metadata or {}).get("runtime_cli") or "").strip()
        raw_prompt_purity = runtime_request.invocation.metadata.get("prompt_purity")
        prompt_purity = dict(raw_prompt_purity) if isinstance(raw_prompt_purity, Mapping) else None
        purity_policy = resolve_prompt_purity_policy(prompt_purity)
        prompt_user_text = prepared_user_prompt if purity_policy.include_recent_in_prompt else turn_input.user_prompt
        metadata = dict(runtime_request.invocation.metadata or {})
        resolved_skill_collection_id = str(
            resolve_skill_collection_id(
                recent_mode=recent_mode,
                runtime_cli=effective_cli,
            )
            or ""
        ).strip()
        derived_skill_collection_id = str(runtime_request.compile_plan.skill_collection_id or "").strip()
        skill_collection_id = str(metadata.get("skill_collection_id") or "").strip() or resolved_skill_collection_id
        if (
            effective_cli
            and resolved_skill_collection_id
            and skill_collection_id == derived_skill_collection_id
        ):
            skill_collection_id = resolved_skill_collection_id
        raw_explicit_main_mode = str((runtime_request.invocation.metadata or {}).get("chat_main_mode") or "").strip()
        explicit_main_mode = canonical_main_mode(raw_explicit_main_mode) if raw_explicit_main_mode else ""
        raw_explicit_project_phase = str((runtime_request.invocation.metadata or {}).get("chat_project_phase") or "").strip()
        explicit_project_phase = canonical_project_phase(raw_explicit_project_phase) if raw_explicit_project_phase else ""
        role_id = str(metadata.get("chat_role_id") or runtime_request.compile_plan.role_id or "").strip()
        injection_tier = canonical_injection_tier(
            metadata.get("chat_injection_tier") or runtime_request.compile_plan.injection_tier
        )
        capability_policy = canonical_capability_policy(
            metadata.get("chat_capability_policy") or runtime_request.compile_plan.capability_policy
        )
        session_action = str(metadata.get("router_session_action") or runtime_request.compile_plan.router_session_action or "").strip()
        session_confidence = str(
            metadata.get("router_session_confidence") or runtime_request.compile_plan.router_session_confidence or ""
        ).strip()
        session_reason_flags = str(
            metadata.get("router_session_reason_flags") or runtime_request.compile_plan.router_session_reason_flags or ""
        ).strip()
        raw_skill_exposure = runtime_request.invocation.metadata.get("skill_exposure")
        skill_exposure = normalize_skill_exposure_payload(
            dict(raw_skill_exposure) if isinstance(raw_skill_exposure, Mapping) else None,
            default_collection_id=skill_collection_id,
            provider_skill_source="butler",
        )
        if skill_exposure is None:
            skill_exposure = normalize_skill_exposure_payload(
                {},
                default_collection_id=skill_collection_id,
                provider_skill_source="butler",
            )
        should_render_capabilities = bool(
            self._should_include_capabilities_for_mode(
                main_mode=explicit_main_mode,
                project_phase=explicit_project_phase,
                recent_mode=recent_mode,
                purity_policy=purity_policy,
                capability_policy=capability_policy,
            )
            and should_include_agent_capabilities_prompt(
                turn_input.user_prompt,
                explicit_main_mode or recent_mode,
                project_phase=explicit_project_phase,
            )
        )

        prompt_provider = self._prompt_provider
        skills_started_at = time.perf_counter()
        include_skills_prompt = should_include_skills_for_purity(turn_input.user_prompt, purity_policy)
        if prompt_provider is not None:
            if not include_skills_prompt:
                skills_prompt = ""
            elif hasattr(prompt_provider, "render_skill_exposure_prompt"):
                skills_prompt = prompt_provider.render_skill_exposure_prompt(
                    turn_input.workspace,
                    exposure=dict(skill_exposure or {}),
                    source_prompt=turn_input.user_prompt,
                    runtime_name="chat",
                    max_skills=100,
                    max_chars=2000,
                )
            elif hasattr(prompt_provider, "render_skills_prompt_for_collection"):
                skills_prompt = prompt_provider.render_skills_prompt_for_collection(
                    turn_input.workspace,
                    collection_id=skill_collection_id,
                )
            else:
                skills_prompt = prompt_provider.render_skills_prompt(turn_input.workspace)
            skills_elapsed = time.perf_counter() - skills_started_at
            capabilities_started_at = time.perf_counter()
            capabilities_prompt = (
                ""
                if not should_render_capabilities
                else prompt_provider.render_agent_capabilities_prompt(turn_input.workspace)
            )
            capabilities_elapsed = time.perf_counter() - capabilities_started_at
            build_prompt_started_at = time.perf_counter()
            prompt_debug_metadata: dict[str, Any] = {}
            prompt = prompt_provider.build_prompt(
                prompt_user_text,
                workspace=turn_input.workspace,
                image_paths=turn_input.image_paths,
                raw_user_prompt=turn_input.user_prompt,
                request_intake_prompt=self._request_intake_service.build_frontdesk_prompt_block(intake_decision),
                metadata={
                    "skills_prompt": skills_prompt,
                    "skill_exposure": dict(skill_exposure or {}),
                    "skill_collection_id": skill_collection_id,
                    "agent_capabilities_prompt": capabilities_prompt,
                    "request_intake_decision": dict(intake_decision or {}),
                    "runtime_cli": effective_cli,
                    "prompt_purity": prompt_purity,
                    "channel": runtime_request.invocation.channel,
                    "channel_profile": runtime_request.channel_profile,
                    "conversation_mode": explicit_main_mode,
                    "project_phase": explicit_project_phase,
                    "role_id": role_id,
                    "injection_tier": injection_tier,
                    "capability_policy": capability_policy,
                    "session_action": session_action,
                    "session_confidence": session_confidence,
                    "session_reason_flags": session_reason_flags,
                    "prompt_debug_metadata": prompt_debug_metadata,
                },
            )
        else:
            if include_skills_prompt:
                skills_prompt = render_skill_exposure_prompt(
                    turn_input.workspace,
                    exposure=dict(skill_exposure or {}),
                    source_prompt=turn_input.user_prompt,
                    runtime_name="chat",
                    max_catalog_skills=100,
                    max_catalog_chars=2000,
                )
            else:
                skills_prompt = ""
            if not skills_prompt and include_skills_prompt:
                try:
                    skills_prompt = self._render_skills_prompt_fn(turn_input.workspace, collection_id=skill_collection_id)
                except TypeError:
                    skills_prompt = self._render_skills_prompt_fn(turn_input.workspace)
            skills_elapsed = time.perf_counter() - skills_started_at
            capabilities_started_at = time.perf_counter()
            capabilities_prompt = (
                ""
                if not should_render_capabilities
                else self._render_agent_capabilities_prompt_fn(turn_input.workspace)
            )
            capabilities_elapsed = time.perf_counter() - capabilities_started_at
            build_prompt_started_at = time.perf_counter()
            prompt_debug_metadata = {}
            prompt = self._build_prompt_fn(
                prompt_user_text,
                turn_input.image_paths,
                skills_prompt=skills_prompt,
                skill_exposure=dict(skill_exposure or {}),
                skill_collection_id=skill_collection_id,
                agent_capabilities_prompt=capabilities_prompt,
                raw_user_prompt=turn_input.user_prompt,
                request_intake_prompt=self._request_intake_service.build_frontdesk_prompt_block(intake_decision),
                request_intake_decision=dict(intake_decision or {}),
                runtime_cli=effective_cli,
                prompt_purity=prompt_purity,
                channel=runtime_request.invocation.channel,
                channel_profile=runtime_request.channel_profile,
                conversation_mode=explicit_main_mode,
                project_phase=explicit_project_phase,
                role_id=role_id,
                injection_tier=injection_tier,
                capability_policy=capability_policy,
                session_action=session_action,
                session_confidence=session_confidence,
                session_reason_flags=session_reason_flags,
                prompt_debug_metadata=prompt_debug_metadata,
            )
        build_prompt_elapsed = time.perf_counter() - build_prompt_started_at
        return ConversationPromptBuild(
            prompt=prompt,
            metadata={
                "user_len": len(turn_input.user_prompt),
                "recent_len": len(prompt_user_text),
                "skills_len": len(skills_prompt),
                "capabilities_len": len(capabilities_prompt),
                "full_len": len(prompt),
                "skills_elapsed": skills_elapsed,
                "capabilities_elapsed": capabilities_elapsed,
                "build_prompt_elapsed": build_prompt_elapsed,
                "skill_exposure": summarize_skill_exposure(skill_exposure),
                "prompt_purity": prompt_purity or {},
                "prompt_block_stats": list(prompt_debug_metadata.get("block_stats") or []),
                "prompt_block_budgets": dict(prompt_debug_metadata.get("block_budgets") or {}),
                "chat_main_mode": explicit_main_mode or recent_mode,
                "chat_role_id": role_id,
                "chat_injection_tier": injection_tier,
                "chat_capability_policy": capability_policy,
                "channel": runtime_request.invocation.channel,
                "prompt_purity_level": int(purity_policy.level or 0),
                "intake_reused": bool(metadata.get("prefilled_intake_decision")),
            },
        )

    @staticmethod
    def _should_include_capabilities_for_mode(
        *,
        main_mode: str,
        project_phase: str,
        recent_mode: str,
        purity_policy,
        capability_policy: str = "conditional",
    ) -> bool:
        if not purity_policy.include_agent_capabilities:
            return False
        normalized_capability_policy = canonical_capability_policy(capability_policy)
        if normalized_capability_policy == "disabled":
            return False
        if normalized_capability_policy == "enabled":
            return True
        normalized_main_mode = canonical_main_mode(main_mode or recent_mode)
        normalized_project_phase = canonical_project_phase(project_phase)
        if normalized_main_mode in {SHARE_MAIN_MODE, BRAINSTORM_MAIN_MODE}:
            return False
        if normalized_main_mode == BACKGROUND_MAIN_MODE:
            return False
        if normalized_main_mode == PROJECT_MAIN_MODE:
            return normalized_project_phase == "imp"
        return True

    def _execute_prompt_for_turn(
        self,
        *,
        prompt: str,
        turn_input: ConversationTurnInput,
        turn_state,
    ) -> str:
        del turn_state
        event_callback = turn_input.metadata.get("event_callback")
        if not callable(event_callback):
            event_callback = None
        return self._execute_prompt(
            prompt=prompt,
            effective_prompt=turn_input.user_prompt,
            workspace=turn_input.workspace,
            timeout=turn_input.timeout,
            effective_model=turn_input.model,
            max_len=turn_input.max_len,
            stream_callback=turn_input.stream_callback,
            event_callback=event_callback,
            execution_capture=turn_input.metadata.get("_execution_capture"),
        )

    def _execute_prompt(
        self,
        *,
        prompt: str,
        effective_prompt: str,
        workspace: str,
        timeout: int,
        effective_model: str,
        max_len: int,
        stream_callback: Callable[[str], None] | None,
        event_callback: Callable[[dict], None] | None,
        execution_capture: dict[str, Any] | None,
    ) -> str:
        buffered_segments: list[str] = []
        if stream_callback:

            def _capture_segment(segment: str) -> None:
                buffered_segments.append(segment)
                stream_callback(segment)

            try:
                runner_result = self._run_agent_streaming_fn(
                    prompt,
                    workspace,
                    timeout,
                    effective_model,
                    _capture_segment,
                    event_callback,
                )
            except TypeError:
                runner_result = self._run_agent_streaming_fn(prompt, workspace, timeout, effective_model, _capture_segment)
        else:
            runner_result = self._run_agent_via_cli_fn(prompt, workspace, timeout, effective_model)

        out, ok, execution_metadata = self._normalize_execution_result(runner_result)
        if execution_capture is not None:
            execution_capture.clear()
            execution_capture.update({"metadata": execution_metadata})

        clean_out = sanitize_markdown_structure(out)
        if ok:
            return safe_truncate_markdown(clean_out, int(max_len))
        if not out:
            out = "管家bot 执行失败（可能 API 暂不可用）。"
        return safe_truncate_markdown(sanitize_markdown_structure(out), int(max_len))

    @staticmethod
    def _normalize_execution_result(result: Any) -> tuple[str, bool, dict[str, Any]]:
        if isinstance(result, tuple) and len(result) == 2:
            return str(result[0] or ""), bool(result[1]), {}
        metadata = dict(getattr(result, "metadata", {}) or {})
        status = str(getattr(result, "status", "") or "").strip().lower()
        if metadata or status:
            bundle = getattr(result, "output_bundle", None)
            if bundle is not None:
                for block in list(getattr(bundle, "text_blocks", []) or [])[::-1]:
                    text = str(getattr(block, "text", "") or "").strip()
                    if text:
                        return text, status == "completed", metadata
            return str(getattr(result, "summary", "") or "").strip(), status == "completed", metadata
        if isinstance(result, dict):
            return str(result.get("output") or ""), bool(result.get("ok")), dict(result.get("metadata") or {})
        return str(result or ""), False, {}

    def _append_receipt_process_events(self, process_events: list[dict[str, Any]], execution_metadata: dict[str, Any]) -> None:
        command_events = list(execution_metadata.get("command_events") or [])
        cli_events = dict(execution_metadata.get("cli_events") or {})
        command_events.extend(list(cli_events.get("command_events") or []))
        for item in command_events:
            normalized = self._normalize_process_event(item)
            if normalized:
                self._append_process_event(process_events, normalized)

    @staticmethod
    def _resolve_session_scope_id(runtime_request: ChatRuntimeRequest) -> str:
        channel = ChatRuntimeService._canonical_scope_channel(
            runtime_request.channel_profile.channel or runtime_request.invocation.channel
        )
        metadata = runtime_request.invocation.metadata or {}
        if channel == "weixin":
            raw_scope_id = (
                str(runtime_request.invocation.session_id or "").strip()
                or str(metadata.get("weixin.conversation_key") or "").strip()
                or str(metadata.get("weixin.raw_session_ref") or "").strip()
            )
        elif channel == "feishu":
            raw_scope_id = (
                str(runtime_request.invocation.session_id or "").strip()
                or str(metadata.get("feishu.raw_session_ref") or "").strip()
            )
        elif channel == "cli":
            raw_scope_id = str(runtime_request.invocation.session_id or "").strip()
        else:
            return ""
        return ChatRuntimeService._ensure_scope_namespace(raw_scope_id, channel=channel)

    @staticmethod
    def _canonical_scope_channel(channel: str) -> str:
        normalized = str(channel or "").strip().lower()
        if normalized in {"weixi", "weixin", "wechat"}:
            return "weixin"
        if normalized == "feishu":
            return "feishu"
        if normalized == "cli":
            return "cli"
        return ""

    @staticmethod
    def _ensure_scope_namespace(session_scope_id: str, *, channel: str) -> str:
        raw = str(session_scope_id or "").strip()
        normalized_channel = str(channel or "").strip().lower()
        if not raw or not normalized_channel:
            return ""
        if raw.lower().startswith(f"{normalized_channel}:"):
            return raw
        return f"{normalized_channel}:{raw}"

    def _build_output_bundle(
        self,
        *,
        runtime_request: ChatRuntimeRequest,
        visible_reply: str,
        decide_list: list[dict],
    ) -> OutputBundle:
        images: list[ImageAsset] = []
        files: list[FileAsset] = []
        artifacts: list[ArtifactRef] = []
        for item in decide_list:
            path_text = str(item.get("send") or "").strip()
            if not path_text:
                continue
            suffix = Path(path_text).suffix.lower()
            media_type = self._guess_media_type(suffix)
            metadata = {"source": "chat_decide"}
            if self._is_image_suffix(suffix):
                images.append(
                    ImageAsset(
                        path=path_text,
                        caption="chat decide output",
                        media_type=media_type,
                        metadata=metadata,
                    )
                )
            else:
                files.append(
                    FileAsset(
                        path=path_text,
                        description="chat decide output",
                        media_type=media_type,
                        metadata=metadata,
                    )
                )
            artifacts.append(
                ArtifactRef(
                    name=Path(path_text).name or path_text,
                    uri=path_text,
                    kind="local_file",
                    metadata=metadata,
                )
            )
        return OutputBundle(
            summary=f"chat reply [{runtime_request.decision.route}]",
            text_blocks=[TextBlock(text=visible_reply)] if visible_reply else [],
            images=images,
            files=files,
            artifacts=artifacts,
            metadata={
                "route": runtime_request.decision.route,
                "runtime_owner": runtime_request.decision.runtime_owner,
                "delivery_mode": runtime_request.decision.delivery_mode,
                "decide_count": len(decide_list),
                "channel_profile": runtime_request.channel_profile.channel,
            },
        )

    @staticmethod
    def _normalize_process_event(event: Any) -> dict[str, Any] | None:
        if not isinstance(event, dict):
            return None
        kind = str(event.get("kind") or "").strip().lower()
        text = ChatRuntimeService._strip_process_ordinal(str(event.get("text") or ""))
        status = str(event.get("status") or "").strip().lower()
        source = str(event.get("source") or "").strip().lower()
        event_type = str(event.get("event_type") or "").strip().lower()
        if kind not in {"command", "usage", "stderr", "error"} and not text:
            return None
        payload: dict[str, Any] = {"kind": kind or "event", "text": text[:240]}
        if status:
            payload["status"] = status[:40]
        if source:
            payload["source"] = source[:40]
        if event_type:
            payload["event_type"] = event_type[:80]
        return payload

    @staticmethod
    def _append_process_event(current: list[dict[str, Any]], event: dict[str, Any]) -> None:
        if current and current[-1] == event:
            return
        current.append(dict(event))

    @staticmethod
    def _strip_process_ordinal(text: str) -> str:
        normalized = re.sub(r"\s+", " ", str(text or "").strip())
        return _LEADING_PROCESS_ORDINAL_RE.sub("", normalized).strip()

    @staticmethod
    def _guess_media_type(suffix: str) -> str:
        mapping = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
            ".md": "text/markdown",
            ".txt": "text/plain",
            ".json": "application/json",
            ".csv": "text/csv",
            ".yaml": "application/yaml",
            ".yml": "application/yaml",
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".webm": "video/webm",
        }
        return mapping.get(str(suffix or "").strip().lower(), "application/octet-stream")

    @staticmethod
    def _is_image_suffix(suffix: str) -> bool:
        return str(suffix or "").strip().lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


__all__ = ["ChatRuntimeExecution", "ChatRuntimeService"]
