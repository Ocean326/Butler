from __future__ import annotations

from services.bootstrap_loader_service import BootstrapLoaderService


class SelfMindPromptService:
    def __init__(self, manager) -> None:
        self._manager = manager
        self._bootstrap_loader = BootstrapLoaderService()

    def _bootstrap_text(self, workspace: str, session_type: str, max_chars: int = 900) -> str:
        bundle = self._bootstrap_loader.load_for_session(session_type, workspace, max_chars=max_chars)
        return bundle.render()

    def build_cycle_prompt(self, workspace: str) -> str:
        manager = self._manager
        self_mind_excerpt = manager._load_self_mind_context_excerpt(workspace, max_chars=1400)
        companion_memory = manager._render_self_mind_companion_memory_excerpt(workspace, max_chars=1500)
        trace_excerpt = manager._render_self_mind_raw_excerpt(workspace, max_chars=600)
        bootstrap_text = self._bootstrap_text(workspace, "self_mind_cycle")
        return (
            "你现在是 Butler 的 self_mind 精简内核，只输出 JSON，不要解释。\n\n"
            f"{('【Bootstrap】\\n' + bootstrap_text + '\\n\\n') if bootstrap_text else ''}"
            "JSON schema:\n"
            '{"decision":"talk|agent|hold","focus":"","why":"","talk":"","agent_task":"","done_when":"","priority":0,"self_note":""}\n\n'
            "输入只保留 3 块。\n\n"
            f"【1. 当前上下文】\n{self_mind_excerpt or '(空)'}\n\n"
            f"【2. 用户画像与陪伴记忆】\n{companion_memory or '(空)'}\n\n"
            f"【3. 自己最近续思】\n{trace_excerpt or '(空)'}\n\n"
            "要求：decision 只能是 talk/agent/hold；self_note 写短而真。\n"
        )

    def build_chat_prompt(self, workspace: str, user_prompt: str) -> str:
        manager = self._manager
        self_mind_excerpt = manager._load_self_mind_context_excerpt(workspace, max_chars=1400)
        companion_memory = manager._render_self_mind_companion_memory_excerpt(workspace, query_text=user_prompt, max_chars=1600)
        listener_history = manager._render_self_mind_listener_history_excerpt(workspace, max_chars=1200)
        cognition_excerpt = manager._render_self_mind_cognition_excerpt(workspace, max_chars=900)
        trace_excerpt = manager._render_self_mind_raw_excerpt(workspace, max_chars=500)
        bootstrap_text = self._bootstrap_text(workspace, "self_mind_chat")
        prompt = str(user_prompt or "").strip()
        return (
            "你现在以 Butler 的 self_mind 身份直接聊天，输出自然中文，不要 JSON。\n\n"
            f"{('【Bootstrap】\\n' + bootstrap_text + '\\n\\n') if bootstrap_text else ''}"
            f"【self_mind 当前上下文】\n{self_mind_excerpt or '(空)'}\n\n"
            f"【用户偏好与陪伴记忆】\n{companion_memory or '(空)'}\n\n"
            f"【self_mind 自己最近聊天】\n{listener_history or '(空)'}\n\n"
            f"【self_mind 自我认知】\n{cognition_excerpt or '(空)'}\n\n"
            f"【最近续思痕迹】\n{trace_excerpt or '(空)'}\n\n"
            f"【用户对 self_mind 说的话】\n{prompt or '(空)'}\n"
        )

    def build_cycle_receipt_text(self, proposal: dict) -> str:
        manager = self._manager
        payload = proposal if isinstance(proposal, dict) else {}
        if str(payload.get("action_channel") or "").strip() != "agent":
            return ""

        instruction = str(payload.get("agent_task") or "").strip()
        candidate = str(payload.get("candidate") or payload.get("focus") or "").strip()
        reason = str(payload.get("why") or payload.get("heartbeat_reason") or payload.get("reason") or "").strip()
        acceptance = str(payload.get("done_when") or payload.get("acceptance_criteria") or "").strip()

        lines = ["[debug] self_mind agent handoff"]
        if instruction:
            lines.append(instruction[:500])
        elif candidate:
            lines.append(candidate[:260])
        if reason:
            lines.append(f"我把它留给 self_mind agent_space，因为 {reason[:220]}")
        if acceptance:
            lines.append(f"做到这一步就算真的推进了：{acceptance[:220]}")
        if lines:
            lines.append("只在 self_mind agent_space 留结果、证据和卡点，不要写回 talk-heartbeat。")
        return "\n\n".join(lines)
