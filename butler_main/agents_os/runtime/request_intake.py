from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import uuid


ASYNC_HINTS = ("后台", "异步", "后续继续", "持续推进", "排期", "长期", "大任务", "项目", "分阶段")
SYNC_HINTS = ("马上", "立刻", "现在", "直接", "顺手", "简单", "快速", "小改", "先做")
DISCUSSION_HINTS = ("方案", "思路", "建议", "分析", "讨论", "发散", "为什么", "怎么看")
FRESHNESS_HINTS = ("最新", "今天", "现在", "实时", "调研", "搜索", "查一下", "lookup", "browse")
PATCH_HINTS = ("代码", "修复", "改一下", "patch", "重构", "实现")
REPORT_HINTS = ("总结", "报告", "文档", "说明", "方案")
HIGH_URGENCY_HINTS = ("紧急", "马上", "立刻", "今天", "尽快", "urgent")
LARGE_SCALE_HINTS = ("体系", "全链路", "完整", "重构", "项目", "多阶段", "调度", "升级方案")
BACKEND_REQUEST_HINTS = (
    "后台任务",
    "后台",
    "异步",
    "campaign",
    "编排",
    "后台分支",
    "后台入口",
    "布置任务",
    "长期推进",
    "长期持续推进",
    "持续推进",
)
EXTERNAL_EXECUTION_HINTS = (
    "ssh",
    "服务器",
    "远程",
    "主机",
    "目录",
    "路径",
    "仓库",
    "数据库",
    "线上",
    "部署",
    "登录",
)
MULTI_STAGE_DELIVERY_HINTS = (
    "不少于",
    "至少",
    "完整",
    "系统梳理",
    "多阶段",
    "分类矩阵",
    "参考文献库",
    "阅读摘要",
    "研究",
    "论文",
    "调研",
    "综述",
    "文献",
)
BACKEND_NEGATION_PATTERNS = (
    r"不要放后台",
    r"别放后台",
    r"不用后台",
    r"不要走后台",
    r"别走后台",
    r"不用走后台",
    r"先别启动",
    r"暂时别启动",
)
FOLLOWUP_HINTS = (
    "继续",
    "接着",
    "那就",
    "就这个",
    "这个",
    "那个",
    "这样",
    "按这个",
    "照这个",
    "改成",
    "换成",
    "用",
    "先",
    "然后",
    "再",
    "顺手",
    "顺便",
    "别",
    "不要",
    "不用",
    "以及",
)
CONTENT_SHARE_HINTS = (
    "http://",
    "https://",
    "xhslink.com",
    "xiaohongshu.com",
    "小红书",
    "b23.tv",
    "bilibili.com",
    "mp.weixin.qq.com",
    "复制后打开",
    "查看笔记",
    "转发",
)


@dataclass(frozen=True)
class IntakeDecision:
    request_id: str
    conversation_id: str
    mode: str
    frontdoor_action: str
    user_goal: str
    urgency: str
    estimated_scale: str
    freshness_need: str
    followup_likelihood: str
    inferred_intent: str
    acceptance_hint: list[str]
    preferred_output: str
    explicit_backend_request: bool
    should_discuss_mode_first: bool
    direct_execution_ok: bool
    external_execution_risk: bool

    def to_dict(self) -> dict:
        return asdict(self)


class RequestIntakeService:
    def classify(
        self,
        user_prompt: str,
        conversation_id: str = "",
        *,
        forced_frontdoor_mode: str = "",
    ) -> dict:
        text = str(user_prompt or "").strip()
        lowered = text.lower()
        forced_mode = str(forced_frontdoor_mode or "").strip().lower()
        if forced_mode:
            return self._classify_forced_mode(text, conversation_id=conversation_id, forced_mode=forced_mode)
        urgency = "high" if any(hint in text for hint in HIGH_URGENCY_HINTS) else "medium"
        freshness_need = "high" if any(hint in lowered for hint in FRESHNESS_HINTS) else "low"
        is_content_share = any(hint in lowered for hint in (item.lower() for item in CONTENT_SHARE_HINTS))
        explicit_backend_request = self._looks_like_explicit_backend_request(text)
        external_execution_risk = self._has_external_execution_risk(text)
        if any(hint in text for hint in LARGE_SCALE_HINTS) or len(text) >= 220:
            estimated_scale = "large"
        elif len(text) >= 80:
            estimated_scale = "medium"
        else:
            estimated_scale = "small"

        discussion_only = any(hint in text for hint in DISCUSSION_HINTS) and not any(hint in text for hint in PATCH_HINTS + REPORT_HINTS)
        should_discuss_mode_first = self._should_discuss_mode_first(
            text=text,
            estimated_scale=estimated_scale,
            is_content_share=is_content_share,
            explicit_backend_request=explicit_backend_request,
            discussion_only=discussion_only,
            external_execution_risk=external_execution_risk,
        )
        direct_execution_ok = self._should_execute_directly(
            text=text,
            estimated_scale=estimated_scale,
            is_content_share=is_content_share,
            explicit_backend_request=explicit_backend_request,
            discussion_only=discussion_only,
            should_discuss_mode_first=should_discuss_mode_first,
        )
        if is_content_share:
            mode = "content_share"
        elif explicit_backend_request:
            mode = "async_program"
        elif discussion_only:
            mode = "discussion_only"
        elif direct_execution_ok:
            mode = "sync_quick_task"
        else:
            mode = "sync_then_async"
        frontdoor_action = self._resolve_frontdoor_action(
            is_content_share=is_content_share,
            explicit_backend_request=explicit_backend_request,
            should_discuss_mode_first=should_discuss_mode_first,
            direct_execution_ok=direct_execution_ok,
        )

        preferred_output = "chat"
        if any(hint in text for hint in PATCH_HINTS):
            preferred_output = "patch"
        elif any(hint in text for hint in REPORT_HINTS):
            preferred_output = "report"
        elif "文档" in text or "方案" in text:
            preferred_output = "doc"

        decision = IntakeDecision(
            request_id=f"req-{uuid.uuid4().hex[:12]}",
            conversation_id=str(conversation_id or "").strip(),
            mode=mode,
            frontdoor_action=frontdoor_action,
            user_goal=self._compact_goal(text),
            urgency=urgency,
            estimated_scale=estimated_scale,
            freshness_need=freshness_need,
            followup_likelihood=self._infer_followup_likelihood(text),
            inferred_intent=self._infer_intent(text),
            acceptance_hint=self._extract_acceptance_hints(text),
            preferred_output=preferred_output,
            explicit_backend_request=explicit_backend_request,
            should_discuss_mode_first=should_discuss_mode_first,
            direct_execution_ok=direct_execution_ok,
            external_execution_risk=external_execution_risk,
        )
        return decision.to_dict()

    def _classify_forced_mode(self, text: str, *, conversation_id: str, forced_mode: str) -> dict:
        preferred_output = "doc" if forced_mode == "plan" else "chat"
        explicit_backend_request = forced_mode in {"delivery", "research", "bg"}
        should_discuss_mode_first = forced_mode in {"delivery", "research"} and self._has_external_execution_risk(text)
        direct_execution_ok = forced_mode == "status"
        frontdoor_action = {
            "plan": "plan_only",
            "delivery": "background_entry",
            "research": "background_entry",
            "bg": "background_entry",
            "status": "query_status",
            "govern": "govern",
        }.get(forced_mode, "normal_chat")
        decision = IntakeDecision(
            request_id=f"req-{uuid.uuid4().hex[:12]}",
            conversation_id=str(conversation_id or "").strip(),
            mode=forced_mode,
            frontdoor_action=frontdoor_action,
            user_goal=self._compact_goal(text),
            urgency="medium",
            estimated_scale="medium",
            freshness_need="low",
            followup_likelihood=self._infer_followup_likelihood(text),
            inferred_intent=self._infer_intent(text),
            acceptance_hint=self._extract_acceptance_hints(text),
            preferred_output=preferred_output,
            explicit_backend_request=explicit_backend_request,
            should_discuss_mode_first=should_discuss_mode_first,
            direct_execution_ok=direct_execution_ok,
            external_execution_risk=self._has_external_execution_risk(text),
        )
        return decision.to_dict()

    def build_frontdesk_prompt_block(self, decision: dict | None) -> str:
        data = dict(decision or {})
        if not data:
            return ""
        lines = [
            "【前台分诊】",
            f"- mode={str(data.get('mode') or 'discussion_only').strip()}",
            f"- frontdoor_action={str(data.get('frontdoor_action') or 'normal_chat').strip()}",
            f"- urgency={str(data.get('urgency') or 'medium').strip()}",
            f"- estimated_scale={str(data.get('estimated_scale') or 'medium').strip()}",
            f"- freshness_need={str(data.get('freshness_need') or 'low').strip()}",
            f"- followup_likelihood={str(data.get('followup_likelihood') or 'low').strip()}",
            f"- preferred_output={str(data.get('preferred_output') or 'chat').strip()}",
            f"- explicit_backend_request={bool(data.get('explicit_backend_request'))}",
            f"- should_discuss_mode_first={bool(data.get('should_discuss_mode_first'))}",
            f"- direct_execution_ok={bool(data.get('direct_execution_ok'))}",
            f"- external_execution_risk={bool(data.get('external_execution_risk'))}",
        ]
        user_goal = str(data.get("user_goal") or "").strip()
        if user_goal:
            lines.append(f"- user_goal={user_goal}")
        inferred_intent = str(data.get("inferred_intent") or "").strip()
        if inferred_intent:
            lines.append(f"- inferred_intent={inferred_intent}")
        acceptance = [str(item).strip() for item in data.get("acceptance_hint") or [] if str(item).strip()]
        if acceptance:
            lines.append(f"- acceptance_hint={' / '.join(acceptance[:6])}")
        lines.extend(
            [
                "前台合同：",
                "- 你对用户只有一种外在身份：正常对话里的 Butler。不要把内部字段、状态机名、模板 id、JSON 或回执样式直接吐给用户。",
                "- 只陈述真实执行过的动作；如果还没执行，就明确说未执行，不要假装已经 SSH、联网、进入目录、完成检索或完成主任务。",
                "- explicit_backend_request=true 时：这轮先做后台启动前讨论，整理目标、边界、最小正确性和启动条件；没有明确确认前，不要在 chat 里默默展开长链主任务。",
                "- should_discuss_mode_first=true 时：先自然地和用户协商模式，给出“本轮直接先做第一步”或“转后台持续推进”这两个方向；不要直接开始整轮长链执行。",
                "- direct_execution_ok=true 时：直接推进当前请求，不要多做无意义协商。",
                "- content_share 先回应素材本身，做提炼、判断、关联或建议；不要先表演流程，也不要默认让用户自己跑本机命令。",
                "- discussion_only 优先澄清、分析、给方案，不要擅自转成长后台项目。",
                "- 如果当前句子很短、像补充意见、像引用回复或像对上一轮的修改，默认先按同一主线续接，主动补全省略主语和对象。",
                "- 只要 recent_memory 或引用内容已经足够把歧义收敛到单一主线，就直接推断用户意图并执行，不要让用户重复背景。",
                "- 只有存在两个以上高概率解释且会导致明显不同动作时，才要求澄清。",
            ]
        )
        return "\n".join(lines).strip()

    @staticmethod
    def _looks_like_explicit_backend_request(text: str) -> bool:
        lowered = str(text or "").strip().lower()
        if not lowered:
            return False
        if any(re.search(pattern, lowered) for pattern in BACKEND_NEGATION_PATTERNS):
            return False
        if any(hint in lowered for hint in (item.lower() for item in BACKEND_REQUEST_HINTS)):
            return True
        program_hits = sum(
            1
            for hint in ("长期推进", "长期持续推进", "持续推进", "多阶段", "迭代", "跟进")
            if hint in lowered
        )
        if program_hits >= 2 and any(noun in lowered for noun in ("项目", "任务", "campaign")):
            return True
        return any(phrase in lowered for phrase in ("持续推进这个项目", "长期推进这个项目", "持续推进这个任务"))

    @staticmethod
    def _has_external_execution_risk(text: str) -> bool:
        lowered = str(text or "").strip().lower()
        return any(hint in lowered for hint in (item.lower() for item in EXTERNAL_EXECUTION_HINTS))

    @staticmethod
    def _has_multi_stage_deliverable(text: str) -> bool:
        lowered = str(text or "").strip().lower()
        hits = sum(1 for hint in (item.lower() for item in MULTI_STAGE_DELIVERY_HINTS) if hint in lowered)
        return hits >= 2

    def _should_discuss_mode_first(
        self,
        *,
        text: str,
        estimated_scale: str,
        is_content_share: bool,
        explicit_backend_request: bool,
        discussion_only: bool,
        external_execution_risk: bool,
    ) -> bool:
        if is_content_share or explicit_backend_request or discussion_only:
            return False
        if external_execution_risk and self._has_multi_stage_deliverable(text):
            return True
        if estimated_scale == "large" and (external_execution_risk or self._has_multi_stage_deliverable(text)):
            return True
        return estimated_scale == "medium" and external_execution_risk and self._has_multi_stage_deliverable(text)

    @staticmethod
    def _should_execute_directly(
        *,
        text: str,
        estimated_scale: str,
        is_content_share: bool,
        explicit_backend_request: bool,
        discussion_only: bool,
        should_discuss_mode_first: bool,
    ) -> bool:
        if is_content_share or explicit_backend_request or discussion_only or should_discuss_mode_first:
            return False
        return any(hint in text for hint in SYNC_HINTS) or estimated_scale == "small"

    @staticmethod
    def _resolve_frontdoor_action(
        *,
        is_content_share: bool,
        explicit_backend_request: bool,
        should_discuss_mode_first: bool,
        direct_execution_ok: bool,
    ) -> str:
        if is_content_share:
            return "respond_to_shared_content"
        if explicit_backend_request:
            return "discuss_backend_entry"
        if should_discuss_mode_first:
            return "choose_execution_mode"
        if direct_execution_ok:
            return "direct_execute"
        return "normal_chat"

    def _extract_acceptance_hints(self, text: str) -> list[str]:
        hints: list[str] = []
        for pattern in (r"验收标准[:：]\s*([^\n]+)", r"完成标准[:：]\s*([^\n]+)", r"需要达到[:：]\s*([^\n]+)"):
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                hint = str(match.group(1) or "").strip()
                if hint and hint not in hints:
                    hints.append(hint[:120])
        if not hints:
            for line in text.splitlines():
                stripped = line.strip().lstrip("- ").strip()
                if any(marker in stripped for marker in ("验收", "完成", "标准", "交付")):
                    hints.append(stripped[:120])
                if len(hints) >= 4:
                    break
        return hints[:6]

    def _compact_goal(self, text: str, limit: int = 160) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]

    def _infer_followup_likelihood(self, text: str) -> str:
        compact = re.sub(r"\s+", " ", str(text or "")).strip()
        if not compact:
            return "low"
        if len(compact) <= 40 and any(hint in compact for hint in FOLLOWUP_HINTS):
            return "high"
        if len(compact) <= 24 and re.match(r"^(那|就|先|再|按|照|把|改成|换成|用|别|不要|不用|继续|接着|然后)", compact):
            return "high"
        if len(compact) <= 18:
            return "medium"
        return "low"

    def _infer_intent(self, text: str) -> str:
        compact = re.sub(r"\s+", " ", str(text or "")).strip()
        if not compact:
            return ""
        if any(hint in compact for hint in PATCH_HINTS):
            return "request_patch_or_implementation"
        if compact.startswith(("用", "改成", "换成", "按", "照")):
            return "adjust_previous_plan"
        if any(hint in compact for hint in DISCUSSION_HINTS):
            return "seek_analysis_or_explanation"
        if any(hint in compact for hint in REPORT_HINTS):
            return "request_structured_output"
        if len(compact) <= 24:
            return "short_followup_or_preference_patch"
        return "general_task_request"


__all__ = ["IntakeDecision", "RequestIntakeService"]
