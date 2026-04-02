from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _normalize_strings(values: list[Any] | tuple[Any, ...] | set[Any] | None) -> list[str]:
    normalized: list[str] = []
    for item in values or []:
        value = str(item or "").strip()
        if value:
            normalized.append(value)
    return normalized


@dataclass(slots=True)
class MailboxMessage:
    """One typed mailbox item exchanged between bound roles in a session."""

    message_id: str = field(default_factory=lambda: _new_id("mailbox_message"))
    recipient_role_id: str = ""
    sender_role_id: str = ""
    step_id: str = ""
    message_kind: str = "handoff"
    summary: str = ""
    artifact_refs: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    dedupe_key: str = ""
    status: str = "queued"
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.message_id = str(self.message_id or _new_id("mailbox_message")).strip()
        self.recipient_role_id = str(self.recipient_role_id or "").strip()
        self.sender_role_id = str(self.sender_role_id or "").strip()
        self.step_id = str(self.step_id or "").strip()
        self.message_kind = str(self.message_kind or "handoff").strip() or "handoff"
        self.summary = str(self.summary or "").strip()
        self.artifact_refs = _normalize_strings(self.artifact_refs)
        self.payload = dict(self.payload or {})
        self.dedupe_key = str(self.dedupe_key or "").strip()
        self.status = str(self.status or "queued").strip() or "queued"
        self.created_at = str(self.created_at or _utc_now_iso()).strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "recipient_role_id": self.recipient_role_id,
            "sender_role_id": self.sender_role_id,
            "step_id": self.step_id,
            "message_kind": self.message_kind,
            "summary": self.summary,
            "artifact_refs": list(self.artifact_refs),
            "payload": dict(self.payload or {}),
            "dedupe_key": self.dedupe_key,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "MailboxMessage":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class StepOwnership:
    """Local ownership record for one workflow step/output boundary."""

    step_id: str = ""
    owner_role_id: str = ""
    assignee_id: str = ""
    output_key: str = ""
    status: str = "assigned"
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.step_id = str(self.step_id or "").strip()
        self.owner_role_id = str(self.owner_role_id or "").strip()
        self.assignee_id = str(self.assignee_id or "").strip()
        self.output_key = str(self.output_key or "").strip()
        self.status = str(self.status or "assigned").strip() or "assigned"
        self.metadata = dict(self.metadata or {})
        self.updated_at = str(self.updated_at or _utc_now_iso()).strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "owner_role_id": self.owner_role_id,
            "assignee_id": self.assignee_id,
            "output_key": self.output_key,
            "status": self.status,
            "metadata": dict(self.metadata or {}),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "StepOwnership":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class JoinContract:
    """Minimal join/merge contract for multi-role step convergence."""

    join_contract_id: str = field(default_factory=lambda: _new_id("join_contract"))
    step_id: str = ""
    join_kind: str = "all_inputs_ready"
    source_role_ids: list[str] = field(default_factory=list)
    target_role_id: str = ""
    merge_strategy: str = ""
    required_artifact_refs: list[str] = field(default_factory=list)
    dedupe_key: str = ""
    status: str = "open"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.join_contract_id = str(self.join_contract_id or _new_id("join_contract")).strip()
        self.step_id = str(self.step_id or "").strip()
        self.join_kind = str(self.join_kind or "all_inputs_ready").strip() or "all_inputs_ready"
        self.source_role_ids = _normalize_strings(self.source_role_ids)
        self.target_role_id = str(self.target_role_id or "").strip()
        self.merge_strategy = str(self.merge_strategy or "").strip()
        self.required_artifact_refs = _normalize_strings(self.required_artifact_refs)
        self.dedupe_key = str(self.dedupe_key or "").strip()
        self.status = str(self.status or "open").strip() or "open"
        self.metadata = dict(self.metadata or {})
        self.created_at = str(self.created_at or _utc_now_iso()).strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "join_contract_id": self.join_contract_id,
            "step_id": self.step_id,
            "join_kind": self.join_kind,
            "source_role_ids": list(self.source_role_ids),
            "target_role_id": self.target_role_id,
            "merge_strategy": self.merge_strategy,
            "required_artifact_refs": list(self.required_artifact_refs),
            "dedupe_key": self.dedupe_key,
            "status": self.status,
            "metadata": dict(self.metadata or {}),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "JoinContract":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class RoleHandoff:
    """Typed handoff receipt between roles inside one workflow session."""

    handoff_id: str = field(default_factory=lambda: _new_id("role_handoff"))
    step_id: str = ""
    source_role_id: str = ""
    target_role_id: str = ""
    handoff_kind: str = "step_output"
    summary: str = ""
    artifact_refs: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    dedupe_key: str = ""
    status: str = "pending_ack"
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.handoff_id = str(self.handoff_id or _new_id("role_handoff")).strip()
        self.step_id = str(self.step_id or "").strip()
        self.source_role_id = str(self.source_role_id or "").strip()
        self.target_role_id = str(self.target_role_id or "").strip()
        self.handoff_kind = str(self.handoff_kind or "step_output").strip() or "step_output"
        self.summary = str(self.summary or "").strip()
        self.artifact_refs = _normalize_strings(self.artifact_refs)
        self.payload = dict(self.payload or {})
        self.dedupe_key = str(self.dedupe_key or "").strip()
        self.status = str(self.status or "pending_ack").strip() or "pending_ack"
        self.created_at = str(self.created_at or _utc_now_iso()).strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "handoff_id": self.handoff_id,
            "step_id": self.step_id,
            "source_role_id": self.source_role_id,
            "target_role_id": self.target_role_id,
            "handoff_kind": self.handoff_kind,
            "summary": self.summary,
            "artifact_refs": list(self.artifact_refs),
            "payload": dict(self.payload or {}),
            "dedupe_key": self.dedupe_key,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "RoleHandoff":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class CollaborationSubstrate:
    """Typed local collaboration substrate persisted per workflow session."""

    session_id: str = ""
    mailbox_messages: list[MailboxMessage] = field(default_factory=list)
    step_ownerships: dict[str, StepOwnership] = field(default_factory=dict)
    join_contracts: list[JoinContract] = field(default_factory=list)
    handoffs: list[RoleHandoff] = field(default_factory=list)
    last_updated_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.session_id = str(self.session_id or "").strip()
        self.mailbox_messages = [
            item if isinstance(item, MailboxMessage) else MailboxMessage.from_dict(item)
            for item in (self.mailbox_messages or [])
            if isinstance(item, (MailboxMessage, Mapping))
        ]
        ownerships: dict[str, StepOwnership] = {}
        for step_id, payload in dict(self.step_ownerships or {}).items():
            normalized_step_id = str(step_id or "").strip()
            if not normalized_step_id or not isinstance(payload, (StepOwnership, Mapping)):
                continue
            ownership = payload if isinstance(payload, StepOwnership) else StepOwnership.from_dict(payload)
            if not ownership.step_id:
                ownership.step_id = normalized_step_id
            ownerships[normalized_step_id] = ownership
        self.step_ownerships = ownerships
        self.join_contracts = [
            item if isinstance(item, JoinContract) else JoinContract.from_dict(item)
            for item in (self.join_contracts or [])
            if isinstance(item, (JoinContract, Mapping))
        ]
        self.handoffs = [
            item if isinstance(item, RoleHandoff) else RoleHandoff.from_dict(item)
            for item in (self.handoffs or [])
            if isinstance(item, (RoleHandoff, Mapping))
        ]
        self.last_updated_at = str(self.last_updated_at or _utc_now_iso()).strip()

    def post_message(
        self,
        *,
        recipient_role_id: str,
        sender_role_id: str = "",
        step_id: str = "",
        message_kind: str = "handoff",
        summary: str = "",
        artifact_refs: list[str] | None = None,
        payload: Mapping[str, Any] | None = None,
        dedupe_key: str = "",
        status: str = "queued",
    ) -> tuple[MailboxMessage, bool]:
        message = MailboxMessage(
            recipient_role_id=recipient_role_id,
            sender_role_id=sender_role_id,
            step_id=step_id,
            message_kind=message_kind,
            summary=summary,
            artifact_refs=list(artifact_refs or []),
            payload=dict(payload or {}),
            dedupe_key=dedupe_key,
            status=status,
        )
        if message.dedupe_key:
            existing_index = self._find_mailbox_message_index(message.dedupe_key)
            if existing_index >= 0:
                existing = self.mailbox_messages[existing_index]
                message.message_id = existing.message_id
                message.created_at = existing.created_at
                if existing.to_dict() == message.to_dict():
                    return existing, False
                self.mailbox_messages[existing_index] = message
                self.touch()
                return message, True
        self.mailbox_messages.append(message)
        self.touch()
        return message, True

    def assign_step_owner(
        self,
        *,
        step_id: str,
        owner_role_id: str,
        assignee_id: str = "",
        output_key: str = "",
        status: str = "assigned",
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[StepOwnership, bool]:
        ownership = StepOwnership(
            step_id=step_id,
            owner_role_id=owner_role_id,
            assignee_id=assignee_id,
            output_key=output_key,
            status=status,
            metadata=dict(metadata or {}),
        )
        if ownership.step_id:
            existing = self.step_ownerships.get(ownership.step_id)
            if existing is not None:
                if existing.owner_role_id == ownership.owner_role_id and existing.assignee_id == ownership.assignee_id and existing.output_key == ownership.output_key and existing.status == ownership.status and existing.metadata == ownership.metadata:
                    return existing, False
            self.step_ownerships[ownership.step_id] = ownership
            self.touch()
            return ownership, True
        return ownership, False

    def declare_join_contract(
        self,
        *,
        step_id: str,
        source_role_ids: list[str] | None = None,
        target_role_id: str = "",
        join_kind: str = "all_inputs_ready",
        merge_strategy: str = "",
        required_artifact_refs: list[str] | None = None,
        dedupe_key: str = "",
        status: str = "open",
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[JoinContract, bool]:
        contract = JoinContract(
            step_id=step_id,
            source_role_ids=list(source_role_ids or []),
            target_role_id=target_role_id,
            join_kind=join_kind,
            merge_strategy=merge_strategy,
            required_artifact_refs=list(required_artifact_refs or []),
            dedupe_key=dedupe_key,
            status=status,
            metadata=dict(metadata or {}),
        )
        if contract.dedupe_key:
            existing_index = self._find_join_contract_index(contract.dedupe_key)
            if existing_index >= 0:
                existing = self.join_contracts[existing_index]
                contract.join_contract_id = existing.join_contract_id
                contract.created_at = existing.created_at
                if existing.to_dict() == contract.to_dict():
                    return existing, False
                self.join_contracts[existing_index] = contract
                self.touch()
                return contract, True
        self.join_contracts.append(contract)
        self.touch()
        return contract, True

    def record_handoff(
        self,
        *,
        step_id: str,
        source_role_id: str,
        target_role_id: str,
        summary: str,
        handoff_kind: str = "step_output",
        artifact_refs: list[str] | None = None,
        payload: Mapping[str, Any] | None = None,
        dedupe_key: str = "",
        status: str = "pending_ack",
    ) -> tuple[RoleHandoff, bool]:
        handoff = RoleHandoff(
            step_id=step_id,
            source_role_id=source_role_id,
            target_role_id=target_role_id,
            summary=summary,
            handoff_kind=handoff_kind,
            artifact_refs=list(artifact_refs or []),
            payload=dict(payload or {}),
            dedupe_key=dedupe_key,
            status=status,
        )
        if handoff.dedupe_key:
            existing_index = self._find_handoff_index(handoff.dedupe_key)
            if existing_index >= 0:
                existing = self.handoffs[existing_index]
                handoff.handoff_id = existing.handoff_id
                handoff.created_at = existing.created_at
                if existing.to_dict() == handoff.to_dict():
                    return existing, False
                self.handoffs[existing_index] = handoff
                self.touch()
                return handoff, True
        self.handoffs.append(handoff)
        self.touch()
        return handoff, True

    def _find_mailbox_message_index(self, dedupe_key: str) -> int:
        normalized = str(dedupe_key or "").strip()
        if not normalized:
            return -1
        for index, message in enumerate(self.mailbox_messages):
            if message.dedupe_key == normalized:
                return index
        return -1

    def _find_join_contract_index(self, dedupe_key: str) -> int:
        normalized = str(dedupe_key or "").strip()
        if not normalized:
            return -1
        for index, contract in enumerate(self.join_contracts):
            if contract.dedupe_key == normalized:
                return index
        return -1

    def _find_handoff_index(self, dedupe_key: str) -> int:
        normalized = str(dedupe_key or "").strip()
        if not normalized:
            return -1
        for index, handoff in enumerate(self.handoffs):
            if handoff.dedupe_key == normalized:
                return index
        return -1

    def touch(self) -> None:
        self.last_updated_at = _utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "mailbox_messages": [item.to_dict() for item in self.mailbox_messages],
            "step_ownerships": {
                step_id: ownership.to_dict()
                for step_id, ownership in self.step_ownerships.items()
            },
            "join_contracts": [item.to_dict() for item in self.join_contracts],
            "handoffs": [item.to_dict() for item in self.handoffs],
            "last_updated_at": self.last_updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "CollaborationSubstrate":
        if not isinstance(payload, Mapping):
            return cls()
        data = dict(payload)
        data["mailbox_messages"] = [
            item if isinstance(item, MailboxMessage) else MailboxMessage.from_dict(item)
            for item in (data.get("mailbox_messages") or [])
            if isinstance(item, (MailboxMessage, Mapping))
        ]
        ownership_payload = data.get("step_ownerships") if isinstance(data.get("step_ownerships"), Mapping) else {}
        data["step_ownerships"] = {
            str(step_id or "").strip(): (
                item if isinstance(item, StepOwnership) else StepOwnership.from_dict(item)
            )
            for step_id, item in dict(ownership_payload).items()
            if str(step_id or "").strip() and isinstance(item, (StepOwnership, Mapping))
        }
        data["join_contracts"] = [
            item if isinstance(item, JoinContract) else JoinContract.from_dict(item)
            for item in (data.get("join_contracts") or [])
            if isinstance(item, (JoinContract, Mapping))
        ]
        data["handoffs"] = [
            item if isinstance(item, RoleHandoff) else RoleHandoff.from_dict(item)
            for item in (data.get("handoffs") or [])
            if isinstance(item, (RoleHandoff, Mapping))
        ]
        return cls(**data)
