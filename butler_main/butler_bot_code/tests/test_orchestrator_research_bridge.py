from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.butler_bot_code.tests._tmpdir import test_workdir  # noqa: E402
from agents_os.runtime import AcceptanceReceipt  # noqa: E402
from butler_main.orchestrator import (  # noqa: E402
    FileLedgerEventStore,
    FileMissionStore,
    MissionNode,
    OrchestratorResearchBridge,
    OrchestratorService,
)
from butler_main.research.manager.code.research_manager import (  # noqa: E402
    FileResearchScenarioInstanceStore,
    ResearchManager,
    ResearchResult,
)


class OrchestratorResearchBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_ctx = test_workdir("orchestrator_research_bridge")
        self.root = self._tmp_ctx.__enter__()
        self.service = OrchestratorService(
            FileMissionStore(self.root / "orchestrator"),
            FileLedgerEventStore(self.root / "orchestrator"),
        )
        self.manager = ResearchManager(
            scenario_instance_store=FileResearchScenarioInstanceStore(self.root / "scenario_instances")
        )
        self.bridge = OrchestratorResearchBridge(
            manager=self.manager,
            workspace_resolver=lambda mission, node, branch: str(self.root / "workspace"),
        )

    def tearDown(self) -> None:
        self._tmp_ctx.__exit__(None, None, None)

    def test_research_scenario_branch_invokes_manager_and_records_result(self) -> None:
        mission = self.service.create_mission(
            mission_type="research",
            title="Research scenario mission",
            goal="Plan the next project step",
            nodes=[
                MissionNode(
                    node_id="research_node",
                    kind="research_scenario",
                    title="Plan next step",
                    runtime_plan={
                        "workflow_template": {
                            "template_id": "research.project_next_step",
                            "kind": "research_scenario",
                            "roles": [{"role_id": "planner", "capability_id": "research"}],
                            "steps": [{"step_id": "capture", "title": "Capture"}],
                        },
                        "workflow_inputs": {"project_id": "demo_project", "goal": "Plan the next project step"},
                        "research_unit_id": "paper_manager.project_next_step_planning",
                        "scenario_action": "prepare",
                        "subworkflow_kind": "research_scenario",
                    },
                    metadata={
                        "research_unit_id": "paper_manager.project_next_step_planning",
                        "scenario_action": "prepare",
                        "subworkflow_kind": "research_scenario",
                    },
                )
            ],
        )

        dispatched = self.service.dispatch_ready_nodes(mission.mission_id, limit=1)
        self.assertEqual(len(dispatched), 1)
        branch = dispatched[0]
        session_id = str(branch["input_payload"].get("workflow_session_id") or "")
        self.assertTrue(session_id)

        outcomes = self.bridge.execute_and_record(
            self.service,
            mission_id=mission.mission_id,
            branch_ids=[branch["branch_id"]],
        )
        self.assertEqual(len(outcomes), 1)
        outcome = outcomes[0]
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.status, "ready")
        self.assertEqual(outcome.result_payload["workflow_session_id"], session_id)
        self.assertEqual(outcome.result_payload["unit_id"], "paper_manager.project_next_step_planning")
        self.assertTrue(str(outcome.result_payload["scenario_instance_id"]))

        summary = self.service.summarize_mission(mission.mission_id)
        self.assertEqual(summary["branches"][0]["status"], "succeeded")
        self.assertEqual(summary["nodes"][0]["status"], "done")

        session_root = self.root / "orchestrator" / "workflow_sessions" / session_id
        session_payload = json.loads((session_root / "session.json").read_text(encoding="utf-8"))
        shared_state_payload = json.loads((session_root / "shared_state.json").read_text(encoding="utf-8"))
        artifact_registry = json.loads((session_root / "artifact_registry.json").read_text(encoding="utf-8"))
        collaboration_payload = json.loads((session_root / "collaboration.json").read_text(encoding="utf-8"))

        self.assertEqual(session_payload["status"], "completed")
        self.assertEqual(shared_state_payload["state"]["research_unit_id"], "paper_manager.project_next_step_planning")
        self.assertEqual(shared_state_payload["state"]["scenario_action"], "prepare")
        self.assertEqual(shared_state_payload["state"]["current_step_id"], "capture")
        self.assertTrue(shared_state_payload["state"]["scenario_instance_id"])
        with (session_root / "events.jsonl").open("r", encoding="utf-8") as handle:
            self.assertGreaterEqual(sum(1 for _ in handle), 4)
        self.assertIn("capture", artifact_registry["refs_by_step"])
        self.assertEqual(collaboration_payload["step_ownerships"]["capture"]["owner_role_id"], "manager")
        self.assertEqual(collaboration_payload["step_ownerships"]["capture"]["assignee_id"], "research_manager:brainstorm")
        self.assertEqual(collaboration_payload["mailbox_messages"][0]["recipient_role_id"], "planner")
        self.assertEqual(collaboration_payload["handoffs"][0]["target_role_id"], "planner")
        self.assertEqual(collaboration_payload["join_contracts"][0]["merge_strategy"], "proceed")

        workflow_summary = self.service.summarize_workflow_session(session_id)
        self.assertEqual(workflow_summary["collaboration"]["mailbox_message_count"], 1)
        self.assertEqual(workflow_summary["collaboration"]["join_contract_count"], 1)
        self.assertEqual(workflow_summary["collaboration"]["handoff_count"], 1)

    def test_research_scenario_bridge_uses_workflow_session_id_as_invocation_session(self) -> None:
        mission = self.service.create_mission(
            mission_type="research",
            title="Research session binding",
            nodes=[
                MissionNode(
                    node_id="research_node",
                    kind="research_scenario",
                    title="Daily discovery",
                    runtime_plan={
                        "workflow_template": {
                            "template_id": "research.daily_discovery",
                            "kind": "research_scenario",
                            "steps": [{"step_id": "discover", "title": "Discover"}],
                        },
                        "research_unit_id": "paper_finding.daily_paper_discovery",
                        "scenario_action": "scan",
                        "subworkflow_kind": "research_scenario",
                    },
                )
            ],
        )

        dispatched = self.service.dispatch_ready_nodes(mission.mission_id, limit=1)
        branch = dispatched[0]
        session_id = str(branch["input_payload"].get("workflow_session_id") or "")
        self.bridge.execute_and_record(
            self.service,
            mission_id=mission.mission_id,
            branch_ids=[branch["branch_id"]],
        )

        scenario_store = self.manager.scenario_instance_store
        index = json.loads((scenario_store.root_dir / "index.json").read_text(encoding="utf-8"))
        key = f"session::paper_finding.daily_paper_discovery::{session_id}"
        self.assertIn(key, index)
        instance_id = index[key]
        instance_payload = json.loads((scenario_store.root_dir / instance_id / "instance.json").read_text(encoding="utf-8"))
        self.assertEqual(instance_payload["session_id"], session_id)
        self.assertEqual(instance_payload["task_id"], branch["branch_id"])

    def test_research_scenario_bridge_blocks_when_research_unit_missing(self) -> None:
        mission = self.service.create_mission(
            mission_type="research",
            title="Missing unit id",
            nodes=[
                MissionNode(
                    node_id="research_node",
                    kind="research_scenario",
                    title="Broken research node",
                    runtime_plan={
                        "workflow_template": {
                            "template_id": "research.broken",
                            "kind": "research_scenario",
                            "steps": [{"step_id": "start", "title": "Start"}],
                        },
                        "subworkflow_kind": "research_scenario",
                    },
                )
            ],
        )

        dispatched = self.service.dispatch_ready_nodes(mission.mission_id, limit=1)
        branch = dispatched[0]

        outcomes = self.bridge.execute_and_record(
            self.service,
            mission_id=mission.mission_id,
            branch_ids=[branch["branch_id"]],
        )
        outcome = outcomes[0]
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.status, "blocked")
        self.assertEqual(outcome.result.acceptance.failure_class, "context_missing")

        summary = self.service.summarize_mission(mission.mission_id)
        self.assertEqual(summary["branches"][0]["status"], "failed")
        self.assertEqual(summary["nodes"][0]["status"], "repairing")
        self.assertEqual(
            summary["branches"][0]["metadata"]["result_payload"]["failure_class"],
            "context_missing",
        )

    def test_research_projection_replay_is_idempotent_for_same_workflow_session(self) -> None:
        session = self.service._workflow_factory.create_session(
            template={
                "template_id": "research.project_next_step",
                "kind": "research_scenario",
                "roles": [
                    {"role_id": "manager", "capability_id": "research"},
                    {"role_id": "planner", "capability_id": "planning"},
                ],
                "steps": [{"step_id": "capture", "title": "Capture"}],
            },
            driver_kind="research_scenario",
        )

        result = ResearchResult(
            status="ready",
            entrypoint="codex",
            unit_id="paper_manager.project_next_step_planning",
            summary="Prepared project next-step planning via codex",
            acceptance=AcceptanceReceipt(
                goal_achieved=False,
                summary="Prepared project next-step planning via codex",
                evidence=["manager_id=research_manager"],
                artifacts=["artifact:planning-note"],
                uncertainties=[],
                next_action="finish capture and hand off to cluster",
                failure_class="",
            ),
            route={"scenario_instance_id": "scenario_instance_1"},
            payload={
                "dispatch": {
                    "scenario": {"scenario_id": "brainstorm"},
                    "scenario_instance": {
                        "scenario_instance_id": "scenario_instance_1",
                        "scenario_id": "brainstorm",
                        "workflow_id": "brainstorm_session",
                        "current_step_id": "capture",
                        "latest_decision": "proceed",
                    },
                    "workflow_cursor": {
                        "workflow_id": "brainstorm_session",
                        "current_step_id": "capture",
                    },
                    "active_step": {"step_id": "capture"},
                    "step_receipt": {
                        "step_id": "capture",
                        "workflow_id": "brainstorm_session",
                        "worker_name": "research_manager:brainstorm",
                        "process_role": "manager",
                        "step_kind": "prepare",
                        "status": "pending",
                        "metadata": {
                            "artifact_slot": "research.scenario.brainstorm.capture",
                            "step_output_fields": ["problem_frame"],
                        },
                    },
                    "handoff_receipt": {
                        "workflow_id": "brainstorm_session",
                        "source_step_id": "capture",
                        "target_step_id": "cluster",
                        "producer": "manager",
                        "consumer": "planner",
                        "handoff_kind": "scenario_step",
                        "status": "pending",
                        "summary": "handoff from capture to cluster",
                        "artifacts": ["artifact:planning-note"],
                        "handoff_ready": False,
                        "next_action": "finish Capture Problem Frame and hand off to cluster",
                        "metadata": {"scenario_id": "brainstorm"},
                    },
                    "decision_receipt": {
                        "workflow_id": "brainstorm_session",
                        "decision_id": "decision_1",
                        "step_id": "capture",
                        "producer": "research_manager",
                        "status": "pending",
                        "decision": "proceed",
                        "decision_reason": "scenario_action=prepare",
                        "retryable": False,
                        "next_action": "finish Capture Problem Frame and hand off to cluster",
                        "resume_from": "cluster",
                        "artifacts": ["artifact:planning-note"],
                        "metadata": {"scenario_id": "brainstorm"},
                    },
                }
            },
        )

        first_refs = self.bridge._write_back_workflow_session(
            self.service,
            workflow_session_id=session.session_id,
            research_unit_id="paper_manager.project_next_step_planning",
            scenario_action="prepare",
            result=result,
        )
        second_refs = self.bridge._write_back_workflow_session(
            self.service,
            workflow_session_id=session.session_id,
            research_unit_id="paper_manager.project_next_step_planning",
            scenario_action="prepare",
            result=result,
        )

        bundle = self.service._workflow_factory.load_session(session.session_id)
        workflow_summary = self.service.summarize_workflow_session(session.session_id)
        events = self.service._workflow_factory.list_events(session.session_id)

        self.assertEqual(first_refs, second_refs)
        self.assertEqual(bundle.shared_state.state["scenario_instance_id"], "scenario_instance_1")
        self.assertEqual(bundle.shared_state.state_version, 2)
        self.assertEqual(len(bundle.artifact_registry.artifacts), 2)
        self.assertEqual(bundle.artifact_registry.refs_by_step["capture"], [
            "artifact:planning-note",
            "scenario_instance:scenario_instance_1",
        ])
        self.assertEqual(len(bundle.collaboration.mailbox_messages), 1)
        self.assertEqual(len(bundle.collaboration.handoffs), 1)
        self.assertEqual(len(bundle.collaboration.join_contracts), 1)
        self.assertEqual(workflow_summary["collaboration"]["mailbox_message_count"], 1)
        self.assertEqual(workflow_summary["collaboration"]["handoff_count"], 1)
        self.assertEqual(workflow_summary["collaboration"]["join_contract_count"], 1)
        self.assertEqual([event["event_type"] for event in events], [
            "session_created",
            "state_patched",
            "artifact_added",
            "artifact_added",
            "step_owner_assigned",
            "role_handoff_recorded",
            "mailbox_message_posted",
            "join_contract_declared",
        ])


if __name__ == "__main__":
    unittest.main()
