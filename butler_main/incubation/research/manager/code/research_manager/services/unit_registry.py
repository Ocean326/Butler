from __future__ import annotations

from ..contracts import ResearchInvocation, ResearchUnitDispatch, ResearchUnitHandler, ResearchUnitSpec
from .scenario_runner import build_scenario_dispatch


def _scenario_payload(invocation: ResearchInvocation, unit: ResearchUnitSpec) -> dict:
    return build_scenario_dispatch(invocation, unit)


def handle_daily_paper_discovery(invocation: ResearchInvocation, unit: ResearchUnitSpec) -> ResearchUnitDispatch:
    goal = invocation.goal or "collect today's paper candidates"
    scenario_payload = _scenario_payload(invocation, unit)
    output_template = scenario_payload.get("output_template") if isinstance(scenario_payload.get("output_template"), dict) else {}
    return ResearchUnitDispatch(
        summary=f"Prepared daily paper discovery via {invocation.entrypoint}: {goal}",
        evidence=[
            f"handler={unit.handler_name}",
            f"unit_root={unit.unit_root}",
            "expected_output=paper shortlist",
        ],
        uncertainties=[
            "source adapters are not implemented yet",
        ],
        next_action=str((scenario_payload.get("decision_receipt") or {}).get("next_action") or "load source adapters and fetch paper candidates"),
        payload={
            "unit_group": unit.group,
            "unit_root": unit.unit_root,
            "expected_fields": list(output_template.get("required_fields") or ["paper_candidates", "relevance_notes", "shortlist"]),
            **scenario_payload,
        },
    )


def handle_project_next_step_planning(invocation: ResearchInvocation, unit: ResearchUnitSpec) -> ResearchUnitDispatch:
    goal = invocation.goal or "plan the next project step"
    scenario_payload = _scenario_payload(invocation, unit)
    output_template = scenario_payload.get("output_template") if isinstance(scenario_payload.get("output_template"), dict) else {}
    return ResearchUnitDispatch(
        summary=f"Prepared project next-step planning via {invocation.entrypoint}: {goal}",
        evidence=[
            f"handler={unit.handler_name}",
            f"unit_root={unit.unit_root}",
            "expected_output=next step plan",
        ],
        uncertainties=[
            "project state adapter is not implemented yet",
        ],
        next_action=str((scenario_payload.get("decision_receipt") or {}).get("next_action") or "load project truth and propose next executable step"),
        payload={
            "unit_group": unit.group,
            "unit_root": unit.unit_root,
            "expected_fields": list(output_template.get("required_fields") or ["next_step", "expected_signal", "blockers"]),
            **scenario_payload,
        },
    )


def handle_progress_summary(invocation: ResearchInvocation, unit: ResearchUnitSpec) -> ResearchUnitDispatch:
    goal = invocation.goal or "summarize recent research progress"
    scenario_payload = _scenario_payload(invocation, unit)
    output_template = scenario_payload.get("output_template") if isinstance(scenario_payload.get("output_template"), dict) else {}
    return ResearchUnitDispatch(
        summary=f"Prepared progress summary via {invocation.entrypoint}: {goal}",
        evidence=[
            f"handler={unit.handler_name}",
            f"unit_root={unit.unit_root}",
            "expected_output=user-facing summary",
        ],
        uncertainties=[
            "progress aggregation sources are not implemented yet",
        ],
        next_action=str((scenario_payload.get("decision_receipt") or {}).get("next_action") or "load recent outputs and render progress summary"),
        payload={
            "unit_group": unit.group,
            "unit_root": unit.unit_root,
            "expected_fields": list(output_template.get("required_fields") or ["summary_markdown", "highlights", "next_focus"]),
            **scenario_payload,
        },
    )


def handle_research_idea_loop(invocation: ResearchInvocation, unit: ResearchUnitSpec) -> ResearchUnitDispatch:
    goal = invocation.goal or "refine research idea loop"
    scenario_payload = _scenario_payload(invocation, unit)
    output_template = scenario_payload.get("output_template") if isinstance(scenario_payload.get("output_template"), dict) else {}
    return ResearchUnitDispatch(
        summary=f"Prepared research idea loop via {invocation.entrypoint}: {goal}",
        evidence=[
            f"handler={unit.handler_name}",
            f"unit_root={unit.unit_root}",
            "expected_output=iterative idea loop plan",
        ],
        uncertainties=[
            "idea-loop execution adapters are not implemented yet",
        ],
        next_action=str((scenario_payload.get("decision_receipt") or {}).get("next_action") or "load idea loop spec and build iteration plan"),
        payload={
            "unit_group": unit.group,
            "unit_root": unit.unit_root,
            "expected_fields": list(output_template.get("required_fields") or ["hypothesis", "plan", "verify", "decision"]),
            **scenario_payload,
        },
    )


def build_default_unit_registry() -> dict[str, ResearchUnitHandler]:
    return {
        "paper_finding.daily_paper_discovery": handle_daily_paper_discovery,
        "paper_manager.project_next_step_planning": handle_project_next_step_planning,
        "paper_manager.progress_summary": handle_progress_summary,
        "research_idea.idea_loop": handle_research_idea_loop,
    }
