from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol

from ..contracts import Invocation, OutputBundle, TextBlock
from ..protocol import DecisionReceipt, HandoffReceipt, StepReceipt
from ..process_runtime.workflow import (
    FileWorkflowCheckpointStore,
    WorkflowCheckpoint,
    WorkflowCursor,
    WorkflowEdgeSpec,
    WorkflowRunProjection,
    WorkflowSpec,
    WorkflowStepSpec,
)
from .capability_registry import CapabilityRegistry
from .contracts import normalize_failure_class, normalize_run_status
from .orchestrator import AgentResult, AgentRuntime, ExecutionContext
from .receipts import ExecutionReceipt
from .subworkflow_interface import CapabilityBinding, CapabilityResolver


class ExecutionHandler(Protocol):
    def __call__(
        self,
        context: ExecutionContext,
        *,
        binding: CapabilityBinding | None,
        contract: Mapping[str, Any],
    ) -> ExecutionReceipt | Mapping[str, Any] | None: ...


@dataclass(slots=True)
class _StepOutcome:
    status: str = "completed"
    summary: str = ""
    transition: str = "success"
    metadata: dict[str, Any] = field(default_factory=dict)
    output_bundle: OutputBundle | None = None
    model_input: Any = None
    evidence: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    handoff_payload: dict[str, Any] = field(default_factory=dict)
    decision: str = ""
    next_action: str = ""
    resume_from: str = ""
    failure_class: str = ""

    def __post_init__(self) -> None:
        self.status = normalize_run_status(self.status, default="completed")
        self.failure_class = normalize_failure_class(self.failure_class)
        if str(self.transition or "").strip():
            self.transition = str(self.transition).strip().lower()
            return
        if self.status == "failed":
            self.transition = "failure"
        elif self.status == "blocked":
            self.transition = "blocked"
        elif self.status in {"pending", "running"}:
            self.transition = "pending"
        else:
            self.transition = "success"


def _coerce_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _coerce_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    lowered = str(value or "").strip().lower()
    if not lowered:
        return default
    if lowered in {"1", "true", "yes", "on", "required", "enabled"}:
        return True
    if lowered in {"0", "false", "no", "off", "optional", "disabled"}:
        return False
    return default


def _normalize_gate_status(value: Any) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"approved", "passed", "verified", "skipped", "not_required", "complete", "completed"}:
        return lowered
    if lowered in {"failed", "rejected", "blocked", "pending", "queued"}:
        return lowered
    return ""


def _dedupe_edges(edges: list[WorkflowEdgeSpec]) -> list[WorkflowEdgeSpec]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[WorkflowEdgeSpec] = []
    for edge in edges:
        key = (edge.source_step_id, edge.edge_kind, edge.target_step_id)
        if key in seen or not edge.source_step_id:
            continue
        seen.add(key)
        deduped.append(edge)
    return deduped


def _build_step_specs(
    workflow_id: str,
    current_step_id: str,
    *,
    workflow_template: Mapping[str, Any],
    verification_required: bool,
    approval_required: bool,
) -> list[WorkflowStepSpec]:
    raw_steps = workflow_template.get("steps")
    step_specs: list[WorkflowStepSpec] = []
    if isinstance(raw_steps, list):
        for item in raw_steps:
            if not isinstance(item, Mapping):
                continue
            step_id = str(item.get("step_id") or item.get("id") or "").strip()
            if not step_id:
                continue
            metadata = dict(item)
            metadata.setdefault("workflow_id", workflow_id)
            step_specs.append(
                WorkflowStepSpec(
                    step_id=step_id,
                    step_kind=str(item.get("step_kind") or item.get("kind") or "dispatch").strip() or "dispatch",
                    process_role=str(item.get("process_role") or item.get("role") or "executor").strip() or "executor",
                    worker_hint=str(item.get("worker_hint") or item.get("worker") or "").strip(),
                    requires_verification=_coerce_bool(item.get("requires_verification"), default=verification_required),
                    requires_approval=_coerce_bool(item.get("requires_approval"), default=approval_required),
                    allow_parallel=_coerce_bool(item.get("allow_parallel"), default=False),
                    metadata=metadata,
                )
            )
    if step_specs:
        return step_specs
    if current_step_id:
        return [
            WorkflowStepSpec(
                step_id=current_step_id,
                requires_verification=verification_required,
                requires_approval=approval_required,
                metadata={"workflow_id": workflow_id, "source": "current_step_fallback"},
            )
        ]
    return []


def _build_edge_specs(step_specs: list[WorkflowStepSpec], workflow_template: Mapping[str, Any]) -> list[WorkflowEdgeSpec]:
    raw_edges = workflow_template.get("edges")
    explicit_edges: list[WorkflowEdgeSpec] = []
    if isinstance(raw_edges, list):
        for item in raw_edges:
            if not isinstance(item, Mapping):
                continue
            edge = WorkflowEdgeSpec.from_dict(item)
            if edge.source_step_id:
                explicit_edges.append(edge)
    raw_steps = workflow_template.get("steps")
    if isinstance(raw_steps, list):
        for item in raw_steps:
            if not isinstance(item, Mapping):
                continue
            step_id = str(item.get("step_id") or item.get("id") or "").strip()
            if not step_id:
                continue
            for edge_kind in ("next", "on_success", "on_failure", "resume_from"):
                target = str(item.get(edge_kind) or "").strip()
                if not target:
                    continue
                explicit_edges.append(
                    WorkflowEdgeSpec(
                        source_step_id=step_id,
                        target_step_id=target,
                        edge_kind=edge_kind,
                        metadata={"source": "step_inline"},
                    )
                )
    if explicit_edges:
        return _dedupe_edges(explicit_edges)
    fallback_edges: list[WorkflowEdgeSpec] = []
    for index, step in enumerate(step_specs[:-1]):
        fallback_edges.append(
            WorkflowEdgeSpec(
                source_step_id=step.step_id,
                target_step_id=step_specs[index + 1].step_id,
                edge_kind="next",
                metadata={"source": "sequential_fallback"},
            )
        )
    return fallback_edges


class ExecutionRuntime(AgentRuntime):
    def __init__(
        self,
        *,
        capability_resolver: CapabilityResolver | None = None,
        checkpoint_store: FileWorkflowCheckpointStore | None = None,
        handler: ExecutionHandler | None = None,
        default_ready_status: str = "pending",
    ) -> None:
        self._capability_resolver = capability_resolver or CapabilityRegistry()
        self._checkpoint_store = checkpoint_store
        self._handler = handler
        self._default_ready_status = str(default_ready_status or "pending").strip() or "pending"

    def execute(self, context: ExecutionContext) -> ExecutionReceipt:
        request = context.request
        workflow_projection = request.workflow
        workflow_id = workflow_projection.workflow_id if workflow_projection is not None else ""
        workflow_kind = workflow_projection.workflow_kind if workflow_projection is not None else ""
        workflow_metadata = _coerce_mapping(workflow_projection.metadata if workflow_projection is not None else {})
        runtime_metadata = _coerce_mapping(request.metadata)
        workflow_ir = _coerce_mapping(runtime_metadata.get("workflow_ir"))
        workflow_template = _coerce_mapping(workflow_ir.get("workflow_template") or workflow_metadata.get("workflow_template"))
        gate_contracts = self._resolve_gate_contracts(workflow_metadata=workflow_metadata, workflow_ir=workflow_ir)
        requested_step_id = str(
            workflow_projection.current_step_id if workflow_projection is not None else ""
        ).strip() or str(runtime_metadata.get("current_step_id") or runtime_metadata.get("step_id") or "").strip()
        step_specs = _build_step_specs(
            workflow_id,
            requested_step_id,
            workflow_template=workflow_template,
            verification_required=gate_contracts["verification"]["required"],
            approval_required=gate_contracts["approval"]["required"],
        )
        workflow_spec = WorkflowSpec(
            workflow_id=workflow_id,
            run_type=str(workflow_kind or request.invocation.entrypoint or "").strip(),
            title=str(workflow_template.get("title") or workflow_ir.get("node_title") or workflow_id or "").strip(),
            scenario_id=str(runtime_metadata.get("scenario_id") or workflow_ir.get("research_unit_id") or "").strip(),
            steps=step_specs,
            edges=_build_edge_specs(step_specs, workflow_template),
            metadata={
                "workflow_kind": workflow_kind,
                "template_id": str(workflow_ir.get("workflow_template_id") or workflow_metadata.get("template_id") or "").strip(),
                "workflow_session_id": str(workflow_ir.get("workflow_session_id") or workflow_metadata.get("workflow_session_id") or "").strip(),
            },
        )
        capability_resolution = self._resolve_capability(
            invocation=request.invocation,
            workflow_kind=workflow_kind,
            workflow_projection=workflow_projection,
            gate_contracts=gate_contracts,
        )
        checkpoint_store = self._resolve_checkpoint_store(request=request)
        checkpoint_hint = str(
            context.runtime_state.get("checkpoint_id")
            or context.runtime_state.get("workflow_checkpoint_id")
            or request.metadata.get("checkpoint_id")
            or request.metadata.get("workflow_checkpoint_id")
            or ""
        ).strip()
        resume_checkpoint = self._load_resume_checkpoint(
            request=request,
            runtime_state=context.runtime_state,
            checkpoint_store=checkpoint_store,
        )
        projection = self._restore_projection(workflow_spec=workflow_spec, checkpoint=resume_checkpoint)
        cursor = self._resolve_cursor(
            workflow_spec=workflow_spec,
            requested_step_id=requested_step_id,
            runtime_state=context.runtime_state,
            checkpoint=resume_checkpoint,
            existing_cursor=projection.cursor,
        )
        projection.cursor = cursor
        return self._run_engine(
            context=context,
            workflow_spec=workflow_spec,
            projection=projection,
            cursor=cursor,
            gate_contracts=gate_contracts,
            capability_resolution=capability_resolution,
            checkpoint_store=checkpoint_store,
            resume_checkpoint=resume_checkpoint,
            checkpoint_hint=checkpoint_hint,
        )

    def run(self, context: ExecutionContext) -> AgentResult:
        receipt = self.execute(context)
        return AgentResult(
            message=receipt.summary,
            payload=receipt.metadata,
            receipt=receipt,
            output_bundle=receipt.output_bundle,
        )

    def _run_engine(
        self,
        *,
        context: ExecutionContext,
        workflow_spec: WorkflowSpec,
        projection: WorkflowRunProjection,
        cursor: WorkflowCursor,
        gate_contracts: Mapping[str, Mapping[str, Any]],
        capability_resolution: Mapping[str, Any],
        checkpoint_store: FileWorkflowCheckpointStore | None,
        resume_checkpoint: WorkflowCheckpoint | None,
        checkpoint_hint: str,
    ) -> ExecutionReceipt:
        request = context.request
        if workflow_spec.step_by_id(cursor.current_step_id) is None:
            return self._invalid_plan_receipt(
                context=context,
                workflow_spec=workflow_spec,
                projection=projection,
                cursor=cursor,
                gate_contracts=gate_contracts,
                capability_resolution=capability_resolution,
                checkpoint_store=checkpoint_store,
                resumed_from_checkpoint=resume_checkpoint is not None,
                checkpoint_hint=checkpoint_hint,
            )

        latest_output_bundle: OutputBundle | None = None
        latest_model_input: Any = None
        latest_checkpoint = resume_checkpoint
        resumed_from_checkpoint = resume_checkpoint is not None
        guard_budget = max(1, len(workflow_spec.steps) * 3)

        while guard_budget > 0:
            guard_budget -= 1
            current_step = workflow_spec.step_by_id(cursor.current_step_id)
            if current_step is None:
                break
            step_binding_resolution = self._resolve_step_binding(
                step=current_step,
                workflow_projection=request.workflow,
                capability_resolution=capability_resolution,
            )
            current_step_mode = self._side_effect_mode(current_step)
            semantic_contract = self._build_semantic_contract(
                request=request,
                workflow_spec=workflow_spec,
                projection=projection,
                cursor=cursor,
                gate_contracts=gate_contracts,
                capability_resolution=capability_resolution,
                step_binding_resolution=step_binding_resolution,
                current_step=current_step,
                current_step_mode=current_step_mode,
            )
            pre_gate = self._decide_pre_step_gate(
                workflow_spec=workflow_spec,
                step=current_step,
                gate_contracts=gate_contracts,
                runtime_state=context.runtime_state,
            )
            if pre_gate is not None:
                outcome = pre_gate
            elif self._step_requires_external_execution(current_step):
                if step_binding_resolution["required"] and not step_binding_resolution["matched"]:
                    outcome = _StepOutcome(
                        status="failed",
                        summary=f"execution contract missing capability binding for step {current_step.step_id}",
                        transition="failure",
                        metadata={"phase": "capability_resolution_failed"},
                        failure_class="context_missing",
                    )
                else:
                    outcome = self._execute_external_step(
                        context=context,
                        step=current_step,
                        binding=step_binding_resolution["selected_binding"],
                        contract=semantic_contract,
                    )
            else:
                outcome = self._execute_internal_step(
                    step=current_step,
                    workflow_spec=workflow_spec,
                    runtime_state=context.runtime_state,
                    gate_contracts=gate_contracts,
                    latest_handoff=projection.handoff_receipts[-1] if projection.handoff_receipts else None,
                )
            if outcome.output_bundle is not None:
                latest_output_bundle = outcome.output_bundle
            if outcome.model_input is not None:
                latest_model_input = outcome.model_input
            step_receipt = self._build_step_receipt(
                workflow_spec=workflow_spec,
                step=current_step,
                outcome=outcome,
                current_step_mode=current_step_mode,
                binding_resolution=step_binding_resolution,
            )
            projection.step_receipts.append(step_receipt)
            cursor.iteration += 1
            cursor.updated_at = step_receipt.created_at

            if outcome.transition in {"blocked", "pending"}:
                cursor.status = normalize_run_status(outcome.status, default="pending")
                cursor.current_step_id = current_step.step_id
                cursor.resume_from = outcome.resume_from or current_step.step_id
                cursor.latest_decision = outcome.decision or "wait"
                decision_receipt = self._build_decision_receipt(
                    workflow_spec=workflow_spec,
                    step=current_step,
                    outcome=outcome,
                    next_step_id="",
                    edge_kind="",
                )
                projection.decision_receipts.append(decision_receipt)
                projection.cursor = cursor
                latest_checkpoint = self._save_checkpoint(
                    checkpoint_store=checkpoint_store,
                    request=request,
                    workflow_spec=workflow_spec,
                    cursor=cursor,
                    projection=projection,
                    step_receipt=step_receipt,
                    handoff_receipt=None,
                    decision_receipt=decision_receipt,
                    extra_metadata={"failure_class": outcome.failure_class, "projection": projection.to_dict()},
                )
                return self._final_receipt(
                    context=context,
                    workflow_spec=workflow_spec,
                    projection=projection,
                    gate_contracts=gate_contracts,
                    capability_resolution=capability_resolution,
                    step_binding_resolution=step_binding_resolution,
                    current_step=current_step,
                    current_step_mode=current_step_mode,
                    checkpoint=latest_checkpoint,
                    status=outcome.status,
                    summary=outcome.summary or f"workflow is waiting at step {current_step.step_id}",
                    phase=str(outcome.metadata.get("phase") or "waiting"),
                    resumed_from_checkpoint=resumed_from_checkpoint,
                    failure_class=outcome.failure_class,
                    output_bundle=latest_output_bundle,
                    model_input=latest_model_input,
                    extra_metadata=outcome.metadata,
                    checkpoint_hint=checkpoint_hint,
                    prefer_checkpoint_hint=checkpoint_store is None and bool(checkpoint_hint),
                )

            next_step_id, edge_kind = self._select_transition_target(
                workflow_spec=workflow_spec,
                step=current_step,
                transition=outcome.transition,
            )
            decision_receipt = self._build_decision_receipt(
                workflow_spec=workflow_spec,
                step=current_step,
                outcome=outcome,
                next_step_id=next_step_id,
                edge_kind=edge_kind,
            )
            projection.decision_receipts.append(decision_receipt)
            cursor.latest_decision = decision_receipt.decision
            if outcome.transition == "failure" and not next_step_id:
                cursor.status = "failed"
                cursor.current_step_id = current_step.step_id
                cursor.resume_from = outcome.resume_from or current_step.step_id
                cursor.pending_handoff_id = ""
                projection.cursor = cursor
                latest_checkpoint = self._save_checkpoint(
                    checkpoint_store=checkpoint_store,
                    request=request,
                    workflow_spec=workflow_spec,
                    cursor=cursor,
                    projection=projection,
                    step_receipt=step_receipt,
                    handoff_receipt=None,
                    decision_receipt=decision_receipt,
                    extra_metadata={"failure_class": outcome.failure_class, "projection": projection.to_dict()},
                )
                return self._final_receipt(
                    context=context,
                    workflow_spec=workflow_spec,
                    projection=projection,
                    gate_contracts=gate_contracts,
                    capability_resolution=capability_resolution,
                    step_binding_resolution=step_binding_resolution,
                    current_step=current_step,
                    current_step_mode=current_step_mode,
                    checkpoint=latest_checkpoint,
                    status="failed",
                    summary=outcome.summary or f"workflow failed at step {current_step.step_id}",
                    phase=str(outcome.metadata.get("phase") or "failed"),
                    resumed_from_checkpoint=resumed_from_checkpoint,
                    failure_class=outcome.failure_class,
                    output_bundle=latest_output_bundle,
                    model_input=latest_model_input,
                    extra_metadata=outcome.metadata,
                    checkpoint_hint=checkpoint_hint,
                    prefer_checkpoint_hint=checkpoint_store is None and bool(checkpoint_hint),
                )

            if next_step_id:
                handoff_receipt = self._build_handoff_receipt(
                    workflow_spec=workflow_spec,
                    step=current_step,
                    outcome=outcome,
                    next_step_id=next_step_id,
                    edge_kind=edge_kind,
                )
                projection.handoff_receipts.append(handoff_receipt)
                cursor.pending_handoff_id = handoff_receipt.handoff_id
                cursor.current_step_id = next_step_id
                cursor.resume_from = next_step_id
                cursor.status = "running"
                projection.cursor = cursor
                latest_checkpoint = self._save_checkpoint(
                    checkpoint_store=checkpoint_store,
                    request=request,
                    workflow_spec=workflow_spec,
                    cursor=cursor,
                    projection=projection,
                    step_receipt=step_receipt,
                    handoff_receipt=handoff_receipt,
                    decision_receipt=decision_receipt,
                    extra_metadata={"failure_class": outcome.failure_class, "projection": projection.to_dict()},
                )
                continue

            cursor.status = "completed" if outcome.status != "failed" else "failed"
            cursor.pending_handoff_id = ""
            cursor.resume_from = ""
            cursor.current_step_id = current_step.step_id
            projection.cursor = cursor
            latest_checkpoint = self._save_checkpoint(
                checkpoint_store=checkpoint_store,
                request=request,
                workflow_spec=workflow_spec,
                cursor=cursor,
                projection=projection,
                step_receipt=step_receipt,
                handoff_receipt=None,
                decision_receipt=decision_receipt,
                extra_metadata={"failure_class": outcome.failure_class, "projection": projection.to_dict()},
            )
            return self._final_receipt(
                context=context,
                workflow_spec=workflow_spec,
                projection=projection,
                gate_contracts=gate_contracts,
                capability_resolution=capability_resolution,
                step_binding_resolution=step_binding_resolution,
                current_step=current_step,
                current_step_mode=current_step_mode,
                checkpoint=latest_checkpoint,
                status="completed" if outcome.status != "failed" else "failed",
                summary=outcome.summary or f"workflow finished at step {current_step.step_id}",
                phase=str(outcome.metadata.get("phase") or ("executed" if current_step_mode == "external" else "completed")),
                resumed_from_checkpoint=resumed_from_checkpoint,
                failure_class=outcome.failure_class,
                output_bundle=latest_output_bundle,
                model_input=latest_model_input,
                extra_metadata=outcome.metadata,
                checkpoint_hint=checkpoint_hint,
                prefer_checkpoint_hint=checkpoint_store is None and bool(checkpoint_hint),
            )

        cursor.status = "failed"
        projection.cursor = cursor
        latest_checkpoint = self._save_checkpoint(
            checkpoint_store=checkpoint_store,
            request=request,
            workflow_spec=workflow_spec,
            cursor=cursor,
            projection=projection,
            step_receipt=None,
            handoff_receipt=None,
            decision_receipt=None,
            extra_metadata={"failure_class": "stale_loop", "projection": projection.to_dict()},
        )
        return self._final_receipt(
            context=context,
            workflow_spec=workflow_spec,
            projection=projection,
            gate_contracts=gate_contracts,
            capability_resolution=capability_resolution,
            step_binding_resolution={},
            current_step=workflow_spec.step_by_id(cursor.current_step_id),
            current_step_mode="internal",
            checkpoint=latest_checkpoint,
            status="failed",
            summary="workflow execution aborted because the transition budget was exhausted",
            phase="stale_loop",
            resumed_from_checkpoint=resumed_from_checkpoint,
            failure_class="stale_loop",
            output_bundle=latest_output_bundle,
            model_input=latest_model_input,
            extra_metadata={},
            checkpoint_hint=checkpoint_hint,
            prefer_checkpoint_hint=checkpoint_store is None and bool(checkpoint_hint),
        )

    @staticmethod
    def _resolve_gate_contracts(
        *,
        workflow_metadata: Mapping[str, Any],
        workflow_ir: Mapping[str, Any],
    ) -> dict[str, dict[str, Any]]:
        approval = _coerce_mapping(workflow_metadata.get("approval") or workflow_ir.get("approval"))
        verification = _coerce_mapping(workflow_metadata.get("verification") or workflow_ir.get("verification"))
        recovery = _coerce_mapping(workflow_metadata.get("recovery") or workflow_ir.get("recovery"))
        approval.setdefault("required", _coerce_bool(approval.get("required"), default=False))
        verification.setdefault("required", _coerce_bool(verification.get("required"), default=False))
        recovery.setdefault(
            "enabled",
            _coerce_bool(
                recovery.get("enabled"),
                default=str(recovery.get("kind") or "").strip().lower() in {"retry", "repair", "resume"},
            ),
        )
        return {"approval": approval, "verification": verification, "recovery": recovery}

    def _resolve_capability(
        self,
        *,
        invocation: Invocation,
        workflow_kind: str,
        workflow_projection,
        gate_contracts: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        required_policies: list[str] = []
        if _coerce_bool(gate_contracts["approval"].get("required"), default=False):
            required_policies.append("approval")
        if _coerce_bool(gate_contracts["verification"].get("required"), default=False):
            required_policies.append("verification")
        if _coerce_bool(gate_contracts["recovery"].get("enabled"), default=False):
            required_policies.append("recovery")
        matches = self._capability_resolver.resolve(
            invocation=invocation,
            workflow_kind=workflow_kind,
            required_policies=tuple(required_policies),
        )
        required_capability_ids: list[str] = []
        if workflow_projection is not None:
            required_capability_ids.extend(
                [str(item).strip() for item in workflow_projection.required_capability_ids if str(item).strip()]
            )
        route_capability_id = str(
            workflow_projection.route.capability_id
            if workflow_projection is not None and workflow_projection.route is not None
            else ""
        ).strip()
        if route_capability_id:
            required_capability_ids.append(route_capability_id)
        if required_capability_ids:
            allowed = set(required_capability_ids)
            matches = [item for item in matches if item.capability.capability_id in allowed]
        selected = matches[0] if matches else None
        return {
            "required": bool(required_policies or required_capability_ids),
            "required_policies": required_policies,
            "required_capability_ids": required_capability_ids,
            "matched": bool(selected is not None),
            "selected_binding": selected,
            "selected": self._binding_snapshot(selected),
            "matches": [self._binding_snapshot(item) for item in matches],
            "resolved_capability_ids": [item.capability.capability_id for item in matches],
        }

    def _resolve_step_binding(
        self,
        *,
        step: WorkflowStepSpec,
        workflow_projection,
        capability_resolution: Mapping[str, Any],
    ) -> dict[str, Any]:
        metadata = dict(step.metadata or {})
        runtime_binding = _coerce_mapping(metadata.get("runtime_binding"))
        requested_capability_ids: list[str] = []
        capability_id = str(metadata.get("capability_id") or runtime_binding.get("capability_id") or "").strip()
        if capability_id:
            requested_capability_ids.append(capability_id)
        requested_capability_ids.extend(_coerce_list(metadata.get("capability_ids")))
        requested_capability_ids.extend(_coerce_list(runtime_binding.get("capability_ids")))
        if self._step_requires_external_execution(step) and not requested_capability_ids and workflow_projection is not None:
            requested_capability_ids.extend(
                [str(item).strip() for item in workflow_projection.required_capability_ids if str(item).strip()]
            )
        selected_snapshot = dict(capability_resolution.get("selected") or {})
        selected_binding = capability_resolution.get("selected_binding")
        if requested_capability_ids:
            allowed = set(requested_capability_ids)
            if str(((selected_snapshot.get("capability") or {}).get("capability_id") or "")).strip() not in allowed:
                selected_snapshot = {}
                selected_binding = None
        return {
            "required": self._step_requires_external_execution(step) and bool(
                requested_capability_ids or capability_resolution.get("required")
            ),
            "matched": bool(selected_binding is not None),
            "selected_binding": selected_binding,
            "selected": selected_snapshot,
            "matches": list(capability_resolution.get("matches") or []),
            "requested_capability_ids": requested_capability_ids,
            "runtime_binding": runtime_binding,
            "runtime_binding_ref": str(
                runtime_binding.get("binding_ref")
                or metadata.get("runtime_binding_ref")
                or metadata.get("capability_package_ref")
                or ""
            ).strip(),
            "team_package_ref": str(metadata.get("team_package_ref") or runtime_binding.get("team_package_ref") or "").strip(),
        }

    @staticmethod
    def _binding_snapshot(binding: CapabilityBinding | None) -> dict[str, Any]:
        if binding is None:
            return {}
        capability = binding.capability
        return {
            "agent_id": binding.agent_id,
            "agent_spec_id": binding.agent_spec_id,
            "priority": binding.priority,
            "default_route_key": binding.default_route_key,
            "metadata": dict(binding.metadata or {}),
            "capability": {
                "capability_id": capability.capability_id,
                "name": capability.name,
                "supported_entrypoints": list(capability.supported_entrypoints),
                "supported_workflow_kinds": list(capability.supported_workflow_kinds),
                "required_policies": list(capability.required_policies),
                "expected_outputs": list(capability.expected_outputs),
                "metadata": dict(capability.metadata or {}),
            },
        }

    def _resolve_checkpoint_store(self, *, request) -> FileWorkflowCheckpointStore | None:
        if self._checkpoint_store is not None:
            return self._checkpoint_store
        checkpoint_path = str(
            request.metadata.get("workflow_checkpoint_path")
            or request.metadata.get("checkpoint_path")
            or ""
        ).strip()
        return FileWorkflowCheckpointStore(Path(checkpoint_path)) if checkpoint_path else None

    @staticmethod
    def _load_resume_checkpoint(
        *,
        request,
        runtime_state: Mapping[str, Any],
        checkpoint_store: FileWorkflowCheckpointStore | None,
    ) -> WorkflowCheckpoint | None:
        if checkpoint_store is None:
            return None
        checkpoint_id = str(
            runtime_state.get("checkpoint_id")
            or runtime_state.get("workflow_checkpoint_id")
            or request.metadata.get("checkpoint_id")
            or request.metadata.get("workflow_checkpoint_id")
            or ""
        ).strip()
        if checkpoint_id:
            return checkpoint_store.get(checkpoint_id)
        if _coerce_bool(runtime_state.get("resume"), default=False) or _coerce_bool(request.metadata.get("resume"), default=False):
            return checkpoint_store.latest()
        return None

    @staticmethod
    def _restore_projection(*, workflow_spec: WorkflowSpec, checkpoint: WorkflowCheckpoint | None) -> WorkflowRunProjection:
        if checkpoint is not None and isinstance(checkpoint.metadata.get("projection"), Mapping):
            projection = WorkflowRunProjection.from_dict(checkpoint.metadata.get("projection"))
            projection.spec = workflow_spec
            projection.cursor = WorkflowCursor.from_dict(checkpoint.cursor.to_dict())
            return projection
        return WorkflowRunProjection(
            spec=workflow_spec,
            cursor=WorkflowCursor(workflow_id=workflow_spec.workflow_id, current_step_id=workflow_spec.first_step_id(), status="pending"),
        )

    def _resolve_cursor(
        self,
        *,
        workflow_spec: WorkflowSpec,
        requested_step_id: str,
        runtime_state: Mapping[str, Any],
        checkpoint: WorkflowCheckpoint | None,
        existing_cursor: WorkflowCursor,
    ) -> WorkflowCursor:
        if checkpoint is not None:
            cursor = WorkflowCursor.from_dict(checkpoint.cursor.to_dict())
            cursor.workflow_id = workflow_spec.workflow_id
            resume_step_id = str(cursor.resume_from or cursor.current_step_id or "").strip()
            cursor.current_step_id = self._resume_target_step_id(workflow_spec, resume_step_id) if resume_step_id else workflow_spec.first_step_id()
            cursor.status = "running"
            return cursor
        cursor = WorkflowCursor.from_dict(existing_cursor.to_dict())
        cursor.workflow_id = workflow_spec.workflow_id
        cursor.current_step_id = str(
            runtime_state.get("resume_from") or requested_step_id or cursor.current_step_id or workflow_spec.first_step_id()
        ).strip()
        cursor.status = "running"
        cursor.resume_from = cursor.current_step_id
        return cursor

    def _decide_pre_step_gate(
        self,
        *,
        workflow_spec: WorkflowSpec,
        step: WorkflowStepSpec,
        gate_contracts: Mapping[str, Mapping[str, Any]],
        runtime_state: Mapping[str, Any],
    ) -> _StepOutcome | None:
        if not self._step_requires_external_execution(step):
            return None
        if step.requires_approval and not self._workflow_has_step_kind(workflow_spec, "approve"):
            approval_status = _normalize_gate_status(runtime_state.get("approval_status"))
            if approval_status not in {"approved", "skipped", "not_required", "completed"}:
                return _StepOutcome(
                    status="blocked",
                    summary=f"awaiting approval before step {step.step_id}",
                    transition="blocked",
                    metadata={"phase": "approval_gate"},
                    decision="await_approval",
                    resume_from=step.step_id,
                )
        verification_status = _normalize_gate_status(runtime_state.get("verification_status"))
        if (
            step.requires_verification
            and not self._workflow_has_step_kind(workflow_spec, "verify")
            and verification_status in {"failed", "rejected"}
            and _coerce_bool(gate_contracts["recovery"].get("enabled"), default=False)
        ):
            return _StepOutcome(
                status="pending",
                summary=f"verification failed; recovery is pending from step {step.step_id}",
                transition="pending",
                metadata={"phase": "recovery_pending"},
                decision="retry",
                resume_from=step.step_id,
                failure_class="acceptance_failed",
            )
        return None

    def _execute_external_step(
        self,
        *,
        context: ExecutionContext,
        step: WorkflowStepSpec,
        binding: CapabilityBinding | None,
        contract: Mapping[str, Any],
    ) -> _StepOutcome:
        if self._handler is None:
            return _StepOutcome(
                status=self._default_ready_status,
                summary=f"execution contract ready for step {step.step_id or 'unknown'}",
                transition="pending",
                metadata={"phase": "ready"},
                decision="ready",
                next_action=f"execute step {step.step_id}",
                resume_from=step.step_id,
            )
        handled = self._handler(context, binding=binding, contract=contract)
        normalized = self._normalize_handler_result(handled, step=step)
        normalized.metadata.setdefault("phase", "executed")
        return normalized

    def _execute_internal_step(
        self,
        *,
        step: WorkflowStepSpec,
        workflow_spec: WorkflowSpec,
        runtime_state: Mapping[str, Any],
        gate_contracts: Mapping[str, Mapping[str, Any]],
        latest_handoff: HandoffReceipt | None,
    ) -> _StepOutcome:
        if step.step_kind == "verify":
            verification_required = step.requires_verification or step.step_kind == "verify"
            verification_status = _normalize_gate_status(runtime_state.get("verification_status"))
            if not verification_required and not verification_status:
                return _StepOutcome(status="completed", summary=f"verification skipped for step {step.step_id}", metadata={"phase": "verified"}, decision="skipped")
            if verification_status in {"approved", "passed", "verified", "skipped", "not_required", "completed"}:
                return _StepOutcome(status="completed", summary=f"verification passed for step {step.step_id}", metadata={"phase": "verified"}, decision="verified")
            if verification_status in {"failed", "rejected"}:
                if self._select_edge_target(workflow_spec, step.step_id, "on_failure"):
                    return _StepOutcome(status="failed", summary=f"verification failed at step {step.step_id}", transition="failure", metadata={"phase": "verification_failed"}, decision="rejected", failure_class="acceptance_failed")
                if _coerce_bool(gate_contracts["recovery"].get("enabled"), default=False):
                    return _StepOutcome(status="pending", summary=f"verification failed; recovery is pending from step {step.step_id}", transition="pending", metadata={"phase": "recovery_pending"}, decision="retry", resume_from=step.step_id, failure_class="acceptance_failed")
                return _StepOutcome(status="failed", summary=f"verification failed at step {step.step_id}", transition="failure", metadata={"phase": "verification_failed"}, decision="rejected", failure_class="acceptance_failed")
            return _StepOutcome(status="pending", summary=f"awaiting verification for step {step.step_id}", transition="pending", metadata={"phase": "verification_gate"}, decision="await_verification", resume_from=step.step_id)
        if step.step_kind == "approve":
            approval_required = step.requires_approval or step.step_kind == "approve"
            approval_status = _normalize_gate_status(runtime_state.get("approval_status"))
            if not approval_required and not approval_status:
                return _StepOutcome(status="completed", summary=f"approval skipped for step {step.step_id}", metadata={"phase": "approval_skipped"}, decision="skipped")
            if approval_status in {"approved", "skipped", "not_required", "completed"}:
                return _StepOutcome(status="completed", summary=f"approval granted for step {step.step_id}", metadata={"phase": "approved"}, decision="approved")
            if approval_status in {"failed", "rejected"} and self._select_edge_target(workflow_spec, step.step_id, "on_failure"):
                return _StepOutcome(status="failed", summary=f"approval rejected for step {step.step_id}", transition="failure", metadata={"phase": "approval_rejected"}, decision="rejected", failure_class="policy_blocked")
            return _StepOutcome(status="blocked", summary=f"awaiting approval before step {step.step_id}", transition="blocked", metadata={"phase": "approval_gate"}, decision="await_approval", resume_from=step.step_id, failure_class="policy_blocked" if approval_status in {"failed", "rejected"} else "")
        if step.step_kind == "join":
            summary = f"joined inputs for step {step.step_id}"
            if latest_handoff is not None and latest_handoff.source_step_id:
                summary = f"joined handoff from {latest_handoff.source_step_id} into {step.step_id}"
            return _StepOutcome(status="completed", summary=summary, metadata={"phase": "joined"}, decision="joined", handoff_payload={"joined_from": latest_handoff.source_step_id if latest_handoff is not None else ""})
        if step.step_kind == "finalize":
            return _StepOutcome(status="completed", summary=f"workflow finalized at step {step.step_id}", metadata={"phase": "completed"}, decision="finalized")
        return _StepOutcome(status="completed", summary=f"advanced internal step {step.step_id}", metadata={"phase": "advanced"}, decision="proceed")

    @staticmethod
    def _normalize_handler_result(result: ExecutionReceipt | Mapping[str, Any] | None, *, step: WorkflowStepSpec) -> _StepOutcome:
        if isinstance(result, ExecutionReceipt):
            return _StepOutcome(status=result.status, summary=result.summary or f"step {step.step_id} executed", metadata=dict(result.metadata or {}), output_bundle=result.output_bundle, model_input=result.model_input)
        payload = _coerce_mapping(result)
        return _StepOutcome(
            status=str(payload.get("status") or "completed").strip() or "completed",
            summary=str(payload.get("summary") or f"step {step.step_id} executed").strip(),
            transition=str(payload.get("transition") or "").strip(),
            metadata=_coerce_mapping(payload.get("metadata")),
            output_bundle=payload.get("output_bundle") if isinstance(payload.get("output_bundle"), OutputBundle) else None,
            model_input=payload.get("model_input"),
            evidence=_coerce_list(payload.get("evidence")),
            artifacts=_coerce_list(payload.get("artifacts")),
            handoff_payload=_coerce_mapping(payload.get("handoff_payload")),
            decision=str(payload.get("decision") or "").strip(),
            next_action=str(payload.get("next_action") or "").strip(),
            resume_from=str(payload.get("resume_from") or "").strip(),
            failure_class=str(payload.get("failure_class") or "").strip(),
        )

    @staticmethod
    def _step_requires_external_execution(step: WorkflowStepSpec) -> bool:
        metadata = dict(step.metadata or {})
        return _coerce_bool(metadata.get("external_execution"), default=False) or step.step_kind == "dispatch"

    @classmethod
    def _side_effect_mode(cls, step: WorkflowStepSpec) -> str:
        return "external" if cls._step_requires_external_execution(step) else "internal"

    @staticmethod
    def _workflow_has_step_kind(workflow_spec: WorkflowSpec, step_kind: str) -> bool:
        return any(step.step_kind == step_kind for step in workflow_spec.steps)

    def _select_transition_target(self, *, workflow_spec: WorkflowSpec, step: WorkflowStepSpec, transition: str) -> tuple[str, str]:
        if step.step_kind == "finalize":
            return "", ""
        if transition == "failure":
            target = self._select_edge_target(workflow_spec, step.step_id, "on_failure")
            return target, ("on_failure" if target else "")
        target = self._select_edge_target(workflow_spec, step.step_id, "on_success")
        if target:
            return target, "on_success"
        target = self._select_edge_target(workflow_spec, step.step_id, "next")
        return (target, "next") if target else ("", "")

    @staticmethod
    def _select_edge_target(workflow_spec: WorkflowSpec, step_id: str, edge_kind: str) -> str:
        edges = workflow_spec.outgoing_edges(step_id, edge_kind=edge_kind)
        return str(edges[0].target_step_id).strip() if edges else ""

    def _resume_target_step_id(self, workflow_spec: WorkflowSpec, resume_from: str) -> str:
        return self._select_edge_target(workflow_spec, resume_from, "resume_from") or resume_from or workflow_spec.first_step_id()

    @staticmethod
    def _build_step_receipt(
        *,
        workflow_spec: WorkflowSpec,
        step: WorkflowStepSpec,
        outcome: _StepOutcome,
        current_step_mode: str,
        binding_resolution: Mapping[str, Any],
    ) -> StepReceipt:
        return StepReceipt(
            step_id=step.step_id,
            workflow_id=workflow_spec.workflow_id,
            worker_name=str(((binding_resolution.get("selected") or {}).get("agent_id") or step.worker_hint or "")).strip(),
            process_role=step.process_role,
            step_kind=step.step_kind,
            status=outcome.status,
            summary=outcome.summary,
            evidence=list(outcome.evidence),
            artifacts=list(outcome.artifacts),
            failure_class=outcome.failure_class,
            next_action=outcome.next_action,
            handoff_payload=dict(outcome.handoff_payload or {}),
            metadata={**dict(outcome.metadata or {}), "side_effect_boundary": current_step_mode, "binding": dict(binding_resolution.get("selected") or {}), "runtime_binding_ref": str(binding_resolution.get("runtime_binding_ref") or "").strip()},
        )

    @staticmethod
    def _build_handoff_receipt(
        *,
        workflow_spec: WorkflowSpec,
        step: WorkflowStepSpec,
        outcome: _StepOutcome,
        next_step_id: str,
        edge_kind: str,
    ) -> HandoffReceipt:
        next_step = workflow_spec.step_by_id(next_step_id)
        return HandoffReceipt(
            workflow_id=workflow_spec.workflow_id,
            source_step_id=step.step_id,
            target_step_id=next_step_id,
            producer=step.process_role,
            consumer=next_step.process_role if next_step is not None else "",
            handoff_kind=edge_kind or "step_output",
            status="completed",
            summary=f"handoff from {step.step_id} to {next_step_id}",
            payload=dict(outcome.handoff_payload or {}),
            handoff_ready=True,
            next_action=f"advance to {next_step_id}",
            metadata={"transition": outcome.transition},
        )

    @staticmethod
    def _build_decision_receipt(
        *,
        workflow_spec: WorkflowSpec,
        step: WorkflowStepSpec,
        outcome: _StepOutcome,
        next_step_id: str,
        edge_kind: str,
    ) -> DecisionReceipt:
        decision = str(outcome.decision or "").strip()
        if not decision:
            decision = "wait" if outcome.transition in {"blocked", "pending"} else ("fail" if outcome.transition == "failure" and not next_step_id else ("complete" if not next_step_id else "proceed"))
        next_action = str(outcome.next_action or "").strip()
        if not next_action:
            next_action = f"advance via {edge_kind or 'next'} to {next_step_id}" if next_step_id else ("close workflow" if outcome.transition not in {"blocked", "pending"} else f"resume from {outcome.resume_from or step.step_id}")
        return DecisionReceipt(
            workflow_id=workflow_spec.workflow_id,
            step_id=step.step_id,
            producer=step.process_role,
            status=outcome.status if outcome.status in {"blocked", "pending"} else "completed",
            summary=outcome.summary,
            decision=decision,
            decision_reason=edge_kind or outcome.transition or "state_transition",
            retryable=decision in {"retry", "wait"},
            next_action=next_action,
            resume_from=outcome.resume_from or next_step_id or step.step_id,
            artifacts=list(outcome.artifacts),
            metadata=dict(outcome.metadata or {}),
        )

    def _build_semantic_contract(
        self,
        *,
        request,
        workflow_spec: WorkflowSpec,
        projection: WorkflowRunProjection,
        cursor: WorkflowCursor,
        gate_contracts: Mapping[str, Mapping[str, Any]],
        capability_resolution: Mapping[str, Any],
        step_binding_resolution: Mapping[str, Any],
        current_step: WorkflowStepSpec,
        current_step_mode: str,
    ) -> dict[str, Any]:
        return {
            "workflow": {
                "workflow_id": workflow_spec.workflow_id,
                "workflow_kind": str(workflow_spec.metadata.get("workflow_kind") or "").strip(),
                "step_count": len(workflow_spec.steps),
                "current_step_id": current_step.step_id,
                "current_step_kind": current_step.step_kind,
                "next_step_id": self._select_edge_target(workflow_spec, current_step.step_id, "on_success") or self._select_edge_target(workflow_spec, current_step.step_id, "next"),
                "cursor": cursor.to_dict(),
                "spec": workflow_spec.to_dict(),
            },
            "step": current_step.to_dict(),
            "step_binding_resolution": {key: value for key, value in dict(step_binding_resolution or {}).items() if key != "selected_binding"},
            "gates": gate_contracts,
            "capability_resolution": {key: value for key, value in dict(capability_resolution or {}).items() if key != "selected_binding"},
            "projection": projection.to_dict(),
            "side_effect_boundary": {"current_step_mode": current_step_mode, "external_step_kinds": ["dispatch"], "internal_step_kinds": ["verify", "approve", "join", "finalize", "prepare", "plan", "promote", "recover"]},
            "observability": {"route_id": request.route.route_id if request.route is not None else "", "route_key": request.route.route_key if request.route is not None else "", "target_agent_id": request.route.target_agent_id if request.route is not None else "", "agent_id": request.agent_spec.agent_id if request.agent_spec is not None else ""},
        }

    def _save_checkpoint(
        self,
        *,
        checkpoint_store: FileWorkflowCheckpointStore | None,
        request,
        workflow_spec: WorkflowSpec,
        cursor: WorkflowCursor,
        projection: WorkflowRunProjection,
        step_receipt: StepReceipt | None,
        handoff_receipt: HandoffReceipt | None,
        decision_receipt: DecisionReceipt | None,
        extra_metadata: Mapping[str, Any],
    ) -> WorkflowCheckpoint:
        checkpoint = WorkflowCheckpoint(
            instance_id=str(request.metadata.get("instance_id") or "").strip(),
            session_id=request.invocation.session_id,
            run_id=request.invocation.invocation_id,
            workflow_id=workflow_spec.workflow_id,
            cursor=WorkflowCursor.from_dict(cursor.to_dict()),
            step_receipt=step_receipt,
            handoff_receipt=handoff_receipt,
            decision_receipt=decision_receipt,
            metadata={"projection": projection.to_dict(), **dict(extra_metadata or {})},
        )
        if checkpoint_store is not None:
            checkpoint_store.save(checkpoint)
            checkpoint_store.write_current(checkpoint)
        return checkpoint

    def _final_receipt(
        self,
        *,
        context: ExecutionContext,
        workflow_spec: WorkflowSpec,
        projection: WorkflowRunProjection,
        gate_contracts: Mapping[str, Mapping[str, Any]],
        capability_resolution: Mapping[str, Any],
        step_binding_resolution: Mapping[str, Any],
        current_step: WorkflowStepSpec | None,
        current_step_mode: str,
        checkpoint: WorkflowCheckpoint | None,
        status: str,
        summary: str,
        phase: str,
        resumed_from_checkpoint: bool,
        failure_class: str,
        output_bundle: OutputBundle | None,
        model_input: Any,
        extra_metadata: Mapping[str, Any],
        checkpoint_hint: str,
        prefer_checkpoint_hint: bool,
    ) -> ExecutionReceipt:
        metadata = self._build_receipt_metadata(
            request=context.request,
            workflow_spec=workflow_spec,
            projection=projection,
            gate_contracts=gate_contracts,
            capability_resolution=capability_resolution,
            step_binding_resolution=step_binding_resolution,
            current_step=current_step,
            current_step_mode=current_step_mode,
            checkpoint=checkpoint,
            execution_phase=phase,
            resumed_from_checkpoint=resumed_from_checkpoint,
            failure_class=failure_class,
            checkpoint_hint=checkpoint_hint,
            prefer_checkpoint_hint=prefer_checkpoint_hint,
        )
        metadata.update(dict(extra_metadata or {}))
        return self._build_receipt(
            context,
            status=status,
            summary=summary,
            metadata=metadata,
            output_bundle=output_bundle or self._bundle(summary, phase=phase, workflow_spec=workflow_spec, cursor=projection.cursor),
            model_input=model_input,
        )

    def _invalid_plan_receipt(
        self,
        *,
        context: ExecutionContext,
        workflow_spec: WorkflowSpec,
        projection: WorkflowRunProjection,
        cursor: WorkflowCursor,
        gate_contracts: Mapping[str, Mapping[str, Any]],
        capability_resolution: Mapping[str, Any],
        checkpoint_store: FileWorkflowCheckpointStore | None,
        resumed_from_checkpoint: bool,
        checkpoint_hint: str,
    ) -> ExecutionReceipt:
        checkpoint = self._save_checkpoint(
            checkpoint_store=checkpoint_store,
            request=context.request,
            workflow_spec=workflow_spec,
            cursor=cursor,
            projection=projection,
            step_receipt=None,
            handoff_receipt=None,
            decision_receipt=None,
            extra_metadata={"failure_class": "invalid_plan", "projection": projection.to_dict()},
        )
        return self._final_receipt(
            context=context,
            workflow_spec=workflow_spec,
            projection=projection,
            gate_contracts=gate_contracts,
            capability_resolution=capability_resolution,
            step_binding_resolution={},
            current_step=None,
            current_step_mode="internal",
            checkpoint=checkpoint,
            status="failed",
            summary=f"workflow step not found: {cursor.current_step_id or 'unknown'}",
            phase="invalid_plan",
            resumed_from_checkpoint=resumed_from_checkpoint,
            failure_class="invalid_plan",
            output_bundle=None,
            model_input=None,
            extra_metadata={},
            checkpoint_hint=checkpoint_hint,
            prefer_checkpoint_hint=checkpoint_store is None and bool(checkpoint_hint),
        )

    def _build_receipt_metadata(
        self,
        *,
        request,
        workflow_spec: WorkflowSpec,
        projection: WorkflowRunProjection,
        gate_contracts: Mapping[str, Mapping[str, Any]],
        capability_resolution: Mapping[str, Any],
        step_binding_resolution: Mapping[str, Any],
        current_step: WorkflowStepSpec | None,
        current_step_mode: str,
        checkpoint: WorkflowCheckpoint | None,
        execution_phase: str,
        resumed_from_checkpoint: bool,
        failure_class: str = "",
        checkpoint_hint: str = "",
        prefer_checkpoint_hint: bool = False,
    ) -> dict[str, Any]:
        completed_step_ids = [receipt.step_id for receipt in projection.step_receipts if receipt.status == "completed" and receipt.step_id]
        resolved_checkpoint_id = str(checkpoint_hint or "").strip() if prefer_checkpoint_hint else str(checkpoint.checkpoint_id if checkpoint is not None else "").strip()
        metadata = {
            "workflow": {
                "workflow_id": workflow_spec.workflow_id,
                "workflow_kind": str(workflow_spec.metadata.get("workflow_kind") or "").strip(),
                "step_count": len(workflow_spec.steps),
                "current_step_id": projection.cursor.current_step_id,
                "current_step_kind": current_step.step_kind if current_step is not None else "",
                "next_step_id": self._select_edge_target(workflow_spec, projection.cursor.current_step_id, "on_success") or self._select_edge_target(workflow_spec, projection.cursor.current_step_id, "next"),
                "completed_step_ids": completed_step_ids,
                "resumed_from_checkpoint": resumed_from_checkpoint,
                "spec": workflow_spec.to_dict(),
            },
            "workflow_projection": projection.to_dict(),
            "step": current_step.to_dict() if current_step is not None else {},
            "checkpoint": {"checkpoint_id": resolved_checkpoint_id, "resume_from": str(projection.cursor.resume_from or projection.cursor.current_step_id or "").strip(), "replay_from": "", "resume_token": "", "resumable": bool(projection.cursor.current_step_id)},
            "gates": dict(gate_contracts or {}),
            "capability_resolution": {key: value for key, value in dict(capability_resolution or {}).items() if key != "selected_binding"},
            "step_binding_resolution": {key: value for key, value in dict(step_binding_resolution or {}).items() if key != "selected_binding"},
            "side_effect_boundary": {"current_step_mode": current_step_mode, "external_step_kinds": ["dispatch"], "internal_step_kinds": ["verify", "approve", "join", "finalize", "prepare", "plan", "promote", "recover"]},
            "observability": {"route_id": request.route.route_id if request.route is not None else "", "route_key": request.route.route_key if request.route is not None else "", "target_agent_id": request.route.target_agent_id if request.route is not None else "", "agent_id": request.agent_spec.agent_id if request.agent_spec is not None else "", "has_prompt_context": False, "has_memory_context": False},
            "execution_phase": execution_phase,
        }
        if failure_class:
            metadata["failure_class"] = failure_class
        return metadata

    @staticmethod
    def _build_receipt(
        context: ExecutionContext,
        *,
        status: str,
        summary: str,
        metadata: Mapping[str, Any],
        output_bundle: OutputBundle | None = None,
        model_input=None,
    ) -> ExecutionReceipt:
        request = context.request
        return ExecutionReceipt(
            invocation_id=request.invocation.invocation_id,
            workflow_id=request.workflow.workflow_id if request.workflow is not None else "",
            route=request.route,
            projection=request.workflow,
            agent_id=request.agent_spec.agent_id if request.agent_spec is not None else "",
            status=status,
            summary=summary,
            model_input=model_input,
            output_bundle=output_bundle,
            metadata=dict(metadata or {}),
        )

    @staticmethod
    def _bundle(summary: str, *, phase: str, workflow_spec: WorkflowSpec, cursor: WorkflowCursor) -> OutputBundle:
        return OutputBundle(
            status="ready",
            summary=summary,
            text_blocks=[TextBlock(text=summary)],
            metadata={"phase": phase, "workflow_id": workflow_spec.workflow_id, "current_step_id": cursor.current_step_id},
        )
