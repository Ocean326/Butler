from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from agents_os.contracts import DocLink, OutputBundle, TextBlock
from butler_main.orchestrator.interfaces.query_service import OrchestratorQueryService
from .negotiation import CampaignNegotiationStore
from .providers.butler_prompt_support_provider import ButlerChatPromptSupportProvider


_STATUS_QUERY_KEYWORDS = (
    "任务进度",
    "任务进展",
    "后台任务进度",
    "后台任务进展",
    "campaign progress",
    "campaign status",
    "progress",
    "status",
    "进度",
    "进展",
    "状态",
    "做到哪",
    "到哪了",
    "怎么样了",
)
_CAMPAIGN_ID_RE = re.compile(r"\b(campaign_[A-Za-z0-9]+)\b")


@dataclass(slots=True, frozen=True)
class FrontDoorCollaborationResolution:
    action: str
    target_kind: str = ""
    target_id: str = ""
    source: str = ""
    blocked: bool = False
    session_context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class FrontDoorCapabilityResult:
    handled: bool
    resolution: FrontDoorCollaborationResolution
    output_bundle: OutputBundle | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class FrontDoorTaskQueryService:
    def __init__(
        self,
        *,
        store: CampaignNegotiationStore | None = None,
        query_service: OrchestratorQueryService | None = None,
        prompt_support_provider: ButlerChatPromptSupportProvider | None = None,
    ) -> None:
        self._store = store or CampaignNegotiationStore()
        self._query_service = query_service or OrchestratorQueryService()
        self._prompt_support = prompt_support_provider or ButlerChatPromptSupportProvider()

    def handle(
        self,
        *,
        workspace: str,
        session_id: str,
        user_text: str,
        force_status: bool = False,
    ) -> FrontDoorCapabilityResult | None:
        if not force_status and not self._looks_like_status_query(user_text):
            return None
        campaign_id, source = self._resolve_campaign_id(workspace=workspace, session_id=session_id, user_text=user_text)
        if not campaign_id:
            resolution = FrontDoorCollaborationResolution(
                action="query_status",
                source="no_session_target",
                blocked=True,
                session_context={"session_id": session_id},
            )
            text = "我这边还没定位到当前会话关联的后台任务；如果你要查特定任务，给我 `campaign_id` 或明确是哪一个任务。"
            bundle = OutputBundle(
                summary="task query target unresolved",
                text_blocks=[TextBlock(text=text)],
                metadata={
                    "frontdoor_action": "query_status",
                    "frontdoor_blocked": True,
                    "frontdoor_resolution_source": resolution.source,
                    "task_query_hit": True,
                    "task_query_kind": "",
                    "task_query_status": "unresolved",
                },
            )
            return FrontDoorCapabilityResult(
                handled=True,
                resolution=resolution,
                output_bundle=bundle,
                metadata={
                    "frontdoor_action": "query_status",
                    "frontdoor_target_kind": "",
                    "frontdoor_target_id": "",
                    "frontdoor_blocked": True,
                    "frontdoor_resolution_source": resolution.source,
                    "task_query_hit": True,
                    "task_query_kind": "",
                    "task_query_status": "unresolved",
                    "model_reply_prompt": self._build_unresolved_model_prompt(),
                },
            )

        try:
            payload = self._query_service.get_campaign_status(workspace, campaign_id)
        except Exception as exc:
            resolution = FrontDoorCollaborationResolution(
                action="query_status",
                target_kind="campaign",
                target_id=campaign_id,
                source=source,
                blocked=True,
                session_context={"session_id": session_id},
            )
            text = (
                "我这边没找到这个 campaign_id 对应的后台任务。"
                "请确认是否拼写正确，或者告诉我是哪个正在运行的任务。"
            )
            bundle = OutputBundle(
                summary=f"task query not found: {campaign_id}",
                text_blocks=[TextBlock(text=text)],
                metadata={
                    "frontdoor_action": "query_status",
                    "frontdoor_target_kind": "campaign",
                    "frontdoor_target_id": campaign_id,
                    "frontdoor_blocked": True,
                    "frontdoor_resolution_source": source,
                    "task_query_hit": True,
                    "task_query_kind": "campaign",
                    "task_query_status": "not_found",
                    "campaign_id": campaign_id,
                    "error_type": type(exc).__name__,
                },
            )
            return FrontDoorCapabilityResult(
                handled=True,
                resolution=resolution,
                output_bundle=bundle,
                metadata={
                    **(bundle.metadata or {}),
                    "model_reply_prompt": self._build_missing_campaign_prompt(campaign_id),
                },
            )
        campaign_view = dict(payload.get("campaign_view") or {})
        session_view = dict(payload.get("session_view") or {})
        session_plane = dict(payload.get("session_plane") or {})
        session_evidence = dict(payload.get("session_evidence") or {})
        user_feedback = dict(payload.get("user_feedback") or {})
        feedback_doc = dict(payload.get("feedback_doc") or (payload.get("metadata") or {}).get("feedback_doc") or {})
        doc_url = str(feedback_doc.get("url") or "").strip()
        doc_title = str(feedback_doc.get("title") or "").strip() or "Task Doc"

        status = str(campaign_view.get("status") or payload.get("status") or "").strip() or "unknown"
        current_phase = str(campaign_view.get("current_phase") or payload.get("current_phase") or "").strip() or "-"
        next_phase = str(campaign_view.get("next_phase") or payload.get("next_phase") or "").strip() or "-"
        current_iteration = int(campaign_view.get("current_iteration") or payload.get("current_iteration") or 0)
        artifact_count = int(campaign_view.get("artifact_count") or session_evidence.get("artifact_count") or len(payload.get("artifacts") or []))
        session_event_count = int(session_evidence.get("session_event_count") or session_plane.get("session_event_count") or 0)
        handoff_count = int(session_plane.get("handoff_count") or 0)
        mailbox_count = int(session_plane.get("mailbox_count") or 0)
        user_feedback_count = int(user_feedback.get("count") or 0)
        workflow_session_id = str(session_view.get("workflow_session_id") or session_evidence.get("workflow_session_id") or "").strip()
        workflow_status = str(session_view.get("status") or (payload.get("workflow_session") or {}).get("status") or "").strip() or "-"
        active_step = str(session_view.get("active_step") or session_evidence.get("active_step") or "").strip() or "-"
        task_summary = dict(payload.get("task_summary") or {})
        next_action = str(task_summary.get("next_action") or "-").strip() or "-"
        risk_summary = dict(task_summary.get("risk") or {})
        risk_level = str(risk_summary.get("risk_level") or "-").strip() or "-"
        mode_id = str(task_summary.get("mode_id") or "-").strip() or "-"
        runtime_mode = str(payload.get("runtime_mode") or "-").strip() or "-"
        bundle_root = str(payload.get("bundle_root") or "").strip()
        pending_checks = [str(item).strip() for item in payload.get("pending_checks") or [] if str(item).strip()]
        resolved_checks = [str(item).strip() for item in payload.get("resolved_checks") or [] if str(item).strip()]
        waived_checks = [str(item).strip() for item in payload.get("waived_checks") or [] if str(item).strip()]
        operational_checks = [str(item).strip() for item in payload.get("operational_checks_pending") or [] if str(item).strip()]
        closure_checks = [str(item).strip() for item in payload.get("closure_checks_pending") or [] if str(item).strip()]
        execution_state = str(payload.get("execution_state") or "-").strip() or "-"
        closure_state = str(payload.get("closure_state") or "-").strip() or "-"
        progress_reason = str(payload.get("progress_reason") or "").strip()
        closure_reason = str(payload.get("closure_reason") or "").strip()
        latest_stage_summary = str(payload.get("latest_stage_summary") or "").strip()
        stage_artifact_refs = [str(item).strip() for item in payload.get("stage_artifact_refs") or [] if str(item).strip()]
        latest_acceptance_decision = str(payload.get("latest_acceptance_decision") or "-").strip() or "-"
        not_done_reason = str(payload.get("not_done_reason") or "").strip()

        resolution = FrontDoorCollaborationResolution(
            action="query_status",
            target_kind="campaign",
            target_id=campaign_id,
            source=source,
            session_context={"session_id": session_id, "workflow_session_id": workflow_session_id},
        )
        text_lines = [
            "campaign progress",
            f"campaign_id: {campaign_id}",
            f"status: {status}",
            f"current_phase: {current_phase}",
            f"next_phase: {next_phase}",
            f"current_iteration: {current_iteration}",
            f"workflow_session_status: {workflow_status}",
            f"active_step: {active_step}",
            f"mode_id: {mode_id}",
            f"runtime_mode: {runtime_mode}",
            f"execution_state: {execution_state}",
            f"closure_state: {closure_state}",
            f"next_action: {next_action}",
            f"risk_level: {risk_level}",
            f"latest_acceptance_decision: {latest_acceptance_decision}",
            f"artifacts: {artifact_count}",
            f"session_events: {session_event_count}",
            f"handoffs: {handoff_count}",
            f"mailbox_messages: {mailbox_count}",
            f"user_feedback_count: {user_feedback_count}",
        ]
        if latest_stage_summary:
            text_lines.append(f"latest_stage_summary: {latest_stage_summary}")
        if progress_reason:
            text_lines.append(f"progress_reason: {progress_reason}")
        if closure_reason:
            text_lines.append(f"closure_reason: {closure_reason}")
        if bundle_root:
            text_lines.append(f"bundle_root: {bundle_root}")
        if pending_checks:
            text_lines.append("pending_checks: " + ", ".join(pending_checks))
        if operational_checks:
            text_lines.append("operational_checks_pending: " + ", ".join(operational_checks))
        if closure_checks:
            text_lines.append("closure_checks_pending: " + ", ".join(closure_checks))
        if resolved_checks:
            text_lines.append("resolved_checks: " + ", ".join(resolved_checks))
        if waived_checks:
            text_lines.append("waived_checks: " + ", ".join(waived_checks))
        if stage_artifact_refs:
            text_lines.append("stage_artifact_refs: " + ", ".join(stage_artifact_refs[:6]))
        if not_done_reason:
            text_lines.append(f"not_done_reason: {not_done_reason}")
        if doc_url:
            text_lines.append(f"task_doc: {doc_url}")
        bundle = OutputBundle(
            summary=f"campaign progress: {campaign_id}",
            text_blocks=[TextBlock(text="\n".join(text_lines))],
            doc_links=[DocLink(url=doc_url, title=doc_title, metadata={"campaign_id": campaign_id})] if doc_url else [],
            metadata={
                "frontdoor_action": "query_status",
                "frontdoor_target_kind": "campaign",
                "frontdoor_target_id": campaign_id,
                "frontdoor_blocked": False,
                "frontdoor_resolution_source": source,
                "task_query_hit": True,
                "task_query_kind": "campaign",
                "task_query_status": status,
                "campaign_id": campaign_id,
                "workflow_session_id": workflow_session_id,
                "current_phase": current_phase,
                "next_phase": next_phase,
                "current_iteration": current_iteration,
                "mode_id": mode_id,
                "runtime_mode": runtime_mode,
                "execution_state": execution_state,
                "closure_state": closure_state,
                "progress_reason": progress_reason,
                "closure_reason": closure_reason,
                "latest_stage_summary": latest_stage_summary,
                "next_action": next_action,
                "risk_level": risk_level,
                "bundle_root": bundle_root,
                "pending_checks": pending_checks,
                "operational_checks_pending": operational_checks,
                "closure_checks_pending": closure_checks,
                "resolved_checks": resolved_checks,
                "waived_checks": waived_checks,
                "stage_artifact_refs": stage_artifact_refs,
                "latest_acceptance_decision": latest_acceptance_decision,
                "not_done_reason": not_done_reason,
                "artifact_count": artifact_count,
                "session_event_count": session_event_count,
                "handoff_count": handoff_count,
                "mailbox_count": mailbox_count,
                "user_feedback_count": user_feedback_count,
                "feedback_doc": feedback_doc,
                "task_summary": task_summary,
            },
        )
        return FrontDoorCapabilityResult(
            handled=True,
            resolution=resolution,
            output_bundle=bundle,
            metadata={
                **dict(bundle.metadata or {}),
                "collaboration_snapshot": {
                    "campaign_view": campaign_view,
                    "session_view": session_view,
                    "session_plane": session_plane,
                    "session_evidence": session_evidence,
                },
                "model_reply_prompt": self._build_status_model_prompt(
                    campaign_id=campaign_id,
                    source=source,
                    status=status,
                    current_phase=current_phase,
                    next_phase=next_phase,
                    current_iteration=current_iteration,
                    workflow_status=workflow_status,
                    active_step=active_step,
                    artifact_count=artifact_count,
                    session_event_count=session_event_count,
                    handoff_count=handoff_count,
                    mailbox_count=mailbox_count,
                    user_feedback_count=user_feedback_count,
                    runtime_mode=runtime_mode,
                    bundle_root=bundle_root,
                    latest_acceptance_decision=latest_acceptance_decision,
                    not_done_reason=not_done_reason,
                    doc_url=doc_url,
                ),
            },
        )

    @staticmethod
    def _looks_like_status_query(user_text: str) -> bool:
        lowered = str(user_text or "").strip().lower()
        if not lowered:
            return False
        return any(keyword in lowered for keyword in _STATUS_QUERY_KEYWORDS)

    def _resolve_campaign_id(self, *, workspace: str, session_id: str, user_text: str) -> tuple[str, str]:
        matched = _CAMPAIGN_ID_RE.search(str(user_text or ""))
        if matched:
            return str(matched.group(1) or "").strip(), "explicit_campaign_id"
        draft = self._store.load(workspace=workspace, session_id=session_id)
        if draft is not None and str(draft.started_campaign_id or "").strip():
            return str(draft.started_campaign_id or "").strip(), "session_started_campaign"
        return "", "no_session_target"

    def _build_unresolved_model_prompt(self) -> str:
        blocks = [
            self._prompt_support.render_protocol_block("frontdoor_collaboration", heading="前门协作协议").strip(),
            self._prompt_support.render_protocol_block("status_query_collaboration", heading="状态查询协作协议").strip(),
            "你现在处于 Butler 的前门协作查询态。",
            "这轮用户是在问任务进展，但当前会话没有定位到关联后台任务。",
            "请直接用自然中文说明：你还没定位到当前会话关联的后台任务；如果用户要查某个后台任务，请补充 campaign_id 或明确是哪一个任务。",
            "不要输出字段名、JSON、回执样式，也不要假装已经查到了后台状态。",
        ]
        return "\n\n".join(item for item in blocks if item)

    def _build_missing_campaign_prompt(self, campaign_id: str) -> str:
        blocks = [
            self._prompt_support.render_protocol_block("frontdoor_collaboration", heading="前门协作协议").strip(),
            self._prompt_support.render_protocol_block("status_query_collaboration", heading="状态查询协作协议").strip(),
            "你现在处于 Butler 的前门协作查询态。",
            f"campaign_id={campaign_id}",
            "系统没有找到该 campaign_id 对应的后台任务。",
            "请用自然中文说明：未找到该任务，请确认 campaign_id 是否正确，或说明要查的任务是哪一个。",
            "不要输出字段名、JSON、回执样式，也不要假装查到了后台状态。",
        ]
        return "\n\n".join(item for item in blocks if item)

    def _build_status_model_prompt(
        self,
        *,
        campaign_id: str,
        source: str,
        status: str,
        current_phase: str,
        next_phase: str,
        current_iteration: int,
        workflow_status: str,
        active_step: str,
        artifact_count: int,
        session_event_count: int,
        handoff_count: int,
        mailbox_count: int,
        user_feedback_count: int,
        runtime_mode: str,
        bundle_root: str,
        latest_acceptance_decision: str,
        not_done_reason: str,
        doc_url: str,
    ) -> str:
        blocks = [
            self._prompt_support.render_protocol_block("frontdoor_collaboration", heading="前门协作协议").strip(),
            self._prompt_support.render_protocol_block("status_query_collaboration", heading="状态查询协作协议").strip(),
            "你现在处于 Butler 的前门协作查询态。",
            "下面这些信息来自 ObservationPort / QueryService 的真实状态，不要补造没看到的执行事实。",
            f"target_kind=campaign",
            f"campaign_id={campaign_id}",
            f"resolution_source={source}",
            f"status={status}",
            f"current_phase={current_phase}",
            f"next_phase={next_phase}",
            f"current_iteration={current_iteration}",
            f"workflow_session_status={workflow_status}",
            f"active_step={active_step}",
            f"artifact_count={artifact_count}",
            f"session_event_count={session_event_count}",
            f"handoff_count={handoff_count}",
            f"mailbox_count={mailbox_count}",
            f"user_feedback_count={user_feedback_count}",
            f"runtime_mode={runtime_mode}",
            (f"bundle_root={bundle_root}" if bundle_root else ""),
            f"latest_acceptance_decision={latest_acceptance_decision}",
            (f"not_done_reason={not_done_reason}" if not_done_reason else ""),
            (f"task_doc={doc_url}" if doc_url else ""),
            "请直接面向用户输出自然中文：先说当前进展，再补一两条最有信息量的协作证据；不要输出字段名、JSON、模板 id 或回执格式。",
        ]
        return "\n\n".join(item for item in blocks if item)


__all__ = [
    "FrontDoorCapabilityResult",
    "FrontDoorCollaborationResolution",
    "FrontDoorTaskQueryService",
]
