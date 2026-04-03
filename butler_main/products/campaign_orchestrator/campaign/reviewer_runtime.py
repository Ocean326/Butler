from __future__ import annotations

from typing import Any, Mapping

from .models import CampaignInstance, CampaignPhase, EvaluationVerdict


class CampaignReviewerRuntime:
    """Independent reviewer-owned verdict source for Campaign iterations."""

    def evaluate(
        self,
        *,
        instance: CampaignInstance,
        implement_artifact_id: str,
    ) -> EvaluationVerdict:
        budget = instance.working_contract.iteration_budget.max_iterations
        blockers = self._acceptance_blockers(instance)
        decision = self._decision_for_iteration(instance, budget=budget, blockers=blockers)
        score = min(0.45 + (0.15 * instance.current_iteration), 0.95)
        if blockers:
            score = min(score, 0.7)
        next_goal = instance.working_contract.working_goal
        if decision != "converge":
            if blockers:
                next_goal = f"{instance.top_level_goal} / close acceptance blockers for iteration {instance.current_iteration + 1}"
            else:
                next_goal = f"{instance.top_level_goal} / tighten scope for iteration {instance.current_iteration + 1}"
        rationale_by_decision = {
            "converge": "Independent reviewer accepted the current evidence as sufficient.",
            "continue": "Independent reviewer requests one more bounded iteration before convergence.",
            "recover": "Independent reviewer requires a bounded recovery pass before another implementation attempt.",
        }
        rationale = rationale_by_decision[decision]
        if blockers:
            rationale = f"{rationale} blockers={', '.join(blockers)}"
        return EvaluationVerdict(
            campaign_id=instance.campaign_id,
            iteration=instance.current_iteration,
            phase=CampaignPhase.EVALUATE.value,
            decision=decision,
            score=score,
            rationale=rationale,
            reviewer_role_id="campaign_reviewer",
            evidence_artifact_ids=[str(implement_artifact_id or "").strip()],
            next_iteration_goal=next_goal,
            contract_patch={
                "working_goal": next_goal,
                "goal_immutable": instance.top_level_goal,
                "hard_constraints_immutable": list(instance.hard_constraints),
                "reviewer_role_id": "campaign_reviewer",
                "acceptance_blockers": blockers,
            },
            metadata={"evaluator_kind": "deterministic_reviewer", "acceptance_blockers": blockers},
        )

    def _decision_for_iteration(self, instance: CampaignInstance, *, budget: int, blockers: list[str]) -> str:
        if blockers and self._strict_acceptance_required(instance):
            return "recover" if instance.current_iteration >= budget else "continue"
        sequence = self._decision_sequence(instance)
        if sequence:
            index = max(0, instance.current_iteration - 1)
            if index < len(sequence):
                return sequence[index]
        decision = "converge" if instance.current_iteration >= budget else "continue"
        if instance.current_iteration == max(1, budget - 1):
            decision = "recover"
        return decision

    def _acceptance_blockers(self, instance: CampaignInstance) -> list[str]:
        if not self._strict_acceptance_required(instance):
            return []
        metadata = dict(instance.metadata or {})
        latest_artifact = dict(metadata.get("latest_implement_artifact") or {})
        pending_checks = [
            str(item).strip()
            for item in metadata.get("pending_correctness_checks") or []
            if str(item).strip()
        ]
        resolved_checks = {
            str(item).strip()
            for item in metadata.get("resolved_correctness_checks") or []
            if str(item).strip()
        }
        waived_checks = {
            str(item).strip()
            for item in metadata.get("waived_correctness_checks") or []
            if str(item).strip()
        }
        checks_remaining = [
            item for item in pending_checks if item not in resolved_checks and item not in waived_checks
        ]
        deliverable_refs = [
            str(item).strip()
            for item in latest_artifact.get("deliverable_refs") or []
            if str(item).strip()
        ]
        blockers: list[str] = []
        if latest_artifact and bool(latest_artifact.get("placeholder", True)):
            blockers.append("placeholder_implement_artifact")
        if not deliverable_refs:
            blockers.append("missing_deliverable_refs")
        if checks_remaining:
            blockers.append("pending_correctness_checks")
        return blockers

    @staticmethod
    def _strict_acceptance_required(instance: CampaignInstance) -> bool:
        metadata = dict(instance.metadata or {})
        if bool(metadata.get("strict_acceptance_required")):
            return True
        spec_payload = metadata.get("spec")
        if isinstance(spec_payload, Mapping):
            return bool(dict(spec_payload.get("metadata") or {}).get("strict_acceptance_required"))
        return False

    def _decision_sequence(self, instance: CampaignInstance) -> list[str]:
        metadata = dict(instance.metadata or {})
        spec_payload = metadata.get("spec")
        spec_metadata = {}
        if isinstance(spec_payload, Mapping):
            spec_metadata = dict(spec_payload.get("metadata") or {})
        return _normalized_decisions(
            metadata.get("reviewer_decision_sequence")
            or spec_metadata.get("reviewer_decision_sequence")
        )


def _normalized_decisions(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        decision = str(item or "").strip().lower()
        if decision in {"continue", "recover", "converge"}:
            result.append(decision)
    return result


__all__ = ["CampaignReviewerRuntime"]
