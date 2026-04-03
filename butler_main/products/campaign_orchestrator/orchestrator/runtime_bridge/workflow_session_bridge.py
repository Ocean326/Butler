from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from butler_main.runtime_os.process_runtime import WorkflowFactory, WorkflowSession

from ..event_store import FileLedgerEventStore
from ..models import Branch, LedgerEvent, Mission, MissionNode
from ..workflow_ir import WorkflowIR


class OrchestratorWorkflowSessionBridge:
    """Keep workflow-session persistence and runtime metadata out of control-plane service."""

    def __init__(
        self,
        *,
        workflow_factory: WorkflowFactory,
        event_store: FileLedgerEventStore,
        now_factory: Callable[[], str],
    ) -> None:
        self._workflow_factory = workflow_factory
        self._event_store = event_store
        self._now_factory = now_factory

    def summarize_workflow_session(self, session_id: str) -> dict[str, Any]:
        target = str(session_id or "").strip()
        if not target:
            raise KeyError("workflow session not found: ")
        try:
            bundle = self._workflow_factory.load_session(target)
        except Exception as exc:
            raise KeyError(f"workflow session not found: {session_id}") from exc
        session = bundle.session
        session_root = self._workflow_factory.session_root(session.session_id)
        event_log_path = session_root / (session.event_log_ref or "events.jsonl")
        template = bundle.template
        shared_state = bundle.shared_state
        artifact_registry = bundle.artifact_registry
        blackboard = bundle.blackboard
        collaboration = bundle.collaboration
        events = self._workflow_factory.list_events(session.session_id)
        step_ids: list[str] = []
        for step in template.steps:
            step_id = str(step.get("step_id") or step.get("id") or "").strip()
            if step_id:
                step_ids.append(step_id)
        refs_by_step = {
            step_id: list(refs)
            for step_id, refs in dict(artifact_registry.refs_by_step or {}).items()
            if step_id
        }
        return {
            "session_id": session.session_id,
            "template_id": session.template_id,
            "driver_kind": session.driver_kind,
            "status": session.status,
            "active_step": session.active_step,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "session_root": str(session_root),
            "role_bindings": [binding.to_dict() for binding in session.role_bindings],
            "metadata": dict(session.metadata or {}),
            "template": {
                "template_id": template.template_id,
                "kind": template.kind,
                "role_count": len(template.roles),
                "step_count": len(template.steps),
                "step_ids": step_ids,
                "entry_contract": dict(template.entry_contract or {}),
                "exit_contract": dict(template.exit_contract or {}),
                "metadata": dict(template.metadata or {}),
            },
            "shared_state": {
                "state_version": shared_state.state_version,
                "last_updated_at": shared_state.last_updated_at,
                "key_count": len(shared_state.state),
                "keys": sorted(shared_state.state.keys()),
                "state": dict(shared_state.state or {}),
            },
            "artifact_registry": {
                "artifact_count": len(artifact_registry.artifacts),
                "artifacts": [item.to_dict() for item in artifact_registry.artifacts],
                "latest_output_keys": sorted(dict(artifact_registry.latest_outputs or {}).keys()),
                "refs_by_step": refs_by_step,
            },
            "blackboard": {
                "entry_count": len(blackboard.entries),
                "entry_keys": sorted(blackboard.entries.keys()),
                "entries": [entry.to_dict() for entry in blackboard.entries.values()],
                "last_updated_at": blackboard.last_updated_at,
            },
            "collaboration": {
                "mailbox_message_count": len(collaboration.mailbox_messages),
                "queued_mailbox_message_count": len(
                    [item for item in collaboration.mailbox_messages if item.status == "queued"]
                ),
                "owned_step_ids": sorted(collaboration.step_ownerships.keys()),
                "join_contract_count": len(collaboration.join_contracts),
                "open_join_contract_count": len(
                    [item for item in collaboration.join_contracts if item.status == "open"]
                ),
                "handoff_count": len(collaboration.handoffs),
                "last_updated_at": collaboration.last_updated_at,
            },
            "event_log": {
                "path": str(event_log_path),
                "exists": event_log_path.exists(),
                "line_count": self._line_count(event_log_path),
            },
            "events": events,
        }

    def session_id_from_branch(self, branch: Branch) -> str:
        return str(
            branch.input_payload.get("workflow_session_id")
            or branch.metadata.get("workflow_session_id")
            or ""
        ).strip()

    def workflow_session_summary(self, session_id: str) -> dict[str, Any] | None:
        session = self.load_workflow_session(session_id)
        if session is None:
            return None
        return {
            "session_id": session.session_id,
            "template_id": session.template_id,
            "driver_kind": session.driver_kind,
            "status": session.status,
            "active_step": session.active_step,
            "updated_at": session.updated_at,
        }

    def workflow_ir_summary_from_branch(self, branch: Branch) -> dict[str, Any] | None:
        payload = branch.metadata.get("workflow_ir")
        if not isinstance(payload, dict) or not payload:
            return None
        return WorkflowIR.from_dict(payload).summary()

    def workflow_ir_summary_from_node(self, node: MissionNode) -> dict[str, Any] | None:
        payload = node.metadata.get("workflow_ir_summary")
        if isinstance(payload, dict) and payload:
            return dict(payload)
        return None

    def workflow_ir_from_branch(self, branch: Branch) -> WorkflowIR | None:
        payload = branch.metadata.get("workflow_ir")
        if not isinstance(payload, dict) or not payload:
            return None
        return WorkflowIR.from_dict(payload)

    def load_shared_state(self, session_id: str) -> dict[str, Any]:
        target = str(session_id or "").strip()
        if not target:
            return {}
        try:
            bundle = self._workflow_factory.load_session(target)
        except Exception:
            return {}
        return dict(bundle.shared_state.state or {})

    def append_user_feedback(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        feedback: str,
        event_id: str = "",
        recorded_at: str = "",
    ) -> dict[str, Any] | None:
        session_id = str(node.metadata.get("workflow_session_id") or "").strip()
        feedback_text = str(feedback or "").strip()
        if not session_id or not feedback_text:
            return None
        try:
            bundle = self._workflow_factory.load_session(session_id)
        except Exception:
            self._event_store.append(
                LedgerEvent(
                    mission_id=mission.mission_id,
                    node_id=node.node_id,
                    event_type="workflow_session_feedback_missing",
                    payload={
                        "workflow_session_id": session_id,
                        "feedback_event_id": str(event_id or "").strip(),
                    },
                )
            )
            return None

        feedback_recorded_at = str(recorded_at or self._now_factory() or "").strip()
        feedback_item = {
            "event_id": str(event_id or "").strip(),
            "feedback": feedback_text,
            "recorded_at": feedback_recorded_at,
        }
        history = self._normalize_feedback_history(bundle.shared_state.state.get("user_feedback_items"))
        history.append(feedback_item)
        history = history[-10:]
        self._workflow_factory.patch_shared_state(
            session_id,
            {
                "latest_user_feedback": feedback_text,
                "latest_user_feedback_at": feedback_recorded_at,
                "user_feedback_count": len(history),
                "user_feedback_items": history,
            },
        )
        entry_key = f"user_feedback_{str(event_id or feedback_recorded_at).replace(':', '_')}"
        self._workflow_factory.upsert_blackboard_entry(
            session_id,
            entry_key=entry_key,
            payload=feedback_item,
            entry_kind="user_feedback",
            author_role_id="user",
            tags=["user_feedback", "frontdoor_feedback"],
            visibility_scope="session",
            dedupe_key=str(event_id or feedback_recorded_at).strip(),
        )
        recipient_role_id = self._feedback_recipient_role_id(bundle.session)
        if recipient_role_id:
            self._workflow_factory.post_mailbox_message(
                session_id,
                recipient_role_id=recipient_role_id,
                sender_role_id="user",
                step_id=str(bundle.session.active_step or "").strip(),
                message_kind="user_feedback",
                summary=feedback_text[:160],
                payload=feedback_item,
                dedupe_key=str(event_id or feedback_recorded_at).strip(),
                status="queued",
            )
        self._event_store.append(
            LedgerEvent(
                mission_id=mission.mission_id,
                node_id=node.node_id,
                event_type="workflow_session_user_feedback_appended",
                payload={
                    "workflow_session_id": session_id,
                    "feedback_event_id": str(event_id or "").strip(),
                    "feedback_summary": feedback_text[:160],
                    "recipient_role_id": recipient_role_id,
                    "feedback_count": len(history),
                },
            )
        )
        return {
            "workflow_session_id": session_id,
            "recipient_role_id": recipient_role_id,
            "feedback_count": len(history),
            "recorded_at": feedback_recorded_at,
        }

    def apply_collaboration_projection(self, projection: Any) -> None:
        if projection is None:
            return
        session_id = str(getattr(projection, "workflow_session_id", "") or "").strip()
        if not session_id:
            return
        shared_state_patch = getattr(projection, "shared_state_patch", None)
        if isinstance(shared_state_patch, Mapping):
            self._workflow_factory.patch_shared_state(session_id, dict(shared_state_patch))
        for artifact in list(getattr(projection, "artifacts", []) or []):
            self._workflow_factory.add_artifact(
                session_id,
                step_id=getattr(artifact, "step_id", ""),
                ref=getattr(artifact, "ref", ""),
                payload=getattr(artifact, "payload", None),
                producer_role_id=getattr(artifact, "producer_role_id", ""),
                owner_role_id=getattr(artifact, "owner_role_id", ""),
                visibility_scope=getattr(artifact, "visibility_scope", "workflow"),
                consumer_role_ids=getattr(artifact, "consumer_role_ids", None),
                visibility_metadata=getattr(artifact, "visibility_metadata", None),
                dedupe_key=getattr(artifact, "dedupe_key", ""),
            )
        step_ownership = getattr(projection, "step_ownership", None)
        if step_ownership is not None:
            self._workflow_factory.assign_step_owner(
                session_id,
                step_id=getattr(step_ownership, "step_id", ""),
                owner_role_id=getattr(step_ownership, "owner_role_id", ""),
                assignee_id=getattr(step_ownership, "assignee_id", ""),
                output_key=getattr(step_ownership, "output_key", ""),
                status=getattr(step_ownership, "status", ""),
                metadata=getattr(step_ownership, "metadata", None),
            )
        role_handoff = getattr(projection, "role_handoff", None)
        if role_handoff is not None:
            self._workflow_factory.record_role_handoff(
                session_id,
                step_id=getattr(role_handoff, "step_id", ""),
                source_role_id=getattr(role_handoff, "source_role_id", ""),
                target_role_id=getattr(role_handoff, "target_role_id", ""),
                summary=getattr(role_handoff, "summary", ""),
                handoff_kind=getattr(role_handoff, "handoff_kind", ""),
                artifact_refs=getattr(role_handoff, "artifact_refs", None),
                payload=getattr(role_handoff, "payload", None),
                dedupe_key=getattr(role_handoff, "dedupe_key", ""),
                status=getattr(role_handoff, "status", ""),
            )
        mailbox_message = getattr(projection, "mailbox_message", None)
        if mailbox_message is not None:
            self._workflow_factory.post_mailbox_message(
                session_id,
                recipient_role_id=getattr(mailbox_message, "recipient_role_id", ""),
                sender_role_id=getattr(mailbox_message, "sender_role_id", ""),
                step_id=getattr(mailbox_message, "step_id", ""),
                message_kind=getattr(mailbox_message, "message_kind", ""),
                summary=getattr(mailbox_message, "summary", ""),
                artifact_refs=getattr(mailbox_message, "artifact_refs", None),
                payload=getattr(mailbox_message, "payload", None),
                dedupe_key=getattr(mailbox_message, "dedupe_key", ""),
                status=getattr(mailbox_message, "status", ""),
            )
        join_contract = getattr(projection, "join_contract", None)
        if join_contract is not None:
            self._workflow_factory.declare_join_contract(
                session_id,
                step_id=getattr(join_contract, "step_id", ""),
                source_role_ids=getattr(join_contract, "source_role_ids", None),
                target_role_id=getattr(join_contract, "target_role_id", ""),
                join_kind=getattr(join_contract, "join_kind", ""),
                merge_strategy=getattr(join_contract, "merge_strategy", ""),
                required_artifact_refs=getattr(join_contract, "required_artifact_refs", None),
                dedupe_key=getattr(join_contract, "dedupe_key", ""),
                status=getattr(join_contract, "status", ""),
                metadata=getattr(join_contract, "metadata", None),
            )
        active_step = str(getattr(projection, "active_step", "") or "").strip()
        if active_step:
            self._workflow_factory.update_active_step(session_id, active_step, status="active")

    def load_workflow_session(self, session_id: str) -> WorkflowSession | None:
        target = str(session_id or "").strip()
        if not target:
            return None
        path = self._workflow_session_file(target)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return WorkflowSession.from_dict(payload)

    def save_workflow_session(self, session: WorkflowSession) -> WorkflowSession:
        path = self._workflow_session_file(session.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(session.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return session

    def prepare_branch_workflow_session(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        workflow_ir: WorkflowIR,
    ) -> tuple[WorkflowSession | None, bool]:
        action = str(node.metadata.get("recovery_action") or "").strip()
        if action in {"retry_step", "resume"}:
            session_id = str(node.metadata.get("workflow_session_id") or "").strip()
            if session_id:
                resumed = self._reuse_existing_session(
                    mission=mission,
                    node=node,
                    branch=branch,
                    workflow_ir=workflow_ir,
                    session_id=session_id,
                    recovery_action=action,
                )
                if resumed is not None:
                    return resumed, True
        prebound_session_id = str(node.metadata.get("workflow_session_id") or "").strip()
        if prebound_session_id and action not in {"retry", "repair", "repair_branch"}:
            resumed = self._reuse_existing_session(
                mission=mission,
                node=node,
                branch=branch,
                workflow_ir=workflow_ir,
                session_id=prebound_session_id,
                recovery_action="prebound",
                allow_terminal=False,
            )
            if resumed is not None:
                return resumed, True
        workflow_session = self._workflow_factory.build_session_from_orchestrator_node(
            mission_id=mission.mission_id,
            node_id=node.node_id,
            branch_id=branch.branch_id,
            node_kind=node.kind,
            node_title=node.title,
            runtime_plan=workflow_ir.to_runtime_plan_payload(),
            node_metadata=node.metadata,
            mission_metadata=mission.metadata,
        )
        return workflow_session, False

    def _reuse_existing_session(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        workflow_ir: WorkflowIR,
        session_id: str,
        recovery_action: str,
        allow_terminal: bool = True,
    ) -> WorkflowSession | None:
        session = self.load_workflow_session(session_id)
        if session is None:
            return None
        if not allow_terminal and str(session.status or "").strip().lower() in {
            "completed",
            "failed",
            "stopped",
            "cancelled",
        }:
            return None
        resume_from = str(
            node.metadata.get("recovery_resume_from") or session.active_step or ""
        ).strip()
        if not resume_from:
            resume_from = self.workflow_template_first_step_id(workflow_ir)
        resumed = self._workflow_factory.update_active_step(
            session_id,
            resume_from,
            status="active",
        )
        resumed.metadata["mission_id"] = mission.mission_id
        resumed.metadata["node_id"] = node.node_id
        resumed.metadata["branch_id"] = branch.branch_id
        resumed.metadata["recovery_action"] = recovery_action
        resumed.metadata["recovery_resume_from"] = resume_from
        resumed.touch()
        self.save_workflow_session(resumed)
        return resumed

    def bind_dispatched_branch_workflow_session(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        workflow_ir: WorkflowIR,
        workflow_session: WorkflowSession | None,
        session_reused: bool,
    ) -> WorkflowIR:
        if workflow_session is None:
            return workflow_ir
        session_id = str(workflow_session.session_id or "").strip()
        template_id = str(workflow_session.template_id or "").strip()
        driver_kind = str(workflow_session.driver_kind or "").strip()
        self._bind_workflow_session_refs(
            branch=branch,
            node=node,
            workflow_session_id=session_id,
            workflow_template_id=template_id,
            workflow_driver_kind=driver_kind,
        )
        updated = self.attach_compiled_workflow_ir(
            branch=branch,
            node=node,
            workflow_ir=workflow_ir,
            workflow_session_id=session_id,
            workflow_template_id=template_id,
        )
        self._event_store.append(
            LedgerEvent(
                mission_id=mission.mission_id,
                node_id=node.node_id,
                branch_id=branch.branch_id,
                event_type="workflow_session_resumed" if session_reused else "workflow_session_created",
                payload={
                    "workflow_session_id": session_id,
                    "workflow_template_id": template_id,
                    "driver_kind": driver_kind,
                    "recovery_action": str(node.metadata.get("recovery_action") or "").strip(),
                    "resume_from": str(node.metadata.get("recovery_resume_from") or "").strip(),
                },
            )
        )
        return updated

    def attach_compiled_workflow_ir(
        self,
        *,
        branch: Branch,
        node: MissionNode,
        workflow_ir: WorkflowIR,
        workflow_session_id: str,
        workflow_template_id: str,
    ) -> WorkflowIR:
        updated = WorkflowIR.from_dict(workflow_ir.to_dict())
        updated.workflow_session_id = str(workflow_session_id or "").strip()
        updated.workflow_template_id = str(workflow_template_id or "").strip()
        branch.metadata["workflow_ir"] = updated.to_dict()
        node.metadata["workflow_ir_summary"] = updated.summary()
        return updated

    def finalize_branch_workflow_session(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        ok: bool,
        result_ref: str,
        result_payload: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        return self.update_branch_workflow_session(
            mission=mission,
            node=node,
            branch=branch,
            status="completed" if ok else "failed",
            clear_active_step=True,
            result_ok=ok,
            result_ref=result_ref,
            result_payload=result_payload,
            governance={
                "phase": "finalized",
                "ok": bool(ok),
            },
        )

    def refresh_branch_workflow_session_metadata(
        self,
        *,
        branch: Branch,
        node: MissionNode,
    ) -> dict[str, Any] | None:
        summary = self.workflow_session_summary(self.session_id_from_branch(branch))
        for target in (branch.metadata, node.metadata):
            if summary is None:
                target.pop("workflow_session_status", None)
                target.pop("workflow_session_updated_at", None)
                continue
            target["workflow_session_status"] = summary["status"]
            target["workflow_session_updated_at"] = summary["updated_at"]
        return summary

    def update_branch_workflow_session(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        status: str,
        active_step: str | None = None,
        clear_active_step: bool = False,
        result_ok: bool | None = None,
        result_ref: str = "",
        result_payload: dict[str, Any] | None = None,
        governance: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        session_id = self.session_id_from_branch(branch)
        if not session_id:
            return None
        try:
            session = self.load_workflow_session(session_id)
            if session is None:
                self._event_store.append(
                    LedgerEvent(
                        mission_id=mission.mission_id,
                        node_id=node.node_id,
                        branch_id=branch.branch_id,
                        event_type="workflow_session_missing",
                        payload={"workflow_session_id": session_id},
                    )
                )
                return None
            session.status = str(status or session.status).strip() or session.status
            if clear_active_step:
                session.active_step = ""
            elif active_step is not None:
                session.active_step = str(active_step or "").strip()
            session.metadata["mission_id"] = mission.mission_id
            session.metadata["node_id"] = node.node_id
            session.metadata["branch_id"] = branch.branch_id
            if governance is not None:
                session.metadata["orchestrator_governance"] = dict(governance)
            if result_ok is not None:
                session.metadata["orchestrator_result"] = self.workflow_session_result_summary(
                    ok=result_ok,
                    branch_status=branch.status,
                    result_ref=result_ref,
                    result_payload=result_payload,
                )
            session.touch()
            self.save_workflow_session(session)
            self._event_store.append(
                LedgerEvent(
                    mission_id=mission.mission_id,
                    node_id=node.node_id,
                    branch_id=branch.branch_id,
                    event_type="workflow_session_updated",
                    payload={
                        "workflow_session_id": session.session_id,
                        "workflow_template_id": session.template_id,
                        "status": session.status,
                        "active_step": session.active_step,
                        "governance_phase": str((governance or {}).get("phase") or "").strip(),
                    },
                )
            )
            return self.workflow_session_summary(session.session_id)
        except Exception as exc:
            self._event_store.append(
                LedgerEvent(
                    mission_id=mission.mission_id,
                    node_id=node.node_id,
                    branch_id=branch.branch_id,
                    event_type="workflow_session_update_failed",
                    payload={
                        "workflow_session_id": session_id,
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
            )
            return None

    def workflow_session_result_summary(
        self,
        *,
        ok: bool,
        branch_status: str,
        result_ref: str,
        result_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload = dict(result_payload or {})
        summary = str(
            payload.get("summary")
            or payload.get("output_bundle_summary")
            or payload.get("output_text")
            or ""
        ).strip()
        result = {
            "ok": bool(ok),
            "branch_status": str(branch_status or "").strip(),
            "result_ref": str(result_ref or "").strip(),
            "recorded_at": str(self._now_factory() or "").strip(),
        }
        if summary:
            result["summary"] = summary[:500]
        return result

    @staticmethod
    def workflow_template_first_step_id(workflow_ir: WorkflowIR | None) -> str:
        if workflow_ir is None:
            return ""
        template = dict(workflow_ir.workflow_template or {})
        steps = template.get("steps")
        if not isinstance(steps, list):
            return ""
        for item in steps:
            if not isinstance(item, dict):
                continue
            step_id = str(item.get("step_id") or item.get("id") or "").strip()
            if step_id:
                return step_id
        return ""

    @staticmethod
    def extract_branch_reference_fields(
        *,
        runtime_plan: dict[str, Any] | None,
        node_metadata: dict[str, Any] | None,
        keys: tuple[str, ...],
    ) -> dict[str, str]:
        result: dict[str, str] = {}
        for key in keys:
            for source in (runtime_plan or {}, node_metadata or {}):
                value = str(source.get(key) or "").strip()
                if value:
                    result[key] = value
                    break
        return result

    @staticmethod
    def extract_branch_workflow_inputs(
        *,
        runtime_plan: dict[str, Any] | None,
        node_metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        for source in (runtime_plan or {}, node_metadata or {}):
            payload = source.get("workflow_inputs")
            if isinstance(payload, dict):
                return dict(payload)
        return {}

    def _workflow_session_file(self, session_id: str) -> Path:
        return self._workflow_factory.session_root(session_id) / "session.json"

    @staticmethod
    def _normalize_feedback_history(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        result: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, Mapping):
                continue
            result.append(
                {
                    "event_id": str(item.get("event_id") or "").strip(),
                    "feedback": str(item.get("feedback") or "").strip(),
                    "recorded_at": str(item.get("recorded_at") or "").strip(),
                }
            )
        return result

    @staticmethod
    def _feedback_recipient_role_id(session: WorkflowSession) -> str:
        driver_kind = str(getattr(session, "driver_kind", "") or "").strip()
        if driver_kind:
            return driver_kind
        role_bindings = list(getattr(session, "role_bindings", []) or [])
        for binding in role_bindings:
            role_id = str(getattr(binding, "role_id", "") or "").strip()
            if role_id:
                return role_id
        return ""

    @staticmethod
    def _bind_workflow_session_refs(
        *,
        branch: Branch,
        node: MissionNode,
        workflow_session_id: str,
        workflow_template_id: str,
        workflow_driver_kind: str,
    ) -> None:
        branch.input_payload["workflow_session_id"] = workflow_session_id
        branch.input_payload["workflow_template_id"] = workflow_template_id
        branch.metadata["workflow_session_id"] = workflow_session_id
        branch.metadata["workflow_template_id"] = workflow_template_id
        node.metadata["workflow_session_id"] = workflow_session_id
        node.metadata["workflow_template_id"] = workflow_template_id
        node.metadata["workflow_driver_kind"] = workflow_driver_kind

    @staticmethod
    def _line_count(path: Path) -> int:
        if not path.exists():
            return 0
        try:
            with path.open("r", encoding="utf-8") as handle:
                return sum(1 for _ in handle)
        except Exception:
            return 0
