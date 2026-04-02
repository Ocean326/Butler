from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Mapping

from butler_main.runtime_os.agent_runtime import (
    AgentRuntime,
    CapabilityBinding,
    CapabilityRegistry,
    ExecutionContext,
    OutputBundle,
    TextBlock,
    cli_runner,
)
from butler_main.runtime_os.process_runtime import (
    ExecutionReceipt,
    ExecutionRuntime,
    SubworkflowCapability,
)
from .runtime_policy_adapter import ButlerRuntimePolicyAdapter

if TYPE_CHECKING:
    from .interfaces.campaign_service import OrchestratorCampaignService


ORCHESTRATOR_EXECUTION_TIMEOUT_SECONDS_DEFAULT = 900
ORCHESTRATOR_EXECUTION_CAPABILITY_ID = "orchestrator.branch.execute"


def _orchestrator_cfg(config_snapshot: dict | None) -> dict[str, Any]:
    raw = (config_snapshot or {}).get("orchestrator") or {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _execution_timeout_seconds(config_snapshot: dict | None) -> int:
    orchestrator_cfg = _orchestrator_cfg(config_snapshot)
    raw = orchestrator_cfg.get("execution_timeout_seconds", orchestrator_cfg.get("branch_timeout_seconds", ORCHESTRATOR_EXECUTION_TIMEOUT_SECONDS_DEFAULT))
    try:
        value = int(raw)
    except Exception:
        value = ORCHESTRATOR_EXECUTION_TIMEOUT_SECONDS_DEFAULT
    return max(30, min(7200, value))


def _default_model_name(config_snapshot: dict | None) -> str:
    orchestrator_cfg = _orchestrator_cfg(config_snapshot)
    if str(orchestrator_cfg.get("default_model") or "").strip():
        return str(orchestrator_cfg.get("default_model") or "").strip()
    cli_runtime = (config_snapshot or {}).get("cli_runtime") or {}
    defaults = cli_runtime.get("defaults") if isinstance(cli_runtime, Mapping) else {}
    model = str((defaults or {}).get("model") or "").strip()
    return model or "auto"


class OrchestratorCLIRuntime(AgentRuntime):
    """Thin runtime adapter that binds orchestrator branches to the existing CLI runner."""

    def __init__(
        self,
        *,
        workspace: str,
        config_snapshot: dict | None = None,
        runtime_policy: ButlerRuntimePolicyAdapter | None = None,
        timeout_seconds: int | None = None,
        run_prompt_fn: Callable[..., tuple[str, bool]] | None = None,
    ) -> None:
        self._workspace = str(workspace or "").strip()
        self._config_snapshot = dict(config_snapshot or {})
        self._runtime_policy = runtime_policy or ButlerRuntimePolicyAdapter()
        self._timeout_seconds = int(timeout_seconds or _execution_timeout_seconds(config_snapshot))
        self._run_prompt_fn = run_prompt_fn or cli_runner.run_prompt

    def execute(self, context: ExecutionContext) -> ExecutionReceipt:
        request = context.request
        prompt = self._prompt_text(request)
        branch_payload = self._branch_payload(request)
        try:
            decision = self._runtime_policy.route_branch(
                self._workspace,
                branch_payload,
                _default_model_name(self._config_snapshot),
                self._config_snapshot,
            )
            output_text, ok = self._run_prompt_fn(
                prompt,
                self._workspace,
                self._timeout_seconds,
                self._config_snapshot,
                decision.runtime_request,
            )
        except Exception as exc:
            return self._failed_receipt(
                request,
                summary=f"branch execution failed: {type(exc).__name__}: {exc}",
                metadata={
                    "workspace": self._workspace,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )

        clean_output = str(output_text or "").strip()
        status = "completed" if ok else "failed"
        summary = clean_output or ("branch executed" if ok else "branch execution failed")
        runtime_profile = dict(decision.runtime_profile or {})
        metadata = {
            "workspace": self._workspace,
            "manager_note": str(decision.manager_note or "").strip(),
            "cli": str(runtime_profile.get("cli") or decision.runtime_request.get("cli") or "").strip(),
            "model": str(runtime_profile.get("model") or decision.runtime_request.get("model") or "").strip(),
            "reasoning_effort": str(runtime_profile.get("reasoning_effort") or "").strip(),
            "why": str(runtime_profile.get("why") or "").strip(),
            "runtime_request": dict(decision.runtime_request or {}),
            "runtime_profile": runtime_profile,
        }
        bundle = OutputBundle(
            status="ready" if ok else "failed",
            summary=summary[:500],
            text_blocks=[TextBlock(text=clean_output)] if clean_output else [],
            metadata={"runtime_profile": runtime_profile},
        )
        return ExecutionReceipt(
            invocation_id=request.invocation.invocation_id,
            workflow_id=request.workflow.workflow_id if request.workflow is not None else "",
            route=request.route,
            projection=request.workflow,
            agent_id=request.agent_spec.agent_id if request.agent_spec is not None else "",
            status=status,
            summary=summary[:500],
            output_bundle=bundle,
            metadata=metadata,
        )

    @staticmethod
    def _prompt_text(request) -> str:
        text = str(request.invocation.user_text or "").strip()
        if text:
            return text
        return str(request.invocation.subject_id or request.invocation.entrypoint or "orchestrator branch").strip()

    @staticmethod
    def _branch_payload(request) -> dict[str, Any]:
        metadata = dict(request.metadata or {})
        invocation_metadata = dict(request.invocation.metadata or {})
        workflow_ir = metadata.get("workflow_ir")
        workflow_ir_map = dict(workflow_ir) if isinstance(workflow_ir, Mapping) else {}
        workflow_ir_metadata = workflow_ir_map.get("metadata")
        workflow_ir_meta_map = dict(workflow_ir_metadata) if isinstance(workflow_ir_metadata, Mapping) else {}
        runtime_profile = metadata.get("runtime_profile")
        runtime_profile_map = dict(runtime_profile) if isinstance(runtime_profile, Mapping) else {}
        if not runtime_profile_map:
            candidate = workflow_ir_meta_map.get("runtime_profile")
            runtime_profile_map = dict(candidate) if isinstance(candidate, Mapping) else {}
        return {
            "branch_id": str(metadata.get("branch_id") or invocation_metadata.get("branch_id") or "").strip(),
            "node_id": str(metadata.get("node_id") or invocation_metadata.get("node_id") or "").strip(),
            "process_role": str(workflow_ir_map.get("worker_profile") or "").strip(),
            "execution_kind": str(metadata.get("node_kind") or workflow_ir_map.get("node_kind") or "").strip(),
            "team_id": str(workflow_ir_map.get("workflow_session_id") or "").strip(),
            "capability_type": "analysis" if str(workflow_ir_map.get("workflow_kind") or "").strip() not in {"", "mission"} else "",
            "runtime_profile": runtime_profile_map,
        }

    @staticmethod
    def _failed_receipt(request, *, summary: str, metadata: dict[str, Any]) -> ExecutionReceipt:
        return ExecutionReceipt(
            invocation_id=request.invocation.invocation_id,
            workflow_id=request.workflow.workflow_id if request.workflow is not None else "",
            route=request.route,
            projection=request.workflow,
            agent_id=request.agent_spec.agent_id if request.agent_spec is not None else "",
            status="failed",
            summary=summary[:500],
            metadata=metadata,
        )


class OrchestratorCampaignRuntime(AgentRuntime):
    """Run campaign-supervisor branches through the campaign domain service."""

    _TERMINAL_STATUSES = {"completed", "failed", "stopped"}

    def __init__(
        self,
        *,
        workspace: str,
        campaign_service: "OrchestratorCampaignService" | None = None,
    ) -> None:
        self._workspace = str(workspace or "").strip()
        if campaign_service is None:
            from .interfaces.campaign_service import OrchestratorCampaignService

            campaign_service = OrchestratorCampaignService()
        self._campaign_service = campaign_service

    def execute(self, context: ExecutionContext) -> ExecutionReceipt:
        request = context.request
        campaign_id = self._campaign_id_from_request(request)
        if not campaign_id:
            return self._failed_receipt(
                request,
                summary="campaign runtime missing campaign_id",
                metadata={"workspace": self._workspace},
            )
        try:
            payload = self._campaign_service.get_campaign_status(self._workspace, campaign_id)
            payload = self._resume_until_terminal(campaign_id=campaign_id, payload=payload)
        except Exception as exc:
            return self._failed_receipt(
                request,
                summary=f"campaign runtime failed: {type(exc).__name__}: {exc}",
                metadata={
                    "workspace": self._workspace,
                    "campaign_id": campaign_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )

        status = self._receipt_status_from_campaign(payload)
        summary = self._campaign_summary(payload)
        metadata = {
            "workspace": self._workspace,
            "campaign_id": campaign_id,
            "campaign_status": str(payload.get("status") or "").strip(),
            "campaign_phase": str(payload.get("current_phase") or "").strip(),
            "campaign_next_phase": str(payload.get("next_phase") or "").strip(),
            "campaign_iteration": int(payload.get("current_iteration") or 0),
            "campaign_runtime": dict((payload.get("metadata") or {}).get("campaign_runtime") or {}),
        }
        bundle = OutputBundle(
            status="ready" if status == "completed" else "failed",
            summary=summary[:500],
            text_blocks=[TextBlock(text=summary)],
            metadata={"campaign_status": str(payload.get("status") or "").strip()},
        )
        return ExecutionReceipt(
            invocation_id=request.invocation.invocation_id,
            workflow_id=request.workflow.workflow_id if request.workflow is not None else "",
            route=request.route,
            projection=request.workflow,
            agent_id=request.agent_spec.agent_id if request.agent_spec is not None else "",
            status=status,
            summary=summary[:500],
            output_bundle=bundle,
            metadata=metadata,
        )

    def _resume_until_terminal(self, *, campaign_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        current = dict(payload or {})
        remaining = self._remaining_iterations(current)
        while remaining > 0 and str(current.get("status") or "").strip() not in self._TERMINAL_STATUSES:
            current = dict(self._campaign_service.resume_campaign(self._workspace, campaign_id) or {})
            remaining -= 1
        if str(current.get("status") or "").strip() in self._TERMINAL_STATUSES:
            return current
        raise RuntimeError(
            f"campaign remained active after iteration budget exhausted: {campaign_id}"
        )

    @staticmethod
    def _remaining_iterations(payload: Mapping[str, Any]) -> int:
        current_iteration = max(0, int(payload.get("current_iteration") or 0))
        working_contract = dict(payload.get("working_contract") or {})
        iteration_budget = dict(working_contract.get("iteration_budget") or {})
        max_iterations = int(iteration_budget.get("max_iterations") or 0)
        if max_iterations <= 0:
            spec_payload = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
            spec = dict((spec_payload or {}).get("spec") or {})
            iteration_budget = dict(spec.get("iteration_budget") or {})
            max_iterations = int(iteration_budget.get("max_iterations") or 3)
        return max(2, max_iterations - current_iteration + 1)

    @staticmethod
    def _campaign_id_from_request(request) -> str:
        metadata = dict(request.metadata or {})
        workflow_ir = metadata.get("workflow_ir")
        workflow_ir_map = dict(workflow_ir) if isinstance(workflow_ir, Mapping) else {}
        workflow_inputs = workflow_ir_map.get("workflow_inputs")
        workflow_inputs_map = dict(workflow_inputs) if isinstance(workflow_inputs, Mapping) else {}
        branch_input = metadata.get("branch_input")
        branch_input_map = dict(branch_input) if isinstance(branch_input, Mapping) else {}
        branch_workflow_inputs = branch_input_map.get("workflow_inputs")
        branch_workflow_inputs_map = dict(branch_workflow_inputs) if isinstance(branch_workflow_inputs, Mapping) else {}
        for source in (branch_workflow_inputs_map, workflow_inputs_map, branch_input_map):
            campaign_id = str(source.get("campaign_id") or "").strip()
            if campaign_id:
                return campaign_id
        return ""

    @staticmethod
    def _campaign_summary(payload: Mapping[str, Any]) -> str:
        return (
            "campaign "
            f"{str(payload.get('campaign_id') or '').strip()} "
            f"status={str(payload.get('status') or '').strip() or '-'} "
            f"phase={str(payload.get('current_phase') or '').strip() or '-'} "
            f"next={str(payload.get('next_phase') or '').strip() or '-'} "
            f"iteration={int(payload.get('current_iteration') or 0)}"
        )

    @staticmethod
    def _receipt_status_from_campaign(payload: Mapping[str, Any]) -> str:
        status = str(payload.get("status") or "").strip().lower()
        if status == "completed":
            return "completed"
        if status == "stopped":
            return "cancelled"
        return "failed"

    @staticmethod
    def _failed_receipt(request, *, summary: str, metadata: dict[str, Any]) -> ExecutionReceipt:
        return ExecutionReceipt(
            invocation_id=request.invocation.invocation_id,
            workflow_id=request.workflow.workflow_id if request.workflow is not None else "",
            route=request.route,
            projection=request.workflow,
            agent_id=request.agent_spec.agent_id if request.agent_spec is not None else "",
            status="failed",
            summary=summary[:500],
            metadata=metadata,
        )


def build_orchestrator_execution_runtime(
    *,
    workspace: str,
    config_snapshot: dict | None = None,
    runtime_policy: ButlerRuntimePolicyAdapter | None = None,
    timeout_seconds: int | None = None,
    run_prompt_fn: Callable[..., tuple[str, bool]] | None = None,
    capability_resolver: CapabilityRegistry | None = None,
) -> ExecutionRuntime:
    cli_runtime = OrchestratorCLIRuntime(
        workspace=workspace,
        config_snapshot=config_snapshot,
        runtime_policy=runtime_policy,
        timeout_seconds=timeout_seconds,
        run_prompt_fn=run_prompt_fn,
    )
    registry = capability_resolver or CapabilityRegistry()
    if not registry.resolve(invocation=None, workflow_kind=""):
        registry.register(
            CapabilityBinding(
                capability=SubworkflowCapability(
                    capability_id=ORCHESTRATOR_EXECUTION_CAPABILITY_ID,
                    name="Orchestrator Branch Execution",
                    supported_entrypoints=["orchestrator_branch"],
                    required_policies=["approval", "verification", "recovery"],
                    metadata={"source": "orchestrator.runtime_adapter"},
                ),
                agent_id="orchestrator.execution.kernel",
                agent_spec_id="orchestrator.execution.kernel",
                priority=100,
                default_route_key="orchestrator_branch",
                metadata={"executor": "orchestrator_cli_runtime"},
            )
        )

    def _handler(context: ExecutionContext, *, binding, contract):
        receipt = cli_runtime.execute(context)
        metadata = {
            **dict(receipt.metadata or {}),
            "executor_runtime": "orchestrator_cli_runtime",
            "resolved_capability_id": str(
                ((contract.get("capability_resolution") or {}).get("selected") or {}).get("capability", {}).get("capability_id") or ""
            ).strip(),
        }
        return {
            "status": receipt.status,
            "summary": receipt.summary,
            "metadata": metadata,
            "output_bundle": receipt.output_bundle,
            "model_input": receipt.model_input,
        }

    return ExecutionRuntime(capability_resolver=registry, handler=_handler)


def build_orchestrator_campaign_runtime(
    *,
    workspace: str,
    campaign_service: "OrchestratorCampaignService" | None = None,
) -> OrchestratorCampaignRuntime:
    return OrchestratorCampaignRuntime(
        workspace=workspace,
        campaign_service=campaign_service,
    )
