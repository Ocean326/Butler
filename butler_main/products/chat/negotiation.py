from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import re
from pathlib import Path
from typing import Any, Mapping

from agents_os.contracts import DeliverySession, DocLink, OutputBundle, TextBlock
from butler_main.domains.campaign.template_registry import CampaignTemplateRegistry
from .orchestrator_bootstrap import OrchestratorBootstrapResult
from butler_main.orchestrator import OrchestratorCampaignService
from butler_main.orchestrator.interfaces.query_service import OrchestratorQueryService
from .providers.butler_prompt_support_provider import ButlerChatPromptSupportProvider
from butler_main.orchestrator.workspace import resolve_orchestrator_root


_CAMPAIGN_KEYWORDS = (
    "campaign",
    "长期",
    "持续",
    "迭代",
    "多阶段",
    "跟进",
    "推进",
    "复盘",
    "review",
    "监督",
    "自治",
    "大任务",
    "后台任务",
    "复杂后台",
    "布置任务",
)
_EXPLICIT_BACKEND_HINTS = (
    "后台任务",
    "后台",
    "异步",
    "campaign",
    "编排",
    "后台分支",
    "后台入口",
    "布置任务",
    "持续推进这个项目",
    "长期推进这个项目",
    "持续推进这个任务",
)
_RESEARCH_DELIVERY_KEYWORDS = (
    "ssh",
    "服务器",
    "目录",
    "研究主题",
    "文献",
    "论文",
    "kdd",
    "transfer_recovery",
    "transferrecovery",
    "阅读摘要",
    "参考文献库",
    "分类矩阵",
)
_DISCUSSION_FIRST_KEYWORDS = (
    "ssh",
    "服务器",
    "研究主题",
    "文献",
    "论文",
    "kdd",
    "不少于",
    "分类矩阵",
    "阅读摘要",
    "参考文献库",
)
_BACKGROUND_TASK_ACTION_KEYWORDS = (
    "整理",
    "梳理",
    "系统梳理",
    "撰写",
    "写一版",
    "写论文",
    "调研",
    "检索",
    "综述",
    "收集",
    "构建",
    "形成",
)
_BACKGROUND_TASK_SCOPE_KEYWORDS = (
    "不少于",
    "至少",
    "100篇",
    "一百篇",
    "分类矩阵",
    "阅读摘要",
    "参考文献库",
    "研究背景",
    "现状",
)
_DIRECT_EXECUTION_HINTS = (
    "请执行命令",
    "执行命令",
    "运行命令",
    "只回复输出",
    "只告诉我结果",
)
_SKELETON_CHANGE_KEYWORDS = (
    "改阶段",
    "阶段改成",
    "调整阶段",
    "阶段顺序",
    "新增阶段",
    "删除阶段",
    "改角色",
    "新增角色",
    "删除角色",
    "role",
    "phase",
)
_COMPOSITION_KEYWORDS = (
    "组合",
    "合成",
    "混合",
    "编排",
    "自定义",
    "composition",
    "compose",
)
_BACKEND_NEGATION_PATTERNS = (
    r"不要放后台",
    r"别放后台",
    r"不用后台",
    r"不要走后台",
    r"别走后台",
    r"不用走后台",
)
_DEFER_START_PATTERNS = (
    r"先别启动",
    r"暂时别启动",
    r"先不要启动",
    r"暂不启动",
    r"不要启动",
)
_STARTED_FEEDBACK_HINTS = (
    "补充",
    "反馈",
    "还有",
    "另外",
    "顺便",
    "顺手",
    "附加",
    "加上",
    "再加",
    "限制",
    "约束",
    "范围",
    "优先",
    "截止",
    "期限",
    "也需要",
    "英文",
    "中文",
    "风险",
    "风险点",
    "继续",
    "接着",
    "顺着",
    "吸收",
    "并进",
)
_NEGOTIATION_RESTART_HINTS = (
    "新任务",
    "全新任务",
    "重新开始",
    "从头开始",
    "换个任务",
    "另一个任务",
    "切换话题",
    "new task",
    "start over",
    "new topic",
    "reset context",
)
_CONFIRM_KEYWORDS = ("确认", "同意", "ok", "okay", "好的", "yes")
_START_INTENT_VERBS = ("启动", "开始", "开跑", "进后台", "放后台")
_TEMPLATE_HINT_PATTERN = re.compile(r"(?:template|模板)[:：\s]*([A-Za-z0-9._-]+)", re.IGNORECASE)
_MINIMAL_CHECK_LABELS = {
    "ssh_reachable": "SSH / 服务器可达",
    "target_path_exists": "目标目录或材料入口存在",
    "research_anchor_confirmed": "研究主题锚点明确",
    "literature_scope_confirmed": "文献筛选边界明确",
    "output_contract_confirmed": "产出语言 / 格式合同明确",
}


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _safe_id(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "session"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw)[:120] or "session"


@dataclass(slots=True, frozen=True)
class CampaignTemplate:
    template_id: str
    display_name: str
    summary: str
    keywords: tuple[str, ...]
    phases: tuple[str, ...]
    roles: tuple[str, ...]


@dataclass(slots=True)
class CampaignCompositionPlan:
    base_template_id: str
    phase_plan: list[str] = field(default_factory=list)
    role_plan: list[str] = field(default_factory=list)
    governance_plan: dict[str, Any] = field(default_factory=dict)
    diff_summary: list[str] = field(default_factory=list)
    skeleton_changed: bool = False
    composition_mode: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_template_id": self.base_template_id,
            "phase_plan": list(self.phase_plan),
            "role_plan": list(self.role_plan),
            "governance_plan": dict(self.governance_plan or {}),
            "diff_summary": list(self.diff_summary),
            "skeleton_changed": bool(self.skeleton_changed),
            "composition_mode": str(self.composition_mode or "").strip() or "template",
        }


@dataclass(slots=True)
class CampaignNegotiationDraft:
    draft_id: str
    session_id: str
    status: str = "collecting"
    goal: str = ""
    materials: list[str] = field(default_factory=list)
    hard_constraints: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    iteration_budget: dict[str, Any] = field(default_factory=dict)
    recommended_template_id: str = ""
    selected_template_id: str = ""
    skill_selection: dict[str, Any] = field(default_factory=dict)
    composition_plan: dict[str, Any] = field(default_factory=dict)
    skeleton_changed: bool = False
    composition_mode: str = ""
    pending_confirmation: bool = False
    started_campaign_id: str = ""
    confidence: float = 0.0
    start_reason: str = ""
    task_mode: str = ""
    background_reason: str = ""
    startup_mode: str = ""
    frontdoor_mode_id: str = ""
    minimal_correctness_checks: list[str] = field(default_factory=list)
    confirmed_correctness_checks: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "CampaignNegotiationDraft":
        if not isinstance(payload, Mapping):
            return cls(draft_id=_safe_id("draft"), session_id="session")
        return cls(**dict(payload))

    def touch(self) -> None:
        self.updated_at = _utc_now_iso()


@dataclass(slots=True, frozen=True)
class CampaignNegotiationResult:
    handled: bool
    output_bundle: OutputBundle | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CampaignNegotiationStore:
    def __init__(self) -> None:
        self._cache: dict[str, CampaignNegotiationDraft] = {}

    def load(self, *, workspace: str, session_id: str) -> CampaignNegotiationDraft | None:
        key = self._cache_key(workspace, session_id)
        if key in self._cache:
            return self._cache[key]
        path = self._path_for(workspace, session_id)
        if not path.exists():
            return None
        try:
            payload = path.read_text(encoding="utf-8")
        except Exception:
            return None
        try:
            import json

            data = json.loads(payload)
        except Exception:
            return None
        draft = CampaignNegotiationDraft.from_dict(data)
        self._cache[key] = draft
        return draft

    def save(self, *, workspace: str, draft: CampaignNegotiationDraft) -> None:
        import json

        path = self._path_for(workspace, draft.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(draft.to_dict(), ensure_ascii=False, indent=2)
        path.write_text(payload, encoding="utf-8")
        self._cache[self._cache_key(workspace, draft.session_id)] = draft

    @staticmethod
    def _cache_key(workspace: str, session_id: str) -> str:
        return f"{workspace}:{session_id}"

    @staticmethod
    def _path_for(workspace: str, session_id: str) -> Path:
        root = Path(resolve_orchestrator_root(workspace)) / "negotiations" / "campaign"
        return root / f"{_safe_id(session_id)}.json"


class CampaignTemplateLibrary:
    def __init__(self) -> None:
        self._registry = CampaignTemplateRegistry()
        self._templates = [
            CampaignTemplate(
                template_id=item.template_id,
                display_name=item.display_name,
                summary=item.summary,
                keywords=item.keywords,
                phases=item.default_phase_ids,
                roles=item.default_role_ids,
            )
            for item in self._registry.list_templates()
        ]

    def templates(self) -> tuple[CampaignTemplate, ...]:
        return tuple(self._templates)

    def recommend(self, text: str) -> tuple[CampaignTemplate, float, str]:
        normalized = str(text or "").strip().lower()
        best = self._templates[0]
        best_score = 0.0
        reason = "default_template"
        for template in self._templates:
            score = 0.0
            for keyword in template.keywords:
                if keyword and keyword.lower() in normalized:
                    score += 0.2
            if template.template_id in normalized:
                score += 0.4
            if template.display_name.lower() in normalized:
                score += 0.3
            if score > best_score:
                best = template
                best_score = score
                reason = f"matched:{template.template_id}"
        return best, min(0.95, max(0.55, best_score + 0.4)), reason

    def get(self, template_id: str) -> CampaignTemplate | None:
        for template in self._templates:
            if template.template_id == template_id:
                return template
        return None


class CampaignNegotiationService:
    def __init__(
        self,
        *,
        store: CampaignNegotiationStore | None = None,
        template_library: CampaignTemplateLibrary | None = None,
        campaign_service: OrchestratorCampaignService | None = None,
        query_service: OrchestratorQueryService | None = None,
        prompt_support_provider: ButlerChatPromptSupportProvider | None = None,
        orchestrator_bootstrap=None,
    ) -> None:
        self._store = store or CampaignNegotiationStore()
        self._library = template_library or CampaignTemplateLibrary()
        self._campaign_service = campaign_service or OrchestratorCampaignService()
        self._query_service = query_service or OrchestratorQueryService(campaign_service=self._campaign_service)
        self._prompt_support = prompt_support_provider or ButlerChatPromptSupportProvider()
        self._orchestrator_bootstrap = orchestrator_bootstrap

    def handle(
        self,
        *,
        workspace: str,
        session_id: str,
        user_text: str,
        delivery_session: DeliverySession | None = None,
        force_open: bool = False,
        intake_decision: Mapping[str, Any] | None = None,
        explicit_mode: str = "",
    ) -> CampaignNegotiationResult | None:
        intake_map = dict(intake_decision or {})
        draft = self._store.load(workspace=workspace, session_id=session_id)
        if draft is None and not (force_open or self._should_open_negotiation(user_text)):
            return None
        if draft is not None and draft.started_campaign_id:
            if self._is_confirmation(user_text):
                draft.status = "started"
                draft.touch()
                self._store.save(workspace=workspace, draft=draft)
                return self._result_for_started(draft, workspace=workspace)
            if self._allows_frontdoor_escape(user_text):
                return None
            if self._should_restart_started_campaign_negotiation(user_text):
                draft = CampaignNegotiationDraft(
                    draft_id=_safe_id(f"draft_{session_id}"),
                    session_id=session_id,
                )
            elif not self._should_append_feedback_to_started_campaign(user_text, intake_decision=intake_map):
                return None
            else:
                feedback_result = self._append_feedback_to_started_campaign(
                    workspace=workspace,
                    draft=draft,
                    feedback=user_text,
                )
                if feedback_result is not None:
                    draft.touch()
                    self._store.save(workspace=workspace, draft=draft)
                    return feedback_result
                return None
        if draft is None:
            draft = CampaignNegotiationDraft(
                draft_id=_safe_id(f"draft_{session_id}"),
                session_id=session_id,
            )
        draft = self._update_draft(draft, user_text)
        explicit_mode_id = str(explicit_mode or "").strip().lower()
        if explicit_mode_id in {"plan", "delivery", "research"}:
            draft.frontdoor_mode_id = explicit_mode_id
        if force_open:
            draft.task_mode = "background_entry"
            if not draft.background_reason:
                draft.background_reason = self._infer_background_reason(user_text)
        if bool(intake_map.get("external_execution_risk")):
            draft.task_mode = "background_entry"
            if "ssh_reachable" not in draft.minimal_correctness_checks:
                draft.minimal_correctness_checks.append("ssh_reachable")
        if bool(intake_map.get("should_discuss_mode_first")) and not draft.background_reason:
            draft.background_reason = "request_intake_discussion_first"
        if explicit_mode_id == "delivery":
            draft.task_mode = "campaign"
            draft.selected_template_id = "campaign.single_repo_delivery"
        elif explicit_mode_id == "research":
            draft.task_mode = "campaign"
            draft.background_reason = draft.background_reason or "slash_mode_research"
            draft.selected_template_id = "campaign.research_then_implement"
        template_hint = self._extract_template_hint(user_text)
        if template_hint:
            matched = self._library.get(template_hint)
            if matched is not None:
                draft.selected_template_id = matched.template_id
        template, confidence, reason = self._library.recommend(f"{draft.goal} {user_text}")
        if self._looks_like_campaign(user_text):
            confidence = max(confidence, 0.8)
        if not draft.recommended_template_id:
            draft.recommended_template_id = template.template_id
        if not draft.selected_template_id:
            draft.selected_template_id = draft.recommended_template_id
        draft.confidence = max(float(draft.confidence or 0.0), confidence)
        draft.start_reason = reason
        draft.skeleton_changed = draft.skeleton_changed or self._detect_skeleton_change(user_text)
        draft.composition_mode = self._resolve_composition_mode(draft, user_text)
        chosen_template = self._resolve_template(draft, template)
        draft.composition_plan = self._build_composition_plan(draft, chosen_template).to_dict()
        if explicit_mode_id == "plan":
            draft.status = "planned"
            draft.pending_confirmation = False
            draft.touch()
            self._store.save(workspace=workspace, draft=draft)
            return self._result_for_plan(draft, workspace=workspace)
        launch_requested = self._should_launch_from_followup(draft, user_text)

        if self._explicitly_defers_start(user_text):
            draft.status = "collecting"
            draft.pending_confirmation = False
            draft.touch()
            self._store.save(workspace=workspace, draft=draft)
            return self._result_for_clarify(draft)

        if draft.skeleton_changed:
            if launch_requested and self._minimal_correctness_ready(draft):
                draft.startup_mode = "confirmed"
                bootstrap = self._ensure_orchestrator_online()
                if bootstrap is not None and not bootstrap.ok:
                    draft.status = "blocked_orchestrator_offline"
                    draft.pending_confirmation = True
                    draft.touch()
                    self._store.save(workspace=workspace, draft=draft)
                    return self._result_for_orchestrator_unavailable(draft, bootstrap)
                campaign_payload = self._start_campaign(workspace, draft, delivery_session=delivery_session)
                draft.started_campaign_id = str(campaign_payload.get("campaign_id") or "").strip()
                draft.status = "started"
                draft.pending_confirmation = False
                draft.touch()
                self._store.save(workspace=workspace, draft=draft)
                return self._result_for_started(draft, workspace=workspace, campaign_payload=campaign_payload)
            draft.status = "confirmation_required"
            draft.pending_confirmation = True
            draft.touch()
            self._store.save(workspace=workspace, draft=draft)
            return self._result_for_confirmation(draft)

        if self._requires_discussion_before_start(draft):
            if not self._minimal_correctness_ready(draft):
                if launch_requested:
                    draft.startup_mode = "exploratory"
                    bootstrap = self._ensure_orchestrator_online()
                    if bootstrap is not None and not bootstrap.ok:
                        draft.status = "blocked_orchestrator_offline"
                        draft.pending_confirmation = False
                        draft.touch()
                        self._store.save(workspace=workspace, draft=draft)
                        return self._result_for_orchestrator_unavailable(draft, bootstrap)
                    campaign_payload = self._start_campaign(workspace, draft, delivery_session=delivery_session)
                    draft.started_campaign_id = str(campaign_payload.get("campaign_id") or "").strip()
                    draft.status = "started"
                    draft.pending_confirmation = False
                    draft.touch()
                    self._store.save(workspace=workspace, draft=draft)
                    return self._result_for_started(draft, workspace=workspace, campaign_payload=campaign_payload)
                draft.status = "backend_entry_required"
                draft.pending_confirmation = True
                draft.touch()
                self._store.save(workspace=workspace, draft=draft)
                return self._result_for_backend_entry(draft)
            if not launch_requested:
                draft.status = "backend_entry_required"
                draft.pending_confirmation = True
                draft.touch()
                self._store.save(workspace=workspace, draft=draft)
                return self._result_for_backend_entry(draft)
 
        if self._ready_to_start(draft):
            if not draft.startup_mode:
                draft.startup_mode = "confirmed"
            bootstrap = self._ensure_orchestrator_online()
            if bootstrap is not None and not bootstrap.ok:
                draft.status = "blocked_orchestrator_offline"
                draft.pending_confirmation = False
                draft.touch()
                self._store.save(workspace=workspace, draft=draft)
                return self._result_for_orchestrator_unavailable(draft, bootstrap)
            campaign_payload = self._start_campaign(workspace, draft, delivery_session=delivery_session)
            draft.started_campaign_id = str(campaign_payload.get("campaign_id") or "").strip()
            draft.status = "started"
            draft.pending_confirmation = False
            draft.touch()
            self._store.save(workspace=workspace, draft=draft)
            return self._result_for_started(draft, workspace=workspace, campaign_payload=campaign_payload)

        draft.status = "collecting"
        draft.pending_confirmation = False
        draft.touch()
        self._store.save(workspace=workspace, draft=draft)
        return self._result_for_clarify(draft)

    def _start_campaign(
        self,
        workspace: str,
        draft: CampaignNegotiationDraft,
        *,
        delivery_session: DeliverySession | None = None,
    ) -> dict[str, Any]:
        composition_mode = draft.composition_mode or ("composition" if draft.skeleton_changed else "template")
        template_origin = draft.selected_template_id or draft.recommended_template_id
        pending_checks = self._pending_minimal_correctness_checks(draft)
        feedback_contract = self._feedback_contract_from_delivery_session(delivery_session)
        spec = {
            "top_level_goal": draft.goal or "Campaign Goal",
            "materials": list(draft.materials),
            "hard_constraints": list(draft.hard_constraints),
            "workspace_root": workspace,
            "repo_root": workspace,
            "campaign_title": (draft.goal or "Campaign").strip()[:80],
            "iteration_budget": draft.iteration_budget or {},
            "metadata": {
                "template_origin": template_origin,
                "composition_mode": composition_mode,
                "skeleton_changed": bool(draft.skeleton_changed),
                "composition_plan": dict(draft.composition_plan or {}),
                "created_from": "campaign_negotiation",
                "negotiation_session_id": draft.session_id,
                "startup_mode": draft.startup_mode or "confirmed",
                "pending_correctness_checks": pending_checks,
                "minimal_correctness_ready": not pending_checks,
                "planning_contract": {
                    "mode_id": draft.frontdoor_mode_id or "delivery",
                    "method_profile_id": self._method_profile_for_mode(draft.frontdoor_mode_id or "delivery"),
                    "plan_only": False,
                    "draft_ref": f"negotiations/campaign/{_safe_id(draft.session_id)}.json",
                    "spec_ref": "",
                    "plan_ref": "",
                    "progress_ref": "",
                },
                "evaluation_contract": {
                    "review_ref": "",
                    "latest_review_decision": "",
                    "latest_acceptance_decision": "",
                },
                "governance_contract": {
                    "autonomy_profile": self._autonomy_profile_for_template(template_origin),
                    "risk_level": "medium",
                    "approval_state": "none",
                },
            },
        }
        if feedback_contract:
            spec["metadata"]["feedback_contract"] = feedback_contract
        return self._campaign_service.create_campaign(workspace, spec)

    @staticmethod
    def _method_profile_for_mode(mode_id: str) -> str:
        normalized = str(mode_id or "").strip().lower()
        if normalized in {"delivery", "plan", "research"}:
            return "superpowers_like"
        return ""

    @staticmethod
    def _autonomy_profile_for_template(template_origin: str) -> str:
        template_id = str(template_origin or "").strip().lower()
        if template_id == "campaign.guarded_autonomy":
            return "guarded_autonomy"
        if template_id == "campaign.research_then_implement":
            return "research_delivery"
        return "reviewed_delivery"

    @staticmethod
    def _feedback_contract_from_delivery_session(delivery_session: DeliverySession | None) -> dict[str, Any]:
        if not isinstance(delivery_session, DeliverySession):
            return {}
        metadata = {
            key: value
            for key, value in dict(delivery_session.metadata or {}).items()
            if value not in (None, "")
        }
        platform = str(delivery_session.platform or "").strip().lower()
        contract = {
            "platform": platform,
            "delivery_mode": str(delivery_session.mode or "").strip() or "reply",
            "target": str(delivery_session.target or "").strip(),
            "target_type": str(delivery_session.target_type or "").strip() or "open_id",
            "thread_id": str(delivery_session.thread_id or "").strip(),
            "session_id": str(delivery_session.session_id or "").strip(),
            "progress_surface": "doc_plus_push" if platform == "feishu" else "push_only",
            "doc_enabled": platform == "feishu",
            "metadata": metadata,
        }
        return {key: value for key, value in contract.items() if value not in (None, "", {})}

    @staticmethod
    def _ready_to_start(draft: CampaignNegotiationDraft) -> bool:
        if not bool(draft.goal) or draft.confidence < 0.75:
            return False
        if CampaignNegotiationService._requires_discussion_before_start(draft):
            return CampaignNegotiationService._minimal_correctness_ready(draft)
        return True

    def _ensure_orchestrator_online(self):
        bootstrap = self._orchestrator_bootstrap
        if bootstrap is None or not hasattr(bootstrap, "ensure_online"):
            return None
        return bootstrap.ensure_online()

    @staticmethod
    def _is_confirmation(user_text: str) -> bool:
        lowered = str(user_text or "").strip().lower()
        if not lowered:
            return False
        if lowered in _CONFIRM_KEYWORDS:
            return True
        if len(lowered) <= 16 and any(keyword in lowered for keyword in _CONFIRM_KEYWORDS):
            return True
        return any(
            phrase in lowered
            for phrase in (
                "确认启动",
                "同意启动",
                "可以启动",
                "ok start",
                "start campaign",
            )
        )

    @staticmethod
    def _has_contextual_start_intent(user_text: str) -> bool:
        lowered = str(user_text or "").strip().lower()
        if not lowered:
            return False
        if any(re.search(pattern, lowered) for pattern in _DEFER_START_PATTERNS):
            return False
        if any(re.search(pattern, lowered) for pattern in _BACKEND_NEGATION_PATTERNS):
            return False
        normalized = re.sub(r"^(那就|就|直接|现在|可以|那|按这个|按现在的方向|按这个方向)\s*", "", lowered)
        return any(
            normalized == verb
            or normalized.startswith(f"{verb} ")
            or normalized.startswith(f"{verb}，")
            or normalized.startswith(f"{verb},")
            or normalized.startswith(f"{verb}。")
            or normalized.startswith(f"{verb}；")
            or normalized.startswith(f"{verb};")
            or normalized.startswith(f"{verb}：")
            or normalized.startswith(f"{verb}:")
            for verb in _START_INTENT_VERBS
        )

    def _should_launch_from_followup(
        self,
        draft: CampaignNegotiationDraft,
        user_text: str,
    ) -> bool:
        if self._is_confirmation(user_text):
            return True
        if not bool(draft.pending_confirmation):
            return False
        return self._has_contextual_start_intent(user_text)

    def _should_restart_started_campaign_negotiation(self, user_text: str) -> bool:
        lowered = str(user_text or "").strip().lower()
        if not lowered:
            return False
        if any(hint in lowered for hint in _NEGOTIATION_RESTART_HINTS):
            return True
        return self._looks_like_campaign(user_text) or self._looks_like_background_task_candidate(user_text)

    def _should_append_feedback_to_started_campaign(
        self,
        user_text: str,
        *,
        intake_decision: Mapping[str, Any] | None = None,
    ) -> bool:
        lowered = str(user_text or "").strip().lower()
        if not lowered:
            return False
        if self._has_contextual_start_intent(user_text):
            return True
        if any(hint in lowered for hint in _STARTED_FEEDBACK_HINTS):
            return True
        intake_map = dict(intake_decision or {})
        if str(intake_map.get("mode") or "").strip() == "status_query":
            return False
        return False

    @staticmethod
    def _looks_like_campaign(user_text: str) -> bool:
        text = str(user_text or "").strip()
        lowered = text.lower()
        if "`" in text and any(keyword in text for keyword in _DIRECT_EXECUTION_HINTS):
            return False
        if any(re.search(pattern, lowered) for pattern in _BACKEND_NEGATION_PATTERNS):
            return False
        if any(keyword in lowered for keyword in _EXPLICIT_BACKEND_HINTS):
            return True
        if "campaign" in lowered:
            return True
        program_hits = sum(1 for keyword in ("长期推进", "长期持续推进", "持续推进", "多阶段", "迭代", "跟进") if keyword in lowered)
        if program_hits >= 2 and any(keyword in lowered for keyword in ("项目", "任务")):
            return True
        return any(keyword in lowered for keyword in _CAMPAIGN_KEYWORDS if keyword not in {"长期", "持续", "迭代", "推进"})

    @staticmethod
    def _looks_like_background_task_candidate(user_text: str) -> bool:
        text = str(user_text or "").strip()
        lowered = text.lower()
        if not lowered:
            return False
        if any(keyword in text for keyword in _DIRECT_EXECUTION_HINTS):
            return False
        if any(re.search(pattern, lowered) for pattern in _BACKEND_NEGATION_PATTERNS):
            return False
        if not any(keyword in lowered for keyword in _EXPLICIT_BACKEND_HINTS):
            return False
        env_hits = sum(1 for keyword in ("ssh", "服务器", "目录", "路径", "workspace", "仓库") if keyword in lowered)
        research_hits = sum(1 for keyword in _RESEARCH_DELIVERY_KEYWORDS if keyword in lowered)
        action_hits = sum(1 for keyword in _BACKGROUND_TASK_ACTION_KEYWORDS if keyword in lowered)
        scope_hits = sum(1 for keyword in _BACKGROUND_TASK_SCOPE_KEYWORDS if keyword in lowered)
        if "后台任务" in lowered or "后台入口" in lowered:
            return True
        if env_hits >= 1 and research_hits >= 1 and action_hits >= 1:
            return True
        if research_hits >= 2 and (action_hits >= 1 or scope_hits >= 1):
            return True
        return scope_hits >= 2 and action_hits >= 1

    def _should_open_negotiation(self, user_text: str) -> bool:
        return (
            self._looks_like_campaign(user_text)
            or self._looks_like_background_task_candidate(user_text)
            or self._detect_skeleton_change(user_text)
        )

    @staticmethod
    def _allows_frontdoor_escape(user_text: str) -> bool:
        lowered = str(user_text or "").strip().lower()
        return any(re.search(pattern, lowered) for pattern in _BACKEND_NEGATION_PATTERNS)

    @staticmethod
    def _requires_discussion_before_start(draft: CampaignNegotiationDraft) -> bool:
        lowered = str(draft.goal or "").strip().lower()
        return bool(str(draft.task_mode or "").strip() == "background_entry") or any(
            keyword in lowered for keyword in _DISCUSSION_FIRST_KEYWORDS
        )

    @staticmethod
    def _detect_skeleton_change(user_text: str) -> bool:
        lowered = str(user_text or "").strip().lower()
        return any(keyword in lowered for keyword in _SKELETON_CHANGE_KEYWORDS)

    @staticmethod
    def _detect_composition_request(user_text: str) -> bool:
        lowered = str(user_text or "").strip().lower()
        return any(keyword in lowered for keyword in _COMPOSITION_KEYWORDS)

    @staticmethod
    def _explicitly_defers_start(user_text: str) -> bool:
        lowered = str(user_text or "").strip().lower()
        return any(re.search(pattern, lowered) for pattern in _DEFER_START_PATTERNS)

    def _resolve_composition_mode(self, draft: CampaignNegotiationDraft, user_text: str) -> str:
        if self._detect_composition_request(user_text):
            return "composition"
        if draft.skeleton_changed:
            return "composition"
        if draft.composition_mode:
            return draft.composition_mode
        return "template"

    def _resolve_template(
        self,
        draft: CampaignNegotiationDraft,
        fallback: CampaignTemplate,
    ) -> CampaignTemplate:
        template_id = draft.selected_template_id or draft.recommended_template_id
        if template_id:
            matched = self._library.get(template_id)
            if matched is not None:
                return matched
        return fallback

    def _extract_template_hint(self, user_text: str) -> str:
        text = str(user_text or "")
        match = _TEMPLATE_HINT_PATTERN.search(text)
        if match:
            return match.group(1).strip()
        normalized = text.strip().lower()
        for template in self._library.templates():
            if template.template_id.lower() in normalized:
                return template.template_id
            if template.display_name.lower() in normalized:
                return template.template_id
        return ""

    def _update_draft(self, draft: CampaignNegotiationDraft, user_text: str) -> CampaignNegotiationDraft:
        text = str(user_text or "").strip()
        if not draft.goal and text:
            draft.goal = text[:180]
        if not draft.task_mode:
            draft.task_mode = "background_entry" if self._looks_like_background_task_candidate(text) else "campaign"
        if not draft.background_reason and draft.task_mode == "background_entry":
            draft.background_reason = self._infer_background_reason(text)
        draft.materials.extend(self._extract_tagged_list(text, ("材料", "参考", "链接")))
        draft.hard_constraints.extend(self._extract_tagged_list(text, ("约束", "必须", "禁止", "不要")))
        draft.acceptance_criteria.extend(self._extract_tagged_list(text, ("验收", "目标", "做到")))
        draft.materials = list(dict.fromkeys([item for item in draft.materials if item]))
        draft.hard_constraints = list(dict.fromkeys([item for item in draft.hard_constraints if item]))
        draft.acceptance_criteria = list(dict.fromkeys([item for item in draft.acceptance_criteria if item]))
        required_checks = self._collect_minimal_correctness_checks(draft.goal or text)
        if required_checks:
            draft.minimal_correctness_checks = list(dict.fromkeys([*draft.minimal_correctness_checks, *required_checks]))
        draft.confirmed_correctness_checks = self._merge_confirmed_correctness_checks(
            draft.confirmed_correctness_checks,
            self._detect_confirmed_correctness_checks(text, required_checks=draft.minimal_correctness_checks),
        )
        draft.touch()
        return draft

    @staticmethod
    def _infer_background_reason(text: str) -> str:
        lowered = str(text or "").strip().lower()
        reasons: list[str] = []
        if any(keyword in lowered for keyword in ("ssh", "服务器")):
            reasons.append("external_environment")
        if any(keyword in lowered for keyword in ("文献", "论文", "kdd", "研究背景", "现状")):
            reasons.append("research_delivery")
        if any(keyword in lowered for keyword in ("不少于", "100篇", "一百篇", "分类矩阵", "参考文献库")):
            reasons.append("multi_step_deliverable")
        return ",".join(reasons) or "complex_background_task"

    @staticmethod
    def _collect_minimal_correctness_checks(text: str) -> list[str]:
        lowered = str(text or "").strip().lower()
        checks: list[str] = []
        if any(keyword in lowered for keyword in ("ssh", "服务器")):
            checks.append("ssh_reachable")
        if any(keyword in lowered for keyword in ("目录", "路径", "仓库", "transfer_recovery", "transferrecovery")):
            checks.append("target_path_exists")
        if any(keyword in lowered for keyword in ("研究主题", "研究问题", "topic")):
            checks.append("research_anchor_confirmed")
        if any(keyword in lowered for keyword in ("文献", "不少于", "100篇", "一百篇", "分类矩阵", "参考文献库")):
            checks.append("literature_scope_confirmed")
        if any(keyword in lowered for keyword in ("kdd", "研究背景", "现状", "输出", "格式", "中文", "英文")):
            checks.append("output_contract_confirmed")
        return list(dict.fromkeys(checks))

    @staticmethod
    def _detect_confirmed_correctness_checks(text: str, *, required_checks: list[str]) -> list[str]:
        lowered = str(text or "").strip().lower()
        confirmed: list[str] = []
        if not lowered:
            return confirmed
        explicit_confirm = any(keyword in lowered for keyword in ("已确认", "已明确", "已验证", "已经", "可连", "存在", "已定", "定为"))
        if "ssh_reachable" in required_checks and (
            re.search(r"ssh.*(可连|已通|正常|没问题)", lowered)
            or re.search(r"(服务器|179).*(可连|可达|能连|已通)", lowered)
            or "已确认ssh" in lowered
        ):
            confirmed.append("ssh_reachable")
        if "target_path_exists" in required_checks and (
            re.search(r"(目录|路径|transfer_?recovery).*(存在|已进入|可访问|可读)", lowered)
            or "材料入口已确认" in lowered
        ):
            confirmed.append("target_path_exists")
        if "research_anchor_confirmed" in required_checks and (
            re.search(r"(研究主题|研究问题).*(已明确|已确认|明确为|定为)", lowered)
            or re.search(r"(研究主题|研究问题)[:：]\s*.+", text)
        ):
            confirmed.append("research_anchor_confirmed")
        if "literature_scope_confirmed" in required_checks and (
            "文献筛选边界" in lowered
            or "不少于" in lowered
            or "100篇" in lowered
            or "一百篇" in lowered
            or explicit_confirm and "文献" in lowered
        ):
            confirmed.append("literature_scope_confirmed")
        if "output_contract_confirmed" in required_checks and (
            "kdd" in lowered
            or re.search(r"(输出|格式|语言).*(已定|明确|为)", lowered)
            or "研究背景与现状" in lowered
        ):
            confirmed.append("output_contract_confirmed")
        return list(dict.fromkeys(confirmed))

    @staticmethod
    def _merge_confirmed_correctness_checks(existing: list[str], incoming: list[str]) -> list[str]:
        return list(dict.fromkeys([*(existing or []), *(incoming or [])]))

    @staticmethod
    def _minimal_correctness_ready(draft: CampaignNegotiationDraft) -> bool:
        required = list(draft.minimal_correctness_checks or [])
        if not required:
            return True
        confirmed = set(draft.confirmed_correctness_checks or [])
        return all(item in confirmed for item in required)

    @staticmethod
    def _pending_minimal_correctness_checks(draft: CampaignNegotiationDraft) -> list[str]:
        required = list(draft.minimal_correctness_checks or [])
        confirmed = set(draft.confirmed_correctness_checks or [])
        return [item for item in required if item not in confirmed]

    @staticmethod
    def _extract_tagged_list(text: str, tags: tuple[str, ...]) -> list[str]:
        results: list[str] = []
        for tag in tags:
            if tag not in text:
                continue
            segments = text.split(tag, 1)[-1]
            for item in re.split(r"[，,;；。\n]", segments):
                cleaned = item.strip(" :：\t")
                if cleaned:
                    results.append(cleaned)
        return results

    def _build_composition_plan(
        self,
        draft: CampaignNegotiationDraft,
        template: CampaignTemplate,
    ) -> CampaignCompositionPlan:
        plan = CampaignCompositionPlan(
            base_template_id=template.template_id,
            phase_plan=list(template.phases),
            role_plan=list(template.roles),
            diff_summary=[],
            skeleton_changed=bool(draft.skeleton_changed),
            composition_mode=draft.composition_mode or "template",
        )
        if draft.composition_mode == "composition":
            plan.diff_summary.append("composition_requested")
        if draft.skeleton_changed:
            plan.diff_summary.append("custom_skeleton_requested")
        return plan

    def _result_for_started(
        self,
        draft: CampaignNegotiationDraft,
        *,
        workspace: str = "",
        campaign_payload: Mapping[str, Any] | None = None,
    ) -> CampaignNegotiationResult:
        template_id = draft.selected_template_id or draft.recommended_template_id
        composition_mode = draft.composition_mode or ("composition" if draft.skeleton_changed else "template")
        startup_mode = draft.startup_mode or "confirmed"
        pending_checks = self._pending_minimal_correctness_checks(draft)
        payload = dict(campaign_payload or {})
        if not payload and workspace and draft.started_campaign_id:
            try:
                payload = self._query_service.get_campaign_status(workspace, draft.started_campaign_id)
            except Exception:
                payload = {}
        feedback_doc = dict(payload.get("feedback_doc") or (payload.get("metadata") or {}).get("feedback_doc") or {})
        doc_url = str(feedback_doc.get("url") or "").strip()
        doc_title = str(feedback_doc.get("title") or "").strip() or "Task Doc"
        text = "\n".join(
            [
                "campaign started",
                f"campaign_id: {draft.started_campaign_id}",
                f"goal: {draft.goal}",
                f"template: {template_id}",
                f"mode: {composition_mode}",
                f"startup_mode: {startup_mode}",
                (
                    "pending_checks: none"
                    if not pending_checks
                    else "pending_checks: " + ", ".join(pending_checks)
                ),
            ]
            + ([f"task_doc: {doc_url}"] if doc_url else [])
        )
        bundle = OutputBundle(
            summary=f"campaign started: {draft.started_campaign_id}",
            text_blocks=[TextBlock(text=text)],
            doc_links=[DocLink(url=doc_url, title=doc_title, metadata={"campaign_id": draft.started_campaign_id})] if doc_url else [],
            metadata={
                "campaign_id": draft.started_campaign_id,
                "negotiation_status": "started",
                "frontdoor_action": "background_entry",
                "frontdoor_target_kind": "campaign",
                "frontdoor_target_id": draft.started_campaign_id,
                "frontdoor_blocked": False,
                "frontdoor_resolution_source": "campaign_negotiation",
                "template_id": template_id,
                "composition_mode": composition_mode,
                "skeleton_changed": bool(draft.skeleton_changed),
                "startup_mode": startup_mode,
                "pending_correctness_checks": pending_checks,
                "minimal_correctness_ready": not pending_checks,
                "feedback_doc": feedback_doc,
            },
        )
        return CampaignNegotiationResult(
            handled=True,
            output_bundle=bundle,
            metadata={
                "campaign_id": draft.started_campaign_id,
                "negotiation_status": "started",
                "frontdoor_action": "background_entry",
                "frontdoor_target_kind": "campaign",
                "frontdoor_target_id": draft.started_campaign_id,
                "frontdoor_blocked": False,
                "frontdoor_resolution_source": "campaign_negotiation",
                "template_origin": template_id,
                "composition_mode": composition_mode,
                "skeleton_changed": bool(draft.skeleton_changed),
                "startup_mode": startup_mode,
                "pending_correctness_checks": pending_checks,
                "minimal_correctness_ready": not pending_checks,
                "feedback_doc": feedback_doc,
                "model_reply_prompt": self._build_model_reply_prompt(
                    draft,
                    status="started",
                    extra_lines=[
                        "后台任务已经创建完成。请自然地告诉用户：任务已转入后台推进，并吸收本轮启动前的约束补充；不要回放固定 started 回执。",
                        (
                            f"任务文档：{doc_url}"
                            if doc_url
                            else "如果当前没有任务文档链接，就只说明后续会通过正常进度同步渠道回报。"
                        ),
                    ],
                ),
            },
        )

    def _result_for_plan(self, draft: CampaignNegotiationDraft, *, workspace: str) -> CampaignNegotiationResult:
        template_id = draft.selected_template_id or draft.recommended_template_id
        draft_ref = f"negotiations/campaign/{_safe_id(draft.session_id)}.json"
        planning_contract = {
            "mode_id": "plan",
            "method_profile_id": self._method_profile_for_mode("plan"),
            "plan_only": True,
            "draft_ref": draft_ref,
            "spec_ref": draft_ref,
            "plan_ref": draft_ref,
            "progress_ref": "",
        }
        lines = [
            "planning summary ready",
            f"goal: {draft.goal or '(missing)'}",
            f"template: {template_id or '-'}",
            f"draft_ref: {draft_ref}",
            f"materials: {len(draft.materials)}",
            f"constraints: {len(draft.hard_constraints)}",
        ]
        if workspace:
            lines.append(f"workspace: {workspace}")
        bundle = OutputBundle(
            summary="planning summary ready",
            text_blocks=[TextBlock(text="\n".join(lines))],
            metadata={
                "negotiation_status": "planned",
                "frontdoor_action": "plan_only",
                "frontdoor_target_kind": "campaign_draft",
                "frontdoor_target_id": draft.draft_id,
                "frontdoor_blocked": False,
                "frontdoor_resolution_source": "campaign_negotiation",
                "template_id": template_id,
                "planning_contract": planning_contract,
            },
        )
        return CampaignNegotiationResult(
            handled=True,
            output_bundle=bundle,
            metadata={
                **dict(bundle.metadata or {}),
                "template_origin": template_id,
                "model_reply_prompt": self._build_model_reply_prompt(
                    draft,
                    status="planned",
                    extra_lines=[
                        "这是 `/plan` 模式，只输出任务草案、工作规格和执行计划摘要，不创建 campaign。",
                        f"当前草案引用：{draft_ref}",
                    ],
                ),
            },
        )

    def _append_feedback_to_started_campaign(
        self,
        *,
        workspace: str,
        draft: CampaignNegotiationDraft,
        feedback: str,
    ) -> CampaignNegotiationResult | None:
        campaign_id = str(draft.started_campaign_id or "").strip()
        if not workspace or not campaign_id:
            return None
        try:
            payload = self._query_service.get_campaign_status(workspace, campaign_id)
        except Exception:
            payload = {}
        mission_id = str(payload.get("mission_id") or "").strip()
        if not mission_id:
            return None
        append_result = self._query_service.append_user_feedback(workspace, mission_id, feedback)
        event_id = str(append_result.get("event_id") or "").strip()
        text = "\n".join(
            [
                "campaign feedback appended",
                f"campaign_id: {campaign_id}",
                f"mission_id: {mission_id}",
                f"feedback: {str(feedback or '').strip()[:160]}",
            ]
        )
        bundle = OutputBundle(
            summary=f"campaign feedback appended: {campaign_id}",
            text_blocks=[TextBlock(text=text)],
            metadata={
                "campaign_id": campaign_id,
                "mission_id": mission_id,
                "feedback_event_id": event_id,
                "negotiation_status": "started",
                "frontdoor_action": "append_feedback",
                "frontdoor_target_kind": "campaign",
                "frontdoor_target_id": campaign_id,
                "frontdoor_blocked": False,
                "frontdoor_resolution_source": "campaign_negotiation",
                "feedback_appended": True,
            },
        )
        return CampaignNegotiationResult(
            handled=True,
            output_bundle=bundle,
            metadata={
                "campaign_id": campaign_id,
                "mission_id": mission_id,
                "feedback_event_id": event_id,
                "negotiation_status": "started",
                "frontdoor_action": "append_feedback",
                "frontdoor_target_kind": "campaign",
                "frontdoor_target_id": campaign_id,
                "frontdoor_blocked": False,
                "frontdoor_resolution_source": "campaign_negotiation",
                "feedback_appended": True,
                "model_reply_prompt": self._build_model_reply_prompt(
                    draft,
                    status="started",
                    extra_lines=[
                        "这轮用户是在给已启动的后台任务补充约束或补充反馈。",
                        "请自然告诉用户：我已把这条补充记入后台任务，并会让后台主线吸收它；不要回退成前台自己继续执行主任务。",
                    ],
                ),
            },
        )

    def _result_for_confirmation(self, draft: CampaignNegotiationDraft) -> CampaignNegotiationResult:
        template_id = draft.selected_template_id or draft.recommended_template_id
        composition_mode = draft.composition_mode or "composition"
        text = "\n".join(
            [
                "campaign draft needs confirmation (custom skeleton detected)",
                f"goal: {draft.goal}",
                f"template: {template_id}",
                "reply with '确认启动' to start campaign.",
            ]
        )
        bundle = OutputBundle(
            summary="campaign draft requires confirmation",
            text_blocks=[TextBlock(text=text)],
            metadata={
                "negotiation_status": "confirmation_required",
                "frontdoor_action": "background_entry",
                "frontdoor_target_kind": "campaign",
                "frontdoor_target_id": "",
                "frontdoor_blocked": False,
                "frontdoor_resolution_source": "campaign_negotiation",
                "template_id": template_id,
                "composition_mode": composition_mode,
                "skeleton_changed": True,
            },
        )
        return CampaignNegotiationResult(
            handled=True,
            output_bundle=bundle,
            metadata={
                "negotiation_status": "confirmation_required",
                "frontdoor_action": "background_entry",
                "frontdoor_target_kind": "campaign",
                "frontdoor_target_id": "",
                "frontdoor_blocked": False,
                "frontdoor_resolution_source": "campaign_negotiation",
                "template_origin": template_id,
                "composition_mode": composition_mode,
                "skeleton_changed": True,
                "model_reply_prompt": self._build_model_reply_prompt(draft, status="confirmation_required"),
            },
        )

    def _result_for_clarify(self, draft: CampaignNegotiationDraft) -> CampaignNegotiationResult:
        template_id = draft.selected_template_id or draft.recommended_template_id
        composition_mode = draft.composition_mode or ("composition" if draft.skeleton_changed else "template")
        text = "\n".join(
            [
                "campaign negotiation in progress",
                f"goal: {draft.goal or '(missing)'}",
                f"template: {template_id}",
                "please provide missing goal/materials/constraints to start.",
            ]
        )
        bundle = OutputBundle(
            summary="campaign negotiation in progress",
            text_blocks=[TextBlock(text=text)],
            metadata={
                "negotiation_status": "collecting",
                "frontdoor_action": "background_entry",
                "frontdoor_target_kind": "campaign",
                "frontdoor_target_id": "",
                "frontdoor_blocked": False,
                "frontdoor_resolution_source": "campaign_negotiation",
                "template_id": template_id,
                "composition_mode": composition_mode,
                "skeleton_changed": bool(draft.skeleton_changed),
            },
        )
        return CampaignNegotiationResult(
            handled=True,
            output_bundle=bundle,
            metadata={
                "negotiation_status": "collecting",
                "frontdoor_action": "background_entry",
                "frontdoor_target_kind": "campaign",
                "frontdoor_target_id": "",
                "frontdoor_blocked": False,
                "frontdoor_resolution_source": "campaign_negotiation",
                "template_origin": template_id,
                "composition_mode": composition_mode,
                "skeleton_changed": bool(draft.skeleton_changed),
                "task_mode": draft.task_mode or "",
                "model_reply_prompt": self._build_model_reply_prompt(draft, status="collecting"),
            },
        )

    def _result_for_backend_entry(self, draft: CampaignNegotiationDraft) -> CampaignNegotiationResult:
        template_id = draft.selected_template_id or draft.recommended_template_id
        composition_mode = draft.composition_mode or ("composition" if draft.skeleton_changed else "template")
        required_checks = list(draft.minimal_correctness_checks or [])
        confirmed_checks = set(draft.confirmed_correctness_checks or [])
        missing_checks = [item for item in required_checks if item not in confirmed_checks]
        readiness_line = (
            "最小正确性验证已就绪，可在确认后放入后台。"
            if not missing_checks
            else "当前仍缺少最小正确性验证，chat 不会继续在前台执行主任务。"
        )
        lines = [
            "进入后台任务入口态。",
            f"goal: {draft.goal or '(missing)'}",
            f"template: {template_id}",
            readiness_line,
            "创建后台分支前，先和用户讨论并完成最小正确性验证；未完成前，不得回落成 chat 自己执行任务。",
        ]
        if required_checks:
            lines.append("最小正确性检查：")
            lines.extend(
                [
                    f"- [{ 'x' if item in confirmed_checks else ' ' }] {_MINIMAL_CHECK_LABELS.get(item, item)}"
                    for item in required_checks
                ]
            )
        if missing_checks:
            lines.append("你可以继续补齐这些缺口；如果你接受后台先边做边探索，也可以现在直接回复“确认启动”。")
        else:
            lines.append("现在只差你一句“确认启动”，就会进入后台任务创建分支。")
        bundle = OutputBundle(
            summary="campaign backend entry required",
            text_blocks=[TextBlock(text="\n".join(lines))],
            metadata={
                "negotiation_status": "backend_entry_required",
                "frontdoor_action": "background_entry",
                "frontdoor_target_kind": "campaign",
                "frontdoor_target_id": "",
                "frontdoor_blocked": True,
                "frontdoor_resolution_source": "campaign_negotiation",
                "template_id": template_id,
                "composition_mode": composition_mode,
                "skeleton_changed": bool(draft.skeleton_changed),
                "chat_execution_blocked": True,
                "task_mode": draft.task_mode or "",
                "background_reason": draft.background_reason or "",
                "minimal_correctness_ready": not missing_checks,
                "minimal_correctness_checks": required_checks,
                "confirmed_correctness_checks": list(confirmed_checks),
            },
        )
        return CampaignNegotiationResult(
            handled=True,
            output_bundle=bundle,
            metadata={
                "negotiation_status": "backend_entry_required",
                "frontdoor_action": "background_entry",
                "frontdoor_target_kind": "campaign",
                "frontdoor_target_id": "",
                "frontdoor_blocked": True,
                "frontdoor_resolution_source": "campaign_negotiation",
                "template_origin": template_id,
                "composition_mode": composition_mode,
                "skeleton_changed": bool(draft.skeleton_changed),
                "chat_execution_blocked": True,
                "task_mode": draft.task_mode or "",
                "background_reason": draft.background_reason or "",
                "minimal_correctness_ready": not missing_checks,
                "minimal_correctness_checks": required_checks,
                "confirmed_correctness_checks": list(confirmed_checks),
                "model_reply_prompt": self._build_model_reply_prompt(draft, status="backend_entry_required"),
            },
        )

    def _result_for_orchestrator_unavailable(
        self,
        draft: CampaignNegotiationDraft,
        bootstrap: OrchestratorBootstrapResult,
    ) -> CampaignNegotiationResult:
        template_id = draft.selected_template_id or draft.recommended_template_id
        text = "\n".join(
            [
                "campaign start blocked: orchestrator is offline and auto-start failed",
                f"goal: {draft.goal or '(missing)'}",
                f"template: {template_id}",
                f"try: {bootstrap.command_hint}",
                f"fallback: {bootstrap.fallback_command_hint}",
            ]
        )
        bundle = OutputBundle(
            summary="campaign blocked: orchestrator offline",
            text_blocks=[TextBlock(text=text)],
            metadata={
                "negotiation_status": "blocked_orchestrator_offline",
                "frontdoor_action": "background_entry",
                "frontdoor_target_kind": "campaign",
                "frontdoor_target_id": "",
                "frontdoor_blocked": True,
                "frontdoor_resolution_source": "campaign_negotiation",
                "template_id": template_id,
                "orchestrator_bootstrap_ok": False,
                "orchestrator_bootstrap_reason": bootstrap.reason,
            },
        )
        return CampaignNegotiationResult(
            handled=True,
            output_bundle=bundle,
            metadata={
                "negotiation_status": "blocked_orchestrator_offline",
                "frontdoor_action": "background_entry",
                "frontdoor_target_kind": "campaign",
                "frontdoor_target_id": "",
                "frontdoor_blocked": True,
                "frontdoor_resolution_source": "campaign_negotiation",
                "template_origin": template_id,
                "orchestrator_bootstrap_ok": False,
                "orchestrator_bootstrap_reason": bootstrap.reason,
                "model_reply_prompt": self._build_model_reply_prompt(
                    draft,
                    status="blocked_orchestrator_offline",
                    extra_lines=[
                        f"自动启动 orchestrator 失败，建议命令：{bootstrap.command_hint}",
                        f"备用命令：{bootstrap.fallback_command_hint}",
                    ],
                ),
            },
        )

    def _build_model_reply_prompt(
        self,
        draft: CampaignNegotiationDraft,
        *,
        status: str,
        extra_lines: list[str] | None = None,
    ) -> str:
        template_id = draft.selected_template_id or draft.recommended_template_id
        template = self._library.get(template_id) if template_id else None
        template_name = str(template.display_name if template is not None else template_id or "未定").strip()
        required_checks = list(draft.minimal_correctness_checks or [])
        confirmed_checks = set(draft.confirmed_correctness_checks or [])
        check_lines = [
            f"- {_MINIMAL_CHECK_LABELS.get(item, item)}：{'已确认' if item in confirmed_checks else '未确认'}"
            for item in required_checks
        ]
        protocol_blocks = [
            self._prompt_support.render_protocol_block("frontdoor_collaboration", heading="前门协作协议").strip(),
            self._prompt_support.render_protocol_block("background_entry_collaboration", heading="后台入口协作协议").strip(),
        ]
        status_instruction_map = {
            "backend_entry_required": "当前处于后台入口协作态。请自然地说明：你已经理解任务；如果用户愿意，也可以在未完全补齐最小正确性时以探索式后台启动，而不是只能卡在前台。",
            "confirmation_required": "当前处于后台入口确认态。请自然地说明：任务骨架已被改写，启动前还需要用户确认。",
            "collecting": "当前处于后台入口信息补齐态。请自然地说明：你已经理解了部分目标，但还缺少关键信息，先补齐再决定是否进入后台。",
            "blocked_orchestrator_offline": "当前处于后台入口阻塞说明态。请自然地说明：任务方向没问题，但 orchestrator 当前未成功启动，所以还不能进入后台。",
            "started": "当前后台任务已经创建。请自然地说明：任务已进入后台推进，吸收本轮补充约束；不要把这轮回复写成固定 started 回执，也不要回到前台执行主任务。",
        }
        lines = [
            *[item for item in protocol_blocks if item],
            "你现在不是执行态，而是 Butler 的前门协作入口态。",
            "请直接面向用户输出自然中文，不要输出内部字段名、模板 id、JSON、goal/template 这类测试或回执格式。",
            "不要假装已经 SSH 到服务器、不要假装已经检索文献、也不要假装已经写完论文。",
            "这一轮你的职责只有三件事：",
            "1. 复述你已理解的任务目标。",
            "2. 说明当前为什么还不能直接开始，或者还差什么。",
            "3. 引导用户补齐缺失信息；如果已经都齐了，就提示用户回复“确认启动”；如果还没齐但用户接受边做边探索，也可以提示现在确认后以探索式后台启动。",
            "如果当前会话已经进入后台入口态，而用户这轮明显是在推进启动并顺手补充约束，就把它理解为‘启动意图 + 约束补充’，不要回落成 chat 前台执行主任务。",
            "只有当用户明确说先别启动、不要后台、或者只要前台结果时，才继续停留前台协商。",
            status_instruction_map.get(status, "当前处于协商态，请先讨论再决定是否进入后台。"),
            f"当前任务目标：{draft.goal or '(missing)'}",
            f"推荐编排方向：{template_name}",
        ]
        if check_lines:
            lines.append("当前最小正确性检查状态：")
            lines.extend(check_lines)
        if extra_lines:
            lines.extend([str(item).strip() for item in extra_lines if str(item or "").strip()])
        lines.append("请保持回复像正常对话，而不是系统回执或 started 回放。")
        return "\n".join(lines)
