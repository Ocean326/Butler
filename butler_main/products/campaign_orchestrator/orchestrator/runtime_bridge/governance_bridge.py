from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from butler_main.runtime_os.process_runtime import RuntimeVerdict

from ..event_store import FileLedgerEventStore
from ..judge_adapter import JUDGE_DECISIONS, JudgeVerdict, OrchestratorJudgeAdapter
from ..mission_store import FileMissionStore
from ..models import Branch, LedgerEvent, Mission, MissionNode, normalize_branch_status, normalize_mission_status, normalize_node_status
from ..policy import OrchestratorPolicy
from ..workflow_ir import WorkflowIR
from .workflow_session_bridge import OrchestratorWorkflowSessionBridge


@dataclass(slots=True, frozen=True)
class BranchGovernanceOutcome:
    judge_decision: str = ""
    writeback_status: str = "pending"
    terminal: bool = False


@dataclass(slots=True, frozen=True)
class ApprovalResolutionOutcome:
    decision: str
    judge_decision: str = ""


class OrchestratorGovernanceBridge:
    """Keep approval, verification, and recovery flow out of the control-plane service."""

    def __init__(
        self,
        *,
        event_store: FileLedgerEventStore,
        mission_store: FileMissionStore,
        judge: OrchestratorJudgeAdapter,
        policy: OrchestratorPolicy,
        workflow_session_bridge: OrchestratorWorkflowSessionBridge,
        now_factory: Callable[[], str],
    ) -> None:
        self._event_store = event_store
        self._mission_store = mission_store
        self._judge = judge
        self._policy = policy
        self._workflow_session_bridge = workflow_session_bridge
        self._now_factory = now_factory

    def handle_branch_completion(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        ok: bool,
        result_ref: str,
        result_payload: dict[str, Any] | None,
        runtime_verdict: RuntimeVerdict | None = None,
    ) -> BranchGovernanceOutcome:
        verdict = runtime_verdict or RuntimeVerdict.from_legacy(
            ok=ok,
            result_ref=result_ref,
            result_payload=result_payload,
        )
        judge_decision = ""
        if verdict.status == "awaiting_approval":
            self._enter_approval_gate(
                mission=mission,
                node=node,
                branch=branch,
                result_ref=result_ref,
                result_payload=result_payload,
            )
        elif verdict.status in {"repair_scheduled", "resumable"}:
            self._enter_recovery_action(
                mission=mission,
                node=node,
                branch=branch,
                source="runtime_verdict",
                reason=verdict.status,
                result_ref=result_ref,
                result_payload=result_payload,
            )
        elif verdict.status == "awaiting_verification":
            judge_decision = self._run_judge_for_branch(
                mission=mission,
                node=node,
                branch=branch,
                result_ref=result_ref,
                result_payload=result_payload,
            )
        elif ok:
            if self._approval_gate_required(branch):
                self._enter_approval_gate(
                    mission=mission,
                    node=node,
                    branch=branch,
                    result_ref=result_ref,
                    result_payload=result_payload,
                )
            else:
                judge_decision = self._apply_success_path(
                    mission=mission,
                    node=node,
                    branch=branch,
                    result_ref=result_ref,
                    result_payload=result_payload,
                )
        else:
            self._enter_recovery_action(
                mission=mission,
                node=node,
                branch=branch,
                source="branch_failed",
                reason="branch_execution_failed",
                result_ref=result_ref,
                result_payload=result_payload,
            )
        writeback_status = self._derive_writeback_status(
            mission=mission,
            node=node,
            fallback_status=verdict.status,
        )
        return BranchGovernanceOutcome(
            judge_decision=judge_decision,
            writeback_status=writeback_status,
            terminal=writeback_status in {"completed", "failed", "cancelled", "stale"},
        )

    def resolve_node_approval(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        decision: str,
        note: str = "",
    ) -> ApprovalResolutionOutcome:
        normalized = str(decision or "").strip().lower()
        if normalized not in {"approve", "reject"}:
            raise ValueError(f"unsupported approval decision: {decision}")
        result_ref = str(node.metadata.get("approval_result_ref") or branch.result_ref or "").strip()
        stored_payload = node.metadata.get("approval_result_payload")
        if isinstance(stored_payload, dict):
            result_payload = dict(stored_payload)
        else:
            result_payload = dict(branch.metadata.get("result_payload") or {})
        self._clear_approval_state(node)
        judge_decision = ""
        mission.status = "running"
        if normalized == "approve":
            judge_decision = self._apply_success_path(
                mission=mission,
                node=node,
                branch=branch,
                result_ref=result_ref,
                result_payload=result_payload,
            )
        else:
            self._enter_recovery_action(
                mission=mission,
                node=node,
                branch=branch,
                source="approval_rejected",
                reason="approval_rejected",
                result_ref=result_ref,
                result_payload=result_payload,
            )
        self._event_store.append(
            LedgerEvent(
                mission_id=mission.mission_id,
                node_id=node.node_id,
                branch_id=branch.branch_id,
                event_type="approval_resolved",
                payload={
                    "decision": normalized,
                    "note": str(note or "").strip(),
                    "judge_decision": judge_decision,
                },
            )
        )
        return ApprovalResolutionOutcome(decision=normalized, judge_decision=judge_decision)

    def _approval_gate_required(self, branch: Branch) -> bool:
        return bool(self._approval_policy(branch).get("required"))

    def _verification_gate_required(self, branch: Branch) -> bool:
        return bool(self._verification_policy(branch).get("required"))

    def _enter_approval_gate(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        result_ref: str,
        result_payload: dict[str, Any] | None,
    ) -> None:
        node.status = "blocked"
        mission.status = "awaiting_decision"
        node.metadata["approval_pending"] = True
        node.metadata["approval_branch_id"] = branch.branch_id
        node.metadata["approval_result_ref"] = str(result_ref or "").strip()
        node.metadata["approval_result_payload"] = dict(result_payload or {})
        node.metadata["approval_requested_at"] = self._now_text()
        self._workflow_session_bridge.update_branch_workflow_session(
            mission=mission,
            node=node,
            branch=branch,
            status="awaiting_approval",
            result_ok=True,
            result_ref=result_ref,
            result_payload=result_payload,
            governance={
                "phase": "approval_gate",
                "gate": "approval",
            },
        )
        self._event_store.append(
            LedgerEvent(
                mission_id=mission.mission_id,
                node_id=node.node_id,
                branch_id=branch.branch_id,
                event_type="approval_requested",
                payload={
                    "result_ref": str(result_ref or "").strip(),
                    "summary": str(
                        (result_payload or {}).get("summary")
                        or (result_payload or {}).get("output_bundle_summary")
                        or ""
                    ).strip(),
                    "approval_policy": self._approval_policy(branch),
                },
            )
        )

    @staticmethod
    def _clear_approval_state(node: MissionNode) -> None:
        for key in (
            "approval_pending",
            "approval_branch_id",
            "approval_result_ref",
            "approval_result_payload",
            "approval_requested_at",
        ):
            node.metadata.pop(key, None)

    def _apply_success_path(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        result_ref: str,
        result_payload: dict[str, Any] | None,
    ) -> str:
        if self._verification_gate_required(branch):
            return self._run_judge_for_branch(
                mission=mission,
                node=node,
                branch=branch,
                result_ref=result_ref,
                result_payload=result_payload,
            )
        node.status = "done"
        self._clear_recovery_state(node)
        verification_policy = self._verification_policy(branch)
        self._workflow_session_bridge.finalize_branch_workflow_session(
            mission=mission,
            node=node,
            branch=branch,
            ok=True,
            result_ref=result_ref,
            result_payload=result_payload,
        )
        self._event_store.append(
            LedgerEvent(
                mission_id=mission.mission_id,
                node_id=node.node_id,
                branch_id=branch.branch_id,
                event_type="verification_skipped",
                payload={
                    "result_ref": str(result_ref or "").strip(),
                    "reason": "workflow_ir_verification_disabled",
                    "verification_policy": verification_policy,
                },
            )
        )
        return ""

    def _run_judge_for_branch(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        result_ref: str,
        result_payload: dict[str, Any] | None,
    ) -> str:
        artifacts = [{"result_ref": str(result_ref or "").strip(), "result_payload": dict(result_payload or {})}]
        node.status = "awaiting_judge"
        self._workflow_session_bridge.update_branch_workflow_session(
            mission=mission,
            node=node,
            branch=branch,
            status="verifying",
            result_ok=True,
            result_ref=result_ref,
            result_payload=result_payload,
            governance={
                "phase": "verification",
                "gate": "verification",
            },
        )
        mission.updated_at = self._now_text()
        self._mission_store.save(mission)
        verdict = self._judge.evaluate_node(mission.mission_id, node.node_id, artifacts)
        judge_decision = self._normalize_judge_decision(verdict.decision)
        self._apply_judge_verdict(
            mission=mission,
            node=node,
            branch=branch,
            verdict=verdict,
            result_ref=result_ref,
            result_payload=result_payload,
        )
        self._event_store.append(
            LedgerEvent(
                mission_id=mission.mission_id,
                node_id=node.node_id,
                branch_id=branch.branch_id,
                event_type="judge_verdict",
                payload={
                    "decision": judge_decision,
                    "reason": verdict.reason,
                    "metadata": dict(verdict.metadata or {}),
                    "verification_policy": self._verification_policy(branch),
                },
            )
        )
        return judge_decision

    def _apply_judge_verdict(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        verdict: JudgeVerdict,
        result_ref: str,
        result_payload: dict[str, Any] | None,
    ) -> None:
        decision = self._normalize_judge_decision(verdict.decision)
        if decision == "accept":
            node.status = "done"
            self._clear_recovery_state(node)
            self._workflow_session_bridge.finalize_branch_workflow_session(
                mission=mission,
                node=node,
                branch=branch,
                ok=True,
                result_ref=result_ref,
                result_payload=result_payload,
            )
            return
        if decision == "repair":
            self._enter_recovery_action(
                mission=mission,
                node=node,
                branch=branch,
                source="judge_repair",
                reason=str(verdict.reason or "").strip() or "judge_requested_repair",
                result_ref=result_ref,
                result_payload=result_payload,
            )
            return
        if decision == "reject":
            node.status = "failed"
            self._workflow_session_bridge.finalize_branch_workflow_session(
                mission=mission,
                node=node,
                branch=branch,
                ok=False,
                result_ref=result_ref,
                result_payload=result_payload,
            )
            return
        if decision in ("escalate", "expand"):
            node.status = "blocked"
            mission.status = "awaiting_decision"
            self._workflow_session_bridge.update_branch_workflow_session(
                mission=mission,
                node=node,
                branch=branch,
                status="awaiting_decision",
                result_ok=True,
                result_ref=result_ref,
                result_payload=result_payload,
                governance={
                    "phase": "awaiting_decision",
                    "gate": "verification",
                    "decision": decision,
                },
            )
            return
        node.status = "done"
        self._clear_recovery_state(node)
        self._workflow_session_bridge.finalize_branch_workflow_session(
            mission=mission,
            node=node,
            branch=branch,
            ok=True,
            result_ref=result_ref,
            result_payload=result_payload,
        )

    @staticmethod
    def _clear_recovery_state(node: MissionNode) -> None:
        for key in (
            "repair_attempts",
            "recovery_retry_cap",
            "recovery_last_source",
            "recovery_last_reason",
            "recovery_action",
            "recovery_resume_from",
        ):
            node.metadata.pop(key, None)

    def _enter_recovery_action(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        source: str,
        reason: str,
        result_ref: str,
        result_payload: dict[str, Any] | None,
    ) -> None:
        normalized_source = str(source or "").strip() or "recovery"
        normalized_reason = str(reason or "").strip() or "retry_requested"
        recovery_policy = self._recovery_policy(branch)
        action = str(recovery_policy.get("action") or "retry").strip()
        resume_from = self._resolve_recovery_resume_from(
            branch=branch,
            node=node,
            recovery_policy=recovery_policy,
        )
        if not bool(recovery_policy.get("enabled")):
            node.status = "failed"
            policy_reason = "workflow_ir_recovery_disabled"
            if not bool(recovery_policy.get("supported", True)):
                policy_reason = "workflow_ir_recovery_unsupported"
            self._workflow_session_bridge.finalize_branch_workflow_session(
                mission=mission,
                node=node,
                branch=branch,
                ok=False,
                result_ref=result_ref,
                result_payload=result_payload,
            )
            self._event_store.append(
                LedgerEvent(
                    mission_id=mission.mission_id,
                    node_id=node.node_id,
                    branch_id=branch.branch_id,
                    event_type="recovery_skipped",
                    payload={
                        "source": normalized_source,
                        "reason": normalized_reason,
                        "policy": policy_reason,
                        "recovery_policy": recovery_policy,
                        "result_ref": str(result_ref or "").strip(),
                        "resume_from": resume_from,
                    },
                )
            )
            return
        attempts = int(node.metadata.get("repair_attempts", 0) or 0) + 1
        cap = int(recovery_policy.get("max_attempts") or 0)
        node.metadata["repair_attempts"] = attempts
        node.metadata["recovery_retry_cap"] = cap
        node.metadata["recovery_last_source"] = normalized_source
        node.metadata["recovery_last_reason"] = normalized_reason
        node.metadata["recovery_action"] = action
        node.metadata["recovery_resume_from"] = resume_from
        if attempts > cap:
            node.status = "failed"
            self._workflow_session_bridge.finalize_branch_workflow_session(
                mission=mission,
                node=node,
                branch=branch,
                ok=False,
                result_ref=result_ref,
                result_payload=result_payload,
            )
            self._event_store.append(
                LedgerEvent(
                    mission_id=mission.mission_id,
                    node_id=node.node_id,
                    branch_id=branch.branch_id,
                    event_type="repair_exhausted",
                    payload={
                        "repair_attempts": attempts,
                        "cap": cap,
                        "action": recovery_policy.get("action"),
                        "source": normalized_source,
                        "reason": normalized_reason,
                        "recovery_policy": recovery_policy,
                        "result_ref": str(result_ref or "").strip(),
                        "resume_from": resume_from,
                    },
                )
            )
            return
        node.status = "repairing"
        self._workflow_session_bridge.update_branch_workflow_session(
            mission=mission,
            node=node,
            branch=branch,
            status="repairing",
            active_step=resume_from or None,
            result_ok=normalize_branch_status(branch.status) == "succeeded",
            result_ref=result_ref,
            result_payload=result_payload,
            governance={
                "phase": "recovery",
                "action": action,
                "source": normalized_source,
                "reason": normalized_reason,
                "resume_from": resume_from,
            },
        )
        self._event_store.append(
            LedgerEvent(
                mission_id=mission.mission_id,
                node_id=node.node_id,
                branch_id=branch.branch_id,
                event_type="recovery_scheduled",
                payload={
                    "action": action,
                    "repair_attempts": attempts,
                    "cap": cap,
                    "source": normalized_source,
                    "reason": normalized_reason,
                    "recovery_policy": recovery_policy,
                    "result_ref": str(result_ref or "").strip(),
                    "summary": str((result_payload or {}).get("summary") or "").strip(),
                    "resume_from": resume_from,
                },
            )
        )

    def _approval_policy(self, branch: Branch) -> dict[str, Any]:
        workflow_ir = self._workflow_session_bridge.workflow_ir_from_branch(branch) or WorkflowIR()
        return workflow_ir.approval_policy()

    def _verification_policy(self, branch: Branch) -> dict[str, Any]:
        workflow_ir = self._workflow_session_bridge.workflow_ir_from_branch(branch) or WorkflowIR()
        return workflow_ir.verification_policy()

    def _recovery_policy(self, branch: Branch) -> dict[str, Any]:
        workflow_ir = self._workflow_session_bridge.workflow_ir_from_branch(branch) or WorkflowIR()
        return workflow_ir.recovery_policy(
            default_max_attempts=max(0, int(self._policy.max_repair_attempts_per_node or 0))
        )

    def _resolve_recovery_resume_from(
        self,
        *,
        branch: Branch,
        node: MissionNode,
        recovery_policy: dict[str, Any],
    ) -> str:
        for source in (recovery_policy, node.metadata, branch.metadata, branch.input_payload):
            for key in ("resume_from", "step_id", "cursor", "active_step"):
                value = str(source.get(key) or "").strip()
                if value:
                    return value
        session = self._workflow_session_bridge.load_workflow_session(
            self._workflow_session_bridge.session_id_from_branch(branch)
        )
        if session is not None and str(session.active_step or "").strip():
            return str(session.active_step or "").strip()
        workflow_ir = self._workflow_session_bridge.workflow_ir_from_branch(branch)
        return self._workflow_session_bridge.workflow_template_first_step_id(workflow_ir)

    def _normalize_judge_decision(self, raw: str) -> str:
        decision = str(raw or "").strip().lower()
        return decision if decision in JUDGE_DECISIONS else "accept"

    def _derive_writeback_status(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        fallback_status: str,
    ) -> str:
        if bool(node.metadata.get("approval_pending")):
            return "awaiting_approval"
        node_status = normalize_node_status(node.status)
        mission_status = normalize_mission_status(mission.status)
        if node_status == "awaiting_judge":
            return "awaiting_verification"
        if node_status == "repairing":
            return "repair_scheduled"
        if node_status == "done":
            return "completed"
        if node_status == "failed":
            return "failed"
        if node_status == "blocked" and mission_status == "awaiting_decision":
            return "awaiting_decision"
        return str(fallback_status or "pending").strip() or "pending"

    def _now_text(self) -> str:
        return str(self._now_factory() or "").strip()
