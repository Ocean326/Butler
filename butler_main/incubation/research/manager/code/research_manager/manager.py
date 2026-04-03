from __future__ import annotations

from dataclasses import dataclass, field, replace

from butler_main.agents_os.runtime import AcceptanceReceipt

from .contracts import (
    RESEARCH_UNITS,
    ResearchInvocation,
    ResearchResult,
    ResearchUnitDispatch,
    ResearchUnitHandler,
    ResearchUnitSpec,
)
from .services.scenario_instance_store import FileResearchScenarioInstanceStore, ResearchScenarioInstance
from .services.unit_registry import build_default_unit_registry


@dataclass(slots=True)
class ResearchManager:
    manager_id: str = "research_manager"
    unit_registry: dict[str, ResearchUnitHandler] = field(default_factory=build_default_unit_registry)
    scenario_instance_store: FileResearchScenarioInstanceStore = field(default_factory=FileResearchScenarioInstanceStore)

    def invoke(self, invocation: ResearchInvocation) -> ResearchResult:
        unit = self._resolve_unit(invocation)
        if unit is None:
            return self._blocked_result(
                invocation,
                summary="No compatible research unit was resolved for this invocation.",
                next_action="set unit_id explicitly or use a default-compatible entrypoint",
                failure_class="context_missing",
            )

        scenario_instance = self.scenario_instance_store.bind(invocation, unit)
        effective_invocation = self._with_scenario_instance(invocation, scenario_instance)
        dispatch = self._dispatch_unit(effective_invocation, unit)
        dispatch_payload = dict(dispatch.payload)
        if scenario_instance is not None:
            scenario_instance = self.scenario_instance_store.apply_dispatch(
                scenario_instance,
                effective_invocation,
                dispatch_payload,
                summary=dispatch.summary,
            )
            dispatch_payload["scenario_instance"] = scenario_instance.to_dict()
        acceptance = AcceptanceReceipt(
            goal_achieved=False,
            summary=dispatch.summary,
            evidence=[
                f"manager_id={self.manager_id}",
                f"entrypoint={effective_invocation.entrypoint}",
                f"unit_id={unit.unit_id}",
                f"group={unit.group}",
                *( [f"scenario_instance_id={scenario_instance.scenario_instance_id}"] if scenario_instance is not None else [] ),
                *dispatch.evidence,
            ],
            artifacts=list(dispatch.artifacts),
            uncertainties=list(dispatch.uncertainties),
            next_action=dispatch.next_action or f"dispatch research unit: {unit.unit_id}",
            failure_class="",
        )
        return ResearchResult(
            status="ready",
            entrypoint=effective_invocation.entrypoint,
            unit_id=unit.unit_id,
            summary=dispatch.summary,
            acceptance=acceptance,
            route={
                "manager_id": self.manager_id,
                "entrypoint": effective_invocation.entrypoint,
                "unit_group": unit.group,
                "unit_description": unit.description,
                "unit_root": unit.unit_root,
                "handler_name": unit.handler_name,
                **({"scenario_instance_id": scenario_instance.scenario_instance_id} if scenario_instance is not None else {}),
            },
            payload={
                "goal": effective_invocation.goal,
                "task_id": effective_invocation.task_id,
                "session_id": effective_invocation.session_id,
                "workspace": effective_invocation.workspace,
                "metadata": dict(effective_invocation.metadata),
                "dispatch": dispatch_payload,
            },
        )

    def _resolve_unit(self, invocation: ResearchInvocation) -> ResearchUnitSpec | None:
        if invocation.unit_id:
            return RESEARCH_UNITS.get(invocation.unit_id)
        for spec in RESEARCH_UNITS.values():
            if invocation.entrypoint in spec.default_entrypoints:
                return spec
        return None

    def _dispatch_unit(self, invocation: ResearchInvocation, unit: ResearchUnitSpec) -> ResearchUnitDispatch:
        handler = self.unit_registry.get(unit.unit_id)
        if handler is None:
            if invocation.goal:
                summary = f"{unit.unit_id} accepted via {invocation.entrypoint}: {invocation.goal}"
            else:
                summary = f"{unit.unit_id} accepted via {invocation.entrypoint}"
            return ResearchUnitDispatch(
                summary=summary,
                evidence=[
                    "handler=missing",
                    f"unit_root={unit.unit_root}",
                ],
                uncertainties=[
                    "unit handler is not registered",
                ],
                next_action=f"register unit handler: {unit.unit_id}",
                payload={
                    "unit_group": unit.group,
                    "unit_root": unit.unit_root,
                },
            )
        return handler(invocation, unit)

    def _with_scenario_instance(
        self,
        invocation: ResearchInvocation,
        scenario_instance: ResearchScenarioInstance | None,
    ) -> ResearchInvocation:
        if scenario_instance is None:
            return invocation
        metadata = dict(invocation.metadata or {})
        payload = dict(invocation.payload or {})
        metadata.setdefault("scenario_instance_id", scenario_instance.scenario_instance_id)
        if scenario_instance.workflow_cursor and "workflow_cursor" not in metadata and "workflow_cursor" not in payload:
            metadata["workflow_cursor"] = dict(scenario_instance.workflow_cursor)
        return replace(invocation, metadata=metadata, payload=payload)

    def _blocked_result(
        self,
        invocation: ResearchInvocation,
        *,
        summary: str,
        next_action: str,
        failure_class: str,
    ) -> ResearchResult:
        acceptance = AcceptanceReceipt(
            goal_achieved=False,
            summary=summary,
            evidence=[
                f"manager_id={self.manager_id}",
                f"entrypoint={invocation.entrypoint}",
            ],
            artifacts=[],
            uncertainties=[
                "unit routing was not resolved",
            ],
            next_action=next_action,
            failure_class=failure_class,
        )
        return ResearchResult(
            status="blocked",
            entrypoint=invocation.entrypoint,
            unit_id=invocation.unit_id,
            summary=summary,
            acceptance=acceptance,
            route={
                "manager_id": self.manager_id,
                "entrypoint": invocation.entrypoint,
            },
            payload={
                "goal": invocation.goal,
                "task_id": invocation.task_id,
                "session_id": invocation.session_id,
                "workspace": invocation.workspace,
                "metadata": dict(invocation.metadata),
            },
        )
