from __future__ import annotations

from importlib import import_module
from typing import Any


_PUBLIC_EXPORTS: dict[str, tuple[str, str]] = {
    "AcceptanceReceipt": (".contracts", "AcceptanceReceipt"),
    "AgentRuntimeInstance": (".instance", "AgentRuntimeInstance"),
    "AgentResult": (".orchestrator", "AgentResult"),
    "AgentRuntime": (".orchestrator", "AgentRuntime"),
    "AllowAllGuardrails": (".kernel", "AllowAllGuardrails"),
    "Artifact": (".contracts", "Artifact"),
    "BackgroundMemoryServices": (".memory_components", "BackgroundMemoryServices"),
    "CapabilityBinding": (".subworkflow_interface", "CapabilityBinding"),
    "CapabilityRegistry": (".capability_registry", "CapabilityRegistry"),
    "CapabilityResolver": (".subworkflow_interface", "CapabilityResolver"),
    "ContextStateSnapshot": (".turn_state", "ContextStateSnapshot"),
    "ExecutionContext": (".orchestrator", "ExecutionContext"),
    "ExecutionReceipt": (".receipts", "ExecutionReceipt"),
    "EDGE_KINDS": (".contracts", "EDGE_KINDS"),
    "FAILURE_CLASSES": (".contracts", "FAILURE_CLASSES"),
    "FileInstanceStore": (".instance_store", "FileInstanceStore"),
    "FileSessionCheckpointStore": (".session_support", "FileSessionCheckpointStore"),
    "FunctionWorker": (".kernel", "FunctionWorker"),
    "GuardrailDecision": (".contracts", "GuardrailDecision"),
    "INSTANCE_STATUSES": (".instance", "INSTANCE_STATUSES"),
    "InMemoryArtifactStore": (".kernel", "InMemoryArtifactStore"),
    "InMemoryContextStore": (".kernel", "InMemoryContextStore"),
    "InMemoryTraceObserver": (".kernel", "InMemoryTraceObserver"),
    "IntakeDecision": (".request_intake", "IntakeDecision"),
    "LocalMemoryIndexService": (".local_memory_index", "LocalMemoryIndexService"),
    "LocalMemoryQueryParams": (".local_memory_index", "LocalMemoryQueryParams"),
    "MemoryRuntime": (".memory_runtime", "MemoryRuntime"),
    "MemoryRuntimeProvider": (".provider_interfaces", "MemoryRuntimeProvider"),
    "MissionOrchestrator": (".orchestrator", "MissionOrchestrator"),
    "Orchestrator": (".orchestrator", "Orchestrator"),
    "PromptAssembler": (".prompt_assembler", "PromptAssembler"),
    "PromptRuntimeProvider": (".provider_interfaces", "PromptRuntimeProvider"),
    "PROCESS_ROLES": (".contracts", "PROCESS_ROLES"),
    "ReplyPersistenceService": (".memory_components", "ReplyPersistenceService"),
    "RequestIntakeService": (".request_intake", "RequestIntakeService"),
    "RouteProjection": (".projection", "RouteProjection"),
    "Run": (".contracts", "Run"),
    "RunInput": (".contracts", "RunInput"),
    "RunResult": (".contracts", "RunResult"),
    "RUN_STATUSES": (".contracts", "RUN_STATUSES"),
    "RuntimeHost": (".host", "RuntimeHost"),
    "RuntimeKernel": (".kernel", "RuntimeKernel"),
    "RuntimeRequest": (".orchestrator", "RuntimeRequest"),
    "RuntimeRequestState": (".runtime_request_state", "RuntimeRequestState"),
    "STEP_KINDS": (".contracts", "STEP_KINDS"),
    "RuntimeRequestOverrideProvider": (".memory_components", "RuntimeRequestOverrideProvider"),
    "RuntimeSessionCheckpoint": (".session_support", "RuntimeSessionCheckpoint"),
    "Session": (".contracts", "Session"),
    "SingleWorkerWorkflow": (".kernel", "SingleWorkerWorkflow"),
    "StepResult": (".workflows", "StepResult"),
    "ThreadLocalStateStore": (".turn_state", "ThreadLocalStateStore"),
    "TraceEvent": (".contracts", "TraceEvent"),
    "TurnLifecycle": (".turn_lifecycle", "TurnLifecycle"),
    "TurnLifecycleStore": (".memory_components", "TurnLifecycleStore"),
    "TurnPromptAssembler": (".memory_components", "TurnPromptAssembler"),
    "AsyncWritebackRunner": (".writeback", "AsyncWritebackRunner"),
    "WorkerRegistry": (".kernel", "WorkerRegistry"),
    "WorkerRequest": (".contracts", "WorkerRequest"),
    "WorkerResult": (".contracts", "WorkerResult"),
    "WorkflowProjection": (".projection", "WorkflowProjection"),
    "WorkflowRegistry": (".kernel", "WorkflowRegistry"),
    "WorkflowReceipt": (".receipts", "WorkflowReceipt"),
    "WritebackCoordinator": (".writeback", "WritebackCoordinator"),
    "VendorCapabilityLayer": (".vendor_capabilities", "VendorCapabilityLayer"),
    "VendorCapabilityOwnership": (".vendor_capabilities", "VendorCapabilityOwnership"),
    "VendorCapabilityRegistry": (".vendor_capabilities", "VendorCapabilityRegistry"),
    "VendorCapabilitySpec": (".vendor_capabilities", "VendorCapabilitySpec"),
    "VendorResumeRecoveryPolicy": (".vendor_capabilities", "VendorResumeRecoveryPolicy"),
    "build_default_vendor_registry": (".vendor_capabilities", "build_default_vendor_registry"),
    "canonical_vendor_name": (".vendor_capabilities", "canonical_vendor_name"),
    "normalize_recovery_policy": (".vendor_capabilities", "normalize_recovery_policy"),
    "KNOWN_CAPABILITIES": (".vendor_capabilities", "KNOWN_CAPABILITIES"),
    "CAPABILITY_SESSION": (".vendor_capabilities", "CAPABILITY_SESSION"),
    "CAPABILITY_RESUME": (".vendor_capabilities", "CAPABILITY_RESUME"),
    "CAPABILITY_COMPACT": (".vendor_capabilities", "CAPABILITY_COMPACT"),
    "CAPABILITY_SKILLS": (".vendor_capabilities", "CAPABILITY_SKILLS"),
    "CAPABILITY_COLLAB": (".vendor_capabilities", "CAPABILITY_COLLAB"),
    "CAPABILITY_SUBAGENT": (".vendor_capabilities", "CAPABILITY_SUBAGENT"),
    "CAPABILITY_AGENT_TEAM": (".vendor_capabilities", "CAPABILITY_AGENT_TEAM"),
    "CAPABILITY_RECENT_MEMORY": (".vendor_capabilities", "CAPABILITY_RECENT_MEMORY"),
    "CAPABILITY_LOCAL_MEMORY": (".vendor_capabilities", "CAPABILITY_LOCAL_MEMORY"),
    "build_instance_roots": (".instance", "build_instance_roots"),
    "looks_like_broken_markdown": (".markdown_safety", "looks_like_broken_markdown"),
    "merge_session_snapshots": (".session_support", "merge_session_snapshots"),
    "normalize_failure_class": (".contracts", "normalize_failure_class"),
    "normalize_edge_kind": (".contracts", "normalize_edge_kind"),
    "normalize_instance_status": (".instance", "normalize_instance_status"),
    "normalize_markdown_text": (".markdown_safety", "normalize_markdown_text"),
    "normalize_process_role": (".contracts", "normalize_process_role"),
    "normalize_run_status": (".contracts", "normalize_run_status"),
    "normalize_step_kind": (".contracts", "normalize_step_kind"),
    "safe_truncate_markdown": (".markdown_safety", "safe_truncate_markdown"),
    "sanitize_markdown_structure": (".markdown_safety", "sanitize_markdown_structure"),
}

_LEGACY_PROCESS_EXPORTS: dict[str, tuple[str, str]] = {
    "ExecutionRuntime": ("..process_runtime.execution_runtime", "ExecutionRuntime"),
    "FileWorkflowCheckpointStore": ("..process_runtime.workflow", "FileWorkflowCheckpointStore"),
    "SubworkflowCapability": (".subworkflow_interface", "SubworkflowCapability"),
    "WorkflowCheckpoint": ("..process_runtime.workflow", "WorkflowCheckpoint"),
    "WorkflowCursor": ("..process_runtime.workflow", "WorkflowCursor"),
    "WorkflowEdgeSpec": ("..process_runtime.workflow", "WorkflowEdgeSpec"),
    "WorkflowRunProjection": ("..process_runtime.workflow", "WorkflowRunProjection"),
    "WorkflowSpec": ("..process_runtime.workflow", "WorkflowSpec"),
    "WorkflowStepSpec": ("..process_runtime.workflow", "WorkflowStepSpec"),
}

__all__ = sorted(_PUBLIC_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _PUBLIC_EXPORTS.get(name)
    if target is None:
        target = _LEGACY_PROCESS_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    module = import_module(module_name, __name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
