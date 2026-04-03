from __future__ import annotations

from copy import deepcopy
from typing import Any


def _role(
    role_id: str,
    capability_id: str,
    *,
    package_ref: str = "",
    policy_refs: list[str] | None = None,
    agent_spec_id: str = "",
) -> dict[str, Any]:
    payload = {
        "role_id": role_id,
        "capability_id": capability_id,
        "package_ref": package_ref,
        "policy_refs": list(policy_refs or []),
    }
    if agent_spec_id:
        payload["agent_spec_id"] = agent_spec_id
    return payload


def _step(
    step_id: str,
    title: str,
    *,
    step_kind: str,
    role_id: str,
    capability_id: str,
) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "title": title,
        "step_kind": step_kind,
        "role_id": role_id,
        "runtime_binding": {
            "role_id": role_id,
            "capability_id": capability_id,
        },
    }


def _edge(source_step_id: str, target_step_id: str, *, edge_kind: str = "next") -> dict[str, Any]:
    return {
        "edge_id": f"{source_step_id}__{edge_kind}__{target_step_id}",
        "source_step_id": source_step_id,
        "target_step_id": target_step_id,
        "edge_kind": edge_kind,
        "condition": edge_kind,
    }


def _handoff(source_step_id: str, target_step_id: str, source_role_id: str, target_role_id: str) -> dict[str, Any]:
    return {
        "handoff_id": f"{source_step_id}__to__{target_step_id}",
        "source_step_id": source_step_id,
        "target_step_id": target_step_id,
        "source_role_id": source_role_id,
        "target_role_id": target_role_id,
        "handoff_kind": "step_output",
        "artifact_refs": [],
    }


SUPERPOWERS_REVIEW_POLICY = "policy.framework.superpowers.review_gate"
GSTACK_RELEASE_POLICY = "policy.framework.gstack.qa_release"
OPENFANG_AUTONOMY_POLICY = "policy.framework.openfang.supervised_autonomy"


FRAMEWORK_COMPILER_PROFILES: dict[str, dict[str, Any]] = {
    "superpowers_like": {
        "framework_id": "superpowers",
        "profile_id": "superpowers_like",
        "display_name": "Superpowers-like Delivery Loop",
        "source_kind": "framework_profile",
        "butler_targets": ["workflow", "role_binding", "capability_package", "governance_policy", "runtime_binding"],
        "compiler_hints": {
            "profile_family": "creative_delivery",
            "delivery_bias": "ideate_then_implement",
        },
        "runtime_binding_hints": {
            "runtime_key": "codex",
            "worker_profile": "framework.superpowers",
        },
        "governance_defaults": {
            "verification": {
                "kind": "judge",
                "mode": "required",
                "required": True,
            },
            "approval": {
                "kind": "approval",
                "required": False,
            },
            "recovery": {
                "kind": "retry",
                "max_attempts": 1,
            },
        },
        "capability_package_ref": "pkg.framework.superpowers.delivery",
        "team_package_ref": "team.framework.superpowers.core",
        "governance_policy_ref": SUPERPOWERS_REVIEW_POLICY,
        "workflow_inputs": {
            "delivery_style": "creative",
            "review_depth": "editorial",
        },
        "input_contract": {
            "required": ["problem_statement"],
            "optional": ["constraints", "target_audience"],
        },
        "output_contract": {
            "required": ["implementation_plan", "review_notes"],
            "artifacts": ["artifact.superpowers.review_packet"],
        },
        "role_bindings": [
            _role("brainstormer", "cap.brainstorm", package_ref="pkg.cap.ideation", policy_refs=[SUPERPOWERS_REVIEW_POLICY]),
            _role("planner", "cap.plan", package_ref="pkg.cap.planning", policy_refs=[SUPERPOWERS_REVIEW_POLICY]),
            _role("implementer", "cap.implement", package_ref="pkg.cap.build", policy_refs=[SUPERPOWERS_REVIEW_POLICY]),
            _role("reviewer", "cap.review", package_ref="pkg.cap.review", policy_refs=[SUPERPOWERS_REVIEW_POLICY]),
        ],
        "workflow_template": {
            "template_id": "framework.superpowers.superpowers_like",
            "kind": "local_collaboration",
            "entry_step_id": "brainstorm",
            "steps": [
                _step("brainstorm", "Brainstorm", step_kind="dispatch", role_id="brainstormer", capability_id="cap.brainstorm"),
                _step("plan", "Plan", step_kind="plan", role_id="planner", capability_id="cap.plan"),
                _step("implement", "Implement", step_kind="dispatch", role_id="implementer", capability_id="cap.implement"),
                _step("review", "Review", step_kind="verify", role_id="reviewer", capability_id="cap.review"),
            ],
            "edges": [
                _edge("brainstorm", "plan", edge_kind="next"),
                _edge("plan", "implement", edge_kind="on_success"),
                _edge("implement", "review", edge_kind="on_success"),
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact.superpowers.review_packet",
                    "artifact_kind": "review_packet",
                    "producer_step_id": "review",
                    "owner_role_id": "reviewer",
                    "contract_ref": "output_contract",
                }
            ],
            "handoffs": [
                _handoff("brainstorm", "plan", "brainstormer", "planner"),
                _handoff("plan", "implement", "planner", "implementer"),
                _handoff("implement", "review", "implementer", "reviewer"),
            ],
        },
    },
    "gstack_like": {
        "framework_id": "gstack",
        "profile_id": "gstack_like",
        "display_name": "gstack-like Delivery Stack",
        "source_kind": "framework_profile",
        "butler_targets": ["workflow", "role_binding", "capability_package", "governance_policy", "runtime_binding"],
        "compiler_hints": {
            "profile_family": "delivery_stack",
            "delivery_bias": "qa_before_ship",
        },
        "runtime_binding_hints": {
            "runtime_key": "codex",
            "worker_profile": "framework.gstack",
        },
        "governance_defaults": {
            "verification": {
                "kind": "judge",
                "mode": "required",
                "required": True,
            },
            "approval": {
                "kind": "approval",
                "required": False,
            },
            "recovery": {
                "kind": "retry_step",
                "resume_from": "build",
                "max_attempts": 2,
            },
        },
        "capability_package_ref": "pkg.framework.gstack.delivery",
        "team_package_ref": "team.framework.gstack.stack",
        "governance_policy_ref": GSTACK_RELEASE_POLICY,
        "workflow_inputs": {
            "stack_mode": "delivery",
            "ship_gate": "qa",
        },
        "input_contract": {
            "required": ["goal"],
            "optional": ["deadline", "risk_budget"],
        },
        "output_contract": {
            "required": ["qa_report", "release_summary"],
            "artifacts": ["artifact.gstack.release_bundle"],
        },
        "role_bindings": [
            _role("thinker", "cap.think", package_ref="pkg.cap.think", policy_refs=[GSTACK_RELEASE_POLICY]),
            _role("planner", "cap.plan", package_ref="pkg.cap.planning", policy_refs=[GSTACK_RELEASE_POLICY]),
            _role("builder", "cap.build", package_ref="pkg.cap.build", policy_refs=[GSTACK_RELEASE_POLICY]),
            _role("qa", "cap.qa", package_ref="pkg.cap.qa", policy_refs=[GSTACK_RELEASE_POLICY]),
            _role("shipper", "cap.ship", package_ref="pkg.cap.release", policy_refs=[GSTACK_RELEASE_POLICY]),
        ],
        "workflow_template": {
            "template_id": "framework.gstack.gstack_like",
            "kind": "local_collaboration",
            "entry_step_id": "think",
            "steps": [
                _step("think", "Think", step_kind="prepare", role_id="thinker", capability_id="cap.think"),
                _step("plan", "Plan", step_kind="plan", role_id="planner", capability_id="cap.plan"),
                _step("build", "Build", step_kind="dispatch", role_id="builder", capability_id="cap.build"),
                _step("qa", "QA", step_kind="verify", role_id="qa", capability_id="cap.qa"),
                _step("ship", "Ship", step_kind="finalize", role_id="shipper", capability_id="cap.ship"),
            ],
            "edges": [
                _edge("think", "plan", edge_kind="next"),
                _edge("plan", "build", edge_kind="on_success"),
                _edge("build", "qa", edge_kind="on_success"),
                _edge("qa", "ship", edge_kind="on_success"),
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact.gstack.release_bundle",
                    "artifact_kind": "release_bundle",
                    "producer_step_id": "ship",
                    "owner_role_id": "shipper",
                    "contract_ref": "output_contract",
                }
            ],
            "handoffs": [
                _handoff("think", "plan", "thinker", "planner"),
                _handoff("plan", "build", "planner", "builder"),
                _handoff("build", "qa", "builder", "qa"),
                _handoff("qa", "ship", "qa", "shipper"),
            ],
        },
    },
    "openfang_guarded_autonomy": {
        "framework_id": "openfang",
        "profile_id": "openfang_guarded_autonomy",
        "display_name": "OpenFang-inspired Guarded Autonomy",
        "source_kind": "framework_profile",
        "butler_targets": ["capability_package", "governance_policy", "approval_gate", "runtime_binding", "workflow"],
        "compiler_hints": {
            "profile_family": "guarded_autonomy",
            "autonomy_mode": "supervised",
        },
        "runtime_binding_hints": {
            "runtime_key": "codex",
            "worker_profile": "framework.openfang",
        },
        "governance_defaults": {
            "verification": {
                "kind": "judge",
                "mode": "required",
                "required": True,
            },
            "approval": {
                "kind": "human_gate",
                "required": True,
            },
            "recovery": {
                "kind": "resume",
                "resume_from": "observe",
                "max_attempts": 1,
            },
        },
        "capability_package_ref": "pkg.framework.openfang.autonomy.monitoring",
        "team_package_ref": "team.framework.openfang.ops",
        "governance_policy_ref": OPENFANG_AUTONOMY_POLICY,
        "workflow_inputs": {
            "autonomy_mode": "guarded",
            "approval_channel": "human_supervisor",
        },
        "input_contract": {
            "required": ["monitor_target"],
            "optional": ["risk_constraints", "alert_threshold"],
        },
        "output_contract": {
            "required": ["approval_record", "execution_report"],
            "artifacts": ["artifact.openfang.execution_report"],
        },
        "role_bindings": [
            _role("observer", "cap.monitor", package_ref="pkg.cap.monitor", policy_refs=[OPENFANG_AUTONOMY_POLICY]),
            _role("analyst", "cap.analyze", package_ref="pkg.cap.analysis", policy_refs=[OPENFANG_AUTONOMY_POLICY]),
            _role("operator", "cap.autonomous_execute", package_ref="pkg.cap.autonomy", policy_refs=[OPENFANG_AUTONOMY_POLICY]),
            _role("approver", "cap.human_gate", package_ref="pkg.cap.governance", policy_refs=[OPENFANG_AUTONOMY_POLICY]),
        ],
        "workflow_template": {
            "template_id": "framework.openfang.openfang_guarded_autonomy",
            "kind": "local_collaboration",
            "entry_step_id": "observe",
            "steps": [
                _step("observe", "Observe", step_kind="dispatch", role_id="observer", capability_id="cap.monitor"),
                _step("analyze", "Analyze", step_kind="plan", role_id="analyst", capability_id="cap.analyze"),
                _step("propose", "Propose", step_kind="dispatch", role_id="operator", capability_id="cap.autonomous_execute"),
                _step("approve", "Approve", step_kind="approve", role_id="approver", capability_id="cap.human_gate"),
                _step("execute", "Execute", step_kind="dispatch", role_id="operator", capability_id="cap.autonomous_execute"),
                _step("finalize", "Finalize", step_kind="finalize", role_id="analyst", capability_id="cap.analyze"),
            ],
            "edges": [
                _edge("observe", "analyze", edge_kind="next"),
                _edge("analyze", "propose", edge_kind="on_success"),
                _edge("propose", "approve", edge_kind="on_success"),
                _edge("approve", "execute", edge_kind="on_success"),
                _edge("approve", "execute", edge_kind="resume_from"),
                _edge("execute", "finalize", edge_kind="on_success"),
                _edge("approve", "observe", edge_kind="on_failure"),
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact.openfang.execution_report",
                    "artifact_kind": "execution_report",
                    "producer_step_id": "finalize",
                    "owner_role_id": "analyst",
                    "contract_ref": "output_contract",
                }
            ],
            "handoffs": [
                _handoff("observe", "analyze", "observer", "analyst"),
                _handoff("analyze", "propose", "analyst", "operator"),
                _handoff("propose", "approve", "operator", "approver"),
                _handoff("approve", "execute", "approver", "operator"),
                _handoff("execute", "finalize", "operator", "analyst"),
            ],
        },
    },
}


FRAMEWORK_PROFILE_ALIASES: dict[str, str] = {
    "superpowers": "superpowers_like",
    "superpowers_like": "superpowers_like",
    "gstack": "gstack_like",
    "gstack_like": "gstack_like",
    "openfang": "openfang_guarded_autonomy",
    "openfang_guarded_autonomy": "openfang_guarded_autonomy",
    "openfang_inspired": "openfang_guarded_autonomy",
}


def list_framework_profile_ids() -> list[str]:
    return sorted(FRAMEWORK_COMPILER_PROFILES)


def resolve_framework_profile_id(profile_id: str = "", framework_id: str = "") -> str:
    for candidate in (str(profile_id or "").strip(), str(framework_id or "").strip()):
        if candidate and candidate in FRAMEWORK_PROFILE_ALIASES:
            return FRAMEWORK_PROFILE_ALIASES[candidate]
    return ""


def get_framework_profile_definition(profile_id: str = "", *, framework_id: str = "") -> dict[str, Any]:
    resolved_id = resolve_framework_profile_id(profile_id, framework_id)
    if not resolved_id:
        return {}
    payload = FRAMEWORK_COMPILER_PROFILES.get(resolved_id)
    return deepcopy(payload) if isinstance(payload, dict) else {}
