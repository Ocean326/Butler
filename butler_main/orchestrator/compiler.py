from __future__ import annotations

from typing import Any, Mapping

from .framework_compiler import FrameworkProfileCompiler
from .models import Branch, Mission, MissionNode
from .workflow_ir import WorkflowIR


class MissionWorkflowCompiler:
    """Compile mission/node/branch facts into a stable orchestrator workflow IR."""

    def __init__(self, *, framework_compiler: FrameworkProfileCompiler | None = None) -> None:
        self._framework_compiler = framework_compiler or FrameworkProfileCompiler()

    def compile(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
    ) -> WorkflowIR:
        framework_ir = self._compile_framework_profile_if_present(
            mission=mission,
            node=node,
            branch=branch,
        )
        if framework_ir is not None:
            return framework_ir
        template_payload = self._extract_template_payload(branch=branch, node=node)
        role_bindings = self._extract_role_bindings(branch=branch, node=node)
        workflow_inputs = self._extract_mapping(branch, node, "workflow_inputs")
        template_id = str(
            template_payload.get("template_id")
            or self._first_text(branch, node, "workflow_template_id")
            or self._first_text(branch, node, "template_id")
            or ""
        ).strip()
        subworkflow_kind = self._first_text(branch, node, "subworkflow_kind")
        runtime_key = (
            self._first_text(branch, node, "runtime_key")
            or self._first_text(branch, node, "worker_profile")
            or str(branch.worker_profile or "").strip()
            or "default"
        )
        worker_profile = (
            self._first_text(branch, node, "worker_profile")
            or str(branch.worker_profile or "").strip()
            or runtime_key
        )
        agent_id = self._first_text(branch, node, "agent_id") or f"orchestrator.{runtime_key}"
        verification = self._extract_contract(branch, node, "verification")
        if not verification and dict(node.judge_spec or {}):
            verification = {
                "kind": "judge",
                "judge_spec": dict(node.judge_spec or {}),
            }
        approval = self._extract_contract(branch, node, "approval")
        recovery = self._extract_contract(branch, node, "recovery")
        workflow_session_id = self._first_text(branch, node, "workflow_session_id")
        workflow_template_id = self._first_text(branch, node, "workflow_template_id") or template_id
        workflow_kind = str(template_payload.get("kind") or "mission").strip() or "mission"
        driver_kind = "research_scenario" if subworkflow_kind == "research_scenario" or node.kind == "research_scenario" else "orchestrator_node"
        runtime_binding = self._extract_mapping(branch, node, "runtime_binding")
        runtime_binding.setdefault("runtime_key", runtime_key)
        runtime_binding.setdefault("agent_id", agent_id)
        runtime_binding.setdefault("worker_profile", worker_profile)
        input_contract = self._extract_mapping(branch, node, "input_contract") or self._extract_mapping(branch, node, "entry_contract")
        if not input_contract and isinstance(template_payload.get("input_contract"), Mapping):
            input_contract = dict(template_payload.get("input_contract") or {})
        if not input_contract and isinstance(template_payload.get("entry_contract"), Mapping):
            input_contract = dict(template_payload.get("entry_contract") or {})
        output_contract = self._extract_mapping(branch, node, "output_contract") or self._extract_mapping(branch, node, "exit_contract")
        if not output_contract and isinstance(template_payload.get("output_contract"), Mapping):
            output_contract = dict(template_payload.get("output_contract") or {})
        if not output_contract and isinstance(template_payload.get("exit_contract"), Mapping):
            output_contract = dict(template_payload.get("exit_contract") or {})
        lineage = {
            "compiler_version": "orchestrator.workflow_ir.v2",
            "mission_type": str(mission.mission_type or "").strip(),
            "mission_title": str(mission.title or "").strip(),
            "mission_priority": int(mission.priority or 0),
            "node_status": str(node.status or "").strip(),
        }
        return WorkflowIR(
            workflow_id=str(branch.branch_id or "").strip(),
            mission_id=str(mission.mission_id or "").strip(),
            node_id=str(node.node_id or "").strip(),
            branch_id=str(branch.branch_id or "").strip(),
            workflow_kind=workflow_kind,
            driver_kind=driver_kind,
            entrypoint="orchestrator",
            runtime_key=runtime_key,
            agent_id=agent_id,
            worker_profile=worker_profile,
            node_kind=str(node.kind or "").strip(),
            node_title=str(node.title or "").strip(),
            template_id=template_id,
            workflow_template=template_payload,
            role_bindings=role_bindings,
            workflow_inputs=workflow_inputs,
            workflow_session_id=workflow_session_id,
            workflow_template_id=workflow_template_id,
            subworkflow_kind=subworkflow_kind,
            research_unit_id=self._first_text(branch, node, "research_unit_id"),
            scenario_action=self._first_text(branch, node, "scenario_action"),
            verification=verification,
            approval=approval,
            recovery=recovery,
            capability_package_ref=self._first_text(branch, node, "capability_package_ref"),
            team_package_ref=self._first_text(branch, node, "team_package_ref"),
            governance_policy_ref=self._first_text(branch, node, "governance_policy_ref"),
            runtime_binding=runtime_binding,
            input_contract=input_contract,
            output_contract=output_contract,
            entry_step_id=self._first_text(branch, node, "entry_step_id") or str(template_payload.get("entry_step_id") or "").strip(),
            steps=list(template_payload.get("steps") or []),
            edges=list(template_payload.get("edges") or []),
            roles=list(template_payload.get("roles") or []),
            artifacts=list(template_payload.get("artifacts") or []),
            handoffs=list(template_payload.get("handoffs") or []),
            runtime_state={
                "workflow_session_id": workflow_session_id,
                "mission_id": str(mission.mission_id or "").strip(),
                "node_id": str(node.node_id or "").strip(),
                "branch_id": str(branch.branch_id or "").strip(),
                "status": "compiled",
                "workflow_inputs": workflow_inputs,
                "runtime_key": runtime_key,
                "agent_id": agent_id,
                "worker_profile": worker_profile,
                "node_kind": str(node.kind or "").strip(),
                "subworkflow_kind": subworkflow_kind,
                "research_unit_id": self._first_text(branch, node, "research_unit_id"),
                "scenario_action": self._first_text(branch, node, "scenario_action"),
            },
            observability={
                "tags": [item for item in [workflow_kind, str(node.kind or "").strip(), worker_profile, subworkflow_kind] if item],
                "lineage": lineage,
            },
            metadata={
                **lineage,
                "field_taxonomy": {
                    "compile_time": [
                        "workflow",
                        "steps",
                        "edges",
                        "roles",
                        "artifacts",
                        "handoffs",
                        "verification",
                        "approval",
                        "recovery",
                        "capability_package_ref",
                        "team_package_ref",
                        "governance_policy_ref",
                        "runtime_binding",
                        "input_contract",
                        "output_contract",
                    ],
                    "runtime": [
                        "workflow_session_id",
                        "workflow_inputs",
                        "runtime_key",
                        "agent_id",
                        "worker_profile",
                        "subworkflow_kind",
                        "research_unit_id",
                        "scenario_action",
                    ],
                    "observability": [
                        "metadata",
                        "lineage",
                        "tags",
                        "gate_policies",
                        "execution_boundary",
                    ],
                },
            },
        )

    def compile_framework_profile(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        profile_id: str = "",
        profile_payload: Mapping[str, Any] | None = None,
    ) -> WorkflowIR:
        return self._framework_compiler.compile(
            mission=mission,
            node=node,
            branch=branch,
            profile_id=profile_id,
            profile_payload=profile_payload,
        )

    def _compile_framework_profile_if_present(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
    ) -> WorkflowIR | None:
        if self._extract_mapping(branch, node, "workflow_template"):
            return None
        profile_payload = self._extract_mapping(branch, node, "framework_profile")
        profile_id = (
            str(profile_payload.get("profile_id") or profile_payload.get("framework_profile_id") or "").strip()
            or self._first_text(branch, node, "framework_profile_id")
            or self._first_text(branch, node, "framework_id")
        )
        if not profile_id and not profile_payload:
            return None
        return self.compile_framework_profile(
            mission=mission,
            node=node,
            branch=branch,
            profile_id=profile_id,
            profile_payload=profile_payload,
        )

    @staticmethod
    def _sources(branch: Branch, node: MissionNode) -> tuple[Mapping[str, Any], ...]:
        return (
            dict(branch.input_payload or {}),
            dict(branch.metadata or {}),
            dict(node.runtime_plan or {}),
            dict(node.metadata or {}),
        )

    def _first_text(self, branch: Branch, node: MissionNode, key: str) -> str:
        for source in self._sources(branch, node):
            value = str(source.get(key) or "").strip()
            if value:
                return value
        return ""

    def _extract_mapping(self, branch: Branch, node: MissionNode, key: str) -> dict[str, Any]:
        for source in self._sources(branch, node):
            payload = source.get(key)
            if isinstance(payload, Mapping):
                return dict(payload)
        return {}

    def _extract_contract(self, branch: Branch, node: MissionNode, key: str) -> dict[str, Any]:
        payload = self._extract_mapping(branch, node, key)
        if not payload:
            return {}
        contract = dict(payload)
        contract.setdefault("kind", key)
        return contract

    def _extract_role_bindings(self, *, branch: Branch, node: MissionNode) -> list[dict[str, Any]]:
        for source in self._sources(branch, node):
            payload = source.get("role_bindings")
            if isinstance(payload, list):
                out: list[dict[str, Any]] = []
                for item in payload:
                    if isinstance(item, Mapping):
                        out.append(dict(item))
                if out:
                    return out
        return []

    def _extract_template_payload(self, *, branch: Branch, node: MissionNode) -> dict[str, Any]:
        for source in self._sources(branch, node):
            raw = source.get("workflow_template")
            if isinstance(raw, Mapping):
                return dict(raw)
        template_id = self._first_text(branch, node, "workflow_template_id") or self._first_text(branch, node, "template_id")
        if not template_id:
            return {}
        roles = self._extract_list_mapping(branch, node, "workflow_roles")
        steps = self._extract_list_mapping(branch, node, "workflow_steps")
        return {
            "template_id": template_id,
            "kind": self._first_text(branch, node, "workflow_kind") or "mission",
            "entry_step_id": self._first_text(branch, node, "entry_step_id"),
            "roles": roles,
            "steps": steps,
            "edges": self._extract_list_mapping(branch, node, "workflow_edges"),
            "artifacts": self._extract_list_mapping(branch, node, "workflow_artifacts"),
            "handoffs": self._extract_list_mapping(branch, node, "workflow_handoffs"),
            "input_contract": self._extract_mapping(branch, node, "input_contract"),
            "output_contract": self._extract_mapping(branch, node, "output_contract"),
            "entry_contract": self._extract_mapping(branch, node, "entry_contract"),
            "exit_contract": self._extract_mapping(branch, node, "exit_contract"),
            "capability_package_ref": self._first_text(branch, node, "capability_package_ref"),
            "team_package_ref": self._first_text(branch, node, "team_package_ref"),
            "governance_policy_ref": self._first_text(branch, node, "governance_policy_ref"),
            "runtime_binding": self._extract_mapping(branch, node, "runtime_binding"),
            "defaults": self._extract_mapping(branch, node, "workflow_defaults"),
            "metadata": self._extract_mapping(branch, node, "workflow_metadata"),
        }

    def _extract_list_mapping(self, branch: Branch, node: MissionNode, key: str) -> list[dict[str, Any]]:
        for source in self._sources(branch, node):
            payload = source.get(key)
            if isinstance(payload, list):
                out: list[dict[str, Any]] = []
                for item in payload:
                    if isinstance(item, Mapping):
                        out.append(dict(item))
                if out:
                    return out
        return []
