from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


def _as_dict(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, Mapping) else {}


def _as_text_list(payload: Any) -> list[str]:
    if not isinstance(payload, (list, tuple, set)):
        return []
    items: list[str] = []
    for item in payload:
        text = str(item or "").strip()
        if text:
            items.append(text)
    return items


def _text(value: Any, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


@dataclass(slots=True)
class FrameworkCatalogEntry:
    framework_id: str
    display_name: str
    source_kind: str
    focus_layers: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)
    status: str = "active"
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.framework_id = _text(self.framework_id)
        self.display_name = _text(self.display_name)
        self.source_kind = _text(self.source_kind)
        self.focus_layers = _as_text_list(self.focus_layers)
        self.strengths = _as_text_list(self.strengths)
        self.non_goals = _as_text_list(self.non_goals)
        self.status = _text(self.status, default="active")
        self.summary = _text(self.summary)
        self.metadata = _as_dict(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "framework_id": self.framework_id,
            "display_name": self.display_name,
            "source_kind": self.source_kind,
            "focus_layers": list(self.focus_layers),
            "strengths": list(self.strengths),
            "non_goals": list(self.non_goals),
            "status": self.status,
            "summary": self.summary,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "FrameworkCatalogEntry":
        if not isinstance(payload, Mapping):
            raise TypeError("framework catalog entry payload must be a mapping")
        raw = dict(payload)
        return cls(
            framework_id=_text(raw.get("framework_id")),
            display_name=_text(raw.get("display_name")),
            source_kind=_text(raw.get("source_kind")),
            focus_layers=raw.get("focus_layers"),
            strengths=raw.get("strengths"),
            non_goals=raw.get("non_goals"),
            status=_text(raw.get("status"), default="active"),
            summary=_text(raw.get("summary")),
            metadata=_as_dict(raw.get("metadata")),
        )


@dataclass(slots=True)
class FrameworkCatalog:
    entries: list[FrameworkCatalogEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        normalized: list[FrameworkCatalogEntry] = []
        for item in self.entries:
            if isinstance(item, FrameworkCatalogEntry):
                normalized.append(item)
            elif isinstance(item, Mapping):
                normalized.append(FrameworkCatalogEntry.from_dict(item))
            else:
                raise TypeError("framework catalog entries must be FrameworkCatalogEntry or mapping")
        self.entries = normalized

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [item.to_dict() for item in self.entries]}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "FrameworkCatalog":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(entries=list(payload.get("entries") or []))

    def list_framework_ids(self) -> list[str]:
        return [item.framework_id for item in self.entries]

    def list_entries(self) -> list[FrameworkCatalogEntry]:
        return list(self.entries)

    def get_entry(self, framework_id: str) -> FrameworkCatalogEntry | None:
        target = _text(framework_id)
        if not target:
            return None
        for item in self.entries:
            if item.framework_id == target:
                return item
        return None

    def require_entry(self, framework_id: str) -> FrameworkCatalogEntry:
        entry = self.get_entry(framework_id)
        if entry is None:
            raise KeyError(f"framework catalog entry not found: {framework_id}")
        return entry

    def find_by_source_kind(self, source_kind: str) -> list[FrameworkCatalogEntry]:
        target = _text(source_kind)
        if not target:
            return []
        return [item for item in self.entries if item.source_kind == target]

    def find_by_focus_layer(self, focus_layer: str) -> list[FrameworkCatalogEntry]:
        target = _text(focus_layer)
        if not target:
            return []
        return [item for item in self.entries if target in item.focus_layers]


_BUILTIN_FRAMEWORK_CATALOG_DATA: list[dict[str, Any]] = [
    {
        "framework_id": "superpowers",
        "display_name": "Superpowers",
        "source_kind": "software_factory_methodology",
        "focus_layers": [
            "Package / Framework Definition Plane",
            "Workflow Compile Plane",
            "Governance / Observability Plane",
        ],
        "strengths": [
            "spec-first and plan-first engineering discipline",
            "hard review and approval gates",
            "task-scoped worker handoff discipline",
        ],
        "non_goals": [
            "copy slash-command UX",
            "copy host-specific prompt style",
            "treat role names as Butler runtime objects",
        ],
        "summary": "Superpowers is valuable to Butler as a governance-heavy software factory method, not as a product shell.",
        "metadata": {
            "primary_absorption": [
                "governance_policy",
                "compiler_profile_template",
                "workflow_package",
            ],
        },
    },
    {
        "framework_id": "gstack",
        "display_name": "gstack",
        "source_kind": "software_factory_flow",
        "focus_layers": [
            "Mission / Control Plane",
            "Workflow Compile Plane",
            "Governance / Observability Plane",
        ],
        "strengths": [
            "explicit engineering cadence from think to reflect",
            "upstream-downstream artifact discipline",
            "review-test-ship stages as first-class flow steps",
        ],
        "non_goals": [
            "copy browser daemon assumptions",
            "bind Butler to shell-command workflow UX",
            "treat skill host conventions as Butler core runtime",
        ],
        "summary": "gstack is a workflow cadence reference for software factory compilation, not a host protocol to clone.",
        "metadata": {
            "primary_absorption": [
                "workflow_package",
                "artifact_contract",
                "verification_policy",
            ],
        },
    },
    {
        "framework_id": "openfang",
        "display_name": "OpenFang",
        "source_kind": "agent_os",
        "focus_layers": [
            "Package / Framework Definition Plane",
            "Execution Kernel Plane",
            "Governance / Observability Plane",
        ],
        "strengths": [
            "runtime-first agent operating system perspective",
            "autonomous capability package mindset",
            "scheduler, supervisor, safety and audit as first-class subsystems",
        ],
        "non_goals": [
            "copy product shell or desktop UI",
            "turn Butler orchestrator into a chat super-agent",
            "rename Butler packages directly into OpenFang hands",
        ],
        "summary": "OpenFang informs Butler capability packages and governance defaults; it should not be copied as a product shell.",
        "metadata": {
            "primary_absorption": [
                "capability_package",
                "governance_policy_package",
                "runtime_binding_hint",
            ],
        },
    },
    {
        "framework_id": "langgraph",
        "display_name": "LangGraph",
        "source_kind": "workflow_runtime",
        "focus_layers": [
            "Workflow Compile Plane",
            "Execution Kernel Plane",
            "Governance / Observability Plane",
        ],
        "strengths": [
            "graph execution semantics with pause and resume",
            "durable state and human-in-the-loop checkpoints",
            "loops, branching and recovery as first-class runtime concerns",
        ],
        "non_goals": [
            "copy graph DSL syntax",
            "bind Butler to LangChain-specific stack assumptions",
        ],
        "summary": "LangGraph is a workflow runtime reference for Butler execution semantics, not a graph syntax to clone.",
        "metadata": {
            "primary_absorption": [
                "workflow_vm",
                "recovery_policy",
                "approval_gate",
            ],
        },
    },
    {
        "framework_id": "openai_agents_sdk",
        "display_name": "OpenAI Agents SDK",
        "source_kind": "agent_sdk",
        "focus_layers": [
            "Execution Kernel Plane",
            "Collaboration State Plane",
            "Governance / Observability Plane",
        ],
        "strengths": [
            "handoffs as first-class control objects",
            "guardrails and tracing as built-in concepts",
            "clean agent runtime surface instead of product shell coupling",
        ],
        "non_goals": [
            "copy SDK API surface verbatim",
            "bind Butler to one provider-specific abstraction",
        ],
        "summary": "OpenAI Agents SDK is a modeling reference for handoff, guardrail and tracing objects inside Butler.",
        "metadata": {
            "primary_absorption": [
                "handoff_contract",
                "governance_policy",
                "trace_contract",
            ],
        },
    },
    {
        "framework_id": "autogen",
        "display_name": "AutoGen",
        "source_kind": "multi_agent_framework",
        "focus_layers": [
            "Package / Framework Definition Plane",
            "Execution Kernel Plane",
            "Collaboration State Plane",
        ],
        "strengths": [
            "layered core and higher-level API split",
            "event-driven multi-agent collaboration patterns",
            "extension-friendly runtime boundaries",
        ],
        "non_goals": [
            "copy group-chat centric UX as Butler default",
            "collapse Butler layers into one chat abstraction",
        ],
        "summary": "AutoGen is useful to Butler as a layering and extension reference, not as a default group-chat product model.",
        "metadata": {
            "primary_absorption": [
                "collaboration_contract",
                "runtime_extension_boundary",
                "agent_runtime_layering",
            ],
        },
    },
    {
        "framework_id": "crewai",
        "display_name": "CrewAI",
        "source_kind": "multi_agent_framework",
        "focus_layers": [
            "Package / Framework Definition Plane",
            "Workflow Compile Plane",
            "Collaboration State Plane",
        ],
        "strengths": [
            "crew vs flow split",
            "delegation-friendly collaboration abstractions",
            "clear separation between autonomy and precise flow control",
        ],
        "non_goals": [
            "copy crew-specific terminology into Butler core",
            "stop at role-playing without contracts",
        ],
        "summary": "CrewAI is a reference for separating autonomy-oriented teams from flow-oriented control in Butler.",
        "metadata": {
            "primary_absorption": [
                "team_package",
                "workflow_package",
                "collaboration_contract",
            ],
        },
    },
    {
        "framework_id": "metagpt",
        "display_name": "MetaGPT",
        "source_kind": "multi_agent_company_framework",
        "focus_layers": [
            "Package / Framework Definition Plane",
            "Workflow Compile Plane",
            "Collaboration State Plane",
        ],
        "strengths": [
            "SOP-first role protocols",
            "explicit input-output expectations between roles",
            "software-company process modeling",
        ],
        "non_goals": [
            "turn Butler into a role museum",
            "copy company-role naming as runtime truth",
        ],
        "summary": "MetaGPT is a SOP and protocol reference for Butler workflow packages, not a role catalog to imitate.",
        "metadata": {
            "primary_absorption": [
                "workflow_package",
                "artifact_contract",
                "handoff_contract",
            ],
        },
    },
    {
        "framework_id": "openhands",
        "display_name": "OpenHands",
        "source_kind": "agentic_software_platform",
        "focus_layers": [
            "Mission / Control Plane",
            "Execution Kernel Plane",
            "Package / Framework Definition Plane",
        ],
        "strengths": [
            "sdk-cli-gui-cloud layering discipline",
            "software-task platform orientation",
            "separation between runtime core and entry surfaces",
        ],
        "non_goals": [
            "copy product shell or GUI",
            "bind Butler roadmap to one interface surface",
        ],
        "summary": "OpenHands is a reference for entry-surface separation and software-task packaging, not a UI shell to reproduce.",
        "metadata": {
            "primary_absorption": [
                "entry_surface_boundary",
                "workflow_package",
                "runtime_binding_hint",
            ],
        },
    },
    {
        "framework_id": "temporal",
        "display_name": "Temporal",
        "source_kind": "durable_execution_runtime",
        "focus_layers": [
            "Execution Kernel Plane",
            "Governance / Observability Plane",
        ],
        "strengths": [
            "durable execution discipline",
            "deterministic replay and retry semantics",
            "workflow recovery as infrastructure instead of best effort",
        ],
        "non_goals": [
            "copy backend infra stack wholesale",
            "force Butler to depend on Temporal server concepts",
        ],
        "summary": "Temporal is a durable-execution reference for Butler recovery and replay semantics, not a product layer.",
        "metadata": {
            "primary_absorption": [
                "recovery_policy",
                "checkpoint_contract",
                "deterministic_runtime_rule",
            ],
        },
    },
]


def load_builtin_framework_catalog() -> FrameworkCatalog:
    return FrameworkCatalog(entries=[FrameworkCatalogEntry.from_dict(item) for item in _BUILTIN_FRAMEWORK_CATALOG_DATA])


def get_builtin_framework_catalog_entry(framework_id: str) -> FrameworkCatalogEntry | None:
    return load_builtin_framework_catalog().get_entry(framework_id)
