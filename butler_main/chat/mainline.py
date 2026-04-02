from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any
from uuid import uuid4

from agents_os.contracts import Invocation, OutputBundle, TextBlock
from agents_os.runtime import RequestIntakeService, RouteProjection, RuntimeRequest
from butler_main.orchestrator import ButlerMissionOrchestrator
from .channel_profiles import normalize_output_bundle_for_channel
from .feature_switches import chat_frontdoor_slash_mode_enabled, chat_frontdoor_tasks_enabled
from .frontdoor_modes import (
    is_background_compat_mode,
    is_control_mode,
    is_project_phase_mode,
    is_scene_mode,
    parse_frontdoor_slash_command,
)
from .governance import FrontDoorGovernService
from .negotiation import CampaignNegotiationService
from .orchestrator_bootstrap import ChatOrchestratorBootstrapService, OrchestratorBootstrapResult
from .prompt_purity import parse_pure_prompt_directive
from .session_modes import (
    BACKGROUND_MAIN_MODE,
    BRAINSTORM_MAIN_MODE,
    CHAT_MAIN_MODE,
    PROJECT_MAIN_MODE,
    SHARE_MAIN_MODE,
    canonical_main_mode,
    canonical_project_phase,
    describe_mode_switch,
    load_chat_session_mode_state,
    project_phase_from_state,
    reset_chat_session_mode_state,
    resolve_session_scope_id_from_invocation,
    save_chat_session_mode_state,
    update_state_after_turn,
)
from .session_selection import (
    build_chat_session_state_after_turn,
    load_chat_session_state,
    save_chat_session_state,
    select_chat_session,
)
from .task_query import FrontDoorTaskQueryService
from butler_main.chat.feishu_bot.delivery import FeishuDeliveryAdapter, FeishuDeliveryPlan
from butler_main.chat.feishu_bot.input import FeishuInputAdapter
from butler_main.chat.weixi.delivery import WeixinDeliveryAdapter, WeixinDeliveryPlan
from butler_main.chat.weixi.input import WeixinInputAdapter
from .routing import ChatRouter, ChatRuntimeRequest


@dataclass(slots=True, frozen=True)
class ChatMainlineResult:
    text: str
    invocation: Invocation
    runtime_request: ChatRuntimeRequest
    output_bundle: OutputBundle
    delivery_plan: FeishuDeliveryPlan | WeixinDeliveryPlan | None = None
    metadata: dict[str, Any] | None = None


class ChatMainlineService:
    """Bridge the new front-door contracts to the current Butler chat runtime."""

    def __init__(
        self,
        *,
        feishu_input_adapter: FeishuInputAdapter | None = None,
        weixin_input_adapter: WeixinInputAdapter | None = None,
        chat_router: ChatRouter | None = None,
        talk_router: ChatRouter | None = None,
        mission_orchestrator: object | None = None,
        task_query: FrontDoorTaskQueryService | None = None,
        govern_service: FrontDoorGovernService | None = None,
        campaign_negotiation: CampaignNegotiationService | None = None,
        orchestrator_bootstrap: object | None = None,
        delivery_adapter: FeishuDeliveryAdapter | None = None,
        weixin_delivery_adapter: WeixinDeliveryAdapter | None = None,
        request_intake_service: RequestIntakeService | None = None,
    ) -> None:
        self._feishu_input_adapter = feishu_input_adapter or FeishuInputAdapter()
        self._weixin_input_adapter = weixin_input_adapter or WeixinInputAdapter()
        self._chat_router = chat_router or talk_router or ChatRouter()
        self._mission_orchestrator = mission_orchestrator or ButlerMissionOrchestrator()
        self._orchestrator_bootstrap = orchestrator_bootstrap or ChatOrchestratorBootstrapService()
        self._task_query = task_query or FrontDoorTaskQueryService()
        self._govern_service = govern_service or FrontDoorGovernService()
        self._campaign_negotiation = campaign_negotiation or CampaignNegotiationService(
            orchestrator_bootstrap=self._orchestrator_bootstrap,
        )
        self._delivery_adapter = delivery_adapter or FeishuDeliveryAdapter()
        self._weixin_delivery_adapter = weixin_delivery_adapter or WeixinDeliveryAdapter()
        self._request_intake_service = request_intake_service or RequestIntakeService()

    def handle_prompt(
        self,
        user_prompt: str,
        *,
        chat_executor: Callable[[ChatRuntimeRequest], str] | None = None,
        talk_executor: Callable[[ChatRuntimeRequest], str] | None = None,
        invocation_metadata: Mapping[str, Any] | None = None,
    ) -> ChatMainlineResult:
        invocation = self.build_invocation(user_prompt, invocation_metadata=invocation_metadata)
        if bool((invocation.metadata or {}).get("prompt_purity")) and not str(invocation.user_text or "").strip():
            runtime_request = self._chat_router.build_runtime_request(invocation)
            return self._result_for_prompt_purity_help(runtime_request)
        frontdoor_tasks_enabled = chat_frontdoor_tasks_enabled()
        route_decision = self._chat_router.route(invocation)
        if frontdoor_tasks_enabled and route_decision.route == "mission_ingress":
            mission_runtime_request = self._chat_router.build_runtime_request(
                invocation,
                decision=route_decision,
                mode_state=None,
            )
            bootstrap = self._ensure_orchestrator_online()
            if bootstrap is not None and not bootstrap.ok:
                return self._result_for_orchestrator_unavailable(mission_runtime_request, bootstrap)
            return self._handle_mission_request(mission_runtime_request)
        workspace = str(invocation.metadata.get("workspace") or invocation.metadata.get("workspace_root") or ".")
        session_scope_id = resolve_session_scope_id_from_invocation(invocation)
        mode_state = load_chat_session_mode_state(workspace, session_scope_id=session_scope_id)
        chat_session_state = load_chat_session_state(workspace, session_scope_id=session_scope_id)
        slash_command = parse_frontdoor_slash_command(invocation.user_text)
        if slash_command is not None and not chat_frontdoor_slash_mode_enabled(slash_command.mode_id):
            slash_command = None
        mode_switch_result = self._handle_mode_switch_if_needed(
            workspace=workspace,
            session_scope_id=session_scope_id,
            invocation=invocation,
            slash_command=slash_command,
            mode_state=mode_state,
        )
        if mode_switch_result is not None:
            return mode_switch_result

        explicit_phase = canonical_project_phase(slash_command.mode_id) if slash_command is not None else ""
        frontdoor_text = slash_command.body if slash_command is not None and slash_command.body else invocation.user_text
        session_selection = select_chat_session(
            frontdoor_text,
            current_state=chat_session_state,
            mode_state=mode_state.to_dict() if hasattr(mode_state, "to_dict") else dict(mode_state or {}),
            explicit_lock=self._session_selection_locked(slash_command=slash_command),
        )
        effective_mode_state = self._resolve_effective_mode_state(mode_state=mode_state, slash_command=slash_command)
        effective_chat_session_state = chat_session_state
        if session_selection.action == "reopen_new_session":
            effective_mode_state = type(mode_state)()
            save_chat_session_mode_state(
                workspace,
                session_scope_id=session_scope_id,
                state=effective_mode_state,
            )
            effective_chat_session_state = build_chat_session_state_after_turn(
                chat_session_state,
                user_text=frontdoor_text,
                main_mode=CHAT_MAIN_MODE,
                session_action=session_selection.action,
                chat_session_id=session_selection.chat_session_id,
            )
            save_chat_session_state(
                workspace,
                session_scope_id=session_scope_id,
                state=effective_chat_session_state,
            )
        elif (
            not str(effective_chat_session_state.active_chat_session_id or "").strip()
            and str(session_selection.chat_session_id or "").strip()
        ):
            effective_chat_session_state = build_chat_session_state_after_turn(
                chat_session_state,
                user_text=frontdoor_text,
                main_mode=canonical_main_mode(effective_mode_state.main_mode),
                session_action=session_selection.action,
                chat_session_id=session_selection.chat_session_id,
            )
            save_chat_session_state(
                workspace,
                session_scope_id=session_scope_id,
                state=effective_chat_session_state,
            )
        router_override_source = self._router_override_source(mode_state=effective_mode_state, slash_command=slash_command)
        explicit_frontdoor_mode = self._explicit_frontdoor_mode_id(
            slash_command=slash_command,
            mode_state=effective_mode_state,
        )
        frontdoor_capabilities_enabled = (
            frontdoor_tasks_enabled
            or bool(explicit_frontdoor_mode)
            or canonical_main_mode(effective_mode_state.main_mode) == BACKGROUND_MAIN_MODE
        )
        intake_decision: dict[str, Any] = {}
        if frontdoor_capabilities_enabled:
            intake_decision = self._request_intake_service.classify(
                frontdoor_text,
                conversation_id=invocation.session_id,
                forced_frontdoor_mode=explicit_frontdoor_mode,
            )
        effective_invocation = replace(
            invocation,
            user_text=frontdoor_text,
            metadata={
                **dict(invocation.metadata or {}),
                "chat_main_mode": canonical_main_mode(effective_mode_state.main_mode),
                "chat_recent_mode": canonical_main_mode(effective_mode_state.main_mode),
                "chat_project_phase": explicit_phase or (
                    project_phase_from_state(effective_mode_state)
                    if canonical_main_mode(effective_mode_state.main_mode) == PROJECT_MAIN_MODE
                    else ""
                ),
                "router_explicit_override_source": router_override_source,
                "router_session_action": session_selection.action,
                "router_session_confidence": session_selection.confidence,
                "router_session_reason_flags": session_selection.reason_flags_text(),
                "chat_session_id": str(effective_chat_session_state.active_chat_session_id or session_selection.chat_session_id or "").strip(),
                "prefilled_intake_decision": dict(intake_decision or {}),
                "chat_mode_state_snapshot": effective_mode_state.to_dict(),
                "chat_session_state_snapshot": effective_chat_session_state.to_dict(),
            },
        )
        runtime_request = self._chat_router.build_runtime_request(
            effective_invocation,
            decision=route_decision,
            mode_state=effective_mode_state.to_dict() if hasattr(effective_mode_state, "to_dict") else dict(effective_mode_state or {}),
        )
        if slash_command is not None and slash_command.mode_id == "govern":
            govern_result = self._govern_service.handle(
                workspace=workspace,
                session_id=runtime_request.invocation.session_id,
                user_text=frontdoor_text,
                slash_command=slash_command,
            )
            if govern_result.handled and govern_result.output_bundle is not None:
                bundle = normalize_output_bundle_for_channel(govern_result.output_bundle, runtime_request.channel_profile)
                text = self._text_from_bundle(bundle, fallback=str(bundle.summary or "").strip())
                delivery_plan = self._create_delivery_plan(runtime_request.delivery_session, bundle)
                return ChatMainlineResult(
                    text=text,
                    invocation=runtime_request.invocation,
                    runtime_request=runtime_request,
                    output_bundle=bundle,
                    delivery_plan=delivery_plan,
                    metadata={**(govern_result.metadata or {}), "route": runtime_request.decision.route},
                )
        task_query = None
        if frontdoor_capabilities_enabled:
            task_query = self._task_query.handle(
                workspace=workspace,
                session_id=runtime_request.invocation.session_id,
                user_text=frontdoor_text,
                force_status=slash_command is not None and slash_command.mode_id == "status",
            )
        if task_query is not None and task_query.handled and task_query.output_bundle is not None:
            executor = chat_executor or talk_executor
            model_reply_prompt = str((task_query.metadata or {}).get("model_reply_prompt") or "").strip()
            if executor is not None and model_reply_prompt and not self._frontdoor_execution_blocked(task_query):
                result = self._handle_frontdoor_capability_via_model(
                    runtime_request,
                    chat_executor=executor,
                    capability_result=task_query,
                    model_reply_prompt=model_reply_prompt,
                    workspace=workspace,
                    session_scope_id=session_scope_id,
                    mode_state=effective_mode_state,
                    chat_session_state=effective_chat_session_state,
                    source_user_text=frontdoor_text,
                )
                return result
            bundle = normalize_output_bundle_for_channel(task_query.output_bundle, runtime_request.channel_profile)
            text = self._text_from_bundle(bundle, fallback=str(bundle.summary or "").strip())
            delivery_plan = self._create_delivery_plan(runtime_request.delivery_session, bundle)
            result = ChatMainlineResult(
                text=text,
                invocation=runtime_request.invocation,
                runtime_request=runtime_request,
                output_bundle=bundle,
                delivery_plan=delivery_plan,
                metadata={**(task_query.metadata or {}), "route": runtime_request.decision.route},
            )
            self._persist_mode_state_after_result(
                workspace=workspace,
                session_scope_id=session_scope_id,
                mode_state=effective_mode_state,
                chat_session_state=effective_chat_session_state,
                compile_plan=runtime_request.compile_plan,
                user_text=frontdoor_text,
                assistant_text=result.text,
            )
            return result
        negotiation = None
        if frontdoor_capabilities_enabled:
            negotiation = self._campaign_negotiation.handle(
                workspace=workspace,
                session_id=runtime_request.invocation.session_id,
                user_text=frontdoor_text,
                delivery_session=runtime_request.delivery_session,
                force_open=(
                    canonical_main_mode(effective_mode_state.main_mode) == BACKGROUND_MAIN_MODE
                    or bool(intake_decision.get("should_discuss_mode_first"))
                    or (slash_command is not None and slash_command.mode_id in {"bg", "delivery", "research"})
                ),
                intake_decision=intake_decision,
                explicit_mode=explicit_frontdoor_mode,
            )
        if negotiation is not None and negotiation.handled and negotiation.output_bundle is not None:
            executor = chat_executor or talk_executor
            model_reply_prompt = str((negotiation.metadata or {}).get("model_reply_prompt") or "").strip()
            if executor is not None and model_reply_prompt and not self._frontdoor_execution_blocked(negotiation):
                result = self._handle_frontdoor_capability_via_model(
                    runtime_request,
                    chat_executor=executor,
                    capability_result=negotiation,
                    model_reply_prompt=model_reply_prompt,
                    workspace=workspace,
                    session_scope_id=session_scope_id,
                    mode_state=effective_mode_state,
                    chat_session_state=effective_chat_session_state,
                    source_user_text=frontdoor_text,
                )
                return result
            bundle = normalize_output_bundle_for_channel(negotiation.output_bundle, runtime_request.channel_profile)
            text = self._text_from_bundle(bundle, fallback=str(bundle.summary or "").strip())
            delivery_plan = self._create_delivery_plan(runtime_request.delivery_session, bundle)
            result = ChatMainlineResult(
                text=text,
                invocation=runtime_request.invocation,
                runtime_request=runtime_request,
                output_bundle=bundle,
                delivery_plan=delivery_plan,
                metadata={
                    **(negotiation.metadata or {}),
                    "route": runtime_request.decision.route,
                    "request_intake": intake_decision,
                },
            )
            self._persist_mode_state_after_result(
                workspace=workspace,
                session_scope_id=session_scope_id,
                mode_state=effective_mode_state,
                chat_session_state=effective_chat_session_state,
                compile_plan=runtime_request.compile_plan,
                user_text=frontdoor_text,
                assistant_text=result.text,
            )
            return result
        executor = chat_executor or talk_executor
        if executor is None:
            raise ValueError("ChatMainlineService.handle_prompt requires chat_executor or talk_executor")
        return self._handle_chat_request(
            runtime_request,
            chat_executor=executor,
            workspace=workspace,
            session_scope_id=session_scope_id,
            mode_state=effective_mode_state,
            chat_session_state=effective_chat_session_state,
            source_user_text=frontdoor_text,
        )

    def build_invocation(
        self,
        user_prompt: str,
        *,
        invocation_metadata: Mapping[str, Any] | None = None,
    ) -> Invocation:
        metadata = dict(invocation_metadata or {})
        pure_directive = parse_pure_prompt_directive(user_prompt)
        effective_user_text = str(user_prompt or "")
        if pure_directive is not None:
            metadata["prompt_purity"] = {
                "level": pure_directive.level,
                "command_text": pure_directive.command_text,
                "source": "slash_command",
            }
            effective_user_text = pure_directive.body
        feishu_event = metadata.get("feishu_event")
        if isinstance(feishu_event, Mapping):
            overrides = dict(metadata.get("metadata_overrides") or {})
            for key in ("workspace", "workspace_root", "mission_operation", "mission_id", "action", "feedback"):
                value = metadata.get(key)
                if value not in (None, ""):
                    overrides[key] = value
            invocation = self._feishu_input_adapter.build_invocation(
                feishu_event,
                entrypoint_hint=str(metadata.get("entrypoint_hint") or "").strip(),
                metadata_overrides=overrides,
            )
            if pure_directive is not None:
                return replace(
                    invocation,
                    user_text=effective_user_text,
                    metadata={**dict(invocation.metadata or {}), "prompt_purity": dict(metadata.get("prompt_purity") or {})},
                )
            return invocation
        weixin_event = metadata.get("weixin_event")
        if isinstance(weixin_event, Mapping):
            overrides = dict(metadata.get("metadata_overrides") or {})
            for key in ("workspace", "workspace_root", "mission_operation", "mission_id", "action", "feedback"):
                value = metadata.get(key)
                if value not in (None, ""):
                    overrides[key] = value
            invocation = self._weixin_input_adapter.build_invocation(
                weixin_event,
                entrypoint_hint=str(metadata.get("entrypoint_hint") or "").strip(),
                metadata_overrides=overrides,
            )
            if pure_directive is not None:
                return replace(
                    invocation,
                    user_text=effective_user_text,
                    metadata={**dict(invocation.metadata or {}), "prompt_purity": dict(metadata.get("prompt_purity") or {})},
                )
            return invocation

        channel = str(metadata.get("channel") or "local").strip() or "local"
        session_id = str(metadata.get("session_id") or metadata.get("message_id") or f"session_{uuid4().hex[:12]}").strip()
        actor_id = str(metadata.get("actor_id") or metadata.get("open_id") or "local_user").strip() or "local_user"
        entrypoint = str(metadata.get("entrypoint_hint") or "chat").strip() or "chat"
        normalized_metadata = {
            key: value
            for key, value in metadata.items()
            if key not in {"feishu_event", "weixin_event", "metadata_overrides"} and value not in (None, "")
        }
        return Invocation(
            entrypoint=entrypoint,
            channel=channel,
            session_id=session_id,
            actor_id=actor_id,
            user_text=effective_user_text,
            source_event_id=str(metadata.get("message_id") or "").strip(),
            metadata=normalized_metadata,
        )

    def _handle_mode_switch_if_needed(
        self,
        *,
        workspace: str,
        session_scope_id: str,
        invocation: Invocation,
        slash_command,
        mode_state,
    ) -> ChatMainlineResult | None:
        if slash_command is None:
            return None
        mode_id = str(slash_command.mode_id or "").strip().lower()
        if mode_id not in {"chat", "reset"} and not is_scene_mode(mode_id) and not is_project_phase_mode(mode_id):
            return None
        if mode_id in {"chat", "reset"}:
            next_state = reset_chat_session_mode_state(workspace, session_scope_id=session_scope_id)
            if str(slash_command.body or "").strip():
                return None
            runtime_request = self._chat_router.build_runtime_request(replace(invocation, user_text=""), mode_state=next_state.to_dict())
            return self._result_for_mode_switch(runtime_request, text=describe_mode_switch(CHAT_MAIN_MODE))

        current_state = self._resolve_effective_mode_state(mode_state=mode_state, slash_command=slash_command)
        if is_scene_mode(mode_id):
            next_state = type(current_state)(
                main_mode=canonical_main_mode(mode_id),
                project_phase="plan" if mode_id == PROJECT_MAIN_MODE else "",
                project_next_phase="plan" if mode_id == PROJECT_MAIN_MODE else "",
                mode_artifacts=dict(current_state.mode_artifacts or {}),
                updated_at="",
            )
        else:
            next_state = type(current_state)(
                main_mode=PROJECT_MAIN_MODE,
                project_phase=canonical_project_phase(mode_id) or "plan",
                project_next_phase=canonical_project_phase(mode_id) or "plan",
                mode_artifacts=dict(current_state.mode_artifacts or {}),
                updated_at="",
            )
        save_chat_session_mode_state(workspace, session_scope_id=session_scope_id, state=next_state)
        if str(slash_command.body or "").strip():
            return None
        runtime_request = self._chat_router.build_runtime_request(replace(invocation, user_text=""), mode_state=next_state.to_dict())
        return self._result_for_mode_switch(
            runtime_request,
            text=describe_mode_switch(
                next_state.main_mode,
                project_phase=project_phase_from_state(next_state),
            ),
        )

    def _resolve_effective_mode_state(self, *, mode_state, slash_command):
        current_state = mode_state
        if slash_command is None:
            return current_state
        mode_id = str(slash_command.mode_id or "").strip().lower()
        if mode_id in {"chat", "reset"}:
            return type(current_state)()
        if is_scene_mode(mode_id):
            return type(current_state)(
                main_mode=canonical_main_mode(mode_id),
                project_phase="plan" if mode_id == PROJECT_MAIN_MODE else "",
                project_next_phase="plan" if mode_id == PROJECT_MAIN_MODE else "",
                mode_artifacts=dict(current_state.mode_artifacts or {}),
                updated_at=current_state.updated_at,
            )
        if is_project_phase_mode(mode_id):
            phase = canonical_project_phase(mode_id) or "plan"
            return type(current_state)(
                main_mode=PROJECT_MAIN_MODE,
                project_phase=phase,
                project_next_phase=phase,
                mode_artifacts=dict(current_state.mode_artifacts or {}),
                updated_at=current_state.updated_at,
            )
        if is_background_compat_mode(mode_id):
            return type(current_state)(
                main_mode=BACKGROUND_MAIN_MODE,
                project_phase=current_state.project_phase,
                project_next_phase=current_state.project_next_phase,
                mode_artifacts=dict(current_state.mode_artifacts or {}),
                updated_at=current_state.updated_at,
            )
        return current_state

    @staticmethod
    def _explicit_frontdoor_mode_id(*, slash_command, mode_state) -> str:
        if slash_command is not None:
            mode_id = str(slash_command.mode_id or "").strip().lower()
            if mode_id in {"status", "govern", "bg", "delivery", "research"}:
                return mode_id
        if canonical_main_mode(mode_state.main_mode) == BACKGROUND_MAIN_MODE:
            return "bg"
        return ""

    @staticmethod
    def _session_selection_locked(*, slash_command) -> bool:
        if slash_command is None:
            return False
        mode_id = str(slash_command.mode_id or "").strip().lower()
        return bool(
            mode_id in {"chat", "reset"}
            or is_scene_mode(mode_id)
            or is_project_phase_mode(mode_id)
            or is_background_compat_mode(mode_id)
        )

    @staticmethod
    def _router_override_source(*, mode_state, slash_command) -> str:
        if slash_command is not None:
            mode_id = str(slash_command.mode_id or "").strip().lower()
            if mode_id in {"chat", "reset"} or is_scene_mode(mode_id) or is_project_phase_mode(mode_id) or is_background_compat_mode(mode_id):
                return "slash_command"
        if canonical_main_mode((mode_state.main_mode if mode_state is not None else "") or "") != CHAT_MAIN_MODE:
            return "sticky_mode"
        return ""

    def _persist_mode_state_after_result(
        self,
        *,
        workspace: str,
        session_scope_id: str,
        mode_state,
        chat_session_state,
        compile_plan,
        user_text: str,
        assistant_text: str,
    ) -> None:
        selected_main_mode = canonical_main_mode(getattr(compile_plan, "main_mode", "") or mode_state.main_mode)
        save_chat_session_state(
            workspace,
            session_scope_id=session_scope_id,
            state=build_chat_session_state_after_turn(
                chat_session_state,
                user_text=user_text,
                main_mode=selected_main_mode,
                session_action=str(getattr(compile_plan, "router_session_action", "") or "continue_current"),
                chat_session_id=str(
                    getattr(compile_plan, "chat_session_id", "")
                    or getattr(chat_session_state, "active_chat_session_id", "")
                    or ""
                ),
            ),
        )
        if selected_main_mode == CHAT_MAIN_MODE:
            save_chat_session_mode_state(
                workspace,
                session_scope_id=session_scope_id,
                state=type(mode_state)(
                    main_mode=CHAT_MAIN_MODE,
                    project_phase="",
                    project_next_phase="",
                    mode_artifacts=dict(getattr(mode_state, "mode_artifacts", {}) or {}),
                    updated_at="",
                ),
            )
            return
        next_state = update_state_after_turn(
            mode_state,
            user_text=user_text,
            assistant_reply=assistant_text,
            explicit_mode=selected_main_mode,
            explicit_project_phase=getattr(compile_plan, "project_phase", "") or (
                project_phase_from_state(mode_state)
                if canonical_main_mode(mode_state.main_mode) == PROJECT_MAIN_MODE
                else ""
            ),
            active_role=str(getattr(compile_plan, "role_id", "") or ""),
            injection_tier=str(getattr(compile_plan, "injection_tier", "") or "standard"),
            auto_route_reason=str(getattr(compile_plan, "auto_route_reason", "") or ""),
            explicit_override_source=str(getattr(compile_plan, "explicit_override_source", "") or ""),
        )
        save_chat_session_mode_state(workspace, session_scope_id=session_scope_id, state=next_state)

    def _result_for_mode_switch(self, runtime_request: ChatRuntimeRequest, *, text: str) -> ChatMainlineResult:
        bundle = OutputBundle(
            summary="chat mode switched",
            text_blocks=[TextBlock(text=text)],
            metadata={
                "route": runtime_request.decision.route,
                "runtime_owner": runtime_request.decision.runtime_owner,
                "mode_switch": True,
            },
        )
        bundle = normalize_output_bundle_for_channel(bundle, runtime_request.channel_profile)
        delivery_plan = self._create_delivery_plan(runtime_request.delivery_session, bundle)
        return ChatMainlineResult(
            text=text,
            invocation=runtime_request.invocation,
            runtime_request=runtime_request,
            output_bundle=bundle,
            delivery_plan=delivery_plan,
            metadata={"route": runtime_request.decision.route, "mode_switch": True},
        )

    def _handle_chat_request(
        self,
        runtime_request: ChatRuntimeRequest,
        *,
        chat_executor: Callable[[ChatRuntimeRequest], str],
        workspace: str,
        session_scope_id: str,
        mode_state,
        chat_session_state=None,
        source_user_text: str,
    ) -> ChatMainlineResult:
        execution = chat_executor(runtime_request)
        bundle: OutputBundle
        if hasattr(execution, "output_bundle") and hasattr(execution, "reply_text"):
            text = str(getattr(execution, "reply_text") or "").strip()
            bundle = getattr(execution, "output_bundle")
            if not isinstance(bundle, OutputBundle):
                bundle = OutputBundle(
                    summary=f"chat reply [{runtime_request.decision.route}]",
                    text_blocks=[TextBlock(text=text)] if text else [],
                    metadata={
                        "route": runtime_request.decision.route,
                        "runtime_owner": runtime_request.decision.runtime_owner,
                    },
                )
        else:
            text = str(execution or "").strip()
            bundle = OutputBundle(
                summary=f"chat reply [{runtime_request.decision.route}]",
                text_blocks=[TextBlock(text=text)] if text else [],
                metadata={
                    "route": runtime_request.decision.route,
                    "runtime_owner": runtime_request.decision.runtime_owner,
                },
            )
        delivery_plan = self._create_delivery_plan(runtime_request.delivery_session, bundle)
        result = ChatMainlineResult(
            text=text,
            invocation=runtime_request.invocation,
            runtime_request=runtime_request,
            output_bundle=bundle,
            delivery_plan=delivery_plan,
            metadata={"route": runtime_request.decision.route},
        )
        self._persist_mode_state_after_result(
            workspace=workspace,
            session_scope_id=session_scope_id,
            mode_state=mode_state,
            chat_session_state=chat_session_state,
            compile_plan=runtime_request.compile_plan,
            user_text=source_user_text,
            assistant_text=result.text,
        )
        return result

    def _handle_frontdoor_capability_via_model(
        self,
        runtime_request: ChatRuntimeRequest,
        *,
        chat_executor: Callable[[ChatRuntimeRequest], str],
        capability_result,
        model_reply_prompt: str,
        workspace: str,
        session_scope_id: str,
        mode_state,
        chat_session_state=None,
        source_user_text: str,
    ) -> ChatMainlineResult:
        negotiation_invocation = replace(
            runtime_request.invocation,
            user_text=model_reply_prompt,
            metadata={
                **dict(runtime_request.invocation.metadata or {}),
                "original_user_prompt": str(
                    (runtime_request.invocation.metadata or {}).get("original_user_prompt")
                    or runtime_request.invocation.user_text
                    or ""
                ).strip(),
                "negotiation_status": str((capability_result.metadata or {}).get("negotiation_status") or "").strip(),
                "chat_execution_blocked": bool((capability_result.metadata or {}).get("chat_execution_blocked")),
                "frontdoor_action": str((capability_result.metadata or {}).get("frontdoor_action") or "").strip(),
                "frontdoor_target_kind": str((capability_result.metadata or {}).get("frontdoor_target_kind") or "").strip(),
                "frontdoor_target_id": str((capability_result.metadata or {}).get("frontdoor_target_id") or "").strip(),
                "frontdoor_resolution_source": str((capability_result.metadata or {}).get("frontdoor_resolution_source") or "").strip(),
                "frontdoor_mode": "collaboration_capability",
            },
        )
        negotiation_request = replace(runtime_request, invocation=negotiation_invocation)
        result = self._handle_chat_request(
            negotiation_request,
            chat_executor=chat_executor,
            workspace=workspace,
            session_scope_id=session_scope_id,
            mode_state=mode_state,
            chat_session_state=chat_session_state,
            source_user_text=source_user_text,
        )
        merged_bundle = OutputBundle(
            summary=result.output_bundle.summary,
            text_blocks=list(result.output_bundle.text_blocks),
            images=list(result.output_bundle.images),
            files=list(result.output_bundle.files),
            cards=list(result.output_bundle.cards),
            doc_links=list(result.output_bundle.doc_links),
            artifacts=list(result.output_bundle.artifacts),
            metadata={**dict(result.output_bundle.metadata or {}), **dict(capability_result.metadata or {})},
        )
        return ChatMainlineResult(
            text=result.text,
            invocation=result.invocation,
            runtime_request=result.runtime_request,
            output_bundle=merged_bundle,
            delivery_plan=result.delivery_plan,
            metadata={**dict(result.metadata or {}), **dict(capability_result.metadata or {}), "route": runtime_request.decision.route},
        )

    def _handle_mission_request(self, runtime_request: ChatRuntimeRequest) -> ChatMainlineResult:
        orchestrator_request = self._build_mission_runtime_request(runtime_request)
        receipt = self._mission_orchestrator.orchestrate(orchestrator_request)
        bundle = receipt.output_bundle
        if not isinstance(bundle, OutputBundle):
            bundle = OutputBundle(
                summary=str(receipt.summary or "mission receipt").strip() or "mission receipt",
                text_blocks=[TextBlock(text=str(receipt.summary or "").strip())] if str(receipt.summary or "").strip() else [],
                metadata={"route": runtime_request.decision.route, "runtime_owner": runtime_request.decision.runtime_owner},
            )
        bundle = normalize_output_bundle_for_channel(bundle, runtime_request.channel_profile)
        text = self._text_from_bundle(bundle, fallback=str(receipt.summary or "").strip())
        delivery_session = receipt.delivery_request.session if receipt.delivery_request is not None else runtime_request.delivery_session
        delivery_plan = self._create_delivery_plan(delivery_session, bundle)
        return ChatMainlineResult(
            text=text,
            invocation=runtime_request.invocation,
            runtime_request=runtime_request,
            output_bundle=bundle,
            delivery_plan=delivery_plan,
            metadata={
                "route": runtime_request.decision.route,
                "workflow_id": str(receipt.workflow_id or "").strip(),
                "status": str(receipt.status or "").strip(),
                "mission_operation": str((receipt.metadata or {}).get("mission_operation") or "").strip(),
            },
        )

    def _result_for_prompt_purity_help(self, runtime_request: ChatRuntimeRequest) -> ChatMainlineResult:
        text = (
            "`/pure` 是单轮纯净模式前缀：\n"
            "- `/pure 你的问题`：一级，保留 recent / 前门协议，去掉画像、长期记忆、self_mind 和大段 bootstrap。\n"
            "- `/pure2 你的问题`：二级，再去掉 role / dialogue 资产和 skills 扩展。\n"
            "- `/pure3 你的问题`：三级，再去掉 recent，只保留最小安全骨架与当前原始用户消息。"
        )
        bundle = OutputBundle(
            summary="prompt purity help",
            text_blocks=[TextBlock(text=text)],
            metadata={
                "route": runtime_request.decision.route,
                "runtime_owner": runtime_request.decision.runtime_owner,
                "prompt_purity_help": True,
            },
        )
        bundle = normalize_output_bundle_for_channel(bundle, runtime_request.channel_profile)
        delivery_plan = self._create_delivery_plan(runtime_request.delivery_session, bundle)
        return ChatMainlineResult(
            text=text,
            invocation=runtime_request.invocation,
            runtime_request=runtime_request,
            output_bundle=bundle,
            delivery_plan=delivery_plan,
            metadata={"route": runtime_request.decision.route, "prompt_purity_help": True},
        )

    def _ensure_orchestrator_online(self):
        bootstrap = self._orchestrator_bootstrap
        if bootstrap is None or not hasattr(bootstrap, "ensure_online"):
            return None
        return bootstrap.ensure_online()

    def _build_mission_runtime_request(self, runtime_request: ChatRuntimeRequest) -> RuntimeRequest:
        route = RouteProjection(
            route_key="mission_ingress",
            workflow_kind="mission",
            target_agent_id=runtime_request.agent_spec.agent_id if runtime_request.agent_spec is not None else "butler.mission_ingress",
            delivery_mode=runtime_request.decision.delivery_mode,
            reason=runtime_request.decision.reason,
            metadata=dict(runtime_request.decision.metadata or {}),
        )
        return RuntimeRequest(
            invocation=runtime_request.invocation,
            agent_spec=runtime_request.agent_spec,
            route=route,
            delivery_session=runtime_request.delivery_session,
            metadata=dict(runtime_request.invocation.metadata or {}),
        )

    def _create_delivery_plan(
        self,
        delivery_session,
        bundle: OutputBundle,
    ) -> FeishuDeliveryPlan | WeixinDeliveryPlan | None:
        if delivery_session is None:
            return None
        platform = str(delivery_session.platform or "").strip().lower()
        if platform == "feishu":
            return self._delivery_adapter.create(delivery_session, bundle)
        if platform in {"weixi", "weixin", "wechat"}:
            return self._weixin_delivery_adapter.create(delivery_session, bundle)
        return None

    @staticmethod
    def _text_from_bundle(bundle: OutputBundle, *, fallback: str = "") -> str:
        text_parts = [str(block.text or "").strip() for block in bundle.text_blocks if str(block.text or "").strip()]
        if text_parts:
            return "\n\n".join(text_parts)
        return str(fallback or bundle.summary or "").strip()

    @staticmethod
    def _frontdoor_execution_blocked(capability_result: object) -> bool:
        metadata = getattr(capability_result, "metadata", None)
        if not isinstance(metadata, dict):
            return False
        return bool(metadata.get("chat_execution_blocked"))

    def _result_for_orchestrator_unavailable(
        self,
        runtime_request: ChatRuntimeRequest,
        bootstrap: OrchestratorBootstrapResult,
    ) -> ChatMainlineResult:
        bundle = OutputBundle(
            summary="orchestrator offline: start required",
            text_blocks=[
                TextBlock(
                    text="\n".join(
                        [
                            "orchestrator is offline and chat failed to start it automatically.",
                            f"try: {bootstrap.command_hint}",
                            f"fallback: {bootstrap.fallback_command_hint}",
                        ]
                    )
                )
            ],
            metadata={
                "route": runtime_request.decision.route,
                "orchestrator_bootstrap_ok": False,
                "orchestrator_bootstrap_reason": bootstrap.reason,
            },
        )
        delivery_plan = self._create_delivery_plan(runtime_request.delivery_session, bundle)
        return ChatMainlineResult(
            text=self._text_from_bundle(bundle),
            invocation=runtime_request.invocation,
            runtime_request=runtime_request,
            output_bundle=bundle,
            delivery_plan=delivery_plan,
            metadata={
                "route": runtime_request.decision.route,
                "orchestrator_bootstrap_ok": False,
                "orchestrator_bootstrap_reason": bootstrap.reason,
            },
        )


__all__ = ["ChatMainlineResult", "ChatMainlineService"]
