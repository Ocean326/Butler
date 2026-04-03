from __future__ import annotations

from copy import deepcopy
from typing import Any


def _superpowers_like_fixture() -> dict[str, Any]:
    framework_profile = {
        "framework_id": "superpowers_like",
        "profile_id": "demo.superpowers_like.v1",
        "display_name": "Superpowers-like Delivery Loop",
        "origin": "external_framework",
        "compilation_mode": "fixture_stub",
        "future_compiler_entry": "framework profile -> Butler Workflow IR",
        "notes": "Lane D freezes the demo input and acceptance evidence before Lane B is fully framework-native.",
    }
    return {
        "demo_id": "superpowers_like",
        "display_name": "Demo 1: Superpowers-like",
        "framework_profile": framework_profile,
        "mission": {
            "mission_type": "framework_demo.superpowers_like",
            "title": "Superpowers-like implementation brief",
            "goal": "Turn a rough feature request into a concise implementation brief with explicit review output.",
            "inputs": {
                "problem_statement": "Need a shippable workflow-demo fixture that proves Butler can execute a framework-shaped flow.",
                "target_deliverable": "implementation_brief",
                "output_style": "concise",
            },
            "success_criteria": [
                "workflow IR compiled from the frozen Superpowers-like fixture",
                "workflow VM executed through the default runtime stack",
                "artifacts, receipts, and node writeback are all observable",
            ],
            "constraints": {
                "no_ui": True,
                "preserve_existing_orchestrator_runner": True,
            },
            "nodes": [
                {
                    "node_id": "ship_superpowers_brief",
                    "kind": "brainstorm",
                    "title": "Produce a reviewed implementation brief",
                    "runtime_plan": {
                        "worker_profile": "superpowers.delivery",
                        "runtime_key": "superpowers.delivery",
                        "agent_id": "orchestrator.demo.superpowers",
                        "role_bindings": [
                            {"role_id": "brainstormer", "capability_id": "cap.superpowers.brainstorm"},
                            {"role_id": "planner", "capability_id": "cap.superpowers.plan"},
                            {"role_id": "implementer", "capability_id": "cap.superpowers.implement"},
                            {"role_id": "reviewer", "capability_id": "cap.superpowers.review"},
                        ],
                        "workflow_template": {
                            "template_id": "demo.superpowers_like.delivery_loop",
                            "kind": "local_collaboration",
                            "entry_step_id": "brainstorm",
                            "metadata": {
                                "framework_origin": framework_profile,
                                "demo_id": "superpowers_like",
                            },
                            "roles": [
                                {"role_id": "brainstormer", "capability_id": "cap.superpowers.brainstorm"},
                                {"role_id": "planner", "capability_id": "cap.superpowers.plan"},
                                {"role_id": "implementer", "capability_id": "cap.superpowers.implement"},
                                {"role_id": "reviewer", "capability_id": "cap.superpowers.review"},
                            ],
                            "steps": [
                                {"step_id": "brainstorm", "title": "Brainstorm", "step_kind": "dispatch", "role": "brainstormer"},
                                {"step_id": "plan", "title": "Plan", "step_kind": "dispatch", "role": "planner"},
                                {"step_id": "implement", "title": "Implement", "step_kind": "dispatch", "role": "implementer"},
                                {"step_id": "review", "title": "Review", "step_kind": "dispatch", "role": "reviewer"},
                            ],
                            "edges": [
                                {"edge_id": "brainstorm__plan", "source_step_id": "brainstorm", "target_step_id": "plan", "condition": "next"},
                                {"edge_id": "plan__implement", "source_step_id": "plan", "target_step_id": "implement", "condition": "next"},
                                {"edge_id": "implement__review", "source_step_id": "implement", "target_step_id": "review", "condition": "next"},
                            ],
                            "artifacts": [
                                {"artifact_id": "implementation_brief", "artifact_kind": "document", "producer_step_id": "implement", "owner_role_id": "implementer", "contract_ref": "contract.output.implementation_brief"},
                                {"artifact_id": "review_notes", "artifact_kind": "document", "producer_step_id": "review", "owner_role_id": "reviewer", "contract_ref": "contract.output.review_notes"},
                            ],
                            "handoffs": [
                                {"handoff_id": "brainstorm_to_plan", "source_step_id": "brainstorm", "target_step_id": "plan", "source_role_id": "brainstormer", "target_role_id": "planner", "artifact_refs": ["implementation_brief"], "handoff_kind": "step_output"},
                                {"handoff_id": "plan_to_implement", "source_step_id": "plan", "target_step_id": "implement", "source_role_id": "planner", "target_role_id": "implementer", "artifact_refs": ["implementation_brief"], "handoff_kind": "step_output"},
                                {"handoff_id": "implement_to_review", "source_step_id": "implement", "target_step_id": "review", "source_role_id": "implementer", "target_role_id": "reviewer", "artifact_refs": ["implementation_brief"], "handoff_kind": "step_output"},
                            ],
                        },
                        "workflow_inputs": {
                            "problem_statement": "Need a shippable workflow-demo fixture that proves Butler can execute a framework-shaped flow.",
                            "target_deliverable": "implementation_brief",
                        },
                        "runtime_binding": {
                            "runtime_key": "superpowers.delivery",
                            "agent_id": "orchestrator.demo.superpowers",
                            "worker_profile": "superpowers.delivery",
                        },
                        "input_contract": {
                            "required": ["problem_statement", "target_deliverable"],
                        },
                        "output_contract": {
                            "required": ["implementation_brief", "review_notes"],
                        },
                        "capability_package_ref": "pkg.cap.superpowers.delivery",
                        "team_package_ref": "team.butler.demo",
                        "governance_policy_ref": "policy.superpowers.review.optional",
                        "verification": {"kind": "judge", "required": False, "mode": "skip"},
                        "recovery": {"kind": "retry_step", "resume_from": "brainstorm", "max_attempts": 1},
                    },
                }
            ],
        },
        "acceptance": {
            "required_event_types": [
                "workflow_ir_compiled",
                "workflow_vm_executed",
                "workflow_session_created",
                "verification_skipped",
                "branch_completed",
            ],
            "required_artifact_ids": ["implementation_brief", "review_notes"],
            "required_package_refs": [
                "capability_package_ref",
                "team_package_ref",
                "governance_policy_ref",
            ],
            "required_framework_origin": {
                "framework_id": "superpowers_like",
                "profile_id": "demo.superpowers_like.v1",
            },
            "required_workflow_template_id": "demo.superpowers_like.delivery_loop",
            "required_vm_engine": "execution_bridge",
            "required_receipt_phase": "executed",
            "required_result_status": "completed",
            "require_output_bundle_summary": True,
            "min_step_count": 4,
            "expected_status": {
                "mission": "completed",
                "node": "done",
                "branch": "succeeded",
                "workflow_session": "completed",
            },
        },
    }


def _openfang_inspired_fixture() -> dict[str, Any]:
    framework_profile = {
        "framework_id": "openfang_inspired",
        "profile_id": "demo.openfang_inspired.v1",
        "display_name": "OpenFang-inspired Guardrail Loop",
        "origin": "external_framework",
        "compilation_mode": "fixture_stub",
        "future_compiler_entry": "framework profile -> capability package + governance refs -> Butler Workflow IR",
        "notes": "This fixture intentionally freezes capability package and approval governance before framework-native compilation lands.",
    }
    return {
        "demo_id": "openfang_inspired",
        "display_name": "Demo 2: OpenFang-inspired",
        "framework_profile": framework_profile,
        "mission": {
            "mission_type": "framework_demo.openfang_inspired",
            "title": "OpenFang-inspired guarded autonomy",
            "goal": "Prepare an operator-approved action packet for a monitored target while keeping governance explicit.",
            "inputs": {
                "watch_target": "Butler orchestrator release lane",
                "risk_posture": "manual_approval_required",
                "action_budget": "single proposal",
            },
            "success_criteria": [
                "workflow IR compiled with capability package and governance refs",
                "workflow VM executed before governance handoff",
                "approval gate becomes observable through orchestrator writeback",
            ],
            "constraints": {
                "operator_gate_required": True,
                "preserve_existing_governance_semantics": True,
            },
            "nodes": [
                {
                    "node_id": "guard_autonomy_packet",
                    "kind": "brainstorm",
                    "title": "Prepare a guarded action packet",
                    "runtime_plan": {
                        "worker_profile": "openfang.guardian",
                        "runtime_key": "openfang.guardian",
                        "agent_id": "orchestrator.demo.openfang",
                        "role_bindings": [
                            {"role_id": "observer", "capability_id": "cap.openfang.observe"},
                            {"role_id": "analyst", "capability_id": "cap.openfang.propose"},
                            {"role_id": "guardian", "capability_id": "cap.openfang.guard"},
                        ],
                        "workflow_template": {
                            "template_id": "demo.openfang_inspired.guardrail_loop",
                            "kind": "local_collaboration",
                            "entry_step_id": "sense",
                            "metadata": {
                                "framework_origin": framework_profile,
                                "demo_id": "openfang_inspired",
                            },
                            "roles": [
                                {"role_id": "observer", "capability_id": "cap.openfang.observe"},
                                {"role_id": "analyst", "capability_id": "cap.openfang.propose"},
                                {"role_id": "guardian", "capability_id": "cap.openfang.guard"},
                            ],
                            "steps": [
                                {"step_id": "sense", "title": "Sense", "step_kind": "dispatch", "role": "observer", "requires_approval": False},
                                {"step_id": "propose", "title": "Propose", "step_kind": "dispatch", "role": "analyst", "requires_approval": False},
                                {"step_id": "package", "title": "Package", "step_kind": "dispatch", "role": "guardian", "requires_approval": False},
                            ],
                            "edges": [
                                {"edge_id": "sense__propose", "source_step_id": "sense", "target_step_id": "propose", "condition": "next"},
                                {"edge_id": "propose__package", "source_step_id": "propose", "target_step_id": "package", "condition": "next"},
                            ],
                            "artifacts": [
                                {"artifact_id": "observation_bundle", "artifact_kind": "document", "producer_step_id": "sense", "owner_role_id": "observer", "contract_ref": "contract.output.observation_bundle"},
                                {"artifact_id": "action_proposal", "artifact_kind": "document", "producer_step_id": "propose", "owner_role_id": "analyst", "contract_ref": "contract.output.action_proposal"},
                                {"artifact_id": "approval_packet", "artifact_kind": "document", "producer_step_id": "package", "owner_role_id": "guardian", "contract_ref": "contract.output.approval_packet"},
                            ],
                            "handoffs": [
                                {"handoff_id": "sense_to_propose", "source_step_id": "sense", "target_step_id": "propose", "source_role_id": "observer", "target_role_id": "analyst", "artifact_refs": ["observation_bundle"], "handoff_kind": "step_output"},
                                {"handoff_id": "propose_to_package", "source_step_id": "propose", "target_step_id": "package", "source_role_id": "analyst", "target_role_id": "guardian", "artifact_refs": ["action_proposal"], "handoff_kind": "step_output"},
                            ],
                        },
                        "workflow_inputs": {
                            "watch_target": "Butler orchestrator release lane",
                            "risk_posture": "manual_approval_required",
                        },
                        "runtime_binding": {
                            "runtime_key": "openfang.guardian",
                            "agent_id": "orchestrator.demo.openfang",
                            "worker_profile": "openfang.guardian",
                        },
                        "input_contract": {
                            "required": ["watch_target", "risk_posture"],
                        },
                        "output_contract": {
                            "required": ["approval_packet"],
                        },
                        "capability_package_ref": "pkg.cap.openfang.guardian",
                        "team_package_ref": "team.butler.autonomy",
                        "governance_policy_ref": "policy.openfang.manual_approval.required",
                        "verification": {"kind": "judge", "required": False, "mode": "skip"},
                        "approval": {"kind": "human_gate", "required": True, "mode": "required"},
                        "recovery": {"kind": "retry_step", "resume_from": "sense", "max_attempts": 1},
                    },
                }
            ],
        },
        "acceptance": {
            "required_event_types": [
                "workflow_ir_compiled",
                "workflow_vm_executed",
                "workflow_session_created",
                "approval_requested",
                "branch_completed",
            ],
            "required_artifact_ids": ["observation_bundle", "action_proposal", "approval_packet"],
            "required_package_refs": [
                "capability_package_ref",
                "team_package_ref",
                "governance_policy_ref",
            ],
            "required_framework_origin": {
                "framework_id": "openfang_inspired",
                "profile_id": "demo.openfang_inspired.v1",
            },
            "required_workflow_template_id": "demo.openfang_inspired.guardrail_loop",
            "required_vm_engine": "execution_bridge",
            "required_receipt_phase": "executed",
            "required_result_status": "completed",
            "require_output_bundle_summary": True,
            "min_step_count": 3,
            "expected_status": {
                "mission": "awaiting_decision",
                "node": "blocked",
                "branch": "succeeded",
                "workflow_session": "awaiting_approval",
            },
        },
    }


_DEMO_FIXTURES: dict[str, dict[str, Any]] = {
    "superpowers_like": _superpowers_like_fixture(),
    "openfang_inspired": _openfang_inspired_fixture(),
}


def list_demo_fixture_ids() -> tuple[str, ...]:
    return tuple(_DEMO_FIXTURES)


def build_demo_fixture(demo_id: str, *, runtime_cli: str = "") -> dict[str, Any]:
    target = str(demo_id or "").strip()
    if target not in _DEMO_FIXTURES:
        raise KeyError(f"unknown demo fixture: {demo_id}")
    payload = deepcopy(_DEMO_FIXTURES[target])
    cli_name = str(runtime_cli or "").strip()
    if cli_name:
        for node in list(payload.get("mission", {}).get("nodes") or []):
            runtime_plan = node.setdefault("runtime_plan", {})
            runtime_profile = dict(runtime_plan.get("runtime_profile") or {})
            runtime_profile["cli"] = cli_name
            runtime_plan["runtime_profile"] = runtime_profile
    return payload
