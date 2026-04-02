from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from butler_main.research.manager.code.research_manager import ResearchResult


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _unique_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for item in values:
        value = _normalize_text(item)
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _composite_dedupe_key(prefix: str, *parts: Any) -> str:
    normalized = [_normalize_text(item) for item in parts]
    return "::".join([prefix, *[item for item in normalized if item]])


@dataclass(slots=True, frozen=True)
class ProjectionArtifact:
    step_id: str
    ref: str
    payload: dict[str, Any] = field(default_factory=dict)
    producer_role_id: str = ""
    owner_role_id: str = ""
    visibility_scope: str = "workflow"
    consumer_role_ids: list[str] = field(default_factory=list)
    visibility_metadata: dict[str, Any] = field(default_factory=dict)
    dedupe_key: str = ""


@dataclass(slots=True, frozen=True)
class ProjectionStepOwnership:
    step_id: str
    owner_role_id: str
    assignee_id: str = ""
    output_key: str = ""
    status: str = "assigned"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ProjectionRoleHandoff:
    step_id: str
    source_role_id: str
    target_role_id: str
    summary: str
    handoff_kind: str = "step_output"
    artifact_refs: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    dedupe_key: str = ""
    status: str = "pending_ack"


@dataclass(slots=True, frozen=True)
class ProjectionMailboxMessage:
    recipient_role_id: str
    summary: str
    sender_role_id: str = ""
    step_id: str = ""
    message_kind: str = "handoff"
    artifact_refs: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    dedupe_key: str = ""
    status: str = "queued"


@dataclass(slots=True, frozen=True)
class ProjectionJoinContract:
    step_id: str
    source_role_ids: list[str]
    target_role_id: str
    join_kind: str = "decision_gate"
    merge_strategy: str = ""
    required_artifact_refs: list[str] = field(default_factory=list)
    dedupe_key: str = ""
    status: str = "open"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ResearchCollaborationProjection:
    workflow_session_id: str
    shared_state_patch: dict[str, Any] = field(default_factory=dict)
    active_step: str = ""
    artifacts: list[ProjectionArtifact] = field(default_factory=list)
    step_ownership: ProjectionStepOwnership | None = None
    role_handoff: ProjectionRoleHandoff | None = None
    mailbox_message: ProjectionMailboxMessage | None = None
    join_contract: ProjectionJoinContract | None = None


def build_research_collaboration_projection(
    *,
    workflow_session_id: str,
    research_unit_id: str,
    scenario_action: str,
    result: ResearchResult,
) -> ResearchCollaborationProjection | None:
    session_id = _normalize_text(workflow_session_id)
    if not session_id:
        return None
    dispatch = _as_dict(result.payload.get("dispatch"))
    scenario_instance = _as_dict(dispatch.get("scenario_instance"))
    scenario_payload = _as_dict(dispatch.get("scenario"))
    workflow_cursor = _as_dict(dispatch.get("workflow_cursor"))
    active_step = _as_dict(dispatch.get("active_step"))
    step_receipt = _as_dict(dispatch.get("step_receipt"))
    handoff_receipt = _as_dict(dispatch.get("handoff_receipt"))
    decision_receipt = _as_dict(dispatch.get("decision_receipt"))

    scenario_instance_id = _normalize_text(
        scenario_instance.get("scenario_instance_id") or result.route.get("scenario_instance_id")
    )
    scenario_id = _normalize_text(scenario_instance.get("scenario_id") or scenario_payload.get("scenario_id"))
    workflow_id = _normalize_text(scenario_instance.get("workflow_id") or workflow_cursor.get("workflow_id"))
    current_step_id = _normalize_text(
        workflow_cursor.get("current_step_id")
        or active_step.get("step_id")
        or scenario_instance.get("current_step_id")
    )
    latest_decision = _normalize_text(
        decision_receipt.get("decision")
        or scenario_instance.get("latest_decision")
    )
    step_id = _normalize_text(
        current_step_id
        or step_receipt.get("step_id")
        or handoff_receipt.get("source_step_id")
        or decision_receipt.get("step_id")
        or "research_scenario"
    ) or "research_scenario"

    artifact_producer = _projection_producer_role(step_receipt, handoff_receipt)
    artifact_consumers = _projection_consumer_roles(handoff_receipt)
    artifacts: list[ProjectionArtifact] = [
        ProjectionArtifact(
            step_id=step_id,
            ref=ref,
            payload={
                "source": "research_acceptance",
                "summary": _normalize_text(result.summary),
            },
            producer_role_id=artifact_producer,
            owner_role_id=artifact_producer,
            visibility_scope="workflow",
            consumer_role_ids=artifact_consumers,
            dedupe_key=_composite_dedupe_key("artifact", step_id, ref),
        )
        for ref in _unique_strings(list(result.acceptance.artifacts or []))
    ]
    if scenario_instance_id:
        artifacts.append(
            ProjectionArtifact(
                step_id=step_id,
                ref=f"scenario_instance:{scenario_instance_id}",
                payload={
                    "scenario_instance_id": scenario_instance_id,
                    "scenario_id": scenario_id,
                    "workflow_id": workflow_id,
                },
                producer_role_id=artifact_producer,
                owner_role_id=artifact_producer,
                visibility_scope="workflow",
                consumer_role_ids=artifact_consumers,
                dedupe_key=_composite_dedupe_key(
                    "artifact",
                    step_id,
                    f"scenario_instance:{scenario_instance_id}",
                ),
            )
        )

    return ResearchCollaborationProjection(
        workflow_session_id=session_id,
        shared_state_patch={
            key: value
            for key, value in {
                "subworkflow_kind": "research_scenario",
                "research_unit_id": _normalize_text(research_unit_id),
                "scenario_action": _normalize_text(scenario_action),
                "scenario_instance_id": scenario_instance_id,
                "scenario_id": scenario_id,
                "workflow_id": workflow_id,
                "workflow_cursor": workflow_cursor,
                "current_step_id": current_step_id,
                "latest_decision": latest_decision,
                "research_summary": _normalize_text(result.summary),
                "next_action": _normalize_text(result.acceptance.next_action),
            }.items()
            if value not in ("", None, [], {})
        },
        active_step=current_step_id,
        artifacts=artifacts,
        step_ownership=_build_step_ownership(step_id=step_id, step_receipt=step_receipt),
        role_handoff=_build_role_handoff(step_id=step_id, handoff_receipt=handoff_receipt),
        mailbox_message=_build_mailbox_message(step_id=step_id, handoff_receipt=handoff_receipt),
        join_contract=_build_join_contract(
            step_id=step_id,
            decision_receipt=decision_receipt,
            handoff_receipt=handoff_receipt,
        ),
    )


def _projection_producer_role(*payloads: Mapping[str, Any]) -> str:
    for payload in payloads:
        if not isinstance(payload, Mapping):
            continue
        for key in ("process_role", "producer", "consumer"):
            value = _normalize_text(payload.get(key))
            if value:
                return value
    return ""


def _projection_consumer_roles(handoff_receipt: Mapping[str, Any]) -> list[str]:
    if not isinstance(handoff_receipt, Mapping):
        return []
    return _unique_strings([handoff_receipt.get("consumer")])


def _build_step_ownership(*, step_id: str, step_receipt: Mapping[str, Any]) -> ProjectionStepOwnership | None:
    if not isinstance(step_receipt, Mapping):
        return None
    owner_role_id = _normalize_text(step_receipt.get("process_role"))
    if not owner_role_id:
        return None
    metadata = _as_dict(step_receipt.get("metadata"))
    output_key = _normalize_text(metadata.get("artifact_slot") or step_id) or step_id
    return ProjectionStepOwnership(
        step_id=step_id,
        owner_role_id=owner_role_id,
        assignee_id=_normalize_text(step_receipt.get("worker_name")),
        output_key=output_key,
        status=_normalize_text(step_receipt.get("status")) or "assigned",
        metadata={
            "workflow_id": _normalize_text(step_receipt.get("workflow_id")),
            "step_kind": _normalize_text(step_receipt.get("step_kind")),
            "artifact_slot": _normalize_text(metadata.get("artifact_slot")),
            "step_output_fields": list(metadata.get("step_output_fields") or []),
        },
    )


def _build_role_handoff(*, step_id: str, handoff_receipt: Mapping[str, Any]) -> ProjectionRoleHandoff | None:
    if not isinstance(handoff_receipt, Mapping):
        return None
    source_role_id = _normalize_text(handoff_receipt.get("producer"))
    target_role_id = _normalize_text(handoff_receipt.get("consumer"))
    summary = _normalize_text(handoff_receipt.get("summary"))
    if not source_role_id or not target_role_id or not summary:
        return None
    return ProjectionRoleHandoff(
        step_id=_normalize_text(handoff_receipt.get("source_step_id") or step_id) or step_id,
        source_role_id=source_role_id,
        target_role_id=target_role_id,
        summary=summary,
        handoff_kind=_normalize_text(handoff_receipt.get("handoff_kind")) or "step_output",
        artifact_refs=_unique_strings(list(handoff_receipt.get("artifacts") or [])),
        payload={
            "workflow_id": _normalize_text(handoff_receipt.get("workflow_id")),
            "target_step_id": _normalize_text(handoff_receipt.get("target_step_id")),
            "handoff_ready": bool(handoff_receipt.get("handoff_ready")),
            "next_action": _normalize_text(handoff_receipt.get("next_action")),
            "metadata": _as_dict(handoff_receipt.get("metadata")),
        },
        dedupe_key=_handoff_dedupe_key(step_id=step_id, handoff_receipt=handoff_receipt),
        status=_normalize_text(handoff_receipt.get("status")) or "pending_ack",
    )


def _build_mailbox_message(*, step_id: str, handoff_receipt: Mapping[str, Any]) -> ProjectionMailboxMessage | None:
    if not isinstance(handoff_receipt, Mapping):
        return None
    recipient_role_id = _normalize_text(handoff_receipt.get("consumer"))
    summary = _normalize_text(handoff_receipt.get("summary"))
    if not recipient_role_id or not summary:
        return None
    return ProjectionMailboxMessage(
        recipient_role_id=recipient_role_id,
        summary=summary,
        sender_role_id=_normalize_text(handoff_receipt.get("producer")),
        step_id=_normalize_text(handoff_receipt.get("source_step_id") or step_id) or step_id,
        message_kind=_normalize_text(handoff_receipt.get("handoff_kind")) or "handoff",
        artifact_refs=_unique_strings(list(handoff_receipt.get("artifacts") or [])),
        payload={
            "workflow_id": _normalize_text(handoff_receipt.get("workflow_id")),
            "target_step_id": _normalize_text(handoff_receipt.get("target_step_id")),
            "handoff_ready": bool(handoff_receipt.get("handoff_ready")),
            "next_action": _normalize_text(handoff_receipt.get("next_action")),
        },
        dedupe_key=_composite_dedupe_key(
            "mailbox",
            _handoff_dedupe_key(step_id=step_id, handoff_receipt=handoff_receipt),
        ),
        status="queued" if bool(handoff_receipt.get("handoff_ready")) else (_normalize_text(handoff_receipt.get("status")) or "pending"),
    )


def _build_join_contract(
    *,
    step_id: str,
    decision_receipt: Mapping[str, Any],
    handoff_receipt: Mapping[str, Any],
) -> ProjectionJoinContract | None:
    if not isinstance(decision_receipt, Mapping):
        return None
    target_role_id = _normalize_text(
        handoff_receipt.get("consumer") if isinstance(handoff_receipt, Mapping) else decision_receipt.get("producer")
    ) or _normalize_text(decision_receipt.get("producer"))
    if not target_role_id:
        return None
    source_role_ids = _unique_strings([
        decision_receipt.get("producer"),
        handoff_receipt.get("producer") if isinstance(handoff_receipt, Mapping) else "",
    ])
    if not source_role_ids:
        return None
    required_artifact_refs = _unique_strings(
        list(decision_receipt.get("artifacts") or []) +
        list(handoff_receipt.get("artifacts") or []) if isinstance(handoff_receipt, Mapping) else list(decision_receipt.get("artifacts") or [])
    )
    return ProjectionJoinContract(
        step_id=_normalize_text(decision_receipt.get("step_id") or step_id) or step_id,
        source_role_ids=source_role_ids,
        target_role_id=target_role_id,
        join_kind="decision_gate",
        merge_strategy=_normalize_text(decision_receipt.get("decision")),
        required_artifact_refs=required_artifact_refs,
        dedupe_key=_decision_dedupe_key(
            step_id=step_id,
            decision_receipt=decision_receipt,
            handoff_receipt=handoff_receipt,
        ),
        status="open",
        metadata={
            "workflow_id": _normalize_text(decision_receipt.get("workflow_id")),
            "decision_id": _normalize_text(decision_receipt.get("decision_id")),
            "decision_reason": _normalize_text(decision_receipt.get("decision_reason")),
            "retryable": bool(decision_receipt.get("retryable")),
            "next_action": _normalize_text(decision_receipt.get("next_action")),
            "resume_from": _normalize_text(decision_receipt.get("resume_from")),
            "metadata": _as_dict(decision_receipt.get("metadata")),
        },
    )


def _handoff_dedupe_key(*, step_id: str, handoff_receipt: Mapping[str, Any]) -> str:
    explicit_handoff_id = _normalize_text(handoff_receipt.get("handoff_id"))
    if explicit_handoff_id:
        return _composite_dedupe_key("handoff", explicit_handoff_id)
    return _composite_dedupe_key(
        "handoff",
        _normalize_text(handoff_receipt.get("workflow_id")),
        _normalize_text(handoff_receipt.get("source_step_id") or step_id) or step_id,
        _normalize_text(handoff_receipt.get("target_step_id")),
        _normalize_text(handoff_receipt.get("producer")),
        _normalize_text(handoff_receipt.get("consumer")),
        _normalize_text(handoff_receipt.get("handoff_kind")) or "step_output",
    )


def _decision_dedupe_key(
    *,
    step_id: str,
    decision_receipt: Mapping[str, Any],
    handoff_receipt: Mapping[str, Any],
) -> str:
    explicit_decision_id = _normalize_text(decision_receipt.get("decision_id"))
    if explicit_decision_id:
        return _composite_dedupe_key("join", explicit_decision_id)
    return _composite_dedupe_key(
        "join",
        _normalize_text(decision_receipt.get("workflow_id")),
        _normalize_text(decision_receipt.get("step_id") or step_id) or step_id,
        _normalize_text(decision_receipt.get("producer")),
        _normalize_text(handoff_receipt.get("consumer") if isinstance(handoff_receipt, Mapping) else ""),
        _normalize_text(decision_receipt.get("decision")),
    )
