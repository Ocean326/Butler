from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from agents_os.contracts import DeliverySession, Invocation, MemoryPolicy, PromptContext, PromptProfile
from agents_os.factory.agent_spec import AgentCapabilities, AgentProfile, AgentSpec
from .channel_profiles import ChannelProfile, resolve_channel_profile
from .feature_switches import chat_frontdoor_tasks_enabled
from .router_plan import RouterCompilePlan, resolve_router_compile_plan
from butler_main.chat.memory_policy import ButlerMemoryPolicyAdapter
from butler_main.chat.prompt_context import ButlerPromptContextAdapter
from butler_main.chat.prompt_profile import ButlerPromptProfileAdapter

_CHAT_ROUTE_ALIASES = {"chat", "talk"}
_MISSION_ROUTE_ALIASES = {"mission", "mission_ingress"}
_MISSION_TEXT_PREFIXES = (
    "/mission",
    "mission:",
    "放进编排",
    "创建编排任务",
    "新建编排任务",
    "查询编排任务",
    "查看编排任务",
    "暂停编排任务",
    "继续编排任务",
    "恢复编排任务",
    "取消编排任务",
    "补充编排反馈",
)
@dataclass(slots=True, frozen=True)
class RouteDecision:
    route: str
    runtime_owner: str
    reason: str
    delivery_mode: str = "reply"
    legacy_boundary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ChatRuntimeRequest:
    invocation: Invocation
    decision: RouteDecision
    compile_plan: RouterCompilePlan
    channel_profile: ChannelProfile
    prompt_profile: PromptProfile
    prompt_context: PromptContext
    memory_policy: MemoryPolicy
    agent_spec: AgentSpec | None = None
    delivery_session: DeliverySession | None = None


class ChatRouter:
    """Front-door router for Butler chat entrypoints."""

    def __init__(
        self,
        *,
        prompt_profile_adapter: ButlerPromptProfileAdapter | None = None,
        prompt_context_adapter: ButlerPromptContextAdapter | None = None,
        memory_policy_adapter: ButlerMemoryPolicyAdapter | None = None,
    ) -> None:
        self._prompt_profile_adapter = prompt_profile_adapter or ButlerPromptProfileAdapter()
        self._prompt_context_adapter = prompt_context_adapter or ButlerPromptContextAdapter(prompt_profile_adapter=self._prompt_profile_adapter)
        self._memory_policy_adapter = memory_policy_adapter or ButlerMemoryPolicyAdapter()

    def route(self, invocation: Invocation) -> RouteDecision:
        route = self._normalize_route(invocation.entrypoint, invocation.user_text, invocation.metadata)
        return self.make_route_decision(
            invocation,
            route,
            reason=f"route={route} from invocation entrypoint={invocation.entrypoint or 'chat'}",
        )

    def make_route_decision(
        self,
        invocation: Invocation,
        route: str,
        *,
        reason: str,
        metadata_extra: dict[str, Any] | None = None,
    ) -> RouteDecision:
        normalized_route = self._normalize_route(route, invocation.user_text, invocation.metadata)
        runtime_owner = "MissionOrchestrator" if normalized_route == "mission_ingress" else "AgentRuntime"
        delivery_mode = self._resolve_delivery_mode(invocation.metadata)
        metadata = {
            "channel": invocation.channel,
            "session_id": invocation.session_id,
            **dict(metadata_extra or {}),
        }
        return RouteDecision(
            route=normalized_route,
            runtime_owner=runtime_owner,
            reason=str(reason or "").strip(),
            delivery_mode=delivery_mode,
            legacy_boundary="",
            metadata=metadata,
        )

    def build_runtime_request(
        self,
        invocation: Invocation,
        *,
        decision: RouteDecision | None = None,
        mode_state: dict[str, Any] | None = None,
    ) -> ChatRuntimeRequest:
        route_decision = decision or self.route(invocation)
        compile_plan = self.resolve_compile_plan(invocation, mode_state=mode_state)
        enriched_invocation = self._attach_compile_plan_metadata(invocation, compile_plan)
        channel_profile = resolve_channel_profile(invocation.channel)
        prompt_profile = self._prompt_profile_adapter.build_profile(route_decision.route)
        prompt_context = self._prompt_context_adapter.build_context(
            enriched_invocation,
            entrypoint=route_decision.route,
            prompt_profile=prompt_profile,
            dynamic_metadata={
                "delivery_mode": route_decision.delivery_mode,
                "runtime_owner": route_decision.runtime_owner,
                "intent_id": compile_plan.intent_id,
                "role_id": compile_plan.role_id,
                "injection_tier": compile_plan.injection_tier,
            },
        )
        memory_policy = self._memory_policy_adapter.resolve_policy(
            route_decision.route,
            visibility_flags=[route_decision.runtime_owner.lower()],
        )
        return ChatRuntimeRequest(
            invocation=enriched_invocation,
            decision=route_decision,
            compile_plan=compile_plan,
            channel_profile=channel_profile,
            prompt_profile=prompt_profile,
            prompt_context=prompt_context,
            memory_policy=memory_policy,
            agent_spec=self.resolve_agent_spec(
                enriched_invocation,
                route_decision,
                compile_plan=compile_plan,
                prompt_profile=prompt_profile,
                memory_policy=memory_policy,
            ),
            delivery_session=self.build_delivery_session(enriched_invocation, route_decision),
        )

    def resolve_compile_plan(
        self,
        invocation: Invocation,
        *,
        mode_state: dict[str, Any] | None = None,
    ) -> RouterCompilePlan:
        metadata = dict(invocation.metadata or {})
        return resolve_router_compile_plan(
            invocation.user_text,
            mode_state=mode_state,
            explicit_main_mode=str(metadata.get("chat_main_mode") or "").strip(),
            explicit_project_phase=str(metadata.get("chat_project_phase") or "").strip(),
            explicit_override_source=str(metadata.get("router_explicit_override_source") or "").strip(),
            runtime_cli=str(metadata.get("runtime_cli") or "").strip(),
            runtime_model=str(metadata.get("runtime_model") or "").strip(),
            runtime_profile=str(metadata.get("runtime_profile") or "").strip(),
            runtime_extra_args=str(metadata.get("runtime_extra_args") or "").splitlines(),
            router_session_action=str(metadata.get("router_session_action") or "").strip(),
            router_session_confidence=str(metadata.get("router_session_confidence") or "").strip(),
            router_session_reason_flags=str(metadata.get("router_session_reason_flags") or "").strip(),
            chat_session_id=str(metadata.get("chat_session_id") or "").strip(),
            route=str(metadata.get("route") or "").strip(),
            frontdoor_action=str(metadata.get("frontdoor_action") or "").strip(),
            router_source=str(metadata.get("router_source") or "").strip(),
            router_reason=str(metadata.get("router_reason") or "").strip(),
            router_confidence=str(metadata.get("router_confidence") or "").strip(),
            request_intake_mode=str(metadata.get("request_intake_mode") or "").strip(),
            should_discuss_mode_first=str(metadata.get("should_discuss_mode_first") or "").strip() == "1",
            external_execution_risk=str(metadata.get("external_execution_risk") or "").strip() == "1",
        )

    def resolve_agent_spec(
        self,
        invocation: Invocation,
        decision: RouteDecision,
        *,
        compile_plan: RouterCompilePlan,
        prompt_profile: PromptProfile,
        memory_policy: MemoryPolicy,
    ) -> AgentSpec:
        runtime_key = "mission_orchestrator" if decision.route == "mission_ingress" else "agent_runtime"
        workflow_kinds = ("mission",) if decision.route == "mission_ingress" else ("chat",)
        profile = AgentProfile(
            profile_id=f"butler.{decision.route}",
            description=f"Butler route profile for {decision.route}",
            prompt_profile=prompt_profile,
            memory_policy=memory_policy,
            metadata={
                "channel": invocation.channel,
                "delivery_mode": decision.delivery_mode,
                "runtime_owner": decision.runtime_owner,
                "role_id": compile_plan.role_id,
                "intent_id": compile_plan.intent_id,
                "injection_tier": compile_plan.injection_tier,
            },
        )
        capabilities = AgentCapabilities(
            memory_mode="session" if memory_policy.session_read else "none",
            retrieval_enabled=bool(memory_policy.retrieval_scopes),
            delivery_target=invocation.channel or "generic",
            capability_ids=tuple(filter(None, [decision.route, decision.legacy_boundary])),
            supported_workflow_kinds=workflow_kinds,
            extras={
                "delivery_mode": decision.delivery_mode,
                "role_id": compile_plan.role_id,
                "injection_tier": compile_plan.injection_tier,
            },
        )
        return AgentSpec(
            agent_id=f"butler.{decision.route}",
            profile=profile,
            capabilities=capabilities,
            runtime_key=runtime_key,
            entrypoints=(decision.route,),
            labels=tuple(filter(None, [invocation.channel, decision.delivery_mode])),
            metadata={
                "legacy_boundary": decision.legacy_boundary or "",
                "runtime_owner": decision.runtime_owner,
                "session_id": invocation.session_id,
                "role_id": compile_plan.role_id,
                "intent_id": compile_plan.intent_id,
            },
        )

    def build_delivery_session(self, invocation: Invocation, decision: RouteDecision) -> DeliverySession:
        channel_profile = resolve_channel_profile(invocation.channel or "feishu")
        platform = channel_profile.channel
        if platform in {"weixi", "weixin", "wechat"}:
            target = str(invocation.metadata.get("weixin.receive_id") or invocation.actor_id).strip()
            target_type = str(invocation.metadata.get("weixin.receive_id_type") or "open_id").strip() or "open_id"
            thread_id = str(invocation.metadata.get("weixin.raw_session_ref") or invocation.session_id or "").strip()
            metadata = {
                "channel": platform,
                "route": decision.route,
                "weixin.chat_type": str(invocation.metadata.get("weixin.chat_type") or "").strip(),
                "weixin.conversation_key": str(invocation.metadata.get("weixin.conversation_key") or invocation.session_id or "").strip(),
                "weixin.message_id": str(invocation.source_event_id or invocation.metadata.get("weixin.message_id") or "").strip(),
                "weixin.raw_session_ref": thread_id,
            }
        else:
            target = str(invocation.metadata.get("feishu.receive_id") or invocation.actor_id).strip()
            target_type = str(invocation.metadata.get("feishu.receive_id_type") or "open_id").strip() or "open_id"
            thread_id = str(invocation.metadata.get("feishu.raw_session_ref") or invocation.session_id or "").strip()
            metadata = {
                "channel": platform,
                "route": decision.route,
                "feishu.message_id": str(invocation.source_event_id or invocation.metadata.get("feishu.message_id") or "").strip(),
                "feishu.raw_session_ref": thread_id,
            }
        if decision.legacy_boundary:
            metadata["legacy_boundary"] = decision.legacy_boundary
        return DeliverySession(
            platform=platform,
            mode=decision.delivery_mode,
            target=target,
            target_type=target_type,
            thread_id=thread_id,
            metadata={key: value for key, value in metadata.items() if str(value or "").strip()},
        )

    def _normalize_route(self, entrypoint: str, user_text: str, metadata: dict[str, Any]) -> str:
        if not chat_frontdoor_tasks_enabled():
            return "chat"
        normalized = str(entrypoint or "").strip().lower()
        if normalized in _MISSION_ROUTE_ALIASES:
            return "mission_ingress"
        route_hint = str(metadata.get("route_hint") or "").strip().lower()
        if route_hint in _MISSION_ROUTE_ALIASES:
            return "mission_ingress"
        if self._looks_like_mission_request(user_text, metadata):
            return "mission_ingress"
        if normalized in _CHAT_ROUTE_ALIASES:
            return "chat"
        if route_hint in _CHAT_ROUTE_ALIASES:
            return "chat"
        return "chat"

    def _looks_like_mission_request(self, user_text: str, metadata: dict[str, Any]) -> bool:
        text = str(user_text or "").strip()
        if not text and not metadata:
            return False
        for key in (
            "mission_operation",
            "mission_id",
            "action",
            "feedback",
            "mission_payload",
            "mission",
            "template_id",
        ):
            value = metadata.get(key)
            if isinstance(value, dict) and value:
                return True
            if str(value or "").strip():
                return True
        lowered = text.lower()
        return any(lowered.startswith(prefix.lower()) for prefix in _MISSION_TEXT_PREFIXES)

    def _resolve_delivery_mode(self, metadata: dict[str, Any]) -> str:
        mode = str(
            metadata.get("delivery_mode")
            or metadata.get("feishu.delivery_mode")
            or metadata.get("weixin.delivery_mode")
            or "reply"
        ).strip().lower()
        if mode in {"reply", "update", "push"}:
            return mode
        return "reply"

    def _attach_compile_plan_metadata(
        self,
        invocation: Invocation,
        compile_plan: RouterCompilePlan,
    ) -> Invocation:
        metadata = {
            **dict(invocation.metadata or {}),
            **compile_plan.to_metadata(),
        }
        return replace(invocation, metadata=metadata)

__all__ = ["ChatRouter", "ChatRuntimeRequest", "RouteDecision"]
