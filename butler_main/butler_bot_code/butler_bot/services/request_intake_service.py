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


@dataclass(frozen=True)
class IntakeDecision:
    request_id: str
    conversation_id: str
    mode: str
    user_goal: str
    urgency: str
    estimated_scale: str
    freshness_need: str
    acceptance_hint: list[str]
    preferred_output: str

    def to_dict(self) -> dict:
        return asdict(self)


class RequestIntakeService:
    def classify(self, user_prompt: str, conversation_id: str = "") -> dict:
        text = str(user_prompt or "").strip()
        lowered = text.lower()
        urgency = "high" if any(hint in text for hint in HIGH_URGENCY_HINTS) else "medium"
        freshness_need = "high" if any(hint in lowered for hint in FRESHNESS_HINTS) else "low"
        if any(hint in text for hint in LARGE_SCALE_HINTS) or len(text) >= 220:
            estimated_scale = "large"
        elif len(text) >= 80:
            estimated_scale = "medium"
        else:
            estimated_scale = "small"

        if any(hint in text for hint in ASYNC_HINTS) or estimated_scale == "large":
            mode = "async_program"
        elif any(hint in text for hint in DISCUSSION_HINTS) and not any(hint in text for hint in PATCH_HINTS + REPORT_HINTS):
            mode = "discussion_only"
        elif any(hint in text for hint in SYNC_HINTS) or estimated_scale == "small":
            mode = "sync_quick_task"
        else:
            mode = "sync_then_async"

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
            user_goal=self._compact_goal(text),
            urgency=urgency,
            estimated_scale=estimated_scale,
            freshness_need=freshness_need,
            acceptance_hint=self._extract_acceptance_hints(text),
            preferred_output=preferred_output,
        )
        return decision.to_dict()

    def build_frontdesk_prompt_block(self, decision: dict | None) -> str:
        data = dict(decision or {})
        if not data:
            return ""
        lines = [
            "【前台分诊】",
            f"- mode={str(data.get('mode') or 'discussion_only').strip()}",
            f"- urgency={str(data.get('urgency') or 'medium').strip()}",
            f"- estimated_scale={str(data.get('estimated_scale') or 'medium').strip()}",
            f"- freshness_need={str(data.get('freshness_need') or 'low').strip()}",
            f"- preferred_output={str(data.get('preferred_output') or 'chat').strip()}",
        ]
        user_goal = str(data.get("user_goal") or "").strip()
        if user_goal:
            lines.append(f"- user_goal={user_goal}")
        acceptance = [str(item).strip() for item in data.get("acceptance_hint") or [] if str(item).strip()]
        if acceptance:
            lines.append(f"- acceptance_hint={' / '.join(acceptance[:6])}")
        lines.extend(
            [
                "前台策略：",
                "1. 先按 mode 决定回复姿态，不要默认把所有任务都一轮做完。",
                "2. discussion_only 优先澄清、分析、给方案，不要擅自转成长异步项目。",
                "3. sync_quick_task 可以直接推进，但要给用户清楚的阶段反馈。",
                "4. sync_then_async 先同步交付框架、第一步或阶段结论，再说明后续异步推进点。",
                "5. async_program 要显式整理目标、边界、验收标准与阶段计划，必要时先补齐澄清问题。",
            ]
        )
        return "\n".join(lines).strip()

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
