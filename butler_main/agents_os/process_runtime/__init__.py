"""Legacy compatibility surface for the process runtime layer."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_TARGET_MODULES = ("butler_main.runtime_os.process_runtime", "runtime_os.process_runtime")
__all__ = [
    "APPROVAL_STATUSES",
    "APPROVAL_TYPES",
    "AcceptanceReceipt",
    "ApprovalTicket",
    "ArtifactRecord",
    "ArtifactRegistry",
    "ArtifactVisibility",
    "BlackboardEntry",
    "CollaborationPrimitiveContract",
    "CollaborationSubstrate",
    "ConversationPromptBuild",
    "ConversationTurnEngine",
    "ConversationTurnInput",
    "ConversationTurnOutput",
    "ConversationTurnState",
    "DecisionReceipt",
    "EDGE_KINDS",
    "ExecutionReceipt",
    "ExecutionRuntime",
    "ExperienceRecord",
    "FROZEN_TYPED_PRIMITIVE_IDS",
    "FROZEN_TYPED_PRIMITIVES",
    "FileSessionCheckpointStore",
    "FileWorkflowCheckpointStore",
    "FileWorkflowEventLog",
    "FileWorkflowSessionStore",
    "HandoffReceipt",
    "JoinContract",
    "MailboxMessage",
    "PROCESS_ROLES",
    "RECOVERY_ACTIONS",
    "RoleBinding",
    "RoleHandoff",
    "RuntimeSessionCheckpoint",
    "RecoveryDirective",
    "STEP_KINDS",
    "SharedState",
    "StepOwnership",
    "StepReceipt",
    "StepResult",
    "SubworkflowCapability",
    "VERIFICATION_DECISIONS",
    "VerificationReceipt",
    "WorkflowBlackboard",
    "WorkflowCheckpoint",
    "WorkflowCursor",
    "WorkflowEdgeSpec",
    "WorkflowFactory",
    "WorkflowReceipt",
    "WorkflowRunProjection",
    "WorkflowSession",
    "WorkflowSessionBundle",
    "WorkflowSessionEvent",
    "WorkflowSpec",
    "WorkflowStepSpec",
    "WorkflowTemplate",
    "check_bash_chain_permissions",
    "extract_bash_commands",
    "matches_bash_permission",
    "merge_session_snapshots",
    "normalize_approval_status",
    "normalize_approval_type",
    "normalize_edge_kind",
    "normalize_failure_class",
    "normalize_process_role",
    "normalize_step_kind",
    "primitive_contract_by_id",
]


def _load_target():
    for candidate in _TARGET_MODULES:
        try:
            return import_module(candidate)
        except ModuleNotFoundError:
            continue
    raise ModuleNotFoundError(f"unable to import process runtime target from {_TARGET_MODULES!r}")


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = _load_target()
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
