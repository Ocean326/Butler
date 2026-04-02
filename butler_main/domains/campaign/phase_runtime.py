from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .models import CampaignInstance, CampaignPhase, CampaignSpec, EvaluationVerdict, WorkingContract


@dataclass(slots=True)
class CampaignArtifactRecord:
    phase: CampaignPhase
    iteration: int
    kind: str
    label: str
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CampaignEventRecord:
    event_type: str
    phase: CampaignPhase
    iteration: int
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CampaignPhaseOutcome:
    phase: CampaignPhase
    next_phase: CampaignPhase
    status: str = "active"
    artifacts: list[CampaignArtifactRecord] = field(default_factory=list)
    events: list[CampaignEventRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class CampaignPhaseRuntime:
    """Deterministic phase runtime that emits explicit phase outcomes."""

    def run_discover(
        self,
        *,
        spec: CampaignSpec,
        contract: WorkingContract,
        mission_id: str,
        supervisor_session_id: str,
    ) -> CampaignPhaseOutcome:
        spec_metadata = dict(spec.metadata or {})
        resolved_checks = [str(item).strip() for item in spec_metadata.get("resolved_correctness_checks") or [] if str(item).strip()]
        waived_checks = [str(item).strip() for item in spec_metadata.get("waived_correctness_checks") or [] if str(item).strip()]
        pending_checks = [
            str(item).strip()
            for item in spec_metadata.get("pending_correctness_checks") or []
            if str(item).strip() and str(item).strip() not in {*resolved_checks, *waived_checks}
        ]
        discover_payload = {
            "top_level_goal": spec.top_level_goal,
            "materials": list(spec.materials),
            "hard_constraints": list(spec.hard_constraints),
            "working_contract_version": contract.version,
            "next_phase": CampaignPhase.IMPLEMENT.value,
            "startup_mode": str(spec_metadata.get("startup_mode") or "").strip(),
            "planning_ready": True,
            "checks_remaining": pending_checks,
            "checks_resolved": resolved_checks,
            "checks_waived": waived_checks,
            "bundle_root": str(spec_metadata.get("bundle_root") or "").strip(),
        }
        artifacts = [
            CampaignArtifactRecord(
                phase=CampaignPhase.DISCOVER,
                iteration=0,
                kind="discover_report",
                label="Initial discover report",
                payload=discover_payload,
                metadata={"phase_runtime": "discover"},
            ),
            CampaignArtifactRecord(
                phase=CampaignPhase.DISCOVER,
                iteration=0,
                kind="working_contract",
                label="Working contract v1",
                payload=contract.to_dict(),
                metadata={
                    "contract_id": contract.contract_id,
                    "version": contract.version,
                    "phase_runtime": "discover",
                },
            ),
        ]
        events = [
            CampaignEventRecord(
                event_type="campaign_created",
                phase=CampaignPhase.DISCOVER,
                iteration=0,
                payload={
                    "mission_id": mission_id,
                    "supervisor_session_id": supervisor_session_id,
                    "working_contract_id": contract.contract_id,
                },
            ),
            CampaignEventRecord(
                event_type="discover_completed",
                phase=CampaignPhase.DISCOVER,
                iteration=0,
                payload={
                    "working_contract_version": contract.version,
                    "next_phase": CampaignPhase.IMPLEMENT.value,
                },
            ),
        ]
        return CampaignPhaseOutcome(
            phase=CampaignPhase.DISCOVER,
            next_phase=CampaignPhase.IMPLEMENT,
            status="active",
            artifacts=artifacts,
            events=events,
            metadata={
                "runtime_kind": "campaign_phase_runtime",
                "phase_path": ["discover"],
            },
        )

    def run_implement(self, *, instance: CampaignInstance) -> CampaignPhaseOutcome:
        iteration = instance.current_iteration
        contract = instance.working_contract
        metadata = dict(instance.metadata or {})
        resolved_checks = [str(item).strip() for item in metadata.get("resolved_correctness_checks") or [] if str(item).strip()]
        waived_checks = [str(item).strip() for item in metadata.get("waived_correctness_checks") or [] if str(item).strip()]
        pending_checks = [
            str(item).strip()
            for item in metadata.get("pending_correctness_checks") or []
            if str(item).strip() and str(item).strip() not in {*resolved_checks, *waived_checks}
        ]
        artifacts = [
            CampaignArtifactRecord(
                phase=CampaignPhase.IMPLEMENT,
                iteration=iteration,
                kind="implementation_report",
                label=f"Implementation report iteration {iteration}",
                payload={
                    "working_goal": contract.working_goal,
                    "acceptance": list(contract.working_acceptance),
                    "budget": contract.iteration_budget.to_dict(),
                    "execution_summary": f"deterministic implementation pass {iteration}",
                    "summary": f"deterministic implementation pass {iteration}",
                    "placeholder": True,
                    "deliverable_refs": [],
                    "checks_resolved": resolved_checks,
                    "checks_remaining": pending_checks,
                    "next_action": "resolve remaining correctness checks before acceptance" if pending_checks else "review current implementation evidence",
                },
                metadata={
                    "phase_runtime": "implement",
                    "contract_version": contract.version,
                    "placeholder": True,
                },
            )
        ]
        events = [
            CampaignEventRecord(
                event_type="implement_completed",
                phase=CampaignPhase.IMPLEMENT,
                iteration=iteration,
                payload={"working_contract_version": contract.version},
            )
        ]
        return CampaignPhaseOutcome(
            phase=CampaignPhase.IMPLEMENT,
            next_phase=CampaignPhase.EVALUATE,
            status="active",
            artifacts=artifacts,
            events=events,
            metadata={
                "runtime_kind": "campaign_phase_runtime",
                "phase_path": ["discover", "implement"],
            },
        )

    def run_iterate(
        self,
        *,
        iteration: int,
        verdict: EvaluationVerdict,
        contract_before: WorkingContract,
        contract_after: WorkingContract | None,
    ) -> CampaignPhaseOutcome:
        artifacts: list[CampaignArtifactRecord] = []
        events: list[CampaignEventRecord] = []
        status = "completed" if verdict.decision == "converge" else "active"
        next_phase = CampaignPhase.ITERATE if verdict.decision == "converge" else CampaignPhase.IMPLEMENT
        if contract_after is not None:
            artifacts.append(
                CampaignArtifactRecord(
                    phase=CampaignPhase.ITERATE,
                    iteration=iteration,
                    kind="working_contract",
                    label=f"Working contract v{contract_after.version}",
                    payload=contract_after.to_dict(),
                    metadata={
                        "contract_id": contract_after.contract_id,
                        "version": contract_after.version,
                        "replaced_contract_version": contract_before.version,
                        "phase_runtime": "iterate",
                    },
                )
            )
            events.append(
                CampaignEventRecord(
                    event_type="working_contract_rewritten",
                    phase=CampaignPhase.ITERATE,
                    iteration=iteration,
                    payload={
                        "contract_id": contract_after.contract_id,
                        "version": contract_after.version,
                        "decision": verdict.decision,
                    },
                )
            )
            if verdict.decision == "recover":
                events.append(
                    CampaignEventRecord(
                        event_type="campaign_recovery_scheduled",
                        phase=CampaignPhase.ITERATE,
                        iteration=iteration,
                        payload={
                            "next_phase": next_phase.value,
                            "reason": verdict.rationale,
                        },
                    )
                )
        else:
            events.append(
                CampaignEventRecord(
                    event_type="campaign_converged",
                    phase=CampaignPhase.ITERATE,
                    iteration=iteration,
                    payload={
                        "verdict_id": verdict.verdict_id,
                        "score": verdict.score,
                    },
                )
            )
        return CampaignPhaseOutcome(
            phase=CampaignPhase.ITERATE,
            next_phase=next_phase,
            status=status,
            artifacts=artifacts,
            events=events,
            metadata={
                "runtime_kind": "campaign_phase_runtime",
                "phase_path": ["discover", "implement", "evaluate", "iterate"],
            },
        )


def merge_phase_metadata(*payloads: Mapping[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    phase_path: list[str] = []
    for payload in payloads:
        if not isinstance(payload, Mapping):
            continue
        for key, value in payload.items():
            if key == "phase_path" and isinstance(value, list):
                for item in value:
                    text = str(item or "").strip()
                    if text and text not in phase_path:
                        phase_path.append(text)
                continue
            merged[key] = value
    if phase_path:
        merged["phase_path"] = phase_path
    return merged


__all__ = [
    "CampaignArtifactRecord",
    "CampaignEventRecord",
    "CampaignPhaseOutcome",
    "CampaignPhaseRuntime",
    "merge_phase_metadata",
]
