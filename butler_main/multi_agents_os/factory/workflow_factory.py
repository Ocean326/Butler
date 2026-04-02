from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from ..bindings.role_binding import RoleBinding
from ..session import (
    ArtifactRecord,
    ArtifactRegistry,
    BlackboardEntry,
    CollaborationSubstrate,
    FileWorkflowEventLog,
    FileWorkflowSessionStore,
    JoinContract,
    MailboxMessage,
    RoleHandoff,
    SharedState,
    StepOwnership,
    WorkflowBlackboard,
    WorkflowSession,
    WorkflowSessionBundle,
)
from ..templates.workflow_template import WorkflowTemplate


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class WorkflowFactory:
    """Assemble and recover one local workflow session bundle."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._store = FileWorkflowSessionStore(self.root_dir)
        self._event_log = FileWorkflowEventLog(self.root_dir)

    def create_session(
        self,
        *,
        template: WorkflowTemplate | Mapping[str, Any],
        driver_kind: str,
        role_bindings: list[RoleBinding | Mapping[str, Any]] | Mapping[str, Any] | None = None,
        active_step: str = "",
        initial_shared_state: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        session_id: str = "",
    ) -> WorkflowSession:
        template_obj = self.load_template(template)
        resolved_bindings = self.resolve_role_bindings(role_bindings, template=template_obj)
        workflow_session_id = str(session_id or "").strip() or _new_id("workflow_session")
        shared_state = SharedState(
            session_id=workflow_session_id,
            state=dict(initial_shared_state or {}),
        )
        artifact_registry = ArtifactRegistry(session_id=workflow_session_id)
        blackboard = WorkflowBlackboard(session_id=workflow_session_id)
        collaboration = CollaborationSubstrate(session_id=workflow_session_id)
        session = WorkflowSession(
            session_id=workflow_session_id,
            template_id=template_obj.template_id,
            driver_kind=str(driver_kind or "").strip(),
            status="active",
            active_step=str(active_step or template_obj.first_step_id()).strip(),
            role_bindings=resolved_bindings,
            shared_state_ref="shared_state.json",
            artifact_registry_ref="artifact_registry.json",
            blackboard_ref="blackboard.json",
            collaboration_ref="collaboration.json",
            event_log_ref="events.jsonl",
            metadata=dict(metadata or {}),
        )
        bundle = WorkflowSessionBundle(
            template=template_obj,
            session=session,
            shared_state=shared_state,
            artifact_registry=artifact_registry,
            blackboard=blackboard,
            collaboration=collaboration,
        )
        self._store.save_bundle(bundle)
        self._event_log.append(
            session_id=workflow_session_id,
            event_type="session_created",
            payload={
                "template_id": template_obj.template_id,
                "driver_kind": session.driver_kind,
                "active_step": session.active_step,
            },
        )
        return session

    def load_session(self, session_id: str) -> WorkflowSessionBundle:
        bundle = self._store.load_bundle(session_id)
        if bundle is None:
            raise KeyError(f"workflow session not found: {session_id}")
        return bundle

    def session_exists(self, session_id: str) -> bool:
        return self._store.exists(session_id)

    def list_session_ids(self) -> list[str]:
        return self._store.list_session_ids()

    def load_collaboration(self, session_id: str) -> CollaborationSubstrate:
        return self.load_session(session_id).collaboration

    def load_blackboard(self, session_id: str) -> WorkflowBlackboard:
        return self.load_session(session_id).blackboard

    def patch_shared_state(self, session_id: str, payload: Mapping[str, Any] | None) -> SharedState:
        bundle = self.load_session(session_id)
        changed = bundle.shared_state.patch(payload)
        if changed:
            bundle.session.touch()
            self._store.save_bundle(bundle)
            self._event_log.append(
                session_id=bundle.session.session_id,
                event_type="state_patched",
                payload={"keys": sorted([str(key) for key in dict(payload or {}).keys()])},
            )
        return bundle.shared_state

    def upsert_blackboard_entry(
        self,
        session_id: str,
        *,
        entry_key: str,
        payload: Mapping[str, Any] | None = None,
        entry_kind: str = "note",
        step_id: str = "",
        author_role_id: str = "",
        tags: list[str] | None = None,
        visibility_scope: str = "session",
        consumer_role_ids: list[str] | None = None,
        visibility_metadata: Mapping[str, Any] | None = None,
        dedupe_key: str = "",
    ) -> BlackboardEntry:
        bundle = self.load_session(session_id)
        entry, changed = bundle.blackboard.upsert_entry(
            entry_key=entry_key,
            payload=payload,
            entry_kind=entry_kind,
            step_id=step_id,
            author_role_id=author_role_id,
            tags=tags,
            visibility_scope=visibility_scope,
            consumer_role_ids=consumer_role_ids,
            visibility_metadata=visibility_metadata,
            dedupe_key=dedupe_key,
        )
        if changed:
            bundle.session.touch()
            self._store.save_bundle(bundle)
            event_payload = {
                "entry_key": entry.entry_key,
                "entry_kind": entry.entry_kind,
                "step_id": entry.step_id,
                "visibility_scope": entry.visibility.scope,
            }
            if entry.author_role_id:
                event_payload["author_role_id"] = entry.author_role_id
            self._event_log.append(
                session_id=bundle.session.session_id,
                event_type="blackboard_entry_upserted",
                payload=event_payload,
            )
        return entry

    def add_artifact(
        self,
        session_id: str,
        *,
        step_id: str,
        ref: str,
        payload: Mapping[str, Any] | None = None,
        producer_role_id: str = "",
        owner_role_id: str = "",
        visibility_scope: str = "session",
        consumer_role_ids: list[str] | None = None,
        visibility_metadata: Mapping[str, Any] | None = None,
        dedupe_key: str = "",
    ) -> ArtifactRegistry:
        bundle = self.load_session(session_id)
        artifact, changed = bundle.artifact_registry.add_artifact(
            step_id=step_id,
            ref=ref,
            payload=payload,
            producer_role_id=producer_role_id,
            owner_role_id=owner_role_id,
            visibility_scope=visibility_scope,
            consumer_role_ids=list(consumer_role_ids or []),
            visibility_metadata=visibility_metadata,
            dedupe_key=dedupe_key,
        )
        if changed:
            bundle.session.touch()
            self._store.save_bundle(bundle)
            event_payload = {"step_id": str(step_id or "").strip(), "ref": str(ref or "").strip()}
            if isinstance(artifact, ArtifactRecord):
                event_payload["visibility_scope"] = artifact.visibility.scope
                if artifact.visibility.producer_role_id:
                    event_payload["producer_role_id"] = artifact.visibility.producer_role_id
                if artifact.visibility.consumer_role_ids:
                    event_payload["consumer_role_ids"] = list(artifact.visibility.consumer_role_ids)
            self._event_log.append(
                session_id=bundle.session.session_id,
                event_type="artifact_added",
                payload=event_payload,
            )
        return bundle.artifact_registry

    def post_mailbox_message(
        self,
        session_id: str,
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
    ) -> MailboxMessage:
        bundle = self.load_session(session_id)
        message, changed = bundle.collaboration.post_message(
            recipient_role_id=recipient_role_id,
            sender_role_id=sender_role_id,
            step_id=step_id,
            message_kind=message_kind,
            summary=summary,
            artifact_refs=list(artifact_refs or []),
            payload=payload,
            dedupe_key=dedupe_key,
            status=status,
        )
        if changed:
            bundle.session.touch()
            self._store.save_bundle(bundle)
            self._event_log.append(
                session_id=bundle.session.session_id,
                event_type="mailbox_message_posted",
                payload={
                    "message_id": message.message_id,
                    "recipient_role_id": message.recipient_role_id,
                    "sender_role_id": message.sender_role_id,
                    "step_id": message.step_id,
                    "message_kind": message.message_kind,
                    "status": message.status,
                },
            )
        return message

    def assign_step_owner(
        self,
        session_id: str,
        *,
        step_id: str,
        owner_role_id: str,
        assignee_id: str = "",
        output_key: str = "",
        status: str = "assigned",
        metadata: Mapping[str, Any] | None = None,
    ) -> StepOwnership:
        bundle = self.load_session(session_id)
        ownership, changed = bundle.collaboration.assign_step_owner(
            step_id=step_id,
            owner_role_id=owner_role_id,
            assignee_id=assignee_id,
            output_key=output_key,
            status=status,
            metadata=metadata,
        )
        if changed:
            bundle.session.touch()
            self._store.save_bundle(bundle)
            self._event_log.append(
                session_id=bundle.session.session_id,
                event_type="step_owner_assigned",
                payload={
                    "step_id": ownership.step_id,
                    "owner_role_id": ownership.owner_role_id,
                    "assignee_id": ownership.assignee_id,
                    "output_key": ownership.output_key,
                    "status": ownership.status,
                },
            )
        return ownership

    def declare_join_contract(
        self,
        session_id: str,
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
    ) -> JoinContract:
        bundle = self.load_session(session_id)
        contract, changed = bundle.collaboration.declare_join_contract(
            step_id=step_id,
            source_role_ids=list(source_role_ids or []),
            target_role_id=target_role_id,
            join_kind=join_kind,
            merge_strategy=merge_strategy,
            required_artifact_refs=list(required_artifact_refs or []),
            dedupe_key=dedupe_key,
            status=status,
            metadata=metadata,
        )
        if changed:
            bundle.session.touch()
            self._store.save_bundle(bundle)
            self._event_log.append(
                session_id=bundle.session.session_id,
                event_type="join_contract_declared",
                payload={
                    "join_contract_id": contract.join_contract_id,
                    "step_id": contract.step_id,
                    "join_kind": contract.join_kind,
                    "target_role_id": contract.target_role_id,
                    "source_role_ids": list(contract.source_role_ids),
                    "status": contract.status,
                },
            )
        return contract

    def record_role_handoff(
        self,
        session_id: str,
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
    ) -> RoleHandoff:
        bundle = self.load_session(session_id)
        handoff, changed = bundle.collaboration.record_handoff(
            step_id=step_id,
            source_role_id=source_role_id,
            target_role_id=target_role_id,
            summary=summary,
            handoff_kind=handoff_kind,
            artifact_refs=list(artifact_refs or []),
            payload=payload,
            dedupe_key=dedupe_key,
            status=status,
        )
        if changed:
            bundle.session.touch()
            self._store.save_bundle(bundle)
            self._event_log.append(
                session_id=bundle.session.session_id,
                event_type="role_handoff_recorded",
                payload={
                    "handoff_id": handoff.handoff_id,
                    "step_id": handoff.step_id,
                    "source_role_id": handoff.source_role_id,
                    "target_role_id": handoff.target_role_id,
                    "handoff_kind": handoff.handoff_kind,
                    "status": handoff.status,
                },
            )
        return handoff

    def update_active_step(self, session_id: str, active_step: str, *, status: str = "") -> WorkflowSession:
        bundle = self.load_session(session_id)
        normalized_active_step = str(active_step or "").strip()
        normalized_status = str(status or "").strip()
        changed = bundle.session.active_step != normalized_active_step or (
            bool(normalized_status) and bundle.session.status != normalized_status
        )
        bundle.session.active_step = normalized_active_step
        if normalized_status:
            bundle.session.status = normalized_status
        if changed:
            bundle.session.touch()
            self._store.save_bundle(bundle)
            self._event_log.append(
                session_id=bundle.session.session_id,
                event_type="active_step_changed",
                payload={"active_step": bundle.session.active_step, "status": bundle.session.status},
            )
        return bundle.session

    def list_events(self, session_id: str, *, event_type: str = "") -> list[dict[str, Any]]:
        return [event.to_dict() for event in self._event_log.list_events(session_id, event_type=event_type)]

    def build_session_from_orchestrator_node(
        self,
        *,
        mission_id: str,
        node_id: str,
        branch_id: str,
        node_kind: str,
        node_title: str = "",
        runtime_plan: Mapping[str, Any] | None = None,
        node_metadata: Mapping[str, Any] | None = None,
        mission_metadata: Mapping[str, Any] | None = None,
    ) -> WorkflowSession | None:
        template_payload = self._extract_template_payload(runtime_plan=runtime_plan, node_metadata=node_metadata)
        if template_payload is None:
            return None
        template_payload = self._ensure_template_payload(
            template_payload,
            node_id=node_id,
            node_kind=node_kind,
            node_title=node_title,
        )
        bindings_payload = self._extract_role_bindings(runtime_plan=runtime_plan, node_metadata=node_metadata)
        workflow_inputs = self._extract_workflow_inputs(runtime_plan=runtime_plan, node_metadata=node_metadata)
        research_refs = self._extract_reference_fields(
            runtime_plan=runtime_plan,
            node_metadata=node_metadata,
            keys=("subworkflow_kind", "research_unit_id", "scenario_action"),
        )
        initial_shared_state = {
            "mission_id": str(mission_id or "").strip(),
            "node_id": str(node_id or "").strip(),
            "branch_id": str(branch_id or "").strip(),
            "node_kind": str(node_kind or "").strip(),
            "node_title": str(node_title or "").strip(),
            "workflow_inputs": workflow_inputs,
        }
        initial_shared_state.update(research_refs)
        session_metadata = {
            "source": "orchestrator.dispatch_ready_nodes",
            "mission_id": str(mission_id or "").strip(),
            "node_id": str(node_id or "").strip(),
            "branch_id": str(branch_id or "").strip(),
            "node_kind": str(node_kind or "").strip(),
            "mission_metadata": dict(mission_metadata or {}),
            "node_metadata": dict(node_metadata or {}),
        }
        session_metadata.update(research_refs)
        return self.create_session(
            template=template_payload,
            driver_kind="orchestrator_node",
            role_bindings=bindings_payload,
            initial_shared_state=initial_shared_state,
            metadata=session_metadata,
        )

    def load_template(self, payload: WorkflowTemplate | Mapping[str, Any]) -> WorkflowTemplate:
        if isinstance(payload, WorkflowTemplate):
            return payload
        if not isinstance(payload, Mapping):
            raise TypeError("workflow template payload must be a mapping")
        template = WorkflowTemplate.from_dict(payload)
        if not template.template_id:
            raise ValueError("workflow template requires template_id")
        return template

    def resolve_role_bindings(
        self,
        payload: list[RoleBinding | Mapping[str, Any]] | Mapping[str, Any] | None,
        *,
        template: WorkflowTemplate | None = None,
    ) -> list[RoleBinding]:
        resolved: list[RoleBinding] = []
        if isinstance(payload, Mapping):
            for role_id, binding in payload.items():
                if isinstance(binding, Mapping):
                    item = dict(binding)
                    item.setdefault("role_id", str(role_id or "").strip())
                    resolved.append(RoleBinding.from_dict(item))
        elif isinstance(payload, list):
            for item in payload:
                if isinstance(item, RoleBinding):
                    resolved.append(item)
                elif isinstance(item, Mapping):
                    resolved.append(RoleBinding.from_dict(item))
        if resolved:
            return [binding for binding in resolved if binding.role_id]
        if template is None:
            return []
        fallback: list[RoleBinding] = []
        for role in template.roles:
            role_id = str(role.get("role_id") or role.get("id") or "").strip()
            if not role_id:
                continue
            fallback.append(
                RoleBinding(
                    role_id=role_id,
                    agent_spec_id=str(role.get("agent_spec_id") or "").strip(),
                    capability_id=str(role.get("capability_id") or role.get("capability") or "").strip(),
                    policy_refs=list(role.get("policy_refs") or []),
                    metadata={"source": "template_role_defaults"},
                )
            )
        return fallback

    def session_root(self, session_id: str) -> Path:
        return self._store.session_root(session_id)

    @staticmethod
    def _extract_template_payload(
        *,
        runtime_plan: Mapping[str, Any] | None,
        node_metadata: Mapping[str, Any] | None,
    ) -> dict[str, Any] | None:
        sources = [dict(runtime_plan or {}), dict(node_metadata or {})]
        for source in sources:
            raw = source.get("workflow_template")
            if isinstance(raw, Mapping):
                return dict(raw)
        template_id = ""
        template_source: dict[str, Any] = {}
        for source in sources:
            candidate = str(source.get("workflow_template_id") or source.get("template_id") or "").strip()
            if candidate:
                template_id = candidate
                template_source = source
                break
        if not template_id:
            return None
        return {
            "template_id": template_id,
            "kind": str(template_source.get("workflow_kind") or "generic").strip() or "generic",
            "roles": list(template_source.get("workflow_roles") or []),
            "steps": list(template_source.get("workflow_steps") or []),
            "entry_contract": dict(template_source.get("entry_contract") or {}),
            "exit_contract": dict(template_source.get("exit_contract") or {}),
            "defaults": dict(template_source.get("workflow_defaults") or {}),
            "metadata": dict(template_source.get("workflow_metadata") or {}),
        }

    @staticmethod
    def _ensure_template_payload(
        payload: Mapping[str, Any],
        *,
        node_id: str,
        node_kind: str,
        node_title: str,
    ) -> dict[str, Any]:
        template = dict(payload or {})
        template_id = str(template.get("template_id") or "").strip()
        if not template_id:
            kind_slug = str(node_kind or "task").strip().replace(" ", "_") or "task"
            node_slug = str(node_id or "node").strip().replace(" ", "_") or "node"
            template["template_id"] = f"orchestrator.{kind_slug}.{node_slug}"
        if not str(template.get("kind") or "").strip():
            template["kind"] = "generic"
        steps = template.get("steps")
        if not isinstance(steps, list) or not steps:
            default_step_id = str(node_id or "dispatch").strip() or "dispatch"
            default_step_title = str(node_title or node_kind or default_step_id).strip() or default_step_id
            template["steps"] = [{"step_id": default_step_id, "title": default_step_title, "kind": "dispatch"}]
        roles = template.get("roles")
        if not isinstance(roles, list) or not roles:
            capability_id = str(node_kind or "task").strip() or "task"
            template["roles"] = [{"role_id": "worker", "capability_id": capability_id}]
        return template

    @staticmethod
    def _extract_role_bindings(
        *,
        runtime_plan: Mapping[str, Any] | None,
        node_metadata: Mapping[str, Any] | None,
    ) -> list[Mapping[str, Any]] | Mapping[str, Any] | None:
        for source in (runtime_plan or {}, node_metadata or {}):
            payload = source.get("role_bindings")
            if isinstance(payload, (list, Mapping)):
                return payload
        return None

    @staticmethod
    def _extract_workflow_inputs(
        *,
        runtime_plan: Mapping[str, Any] | None,
        node_metadata: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        for source in (runtime_plan or {}, node_metadata or {}):
            payload = source.get("workflow_inputs")
            if isinstance(payload, Mapping):
                return dict(payload)
        return {}

    @staticmethod
    def _extract_reference_fields(
        *,
        runtime_plan: Mapping[str, Any] | None,
        node_metadata: Mapping[str, Any] | None,
        keys: tuple[str, ...],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key in keys:
            for source in (runtime_plan or {}, node_metadata or {}):
                value = str(source.get(key) or "").strip()
                if value:
                    result[key] = value
                    break
        return result
