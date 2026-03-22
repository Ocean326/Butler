from __future__ import annotations

from dataclasses import asdict, dataclass, field
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


@dataclass(slots=True)
class WorkflowIR:
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
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "WorkflowIR":
        if not isinstance(payload, Mapping):
            return cls()
        data = dict(payload)
        data["workflow_template"] = _as_dict(payload.get("workflow_template") if isinstance(payload.get("workflow_template"), Mapping) else {})
        data["workflow_inputs"] = _as_dict(payload.get("workflow_inputs") if isinstance(payload.get("workflow_inputs"), Mapping) else {})
        data["verification"] = _as_dict(payload.get("verification") if isinstance(payload.get("verification"), Mapping) else {})
        data["approval"] = _as_dict(payload.get("approval") if isinstance(payload.get("approval"), Mapping) else {})
        data["recovery"] = _as_dict(payload.get("recovery") if isinstance(payload.get("recovery"), Mapping) else {})
        data["metadata"] = _as_dict(payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {})
        data["role_bindings"] = _as_list_of_dicts(payload.get("role_bindings") if isinstance(payload.get("role_bindings"), list) else [])
        return cls(**data)

    def to_runtime_plan_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.workflow_template:
            payload["workflow_template"] = dict(self.workflow_template)
        elif self.template_id:
            payload["workflow_template_id"] = self.template_id
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
        return payload

    def summary(self) -> dict[str, Any]:
        return {
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
            "verification": dict(self.verification),
            "approval": dict(self.approval),
            "recovery": dict(self.recovery),
        }
