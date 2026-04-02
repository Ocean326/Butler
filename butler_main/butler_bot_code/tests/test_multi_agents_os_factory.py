from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from multi_agents_os import WorkflowFactory  # noqa: E402


class MultiAgentsOsFactoryTests(unittest.TestCase):
    def test_factory_persists_and_loads_workflow_session_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            factory = WorkflowFactory(Path(tmp) / "workflow_sessions")
            session = factory.create_session(
                template={
                    "template_id": "demo.template",
                    "kind": "local_collaboration",
                    "roles": [
                        {"role_id": "researcher", "capability_id": "scan"},
                        {"role_id": "writer", "capability_id": "draft"},
                    ],
                    "steps": [
                        {"step_id": "collect", "title": "Collect signals"},
                        {"step_id": "draft", "title": "Draft output"},
                    ],
                },
                driver_kind="orchestrator_node",
                initial_shared_state={"mission_id": "mission_1"},
            )

            self.assertTrue(factory.session_exists(session.session_id))
            self.assertEqual(factory.list_session_ids(), [session.session_id])

            bundle = factory.load_session(session.session_id)
            self.assertEqual(bundle.template.template_id, "demo.template")
            self.assertEqual(bundle.session.driver_kind, "orchestrator_node")
            self.assertEqual(bundle.session.active_step, "collect")
            self.assertEqual(bundle.session.blackboard_ref, "blackboard.json")
            self.assertEqual(bundle.shared_state.state.get("mission_id"), "mission_1")
            self.assertEqual(bundle.blackboard.session_id, session.session_id)
            self.assertEqual(bundle.blackboard.entries, {})
            self.assertEqual(bundle.session.role_bindings[0].role_id, "researcher")

    def test_factory_patch_state_add_artifact_and_track_local_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            factory = WorkflowFactory(Path(tmp) / "workflow_sessions")
            session = factory.create_session(
                template={
                    "template_id": "demo.template",
                    "kind": "local_collaboration",
                    "roles": [
                        {"role_id": "researcher", "capability_id": "scan"},
                        {"role_id": "writer", "capability_id": "draft"},
                    ],
                    "steps": [{"step_id": "collect", "title": "Collect signals"}],
                },
                driver_kind="research_scenario",
            )

            state = factory.patch_shared_state(session.session_id, {"topic": "agent runtime"})
            ownership = factory.assign_step_owner(
                session.session_id,
                step_id="collect",
                owner_role_id="researcher",
                assignee_id="agent.researcher",
                output_key="collect_notes",
            )
            join_contract = factory.declare_join_contract(
                session.session_id,
                step_id="collect",
                source_role_ids=["researcher", "writer"],
                target_role_id="writer",
                merge_strategy="merge_payloads",
            )
            mailbox_message = factory.post_mailbox_message(
                session.session_id,
                recipient_role_id="writer",
                sender_role_id="researcher",
                step_id="collect",
                message_kind="artifact_ready",
                summary="research notes are ready",
                artifact_refs=["artifact:collect-1"],
            )
            registry = factory.add_artifact(
                session.session_id,
                step_id="collect",
                ref="artifact:collect-1",
                payload={"summary": "captured notes"},
                producer_role_id="researcher",
                owner_role_id="researcher",
                visibility_scope="role_scoped",
                consumer_role_ids=["writer"],
            )
            handoff = factory.record_role_handoff(
                session.session_id,
                step_id="collect",
                source_role_id="researcher",
                target_role_id="writer",
                summary="handoff collected notes to writer",
                artifact_refs=["artifact:collect-1"],
            )
            reloaded_session = factory.update_active_step(session.session_id, "draft", status="active")
            events = factory.list_events(session.session_id)

            self.assertEqual(state.state.get("topic"), "agent runtime")
            self.assertEqual(ownership.owner_role_id, "researcher")
            self.assertEqual(join_contract.target_role_id, "writer")
            self.assertEqual(mailbox_message.recipient_role_id, "writer")
            self.assertEqual(registry.refs_by_step.get("collect"), ["artifact:collect-1"])
            self.assertEqual(handoff.target_role_id, "writer")
            self.assertEqual(reloaded_session.active_step, "draft")
            self.assertEqual([event["event_type"] for event in events], [
                "session_created",
                "state_patched",
                "step_owner_assigned",
                "join_contract_declared",
                "mailbox_message_posted",
                "artifact_added",
                "role_handoff_recorded",
                "active_step_changed",
            ])

            bundle = factory.load_session(session.session_id)
            self.assertEqual(bundle.shared_state.state.get("topic"), "agent runtime")
            self.assertEqual(bundle.artifact_registry.latest_outputs["collect"]["ref"], "artifact:collect-1")
            self.assertEqual(bundle.artifact_registry.latest_outputs["collect"]["visibility"]["scope"], "role_scoped")
            self.assertEqual(bundle.collaboration.step_ownerships["collect"].output_key, "collect_notes")
            self.assertEqual(bundle.collaboration.join_contracts[0].source_role_ids, ["researcher", "writer"])
            self.assertEqual(bundle.collaboration.mailbox_messages[0].message_kind, "artifact_ready")
            self.assertEqual(bundle.collaboration.handoffs[0].summary, "handoff collected notes to writer")
            self.assertEqual(bundle.session.active_step, "draft")

    def test_build_session_from_orchestrator_node_keeps_research_reference_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            factory = WorkflowFactory(Path(tmp) / "workflow_sessions")
            session = factory.build_session_from_orchestrator_node(
                mission_id="mission_1",
                node_id="node_1",
                branch_id="branch_1",
                node_kind="research_scenario",
                node_title="Research next step",
                runtime_plan={
                    "workflow_template": {
                        "template_id": "research.project_next_step",
                        "kind": "research_scenario",
                        "steps": [{"step_id": "capture", "title": "Capture"}],
                    },
                    "research_unit_id": "paper_manager.project_next_step_planning",
                    "scenario_action": "prepare",
                    "subworkflow_kind": "research_scenario",
                },
                node_metadata={"subworkflow_kind": "research_scenario"},
            )

            self.assertIsNotNone(session)
            assert session is not None
            bundle = factory.load_session(session.session_id)
            self.assertEqual(bundle.shared_state.state["research_unit_id"], "paper_manager.project_next_step_planning")
            self.assertEqual(bundle.shared_state.state["scenario_action"], "prepare")
            self.assertEqual(bundle.shared_state.state["subworkflow_kind"], "research_scenario")
            self.assertEqual(bundle.session.metadata["research_unit_id"], "paper_manager.project_next_step_planning")

    def test_factory_idempotent_writes_do_not_duplicate_collaboration_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            factory = WorkflowFactory(Path(tmp) / "workflow_sessions")
            session = factory.create_session(
                template={
                    "template_id": "demo.template",
                    "kind": "local_collaboration",
                    "roles": [
                        {"role_id": "researcher", "capability_id": "scan"},
                        {"role_id": "writer", "capability_id": "draft"},
                    ],
                    "steps": [
                        {"step_id": "collect", "title": "Collect signals"},
                        {"step_id": "review", "title": "Review"},
                    ],
                },
                driver_kind="research_scenario",
            )

            factory.patch_shared_state(session.session_id, {"topic": "agent runtime"})
            factory.patch_shared_state(session.session_id, {"topic": "agent runtime"})
            factory.assign_step_owner(
                session.session_id,
                step_id="collect",
                owner_role_id="researcher",
                assignee_id="agent.researcher",
                output_key="collect_notes",
            )
            factory.assign_step_owner(
                session.session_id,
                step_id="collect",
                owner_role_id="researcher",
                assignee_id="agent.researcher",
                output_key="collect_notes",
            )
            factory.declare_join_contract(
                session.session_id,
                step_id="collect",
                source_role_ids=["researcher", "writer"],
                target_role_id="writer",
                merge_strategy="merge_payloads",
                dedupe_key="join::collect",
            )
            factory.declare_join_contract(
                session.session_id,
                step_id="collect",
                source_role_ids=["researcher", "writer"],
                target_role_id="writer",
                merge_strategy="merge_payloads",
                dedupe_key="join::collect",
            )
            factory.post_mailbox_message(
                session.session_id,
                recipient_role_id="writer",
                sender_role_id="researcher",
                step_id="collect",
                message_kind="artifact_ready",
                summary="research notes are ready",
                artifact_refs=["artifact:collect-1"],
                dedupe_key="mailbox::collect::writer",
            )
            factory.post_mailbox_message(
                session.session_id,
                recipient_role_id="writer",
                sender_role_id="researcher",
                step_id="collect",
                message_kind="artifact_ready",
                summary="research notes are ready",
                artifact_refs=["artifact:collect-1"],
                dedupe_key="mailbox::collect::writer",
            )
            factory.add_artifact(
                session.session_id,
                step_id="collect",
                ref="artifact:collect-1",
                payload={"summary": "captured notes"},
                producer_role_id="researcher",
                owner_role_id="researcher",
                visibility_scope="role_scoped",
                consumer_role_ids=["writer"],
                dedupe_key="artifact::collect::artifact:collect-1",
            )
            factory.add_artifact(
                session.session_id,
                step_id="collect",
                ref="artifact:collect-1",
                payload={"summary": "captured notes"},
                producer_role_id="researcher",
                owner_role_id="researcher",
                visibility_scope="role_scoped",
                consumer_role_ids=["writer"],
                dedupe_key="artifact::collect::artifact:collect-1",
            )
            factory.record_role_handoff(
                session.session_id,
                step_id="collect",
                source_role_id="researcher",
                target_role_id="writer",
                summary="handoff collected notes to writer",
                artifact_refs=["artifact:collect-1"],
                dedupe_key="handoff::collect::writer",
            )
            factory.record_role_handoff(
                session.session_id,
                step_id="collect",
                source_role_id="researcher",
                target_role_id="writer",
                summary="handoff collected notes to writer",
                artifact_refs=["artifact:collect-1"],
                dedupe_key="handoff::collect::writer",
            )
            factory.update_active_step(session.session_id, "review", status="active")
            factory.update_active_step(session.session_id, "review", status="active")

            bundle = factory.load_session(session.session_id)
            events = factory.list_events(session.session_id)

            self.assertEqual(bundle.shared_state.state_version, 2)
            self.assertEqual(len(bundle.artifact_registry.artifacts), 1)
            self.assertEqual(bundle.artifact_registry.refs_by_step["collect"], ["artifact:collect-1"])
            self.assertEqual(len(bundle.collaboration.mailbox_messages), 1)
            self.assertEqual(len(bundle.collaboration.handoffs), 1)
            self.assertEqual(len(bundle.collaboration.join_contracts), 1)
            self.assertEqual(bundle.session.active_step, "review")
            self.assertEqual([event["event_type"] for event in events], [
                "session_created",
                "state_patched",
                "step_owner_assigned",
                "join_contract_declared",
                "mailbox_message_posted",
                "artifact_added",
                "role_handoff_recorded",
                "active_step_changed",
            ])


if __name__ == "__main__":
    unittest.main()
