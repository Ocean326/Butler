from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from butler_main.runtime_os.process_runtime import (
    DecisionReceipt,
    HandoffReceipt,
    StepReceipt,
    WorkflowCursor,
    WorkflowRunProjection,
)

from ..contracts import ResearchInvocation, ResearchUnitSpec
from .scenario_registry import get_research_scenario, load_workflow_spec


_SCENARIO_DEFS: dict[str, dict[str, Any]] = {
    "brainstorm": {
        "entry_contract": {
            "supported_entrypoints": ["talk", "codex"],
            "required_inputs": ["goal_or_problem", "constraints_optional"],
        },
        "exit_contract": {
            "output_format": "brainstorm_note",
            "artifact_slot": "research.scenario.brainstorm.outputs",
            "required_fields": [
                "problem_frame",
                "idea_clusters",
                "candidate_directions",
                "recommended_direction",
                "open_questions",
            ],
        },
        "steps": {
            "capture": {
                "title": "Capture Problem Frame",
                "brief": "Lock the problem statement, constraints, and intended outcome before divergence.",
                "step_output_fields": ["problem_frame", "constraints", "target_outcome"],
                "exit_criteria": ["problem statement is explicit", "hard constraints are listed"],
                "artifact_slot": "research.scenario.brainstorm.capture",
            },
            "cluster": {
                "title": "Cluster Input Ideas",
                "brief": "Group raw observations or ideas into coherent clusters before expanding them.",
                "step_output_fields": ["idea_clusters", "cluster_labels", "supporting_signals"],
                "exit_criteria": ["idea groups are distinct", "noise is reduced into clusters"],
                "artifact_slot": "research.scenario.brainstorm.cluster",
            },
            "expand": {
                "title": "Expand Candidate Directions",
                "brief": "Expand the strongest clusters into concrete candidate directions with tradeoffs.",
                "step_output_fields": ["candidate_directions", "tradeoffs", "evidence_gaps"],
                "exit_criteria": ["at least one viable direction exists", "tradeoffs are explicit"],
                "artifact_slot": "research.scenario.brainstorm.expand",
            },
            "converge": {
                "title": "Converge on Options",
                "brief": "Converge to the smallest set of directions worth carrying forward.",
                "step_output_fields": ["recommended_direction", "rejected_options", "decision_reason"],
                "exit_criteria": ["top direction is explicit", "reasons for rejection are noted"],
                "artifact_slot": "research.scenario.brainstorm.converge",
            },
            "archive": {
                "title": "Archive Brainstorm Result",
                "brief": "Package the brainstorm into a reusable note and preserve open questions.",
                "step_output_fields": ["brainstorm_note", "open_questions", "follow_up_actions"],
                "exit_criteria": ["final note is stored", "follow-up actions are explicit"],
                "artifact_slot": "research.scenario.brainstorm.archive",
            },
        },
    },
    "paper_discovery": {
        "entry_contract": {
            "supported_entrypoints": ["orchestrator", "talk", "codex"],
            "required_inputs": ["topic_or_project_focus", "time_window_optional"],
        },
        "exit_contract": {
            "output_format": "paper_digest",
            "artifact_slot": "research.scenario.paper_discovery.outputs",
            "required_fields": [
                "topic_frame",
                "query_set",
                "paper_candidates",
                "screening_notes",
                "shortlist",
            ],
        },
        "steps": {
            "topic_lock": {
                "title": "Lock Topic Window",
                "brief": "Lock the topic, scope, and time window for this discovery round.",
                "step_output_fields": ["topic_frame", "time_window", "screening_boundary"],
                "exit_criteria": ["topic is explicit", "screening boundary is fixed"],
                "artifact_slot": "research.scenario.paper_discovery.topic_lock",
            },
            "query_plan": {
                "title": "Plan Queries",
                "brief": "Build the query set, sources, and screening heuristics before search.",
                "step_output_fields": ["query_set", "source_list", "screening_rules"],
                "exit_criteria": ["query set is usable", "screening rules are defined"],
                "artifact_slot": "research.scenario.paper_discovery.query_plan",
            },
            "search": {
                "title": "Search Candidates",
                "brief": "Collect candidate papers from the planned sources and queries.",
                "step_output_fields": ["paper_candidates", "source_hits", "candidate_metadata"],
                "exit_criteria": ["candidate pool exists", "candidate metadata is attached"],
                "artifact_slot": "research.scenario.paper_discovery.search",
            },
            "screen": {
                "title": "Screen Candidates",
                "brief": "Screen candidate papers and explain why items stay or drop.",
                "step_output_fields": ["screening_notes", "included_papers", "excluded_papers"],
                "exit_criteria": ["shortlist rationale is explicit", "screening notes are recorded"],
                "artifact_slot": "research.scenario.paper_discovery.screen",
            },
            "digest": {
                "title": "Digest Shortlist",
                "brief": "Produce the shortlist and digest for downstream reading or planning.",
                "step_output_fields": ["shortlist", "paper_digest", "next_reading_actions"],
                "exit_criteria": ["digest is ready", "next reading actions are listed"],
                "artifact_slot": "research.scenario.paper_discovery.digest",
            },
        },
    },
    "idea_loop": {
        "entry_contract": {
            "supported_entrypoints": ["orchestrator", "talk", "codex"],
            "required_inputs": ["hypothesis_or_change_goal", "target_metric_optional"],
        },
        "exit_contract": {
            "output_format": "experiment_archive",
            "artifact_slot": "research.scenario.idea_loop.outputs",
            "required_fields": [
                "hypothesis",
                "change_plan",
                "implementation_notes",
                "verification_result",
                "next_iteration",
            ],
        },
        "steps": {
            "idea_lock": {
                "title": "Lock Hypothesis",
                "brief": "Lock the hypothesis and the result signal worth improving.",
                "step_output_fields": ["hypothesis", "target_metric", "success_signal"],
                "exit_criteria": ["hypothesis is explicit", "target signal is measurable enough"],
                "artifact_slot": "research.scenario.idea_loop.idea_lock",
            },
            "plan_lock": {
                "title": "Lock Change Plan",
                "brief": "Define the change plan before implementation or experiment execution.",
                "step_output_fields": ["change_plan", "constraints", "expected_signal"],
                "exit_criteria": ["change plan is executable", "expected signal is explicit"],
                "artifact_slot": "research.scenario.idea_loop.plan_lock",
            },
            "iterate": {
                "title": "Iterate Change",
                "brief": "Execute the iteration by implementing, searching, or restructuring the idea.",
                "step_output_fields": ["implementation_notes", "artifacts", "observed_delta"],
                "exit_criteria": ["iteration result is recorded", "artifacts are linked"],
                "artifact_slot": "research.scenario.idea_loop.iterate",
            },
            "final_verify": {
                "title": "Verify Result",
                "brief": "Verify whether the iteration improved the target or clarified the failure mode.",
                "step_output_fields": ["verification_result", "metric_delta", "decision_reason"],
                "exit_criteria": ["result is judged", "next decision is explicit"],
                "artifact_slot": "research.scenario.idea_loop.final_verify",
            },
            "archive": {
                "title": "Archive Iteration",
                "brief": "Archive the iteration result and frame the next iteration boundary.",
                "step_output_fields": ["experiment_archive", "next_iteration", "lessons"],
                "exit_criteria": ["archive is ready", "next iteration is framed"],
                "artifact_slot": "research.scenario.idea_loop.archive",
            },
            "recover": {
                "title": "Recover Iteration",
                "brief": "Recover from an invalid or weak iteration by reframing the next attempt.",
                "step_output_fields": ["failure_mode", "recovery_plan", "next_iteration"],
                "exit_criteria": ["recovery plan exists", "retry scope is explicit"],
                "artifact_slot": "research.scenario.idea_loop.recover",
            },
        },
    },
}

_ACTIONS = {"prepare", "advance", "resume", "recover"}
_DECISIONS = {"proceed", "refine", "retry", "accept"}


@dataclass(slots=True)
class ScenarioDispatchBundle:
    scenario: dict[str, Any] = field(default_factory=dict)
    workflow_projection: dict[str, Any] = field(default_factory=dict)
    workflow_cursor: dict[str, Any] = field(default_factory=dict)
    active_step: dict[str, Any] = field(default_factory=dict)
    step_receipt: dict[str, Any] = field(default_factory=dict)
    handoff_receipt: dict[str, Any] = field(default_factory=dict)
    decision_receipt: dict[str, Any] = field(default_factory=dict)
    output_template: dict[str, Any] = field(default_factory=dict)
    entry_contract: dict[str, Any] = field(default_factory=dict)
    exit_contract: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_scenario_dispatch(invocation: ResearchInvocation, unit: ResearchUnitSpec) -> dict[str, Any]:
    scenario = get_research_scenario(unit.unit_id)
    spec = load_workflow_spec(unit.unit_id)
    if scenario is None or spec is None:
        return {}
    scenario_def = _SCENARIO_DEFS.get(scenario.scenario_id)
    if not isinstance(scenario_def, dict):
        return {}

    steps_by_id = {step.step_id: step for step in spec.steps}
    step_ids = [step.step_id for step in spec.steps]
    if not step_ids:
        return {}

    action = _normalize_action(invocation.metadata.get("scenario_action"))
    decision = _normalize_decision(invocation.metadata.get("decision"))
    provided_cursor = _extract_mapping(invocation.metadata.get("workflow_cursor")) or _extract_mapping(invocation.payload.get("workflow_cursor"))
    requested_step_id = str((provided_cursor or {}).get("current_step_id") or "").strip()
    current_step_id = requested_step_id if requested_step_id in steps_by_id else step_ids[0]
    previous_step_id = current_step_id
    active_step_id = _resolve_active_step(
        scenario_id=scenario.scenario_id,
        step_ids=step_ids,
        current_step_id=current_step_id,
        action=action,
        decision=decision,
    )
    next_step_id = _resolve_next_step_id(
        scenario_id=scenario.scenario_id,
        step_ids=step_ids,
        active_step_id=active_step_id,
        decision=decision,
    )

    step_spec = steps_by_id[active_step_id]
    step_def = dict((scenario_def.get("steps") or {}).get(active_step_id) or {})
    exit_contract = dict(scenario_def.get("exit_contract") or {})
    active_step = {
        "step_id": step_spec.step_id,
        "step_kind": step_spec.step_kind,
        "process_role": step_spec.process_role,
        "title": str(step_def.get("title") or step_spec.step_id.replace("_", " ").title()).strip(),
        "brief": str(step_def.get("brief") or "").strip(),
        "step_output_fields": [str(item).strip() for item in step_def.get("step_output_fields") or [] if str(item).strip()],
        "exit_criteria": [str(item).strip() for item in step_def.get("exit_criteria") or [] if str(item).strip()],
        "artifact_slot": str(step_def.get("artifact_slot") or "").strip(),
        "next_step_id": next_step_id,
    }
    output_template = {
        "template_id": f"{scenario.scenario_id}.{active_step_id}",
        "output_format": str(exit_contract.get("output_format") or "").strip(),
        "required_fields": [str(item).strip() for item in exit_contract.get("required_fields") or [] if str(item).strip()],
        "step_output_fields": list(active_step["step_output_fields"]),
        "artifact_slot": active_step["artifact_slot"] or str(exit_contract.get("artifact_slot") or "").strip(),
        "skeleton": {
            field_name: ""
            for field_name in [str(item).strip() for item in exit_contract.get("required_fields") or [] if str(item).strip()]
        },
    }
    next_action = _build_next_action(active_step, next_step_id=next_step_id, decision=decision)
    cursor = WorkflowCursor(
        workflow_id=spec.workflow_id,
        current_step_id=active_step_id,
        status="pending",
        latest_decision=decision,
        resume_from=active_step_id,
        metadata={
            "scenario_id": scenario.scenario_id,
            "entrypoint": invocation.entrypoint,
            "scenario_action": action,
            "previous_step_id": previous_step_id,
        },
    )
    step_receipt = StepReceipt(
        step_id=active_step_id,
        workflow_id=spec.workflow_id,
        worker_name=f"research_manager:{scenario.scenario_id}",
        process_role=step_spec.process_role,
        step_kind=step_spec.step_kind,
        status="pending",
        summary=active_step["brief"],
        evidence=[
            f"entrypoint={invocation.entrypoint}",
            f"scenario_action={action}",
            f"unit_id={unit.unit_id}",
        ],
        next_action=next_action,
        metadata={
            "title": active_step["title"],
            "artifact_slot": active_step["artifact_slot"],
            "step_output_fields": list(active_step["step_output_fields"]),
        },
    )
    handoff_receipt = HandoffReceipt(
        workflow_id=spec.workflow_id,
        source_step_id=active_step_id,
        target_step_id=next_step_id,
        producer=step_spec.process_role,
        consumer=steps_by_id[next_step_id].process_role if next_step_id and next_step_id in steps_by_id else "manager",
        handoff_kind="scenario_step",
        status="pending",
        summary=_build_handoff_summary(active_step_id, next_step_id=next_step_id),
        payload={
            "step_output_fields": list(active_step["step_output_fields"]),
            "required_fields": list(output_template["required_fields"]),
        },
        handoff_ready=False,
        next_action=next_action,
        metadata={"scenario_id": scenario.scenario_id},
    )
    decision_receipt = DecisionReceipt(
        workflow_id=spec.workflow_id,
        step_id=active_step_id,
        producer="research_manager",
        status="pending",
        summary=_build_decision_summary(action=action, decision=decision, next_step_id=next_step_id),
        decision=decision,
        decision_reason=f"scenario_action={action}",
        retryable=decision in {"retry", "refine"},
        next_action=next_action,
        resume_from=next_step_id or active_step_id,
        metadata={"scenario_id": scenario.scenario_id},
    )
    projection = WorkflowRunProjection(
        spec=spec,
        cursor=cursor,
        step_receipts=[step_receipt],
        handoff_receipts=[handoff_receipt] if handoff_receipt.target_step_id else [],
        decision_receipts=[decision_receipt],
        metadata={
            "scenario_id": scenario.scenario_id,
            "entrypoint": invocation.entrypoint,
            "scenario_action": action,
        },
    )
    bundle = ScenarioDispatchBundle(
        scenario=scenario.to_dict(),
        workflow_projection=projection.to_dict(),
        workflow_cursor=cursor.to_dict(),
        active_step=active_step,
        step_receipt=step_receipt.to_dict(),
        handoff_receipt=handoff_receipt.to_dict(),
        decision_receipt=decision_receipt.to_dict(),
        output_template=output_template,
        entry_contract=dict(scenario_def.get("entry_contract") or {}),
        exit_contract=exit_contract,
        metadata={
            "scenario_action": action,
            "decision": decision,
            "previous_step_id": previous_step_id,
            "next_step_id": next_step_id,
        },
    )
    return bundle.to_dict()


def _extract_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _normalize_action(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in _ACTIONS else "prepare"


def _normalize_decision(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in _DECISIONS else "proceed"


def _resolve_active_step(
    *,
    scenario_id: str,
    step_ids: list[str],
    current_step_id: str,
    action: str,
    decision: str,
) -> str:
    if action == "resume":
        return current_step_id
    if action == "recover":
        return "recover" if scenario_id == "idea_loop" and "recover" in step_ids else current_step_id
    if action != "advance":
        return current_step_id
    if scenario_id == "idea_loop" and current_step_id == "final_verify" and decision in {"retry", "refine"} and "recover" in step_ids:
        return "recover"
    try:
        index = step_ids.index(current_step_id)
    except ValueError:
        return step_ids[0]
    if index + 1 < len(step_ids):
        return step_ids[index + 1]
    return current_step_id


def _resolve_next_step_id(
    *,
    scenario_id: str,
    step_ids: list[str],
    active_step_id: str,
    decision: str,
) -> str:
    if scenario_id == "idea_loop" and active_step_id == "final_verify" and decision in {"retry", "refine"} and "recover" in step_ids:
        return "recover"
    try:
        index = step_ids.index(active_step_id)
    except ValueError:
        return ""
    if index + 1 < len(step_ids):
        return step_ids[index + 1]
    return ""


def _build_next_action(active_step: Mapping[str, Any], *, next_step_id: str, decision: str) -> str:
    title = str(active_step.get("title") or active_step.get("step_id") or "current step").strip()
    if decision in {"retry", "refine"}:
        if next_step_id:
            return f"finish {title} and prepare recovery handoff to {next_step_id}"
        return f"refine {title} output before proceeding"
    if next_step_id:
        return f"finish {title} and hand off to {next_step_id}"
    return f"finish {title} and close the scenario output contract"


def _build_handoff_summary(active_step_id: str, *, next_step_id: str) -> str:
    if next_step_id:
        return f"handoff from {active_step_id} to {next_step_id}"
    return f"{active_step_id} is terminal and should close the scenario output"


def _build_decision_summary(*, action: str, decision: str, next_step_id: str) -> str:
    if next_step_id:
        return f"scenario action={action}, decision={decision}, next step={next_step_id}"
    return f"scenario action={action}, decision={decision}, terminal step"
