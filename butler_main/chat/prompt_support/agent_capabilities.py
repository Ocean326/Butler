from __future__ import annotations


PARALLEL_GUIDANCE = (
    "【Codex 原生并行协作】当前 chat 前台不再维护自定义 sub-agent / team / public agent library 调度壳。"
    "只有当用户明确要求并行、分工、拆任务或子代理协作时，才依赖 Codex 原生 subagent / parallel 能力。"
    "优先拆成边界清楚、可独立验收的子任务；读多写少的探索可并行，写代码时优先保证文件边界互不冲突。"
    "并行结果必须回到主线程统一汇总结论，不要把多路输出直接原样甩给用户。"
    "若当前运行时支持子代理模型选择，复杂主线与关键子任务默认优先 gpt-5.4；轻量扫描再考虑更快模型。"
    "默认不要为了并行而并行，必须先说明拆分依据、并行度和最终汇总方式。"
)


def load_team_definition(workspace, team_id: str):  # noqa: ANN001
    return None


def render_agent_capability_catalog_for_prompt(workspace, *, max_chars: int = 2600) -> str:  # noqa: ANN001
    if max_chars <= 0:
        return ""
    text = PARALLEL_GUIDANCE.strip()
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


__all__ = ["load_team_definition", "render_agent_capability_catalog_for_prompt"]
