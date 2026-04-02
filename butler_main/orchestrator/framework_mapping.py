from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .framework_catalog import (
    FrameworkCatalog,
    FrameworkCatalogEntry,
    get_builtin_framework_catalog_entry,
    load_builtin_framework_catalog,
)


def _as_dict(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, Mapping) else {}


def _as_list_of_dicts(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    items: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, Mapping):
            items.append(dict(item))
    return items


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
class FrameworkMappingSpec:
    framework_id: str
    source_terms: list[str] = field(default_factory=list)
    butler_targets: list[dict[str, Any]] = field(default_factory=list)
    absorbed_packages: list[dict[str, Any]] = field(default_factory=list)
    governance_defaults: dict[str, Any] = field(default_factory=dict)
    runtime_binding_hints: dict[str, Any] = field(default_factory=dict)
    compiler_profile_templates: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.framework_id = _text(self.framework_id)
        self.source_terms = _as_text_list(self.source_terms)
        self.butler_targets = _as_list_of_dicts(self.butler_targets)
        self.absorbed_packages = _as_list_of_dicts(self.absorbed_packages)
        self.governance_defaults = _as_dict(self.governance_defaults)
        self.runtime_binding_hints = _as_dict(self.runtime_binding_hints)
        self.compiler_profile_templates = _as_list_of_dicts(self.compiler_profile_templates)
        self.metadata = _as_dict(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "framework_id": self.framework_id,
            "source_terms": list(self.source_terms),
            "butler_targets": [dict(item) for item in self.butler_targets],
            "absorbed_packages": [dict(item) for item in self.absorbed_packages],
            "governance_defaults": dict(self.governance_defaults),
            "runtime_binding_hints": dict(self.runtime_binding_hints),
            "compiler_profile_templates": [dict(item) for item in self.compiler_profile_templates],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "FrameworkMappingSpec":
        if not isinstance(payload, Mapping):
            raise TypeError("framework mapping spec payload must be a mapping")
        raw = dict(payload)
        return cls(
            framework_id=_text(raw.get("framework_id")),
            source_terms=raw.get("source_terms"),
            butler_targets=raw.get("butler_targets"),
            absorbed_packages=raw.get("absorbed_packages"),
            governance_defaults=raw.get("governance_defaults"),
            runtime_binding_hints=raw.get("runtime_binding_hints"),
            compiler_profile_templates=raw.get("compiler_profile_templates"),
            metadata=raw.get("metadata"),
        )


@dataclass(slots=True)
class FrameworkMappingRegistry:
    specs: list[FrameworkMappingSpec] = field(default_factory=list)

    def __post_init__(self) -> None:
        normalized: list[FrameworkMappingSpec] = []
        for item in self.specs:
            if isinstance(item, FrameworkMappingSpec):
                normalized.append(item)
            elif isinstance(item, Mapping):
                normalized.append(FrameworkMappingSpec.from_dict(item))
            else:
                raise TypeError("framework mapping specs must be FrameworkMappingSpec or mapping")
        self.specs = normalized

    def to_dict(self) -> dict[str, Any]:
        return {"specs": [item.to_dict() for item in self.specs]}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "FrameworkMappingRegistry":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(specs=list(payload.get("specs") or []))

    def get_spec(self, framework_id: str) -> FrameworkMappingSpec | None:
        target = _text(framework_id)
        if not target:
            return None
        for item in self.specs:
            if item.framework_id == target:
                return item
        return None

    def list_framework_ids(self) -> list[str]:
        return [item.framework_id for item in self.specs]

    def require_spec(self, framework_id: str) -> FrameworkMappingSpec:
        spec = self.get_spec(framework_id)
        if spec is None:
            raise KeyError(f"framework mapping spec not found: {framework_id}")
        return spec

    def find_specs_for_butler_layer(self, butler_layer: str) -> list[FrameworkMappingSpec]:
        target = _text(butler_layer)
        if not target:
            return []
        matches: list[FrameworkMappingSpec] = []
        for spec in self.specs:
            if any(_text(item.get("butler_layer")) == target for item in spec.butler_targets):
                matches.append(spec)
        return matches

    def find_specs_for_target_kind(self, target_kind: str) -> list[FrameworkMappingSpec]:
        target = _text(target_kind)
        if not target:
            return []
        matches: list[FrameworkMappingSpec] = []
        for spec in self.specs:
            if any(_text(item.get("target_kind")) == target for item in spec.butler_targets):
                matches.append(spec)
        return matches

    def compiler_profile_templates_for(self, framework_id: str) -> list[dict[str, Any]]:
        return [dict(item) for item in self.require_spec(framework_id).compiler_profile_templates]

    def governance_defaults_for(self, framework_id: str) -> dict[str, Any]:
        return dict(self.require_spec(framework_id).governance_defaults)

    def runtime_binding_hints_for(self, framework_id: str) -> dict[str, Any]:
        return dict(self.require_spec(framework_id).runtime_binding_hints)


@dataclass(slots=True, frozen=True)
class FrameworkMappingBundle:
    entry: FrameworkCatalogEntry
    mapping: FrameworkMappingSpec

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry": self.entry.to_dict(),
            "mapping": self.mapping.to_dict(),
        }

    def compiler_inputs(self) -> dict[str, Any]:
        return {
            "framework_id": self.entry.framework_id,
            "source_kind": self.entry.source_kind,
            "focus_layers": list(self.entry.focus_layers),
            "butler_targets": [dict(item) for item in self.mapping.butler_targets],
            "absorbed_packages": [dict(item) for item in self.mapping.absorbed_packages],
            "governance_defaults": dict(self.mapping.governance_defaults),
            "runtime_binding_hints": dict(self.mapping.runtime_binding_hints),
            "compiler_profile_templates": [dict(item) for item in self.mapping.compiler_profile_templates],
        }


_BUILTIN_FRAMEWORK_MAPPING_DATA: list[dict[str, Any]] = [
    {
        "framework_id": "superpowers",
        "source_terms": [
            "spec-first",
            "plan-first",
            "tdd",
            "review-before-merge",
            "subagent-driven-development",
        ],
        "butler_targets": [
            {
                "source_concept": "hard gate",
                "butler_layer": "Governance / Observability Plane",
                "target_kind": "governance_policy",
                "adopt": [
                    "spec review gate before implementation",
                    "plan approval gate before execution",
                    "review verdict as a first-class workflow stop point",
                ],
                "do_not_copy": [
                    "slash-command UX",
                    "framework-specific prompt tone",
                ],
                "policy_refs": [
                    "policy.dev.spec_review",
                    "policy.dev.plan_approval",
                    "policy.dev.code_review",
                ],
            },
            {
                "source_concept": "fresh subagent per task",
                "butler_layer": "Workflow Compile Plane",
                "target_kind": "compiler_profile_template",
                "adopt": [
                    "task-scoped runtime binding",
                    "explicit review workflow package",
                ],
                "do_not_copy": [
                    "fixed role theater",
                ],
                "runtime_binding": {
                    "dispatch_mode": "fresh_worker_per_task",
                    "worker_profile": "implementation_lane",
                },
            },
        ],
        "absorbed_packages": [
            {
                "package_kind": "governance_policy_package",
                "package_ref": "policy.dev.spec_review",
                "purpose": "Enforce spec and plan review gates before implementation.",
            },
            {
                "package_kind": "workflow_package",
                "package_ref": "workflow.dev.reviewed_implementation",
                "purpose": "Compile implementation flows with mandatory review phases.",
            },
        ],
        "governance_defaults": {
            "verification": {"kind": "judge", "mode": "required"},
            "approval": {"kind": "human_gate", "required": True},
            "recovery": {"kind": "retry", "max_attempts": 1},
        },
        "runtime_binding_hints": {
            "preferred_runtime_keys": ["codex", "default"],
            "worker_profiles": ["spec_reviewer", "implementation_lane"],
            "dispatch_pattern": "fresh_worker_per_task",
        },
        "compiler_profile_templates": [
            {
                "template_id": "framework.superpowers.reviewed_implementation",
                "workflow_kind": "implementation_governed",
                "capability_package_ref": "pkg.cap.reviewed_implementation",
                "governance_policy_ref": "policy.dev.spec_review",
                "runtime_binding": {"worker_profile": "implementation_lane"},
                "input_contract": {"required": ["task_spec", "implementation_plan"]},
                "output_contract": {"required": ["implementation_patch", "review_verdict"]},
            }
        ],
        "metadata": {
            "lane_a_note": "Superpowers is absorbed as governance and compilation discipline, not as a Butler product interface.",
        },
    },
    {
        "framework_id": "gstack",
        "source_terms": [
            "think-plan-build-review-test-ship-reflect",
            "software factory cadence",
            "artifact handoff discipline",
        ],
        "butler_targets": [
            {
                "source_concept": "engineering cadence",
                "butler_layer": "Workflow Compile Plane",
                "target_kind": "workflow_package",
                "adopt": [
                    "explicit staged flow from planning to reflection",
                    "artifact-producing step boundaries",
                    "review-test-ship phases as compile-time structure",
                ],
                "do_not_copy": [
                    "browser daemon assumptions",
                    "host command protocol",
                ],
                "contract_refs": [
                    "contract.dev.plan_input",
                    "contract.dev.qa_report",
                ],
            },
            {
                "source_concept": "upstream-downstream consumption",
                "butler_layer": "Mission / Control Plane",
                "target_kind": "package_selection_policy",
                "adopt": [
                    "artifact handoff between phases",
                    "control-plane awareness of review and ship milestones",
                ],
                "do_not_copy": [
                    "host-specific skill catalog shape",
                ],
            },
        ],
        "absorbed_packages": [
            {
                "package_kind": "workflow_package",
                "package_ref": "workflow.dev.software_factory",
                "purpose": "Structured delivery cadence from plan to ship.",
            },
            {
                "package_kind": "contract_package",
                "package_ref": "contract.dev.phase_handoff",
                "purpose": "Artifact and handoff contracts between factory phases.",
            },
        ],
        "governance_defaults": {
            "verification": {"kind": "judge", "mode": "required"},
            "approval": {"kind": "approval", "required": False},
            "recovery": {"kind": "retry_step", "max_attempts": 2},
        },
        "runtime_binding_hints": {
            "preferred_runtime_keys": ["codex", "default"],
            "worker_profiles": ["planner", "builder", "reviewer", "qa"],
            "handoff_mode": "artifact_first",
        },
        "compiler_profile_templates": [
            {
                "template_id": "framework.gstack.software_factory",
                "workflow_kind": "software_factory",
                "capability_package_ref": "pkg.cap.software_factory",
                "runtime_binding": {"worker_profile": "planner"},
                "input_contract": {"required": ["goal"]},
                "output_contract": {"required": ["qa_report", "release_note"]},
            }
        ],
        "metadata": {
            "lane_a_note": "gstack is absorbed as staged workflow cadence, not as Butler host UX.",
        },
    },
    {
        "framework_id": "openfang",
        "source_terms": [
            "agent operating system",
            "hands as autonomous capability packages",
            "scheduler supervisor background rbac metering trigger",
        ],
        "butler_targets": [
            {
                "source_concept": "autonomous capability package",
                "butler_layer": "Package / Framework Definition Plane",
                "target_kind": "capability_package",
                "adopt": [
                    "package-first capability definition",
                    "installable and governable autonomous capability bundles",
                    "capability/runtime separation",
                ],
                "do_not_copy": [
                    "hands naming as Butler core term",
                    "product shell or desktop packaging",
                ],
                "package_refs": [
                    "pkg.cap.autonomous.research",
                    "pkg.cap.autonomous.maintenance",
                ],
            },
            {
                "source_concept": "os-style governance and safety subsystems",
                "butler_layer": "Governance / Observability Plane",
                "target_kind": "governance_policy_package",
                "adopt": [
                    "approval and audit as first-class policy defaults",
                    "scheduler and supervisor aware runtime policy",
                    "security boundary reflected in policy objects",
                ],
                "do_not_copy": [
                    "copying UI shell layers",
                    "turning Butler orchestrator into an all-in-one super-agent",
                ],
                "policy_refs": [
                    "policy.autonomy.audit_required",
                    "policy.autonomy.supervised_dispatch",
                ],
            },
            {
                "source_concept": "runtime-first operating system view",
                "butler_layer": "Execution Kernel Plane",
                "target_kind": "runtime_binding",
                "adopt": [
                    "runtime binding hints separate from product entry",
                    "background execution and supervision awareness",
                ],
                "do_not_copy": [
                    "desktop/client shell replication",
                ],
                "runtime_binding": {
                    "host_kind": "background_runtime",
                    "requires_supervisor": True,
                    "policy_mode": "governed_autonomy",
                },
            },
        ],
        "absorbed_packages": [
            {
                "package_kind": "capability_package",
                "package_ref": "pkg.cap.autonomous.research",
                "purpose": "Autonomous package pattern for bounded but governable capability bundles.",
            },
            {
                "package_kind": "governance_policy_package",
                "package_ref": "policy.autonomy.audit_required",
                "purpose": "Approval, audit and supervisor defaults for autonomous execution.",
            },
        ],
        "governance_defaults": {
            "verification": {"kind": "judge", "mode": "required"},
            "approval": {"kind": "human_gate", "required": True},
            "recovery": {"kind": "repair", "max_attempts": 1},
            "policy_refs": ["policy.autonomy.audit_required", "policy.autonomy.supervised_dispatch"],
        },
        "runtime_binding_hints": {
            "preferred_runtime_keys": ["default", "codex"],
            "worker_profiles": ["autonomy_supervisor", "autonomous_capability"],
            "host_kind": "background_runtime",
            "requires_supervisor": True,
        },
        "compiler_profile_templates": [
            {
                "template_id": "framework.openfang.autonomous_capability",
                "workflow_kind": "autonomous_capability_governed",
                "capability_package_ref": "pkg.cap.autonomous.research",
                "governance_policy_ref": "policy.autonomy.audit_required",
                "runtime_binding": {
                    "worker_profile": "autonomous_capability",
                    "host_kind": "background_runtime",
                },
                "input_contract": {"required": ["mission_goal", "risk_budget"]},
                "output_contract": {"required": ["receipt", "audit_record"]},
            }
        ],
        "metadata": {
            "lane_a_note": "OpenFang is mapped to capability/governance/runtime inspiration only; no Butler product shell mapping is allowed.",
        },
    },
    {
        "framework_id": "langgraph",
        "source_terms": [
            "graph execution",
            "pause and resume",
            "human in the loop",
            "durable state",
        ],
        "butler_targets": [
            {
                "source_concept": "graph execution semantics",
                "butler_layer": "Execution Kernel Plane",
                "target_kind": "runtime_binding",
                "adopt": [
                    "step-edge execution semantics",
                    "pause and resume as execution concerns",
                    "branching and loop support in workflow runtime",
                ],
                "do_not_copy": [
                    "LangGraph-specific graph syntax",
                ],
                "runtime_binding": {
                    "supports_resume": True,
                    "supports_branching": True,
                },
            },
            {
                "source_concept": "human in the loop checkpoints",
                "butler_layer": "Governance / Observability Plane",
                "target_kind": "governance_policy",
                "adopt": [
                    "approval gate checkpoints",
                    "resume-aware verification transitions",
                ],
                "do_not_copy": [
                    "framework-specific checkpoint UX",
                ],
            },
        ],
        "absorbed_packages": [
            {
                "package_kind": "workflow_package",
                "package_ref": "workflow.runtime.graph_resume",
                "purpose": "Graph-oriented workflow package with pause/resume semantics.",
            },
            {
                "package_kind": "governance_policy_package",
                "package_ref": "policy.runtime.resume_gate",
                "purpose": "Gate policy defaults for interruptible graph execution.",
            },
        ],
        "governance_defaults": {
            "verification": {"kind": "judge", "mode": "required"},
            "approval": {"kind": "approval", "required": False},
            "recovery": {"kind": "resume", "max_attempts": 2},
        },
        "runtime_binding_hints": {
            "supports_resume": True,
            "supports_branching": True,
            "preferred_runtime_keys": ["default"],
        },
        "compiler_profile_templates": [
            {
                "template_id": "framework.langgraph.graph_resume",
                "workflow_kind": "graph_governed",
                "governance_policy_ref": "policy.runtime.resume_gate",
                "runtime_binding": {"supports_resume": True},
                "input_contract": {"required": ["graph_goal"]},
                "output_contract": {"required": ["receipt"]},
            }
        ],
        "metadata": {
            "lane_a_note": "LangGraph is mapped to execution semantics and gate-aware resumability.",
        },
    },
    {
        "framework_id": "openai_agents_sdk",
        "source_terms": [
            "handoffs",
            "guardrails",
            "tracing",
            "sessions",
        ],
        "butler_targets": [
            {
                "source_concept": "handoff object",
                "butler_layer": "Collaboration State Plane",
                "target_kind": "handoff_contract",
                "adopt": [
                    "structured handoff rules",
                    "handoff-aware collaboration contracts",
                ],
                "do_not_copy": [
                    "SDK-specific agent API surface",
                ],
            },
            {
                "source_concept": "guardrails and tracing",
                "butler_layer": "Governance / Observability Plane",
                "target_kind": "governance_policy",
                "adopt": [
                    "guardrail-aware governance defaults",
                    "tracing as a first-class observability output",
                ],
                "do_not_copy": [
                    "provider-bound runtime abstractions",
                ],
                "policy_refs": [
                    "policy.runtime.guardrail_default",
                    "policy.runtime.trace_required",
                ],
            },
        ],
        "absorbed_packages": [
            {
                "package_kind": "contract_package",
                "package_ref": "contract.runtime.handoff",
                "purpose": "Structured handoff contract package.",
            },
            {
                "package_kind": "governance_policy_package",
                "package_ref": "policy.runtime.guardrail_default",
                "purpose": "Guardrail and tracing defaults for runtime execution.",
            },
        ],
        "governance_defaults": {
            "verification": {"kind": "judge", "mode": "required"},
            "approval": {"kind": "approval", "required": False},
            "recovery": {"kind": "retry", "max_attempts": 1},
        },
        "runtime_binding_hints": {
            "supports_handoff_contracts": True,
            "supports_tracing": True,
            "preferred_runtime_keys": ["default", "codex"],
        },
        "compiler_profile_templates": [
            {
                "template_id": "framework.openai_agents_sdk.handoff_guardrail",
                "workflow_kind": "agent_handoff_governed",
                "governance_policy_ref": "policy.runtime.guardrail_default",
                "runtime_binding": {"supports_handoff_contracts": True, "supports_tracing": True},
                "input_contract": {"required": ["user_request"]},
                "output_contract": {"required": ["handoff_receipt", "trace_record"]},
            }
        ],
        "metadata": {
            "lane_a_note": "OpenAI Agents SDK is mapped to handoff, guardrail and tracing primitives, not provider-specific API cloning.",
        },
    },
    {
        "framework_id": "autogen",
        "source_terms": [
            "core api",
            "agentchat",
            "extensions",
            "event driven",
        ],
        "butler_targets": [
            {
                "source_concept": "core vs higher-level layering",
                "butler_layer": "Package / Framework Definition Plane",
                "target_kind": "compiler_profile_template",
                "adopt": [
                    "core runtime contract separate from higher-level collaboration profile",
                    "extension-friendly package definition",
                ],
                "do_not_copy": [
                    "group-chat-first default abstraction",
                ],
            },
            {
                "source_concept": "event-driven collaboration",
                "butler_layer": "Collaboration State Plane",
                "target_kind": "collaboration_contract",
                "adopt": [
                    "event-shaped collaboration protocol",
                    "extension-aware collaboration substrate",
                ],
                "do_not_copy": [
                    "agent chat UX as the only collaboration mode",
                ],
            },
        ],
        "absorbed_packages": [
            {
                "package_kind": "team_package",
                "package_ref": "team.extension.event_collaboration",
                "purpose": "Extension-aware collaboration profile derived from AutoGen layering.",
            }
        ],
        "governance_defaults": {
            "verification": {"kind": "judge", "mode": "required"},
            "approval": {"kind": "approval", "required": False},
            "recovery": {"kind": "retry_step", "max_attempts": 1},
        },
        "runtime_binding_hints": {
            "supports_event_protocol": True,
            "preferred_runtime_keys": ["default"],
        },
        "compiler_profile_templates": [
            {
                "template_id": "framework.autogen.event_collaboration",
                "workflow_kind": "event_collaboration",
                "runtime_binding": {"supports_event_protocol": True},
                "input_contract": {"required": ["collaboration_goal"]},
                "output_contract": {"required": ["collaboration_receipt"]},
            }
        ],
        "metadata": {
            "lane_a_note": "AutoGen is mapped to layering and event collaboration, not a Butler group-chat shell.",
        },
    },
    {
        "framework_id": "crewai",
        "source_terms": [
            "crew",
            "flow",
            "autonomy",
            "delegation",
        ],
        "butler_targets": [
            {
                "source_concept": "crew vs flow split",
                "butler_layer": "Workflow Compile Plane",
                "target_kind": "workflow_package",
                "adopt": [
                    "autonomy-oriented team package separate from precise flow package",
                    "explicit compiler choice between team mode and flow mode",
                ],
                "do_not_copy": [
                    "CrewAI term as Butler core noun",
                ],
            },
            {
                "source_concept": "delegation-friendly crews",
                "butler_layer": "Package / Framework Definition Plane",
                "target_kind": "team_package",
                "adopt": [
                    "team package for bounded autonomy",
                ],
                "do_not_copy": [
                    "role theater without contracts",
                ],
            },
        ],
        "absorbed_packages": [
            {
                "package_kind": "team_package",
                "package_ref": "team.autonomy.crew_mode",
                "purpose": "Bounded autonomy package for crew-like collaboration.",
            },
            {
                "package_kind": "workflow_package",
                "package_ref": "workflow.flow.precise_control",
                "purpose": "Flow-oriented package for precise control paths.",
            },
        ],
        "governance_defaults": {
            "verification": {"kind": "judge", "mode": "required"},
            "approval": {"kind": "approval", "required": False},
            "recovery": {"kind": "retry", "max_attempts": 1},
        },
        "runtime_binding_hints": {
            "supports_team_mode": True,
            "supports_flow_mode": True,
            "preferred_runtime_keys": ["default"],
        },
        "compiler_profile_templates": [
            {
                "template_id": "framework.crewai.crew_flow_split",
                "workflow_kind": "team_flow_hybrid",
                "capability_package_ref": "pkg.cap.team_flow_hybrid",
                "runtime_binding": {"supports_team_mode": True, "supports_flow_mode": True},
                "input_contract": {"required": ["mission_goal"]},
                "output_contract": {"required": ["artifact_bundle"]},
            }
        ],
        "metadata": {
            "lane_a_note": "CrewAI is mapped to autonomy-vs-flow separation, not to Butler terminology.",
        },
    },
    {
        "framework_id": "metagpt",
        "source_terms": [
            "software company roles",
            "sop",
            "protocol",
            "handoff",
        ],
        "butler_targets": [
            {
                "source_concept": "SOP-first software company",
                "butler_layer": "Package / Framework Definition Plane",
                "target_kind": "workflow_package",
                "adopt": [
                    "SOP as workflow package input",
                    "role protocols represented as contracts",
                ],
                "do_not_copy": [
                    "company role names as Butler runtime truth",
                ],
                "contract_refs": [
                    "contract.sop.role_handoff",
                ],
            },
            {
                "source_concept": "role handoff protocol",
                "butler_layer": "Collaboration State Plane",
                "target_kind": "handoff_contract",
                "adopt": [
                    "handoff contracts between bounded roles",
                    "artifact expectations on role transitions",
                ],
                "do_not_copy": [
                    "role catalog explosion",
                ],
            },
        ],
        "absorbed_packages": [
            {
                "package_kind": "workflow_package",
                "package_ref": "workflow.sop.software_company",
                "purpose": "SOP-driven software company workflow package.",
            },
            {
                "package_kind": "contract_package",
                "package_ref": "contract.sop.role_handoff",
                "purpose": "Role handoff contract package for SOP-based collaboration.",
            },
        ],
        "governance_defaults": {
            "verification": {"kind": "judge", "mode": "required"},
            "approval": {"kind": "approval", "required": False},
            "recovery": {"kind": "repair", "max_attempts": 1},
        },
        "runtime_binding_hints": {
            "supports_sop_protocols": True,
            "preferred_runtime_keys": ["default"],
        },
        "compiler_profile_templates": [
            {
                "template_id": "framework.metagpt.sop_company",
                "workflow_kind": "sop_company_flow",
                "runtime_binding": {"supports_sop_protocols": True},
                "input_contract": {"required": ["goal", "sop_profile"]},
                "output_contract": {"required": ["artifact_bundle", "handoff_receipts"]},
            }
        ],
        "metadata": {
            "lane_a_note": "MetaGPT is mapped to SOP and protocol packages, not to role accumulation.",
        },
    },
    {
        "framework_id": "openhands",
        "source_terms": [
            "sdk cli gui cloud",
            "software task platform",
            "runtime core vs interfaces",
        ],
        "butler_targets": [
            {
                "source_concept": "runtime core vs entry surfaces",
                "butler_layer": "Mission / Control Plane",
                "target_kind": "runtime_binding",
                "adopt": [
                    "entry-surface independence from runtime core",
                    "control-plane selection independent from UI shell",
                ],
                "do_not_copy": [
                    "product shell or GUI",
                ],
                "runtime_binding": {
                    "entry_surface_agnostic": True,
                },
            },
            {
                "source_concept": "software task platform",
                "butler_layer": "Package / Framework Definition Plane",
                "target_kind": "workflow_package",
                "adopt": [
                    "workspace task package",
                    "coding-task oriented workflow package",
                ],
                "do_not_copy": [
                    "OpenHands app shell",
                ],
            },
        ],
        "absorbed_packages": [
            {
                "package_kind": "workflow_package",
                "package_ref": "workflow.dev.workspace_task",
                "purpose": "Workspace-oriented task package independent from entry surfaces.",
            }
        ],
        "governance_defaults": {
            "verification": {"kind": "judge", "mode": "required"},
            "approval": {"kind": "approval", "required": False},
            "recovery": {"kind": "retry", "max_attempts": 1},
        },
        "runtime_binding_hints": {
            "entry_surface_agnostic": True,
            "preferred_runtime_keys": ["codex", "default"],
        },
        "compiler_profile_templates": [
            {
                "template_id": "framework.openhands.workspace_task",
                "workflow_kind": "workspace_task",
                "runtime_binding": {"entry_surface_agnostic": True},
                "input_contract": {"required": ["workspace_goal"]},
                "output_contract": {"required": ["task_result"]},
            }
        ],
        "metadata": {
            "lane_a_note": "OpenHands is mapped to runtime-core separation and workspace task packaging, not to app shell cloning.",
        },
    },
    {
        "framework_id": "temporal",
        "source_terms": [
            "durable execution",
            "deterministic replay",
            "retry and compensation",
        ],
        "butler_targets": [
            {
                "source_concept": "durable execution discipline",
                "butler_layer": "Execution Kernel Plane",
                "target_kind": "runtime_binding",
                "adopt": [
                    "deterministic replay awareness",
                    "side-effect boundary discipline",
                    "recovery as runtime contract",
                ],
                "do_not_copy": [
                    "Temporal server model",
                ],
                "runtime_binding": {
                    "supports_durable_replay": True,
                    "side_effect_boundary": "strict",
                },
            },
            {
                "source_concept": "retry and replay policy",
                "butler_layer": "Governance / Observability Plane",
                "target_kind": "governance_policy",
                "adopt": [
                    "retry/replay policy as explicit governance input",
                ],
                "do_not_copy": [
                    "infra-specific operational model",
                ],
                "policy_refs": [
                    "policy.runtime.durable_replay",
                ],
            },
        ],
        "absorbed_packages": [
            {
                "package_kind": "governance_policy_package",
                "package_ref": "policy.runtime.durable_replay",
                "purpose": "Replay and retry governance defaults for durable execution.",
            }
        ],
        "governance_defaults": {
            "verification": {"kind": "judge", "mode": "required"},
            "approval": {"kind": "approval", "required": False},
            "recovery": {"kind": "resume", "max_attempts": 3},
        },
        "runtime_binding_hints": {
            "supports_durable_replay": True,
            "side_effect_boundary": "strict",
            "preferred_runtime_keys": ["default"],
        },
        "compiler_profile_templates": [
            {
                "template_id": "framework.temporal.durable_workflow",
                "workflow_kind": "durable_governed",
                "governance_policy_ref": "policy.runtime.durable_replay",
                "runtime_binding": {"supports_durable_replay": True},
                "input_contract": {"required": ["workflow_goal"]},
                "output_contract": {"required": ["receipt", "checkpoint_ref"]},
            }
        ],
        "metadata": {
            "lane_a_note": "Temporal is mapped to replay and recovery discipline, not to backend infrastructure cloning.",
        },
    },
]


def load_builtin_framework_mapping_registry() -> FrameworkMappingRegistry:
    return FrameworkMappingRegistry(specs=[FrameworkMappingSpec.from_dict(item) for item in _BUILTIN_FRAMEWORK_MAPPING_DATA])


def get_builtin_framework_mapping_spec(framework_id: str) -> FrameworkMappingSpec | None:
    return load_builtin_framework_mapping_registry().get_spec(framework_id)


def load_framework_mapping_bundle(
    framework_id: str,
    *,
    catalog: FrameworkCatalog | None = None,
    registry: FrameworkMappingRegistry | None = None,
) -> FrameworkMappingBundle:
    resolved_catalog = catalog or load_builtin_framework_catalog()
    resolved_registry = registry or load_builtin_framework_mapping_registry()
    return FrameworkMappingBundle(
        entry=resolved_catalog.require_entry(framework_id),
        mapping=resolved_registry.require_spec(framework_id),
    )


def get_builtin_framework_mapping_bundle(framework_id: str) -> FrameworkMappingBundle | None:
    entry = get_builtin_framework_catalog_entry(framework_id)
    spec = get_builtin_framework_mapping_spec(framework_id)
    if entry is None or spec is None:
        return None
    return FrameworkMappingBundle(entry=entry, mapping=spec)


def load_framework_compiler_inputs(
    framework_id: str,
    *,
    catalog: FrameworkCatalog | None = None,
    registry: FrameworkMappingRegistry | None = None,
) -> dict[str, Any]:
    return load_framework_mapping_bundle(
        framework_id,
        catalog=catalog,
        registry=registry,
    ).compiler_inputs()
