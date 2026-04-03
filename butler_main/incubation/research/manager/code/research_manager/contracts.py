from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from butler_main.agents_os.runtime import AcceptanceReceipt
from butler_main.repo_layout import INCUBATION_RESEARCH_REL


RESEARCH_ENTRYPOINTS: tuple[str, ...] = (
    "orchestrator",
    "talk",
    "codex",
)


def normalize_entrypoint(value: str, *, default: str = "codex") -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in RESEARCH_ENTRYPOINTS:
        return normalized
    return default


def normalize_unit_id(value: str) -> str:
    normalized = str(value or "").strip().lower().replace("\\", "/")
    normalized = normalized.replace("-", "_").replace("/", ".")
    while ".." in normalized:
        normalized = normalized.replace("..", ".")
    return normalized.strip(".")


@dataclass(slots=True)
class ResearchUnitSpec:
    unit_id: str
    group: str
    description: str
    unit_root: str = ""
    handler_name: str = ""
    default_entrypoints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.unit_id = normalize_unit_id(self.unit_id)
        self.group = str(self.group or "").strip().lower().replace("-", "_")
        self.unit_root = str(self.unit_root or "").strip().replace("\\", "/")
        self.handler_name = str(self.handler_name or "").strip()
        self.default_entrypoints = tuple(normalize_entrypoint(item) for item in self.default_entrypoints if str(item or "").strip())


def _research_unit_root(*parts: str) -> str:
    return str((INCUBATION_RESEARCH_REL / "units" / Path(*parts)).as_posix())


RESEARCH_UNITS: dict[str, ResearchUnitSpec] = {
    spec.unit_id: spec
    for spec in (
        ResearchUnitSpec(
            unit_id="research_idea.idea_loop",
            group="research_idea",
            description="Research idea iteration and method refinement loop.",
            unit_root=_research_unit_root("research_idea", "idea_loop"),
            handler_name="handle_research_idea_loop",
        ),
        ResearchUnitSpec(
            unit_id="paper_manager.project_next_step_planning",
            group="paper_manager",
            description="Plan the next concrete step for an active research project.",
            unit_root=_research_unit_root("paper_manager", "project_next_step_planning"),
            handler_name="handle_project_next_step_planning",
            default_entrypoints=("talk",),
        ),
        ResearchUnitSpec(
            unit_id="paper_manager.progress_summary",
            group="paper_manager",
            description="Summarize research progress for user-facing updates.",
            unit_root=_research_unit_root("paper_manager", "progress_summary"),
            handler_name="handle_progress_summary",
        ),
        ResearchUnitSpec(
            unit_id="paper_finding.daily_paper_discovery",
            group="paper_finding",
            description="Discover and triage daily paper candidates.",
            unit_root=_research_unit_root("paper_finding", "daily_paper_discovery"),
            handler_name="handle_daily_paper_discovery",
            default_entrypoints=("orchestrator",),
        ),
    )
}


@dataclass(slots=True)
class ResearchInvocation:
    entrypoint: str
    goal: str = ""
    unit_id: str = ""
    session_id: str = ""
    task_id: str = ""
    workspace: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.entrypoint = normalize_entrypoint(self.entrypoint)
        self.unit_id = normalize_unit_id(self.unit_id)
        self.goal = str(self.goal or "").strip()
        if not isinstance(self.payload, dict):
            self.payload = {"value": self.payload}
        if not isinstance(self.metadata, dict):
            self.metadata = {"value": self.metadata}


@dataclass(slots=True)
class ResearchResult:
    status: str
    entrypoint: str
    unit_id: str
    summary: str
    acceptance: AcceptanceReceipt
    route: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.entrypoint = normalize_entrypoint(self.entrypoint)
        self.unit_id = normalize_unit_id(self.unit_id)
        self.status = str(self.status or "blocked").strip().lower() or "blocked"
        if not isinstance(self.route, dict):
            self.route = {"value": self.route}
        if not isinstance(self.payload, dict):
            self.payload = {"value": self.payload}


@dataclass(slots=True)
class ResearchUnitDispatch:
    summary: str
    evidence: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    next_action: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


ResearchUnitHandler = Callable[[ResearchInvocation, ResearchUnitSpec], ResearchUnitDispatch]
