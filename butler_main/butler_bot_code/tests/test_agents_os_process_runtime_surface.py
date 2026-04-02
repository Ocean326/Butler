from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from agents_os.process_runtime import (  # noqa: E402
    ExecutionRuntime,
    FROZEN_TYPED_PRIMITIVE_IDS,
    RoleBinding,
    WorkflowFactory,
    WorkflowSession,
    WorkflowSpec,
    WorkflowTemplate,
    primitive_contract_by_id,
)
import agents_os.runtime as legacy_runtime  # noqa: E402
from agents_os.runtime import ExecutionRuntime as LegacyExecutionRuntime  # noqa: E402
from agents_os.process_runtime.factory.workflow_factory import WorkflowFactory as LegacyCompatWorkflowFactory  # noqa: E402
from agents_os.process_runtime.session.workflow_session import WorkflowSession as LegacyCompatWorkflowSession  # noqa: E402
from agents_os.process_runtime.templates.workflow_template import WorkflowTemplate as LegacyCompatWorkflowTemplate  # noqa: E402
from agents_os.process_runtime.workflow.models import WorkflowSpec as LegacyCompatWorkflowSpec  # noqa: E402
from agents_os.workflow import WorkflowSpec as LegacyWorkflowSpec  # noqa: E402
from multi_agents_os import RoleBinding as LegacyRoleBinding  # noqa: E402
from multi_agents_os import WorkflowFactory as LegacyWorkflowFactory  # noqa: E402
from multi_agents_os import WorkflowTemplate as LegacyWorkflowTemplate  # noqa: E402
from runtime_os.process_runtime import workflow as process_workflow  # noqa: E402
from runtime_os.durability_substrate import RuntimeSessionCheckpoint as RuntimeDurabilityCheckpoint  # noqa: E402
from runtime_os.multi_agent_protocols import WorkflowTemplate as RuntimeProtocolWorkflowTemplate  # noqa: E402
from runtime_os.multi_agent_runtime import (  # noqa: E402
    WorkflowFactory as RuntimeSessionWorkflowFactory,
    WorkflowSessionEvent as RuntimeSessionWorkflowEvent,
)
from runtime_os.process_runtime import RuntimeSessionCheckpoint as CompatRuntimeSessionCheckpoint  # noqa: E402
from runtime_os.process_runtime.factory.workflow_factory import WorkflowFactory as RuntimeWorkflowFactory  # noqa: E402
from runtime_os.process_runtime.session.workflow_session import WorkflowSession as RuntimeWorkflowSession  # noqa: E402
from runtime_os.process_runtime.templates.workflow_template import WorkflowTemplate as RuntimeWorkflowTemplate  # noqa: E402
from runtime_os.process_runtime.workflow.models import WorkflowSpec as RuntimeWorkflowSpec  # noqa: E402


class AgentsOsProcessRuntimeSurfaceTests(unittest.TestCase):
    def test_process_runtime_surface_reexports_existing_runtime_and_session_types(self) -> None:
        self.assertIs(ExecutionRuntime, LegacyExecutionRuntime)
        self.assertIs(WorkflowSpec, LegacyWorkflowSpec)
        self.assertIs(WorkflowFactory, LegacyWorkflowFactory)
        self.assertIs(WorkflowTemplate, LegacyWorkflowTemplate)
        self.assertIs(RoleBinding, LegacyRoleBinding)
        self.assertIs(WorkflowSpec, process_workflow.WorkflowSpec)
        self.assertEqual(FROZEN_TYPED_PRIMITIVE_IDS[-1], "workflow_blackboard")
        self.assertEqual(primitive_contract_by_id("mailbox").record_type, "MailboxMessage")

    def test_legacy_compat_submodules_continue_to_follow_runtime_os_targets(self) -> None:
        self.assertIs(LegacyCompatWorkflowFactory, RuntimeWorkflowFactory)
        self.assertIs(LegacyCompatWorkflowSession, RuntimeWorkflowSession)
        self.assertIs(LegacyCompatWorkflowTemplate, RuntimeWorkflowTemplate)
        self.assertIs(LegacyCompatWorkflowSpec, RuntimeWorkflowSpec)

    def test_new_layered_runtime_surfaces_resolve_to_same_objects(self) -> None:
        self.assertIs(RuntimeSessionWorkflowFactory, RuntimeWorkflowFactory)
        self.assertIs(RuntimeProtocolWorkflowTemplate, RuntimeWorkflowTemplate)
        self.assertIs(RuntimeDurabilityCheckpoint, CompatRuntimeSessionCheckpoint)
        event = RuntimeSessionWorkflowEvent(session_id="session.demo", event_type="join.completed")
        self.assertEqual(event.layer, "L4.multi_agent_runtime")
        self.assertEqual(event.subject_ref, "session.demo")

    def test_legacy_agent_runtime_no_longer_lists_process_runtime_symbols_in_public_surface(self) -> None:
        self.assertNotIn("ExecutionRuntime", legacy_runtime.__all__)
        self.assertNotIn("WorkflowSpec", legacy_runtime.__all__)
        self.assertNotIn("WorkflowCursor", legacy_runtime.__all__)
        self.assertNotIn("WorkflowCheckpoint", legacy_runtime.__all__)

    def test_process_runtime_factory_round_trip_keeps_session_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            factory = WorkflowFactory(Path(tmp) / "workflow_sessions")
            session = factory.create_session(
                template={
                    "template_id": "demo.template",
                    "kind": "local_collaboration",
                    "roles": [{"role_id": "planner", "capability_id": "cap.plan"}],
                    "steps": [{"step_id": "draft", "title": "Draft"}],
                },
                driver_kind="orchestrator_node",
            )

            bundle = factory.load_session(session.session_id)
            self.assertIsInstance(bundle.session, WorkflowSession)
            self.assertEqual(bundle.session.template_id, "demo.template")
            self.assertEqual(bundle.session.active_step, "draft")


if __name__ == "__main__":
    unittest.main()
