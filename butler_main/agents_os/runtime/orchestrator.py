from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from ..contracts import DeliverySession, Invocation, MemoryContext, OutputBundle, PromptContext
from ..factory.agent_spec import AgentSpec
from .projection import RouteProjection, WorkflowProjection
from .receipts import ExecutionReceipt, WorkflowReceipt


@dataclass(slots=True)
class RuntimeRequest:
    invocation: Invocation
    agent_spec: AgentSpec | None = None
    route: RouteProjection | None = None
    workflow: WorkflowProjection | None = None
    delivery_session: DeliverySession | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionContext:
    request: RuntimeRequest
    prompt_context: PromptContext | None = None
    memory_context: MemoryContext | None = None
    runtime_state: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentResult:
    message: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    receipt: ExecutionReceipt | None = None
    output_bundle: OutputBundle | None = None


class AgentRuntime(Protocol):
    def execute(self, context: ExecutionContext) -> ExecutionReceipt:
        ...


class MissionOrchestrator(Protocol):
    def orchestrate(self, request: RuntimeRequest) -> WorkflowReceipt:
        ...


class Orchestrator:
    def __init__(self, execution_runtime: AgentRuntime) -> None:
        self._execution_runtime = execution_runtime

    def dispatch(
        self,
        invocation: Invocation,
        *,
        agent_spec: AgentSpec | None = None,
        route: RouteProjection | None = None,
        workflow: WorkflowProjection | None = None,
        delivery_session: DeliverySession | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ExecutionReceipt:
        context = ExecutionContext(
            request=RuntimeRequest(
                invocation=invocation,
                agent_spec=agent_spec,
                route=route,
                workflow=workflow,
                delivery_session=delivery_session,
                metadata=dict(metadata or {}),
            )
        )
        return self._execution_runtime.execute(context)
