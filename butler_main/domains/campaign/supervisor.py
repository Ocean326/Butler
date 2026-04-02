from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import CampaignInstance, CampaignSpec, EvaluationVerdict, WorkingContract
from .phase_runtime import CampaignPhaseOutcome, CampaignPhaseRuntime, merge_phase_metadata
from .reviewer_runtime import CampaignReviewerRuntime


@dataclass(slots=True)
class CampaignResumeOutcome:
    implement: CampaignPhaseOutcome
    iterate: CampaignPhaseOutcome
    verdict: EvaluationVerdict
    revised_contract: WorkingContract | None = None
    runtime_metadata: dict[str, Any] = field(default_factory=dict)


class CampaignSupervisorRuntime:
    """Explicit outer-loop supervisor for Discover -> Implement -> Evaluate -> Iterate."""

    def __init__(
        self,
        *,
        phase_runtime: CampaignPhaseRuntime | None = None,
        reviewer_runtime: CampaignReviewerRuntime | None = None,
    ) -> None:
        self._phase_runtime = phase_runtime or CampaignPhaseRuntime()
        self._reviewer_runtime = reviewer_runtime or CampaignReviewerRuntime()

    def bootstrap_campaign(
        self,
        *,
        spec: CampaignSpec,
        contract: WorkingContract,
        mission_id: str,
        supervisor_session_id: str,
    ) -> CampaignPhaseOutcome:
        return self._phase_runtime.run_discover(
            spec=spec,
            contract=contract,
            mission_id=mission_id,
            supervisor_session_id=supervisor_session_id,
        )

    def run_implement_phase(self, *, instance: CampaignInstance) -> CampaignPhaseOutcome:
        return self._phase_runtime.run_implement(instance=instance)

    def review_iteration(
        self,
        *,
        instance: CampaignInstance,
        implement_artifact_id: str,
    ) -> EvaluationVerdict:
        return self._reviewer_runtime.evaluate(
            instance=instance,
            implement_artifact_id=implement_artifact_id,
        )

    def run_iterate_phase(
        self,
        *,
        instance: CampaignInstance,
        verdict: EvaluationVerdict,
    ) -> CampaignResumeOutcome:
        revised_contract: WorkingContract | None = None
        if verdict.decision != "converge":
            revised_contract = instance.working_contract.rewrite_from_evaluation(verdict)
        iterate = self._phase_runtime.run_iterate(
            iteration=instance.current_iteration,
            verdict=verdict,
            contract_before=instance.working_contract,
            contract_after=revised_contract,
        )
        runtime_metadata = merge_phase_metadata({"phase_path": ["evaluate"]}, iterate.metadata)
        return CampaignResumeOutcome(
            implement=CampaignPhaseOutcome(
                phase=iterate.phase,
                next_phase=iterate.next_phase,
                status=iterate.status,
            ),
            iterate=iterate,
            verdict=verdict,
            revised_contract=revised_contract,
            runtime_metadata=runtime_metadata,
        )

    def run_iteration(self, *, instance: CampaignInstance, implement_artifact_id: str) -> CampaignResumeOutcome:
        implement = self._phase_runtime.run_implement(
            instance=instance,
        )
        verdict = self._reviewer_runtime.evaluate(
            instance=instance,
            implement_artifact_id=implement_artifact_id,
        )
        revised_contract: WorkingContract | None = None
        if verdict.decision != "converge":
            revised_contract = instance.working_contract.rewrite_from_evaluation(verdict)
        iterate = self._phase_runtime.run_iterate(
            iteration=instance.current_iteration,
            verdict=verdict,
            contract_before=instance.working_contract,
            contract_after=revised_contract,
        )
        runtime_metadata = merge_phase_metadata(
            implement.metadata,
            {"phase_path": ["evaluate"]},
            iterate.metadata,
        )
        return CampaignResumeOutcome(
            implement=implement,
            iterate=iterate,
            verdict=verdict,
            revised_contract=revised_contract,
            runtime_metadata=runtime_metadata,
        )


__all__ = [
    "CampaignResumeOutcome",
    "CampaignSupervisorRuntime",
]
