from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Protocol

from .contracts import (
    AcceptanceReceipt,
    Artifact,
    GuardrailDecision,
    Run,
    RunInput,
    RunResult,
    TraceEvent,
    WorkerRequest,
    WorkerResult,
    normalize_failure_class,
)


class Worker(Protocol):
    name: str

    def execute(self, request: WorkerRequest) -> WorkerResult: ...


class Workflow(Protocol):
    name: str

    def execute(self, run: Run, kernel: "RuntimeKernel") -> RunResult: ...


class Guardrails(Protocol):
    def inspect(self, run: Run, *, worker_name: str, payload: Any) -> GuardrailDecision: ...


class ContextStore(Protocol):
    def load(self, session_id: str) -> dict[str, Any]: ...

    def merge(self, session_id: str, updates: dict[str, Any]) -> dict[str, Any]: ...


class ArtifactStore(Protocol):
    def add_many(self, run_id: str, artifacts: list[Artifact]) -> list[Artifact]: ...

    def list_for_run(self, run_id: str) -> list[Artifact]: ...


class TraceObserver(Protocol):
    def record(self, event: TraceEvent) -> TraceEvent: ...

    def list_for_run(self, run_id: str) -> list[TraceEvent]: ...


class WorkerRegistry:
    def __init__(self) -> None:
        self._workers: dict[str, Worker] = {}

    def register(self, worker: Worker) -> None:
        name = str(getattr(worker, "name", "") or "").strip()
        if not name:
            raise ValueError("worker.name is required")
        self._workers[name] = worker

    def get(self, name: str) -> Worker:
        worker_name = str(name or "").strip()
        if worker_name not in self._workers:
            raise KeyError(f"worker not registered: {worker_name}")
        return self._workers[worker_name]


class WorkflowRegistry:
    def __init__(self) -> None:
        self._workflows: dict[str, Workflow] = {}

    def register(self, workflow: Workflow) -> None:
        name = str(getattr(workflow, "name", "") or "").strip()
        if not name:
            raise ValueError("workflow.name is required")
        self._workflows[name] = workflow

    def get(self, name: str) -> Workflow:
        workflow_name = str(name or "").strip()
        if workflow_name not in self._workflows:
            raise KeyError(f"workflow not registered: {workflow_name}")
        return self._workflows[workflow_name]


class InMemoryContextStore:
    def __init__(self) -> None:
        self._by_session: dict[str, dict[str, Any]] = {}

    def load(self, session_id: str) -> dict[str, Any]:
        return dict(self._by_session.get(str(session_id or "").strip(), {}))

    def merge(self, session_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        key = str(session_id or "").strip()
        current = dict(self._by_session.get(key, {}))
        current.update(dict(updates or {}))
        self._by_session[key] = current
        return dict(current)


class InMemoryArtifactStore:
    def __init__(self) -> None:
        self._by_run: dict[str, list[Artifact]] = {}

    def add_many(self, run_id: str, artifacts: list[Artifact]) -> list[Artifact]:
        if not artifacts:
            return []
        key = str(run_id or "").strip()
        bucket = self._by_run.setdefault(key, [])
        bucket.extend(list(artifacts))
        return list(bucket)

    def list_for_run(self, run_id: str) -> list[Artifact]:
        return list(self._by_run.get(str(run_id or "").strip(), []))


class InMemoryTraceObserver:
    def __init__(self) -> None:
        self._by_run: dict[str, list[TraceEvent]] = {}

    def record(self, event: TraceEvent) -> TraceEvent:
        key = str(event.run_id or "").strip()
        self._by_run.setdefault(key, []).append(event)
        return event

    def list_for_run(self, run_id: str) -> list[TraceEvent]:
        return list(self._by_run.get(str(run_id or "").strip(), []))


class AllowAllGuardrails:
    def inspect(self, run: Run, *, worker_name: str, payload: Any) -> GuardrailDecision:
        return GuardrailDecision(allowed=True, reason="", code="allow")


class FunctionWorker:
    def __init__(self, name: str, handler: Callable[[WorkerRequest], WorkerResult]) -> None:
        self.name = str(name or "").strip()
        self._handler = handler

    def execute(self, request: WorkerRequest) -> WorkerResult:
        return self._handler(request)


class SingleWorkerWorkflow:
    name = "single_worker"

    def execute(self, run: Run, kernel: "RuntimeKernel") -> RunResult:
        worker_name = str(run.input.worker or run.metadata.get("worker") or "").strip()
        if not worker_name:
            raise ValueError("run.input.worker is required for single_worker workflow")
        return kernel.dispatch(run, worker_name=worker_name, payload=run.input.payload)


class RuntimeKernel:
    def __init__(
        self,
        *,
        workers: WorkerRegistry | None = None,
        workflows: WorkflowRegistry | None = None,
        context_store: ContextStore | None = None,
        artifact_store: ArtifactStore | None = None,
        trace_observer: TraceObserver | None = None,
        guardrails: Guardrails | None = None,
        default_workflow: str = "single_worker",
    ) -> None:
        self.workers = workers or WorkerRegistry()
        self.workflows = workflows or WorkflowRegistry()
        self.context_store = context_store or InMemoryContextStore()
        self.artifact_store = artifact_store or InMemoryArtifactStore()
        self.trace_observer = trace_observer or InMemoryTraceObserver()
        self.guardrails = guardrails or AllowAllGuardrails()
        self.default_workflow = str(default_workflow or "single_worker").strip() or "single_worker"
        if self.default_workflow == "single_worker":
            self.workflows.register(SingleWorkerWorkflow())

    def register_worker(self, worker: Worker) -> Worker:
        self.workers.register(worker)
        return worker

    def register_workflow(self, workflow: Workflow) -> Workflow:
        self.workflows.register(workflow)
        return workflow

    def create_run(self, run_input: RunInput) -> Run:
        run = Run(input=run_input)
        run.metadata = dict(run_input.metadata or {})
        return run

    def execute(self, run_input: RunInput | Run) -> RunResult:
        run = run_input if isinstance(run_input, Run) else self.create_run(run_input)
        workflow_name = str(run.input.workflow or self.default_workflow).strip() or self.default_workflow
        run.status = "running"
        run.started_at = run.started_at or run.created_at
        self.record(
            run.run_id,
            "run_started",
            {
                "workflow": workflow_name,
                "worker": run.input.worker,
                "session_id": str(run.input.session_id or "").strip(),
            },
        )
        try:
            workflow = self.workflows.get(workflow_name)
            result = workflow.execute(run, self)
        except Exception as exc:
            run.status = "failed"
            run.finished_at = run.finished_at or run.started_at
            acceptance = AcceptanceReceipt(
                goal_achieved=False,
                summary=str(exc),
                evidence=["workflow_exception"],
                uncertainties=["runtime execution aborted before completion"],
                failure_class="worker_error",
            )
            self.record(
                run.run_id,
                "receipt_emitted",
                {"status": "failed", "failure_class": acceptance.failure_class, "goal_achieved": acceptance.goal_achieved},
            )
            self.record(run.run_id, "run_failed", {"error": str(exc), "failure_class": acceptance.failure_class})
            return RunResult(
                run_id=run.run_id,
                status="failed",
                error=str(exc),
                acceptance=acceptance,
                failure_class=acceptance.failure_class,
                trace_count=len(self.trace_observer.list_for_run(run.run_id)),
            )
        run.status = result.status
        run.finished_at = run.finished_at or run.started_at
        terminal_event = "run_failed" if result.status == "failed" else "run_completed"
        self.record(
            run.run_id,
            terminal_event,
            {"status": result.status, "failure_class": str(result.failure_class or "").strip()},
        )
        result.trace_count = len(self.trace_observer.list_for_run(run.run_id))
        return result

    def dispatch(self, run: Run, *, worker_name: str, payload: Any) -> RunResult:
        session_id = str(run.input.session_id or "").strip()
        loaded_context = self.context_store.load(session_id) if session_id else {}
        self.record(
            run.run_id,
            "context_prepared",
            {
                "worker": worker_name,
                "session_id": session_id,
                "context_key_count": len(loaded_context),
            },
        )
        decision = self.guardrails.inspect(run, worker_name=worker_name, payload=payload)
        self.record(
            run.run_id,
            "guardrail_checked",
            {"worker": worker_name, "allowed": decision.allowed, "reason": decision.reason, "code": decision.code},
        )
        if not decision.allowed:
            failure_class = "policy_blocked"
            acceptance = AcceptanceReceipt(
                goal_achieved=False,
                summary=str(decision.reason or "blocked by guardrail").strip(),
                evidence=[f"guardrail:{str(decision.code or 'blocked').strip() or 'blocked'}"],
                uncertainties=["worker dispatch was blocked before execution"],
                failure_class=failure_class,
            )
            self.record(run.run_id, "guardrail_blocked", {"worker": worker_name, "reason": decision.reason, "code": decision.code})
            self.record(
                run.run_id,
                "receipt_emitted",
                {"status": "blocked", "failure_class": failure_class, "goal_achieved": acceptance.goal_achieved},
            )
            return RunResult(
                run_id=run.run_id,
                status="blocked",
                error=decision.reason,
                acceptance=acceptance,
                failure_class=failure_class,
                trace_count=len(self.trace_observer.list_for_run(run.run_id)),
            )

        self.record(run.run_id, "worker_dispatched", {"worker": worker_name})
        worker = self.workers.get(worker_name)
        request = WorkerRequest(
            run=replace(run),
            payload=payload,
            context=loaded_context,
            artifacts=self.artifact_store.list_for_run(run.run_id),
        )
        result = worker.execute(request)
        stored_artifacts = self.artifact_store.add_many(run.run_id, list(result.artifacts or []))
        if session_id and result.context_updates:
            self.context_store.merge(session_id, result.context_updates)
        self.record(run.run_id, "worker_completed", {"worker": worker_name, "status": result.status, "artifact_count": len(stored_artifacts)})
        failure_class = self._resolve_failure_class(result.status, result.message, explicit=result.failure_class)
        acceptance = self._build_acceptance_receipt(
            worker_name=worker_name,
            status=result.status,
            message=result.message,
            stored_artifacts=stored_artifacts,
            explicit_receipt=result.acceptance,
            failure_class=failure_class,
        )
        self.record(
            run.run_id,
            "receipt_emitted",
            {"status": result.status, "failure_class": failure_class, "goal_achieved": acceptance.goal_achieved},
        )
        return RunResult(
            run_id=run.run_id,
            status=result.status,
            output=result.output,
            error=result.message if result.status != "completed" else "",
            artifacts=stored_artifacts,
            acceptance=acceptance,
            failure_class=failure_class,
        )

    def record(self, run_id: str, kind: str, payload: dict[str, Any] | None = None, *, message: str = "") -> TraceEvent:
        event = TraceEvent(run_id=str(run_id or "").strip(), kind=str(kind or "").strip(), message=message, payload=dict(payload or {}))
        return self.trace_observer.record(event)

    def _resolve_failure_class(self, status: str, message: str, *, explicit: str = "") -> str:
        normalized_explicit = normalize_failure_class(explicit)
        if normalized_explicit:
            return normalized_explicit
        normalized_status = str(status or "").strip()
        if normalized_status in {"completed", "running", "pending"}:
            return ""
        if normalized_status == "blocked":
            return "policy_blocked"
        if normalized_status == "failed":
            return "worker_error"
        if normalized_status == "stale":
            return "stale_loop"
        if normalized_status == "invalid":
            return "invalid_plan"
        return "worker_error" if str(message or "").strip() else ""

    def _build_acceptance_receipt(
        self,
        *,
        worker_name: str,
        status: str,
        message: str,
        stored_artifacts: list[Artifact],
        explicit_receipt: AcceptanceReceipt | None,
        failure_class: str,
    ) -> AcceptanceReceipt:
        if explicit_receipt is not None:
            explicit_receipt.failure_class = normalize_failure_class(explicit_receipt.failure_class, default=failure_class)
            return explicit_receipt
        normalized_status = str(status or "").strip()
        summary = str(message or "").strip()
        if not summary:
            if normalized_status == "completed":
                summary = f"worker {worker_name} completed"
            elif normalized_status == "blocked":
                summary = f"worker {worker_name} was blocked"
            else:
                summary = f"worker {worker_name} returned {normalized_status or 'unknown'}"
        return AcceptanceReceipt(
            goal_achieved=normalized_status == "completed",
            summary=summary,
            evidence=[f"worker:{worker_name}", f"status:{normalized_status or 'unknown'}"],
            artifacts=[str(item.uri or item.artifact_id or "").strip() for item in stored_artifacts if str(item.uri or item.artifact_id or "").strip()],
            uncertainties=[] if normalized_status == "completed" else ["result requires follow-up or review"],
            next_action="" if normalized_status == "completed" else "inspect failure and decide next step",
            failure_class=failure_class,
        )
