"""Execution engine contracts for the process runtime layer."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS: dict[str, tuple[str, str]] = {
    "ConversationPromptBuild": (".conversation_turn", "ConversationPromptBuild"),
    "ConversationTurnEngine": (".conversation_turn", "ConversationTurnEngine"),
    "ConversationTurnInput": (".conversation_turn", "ConversationTurnInput"),
    "ConversationTurnOutput": (".conversation_turn", "ConversationTurnOutput"),
    "ConversationTurnState": (".conversation_turn", "ConversationTurnState"),
    "FileWorkflowCheckpointStore": ("..workflow.models", "FileWorkflowCheckpointStore"),
    "AcceptanceReceipt": (".contracts", "AcceptanceReceipt"),
    "EDGE_KINDS": (".contracts", "EDGE_KINDS"),
    "PROCESS_ROLES": (".contracts", "PROCESS_ROLES"),
    "STEP_KINDS": (".contracts", "STEP_KINDS"),
    "normalize_edge_kind": (".contracts", "normalize_edge_kind"),
    "normalize_failure_class": (".contracts", "normalize_failure_class"),
    "normalize_process_role": (".contracts", "normalize_process_role"),
    "normalize_step_kind": (".contracts", "normalize_step_kind"),
    "ExecutionReceipt": (".receipts", "ExecutionReceipt"),
    "ProcessExecutionOutcome": (".receipts", "ProcessExecutionOutcome"),
    "ProcessWritebackProjection": (".receipts", "ProcessWritebackProjection"),
    "RuntimeVerdict": (".receipts", "RuntimeVerdict"),
    "WorkflowReceipt": (".receipts", "WorkflowReceipt"),
    "FileSessionCheckpointStore": (".session_support", "FileSessionCheckpointStore"),
    "RuntimeSessionCheckpoint": (".session_support", "RuntimeSessionCheckpoint"),
    "merge_session_snapshots": (".session_support", "merge_session_snapshots"),
    "SubworkflowCapability": (".subworkflow_interface", "SubworkflowCapability"),
    "StepResult": (".workflows", "StepResult"),
}

__all__ = [
    "AcceptanceReceipt",
    "ConversationPromptBuild",
    "ConversationTurnEngine",
    "ConversationTurnInput",
    "ConversationTurnOutput",
    "ConversationTurnState",
    "EDGE_KINDS",
    "ExecutionReceipt",
    "ExecutionRuntime",
    "FileSessionCheckpointStore",
    "FileWorkflowCheckpointStore",
    "PROCESS_ROLES",
    "ProcessExecutionOutcome",
    "ProcessWritebackProjection",
    "RuntimeVerdict",
    "RuntimeSessionCheckpoint",
    "STEP_KINDS",
    "StepResult",
    "SubworkflowCapability",
    "WorkflowReceipt",
    "merge_session_snapshots",
    "normalize_edge_kind",
    "normalize_failure_class",
    "normalize_process_role",
    "normalize_step_kind",
]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is not None:
        module_name, attribute_name = target
        module = import_module(module_name, __name__)
        value = getattr(module, attribute_name)
        globals()[name] = value
        return value
    if name != "ExecutionRuntime":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = import_module(".execution_runtime", __name__).ExecutionRuntime
    globals()[name] = value
    return value
