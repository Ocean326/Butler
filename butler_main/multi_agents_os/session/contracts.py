from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class CollaborationPrimitiveContract:
    """Frozen external contract for one collaboration substrate primitive."""

    primitive_id: str
    bundle_field: str
    record_type: str
    write_api: tuple[str, ...]
    read_api: tuple[str, ...]
    compiler_usage: str
    projection_usage: str
    orchestrator_usage: str
    workflow_vm_usage: str


FROZEN_TYPED_PRIMITIVES: tuple[CollaborationPrimitiveContract, ...] = (
    CollaborationPrimitiveContract(
        primitive_id="mailbox",
        bundle_field="collaboration.mailbox_messages",
        record_type="MailboxMessage",
        write_api=("WorkflowFactory.post_mailbox_message",),
        read_api=("WorkflowSessionBundle.collaboration.mailbox_messages",),
        compiler_usage="emit mailbox binding hints only; do not emit concrete mailbox messages",
        projection_usage="write mailbox items through WorkflowFactory when projecting structured receipts",
        orchestrator_usage="read mailbox state from bundle for observation; do not mutate collaboration internals directly",
        workflow_vm_usage="read queued mailbox items from bundle and write new items through WorkflowFactory",
    ),
    CollaborationPrimitiveContract(
        primitive_id="ownership",
        bundle_field="collaboration.step_ownerships",
        record_type="StepOwnership",
        write_api=("WorkflowFactory.assign_step_owner",),
        read_api=("WorkflowSessionBundle.collaboration.step_ownerships",),
        compiler_usage="emit ownership expectations or output keys only; do not emit runtime ownership records",
        projection_usage="materialize ownership updates through WorkflowFactory from structured step receipts",
        orchestrator_usage="read ownership state from bundle when summarizing collaboration progress",
        workflow_vm_usage="read/write ownership through WorkflowFactory while keeping step execution separate",
    ),
    CollaborationPrimitiveContract(
        primitive_id="join_contract",
        bundle_field="collaboration.join_contracts",
        record_type="JoinContract",
        write_api=("WorkflowFactory.declare_join_contract",),
        read_api=("WorkflowSessionBundle.collaboration.join_contracts",),
        compiler_usage="emit join requirements only; do not emit resolved join state",
        projection_usage="write join contracts through WorkflowFactory from decision or barrier receipts",
        orchestrator_usage="read join state from bundle for observation, not for direct graph execution",
        workflow_vm_usage="consume join contracts from bundle and update them through WorkflowFactory if needed",
    ),
    CollaborationPrimitiveContract(
        primitive_id="handoff",
        bundle_field="collaboration.handoffs",
        record_type="RoleHandoff",
        write_api=("WorkflowFactory.record_role_handoff",),
        read_api=("WorkflowSessionBundle.collaboration.handoffs",),
        compiler_usage="emit handoff-capable role topology only; do not emit runtime handoff receipts",
        projection_usage="write handoff receipts through WorkflowFactory during projection",
        orchestrator_usage="read handoff trace from bundle for reporting and debugging only",
        workflow_vm_usage="read/write handoff receipts through WorkflowFactory as collaboration trace, not as scheduler state",
    ),
    CollaborationPrimitiveContract(
        primitive_id="artifact_visibility",
        bundle_field="artifact_registry.artifacts[*].visibility",
        record_type="ArtifactVisibility",
        write_api=("WorkflowFactory.add_artifact",),
        read_api=("ArtifactRegistry.visible_records", "ArtifactRegistry.visibility_index"),
        compiler_usage="emit visibility hints or scopes only; do not emit concrete artifact instances",
        projection_usage="materialize visibility on artifact write-back through WorkflowFactory.add_artifact",
        orchestrator_usage="read visibility-filtered artifact views through ArtifactRegistry helpers, not raw file layout",
        workflow_vm_usage="consume visibility rules through ArtifactRegistry helpers when selecting accessible artifacts",
    ),
    CollaborationPrimitiveContract(
        primitive_id="workflow_blackboard",
        bundle_field="blackboard.entries",
        record_type="WorkflowBlackboard/BlackboardEntry",
        write_api=("WorkflowFactory.upsert_blackboard_entry",),
        read_api=("WorkflowFactory.load_blackboard", "WorkflowBlackboard.visible_entries"),
        compiler_usage="emit blackboard binding hints only; do not emit runtime blackboard entries",
        projection_usage="write blackboard entries through WorkflowFactory when projecting shared collaborative notes",
        orchestrator_usage="read blackboard views from bundle or WorkflowFactory; only seed entries through factory",
        workflow_vm_usage="read/write blackboard entries through WorkflowFactory as typed collaboration memory",
    ),
)

FROZEN_TYPED_PRIMITIVE_IDS: tuple[str, ...] = tuple(item.primitive_id for item in FROZEN_TYPED_PRIMITIVES)


def primitive_contract_by_id(primitive_id: str) -> CollaborationPrimitiveContract:
    normalized = str(primitive_id or "").strip()
    for item in FROZEN_TYPED_PRIMITIVES:
        if item.primitive_id == normalized:
            return item
    raise KeyError(f"unknown collaboration primitive: {primitive_id}")
