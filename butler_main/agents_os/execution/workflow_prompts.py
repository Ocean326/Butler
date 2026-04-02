from __future__ import annotations

import json
from textwrap import dedent


def truncate_text(text: str, *, limit: int = 6000) -> str:
    raw = str(text or "").strip()
    if len(raw) <= limit:
        return raw
    head = max(400, limit // 2)
    tail = max(300, limit - head - 32)
    return f"{raw[:head]}\n...\n[truncated]\n...\n{raw[-tail:]}"


def compact_json(value, *, limit: int = 4000) -> str:
    return truncate_text(json.dumps(value, ensure_ascii=False, indent=2), limit=limit)


def build_single_goal_codex_prompt(
    *,
    goal: str,
    guard_condition: str,
    attempt_no: int,
    next_instruction: str = "",
    resume_mode: bool = False,
) -> str:
    resume_note = "Resume the prior Codex session and continue from existing context." if resume_mode else "Treat this as the first execution attempt."
    extra = str(next_instruction or "").strip() or "Inspect the repo state, continue the real work, and close the remaining gap."
    return dedent(
        f"""
        You are running inside Butler workflow shell in foreground mode.

        Primary goal:
        {goal}

        Cursor guard condition:
        {guard_condition}

        Workflow kind:
        single_goal

        Current phase:
        free

        Execution contract:
        - Do the real work in the repository, not just a plan.
        - Run the commands/tests needed to verify your result.
        - In the final reply, state what is done, what remains, and what was verified.
        - Attempt number: {attempt_no}
        - Resume note: {resume_note}

        Additional instruction for this attempt:
        {extra}
        """
    ).strip()


def build_project_phase_codex_prompt(
    *,
    goal: str,
    guard_condition: str,
    phase: str,
    attempt_no: int,
    phase_attempt_no: int,
    next_instruction: str = "",
    resume_mode: bool = False,
) -> str:
    phase_objective = {
        "plan": "Produce or repair the concrete implementation plan, identify files/tests, and leave the repo ready for execution.",
        "imp": "Implement the plan, update code/tests/docs as needed, and make the repository materially closer to done.",
        "review": "Review the latest implementation, run verification, fix real issues you find, then summarize residual risks.",
    }.get(phase, "Continue the workflow and drive it toward completion.")
    resume_note = "Resume the prior Codex session and continue from existing context." if resume_mode else "Treat this as a fresh phase attempt."
    extra = str(next_instruction or "").strip() or "Focus on the highest-value next step for this phase."
    return dedent(
        f"""
        You are running inside Butler workflow shell in foreground project-loop mode.

        Overall goal:
        {goal}

        Cursor guard condition:
        {guard_condition}

        Current phase: {phase}
        Phase objective: {phase_objective}
        Overall attempt number: {attempt_no}
        Phase attempt number: {phase_attempt_no}
        Resume note: {resume_note}

        Execution contract:
        - Perform real repo work for the current phase.
        - Preserve momentum into the next phase; do not reset context.
        - In the final reply, state phase progress, verification, blockers, and the next best step.

        Additional instruction for this attempt:
        {extra}
        """
    ).strip()


def build_single_goal_judge_prompt(
    *,
    workflow_kind: str,
    goal: str,
    guard_condition: str,
    phase: str,
    attempt_no: int,
    codex_status: str,
    codex_session_id: str,
    codex_output: str,
    codex_metadata: dict,
    phase_history: list[dict],
    phase_artifact: dict,
) -> str:
    payload = {
        "workflow_kind": str(workflow_kind or "").strip(),
        "current_phase": str(phase or "").strip(),
        "attempt_no": attempt_no,
        "goal": str(goal or "").strip(),
        "guard_condition": str(guard_condition or "").strip(),
        "codex_status": str(codex_status or "").strip(),
        "codex_session_id": str(codex_session_id or "").strip(),
        "codex_metadata": dict(codex_metadata or {}),
        "codex_output": truncate_text(codex_output),
        "recent_phase_history": list(phase_history or []),
        "current_phase_artifact": dict(phase_artifact or {}),
    }
    return dedent(
        f"""
        You are Cursor CLI acting as the workflow judge for Butler foreground workflow shell.

        Decide whether the Codex attempt has satisfied the user's goal and guard condition.
        If the work is unfinished but resumable, prefer RETRY and provide a concrete next_codex_prompt.
        If the session is clearly finished and acceptable, return COMPLETE.
        If continuing is the wrong move, return ABORT.

        Reply with JSON only. No markdown fences.
        Required schema:
        {{
          "decision": "COMPLETE" | "RETRY" | "ABORT",
          "reason": "short explanation",
          "next_codex_prompt": "instruction for the next Codex attempt; empty when complete",
          "completion_summary": "what is done or why it should stop"
        }}

        Evaluation payload:
        {compact_json(payload)}
        """
    ).strip()


def build_project_loop_judge_prompt(
    *,
    workflow_kind: str,
    goal: str,
    guard_condition: str,
    phase: str,
    attempt_no: int,
    phase_attempt_no: int,
    codex_status: str,
    codex_session_id: str,
    codex_output: str,
    codex_metadata: dict,
    phase_history: list[dict],
    phase_artifact: dict,
) -> str:
    payload = {
        "workflow_kind": str(workflow_kind or "").strip(),
        "attempt_no": attempt_no,
        "phase_attempt_no": phase_attempt_no,
        "phase": str(phase or "").strip(),
        "goal": str(goal or "").strip(),
        "guard_condition": str(guard_condition or "").strip(),
        "codex_status": str(codex_status or "").strip(),
        "codex_session_id": str(codex_session_id or "").strip(),
        "codex_metadata": dict(codex_metadata or {}),
        "codex_output": truncate_text(codex_output),
        "recent_phase_history": list(phase_history or []),
        "current_phase_artifact": dict(phase_artifact or {}),
    }
    return dedent(
        f"""
        You are Cursor CLI acting as the workflow judge for Butler foreground project-loop mode.

        Decide whether the workflow should ADVANCE, RETRY, COMPLETE, or ABORT.
        Use next_phase to drive the loop across plan -> imp -> review and back when needed.
        If the current phase is review, only COMPLETE may finish the workflow.
        If review is not done, return RETRY with next_phase="imp" or next_phase="plan".

        Reply with JSON only. No markdown fences.
        Required schema:
        {{
          "decision": "ADVANCE" | "RETRY" | "COMPLETE" | "ABORT",
          "next_phase": "plan" | "imp" | "review" | "done" | "",
          "reason": "short explanation",
          "next_codex_prompt": "instruction for the next Codex attempt; empty when complete",
          "completion_summary": "what is done or why it should stop"
        }}

        Evaluation payload:
        {compact_json(payload)}
        """
    ).strip()


__all__ = [
    "build_project_loop_judge_prompt",
    "build_project_phase_codex_prompt",
    "build_single_goal_codex_prompt",
    "build_single_goal_judge_prompt",
    "truncate_text",
]
