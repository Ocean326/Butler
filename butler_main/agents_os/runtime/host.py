from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from ..protocol import DecisionReceipt, HandoffReceipt, StepReceipt
from ..process_runtime.workflow import FileWorkflowCheckpointStore, WorkflowCheckpoint, WorkflowCursor
from .contracts import Run, RunInput, RunResult
from .instance import AgentRuntimeInstance, normalize_instance_status
from .instance_store import FileInstanceStore
from .kernel import RuntimeKernel
from .session_support import FileSessionCheckpointStore, RuntimeSessionCheckpoint, merge_session_snapshots


def _bump_cursor(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "1"
    try:
        return str(int(text) + 1)
    except Exception:
        return text


class RuntimeHost:
    def __init__(self, kernel: RuntimeKernel | None = None, *, instance_store: FileInstanceStore | None = None) -> None:
        self.kernel = kernel or RuntimeKernel()
        self.instance_store = instance_store or FileInstanceStore()

    def create_instance(self, profile: Mapping[str, Any] | None = None) -> AgentRuntimeInstance:
        payload = dict(profile or {})
        instance = AgentRuntimeInstance.from_dict(payload)
        instance.ensure_roots(self.instance_store.instance_root(instance.instance_id))
        return self.instance_store.create(instance)

    def load_instance(self, instance_id: str) -> AgentRuntimeInstance:
        return self.instance_store.load(instance_id)

    def update_instance(self, instance_id: str, patch: Mapping[str, Any]) -> AgentRuntimeInstance:
        return self.instance_store.update(instance_id, patch)

    def submit_run(self, instance_id: str, run_input: RunInput | Mapping[str, Any] | Run) -> RunResult:
        instance = self.load_instance(instance_id)
        prepared_input = self._prepare_run_input(instance, run_input)
        run = replace(run_input, input=prepared_input) if isinstance(run_input, Run) else self.kernel.create_run(prepared_input)

        instance.status = "running"
        instance.active_run_id = run.run_id
        instance.current_goal = str(run.input.metadata.get("goal") or instance.current_goal or "").strip()
        instance.touch(status="running")
        self.instance_store.save(instance)
        self.instance_store.append_event(
            instance.instance_id,
            kind="run_submitted",
            payload={"run_id": run.run_id, "worker": run.input.worker, "session_id": run.input.session_id},
        )
        self._checkpoint_store(instance).save(
            RuntimeSessionCheckpoint(
                instance_id=instance.instance_id,
                session_id=instance.session_id,
                status="running",
                run_input=self._serialize_run_input(run.input),
                session=instance.session_snapshot(),
                context=self._context_snapshot(instance.session_id),
                metadata={"run_id": run.run_id, "phase": "before_execute"},
            )
        )
        workflow_cursor = self._prepare_workflow_cursor(instance, run.input)
        if workflow_cursor is not None:
            self._workflow_store(instance).save(
                WorkflowCheckpoint(
                    instance_id=instance.instance_id,
                    session_id=instance.session_id,
                    run_id=run.run_id,
                    workflow_id=workflow_cursor.workflow_id,
                    cursor=workflow_cursor,
                    metadata={"phase": "before_execute"},
                )
            )

        result = self.kernel.execute(run)
        self._finalize_instance(instance, run.input, result)
        return result

    def resume_instance(self, instance_id: str, checkpoint_id: str | None = None) -> RunResult:
        instance = self.load_instance(instance_id)
        checkpoint_store = self._checkpoint_store(instance)
        checkpoint = checkpoint_store.get(checkpoint_id or "") if checkpoint_id else checkpoint_store.latest()
        if checkpoint is None:
            raise FileNotFoundError(f"checkpoint not found for instance: {instance_id}")
        if not checkpoint.run_input:
            raise ValueError(f"checkpoint missing run_input: {checkpoint.checkpoint_id}")

        merged_session, persisted_won = merge_session_snapshots(instance.session_snapshot(), checkpoint.session)
        instance.conversation_cursor = str(merged_session.get("conversation_cursor") or instance.conversation_cursor)
        instance.last_checkpoint_id = checkpoint.checkpoint_id
        instance.active_workflow_id = str(merged_session.get("active_workflow_id") or instance.active_workflow_id or "")
        instance.current_step_id = str(merged_session.get("current_step_id") or instance.current_step_id or "")
        instance.last_workflow_checkpoint_id = str(merged_session.get("last_workflow_checkpoint_id") or instance.last_workflow_checkpoint_id or "")
        instance.latest_decision = str(merged_session.get("latest_decision") or instance.latest_decision or "")
        latest_workflow_checkpoint = self._workflow_store(instance).latest()
        if latest_workflow_checkpoint is not None:
            instance.active_workflow_id = str(latest_workflow_checkpoint.workflow_id or instance.active_workflow_id or "")
            instance.current_step_id = str(latest_workflow_checkpoint.cursor.current_step_id or instance.current_step_id or "")
            instance.current_handoff_id = str(latest_workflow_checkpoint.cursor.pending_handoff_id or instance.current_handoff_id or "")
            instance.latest_decision = str(latest_workflow_checkpoint.cursor.latest_decision or instance.latest_decision or "")
            instance.last_workflow_checkpoint_id = latest_workflow_checkpoint.checkpoint_id
        if persisted_won:
            instance.current_goal = str(merged_session.get("current_goal") or instance.current_goal or "")
        self.instance_store.save(instance)
        return self.submit_run(instance_id, checkpoint.run_input)

    def retire_instance(self, instance_id: str) -> AgentRuntimeInstance:
        return self.instance_store.retire(instance_id)

    def _prepare_run_input(self, instance: AgentRuntimeInstance, run_input: RunInput | Mapping[str, Any] | Run) -> RunInput:
        if isinstance(run_input, Run):
            prepared = run_input.input
        elif isinstance(run_input, RunInput):
            prepared = run_input
        else:
            payload = dict(run_input or {})
            prepared = RunInput(
                payload=payload.get("payload"),
                worker=str(payload.get("worker") or "").strip(),
                workflow=str(payload.get("workflow") or "single_worker").strip() or "single_worker",
                session_id=str(payload.get("session_id") or "").strip(),
                task_id=str(payload.get("task_id") or "").strip(),
                metadata=dict(payload.get("metadata") or {}),
            )
        metadata = dict(prepared.metadata or {})
        metadata.update(
            {
                "instance_id": instance.instance_id,
                "agent_id": instance.agent_id,
                "agent_kind": instance.agent_kind,
                "manager_id": instance.manager_id,
                "owner_domain": instance.owner_domain,
            }
        )
        if not str(prepared.session_id or "").strip():
            prepared = replace(prepared, session_id=instance.session_id)
        prepared.metadata = metadata
        return prepared

    def _finalize_instance(self, instance: AgentRuntimeInstance, run_input: RunInput, result: RunResult) -> None:
        next_status = self._map_result_status(result.status)
        instance.status = next_status
        instance.active_run_id = result.run_id
        instance.conversation_cursor = _bump_cursor(instance.conversation_cursor)
        instance.working_summary = str((result.acceptance.summary if result.acceptance else "") or instance.working_summary or "").strip()
        instance.last_error = str(result.error or "").strip()
        instance.health_state = "healthy" if next_status in {"idle", "blocked"} else "degraded"
        instance.last_activity_at = instance.updated_at
        workflow_cursor = self._resolve_workflow_cursor(instance, run_input, result, next_status)
        step_receipt = self._extract_step_receipt(result)
        handoff_receipt = self._extract_handoff_receipt(result)
        decision_receipt = self._extract_decision_receipt(result)
        if workflow_cursor is not None:
            instance.active_workflow_id = workflow_cursor.workflow_id
            instance.current_step_id = workflow_cursor.current_step_id
            instance.current_handoff_id = workflow_cursor.pending_handoff_id
            instance.latest_decision = workflow_cursor.latest_decision
        checkpoint = RuntimeSessionCheckpoint(
            instance_id=instance.instance_id,
            session_id=instance.session_id,
            status=next_status,
            run_input=self._serialize_run_input(run_input),
            session=instance.session_snapshot(),
            context=self._context_snapshot(run_input.session_id),
            metadata={"run_id": result.run_id, "failure_class": result.failure_class, "trace_count": result.trace_count},
        )
        checkpoint_store = self._checkpoint_store(instance)
        checkpoint_store.save(checkpoint)
        checkpoint_store.write_current(checkpoint)
        instance.last_checkpoint_id = checkpoint.checkpoint_id
        if workflow_cursor is not None:
            workflow_checkpoint = WorkflowCheckpoint(
                instance_id=instance.instance_id,
                session_id=instance.session_id,
                run_id=result.run_id,
                workflow_id=workflow_cursor.workflow_id,
                cursor=workflow_cursor,
                step_receipt=step_receipt,
                handoff_receipt=handoff_receipt,
                decision_receipt=decision_receipt,
                acceptance=result.acceptance,
                metadata={"failure_class": result.failure_class, "trace_count": result.trace_count},
            )
            workflow_store = self._workflow_store(instance)
            workflow_store.save(workflow_checkpoint)
            workflow_store.write_current(workflow_checkpoint)
            instance.last_workflow_checkpoint_id = workflow_checkpoint.checkpoint_id
        instance.touch(status=next_status)
        self.instance_store.save(instance)
        self.instance_store.append_event(
            instance.instance_id,
            kind="run_completed" if result.status != "failed" else "run_failed",
            payload={
                "run_id": result.run_id,
                "status": result.status,
                "failure_class": result.failure_class,
                "trace_count": result.trace_count,
            },
            message=str(result.error or ""),
        )

    def _checkpoint_store(self, instance: AgentRuntimeInstance) -> FileSessionCheckpointStore:
        session_root = Path(instance.roots.get("session_root") or self.instance_store.instance_root(instance.instance_id) / "session")
        return FileSessionCheckpointStore(session_root / "checkpoints" / "checkpoints.jsonl")

    def _workflow_store(self, instance: AgentRuntimeInstance) -> FileWorkflowCheckpointStore:
        workflow_root = Path(instance.roots.get("workflow_root") or self.instance_store.instance_root(instance.instance_id) / "workflow")
        return FileWorkflowCheckpointStore(workflow_root / "checkpoints" / "checkpoints.jsonl")

    def _context_snapshot(self, session_id: str) -> dict[str, Any]:
        if not str(session_id or "").strip():
            return {}
        return dict(self.kernel.context_store.load(session_id))

    def _serialize_run_input(self, run_input: RunInput) -> dict[str, Any]:
        return {
            "payload": run_input.payload,
            "worker": run_input.worker,
            "workflow": run_input.workflow,
            "session_id": run_input.session_id,
            "task_id": run_input.task_id,
            "metadata": dict(run_input.metadata or {}),
        }

    def _prepare_workflow_cursor(self, instance: AgentRuntimeInstance, run_input: RunInput) -> WorkflowCursor | None:
        metadata = dict(run_input.metadata or {})
        explicit = metadata.get("workflow_cursor")
        if isinstance(explicit, Mapping):
            cursor = WorkflowCursor.from_dict(explicit)
            if cursor.workflow_id:
                cursor.status = "running"
                return cursor
        workflow_id = str(metadata.get("workflow_id") or instance.active_workflow_id or "").strip()
        if not workflow_id and str(run_input.workflow or "").strip() not in {"", "single_worker"}:
            workflow_id = str(run_input.workflow or "").strip()
        if not workflow_id:
            return None
        return WorkflowCursor(
            workflow_id=workflow_id,
            current_step_id=str(metadata.get("current_step_id") or metadata.get("step_id") or instance.current_step_id or "").strip(),
            pending_handoff_id=str(instance.current_handoff_id or "").strip(),
            latest_decision=str(instance.latest_decision or "").strip(),
            status="running",
            metadata={"source": "run_input"},
        )

    def _resolve_workflow_cursor(
        self,
        instance: AgentRuntimeInstance,
        run_input: RunInput,
        result: RunResult,
        next_status: str,
    ) -> WorkflowCursor | None:
        output = result.output if isinstance(result.output, Mapping) else {}
        explicit = output.get("workflow_cursor") if isinstance(output, Mapping) else None
        if isinstance(explicit, Mapping):
            cursor = WorkflowCursor.from_dict(explicit)
        else:
            cursor = self._prepare_workflow_cursor(instance, run_input)
            if cursor is None:
                return None
        cursor.status = "idle" if next_status == "idle" else next_status
        if not cursor.current_step_id:
            cursor.current_step_id = str((output.get("current_step_id") if isinstance(output, Mapping) else "") or instance.current_step_id or "").strip()
        handoff = self._extract_handoff_receipt(result)
        decision = self._extract_decision_receipt(result)
        if handoff is not None:
            cursor.pending_handoff_id = handoff.handoff_id
        if decision is not None:
            cursor.latest_decision = decision.decision
            if decision.resume_from:
                cursor.resume_from = decision.resume_from
        return cursor

    def _extract_step_receipt(self, result: RunResult) -> StepReceipt | None:
        output = result.output if isinstance(result.output, Mapping) else {}
        payload = output.get("step_receipt") if isinstance(output, Mapping) else None
        if isinstance(payload, Mapping) and payload:
            return StepReceipt.from_dict(payload)
        return None

    def _extract_handoff_receipt(self, result: RunResult) -> HandoffReceipt | None:
        output = result.output if isinstance(result.output, Mapping) else {}
        payload = output.get("handoff_receipt") if isinstance(output, Mapping) else None
        if isinstance(payload, Mapping) and payload:
            return HandoffReceipt.from_dict(payload)
        return None

    def _extract_decision_receipt(self, result: RunResult) -> DecisionReceipt | None:
        output = result.output if isinstance(result.output, Mapping) else {}
        payload = output.get("decision_receipt") if isinstance(output, Mapping) else None
        if isinstance(payload, Mapping) and payload:
            return DecisionReceipt.from_dict(payload)
        return None

    def _map_result_status(self, status: str) -> str:
        normalized = str(status or "").strip()
        if normalized in {"completed", "pending", "cancelled"}:
            return "idle"
        if normalized == "blocked":
            return "blocked"
        if normalized in {"failed", "stale"}:
            return "failed"
        if normalized == "running":
            return "running"
        return normalize_instance_status(normalized, default="idle")
