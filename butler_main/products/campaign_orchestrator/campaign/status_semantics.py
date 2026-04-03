from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_PROGRESSION_CHECK_IDS = {
    "ssh_reachable",
    "target_path_exists",
    "research_anchor_confirmed",
    "literature_scope_confirmed",
    "output_contract_confirmed",
}
_GENERIC_BLOCKER_IDS = {"pending_correctness_checks"}


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict") and callable(value.to_dict):
        payload = value.to_dict()
        if isinstance(payload, Mapping):
            return dict(payload)
    return {}


def _text_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def split_correctness_checks(
    pending_checks: Any,
    resolved_checks: Any = None,
    waived_checks: Any = None,
) -> tuple[list[str], list[str], list[str], list[str], list[str], list[str]]:
    pending = _text_list(pending_checks)
    resolved = _text_list(resolved_checks)
    waived = _text_list(waived_checks)
    done = set(resolved) | set(waived)
    effective_pending = [item for item in pending if item not in done]
    operational_pending = [item for item in effective_pending if item in _PROGRESSION_CHECK_IDS]
    closure_pending = [item for item in effective_pending if item not in _PROGRESSION_CHECK_IDS]
    return effective_pending, resolved, waived, operational_pending, closure_pending, list(done)


def build_campaign_semantics(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    source = _mapping(payload)
    metadata = _mapping(source.get("metadata"))
    if str(metadata.get("campaign_engine") or "").strip().lower() == "agent_turn":
        task_summary = _mapping(metadata.get("task_summary"))
        progress = _mapping(task_summary.get("progress"))
        closure = _mapping(task_summary.get("closure"))
        risk = _mapping(task_summary.get("risk"))
        status = str(source.get("status") or progress.get("status") or "").strip().lower()
        latest_verdict = _mapping(metadata.get("latest_verdict") or closure.get("latest_verdict"))
        latest_delivery_refs = _text_list(
            metadata.get("latest_delivery_refs") or _mapping(task_summary.get("output")).get("latest_delivery_refs")
        )
        pending_checks, resolved_checks, waived_checks, operational_pending, closure_pending, _ = split_correctness_checks(
            metadata.get("pending_correctness_checks"),
            metadata.get("resolved_correctness_checks"),
            metadata.get("waived_correctness_checks"),
        )
        if status == "completed":
            execution_state = "terminal"
            closure_state = "accepted"
        elif status == "failed":
            execution_state = "blocked"
            closure_state = "failed"
        elif status in {"paused", "cancelled"}:
            execution_state = "paused"
            closure_state = "cancelled"
        elif latest_delivery_refs:
            execution_state = "running"
            closure_state = "stage_delivered"
        elif status == "draft":
            execution_state = "ready"
            closure_state = "open"
        else:
            execution_state = "running"
            closure_state = "open"
        latest_acceptance_decision = str(
            latest_verdict.get("decision") or _mapping(metadata.get("evaluation_contract")).get("latest_acceptance_decision") or ""
        ).strip().lower()
        latest_acceptance_blockers = _text_list(metadata.get("latest_acceptance_blockers"))
        if not latest_acceptance_blockers and pending_checks:
            latest_acceptance_blockers = ["pending_correctness_checks"]
        latest_summary = str(progress.get("latest_summary") or metadata.get("latest_summary") or "").strip()
        next_action = str(task_summary.get("next_action") or metadata.get("latest_next_action") or "").strip()
        compatibility_reason = latest_summary if status not in {"completed"} else ""
        return {
            "execution_state": execution_state,
            "closure_state": closure_state,
            "progress_reason": latest_summary or f"campaign is {status or 'active'}",
            "closure_reason": str(closure.get("final_summary") or "").strip(),
            "not_done_reason": compatibility_reason,
            "operational_checks_pending": operational_pending,
            "closure_checks_pending": closure_pending,
            "pending_checks": pending_checks,
            "resolved_checks": resolved_checks,
            "waived_checks": waived_checks,
            "latest_stage_summary": latest_summary,
            "stage_artifact_refs": latest_delivery_refs,
            "acceptance_requirements_remaining": list(operational_pending) + [
                item for item in closure_pending if item not in operational_pending
            ],
            "operator_next_action": next_action,
            "latest_acceptance_decision": latest_acceptance_decision,
            "latest_acceptance_blockers": latest_acceptance_blockers,
            "has_stage_artifacts": bool(latest_delivery_refs),
            "risk_level": str(risk.get("risk_level") or "").strip(),
        }
    verdict_history = [
        _mapping(item)
        for item in source.get("verdict_history") or []
        if isinstance(item, Mapping) or hasattr(item, "to_dict")
    ]
    latest_verdict = _mapping(source.get("latest_verdict")) or (verdict_history[-1] if verdict_history else {})
    latest_implement_artifact = _mapping(metadata.get("latest_implement_artifact"))
    artifacts = [
        _mapping(item)
        for item in source.get("artifacts") or []
        if isinstance(item, Mapping) or hasattr(item, "to_dict")
    ]
    status = str(source.get("status") or "").strip().lower()
    current_phase = str(source.get("current_phase") or "").strip().lower()
    next_phase = str(source.get("next_phase") or "").strip().lower()
    latest_acceptance_decision = str(
        source.get("latest_acceptance_decision")
        or metadata.get("latest_acceptance_decision")
        or latest_verdict.get("decision")
        or ""
    ).strip().lower()
    latest_blockers = _text_list(metadata.get("latest_acceptance_blockers"))
    pending_checks, resolved_checks, waived_checks, operational_pending, closure_pending, _ = split_correctness_checks(
        metadata.get("pending_correctness_checks"),
        metadata.get("resolved_correctness_checks"),
        metadata.get("waived_correctness_checks"),
    )
    deliverable_refs = _text_list(latest_implement_artifact.get("deliverable_refs"))
    if not deliverable_refs:
        deliverable_refs = _text_list(metadata.get("deliverable_refs"))
    artifact_refs = _text_list(
        [
            artifact.get("deliverable_ref")
            or _mapping(artifact.get("metadata")).get("deliverable_ref")
            or artifact.get("ref")
            or ""
            for artifact in artifacts
        ]
    )
    stage_artifact_refs = deliverable_refs or artifact_refs[-8:]

    acceptance_requirements_remaining = list(operational_pending)
    acceptance_requirements_remaining.extend(item for item in closure_pending if item not in acceptance_requirements_remaining)
    for blocker in latest_blockers:
        if blocker in _GENERIC_BLOCKER_IDS:
            continue
        if blocker not in acceptance_requirements_remaining:
            acceptance_requirements_remaining.append(blocker)

    latest_rationale = str(latest_verdict.get("rationale") or "").strip()
    closure_reason = str(metadata.get("closure_reason") or metadata.get("not_done_reason") or "").strip()
    if not closure_reason and acceptance_requirements_remaining:
        closure_reason = ", ".join(acceptance_requirements_remaining)
    if not closure_reason and latest_acceptance_decision and latest_acceptance_decision != "converge":
        closure_reason = latest_rationale

    if status == "completed" or latest_acceptance_decision == "converge":
        execution_state = "terminal"
    elif status == "stopped":
        execution_state = "paused"
    elif status == "failed":
        execution_state = "blocked"
    elif operational_pending:
        execution_state = "waiting_feedback"
    elif status == "draft":
        execution_state = "ready"
    else:
        execution_state = "running"

    if status == "failed":
        closure_state = "failed"
    elif status == "stopped":
        closure_state = "cancelled"
    elif latest_acceptance_decision == "converge" and not acceptance_requirements_remaining:
        closure_state = "accepted"
    elif stage_artifact_refs or artifacts:
        closure_state = "acceptance_blocked" if (acceptance_requirements_remaining or (latest_acceptance_decision and latest_acceptance_decision != "converge")) else "stage_delivered"
    else:
        closure_state = "open"

    if execution_state == "terminal":
        progress_reason = "campaign converged and no further execution is required"
    elif execution_state == "paused":
        progress_reason = "campaign was paused or stopped by operator control"
    elif execution_state == "blocked":
        progress_reason = "campaign entered a failed state and requires recovery"
    elif execution_state == "waiting_feedback":
        progress_reason = (
            "waiting for operator or environment confirmation: "
            + ", ".join(operational_pending)
        )
    elif latest_acceptance_decision == "recover" and latest_rationale:
        progress_reason = latest_rationale
    elif next_phase:
        progress_reason = f"campaign is progressing through {current_phase or next_phase} toward {next_phase}"
    elif current_phase:
        progress_reason = f"campaign is progressing through {current_phase}"
    else:
        progress_reason = "campaign is progressing"

    if closure_state == "accepted" and not closure_reason:
        closure_reason = "final acceptance converged"
    elif closure_state == "cancelled" and not closure_reason:
        closure_reason = "campaign was stopped before final acceptance"
    elif closure_state == "failed" and not closure_reason:
        closure_reason = "campaign failed before final acceptance"

    latest_stage_summary = str(
        latest_implement_artifact.get("summary")
        or latest_implement_artifact.get("execution_summary")
        or latest_implement_artifact.get("next_action")
        or ""
    ).strip()
    if not latest_stage_summary:
        if stage_artifact_refs:
            latest_stage_summary = (
                f"{current_phase or 'current stage'} produced {len(stage_artifact_refs)} tracked artifact(s)"
            )
        elif artifacts:
            latest_stage_summary = (
                f"{current_phase or 'current stage'} has {len(artifacts)} recorded artifact(s)"
            )
        elif current_phase:
            latest_stage_summary = f"{current_phase} is active"
        else:
            latest_stage_summary = "campaign state captured"

    governance_contract = _mapping(metadata.get("governance_contract"))
    approval_state = str(governance_contract.get("approval_state") or "").strip().lower()
    if execution_state == "waiting_feedback" and operational_pending:
        operator_next_action = "confirm or resolve: " + ", ".join(operational_pending)
    elif approval_state == "requested":
        operator_next_action = "resolve pending approval request"
    elif closure_state == "acceptance_blocked" and acceptance_requirements_remaining:
        operator_next_action = "close acceptance requirements: " + ", ".join(acceptance_requirements_remaining)
    elif closure_state == "accepted":
        operator_next_action = "publish or hand off the accepted deliverables"
    elif execution_state == "paused":
        operator_next_action = "resume or close the paused campaign"
    elif next_phase:
        operator_next_action = f"advance {next_phase}"
    elif current_phase:
        operator_next_action = f"continue {current_phase}"
    else:
        operator_next_action = "review the current campaign snapshot"

    compatibility_reason = str(metadata.get("not_done_reason") or "").strip() or closure_reason

    return {
        "execution_state": execution_state,
        "closure_state": closure_state,
        "progress_reason": progress_reason,
        "closure_reason": closure_reason,
        "not_done_reason": compatibility_reason,
        "operational_checks_pending": operational_pending,
        "closure_checks_pending": closure_pending,
        "pending_checks": pending_checks,
        "resolved_checks": resolved_checks,
        "waived_checks": waived_checks,
        "latest_stage_summary": latest_stage_summary,
        "stage_artifact_refs": stage_artifact_refs,
        "acceptance_requirements_remaining": acceptance_requirements_remaining,
        "operator_next_action": operator_next_action,
        "latest_acceptance_decision": latest_acceptance_decision,
        "latest_acceptance_blockers": latest_blockers,
        "has_stage_artifacts": bool(stage_artifact_refs or artifacts),
    }


__all__ = [
    "build_campaign_semantics",
    "split_correctness_checks",
]
