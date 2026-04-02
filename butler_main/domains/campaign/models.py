from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4


CAMPAIGN_STATUSES: tuple[str, ...] = (
    "draft",
    "active",
    "running",
    "waiting",
    "paused",
    "completed",
    "stopped",
    "failed",
    "cancelled",
)

VERDICT_DECISIONS: tuple[str, ...] = (
    "continue",
    "converge",
    "recover",
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_string_list(values: list[Any] | tuple[Any, ...] | None) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for item in values:
        value = _normalize_text(item)
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def normalize_composition_mode(value: Any, *, default: str = "") -> str:
    normalized = _normalize_text(value).lower()
    if normalized in {"template", "composition"}:
        return normalized
    return default


def _template_contract_payload(
    *,
    template_origin: str,
    composition_mode: str,
    skeleton_changed: bool,
    composition_plan: Mapping[str, Any] | None,
    created_from: str,
    negotiation_session_id: str,
) -> dict[str, Any] | None:
    if not any(
        [
            template_origin,
            composition_mode,
            skeleton_changed,
            composition_plan,
            created_from,
            negotiation_session_id,
        ]
    ):
        return None
    payload = {
        "template_origin": template_origin,
        "composition_mode": composition_mode,
        "skeleton_changed": bool(skeleton_changed),
        "composition_plan": dict(composition_plan or {}),
    }
    if created_from:
        payload["created_from"] = created_from
    if negotiation_session_id:
        payload["negotiation_session_id"] = negotiation_session_id
    return payload


class CampaignPhase(str, Enum):
    DISCOVER = "discover"
    IMPLEMENT = "implement"
    EVALUATE = "evaluate"
    ITERATE = "iterate"

    @classmethod
    def normalize(
        cls,
        value: str | "CampaignPhase" | None,
        *,
        default: "CampaignPhase" | None = None,
    ) -> "CampaignPhase":
        if isinstance(value, CampaignPhase):
            return value
        normalized = _normalize_text(value).lower()
        for phase in cls:
            if phase.value == normalized:
                return phase
        return default or cls.DISCOVER


def normalize_campaign_status(value: str, *, default: str = "draft") -> str:
    normalized = _normalize_text(value).lower()
    if not normalized:
        return default
    aliases = {
        "active": "running",
        "stopped": "paused",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in CAMPAIGN_STATUSES else default


def normalize_verdict_decision(value: str, *, default: str = "continue") -> str:
    normalized = _normalize_text(value).lower()
    if not normalized:
        return default
    return normalized if normalized in VERDICT_DECISIONS else default


@dataclass(slots=True)
class IterationBudget:
    max_iterations: int = 3
    max_minutes: int = 120
    max_file_changes: int = 12

    def __post_init__(self) -> None:
        self.max_iterations = max(1, int(self.max_iterations or 1))
        self.max_minutes = max(1, int(self.max_minutes or 1))
        self.max_file_changes = max(1, int(self.max_file_changes or 1))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "IterationBudget":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class CampaignSpec:
    top_level_goal: str = ""
    materials: list[str] = field(default_factory=list)
    hard_constraints: list[str] = field(default_factory=list)
    workspace_root: str = ""
    repo_root: str = ""
    campaign_title: str = ""
    template_origin: str = ""
    composition_mode: str = ""
    skeleton_changed: bool = False
    composition_plan: dict[str, Any] = field(default_factory=dict)
    created_from: str = ""
    negotiation_session_id: str = ""
    iteration_budget: IterationBudget = field(default_factory=IterationBudget)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.top_level_goal = _normalize_text(self.top_level_goal)
        self.materials = _normalize_string_list(self.materials)
        self.hard_constraints = _normalize_string_list(self.hard_constraints)
        self.workspace_root = _normalize_text(self.workspace_root)
        self.repo_root = _normalize_text(self.repo_root)
        self.campaign_title = _normalize_text(self.campaign_title)
        self.template_origin = _normalize_text(self.template_origin)
        self.composition_mode = normalize_composition_mode(self.composition_mode)
        self.skeleton_changed = bool(self.skeleton_changed)
        self.composition_plan = dict(self.composition_plan or {})
        self.created_from = _normalize_text(self.created_from)
        self.negotiation_session_id = _normalize_text(self.negotiation_session_id)
        if not isinstance(self.iteration_budget, IterationBudget):
            self.iteration_budget = IterationBudget.from_dict(self.iteration_budget)
        self.metadata = dict(self.metadata or {})
        self._merge_template_contract(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["iteration_budget"] = self.iteration_budget.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "CampaignSpec":
        if not isinstance(payload, Mapping):
            return cls()
        data = dict(payload)
        data["iteration_budget"] = IterationBudget.from_dict(data.get("iteration_budget"))
        return cls(**data)

    def _merge_template_contract(self, metadata: Mapping[str, Any]) -> None:
        if not isinstance(metadata, Mapping):
            return
        meta_payload = dict(metadata)
        contract_payload = meta_payload.get("template_contract")
        contract = dict(contract_payload) if isinstance(contract_payload, Mapping) else {}
        if not self.template_origin:
            self.template_origin = _normalize_text(
                meta_payload.get("template_origin")
                or meta_payload.get("template_id")
                or meta_payload.get("template")
                or contract.get("template_origin")
                or contract.get("template_id")
                or contract.get("template")
            )
        if not self.composition_mode:
            self.composition_mode = normalize_composition_mode(
                meta_payload.get("composition_mode") or contract.get("composition_mode")
            )
        if "skeleton_changed" in meta_payload or "skeleton_changed" in contract:
            if not self.skeleton_changed:
                self.skeleton_changed = bool(
                    meta_payload.get("skeleton_changed")
                    if "skeleton_changed" in meta_payload
                    else contract.get("skeleton_changed")
                )
        if not self.composition_plan:
            plan = meta_payload.get("composition_plan")
            if plan is None:
                plan = contract.get("composition_plan")
            if isinstance(plan, Mapping):
                self.composition_plan = dict(plan)
        if not self.created_from:
            self.created_from = _normalize_text(
                meta_payload.get("created_from") or contract.get("created_from")
            )
        if not self.negotiation_session_id:
            self.negotiation_session_id = _normalize_text(
                meta_payload.get("negotiation_session_id") or contract.get("negotiation_session_id")
            )
        if self.skeleton_changed and self.composition_mode != "composition":
            self.composition_mode = "composition"
        if not self.composition_mode:
            if self.skeleton_changed or self.composition_plan:
                self.composition_mode = "composition"
            elif self.template_origin:
                self.composition_mode = "template"
        contract = _template_contract_payload(
            template_origin=self.template_origin,
            composition_mode=self.composition_mode,
            skeleton_changed=self.skeleton_changed,
            composition_plan=self.composition_plan,
            created_from=self.created_from,
            negotiation_session_id=self.negotiation_session_id,
        )
        if contract:
            meta_payload["template_contract"] = contract
            self.metadata = meta_payload


@dataclass(slots=True)
class WorkingContract:
    contract_id: str = field(default_factory=lambda: _new_id("contract"))
    version: int = 1
    working_goal: str = ""
    working_acceptance: list[str] = field(default_factory=list)
    iteration_budget: IterationBudget = field(default_factory=IterationBudget)
    risk_register: list[str] = field(default_factory=list)
    phase_scorecard: dict[str, Any] = field(default_factory=dict)
    strategy_notes: list[str] = field(default_factory=list)
    rewrite_count: int = 0
    last_verdict_decision: str = ""
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.version = max(1, int(self.version or 1))
        self.working_goal = _normalize_text(self.working_goal)
        self.working_acceptance = _normalize_string_list(self.working_acceptance)
        if not isinstance(self.iteration_budget, IterationBudget):
            self.iteration_budget = IterationBudget.from_dict(self.iteration_budget)
        self.risk_register = _normalize_string_list(self.risk_register)
        self.phase_scorecard = dict(self.phase_scorecard or {})
        self.strategy_notes = _normalize_string_list(self.strategy_notes)
        self.rewrite_count = max(0, int(self.rewrite_count or 0))
        self.last_verdict_decision = normalize_verdict_decision(self.last_verdict_decision, default="continue")
        self.created_at = _normalize_text(self.created_at) or _utc_now_iso()
        self.updated_at = _normalize_text(self.updated_at) or _utc_now_iso()

    def touch(self) -> None:
        self.updated_at = _utc_now_iso()

    def rewrite_from_evaluation(self, verdict: "EvaluationVerdict") -> "WorkingContract":
        next_goal = _normalize_text(verdict.next_iteration_goal) or self.working_goal
        revised_acceptance = list(self.working_acceptance)
        if verdict.decision == "recover":
            revised_acceptance = list(self.working_acceptance) + ["stabilize failing area before broader change"]
        next_scorecard = dict(self.phase_scorecard or {})
        next_scorecard["last_decision"] = verdict.decision
        next_scorecard["last_score"] = verdict.score
        note = f"reviewer:{verdict.reviewer_role_id or 'reviewer'} decision={verdict.decision}"
        return WorkingContract(
            version=self.version + 1,
            working_goal=next_goal,
            working_acceptance=revised_acceptance,
            iteration_budget=IterationBudget.from_dict(self.iteration_budget.to_dict()),
            risk_register=list(self.risk_register),
            phase_scorecard=next_scorecard,
            strategy_notes=list(self.strategy_notes) + [note],
            rewrite_count=self.rewrite_count + 1,
            last_verdict_decision=verdict.decision,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["iteration_budget"] = self.iteration_budget.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "WorkingContract":
        if not isinstance(payload, Mapping):
            return cls()
        data = dict(payload)
        data["iteration_budget"] = IterationBudget.from_dict(data.get("iteration_budget"))
        return cls(**data)


@dataclass(slots=True)
class EvaluationVerdict:
    verdict_id: str = field(default_factory=lambda: _new_id("verdict"))
    campaign_id: str = ""
    iteration: int = 0
    phase: str = CampaignPhase.EVALUATE.value
    decision: str = "continue"
    score: float = 0.0
    rationale: str = ""
    reviewer_role_id: str = "campaign_reviewer"
    evidence_artifact_ids: list[str] = field(default_factory=list)
    next_iteration_goal: str = ""
    contract_patch: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.campaign_id = _normalize_text(self.campaign_id)
        self.iteration = max(0, int(self.iteration or 0))
        self.phase = CampaignPhase.normalize(self.phase, default=CampaignPhase.EVALUATE).value
        self.decision = normalize_verdict_decision(self.decision)
        self.score = max(0.0, min(1.0, float(self.score or 0.0)))
        self.rationale = _normalize_text(self.rationale)
        self.reviewer_role_id = _normalize_text(self.reviewer_role_id) or "campaign_reviewer"
        self.evidence_artifact_ids = _normalize_string_list(self.evidence_artifact_ids)
        self.next_iteration_goal = _normalize_text(self.next_iteration_goal)
        self.contract_patch = dict(self.contract_patch or {})
        self.created_at = _normalize_text(self.created_at) or _utc_now_iso()
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "EvaluationVerdict":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class CampaignArtifactSummary:
    artifact_id: str = field(default_factory=lambda: _new_id("artifact"))
    campaign_id: str = ""
    iteration: int = 0
    phase: str = CampaignPhase.DISCOVER.value
    kind: str = ""
    label: str = ""
    ref: str = ""
    created_at: str = field(default_factory=_utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.campaign_id = _normalize_text(self.campaign_id)
        self.iteration = max(0, int(self.iteration or 0))
        self.phase = CampaignPhase.normalize(self.phase).value
        self.kind = _normalize_text(self.kind)
        self.label = _normalize_text(self.label)
        self.ref = _normalize_text(self.ref)
        self.created_at = _normalize_text(self.created_at) or _utc_now_iso()
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "CampaignArtifactSummary":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class CampaignEvent:
    event_id: str = field(default_factory=lambda: _new_id("campaign_event"))
    campaign_id: str = ""
    event_type: str = ""
    iteration: int = 0
    phase: str = CampaignPhase.DISCOVER.value
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.campaign_id = _normalize_text(self.campaign_id)
        self.event_type = _normalize_text(self.event_type)
        self.iteration = max(0, int(self.iteration or 0))
        self.phase = CampaignPhase.normalize(self.phase).value
        self.payload = dict(self.payload or {})
        self.created_at = _normalize_text(self.created_at) or _utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "CampaignEvent":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class CampaignTurnReceipt:
    turn_id: str = field(default_factory=lambda: _new_id("turn"))
    campaign_id: str = ""
    session_id: str = ""
    macro_state: str = "running"
    summary: str = ""
    next_action: str = ""
    delivery_refs: list[str] = field(default_factory=list)
    verdict: dict[str, Any] = field(default_factory=dict)
    artifact_records: list[dict[str, Any]] = field(default_factory=list)
    session_patch: dict[str, Any] = field(default_factory=dict)
    advisory_updates: dict[str, Any] = field(default_factory=dict)
    continue_token: str = ""
    yield_reason: str = ""
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.turn_id = _normalize_text(self.turn_id) or _new_id("turn")
        self.campaign_id = _normalize_text(self.campaign_id)
        self.session_id = _normalize_text(self.session_id)
        self.macro_state = normalize_campaign_status(self.macro_state, default="running")
        self.summary = _normalize_text(self.summary)
        self.next_action = _normalize_text(self.next_action)
        self.delivery_refs = _normalize_string_list(self.delivery_refs)
        self.verdict = dict(self.verdict or {})
        self.artifact_records = [
            dict(item)
            for item in (self.artifact_records or [])
            if isinstance(item, Mapping)
        ]
        self.session_patch = dict(self.session_patch or {})
        self.advisory_updates = dict(self.advisory_updates or {})
        self.continue_token = _normalize_text(self.continue_token)
        self.yield_reason = _normalize_text(self.yield_reason)
        self.created_at = _normalize_text(self.created_at) or _utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "CampaignTurnReceipt":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class OperatorActionRecord:
    action_id: str = field(default_factory=lambda: _new_id("operator_action"))
    campaign_id: str = ""
    target_scope: str = "campaign"
    target_node_id: str = ""
    action_type: str = ""
    operator_id: str = ""
    operator_reason: str = ""
    policy_source: str = ""
    trace_id: str = ""
    status: str = "applied"
    result_summary: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    receipt_id: str = ""
    recovery_decision_id: str = ""
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.action_id = _normalize_text(self.action_id) or _new_id("operator_action")
        self.campaign_id = _normalize_text(self.campaign_id)
        self.target_scope = _normalize_text(self.target_scope) or "campaign"
        self.target_node_id = _normalize_text(self.target_node_id)
        self.action_type = _normalize_text(self.action_type)
        self.operator_id = _normalize_text(self.operator_id)
        self.operator_reason = _normalize_text(self.operator_reason)
        self.policy_source = _normalize_text(self.policy_source)
        self.trace_id = _normalize_text(self.trace_id)
        self.status = _normalize_text(self.status) or "applied"
        self.result_summary = _normalize_text(self.result_summary)
        self.payload = dict(self.payload or {})
        self.receipt_id = _normalize_text(self.receipt_id)
        self.recovery_decision_id = _normalize_text(self.recovery_decision_id)
        self.created_at = _normalize_text(self.created_at) or _utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "OperatorActionRecord":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class OperatorPatchReceipt:
    receipt_id: str = field(default_factory=lambda: _new_id("operator_receipt"))
    action_id: str = ""
    patch_kind: str = ""
    before_summary: dict[str, Any] = field(default_factory=dict)
    after_summary: dict[str, Any] = field(default_factory=dict)
    effective_scope: str = "campaign"
    effective_timing: str = "future_execution"
    target_node_id: str = ""
    changed_fields: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.receipt_id = _normalize_text(self.receipt_id) or _new_id("operator_receipt")
        self.action_id = _normalize_text(self.action_id)
        self.patch_kind = _normalize_text(self.patch_kind)
        self.before_summary = dict(self.before_summary or {})
        self.after_summary = dict(self.after_summary or {})
        self.effective_scope = _normalize_text(self.effective_scope) or "campaign"
        self.effective_timing = _normalize_text(self.effective_timing) or "future_execution"
        self.target_node_id = _normalize_text(self.target_node_id)
        self.changed_fields = _normalize_string_list(self.changed_fields)
        self.metadata = dict(self.metadata or {})
        self.created_at = _normalize_text(self.created_at) or _utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "OperatorPatchReceipt":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class RecoveryDecisionReceipt:
    decision_id: str = field(default_factory=lambda: _new_id("recovery_decision"))
    action_id: str = ""
    resume_from: str = ""
    recovery_candidate_id: str = ""
    decision_summary: str = ""
    result_state: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        self.decision_id = _normalize_text(self.decision_id) or _new_id("recovery_decision")
        self.action_id = _normalize_text(self.action_id)
        self.resume_from = _normalize_text(self.resume_from)
        self.recovery_candidate_id = _normalize_text(self.recovery_candidate_id)
        self.decision_summary = _normalize_text(self.decision_summary)
        self.result_state = _normalize_text(self.result_state)
        self.metadata = dict(self.metadata or {})
        self.created_at = _normalize_text(self.created_at) or _utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "RecoveryDecisionReceipt":
        if not isinstance(payload, Mapping):
            return cls()
        return cls(**dict(payload))


@dataclass(slots=True)
class CampaignInstance:
    campaign_id: str = field(default_factory=lambda: _new_id("campaign"))
    campaign_title: str = ""
    top_level_goal: str = ""
    materials: list[str] = field(default_factory=list)
    hard_constraints: list[str] = field(default_factory=list)
    workspace_root: str = ""
    repo_root: str = ""
    mission_id: str = ""
    supervisor_session_id: str = ""
    status: str = "draft"
    current_phase: str = CampaignPhase.DISCOVER.value
    next_phase: str = CampaignPhase.IMPLEMENT.value
    current_iteration: int = 0
    working_contract: WorkingContract = field(default_factory=WorkingContract)
    contract_history: list[WorkingContract] = field(default_factory=list)
    verdict_history: list[EvaluationVerdict] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    stopped_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.campaign_id = _normalize_text(self.campaign_id) or _new_id("campaign")
        self.campaign_title = _normalize_text(self.campaign_title)
        self.top_level_goal = _normalize_text(self.top_level_goal)
        self.materials = _normalize_string_list(self.materials)
        self.hard_constraints = _normalize_string_list(self.hard_constraints)
        self.workspace_root = _normalize_text(self.workspace_root)
        self.repo_root = _normalize_text(self.repo_root)
        self.mission_id = _normalize_text(self.mission_id)
        self.supervisor_session_id = _normalize_text(self.supervisor_session_id)
        self.status = normalize_campaign_status(self.status)
        self.current_phase = CampaignPhase.normalize(self.current_phase).value
        self.next_phase = CampaignPhase.normalize(self.next_phase, default=CampaignPhase.IMPLEMENT).value
        self.current_iteration = max(0, int(self.current_iteration or 0))
        if not isinstance(self.working_contract, WorkingContract):
            self.working_contract = WorkingContract.from_dict(self.working_contract)
        self.contract_history = [
            item if isinstance(item, WorkingContract) else WorkingContract.from_dict(item)
            for item in (self.contract_history or [])
            if isinstance(item, (WorkingContract, Mapping))
        ]
        self.verdict_history = [
            item if isinstance(item, EvaluationVerdict) else EvaluationVerdict.from_dict(item)
            for item in (self.verdict_history or [])
            if isinstance(item, (EvaluationVerdict, Mapping))
        ]
        self.created_at = _normalize_text(self.created_at) or _utc_now_iso()
        self.updated_at = _normalize_text(self.updated_at) or _utc_now_iso()
        self.stopped_at = _normalize_text(self.stopped_at)
        self.metadata = dict(self.metadata or {})

    def touch(self) -> None:
        self.updated_at = _utc_now_iso()

    def add_contract_revision(self, contract: WorkingContract) -> None:
        self.working_contract = contract
        self.contract_history.append(contract)
        self.touch()

    def add_verdict(self, verdict: EvaluationVerdict) -> None:
        self.verdict_history.append(verdict)
        self.touch()

    def latest_verdict(self) -> EvaluationVerdict | None:
        return self.verdict_history[-1] if self.verdict_history else None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["working_contract"] = self.working_contract.to_dict()
        payload["contract_history"] = [item.to_dict() for item in self.contract_history]
        payload["verdict_history"] = [item.to_dict() for item in self.verdict_history]
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "CampaignInstance":
        if not isinstance(payload, Mapping):
            return cls()
        data = dict(payload)
        data["working_contract"] = WorkingContract.from_dict(data.get("working_contract"))
        data["contract_history"] = [
            WorkingContract.from_dict(item)
            for item in data.get("contract_history") or []
            if isinstance(item, Mapping)
        ]
        data["verdict_history"] = [
            EvaluationVerdict.from_dict(item)
            for item in data.get("verdict_history") or []
            if isinstance(item, Mapping)
        ]
        return cls(**data)
