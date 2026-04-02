from __future__ import annotations

from dataclasses import dataclass

from .application import OrchestratorService
from .branch_store import FileBranchStore
from .event_store import FileLedgerEventStore
from .execution_bridge import OrchestratorExecutionBridge
from .mission_store import FileMissionStore
from .paths import ORCHESTRATOR_RUN_DIR_REL, resolve_butler_root
from .research_bridge import OrchestratorResearchBridge
from .runtime_adapter import build_orchestrator_campaign_runtime, build_orchestrator_execution_runtime
from .workflow_vm import OrchestratorWorkflowVM


@dataclass(slots=True, frozen=True)
class OrchestratorRuntimeAssembly:
    service: OrchestratorService
    execution_bridge: OrchestratorExecutionBridge
    research_bridge: OrchestratorResearchBridge
    workflow_vm: OrchestratorWorkflowVM


def resolve_orchestrator_root(workspace: str) -> str:
    return str((resolve_butler_root(workspace) / ORCHESTRATOR_RUN_DIR_REL).resolve())


def build_orchestrator_service_for_workspace(workspace: str) -> OrchestratorService:
    root = resolve_orchestrator_root(workspace)
    return OrchestratorService(
        mission_store=FileMissionStore(root),
        event_store=FileLedgerEventStore(root),
        branch_store=FileBranchStore(root),
    )


def build_orchestrator_runtime_stack_for_workspace(
    workspace: str,
    *,
    config_snapshot: dict | None = None,
) -> OrchestratorRuntimeAssembly:
    service = build_orchestrator_service_for_workspace(workspace)
    cli_runtime = build_orchestrator_execution_runtime(workspace=workspace, config_snapshot=config_snapshot)
    from .interfaces.campaign_service import OrchestratorCampaignService

    campaign_runtime = build_orchestrator_campaign_runtime(
        workspace=workspace,
        campaign_service=OrchestratorCampaignService(),
    )

    def _runtime_resolver(spec):
        runtime_key = str(getattr(spec, "runtime_key", "") or "").strip()
        if runtime_key == "campaign.supervisor":
            return campaign_runtime
        return cli_runtime

    execution_bridge = OrchestratorExecutionBridge(runtime_resolver=_runtime_resolver)
    research_bridge = OrchestratorResearchBridge()
    workflow_vm = OrchestratorWorkflowVM(
        execution_bridge=execution_bridge,
        research_bridge=research_bridge,
    )
    return OrchestratorRuntimeAssembly(
        service=service,
        execution_bridge=execution_bridge,
        research_bridge=research_bridge,
        workflow_vm=workflow_vm,
    )
