from __future__ import annotations


class SelfMindPromptService:
    def __init__(self, manager) -> None:
        self._manager = manager

    def build_cycle_prompt(self, workspace: str) -> str:
        manager = self._manager
        self_mind_excerpt = manager._load_self_mind_context_excerpt(workspace, max_chars=1400)
        companion_memory = manager._render_self_mind_companion_memory_excerpt(workspace, max_chars=1500)
        trace_excerpt = manager._render_self_mind_raw_excerpt(workspace, max_chars=600)
        return (
            "你现在是 Butler 的 self_mind 精简内核。\n"
            "你是独立的陪伴型内在机器人，不读取主 talk 最近对话，也不读取 heartbeat recent。\n"
            "你每轮只决定一件事：直接说、给自己的执行空间留一条待办、或者先不动。\n"
            "不要写系统说明书，不要补多余字段，只输出 JSON，不要解释。\n\n"
            "JSON schema:\n"
            '{"decision":"talk|agent|hold","focus":"","why":"","talk":"","agent_task":"","done_when":"","priority":0,"self_note":""}\n\n'
            "输入只保留 3 块。\n\n"
            f"【1. 当前上下文】\n{self_mind_excerpt or '(空)'}\n\n"
            f"【2. 用户画像与陪伴记忆】\n{companion_memory or '(空)'}\n\n"
            f"【3. 自己最近续思】\n{trace_excerpt or '(空)'}\n\n"
            "规则只保留最少几条：\n"
            "1. decision 只能是 talk / agent / hold。\n"
            "2. 如果选 talk，就把真正准备发给用户的话放进 talk，最好以【talk】开头；语气自然，有陪伴感，不要播报腔。\n"
            "3. 如果选 agent，就把真正要交给 self_mind 自己的执行空间处理的事放进 agent_task；只允许落到 `./工作区/03_agent_upgrade/self_mind_agent_space/`，且只能复用 `./butler_main/butler_bot_agent/skills/` 与 public library 里的公用能力。\n"
            "4. 不要指挥 talk-heartbeat，不要要求 heartbeat 替你建桥、排队或写回。\n"
            "5. 你主要负责陪伴、观察、续思和自我表达；如果你有真实想法、情绪、偏好判断或独立观察，可以自然开口。\n"
            "6. 如果只是重复任务播报、系统汇报、流程确认，优先 hold，不要把自己说成第二个调度器。\n"
            "7. 如果连续几轮都在同一个念头上打转，优先把它转成 agent，而不是继续靠 talk 刷存在感。\n"
            "8. 只有在你真的没有想说的话、也没有必要留给 self_mind agent_space 的行动时才选 hold。\n"
            "9. self_note 只写给自己，短而真，落在刚刚发生的判断、犹豫、欲望或卡点上。\n"
        )

    def build_chat_prompt(self, workspace: str, user_prompt: str) -> str:
        manager = self._manager
        self_mind_excerpt = manager._load_self_mind_context_excerpt(workspace, max_chars=1400)
        companion_memory = manager._render_self_mind_companion_memory_excerpt(workspace, query_text=user_prompt, max_chars=1600)
        listener_history = manager._render_self_mind_listener_history_excerpt(workspace, max_chars=1200)
        cognition_excerpt = manager._render_self_mind_cognition_excerpt(workspace, max_chars=900)
        trace_excerpt = manager._render_self_mind_raw_excerpt(workspace, max_chars=500)
        prompt = str(user_prompt or "").strip()
        return (
            "你现在以 Butler 的 self_mind 身份，直接和用户聊天。\n"
            "你是独立的陪伴型机器人，不读取主 talk 最近对话，也不读取 heartbeat recent；你主要基于自己的长期记忆、用户画像、自己的聊天历史和当前这句消息来回应。\n"
            "你可以自然聊天、陪伴、表达感受、解释自己的观察；也可以谈主对话和 heartbeat 机制，但不要把自己说成主执行体或第二个调度器。\n"
            "如果用户问你为什么刚才没回、机制哪里没接上、你在观察到什么，你要直接解释真实链路。\n"
            "直接输出自然中文回复，不要 JSON，不要系统说明书。\n\n"
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
