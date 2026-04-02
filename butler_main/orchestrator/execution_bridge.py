from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from butler_main.runtime_os.agent_runtime import (
    AgentCapabilities,
    AgentProfile,
    AgentRuntime,
    AgentSpec,
    ExecutionContext,
    Invocation,
    OutputBundle,
    PromptProfile,
    RouteProjection,
    RuntimeRequest,
    WorkflowProjection,
    normalize_run_status,
)
from butler_main.runtime_os.process_runtime import ExecutionReceipt, ProcessExecutionOutcome, RuntimeVerdict

from .compiler import MissionWorkflowCompiler
from .models import Branch, Mission, MissionNode
from .runtime_adapter import ORCHESTRATOR_EXECUTION_CAPABILITY_ID
from .workflow_ir import WorkflowIR


@dataclass(slots=True, frozen=True)
class BranchExecutionOutcome:
    branch_id: str
    receipt: ExecutionReceipt
    process_outcome: ProcessExecutionOutcome

    @property
    def status(self) -> str:
        return self.process_outcome.status

    @property
    def terminal(self) -> bool:
        return self.process_outcome.terminal

    @property
    def ok(self) -> bool:
        return self.process_outcome.ok

    @property
    def result_ref(self) -> str:
        return self.process_outcome.result_ref

    @property
    def result_payload(self) -> dict[str, object]:
        return dict(self.process_outcome.result_payload)

    @property
    def runtime_verdict(self) -> RuntimeVerdict:
        return self.process_outcome.to_runtime_verdict()


class OrchestratorExecutionBridge:
    """Bridge orchestrator branches onto the agent runtime contract."""

    def __init__(
        self,
        *,
        runtime: AgentRuntime | None = None,
        runtime_resolver: Callable[[AgentSpec], AgentRuntime] | None = None,
        workflow_compiler: MissionWorkflowCompiler | None = None,
    ) -> None:
        self._runtime = runtime
        self._runtime_resolver = runtime_resolver
        self._workflow_compiler = workflow_compiler or MissionWorkflowCompiler()

    def execute_and_record(
        self,
        service,
        *,
        mission_id: str,
        branch_ids: list[str],
    ) -> list[BranchExecutionOutcome]:
        outcomes: list[BranchExecutionOutcome] = []
        for branch_id in branch_ids:
            mission = service.get_mission(mission_id)
            if mission is None:
                break
            branch = service.get_branch(branch_id)
            if branch is None or branch.mission_id != mission_id:
                continue
            node = mission.node_by_id(branch.node_id)
            if node is None:
                continue
            outcome = self.execute_branch(mission, node, branch)
            outcomes.append(outcome)
            if not outcome.terminal:
                continue
            service.record_branch_result(
                mission_id,
                branch.branch_id,
                process_outcome=outcome.process_outcome,
            )
        return outcomes

    def execute_branch(self, mission: Mission, node: MissionNode, branch: Branch) -> BranchExecutionOutcome:
        workflow_ir = self._resolve_workflow_ir(mission, node, branch)
        spec = self._build_agent_spec(node, workflow_ir)
        runtime = self._resolve_runtime(spec)
        request = self._build_runtime_request(mission, node, branch, spec, workflow_ir)
        context = ExecutionContext(request=request)
        try:
            receipt = runtime.execute(context)
        except Exception as exc:
            receipt = ExecutionReceipt(
                invocation_id=request.invocation.invocation_id,
                workflow_id=mission.mission_id,
                route=request.route,
                projection=request.workflow,
                agent_id=spec.agent_id,
                status="failed",
                summary=f"branch execution failed: {type(exc).__name__}: {exc}",
                metadata={
                    "mission_id": mission.mission_id,
                    "node_id": node.node_id,
                    "branch_id": branch.branch_id,
                    "worker_profile": branch.worker_profile,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
        status = normalize_run_status(getattr(receipt, "status", "pending") or "pending")
        terminal = status in {"completed", "failed", "cancelled", "stale"}
        ok = status == "completed"
        result_ref = str(receipt.execution_id or branch.branch_id)
        result_payload = self._build_result_payload(mission, node, branch, spec, receipt, status, workflow_ir)
        process_outcome = ProcessExecutionOutcome(
            status=status,
            terminal=terminal,
            result_ok=ok,
            result_ref=result_ref,
            result_payload=result_payload,
            metadata={
                "bridge": "execution_bridge",
                "receipt_status": status,
                "execution_id": str(receipt.execution_id or "").strip(),
                "summary": str(receipt.summary or "").strip(),
                "execution_phase": str((receipt.metadata or {}).get("execution_phase") or "").strip(),
            },
        )
        return BranchExecutionOutcome(branch_id=branch.branch_id, receipt=receipt, process_outcome=process_outcome)

    def _resolve_runtime(self, spec: AgentSpec) -> AgentRuntime:
        if self._runtime_resolver is not None:
            return self._runtime_resolver(spec)
        if self._runtime is not None:
            return self._runtime
        raise RuntimeError("orchestrator execution bridge requires a runtime or runtime_resolver")

    def _build_agent_spec(self, node: MissionNode, workflow_ir: WorkflowIR) -> AgentSpec:
        runtime_key = str(workflow_ir.runtime_key or "default").strip() or "default"
        profile_id = str(node.runtime_plan.get("profile_id") or node.kind or "orchestrator.branch").strip() or "orchestrator.branch"
        prompt_profile = PromptProfile(
            profile_id=profile_id,
            display_name=node.title or node.kind or "Orchestrator Branch",
            metadata={"worker_profile": workflow_ir.worker_profile, "node_kind": node.kind},
        )
        profile = AgentProfile(
            profile_id=profile_id,
            prompt_profile=prompt_profile,
            description=f"orchestrator branch profile for {node.kind or 'task'}",
            metadata={"worker_profile": workflow_ir.worker_profile, "node_id": node.node_id},
        )
        return AgentSpec(
            agent_id=str(workflow_ir.agent_id or f"orchestrator.{runtime_key}").strip(),
            profile=profile,
            capabilities=AgentCapabilities(
                supported_workflow_kinds=("mission",),
                extras={"worker_profile": workflow_ir.worker_profile, "node_kind": node.kind},
            ),
            runtime_key=runtime_key,
            metadata={"worker_profile": workflow_ir.worker_profile, "node_id": node.node_id},
        )

    def _build_runtime_request(
        self,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        spec: AgentSpec,
        workflow_ir: WorkflowIR,
    ) -> RuntimeRequest:
        current_step_id = self._resolve_current_step_id(node=node, workflow_ir=workflow_ir)
        invocation = Invocation(
            entrypoint="orchestrator_branch",
            channel="backend",
            session_id=mission.mission_id,
            actor_id="orchestrator",
            user_text=self._build_user_text(mission, node),
            subject_id=node.node_id,
            metadata={
                "mission_id": mission.mission_id,
                "mission_type": mission.mission_type,
                "mission_title": mission.title,
                "node_id": node.node_id,
                "node_kind": node.kind,
                "branch_id": branch.branch_id,
                "worker_profile": workflow_ir.worker_profile,
                "workflow_ir": workflow_ir.summary(),
            },
        )
        route = RouteProjection(
            route_key="orchestrator_branch",
            workflow_kind=workflow_ir.workflow_kind or "mission",
            target_agent_id=spec.agent_id,
            capability_id=ORCHESTRATOR_EXECUTION_CAPABILITY_ID,
            reason=f"mission={mission.mission_id};node={node.node_id};branch={branch.branch_id}",
            metadata={
                "branch_id": branch.branch_id,
                "node_id": node.node_id,
                "workflow_id": workflow_ir.workflow_id,
                "workflow_session_id": workflow_ir.workflow_session_id,
                "declared_capability_ids": self._declared_capability_ids(workflow_ir),
            },
        )
        workflow = WorkflowProjection(
            workflow_id=workflow_ir.workflow_id or mission.mission_id,
            workflow_kind=workflow_ir.workflow_kind or "mission",
            invocation_id=invocation.invocation_id,
            status="running",
            route=route,
            agent_id=spec.agent_id,
            agent_spec_id=spec.spec_id,
            current_step_id=current_step_id,
            required_capability_ids=[ORCHESTRATOR_EXECUTION_CAPABILITY_ID],
            metadata={
                "branch_id": branch.branch_id,
                "node_kind": node.kind,
                "workflow_session_id": workflow_ir.workflow_session_id,
                "template_id": workflow_ir.workflow_template_id or workflow_ir.template_id,
                "entry_step_id": current_step_id,
                "workflow_template": dict(workflow_ir.workflow_template or {}),
                "declared_capability_ids": self._declared_capability_ids(workflow_ir),
                "verification": dict(workflow_ir.verification),
                "approval": dict(workflow_ir.approval),
                "recovery": dict(workflow_ir.recovery),
            },
        )
        return RuntimeRequest(
            invocation=invocation,
            agent_spec=spec,
            route=route,
            workflow=workflow,
            metadata={
                "mission_id": mission.mission_id,
                "node_id": node.node_id,
                "branch_id": branch.branch_id,
                "current_step_id": current_step_id,
                "entry_step_id": current_step_id,
                "branch_input": dict(branch.input_payload or {}),
                "workflow_ir": workflow_ir.to_dict(),
            },
        )

    @staticmethod
    def _resolve_current_step_id(*, node: MissionNode, workflow_ir: WorkflowIR) -> str:
        current_step_id = str(workflow_ir.entry_step_id or "").strip()
        if current_step_id:
            return current_step_id
        for item in list(workflow_ir.steps or []):
            if not isinstance(item, dict):
                continue
            step_id = str(item.get("step_id") or item.get("id") or "").strip()
            if step_id:
                return step_id
        template = dict(workflow_ir.workflow_template or {})
        steps = template.get("steps")
        if isinstance(steps, list):
            for item in steps:
                if not isinstance(item, dict):
                    continue
                step_id = str(item.get("step_id") or item.get("id") or "").strip()
                if step_id:
                    return step_id
        return str(node.node_id or "").strip()

    @staticmethod
    def _declared_capability_ids(workflow_ir: WorkflowIR) -> list[str]:
        capability_ids: list[str] = []
        for item in list(workflow_ir.role_bindings or []):
            if not isinstance(item, dict):
                continue
            capability_id = str(item.get("capability_id") or "").strip()
            if capability_id:
                capability_ids.append(capability_id)
        for item in list(workflow_ir.roles or []):
            if not isinstance(item, dict):
                continue
            capability_id = str(item.get("capability_id") or item.get("capability") or "").strip()
            if capability_id:
                capability_ids.append(capability_id)
        template = dict(workflow_ir.workflow_template or {})
        roles = template.get("roles")
        if isinstance(roles, list):
            for item in roles:
                if not isinstance(item, dict):
                    continue
                capability_id = str(item.get("capability_id") or "").strip()
                if capability_id:
                    capability_ids.append(capability_id)
        deduped: list[str] = []
        seen: set[str] = set()
        for item in capability_ids:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped

    def _build_result_payload(
        self,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        spec: AgentSpec,
        receipt: ExecutionReceipt,
        status: str,
        workflow_ir: WorkflowIR,
    ) -> dict[str, object]:
        bundle = receipt.output_bundle
        metadata = dict(receipt.metadata or {})
        return {
            "status": status,
            "summary": str(receipt.summary or "").strip(),
            "agent_id": str(receipt.agent_id or spec.agent_id),
            "mission_id": mission.mission_id,
            "node_id": node.node_id,
            "branch_id": branch.branch_id,
            "worker_profile": workflow_ir.worker_profile,
            "metadata": metadata,
            "runtime_debug": self._runtime_debug_payload(spec, branch, metadata),
            "workflow_ir": workflow_ir.summary(),
            "output_bundle_summary": str(bundle.summary or "").strip() if bundle is not None else "",
            "output_text": self._bundle_text(bundle),
        }

    def _resolve_workflow_ir(self, mission: Mission, node: MissionNode, branch: Branch) -> WorkflowIR:
        payload = branch.metadata.get("workflow_ir")
        if isinstance(payload, dict) and payload:
            return WorkflowIR.from_dict(payload)
        return self._workflow_compiler.compile(mission=mission, node=node, branch=branch)

    @staticmethod
    def _runtime_debug_payload(spec: AgentSpec, branch: Branch, metadata: dict[str, object]) -> dict[str, object]:
        return {
            "agent_id": str(metadata.get("agent_id") or spec.agent_id),
            "runtime_key": str(spec.runtime_key or "").strip(),
            "worker_profile": str(branch.worker_profile or "").strip(),
            "cli": str(metadata.get("cli") or "").strip(),
            "model": str(metadata.get("model") or "").strip(),
            "reasoning_effort": str(metadata.get("reasoning_effort") or "").strip(),
            "why": str(metadata.get("why") or "").strip(),
        }

    @staticmethod
    def _build_user_text(mission: Mission, node: MissionNode) -> str:
        title = str(node.title or "").strip()
        goal = str(mission.goal or "").strip()
        if title and goal:
            return f"{title}\n\nMission goal:\n{goal}"
        if title:
            return title
        return goal or mission.title or mission.mission_type or "orchestrator branch"

    @staticmethod
    def _bundle_text(bundle: OutputBundle | None) -> str:
        if bundle is None:
            return ""
        parts = [str(block.text or "").strip() for block in bundle.text_blocks if str(block.text or "").strip()]
        return "\n\n".join(parts)
