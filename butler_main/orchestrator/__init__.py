from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from typing import Any

_BUTLER_MAIN_DIR = Path(__file__).resolve().parents[1]
_BODY_MODULE_DIR = _BUTLER_MAIN_DIR / "butler_bot_code" / "butler_bot"

if str(_BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BUTLER_MAIN_DIR))
if str(_BODY_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_BODY_MODULE_DIR))

_EXPORTS: dict[str, tuple[str, str]] = {
    "Branch": (".models", "Branch"),
    "BranchExecutionOutcome": (".execution_bridge", "BranchExecutionOutcome"),
    "CampaignService": (".interfaces", "OrchestratorCampaignService"),
    "CampaignDashboardMain": (".interfaces", "campaign_dashboard_main"),
    "ButlerMissionOrchestrator": (".interfaces", "ButlerMissionOrchestrator"),
    "FOURTH_LAYER_FORBIDDEN_DIRECT_IMPORTS": (".fourth_layer_contracts", "FOURTH_LAYER_FORBIDDEN_DIRECT_IMPORTS"),
    "FOURTH_LAYER_PORT_NAMESPACE": (".fourth_layer_contracts", "FOURTH_LAYER_PORT_NAMESPACE"),
    "FOURTH_LAYER_PORTS": (".fourth_layer_contracts", "FOURTH_LAYER_PORTS"),
    "FOURTH_LAYER_STABLE_EVIDENCE_KEYS": (".fourth_layer_contracts", "FOURTH_LAYER_STABLE_EVIDENCE_KEYS"),
    "FileBranchStore": (".branch_store", "FileBranchStore"),
    "FrameworkCatalog": (".framework_catalog", "FrameworkCatalog"),
    "FrameworkCatalogEntry": (".framework_catalog", "FrameworkCatalogEntry"),
    "FrameworkProfileCompiler": (".framework_compiler", "FrameworkProfileCompiler"),
    "FrameworkMappingBundle": (".framework_mapping", "FrameworkMappingBundle"),
    "FrameworkMappingRegistry": (".framework_mapping", "FrameworkMappingRegistry"),
    "FrameworkMappingSpec": (".framework_mapping", "FrameworkMappingSpec"),
    "FileLedgerEventStore": (".event_store", "FileLedgerEventStore"),
    "FileMissionStore": (".mission_store", "FileMissionStore"),
    "JUDGE_DECISIONS": (".judge_adapter", "JUDGE_DECISIONS"),
    "JudgeVerdict": (".judge_adapter", "JudgeVerdict"),
    "LedgerEvent": (".models", "LedgerEvent"),
    "Mission": (".models", "Mission"),
    "MissionIngressResolution": (".interfaces", "MissionIngressResolution"),
    "MissionNode": (".models", "MissionNode"),
    "MissionWorkflowCompiler": (".compiler", "MissionWorkflowCompiler"),
    "OrchestratorIngressService": (".interfaces", "OrchestratorIngressService"),
    "OrchestratorGovernanceBridge": (".runtime_bridge", "OrchestratorGovernanceBridge"),
    "OrchestratorExecutionBridge": (".execution_bridge", "OrchestratorExecutionBridge"),
    "OrchestratorCLIRuntime": (".runtime_adapter", "OrchestratorCLIRuntime"),
    "OrchestratorCampaignService": (".interfaces", "OrchestratorCampaignService"),
    "OrchestratorJudgeAdapter": (".judge_adapter", "OrchestratorJudgeAdapter"),
    "OrchestratorPolicy": (".policy", "OrchestratorPolicy"),
    "OrchestratorQueryService": (".interfaces", "OrchestratorQueryService"),
    "OrchestratorResearchBridge": (".research_bridge", "OrchestratorResearchBridge"),
    "OrchestratorRuntimeAssembly": (".workspace", "OrchestratorRuntimeAssembly"),
    "OrchestratorScheduler": (".scheduler", "OrchestratorScheduler"),
    "OrchestratorService": (".application", "OrchestratorService"),
    "OrchestratorWorkflowSessionBridge": (".runtime_bridge", "OrchestratorWorkflowSessionBridge"),
    "OrchestratorWorkflowVM": (".workflow_vm", "OrchestratorWorkflowVM"),
    "ResearchCollaborationProjection": (".research_projection", "ResearchCollaborationProjection"),
    "ResearchBranchExecutionOutcome": (".research_bridge", "ResearchBranchExecutionOutcome"),
    "WorkflowIR": (".workflow_ir", "WorkflowIR"),
    "WorkflowVMExecutionOutcome": (".workflow_vm", "WorkflowVMExecutionOutcome"),
    "build_research_collaboration_projection": (".research_projection", "build_research_collaboration_projection"),
    "get_builtin_framework_catalog_entry": (".framework_catalog", "get_builtin_framework_catalog_entry"),
    "get_builtin_framework_mapping_bundle": (".framework_mapping", "get_builtin_framework_mapping_bundle"),
    "get_builtin_framework_mapping_spec": (".framework_mapping", "get_builtin_framework_mapping_spec"),
    "get_framework_profile_definition": (".framework_profiles", "get_framework_profile_definition"),
    "build_agent_harness_brainstorm_inputs": (".templates", "build_agent_harness_brainstorm_inputs"),
    "build_campaign_dashboard_payload": (".interfaces", "build_campaign_dashboard_payload"),
    "build_branch_view": (".fourth_layer_contracts", "build_branch_view"),
    "build_fourth_layer_contract_manifest": (".fourth_layer_contracts", "build_fourth_layer_contract_manifest"),
    "build_mission_view": (".fourth_layer_contracts", "build_mission_view"),
    "build_mission_payload_from_template": (".templates", "build_mission_payload_from_template"),
    "build_observation_snapshot": (".fourth_layer_contracts", "build_observation_snapshot"),
    "build_orchestrator_runtime_stack_for_workspace": (".workspace", "build_orchestrator_runtime_stack_for_workspace"),
    "build_orchestrator_service_for_workspace": (".workspace", "build_orchestrator_service_for_workspace"),
    "render_campaign_dashboard_html": (".interfaces", "render_campaign_dashboard_html"),
    "build_session_view": (".fourth_layer_contracts", "build_session_view"),
    "build_stable_evidence": (".fourth_layer_contracts", "build_stable_evidence"),
    "list_framework_profile_ids": (".framework_profiles", "list_framework_profile_ids"),
    "load_builtin_framework_catalog": (".framework_catalog", "load_builtin_framework_catalog"),
    "load_builtin_framework_mapping_registry": (".framework_mapping", "load_builtin_framework_mapping_registry"),
    "load_framework_compiler_inputs": (".framework_mapping", "load_framework_compiler_inputs"),
    "load_framework_mapping_bundle": (".framework_mapping", "load_framework_mapping_bundle"),
    "resolve_orchestrator_root": (".workspace", "resolve_orchestrator_root"),
    "write_campaign_dashboard": (".interfaces", "write_campaign_dashboard"),
    "write_campaign_dashboard_html": (".interfaces", "write_campaign_dashboard_html"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    module = import_module(module_name, __name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
