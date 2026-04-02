from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
for candidate in (REPO_ROOT, BUTLER_MAIN_DIR):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)

import runtime_os  # noqa: E402
from agents_os.contracts import Invocation as LegacyInvocation  # noqa: E402
from agents_os.execution import cli_runner as legacy_cli_runner  # noqa: E402
from butler_main.agents_os.governance import ApprovalTicket as NamespacedApprovalTicket  # noqa: E402
from agents_os.runtime import (  # noqa: E402
    ExecutionRuntime as LegacyExecutionRuntime,
    RuntimeRequestState as LegacyRuntimeRequestState,
)
from butler_main.runtime_os import WorkflowFactory as NamespacedWorkflowFactory  # noqa: E402
from multi_agents_os import WorkflowFactory as LegacyWorkflowFactory  # noqa: E402
from runtime_os import (  # noqa: E402
    Invocation,
    OutputBundle,
    RuntimeRequestState,
    WorkflowFactory,
    WorkflowSession,
    agent_runtime,
    durability_substrate,
    multi_agent_protocols,
    multi_agent_runtime,
    process_runtime,
)
from runtime_os.durability_substrate import RuntimeSessionCheckpoint as DurabilityRuntimeSessionCheckpoint  # noqa: E402
from runtime_os.multi_agent_protocols import WorkflowTemplate as ProtocolWorkflowTemplate  # noqa: E402
from runtime_os.multi_agent_runtime import (  # noqa: E402
    RoleBinding as SessionRoleBinding,
    WorkflowFactory as SessionWorkflowFactory,
    WorkflowSession as SessionWorkflowSession,
    WorkflowSessionEvent as SessionWorkflowEvent,
)
from runtime_os.process_runtime.bindings.role_binding import RoleBinding as RuntimeRoleBinding  # noqa: E402
from runtime_os.process_runtime.engine.execution_runtime import ExecutionRuntime as RuntimeExecutionRuntime  # noqa: E402
from runtime_os.process_runtime.factory.workflow_factory import WorkflowFactory as RuntimeWorkflowFactory  # noqa: E402
from runtime_os.process_runtime.governance.approval import ApprovalTicket as RuntimeApprovalTicket  # noqa: E402
from runtime_os.process_runtime.session.workflow_session import WorkflowSession as RuntimeWorkflowSession  # noqa: E402
from runtime_os.process_runtime.templates.workflow_template import WorkflowTemplate as RuntimeWorkflowTemplate  # noqa: E402
from runtime_os.process_runtime.workflow.models import WorkflowSpec as RuntimeWorkflowSpec  # noqa: E402
from multi_agents_os import RoleBinding as LegacyRoleBinding  # noqa: E402
from multi_agents_os import WorkflowTemplate as LegacyWorkflowTemplate  # noqa: E402
from agents_os.workflow import WorkflowSpec as LegacyWorkflowSpec  # noqa: E402


class RuntimeOsNamespaceTests(unittest.TestCase):
    def test_root_namespace_reexports_agent_and_process_surfaces(self) -> None:
        self.assertIs(WorkflowFactory, LegacyWorkflowFactory)
        self.assertIs(WorkflowFactory, NamespacedWorkflowFactory)
        self.assertIs(Invocation, LegacyInvocation)
        self.assertIs(RuntimeRequestState, LegacyRuntimeRequestState)
        self.assertTrue(hasattr(OutputBundle, "__dataclass_fields__"))
        self.assertTrue(callable(getattr(WorkflowSession, "from_dict", None)))

    def test_split_namespaces_point_to_curated_legacy_modules(self) -> None:
        self.assertIs(agent_runtime.cli_runner, legacy_cli_runner)
        self.assertIs(process_runtime.ExecutionRuntime, LegacyExecutionRuntime)
        self.assertIs(runtime_os.agent_runtime, agent_runtime)
        self.assertIs(runtime_os.multi_agent_protocols, multi_agent_protocols)
        self.assertIs(runtime_os.multi_agent_runtime, multi_agent_runtime)
        self.assertIs(runtime_os.durability_substrate, durability_substrate)
        self.assertIs(runtime_os.process_runtime, process_runtime)

    def test_process_runtime_direct_submodule_imports_resolve_to_curated_targets(self) -> None:
        self.assertIs(RuntimeWorkflowFactory, WorkflowFactory)
        self.assertIs(RuntimeWorkflowSession, WorkflowSession)
        self.assertIs(RuntimeExecutionRuntime, LegacyExecutionRuntime)
        self.assertIs(RuntimeWorkflowSpec, LegacyWorkflowSpec)
        self.assertIs(RuntimeWorkflowTemplate, LegacyWorkflowTemplate)
        self.assertIs(RuntimeRoleBinding, LegacyRoleBinding)
        self.assertIs(RuntimeApprovalTicket, process_runtime.ApprovalTicket)

    def test_layered_runtime_surfaces_share_identity_with_compat_exports(self) -> None:
        self.assertIs(SessionWorkflowFactory, WorkflowFactory)
        self.assertIs(SessionWorkflowSession, WorkflowSession)
        self.assertIs(SessionRoleBinding, LegacyRoleBinding)
        self.assertIs(ProtocolWorkflowTemplate, LegacyWorkflowTemplate)
        self.assertIs(DurabilityRuntimeSessionCheckpoint, process_runtime.RuntimeSessionCheckpoint)
        event = SessionWorkflowEvent(session_id="session.demo", event_type="handoff.emitted")
        self.assertEqual(event.layer, "L4.multi_agent_runtime")
        self.assertEqual(event.subject_ref, "session.demo")


if __name__ == "__main__":
    unittest.main()
