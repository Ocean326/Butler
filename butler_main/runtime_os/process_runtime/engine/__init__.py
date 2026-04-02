"""Execution engine contracts for the process runtime layer."""

from importlib import import_module
from typing import Any

from .conversation_turn import (
    ConversationPromptBuild,
    ConversationTurnEngine,
    ConversationTurnInput,
    ConversationTurnOutput,
    ConversationTurnState,
)
from ..workflow.models import FileWorkflowCheckpointStore
from .contracts import (
    AcceptanceReceipt,
    EDGE_KINDS,
    PROCESS_ROLES,
    STEP_KINDS,
    normalize_edge_kind,
    normalize_failure_class,
    normalize_process_role,
    normalize_step_kind,
)
from .receipts import (
    ExecutionReceipt,
    ProcessExecutionOutcome,
    ProcessWritebackProjection,
    RuntimeVerdict,
    WorkflowReceipt,
)
from .session_support import FileSessionCheckpointStore, RuntimeSessionCheckpoint, merge_session_snapshots
from .subworkflow_interface import SubworkflowCapability
from .workflows import StepResult

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
    if name != "ExecutionRuntime":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = import_module(".execution_runtime", __name__).ExecutionRuntime
    globals()[name] = value
    return value
