from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from multi_agents_os import (  # noqa: E402
    FROZEN_TYPED_PRIMITIVE_IDS,
    WorkflowFactory,
    primitive_contract_by_id,
)


class MultiAgentsOsCollaborationTests(unittest.TestCase):
    def test_primitive_contracts_freeze_lane_c_surface(self) -> None:
        self.assertEqual(
            FROZEN_TYPED_PRIMITIVE_IDS,
            (
                "mailbox",
                "ownership",
                "join_contract",
                "handoff",
                "artifact_visibility",
                "workflow_blackboard",
            ),
        )
        blackboard = primitive_contract_by_id("workflow_blackboard")
        visibility = primitive_contract_by_id("artifact_visibility")

        self.assertEqual(blackboard.bundle_field, "blackboard.entries")
        self.assertIn("emit blackboard binding hints only", blackboard.compiler_usage)
        self.assertEqual(blackboard.write_api, ("WorkflowFactory.upsert_blackboard_entry",))
        self.assertEqual(visibility.record_type, "ArtifactVisibility")
        self.assertIn("ArtifactRegistry.visible_records", visibility.read_api)

    def test_blackboard_entries_persist_and_filter_by_visibility(self) -> None:
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

            shared = factory.upsert_blackboard_entry(
                session.session_id,
                entry_key="shared_note",
                payload={"summary": "visible to everyone in session"},
                author_role_id="researcher",
                step_id="collect",
                tags=["summary"],
            )
            scoped = factory.upsert_blackboard_entry(
                session.session_id,
                entry_key="writer_note",
                payload={"summary": "only writer should see this"},
                author_role_id="researcher",
                step_id="collect",
                visibility_scope="role_scoped",
                consumer_role_ids=["writer"],
                tags=["draft"],
            )
            factory.upsert_blackboard_entry(
                session.session_id,
                entry_key="writer_note",
                payload={"summary": "only writer should see this"},
                author_role_id="researcher",
                step_id="collect",
                visibility_scope="role_scoped",
                consumer_role_ids=["writer"],
                tags=["draft"],
            )

            bundle = factory.load_session(session.session_id)
            self.assertEqual(bundle.session.blackboard_ref, "blackboard.json")
            self.assertEqual(bundle.blackboard.get_entry("shared_note").payload["summary"], shared.payload["summary"])
            self.assertEqual(bundle.blackboard.get_entry("writer_note").payload["summary"], scoped.payload["summary"])
            self.assertEqual(
                [entry.entry_key for entry in bundle.blackboard.visible_entries(role_id="writer", step_id="collect")],
                ["shared_note", "writer_note"],
            )
            self.assertEqual(
                [entry.entry_key for entry in bundle.blackboard.visible_entries(role_id="reviewer", step_id="collect")],
                ["shared_note"],
            )

            events = factory.list_events(session.session_id)
            blackboard_events = [event for event in events if event["event_type"] == "blackboard_entry_upserted"]
            self.assertEqual(len(blackboard_events), 2)
            self.assertTrue((factory.session_root(session.session_id) / "blackboard.json").exists())

    def test_artifact_visibility_can_be_read_through_registry_contract(self) -> None:
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

            factory.add_artifact(
                session.session_id,
                step_id="collect",
                ref="artifact:shared",
                payload={"summary": "shared artifact"},
                producer_role_id="researcher",
                owner_role_id="researcher",
                visibility_scope="session",
            )
            factory.add_artifact(
                session.session_id,
                step_id="collect",
                ref="artifact:writer",
                payload={"summary": "writer artifact"},
                producer_role_id="researcher",
                owner_role_id="researcher",
                visibility_scope="role_scoped",
                consumer_role_ids=["writer"],
            )

            bundle = factory.load_session(session.session_id)
            writer_refs = [item.ref for item in bundle.artifact_registry.visible_records(role_id="writer", step_id="collect")]
            reviewer_refs = [item.ref for item in bundle.artifact_registry.visible_records(role_id="reviewer", step_id="collect")]
            writer_index = bundle.artifact_registry.visibility_index(role_id="writer", step_id="collect")

            self.assertEqual(writer_refs, ["artifact:shared", "artifact:writer"])
            self.assertEqual(reviewer_refs, ["artifact:shared"])
            self.assertEqual(writer_index[1]["visibility"]["scope"], "role_scoped")
            self.assertEqual(writer_index[1]["visibility"]["consumer_role_ids"], ["writer"])


if __name__ == "__main__":
    unittest.main()
