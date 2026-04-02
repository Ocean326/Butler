from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

from runtime_os.process_runtime import WorkflowCursor, WorkflowRunProjection, WorkflowSpec


@dataclass(slots=True)
class ResearchScenarioSpec:
    scenario_id: str
    workflow_id: str
    scenario_root: str
    workflow_spec_path: str
    output_contract_path: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SCENARIO_BY_UNIT: dict[str, ResearchScenarioSpec] = {
    "paper_finding.daily_paper_discovery": ResearchScenarioSpec(
        scenario_id="paper_discovery",
        workflow_id="paper_discovery_round",
        scenario_root="butler_main/research/scenarios/paper_discovery",
        workflow_spec_path="butler_main/research/scenarios/paper_discovery/workflow/workflow.spec.json",
        output_contract_path="butler_main/research/scenarios/paper_discovery/outputs/README.md",
        metadata={"entrypoints": ["orchestrator", "talk", "codex"]},
    ),
    "paper_manager.project_next_step_planning": ResearchScenarioSpec(
        scenario_id="brainstorm",
        workflow_id="brainstorm_session",
        scenario_root="butler_main/research/scenarios/brainstorm",
        workflow_spec_path="butler_main/research/scenarios/brainstorm/workflow/workflow.spec.json",
        output_contract_path="butler_main/research/scenarios/brainstorm/outputs/README.md",
        metadata={"entrypoints": ["talk", "codex"]},
    ),
    "paper_manager.progress_summary": ResearchScenarioSpec(
        scenario_id="brainstorm",
        workflow_id="brainstorm_session",
        scenario_root="butler_main/research/scenarios/brainstorm",
        workflow_spec_path="butler_main/research/scenarios/brainstorm/workflow/workflow.spec.json",
        output_contract_path="butler_main/research/scenarios/brainstorm/outputs/README.md",
        metadata={"entrypoints": ["talk", "codex"]},
    ),
    "research_idea.idea_loop": ResearchScenarioSpec(
        scenario_id="idea_loop",
        workflow_id="idea_loop_round",
        scenario_root="butler_main/research/scenarios/idea_loop",
        workflow_spec_path="butler_main/research/scenarios/idea_loop/workflow/workflow.spec.json",
        output_contract_path="butler_main/research/scenarios/idea_loop/outputs/README.md",
        metadata={"entrypoints": ["orchestrator", "talk", "codex"]},
    ),
}


_REPO_ROOT = Path(__file__).resolve().parents[6]


def _resolve_repo_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (_REPO_ROOT / candidate).resolve()


def get_research_scenario(unit_id: str) -> ResearchScenarioSpec | None:
    return SCENARIO_BY_UNIT.get(str(unit_id or "").strip())


def load_workflow_spec(unit_id: str) -> WorkflowSpec | None:
    scenario = get_research_scenario(unit_id)
    if scenario is None:
        return None
    workflow_path = _resolve_repo_path(scenario.workflow_spec_path)
    if not workflow_path.exists():
        return None
    try:
        return WorkflowSpec.from_dict(json.loads(workflow_path.read_text(encoding="utf-8")))
    except Exception:
        return None


def load_workflow_projection(unit_id: str) -> dict[str, Any]:
    scenario = get_research_scenario(unit_id)
    spec = load_workflow_spec(unit_id)
    if scenario is None or spec is None:
        return {}
    cursor = WorkflowCursor(
        workflow_id=scenario.workflow_id,
        current_step_id=spec.steps[0].step_id if spec.steps else "",
        status="pending",
    )
    projection = WorkflowRunProjection(spec=spec, cursor=cursor, metadata={"scenario_id": scenario.scenario_id})
    return projection.to_dict()
