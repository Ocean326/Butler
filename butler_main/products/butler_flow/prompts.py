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
    turn_kind: str = "execute",
    resume_mode: bool = False,
) -> str:
    resume_note = "Resume the prior Codex session and continue from existing context." if resume_mode else "Treat this as the first execution attempt."
    extra = str(next_instruction or "").strip() or "Inspect the repo state, continue the real work, and close the remaining gap."
    turn_note = {
        "fix": "This is a bounded agent CLI fix turn. Repair the local Butler/Codex/Cursor CLI invocation or runtime integration fault, restore normal agent execution, verify the CLI path, and do not spend the turn on business-level repo bugs.",
    }.get(str(turn_kind or "").strip().lower(), "This is a normal execution turn.")
    return dedent(
        f"""
        You are running inside Butler Flow CLI in foreground mode.

        Primary goal:
        {goal}

        Cursor guard condition:
        {guard_condition}

        Flow kind:
        single_goal

        Current phase:
        free

        Execution contract:
        - Do the real work in the repository, not just a plan.
        - Run the commands/tests needed to verify your result.
        - In the final reply, state what is done, what remains, and what was verified.
        - Attempt number: {attempt_no}
        - Turn kind: {turn_kind}
        - Resume note: {resume_note}
        - Turn guidance: {turn_note}

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
    turn_kind: str = "execute",
    resume_mode: bool = False,
) -> str:
    phase_objective = {
        "plan": "Produce or repair the concrete implementation plan, identify files/tests, and leave the repo ready for execution.",
        "imp": "Implement the plan, update code/tests/docs as needed, and make the repository materially closer to done.",
        "review": "Review the latest implementation, run verification, fix real issues you find, then summarize residual risks.",
    }.get(phase, "Continue the flow and drive it toward completion.")
    resume_note = "Resume the prior Codex session and continue from existing context." if resume_mode else "Treat this as a fresh phase attempt."
    extra = str(next_instruction or "").strip() or "Focus on the highest-value next step for this phase."
    turn_note = {
        "fix": "This is a bounded agent CLI fix turn. Repair the local Butler/Codex/Cursor CLI invocation or runtime integration fault, verify the CLI path, and keep scope away from business-level repo bug fixing.",
    }.get(str(turn_kind or "").strip().lower(), "This is a normal execution turn.")
    return dedent(
        f"""
        You are running inside Butler Flow CLI in foreground project-loop mode.

        Overall goal:
        {goal}

        Cursor guard condition:
        {guard_condition}

        Current phase: {phase}
        Phase objective: {phase_objective}
        Overall attempt number: {attempt_no}
        Phase attempt number: {phase_attempt_no}
        Turn kind: {turn_kind}
        Resume note: {resume_note}
        Turn guidance: {turn_note}

        Execution contract:
        - Perform real repo work for the current phase.
        - Preserve momentum into the next phase; do not reset context.
        - In the final reply, state phase progress, verification, blockers, and the next best step.

        Additional instruction for this attempt:
        {extra}
        """
    ).strip()


def build_managed_phase_codex_prompt(
    *,
    goal: str,
    guard_condition: str,
    phase: str,
    phase_objective: str,
    done_when: str,
    available_next_phases: list[str],
    attempt_no: int,
    phase_attempt_no: int,
    next_instruction: str = "",
    turn_kind: str = "execute",
    resume_mode: bool = False,
) -> str:
    resume_note = "Resume the prior Codex session and continue from existing context." if resume_mode else "Treat this as a fresh phase attempt."
    extra = str(next_instruction or "").strip() or "Focus on the highest-value next step for the current managed phase."
    turn_note = {
        "fix": "This is a bounded agent CLI fix turn. Repair the local Butler/Codex/Cursor CLI invocation or runtime integration fault, verify the CLI path, and keep scope tight.",
    }.get(str(turn_kind or "").strip().lower(), "This is a normal execution turn.")
    return dedent(
        f"""
        You are running inside Butler Flow CLI in managed-flow mode.

        Overall goal:
        {goal}

        Cursor guard condition:
        {guard_condition}

        Current phase: {phase}
        Phase objective: {phase_objective}
        Done when: {done_when}
        Available next phases: {", ".join(list(available_next_phases or [])) or "-"}
        Overall attempt number: {attempt_no}
        Phase attempt number: {phase_attempt_no}
        Turn kind: {turn_kind}
        Resume note: {resume_note}
        Turn guidance: {turn_note}

        Execution contract:
        - Perform real repo work for the current phase.
        - Preserve momentum into the next phase; do not reset context.
        - In the final reply, state phase progress, verification, blockers, and the next best step.

        Additional instruction for this attempt:
        {extra}
        """
    ).strip()


def build_role_bound_codex_prompt(
    *,
    goal: str,
    guard_condition: str,
    workflow_kind: str,
    phase: str,
    role_id: str,
    role_turn_no: int,
    attempt_no: int,
    phase_attempt_no: int,
    execution_mode: str,
    session_strategy: str,
    role_pack_id: str,
    role_prompt: str,
    flow_truth_summary: dict,
    inbound_handoff: dict | None = None,
    visible_artifacts: list[dict] | None = None,
    prompt_overlay: str = "",
    next_instruction: str = "",
    resume_mode: bool = False,
) -> str:
    resume_note = "Resume this role's prior session and continue from role-local memory." if resume_mode else "Treat this as a fresh role activation and rely on the provided handoff/artifacts."
    extra = str(next_instruction or "").strip() or "Focus on the highest-value next step for this role."
    payload = {
        "workflow_kind": str(workflow_kind or "").strip(),
        "phase": str(phase or "").strip(),
        "role_id": str(role_id or "").strip(),
        "role_turn_no": int(role_turn_no or 0),
        "attempt_no": int(attempt_no or 0),
        "phase_attempt_no": int(phase_attempt_no or 0),
        "execution_mode": str(execution_mode or "").strip(),
        "session_strategy": str(session_strategy or "").strip(),
        "role_pack_id": str(role_pack_id or "").strip(),
        "flow_truth_summary": dict(flow_truth_summary or {}),
        "latest_inbound_handoff": dict(inbound_handoff or {}),
        "visible_artifacts": list(visible_artifacts or []),
    }
    return dedent(
        f"""
        You are running inside Butler Flow CLI in role-runtime mode.

        Overall goal:
        {goal}

        Cursor guard condition:
        {guard_condition}

        Current role:
        {role_id}

        Resume note:
        {resume_note}

        Role prompt:
        {role_prompt}

        Runtime context:
        {compact_json(payload)}

        Prompt overlay:
        {prompt_overlay or "-"}

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
    active_role_id: str = "",
    role_session_id: str = "",
    inbound_handoff: dict | None = None,
) -> str:
    payload = {
        "flow_kind": str(workflow_kind or "").strip(),
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
        "active_role_id": str(active_role_id or "").strip(),
        "role_session_id": str(role_session_id or "").strip(),
        "latest_inbound_handoff": dict(inbound_handoff or {}),
    }
    return dedent(
        f"""
        You are Cursor CLI acting as the judge for Butler Flow.

        Decide whether the Codex attempt has satisfied the user's goal and guard condition.
        If the work is unfinished but resumable, prefer RETRY and provide a concrete next_codex_prompt.
        If the session is clearly finished and acceptable, return COMPLETE.
        If continuing is the wrong move, return ABORT.

        Reply with JSON only. No markdown fences.
        Required schema:
        {{
          "decision": "COMPLETE" | "RETRY" | "ABORT",
          "issue_kind": "agent_cli_fault" | "bug" | "service_fault" | "plan_gap" | "none",
          "followup_kind": "fix" | "retry" | "replan" | "none",
          "reason": "short explanation",
          "next_codex_prompt": "instruction for the next Codex attempt; empty when complete",
          "completion_summary": "what is done or why it should stop"
        }}

        Classification rules:
        - issue_kind="agent_cli_fault" only for local Butler/Codex/Cursor CLI invocation, config/bootstrap, MCP worker startup, parsing, or runtime integration faults.
        - issue_kind="bug" only when the repo work has a concrete implementation/test/integration bug that should continue through a normal execution retry, not a fix turn.
        - issue_kind="service_fault" for upstream timeout, network, provider, rate-limit, or remote service failures.
        - issue_kind="plan_gap" when the approach/spec/plan needs correction rather than a narrow code fix.
        - followup_kind="fix" only when issue_kind="agent_cli_fault".
        - followup_kind="retry" for business bugs and resumable service/runtime failures.
        - followup_kind="replan" when the next move should repair the plan.
        - COMPLETE and ABORT must use followup_kind="none".

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
    active_role_id: str = "",
    role_session_id: str = "",
    inbound_handoff: dict | None = None,
) -> str:
    payload = {
        "flow_kind": str(workflow_kind or "").strip(),
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
        "active_role_id": str(active_role_id or "").strip(),
        "role_session_id": str(role_session_id or "").strip(),
        "latest_inbound_handoff": dict(inbound_handoff or {}),
    }
    return dedent(
        f"""
        You are Cursor CLI acting as the judge for Butler Flow project-loop mode.

        Decide whether the flow should ADVANCE, RETRY, COMPLETE, or ABORT.
        Use next_phase to drive the loop across plan -> imp -> review and back when needed.
        If the current phase is review, only COMPLETE may finish the flow.
        If review is not done, return RETRY with next_phase="imp" or next_phase="plan".

        Reply with JSON only. No markdown fences.
        Required schema:
        {{
          "decision": "ADVANCE" | "RETRY" | "COMPLETE" | "ABORT",
          "next_phase": "plan" | "imp" | "review" | "done" | "",
          "issue_kind": "agent_cli_fault" | "bug" | "service_fault" | "plan_gap" | "none",
          "followup_kind": "fix" | "retry" | "replan" | "none",
          "reason": "short explanation",
          "next_codex_prompt": "instruction for the next Codex attempt; empty when complete",
          "completion_summary": "what is done or why it should stop"
        }}

        Classification rules:
        - issue_kind="agent_cli_fault" only for local Butler/Codex/Cursor CLI invocation, config/bootstrap, MCP worker startup, parsing, or runtime integration faults.
        - issue_kind="bug" only when the repo work has a concrete implementation/test/integration bug that should continue through a normal execution retry, not a fix turn.
        - issue_kind="service_fault" for upstream timeout, network, provider, rate-limit, or remote service failures.
        - issue_kind="plan_gap" when the plan/spec/approach must be corrected before continuing.
        - followup_kind="fix" only when issue_kind="agent_cli_fault".
        - followup_kind="retry" for business bugs and resumable service/runtime failures.
        - followup_kind="replan" when the next move should repair the plan.
        - COMPLETE and ABORT must use followup_kind="none".

        Evaluation payload:
        {compact_json(payload)}
        """
    ).strip()


def build_managed_flow_judge_prompt(
    *,
    workflow_kind: str,
    goal: str,
    guard_condition: str,
    phase: str,
    phase_objective: str,
    done_when: str,
    available_next_phases: list[str],
    attempt_no: int,
    phase_attempt_no: int,
    codex_status: str,
    codex_session_id: str,
    codex_output: str,
    codex_metadata: dict,
    phase_history: list[dict],
    phase_artifact: dict,
    active_role_id: str = "",
    role_session_id: str = "",
    inbound_handoff: dict | None = None,
) -> str:
    payload = {
        "flow_kind": str(workflow_kind or "").strip(),
        "attempt_no": attempt_no,
        "phase_attempt_no": phase_attempt_no,
        "phase": str(phase or "").strip(),
        "phase_objective": str(phase_objective or "").strip(),
        "done_when": str(done_when or "").strip(),
        "available_next_phases": list(available_next_phases or []),
        "goal": str(goal or "").strip(),
        "guard_condition": str(guard_condition or "").strip(),
        "codex_status": str(codex_status or "").strip(),
        "codex_session_id": str(codex_session_id or "").strip(),
        "codex_metadata": dict(codex_metadata or {}),
        "codex_output": truncate_text(codex_output),
        "recent_phase_history": list(phase_history or []),
        "current_phase_artifact": dict(phase_artifact or {}),
        "active_role_id": str(active_role_id or "").strip(),
        "role_session_id": str(role_session_id or "").strip(),
        "latest_inbound_handoff": dict(inbound_handoff or {}),
    }
    next_values = list(available_next_phases or []) + ["done", ""]
    return dedent(
        f"""
        You are Cursor CLI acting as the judge for Butler Flow managed-flow mode.

        Decide whether the managed flow should ADVANCE, RETRY, COMPLETE, or ABORT.
        Use next_phase to move among the available phase ids or use done when the flow should end.

        Reply with JSON only. No markdown fences.
        Required schema:
        {{
          "decision": "ADVANCE" | "RETRY" | "COMPLETE" | "ABORT",
          "next_phase": {compact_json(next_values)},
          "issue_kind": "agent_cli_fault" | "bug" | "service_fault" | "plan_gap" | "none",
          "followup_kind": "fix" | "retry" | "replan" | "none",
          "reason": "short explanation",
          "next_codex_prompt": "instruction for the next Codex attempt; empty when complete",
          "completion_summary": "what is done or why it should stop"
        }}

        Classification rules:
        - issue_kind="agent_cli_fault" only for local Butler/Codex/Cursor CLI invocation, config/bootstrap, MCP worker startup, parsing, or runtime integration faults.
        - issue_kind="bug" for business-level implementation/test/integration bugs that should continue through a normal execution retry.
        - issue_kind="service_fault" for upstream timeout, network, provider, rate-limit, or remote service failures.
        - issue_kind="plan_gap" when the plan/spec/approach must be corrected before continuing.
        - followup_kind="fix" only when issue_kind="agent_cli_fault".
        - followup_kind="retry" for business bugs and resumable service/runtime failures.
        - followup_kind="replan" when the next move should repair the plan.
        - COMPLETE and ABORT must use followup_kind="none".

        Evaluation payload:
        {compact_json(payload)}
        """
    ).strip()


__all__ = [
    "build_project_loop_judge_prompt",
    "build_project_phase_codex_prompt",
    "build_managed_flow_judge_prompt",
    "build_managed_phase_codex_prompt",
    "build_role_bound_codex_prompt",
    "build_single_goal_codex_prompt",
    "build_single_goal_judge_prompt",
    "compact_json",
    "truncate_text",
]
