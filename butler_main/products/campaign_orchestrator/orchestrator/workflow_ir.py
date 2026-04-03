from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Mapping


def _as_dict(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, Mapping) else {}


def _as_list_of_dicts(payload: list[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
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


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "required"}:
            return True
        if normalized in {"0", "false", "no", "off", "skip", "none", "disabled"}:
            return False
    if value is None:
        return default
    return bool(value)


@dataclass(slots=True)
class WorkflowIR:
    schema_version: str = "butler.workflow_ir.v1"
    workflow_id: str = ""
    mission_id: str = ""
    node_id: str = ""
    branch_id: str = ""
    workflow_kind: str = "mission"
    driver_kind: str = "orchestrator_node"
    entrypoint: str = "orchestrator"
    runtime_key: str = "default"
    agent_id: str = ""
    worker_profile: str = ""
    node_kind: str = ""
    node_title: str = ""
    template_id: str = ""
    workflow_template: dict[str, Any] = field(default_factory=dict)
    role_bindings: list[dict[str, Any]] = field(default_factory=list)
    workflow_inputs: dict[str, Any] = field(default_factory=dict)
    workflow_session_id: str = ""
    workflow_template_id: str = ""
    subworkflow_kind: str = ""
    research_unit_id: str = ""
    scenario_action: str = ""
    verification: dict[str, Any] = field(default_factory=dict)
    approval: dict[str, Any] = field(default_factory=dict)
    recovery: dict[str, Any] = field(default_factory=dict)
    capability_package_ref: str = ""
    team_package_ref: str = ""
    governance_policy_ref: str = ""
    runtime_binding: dict[str, Any] = field(default_factory=dict)
    input_contract: dict[str, Any] = field(default_factory=dict)
    output_contract: dict[str, Any] = field(default_factory=dict)
    entry_step_id: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    roles: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    handoffs: list[dict[str, Any]] = field(default_factory=list)
    runtime_state: dict[str, Any] = field(default_factory=dict)
    observability: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.schema_version = _text(self.schema_version, default="butler.workflow_ir.v1")
        self.workflow_id = _text(self.workflow_id)
        self.mission_id = _text(self.mission_id)
        self.node_id = _text(self.node_id)
        self.branch_id = _text(self.branch_id)
        self.workflow_kind = _text(self.workflow_kind, default="mission")
        self.driver_kind = _text(self.driver_kind, default="orchestrator_node")
        self.entrypoint = _text(self.entrypoint, default="orchestrator")
        self.runtime_key = _text(self.runtime_key, default="default")
        self.agent_id = _text(self.agent_id)
        self.worker_profile = _text(self.worker_profile)
        self.node_kind = _text(self.node_kind)
        self.node_title = _text(self.node_title)
        self.template_id = _text(self.template_id)
        self.workflow_template = _as_dict(self.workflow_template)
        self.role_bindings = _as_list_of_dicts(self.role_bindings)
        self.workflow_inputs = _as_dict(self.workflow_inputs)
        self.workflow_session_id = _text(self.workflow_session_id)
        self.workflow_template_id = _text(self.workflow_template_id)
        self.subworkflow_kind = _text(self.subworkflow_kind)
        self.research_unit_id = _text(self.research_unit_id)
        self.scenario_action = _text(self.scenario_action)
        self.verification = _as_dict(self.verification)
        self.approval = _as_dict(self.approval)
        self.recovery = _as_dict(self.recovery)
        self.capability_package_ref = _text(self.capability_package_ref)
        self.team_package_ref = _text(self.team_package_ref)
        self.governance_policy_ref = _text(self.governance_policy_ref)
        self.runtime_binding = _as_dict(self.runtime_binding)
        self.input_contract = _as_dict(self.input_contract)
        self.output_contract = _as_dict(self.output_contract)
        self.entry_step_id = _text(self.entry_step_id)
        self.steps = _as_list_of_dicts(self.steps)
        self.edges = _as_list_of_dicts(self.edges)
        self.roles = _as_list_of_dicts(self.roles)
        self.artifacts = _as_list_of_dicts(self.artifacts)
        self.handoffs = _as_list_of_dicts(self.handoffs)
        self.runtime_state = _as_dict(self.runtime_state)
        self.observability = _as_dict(self.observability)
        self.metadata = _as_dict(self.metadata)
        self._hydrate_structured_fields()

    def _hydrate_structured_fields(self) -> None:
        template = dict(self.workflow_template)
        if not self.template_id:
            self.template_id = _first_text(template.get("template_id"), self.workflow_template_id)
        if not self.workflow_template_id:
            self.workflow_template_id = self.template_id
        if not self.workflow_kind:
            self.workflow_kind = _text(template.get("kind"), default="mission")
        if not self.steps:
            self.steps = _as_list_of_dicts(template.get("steps"))
        if not self.roles:
            self.roles = _as_list_of_dicts(template.get("roles"))
        if not self.roles and self.role_bindings:
            self.roles = [
                {
                    "role_id": _first_text(item.get("role_id"), item.get("id")),
                    "capability_id": _first_text(item.get("capability_id"), item.get("capability")),
                    "agent_spec_id": _text(item.get("agent_spec_id")),
                    "package_ref": _text(item.get("package_ref")),
                    "policy_refs": _as_text_list(item.get("policy_refs")),
                    "metadata": _as_dict(item.get("metadata")),
                }
                for item in self.role_bindings
                if _first_text(item.get("role_id"), item.get("id"))
            ]
        if not self.edges:
            self.edges = _as_list_of_dicts(template.get("edges"))
        if not self.edges and len(self.steps) > 1:
            self.edges = []
            for index in range(len(self.steps) - 1):
                source = _first_text(self.steps[index].get("step_id"), self.steps[index].get("id"))
                target = _first_text(self.steps[index + 1].get("step_id"), self.steps[index + 1].get("id"))
                if source and target:
                    self.edges.append(
                        {
                            "edge_id": f"{source}__next__{target}",
                            "source_step_id": source,
                            "target_step_id": target,
                            "condition": "next",
                        }
                    )
        if not self.artifacts:
            self.artifacts = _as_list_of_dicts(template.get("artifacts"))
        if not self.handoffs:
            self.handoffs = _as_list_of_dicts(template.get("handoffs"))
        if not self.entry_step_id:
            self.entry_step_id = _first_text(
                template.get("entry_step_id"),
                self.runtime_state.get("current_step_id"),
                self.steps[0].get("step_id") if self.steps else "",
                self.steps[0].get("id") if self.steps else "",
            )
        package_refs = _as_dict(template.get("package_refs"))
        if not self.capability_package_ref:
            self.capability_package_ref = _first_text(template.get("capability_package_ref"), package_refs.get("capability_package_ref"))
        if not self.team_package_ref:
            self.team_package_ref = _first_text(template.get("team_package_ref"), package_refs.get("team_package_ref"))
        if not self.governance_policy_ref:
            self.governance_policy_ref = _first_text(template.get("governance_policy_ref"), package_refs.get("governance_policy_ref"))
        if not self.input_contract:
            self.input_contract = _as_dict(template.get("input_contract") if isinstance(template.get("input_contract"), Mapping) else template.get("entry_contract"))
        if not self.output_contract:
            self.output_contract = _as_dict(template.get("output_contract") if isinstance(template.get("output_contract"), Mapping) else template.get("exit_contract"))
        if not self.runtime_binding:
            self.runtime_binding = {
                "runtime_key": self.runtime_key,
                "agent_id": self.agent_id,
                "worker_profile": self.worker_profile,
                "runtime_profile": _as_dict(self.metadata.get("runtime_profile")),
            }
        self.runtime_key = _first_text(self.runtime_key, self.runtime_binding.get("runtime_key"), self.runtime_state.get("runtime_key"), default="default")
        self.agent_id = _first_text(self.agent_id, self.runtime_binding.get("agent_id"), self.runtime_state.get("agent_id"))
        self.worker_profile = _first_text(
            self.worker_profile,
            self.runtime_binding.get("worker_profile"),
            self.runtime_state.get("worker_profile"),
            self.runtime_key,
        )
        self.runtime_binding.setdefault("runtime_key", self.runtime_key)
        self.runtime_binding.setdefault("agent_id", self.agent_id)
        self.runtime_binding.setdefault("worker_profile", self.worker_profile)
        if not self.workflow_inputs:
            self.workflow_inputs = _as_dict(self.runtime_state.get("workflow_inputs"))
        if not self.workflow_session_id:
            self.workflow_session_id = _text(self.runtime_state.get("workflow_session_id"))
        if not self.subworkflow_kind:
            self.subworkflow_kind = _text(self.runtime_state.get("subworkflow_kind"))
        if not self.research_unit_id:
            self.research_unit_id = _text(self.runtime_state.get("research_unit_id"))
        if not self.scenario_action:
            self.scenario_action = _text(self.runtime_state.get("scenario_action"))
        if not self.observability:
            self.observability = {
                "tags": [item for item in [self.workflow_kind, self.node_kind, self.worker_profile, self.subworkflow_kind] if item],
                "lineage": dict(self.metadata),
            }
        self.runtime_state = {
            **self.runtime_state,
            "workflow_session_id": self.workflow_session_id,
            "mission_id": self.mission_id,
            "node_id": self.node_id,
            "branch_id": self.branch_id,
            "current_step_id": _first_text(self.runtime_state.get("current_step_id"), self.entry_step_id),
            "status": _first_text(self.runtime_state.get("status"), default="compiled"),
            "workflow_inputs": dict(self.workflow_inputs),
            "runtime_key": self.runtime_key,
            "agent_id": self.agent_id,
            "worker_profile": self.worker_profile,
            "node_kind": self.node_kind,
            "subworkflow_kind": self.subworkflow_kind,
            "research_unit_id": self.research_unit_id,
            "scenario_action": self.scenario_action,
            "metadata": _as_dict(self.runtime_state.get("metadata")),
        }

    def workflow_payload(self) -> dict[str, Any]:
        template_payload = dict(self.workflow_template)
        if self.template_id and not template_payload.get("template_id"):
            template_payload["template_id"] = self.template_id
        if self.workflow_kind and not template_payload.get("kind"):
            template_payload["kind"] = self.workflow_kind
        if self.entry_step_id and not template_payload.get("entry_step_id"):
            template_payload["entry_step_id"] = self.entry_step_id
        if self.steps and not template_payload.get("steps"):
            template_payload["steps"] = [dict(item) for item in self.steps]
        if self.roles and not template_payload.get("roles"):
            template_payload["roles"] = [dict(item) for item in self.roles]
        if self.edges and not template_payload.get("edges"):
            template_payload["edges"] = [dict(item) for item in self.edges]
        if self.artifacts and not template_payload.get("artifacts"):
            template_payload["artifacts"] = [dict(item) for item in self.artifacts]
        if self.handoffs and not template_payload.get("handoffs"):
            template_payload["handoffs"] = [dict(item) for item in self.handoffs]
        if self.input_contract and not template_payload.get("entry_contract"):
            template_payload["entry_contract"] = dict(self.input_contract)
        if self.output_contract and not template_payload.get("exit_contract"):
            template_payload["exit_contract"] = dict(self.output_contract)
        return {
            "template_id": self.workflow_template_id or self.template_id,
            "kind": self.workflow_kind,
            "entry_step_id": self.entry_step_id,
            "template": template_payload,
            "package_refs": {
                "capability_package_ref": self.capability_package_ref,
                "team_package_ref": self.team_package_ref,
                "governance_policy_ref": self.governance_policy_ref,
            },
            "role_bindings": [dict(item) for item in self.role_bindings],
            "steps": [dict(item) for item in self.steps],
            "edges": [dict(item) for item in self.edges],
            "roles": [dict(item) for item in self.roles],
            "artifacts": [dict(item) for item in self.artifacts],
            "handoffs": [dict(item) for item in self.handoffs],
            "capability_package_ref": self.capability_package_ref,
            "team_package_ref": self.team_package_ref,
            "governance_policy_ref": self.governance_policy_ref,
            "runtime_binding": dict(self.runtime_binding),
            "input_contract": dict(self.input_contract),
            "output_contract": dict(self.output_contract),
        }

    def compile_time_payload(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow_payload(),
            "verification": dict(self.verification),
            "approval": dict(self.approval),
            "recovery": dict(self.recovery),
        }

    def runtime_payload(self) -> dict[str, Any]:
        payload = dict(self.runtime_state)
        payload["execution_boundary"] = self.execution_boundary()
        return payload

    def observability_payload(self) -> dict[str, Any]:
        payload = dict(self.observability)
        payload.setdefault("tags", _as_text_list(payload.get("tags")))
        payload.setdefault("lineage", dict(self.metadata))
        payload["gate_policies"] = self.gate_policies()
        payload["execution_boundary"] = self.execution_boundary()
        return payload

    def to_dict(self) -> dict[str, Any]:
        self._hydrate_structured_fields()
        return {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "mission_id": self.mission_id,
            "node_id": self.node_id,
            "branch_id": self.branch_id,
            "workflow_kind": self.workflow_kind,
            "driver_kind": self.driver_kind,
            "entrypoint": self.entrypoint,
            "runtime_key": self.runtime_key,
            "agent_id": self.agent_id,
            "worker_profile": self.worker_profile,
            "node_kind": self.node_kind,
            "node_title": self.node_title,
            "template_id": self.template_id,
            "workflow_template": dict(self.workflow_template),
            "role_bindings": [dict(item) for item in self.role_bindings],
            "workflow_inputs": dict(self.workflow_inputs),
            "workflow_session_id": self.workflow_session_id,
            "workflow_template_id": self.workflow_template_id,
            "subworkflow_kind": self.subworkflow_kind,
            "research_unit_id": self.research_unit_id,
            "scenario_action": self.scenario_action,
            "verification": dict(self.verification),
            "approval": dict(self.approval),
            "recovery": dict(self.recovery),
            "capability_package_ref": self.capability_package_ref,
            "team_package_ref": self.team_package_ref,
            "governance_policy_ref": self.governance_policy_ref,
            "runtime_binding": dict(self.runtime_binding),
            "input_contract": dict(self.input_contract),
            "output_contract": dict(self.output_contract),
            "entry_step_id": self.entry_step_id,
            "workflow": self.workflow_payload(),
            "compile_time": self.compile_time_payload(),
            "runtime": self.runtime_payload(),
            "observability": self.observability_payload(),
            "metadata": dict(self.metadata),
            "gate_policies": self.gate_policies(),
            "execution_boundary": self.execution_boundary(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "WorkflowIR":
        if not isinstance(payload, Mapping):
            return cls()
        raw = dict(payload)
        compile_time = _as_dict(raw.get("compile_time") if isinstance(raw.get("compile_time"), Mapping) else None)
        workflow = _as_dict(raw.get("workflow") if isinstance(raw.get("workflow"), Mapping) else None)
        if not workflow and isinstance(compile_time.get("workflow"), Mapping):
            workflow = dict(compile_time.get("workflow") or {})
        runtime = _as_dict(raw.get("runtime") if isinstance(raw.get("runtime"), Mapping) else None)
        observability = _as_dict(raw.get("observability") if isinstance(raw.get("observability"), Mapping) else None)
        workflow_template = _as_dict(raw.get("workflow_template") if isinstance(raw.get("workflow_template"), Mapping) else None)
        if not workflow_template and isinstance(workflow.get("template"), Mapping):
            workflow_template = dict(workflow.get("template") or {})
        verification = _as_dict(raw.get("verification") if isinstance(raw.get("verification"), Mapping) else None)
        approval = _as_dict(raw.get("approval") if isinstance(raw.get("approval"), Mapping) else None)
        recovery = _as_dict(raw.get("recovery") if isinstance(raw.get("recovery"), Mapping) else None)
        if not verification and isinstance(compile_time.get("verification"), Mapping):
            verification = dict(compile_time.get("verification") or {})
        if not approval and isinstance(compile_time.get("approval"), Mapping):
            approval = dict(compile_time.get("approval") or {})
        if not recovery and isinstance(compile_time.get("recovery"), Mapping):
            recovery = dict(compile_time.get("recovery") or {})
        package_refs = _as_dict(workflow.get("package_refs") if isinstance(workflow.get("package_refs"), Mapping) else None)
        return cls(
            schema_version=_first_text(raw.get("schema_version"), default="butler.workflow_ir.v1"),
            workflow_id=_text(raw.get("workflow_id")),
            mission_id=_first_text(raw.get("mission_id"), runtime.get("mission_id")),
            node_id=_first_text(raw.get("node_id"), runtime.get("node_id")),
            branch_id=_first_text(raw.get("branch_id"), runtime.get("branch_id")),
            workflow_kind=_first_text(raw.get("workflow_kind"), workflow.get("kind"), default="mission"),
            driver_kind=_first_text(raw.get("driver_kind"), default="orchestrator_node"),
            entrypoint=_first_text(raw.get("entrypoint"), default="orchestrator"),
            runtime_key=_first_text(raw.get("runtime_key"), runtime.get("runtime_key"), default="default"),
            agent_id=_first_text(raw.get("agent_id"), runtime.get("agent_id")),
            worker_profile=_first_text(raw.get("worker_profile"), runtime.get("worker_profile")),
            node_kind=_first_text(raw.get("node_kind"), runtime.get("node_kind")),
            node_title=_text(raw.get("node_title")),
            template_id=_first_text(raw.get("template_id"), workflow_template.get("template_id"), workflow.get("template_id")),
            workflow_template=workflow_template,
            role_bindings=_as_list_of_dicts(raw.get("role_bindings") if isinstance(raw.get("role_bindings"), list) else workflow.get("role_bindings")),
            workflow_inputs=_as_dict(raw.get("workflow_inputs") if isinstance(raw.get("workflow_inputs"), Mapping) else runtime.get("workflow_inputs")),
            workflow_session_id=_first_text(raw.get("workflow_session_id"), runtime.get("workflow_session_id")),
            workflow_template_id=_first_text(raw.get("workflow_template_id"), workflow.get("template_id")),
            subworkflow_kind=_first_text(raw.get("subworkflow_kind"), runtime.get("subworkflow_kind")),
            research_unit_id=_first_text(raw.get("research_unit_id"), runtime.get("research_unit_id")),
            scenario_action=_first_text(raw.get("scenario_action"), runtime.get("scenario_action")),
            verification=verification,
            approval=approval,
            recovery=recovery,
            capability_package_ref=_first_text(raw.get("capability_package_ref"), workflow.get("capability_package_ref"), package_refs.get("capability_package_ref")),
            team_package_ref=_first_text(raw.get("team_package_ref"), workflow.get("team_package_ref"), package_refs.get("team_package_ref")),
            governance_policy_ref=_first_text(raw.get("governance_policy_ref"), workflow.get("governance_policy_ref"), package_refs.get("governance_policy_ref")),
            runtime_binding=_as_dict(raw.get("runtime_binding") if isinstance(raw.get("runtime_binding"), Mapping) else workflow.get("runtime_binding")),
            input_contract=_as_dict(raw.get("input_contract") if isinstance(raw.get("input_contract"), Mapping) else workflow.get("input_contract")),
            output_contract=_as_dict(raw.get("output_contract") if isinstance(raw.get("output_contract"), Mapping) else workflow.get("output_contract")),
            entry_step_id=_first_text(raw.get("entry_step_id"), workflow.get("entry_step_id")),
            steps=_as_list_of_dicts(workflow.get("steps")),
            edges=_as_list_of_dicts(workflow.get("edges")),
            roles=_as_list_of_dicts(workflow.get("roles")),
            artifacts=_as_list_of_dicts(workflow.get("artifacts")),
            handoffs=_as_list_of_dicts(workflow.get("handoffs")),
            runtime_state=runtime,
            observability=observability,
            metadata=_as_dict(raw.get("metadata")),
        )

    def to_runtime_plan_payload(self) -> dict[str, Any]:
        self._hydrate_structured_fields()
        payload: dict[str, Any] = {}
        workflow_template = dict(self.workflow_template)
        if self.template_id and not workflow_template.get("template_id"):
            workflow_template["template_id"] = self.template_id
        if self.workflow_kind and not workflow_template.get("kind"):
            workflow_template["kind"] = self.workflow_kind
        if self.entry_step_id and not workflow_template.get("entry_step_id"):
            workflow_template["entry_step_id"] = self.entry_step_id
        if self.steps and not workflow_template.get("steps"):
            workflow_template["steps"] = [dict(item) for item in self.steps]
        if self.roles and not workflow_template.get("roles"):
            workflow_template["roles"] = [dict(item) for item in self.roles]
        if self.input_contract and not workflow_template.get("entry_contract"):
            workflow_template["entry_contract"] = dict(self.input_contract)
        if self.output_contract and not workflow_template.get("exit_contract"):
            workflow_template["exit_contract"] = dict(self.output_contract)
        if workflow_template:
            payload["workflow_template"] = workflow_template
        elif self.template_id:
            payload["workflow_template_id"] = self.template_id
        if self.edges:
            payload["workflow_edges"] = [dict(item) for item in self.edges]
        if self.artifacts:
            payload["workflow_artifacts"] = [dict(item) for item in self.artifacts]
        if self.handoffs:
            payload["workflow_handoffs"] = [dict(item) for item in self.handoffs]
        if self.role_bindings:
            payload["role_bindings"] = [dict(item) for item in self.role_bindings]
        if self.workflow_inputs:
            payload["workflow_inputs"] = dict(self.workflow_inputs)
        if self.worker_profile:
            payload["worker_profile"] = self.worker_profile
        if self.runtime_key:
            payload["runtime_key"] = self.runtime_key
        if self.agent_id:
            payload["agent_id"] = self.agent_id
        if self.subworkflow_kind:
            payload["subworkflow_kind"] = self.subworkflow_kind
        if self.research_unit_id:
            payload["research_unit_id"] = self.research_unit_id
        if self.scenario_action:
            payload["scenario_action"] = self.scenario_action
        if self.verification:
            payload["verification"] = dict(self.verification)
        if self.approval:
            payload["approval"] = dict(self.approval)
        if self.recovery:
            payload["recovery"] = dict(self.recovery)
        if self.capability_package_ref:
            payload["capability_package_ref"] = self.capability_package_ref
        if self.team_package_ref:
            payload["team_package_ref"] = self.team_package_ref
        if self.governance_policy_ref:
            payload["governance_policy_ref"] = self.governance_policy_ref
        if self.runtime_binding:
            payload["runtime_binding"] = dict(self.runtime_binding)
        if self.input_contract:
            payload["input_contract"] = dict(self.input_contract)
        if self.output_contract:
            payload["output_contract"] = dict(self.output_contract)
        return payload

    def summary(self) -> dict[str, Any]:
        self._hydrate_structured_fields()
        return {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "workflow_kind": self.workflow_kind,
            "driver_kind": self.driver_kind,
            "entrypoint": self.entrypoint,
            "runtime_key": self.runtime_key,
            "agent_id": self.agent_id,
            "worker_profile": self.worker_profile,
            "template_id": self.workflow_template_id or self.template_id,
            "workflow_session_id": self.workflow_session_id,
            "subworkflow_kind": self.subworkflow_kind,
            "research_unit_id": self.research_unit_id,
            "scenario_action": self.scenario_action,
            "entry_step_id": self.entry_step_id,
            "step_count": len(self.steps),
            "edge_count": len(self.edges),
            "capability_package_ref": self.capability_package_ref,
            "team_package_ref": self.team_package_ref,
            "governance_policy_ref": self.governance_policy_ref,
            "framework_origin": _as_dict(self.metadata.get("framework_origin")),
            "runtime_binding": dict(self.runtime_binding),
            "input_contract": dict(self.input_contract),
            "output_contract": dict(self.output_contract),
            "verification": dict(self.verification),
            "approval": dict(self.approval),
            "recovery": dict(self.recovery),
            "gate_policies": self.gate_policies(),
            "execution_boundary": self.execution_boundary(),
        }

    def gate_policies(self, *, default_recovery_attempts: int = 0) -> dict[str, dict[str, Any]]:
        return {
            "verification": self.verification_policy(),
            "approval": self.approval_policy(),
            "recovery": self.recovery_policy(default_max_attempts=default_recovery_attempts),
        }

    def verification_policy(self) -> dict[str, Any]:
        contract = dict(self.verification or {})
        mode = str(contract.get("mode") or "").strip().lower()
        required = _coerce_bool(
            contract.get("required"),
            default=mode not in {"skip", "none", "disabled"},
        )
        return {
            **contract,
            "kind": str(contract.get("kind") or "judge").strip() or "judge",
            "required": required,
            "mode": "required" if required else "skip",
            "owner": "orchestrator",
            "target_owner": "runtime_os.process_runtime",
            "canonical_target_owner": "runtime_os.durability_substrate",
            "session_runtime_owner": "runtime_os.multi_agent_runtime",
            "runner": "judge_adapter" if required else "none",
        }

    def approval_policy(self) -> dict[str, Any]:
        contract = dict(self.approval or {})
        mode = str(contract.get("mode") or "").strip().lower()
        required = _coerce_bool(
            contract.get("required"),
            default=mode in {"required", "manual", "human_gate"},
        )
        return {
            **contract,
            "kind": str(contract.get("kind") or "approval").strip() or "approval",
            "required": required,
            "mode": "required" if required else "skip",
            "owner": "orchestrator",
            "target_owner": "runtime_os.process_runtime",
            "canonical_target_owner": "runtime_os.durability_substrate",
            "session_runtime_owner": "runtime_os.multi_agent_runtime",
            "runner": "human_gate" if required else "none",
        }

    def recovery_policy(self, *, default_max_attempts: int = 0) -> dict[str, Any]:
        contract = dict(self.recovery or {})
        declared_action = ""
        for key in ("action", "kind", "mode"):
            value = str(contract.get(key) or "").strip().lower()
            if value:
                declared_action = value
                break
        if declared_action == "recovery":
            declared_action = ""
        if declared_action == "retry":
            action = "retry"
            supported = True
        elif declared_action == "retry_step":
            action = "retry_step"
            supported = True
        elif declared_action in {"resume", "workflow_resume"}:
            action = "resume"
            supported = True
        elif declared_action in {"repair", "repair_branch"}:
            action = "repair"
            supported = True
        elif declared_action in {"disabled", "none", "skip", "reject"}:
            action = "disabled"
            supported = True
        elif declared_action:
            action = declared_action
            supported = False
        else:
            enabled = _coerce_bool(contract.get("enabled"), default=True)
            action = "retry" if enabled else "disabled"
            supported = True

        resume_from = ""
        for key in ("resume_from", "step_id", "cursor", "active_step"):
            value = str(contract.get(key) or "").strip()
            if value:
                resume_from = value
                break

        max_attempts = default_max_attempts
        for key in ("max_attempts", "retry_budget", "max_retries"):
            raw = contract.get(key)
            if raw in ("", None):
                continue
            try:
                max_attempts = max(0, int(raw))
            except Exception:
                continue
            break

        enabled = supported and action in {"retry", "retry_step", "repair", "resume"}
        runner = "none"
        if enabled:
            if action == "retry":
                runner = "node_retry_loop"
            elif action == "repair":
                runner = "branch_repair_loop"
            else:
                runner = "workflow_resume_loop"
        return {
            **contract,
            "action": action,
            "enabled": enabled,
            "supported": supported,
            "max_attempts": max(0, int(max_attempts or 0)),
            "resume_from": resume_from,
            "owner": "orchestrator",
            "target_owner": "runtime_os.process_runtime",
            "canonical_target_owner": "runtime_os.durability_substrate",
            "session_runtime_owner": "runtime_os.multi_agent_runtime",
            "runner": runner,
        }

    def execution_boundary(self) -> dict[str, Any]:
        selected_engine = self.selected_engine()
        execution_owner = "research" if selected_engine == "research_bridge" else "runtime_os.agent_runtime"
        return {
            "vm_role": "dispatch_router",
            "control_plane": "orchestrator",
            "runtime_namespace": "runtime_os",
            "governance_owner": "orchestrator",
            "governance_target_owner": "runtime_os.process_runtime",
            "selected_engine": selected_engine,
            "execution_owner": execution_owner,
            "agent_runtime_owner": "runtime_os.agent_runtime",
            "protocol_owner": "runtime_os.multi_agent_protocols",
            "session_runtime_owner": "runtime_os.multi_agent_runtime",
            "durability_owner": "runtime_os.durability_substrate",
            "process_runtime_owner": "runtime_os.process_runtime",
            "collaboration_owner": "runtime_os.process_runtime",
            "compat_execution_owner": "agents_os" if selected_engine != "research_bridge" else "",
            "compat_collaboration_owner": "multi_agents_os",
        }

    def selected_engine(self) -> str:
        if self.subworkflow_kind == "research_scenario":
            return "research_bridge"
        if self.driver_kind == "research_scenario":
            return "research_bridge"
        if self.node_kind == "research_scenario":
            return "research_bridge"
        return "execution_bridge"
