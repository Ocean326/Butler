from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.orchestrator.runner import build_orchestrator_runtime_state_store, run_orchestrator_service  # noqa: E402
from butler_main.orchestrator.interfaces.campaign_service import OrchestratorCampaignService  # noqa: E402
from butler_main.orchestrator.execution_bridge import OrchestratorExecutionBridge  # noqa: E402
from butler_main.orchestrator.interfaces.runner import run_orchestrator_cycle  # noqa: E402
from butler_main.orchestrator.runtime_adapter import ORCHESTRATOR_EXECUTION_CAPABILITY_ID  # noqa: E402
from butler_main.orchestrator.workspace import build_orchestrator_service_for_workspace, resolve_orchestrator_root  # noqa: E402
from butler_main.orchestrator.models import Branch  # noqa: E402
from butler_main.runtime_os.process_runtime import ExecutionReceipt  # noqa: E402


class _CompletedRuntime:
    def execute(self, context) -> ExecutionReceipt:
        request = context.request
        return ExecutionReceipt(
            invocation_id=request.invocation.invocation_id,
            workflow_id=request.workflow.workflow_id if request.workflow is not None else "",
            route=request.route,
            projection=request.workflow,
            agent_id=request.agent_spec.agent_id if request.agent_spec is not None else "orchestrator.test",
            status="completed",
            summary="completed by test runtime",
            metadata={
                "mission_id": str(request.metadata.get("mission_id") or ""),
                "node_id": str(request.metadata.get("node_id") or ""),
                "branch_id": str(request.metadata.get("branch_id") or ""),
            },
        )


class _FakeFeedbackNotifier:
    def __init__(self) -> None:
        self.calls = 0

    def run_cycle(self, *, service) -> dict[str, int]:
        self.calls += 1
        return {
            "campaign_count": 1,
            "doc_sync_count": 1,
            "push_count": 2,
            "error_count": 0,
        }


class OrchestratorRunnerTests(unittest.TestCase):
    def _workspace(self) -> tempfile.TemporaryDirectory[str]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
        (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)
        return tmp

    def test_runtime_state_store_uses_run_orchestrator_root(self) -> None:
        with self._workspace() as tmp:
            store = build_orchestrator_runtime_state_store(tmp)
            self.assertEqual(store.root_dir.name, "orchestrator")
            self.assertEqual(store.pid_file().name, "orchestrator_runtime.pid")
            self.assertEqual(store.watchdog_state_file().name, "orchestrator_watchdog_state.json")
            self.assertEqual(store.run_state_file().name, "orchestrator_run_state.json")

    def test_example_configs_default_to_auto_dispatch_and_auto_execute(self) -> None:
        config_paths = (
            REPO_ROOT / "butler_main" / "butler_bot_code" / "configs" / "butler_bot.json.example",
            REPO_ROOT / "butler_main" / "chat" / "configs" / "butler_bot.json.example",
        )
        for path in config_paths:
            with self.subTest(path=path):
                payload = json.loads(path.read_text(encoding="utf-8"))
                orchestrator_cfg = dict(payload.get("orchestrator") or {})
                self.assertTrue(bool(orchestrator_cfg.get("auto_dispatch")))
                self.assertTrue(bool(orchestrator_cfg.get("auto_execute")))

    def test_once_runner_writes_runtime_state_and_can_dispatch_ready_node(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            service = build_orchestrator_service_for_workspace(workspace)
            mission = service.create_mission(
                mission_type="brainstorm_topic",
                title="runner mission",
                nodes=[{"node_id": "scope", "kind": "define_scope", "title": "Define scope"}],
            )
            summary = run_orchestrator_service(
                {
                    "workspace_root": workspace,
                    "orchestrator": {
                        "auto_dispatch": True,
                        "auto_execute": False,
                        "max_dispatch_per_tick": 1,
                    },
                },
                once=True,
            )
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["mission_count"], 1)
            self.assertEqual(summary["dispatched_count"], 1)

            reloaded = service.get_mission(mission.mission_id)
            assert reloaded is not None
            self.assertEqual(reloaded.status, "running")
            self.assertEqual(reloaded.nodes[0].status, "running")

            store = build_orchestrator_runtime_state_store(workspace)
            watchdog = store.read_watchdog_state()
            run_state = store.read_run_state()
            self.assertEqual(str(watchdog.get("state") or ""), "stopped")
            self.assertEqual(str(run_state.get("state") or ""), "running")
            self.assertIn("missions=1", str(watchdog.get("note") or ""))
            self.assertIn("missions=1", str(run_state.get("note") or ""))

    def test_runner_skips_when_existing_run_state_pid_alive(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            store = build_orchestrator_runtime_state_store(workspace)
            store.write_run_state(run_id="run-prev", state="running", phase="idle", pid=4242, note="previous run")
            store.write_watchdog_state(state="running", pid=4242, note="previous watchdog")

            with mock.patch(
                "butler_main.orchestrator.interfaces.runner._pid_probe",
                return_value={"alive": True, "matches": True},
            ):
                summary = run_orchestrator_service(
                    {
                        "workspace_root": workspace,
                        "orchestrator": {
                            "auto_dispatch": False,
                        },
                    },
                    once=True,
                )

            self.assertFalse(summary["ok"])
            self.assertEqual(summary["reason"], "already-running")
            self.assertEqual(summary["pid"], 4242)
            self.assertEqual(store.read_run_state().get("note"), "previous run")

    def test_once_runner_reconciles_queued_leased_running_branches(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            service = build_orchestrator_service_for_workspace(workspace)
            mission = service.create_mission(
                mission_type="brainstorm_topic",
                title="recover queued/leased/running",
                nodes=[
                    {"node_id": "queued", "kind": "define_scope", "title": "Queued"},
                    {"node_id": "leased", "kind": "define_scope", "title": "Leased"},
                    {"node_id": "running", "kind": "define_scope", "title": "Running"},
                ],
            )
            mission.status = "running"
            for node in mission.nodes:
                node.status = "running"
            service._mission_store.save(mission)

            branch_by_status: dict[str, str] = {}
            for status, node in zip(("queued", "leased", "running"), mission.nodes):
                branch = Branch(
                    mission_id=mission.mission_id,
                    node_id=node.node_id,
                    status=status,
                    metadata={"node_title": node.title},
                )
                service._branch_store.save(branch)
                branch_by_status[status] = branch.branch_id

            summary = run_orchestrator_service(
                {
                    "workspace_root": workspace,
                    "orchestrator": {
                        "auto_dispatch": False,
                        "auto_execute": False,
                    },
                },
                once=True,
            )

            self.assertTrue(summary["ok"])
            mission_summary = service.summarize_mission(mission.mission_id)
            for node_summary in mission_summary["nodes"]:
                self.assertEqual(node_summary["status"], "ready")
            for status, branch_id in branch_by_status.items():
                branch_summary = next(item for item in mission_summary["branches"] if item["branch_id"] == branch_id)
                self.assertEqual(branch_summary["status"], "failed")
                self.assertTrue(bool(branch_summary["metadata"].get("recovered_after_restart")))
                self.assertEqual(branch_summary["metadata"].get("recovered_from_status"), status)

    def test_dispatch_ready_node_can_create_multi_agent_workflow_session(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            service = build_orchestrator_service_for_workspace(workspace)
            mission = service.create_mission(
                mission_type="brainstorm_topic",
                title="workflow-backed mission",
                nodes=[
                    {
                        "node_id": "generate_angles",
                        "kind": "brainstorm",
                        "title": "Generate implementation angles",
                        "runtime_plan": {
                            "worker_profile": "brainstormer",
                            "workflow_template": {
                                "template_id": "brainstorm.generate_angles",
                                "kind": "local_collaboration",
                                "roles": [
                                    {"role_id": "researcher", "capability_id": "reference_scan"},
                                    {"role_id": "ideator", "capability_id": "brainstorm"},
                                ],
                                "steps": [
                                    {"step_id": "collect", "title": "Collect"},
                                    {"step_id": "expand", "title": "Expand"},
                                ],
                            },
                        },
                    }
                ],
            )

            dispatched = service.dispatch_ready_nodes(mission.mission_id, limit=1)
            self.assertEqual(len(dispatched), 1)
            branch = dispatched[0]
            workflow_session_id = str(branch["input_payload"].get("workflow_session_id") or "")
            self.assertTrue(workflow_session_id)
            self.assertEqual(branch["input_payload"].get("workflow_template_id"), "brainstorm.generate_angles")
            self.assertEqual(branch["metadata"].get("workflow_session_id"), workflow_session_id)

            orchestrator_root = Path(resolve_orchestrator_root(workspace))
            session_file = orchestrator_root / "workflow_sessions" / workflow_session_id / "session.json"
            self.assertTrue(session_file.exists())
            payload = session_file.read_text(encoding="utf-8")
            self.assertIn('"template_id": "brainstorm.generate_angles"', payload)
            self.assertIn('"driver_kind": "orchestrator_node"', payload)

            summary = service.summarize_mission(mission.mission_id)
            self.assertEqual(summary["nodes"][0]["metadata"].get("workflow_session_id"), workflow_session_id)

    def test_once_runner_auto_execute_completes_workflow_session(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            service = build_orchestrator_service_for_workspace(workspace)
            mission = service.create_mission(
                mission_type="brainstorm_topic",
                title="auto execute workflow-backed mission",
                nodes=[
                    {
                        "node_id": "generate_angles",
                        "kind": "brainstorm",
                        "title": "Generate implementation angles",
                        "runtime_plan": {
                            "worker_profile": "brainstormer",
                            "workflow_template": {
                                "template_id": "brainstorm.generate_angles",
                                "kind": "local_collaboration",
                                "roles": [
                                    {"role_id": "researcher", "capability_id": "reference_scan"},
                                    {"role_id": "ideator", "capability_id": "brainstorm"},
                                ],
                                "steps": [
                                    {"step_id": "collect", "title": "Collect"},
                                    {"step_id": "expand", "title": "Expand"},
                                ],
                            },
                        },
                    }
                ],
            )
            execution_bridge = OrchestratorExecutionBridge(runtime=_CompletedRuntime())

            summary = run_orchestrator_service(
                {
                    "workspace_root": workspace,
                    "orchestrator": {
                        "auto_dispatch": True,
                        "auto_execute": True,
                        "max_dispatch_per_tick": 1,
                    },
                },
                once=True,
                execution_bridge=execution_bridge,
            )

            self.assertTrue(summary["ok"])
            self.assertEqual(summary["dispatched_count"], 1)
            self.assertEqual(summary["executed_branch_count"], 1)
            self.assertEqual(summary["completed_branch_count"], 1)

            mission_summary = service.summarize_mission(mission.mission_id)
            self.assertEqual(mission_summary["status"], "completed")
            self.assertEqual(mission_summary["branches"][0]["workflow_session"]["status"], "completed")

            workflow_session_id = str(mission_summary["branches"][0]["workflow_session"]["session_id"] or "")
            orchestrator_root = Path(resolve_orchestrator_root(workspace))
            session_file = orchestrator_root / "workflow_sessions" / workflow_session_id / "session.json"
            payload = json.loads(session_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["metadata"]["orchestrator_result"]["branch_status"], "succeeded")

    def test_once_runner_auto_execute_uses_default_runtime_stack(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            service = build_orchestrator_service_for_workspace(workspace)
            mission = service.create_mission(
                mission_type="brainstorm_topic",
                title="default runtime stack mission",
                nodes=[
                    {
                        "node_id": "generate_angles",
                        "kind": "brainstorm",
                        "title": "Generate implementation angles",
                        "runtime_plan": {
                            "worker_profile": "brainstormer",
                            "workflow_template": {
                                "template_id": "brainstorm.generate_angles",
                                "kind": "local_collaboration",
                                "roles": [
                                    {"role_id": "researcher", "capability_id": "reference_scan"},
                                    {"role_id": "ideator", "capability_id": "brainstorm"},
                                ],
                                "steps": [
                                    {"step_id": "collect", "title": "Collect"},
                                    {"step_id": "expand", "title": "Expand"},
                                ],
                            },
                        },
                    }
                ],
            )

            with mock.patch("butler_main.runtime_os.agent_runtime.cli_runner.cli_provider_available", return_value=True), mock.patch(
                "butler_main.runtime_os.agent_runtime.cli_runner.run_prompt",
                return_value=("default runtime stack completed", True),
            ):
                summary = run_orchestrator_service(
                    {
                        "workspace_root": workspace,
                        "orchestrator": {
                            "auto_dispatch": True,
                            "auto_execute": True,
                            "max_dispatch_per_tick": 1,
                        },
                    },
                    once=True,
                )

            self.assertTrue(summary["ok"])
            self.assertEqual(summary["dispatched_count"], 1)
            self.assertEqual(summary["executed_branch_count"], 1)
            self.assertEqual(summary["completed_branch_count"], 1)

            mission_summary = service.summarize_mission(mission.mission_id)
            self.assertEqual(mission_summary["status"], "completed")
            branch_summary = service.summarize_branch(mission_summary["branches"][0]["branch_id"])
            self.assertEqual(mission_summary["branches"][0]["workflow_session"]["status"], "completed")
            self.assertEqual(branch_summary["runtime_debug"]["cli"], "cursor")
            result_payload = dict(branch_summary["metadata"].get("result_payload") or {})
            receipt_metadata = dict(result_payload.get("metadata") or {})
            capability_resolution = dict(receipt_metadata.get("capability_resolution") or {})
            selected = dict(capability_resolution.get("selected") or {})
            selected_capability = dict(selected.get("capability") or {})
            self.assertEqual(receipt_metadata.get("execution_phase"), "executed")
            self.assertTrue(bool(capability_resolution.get("matched")))
            self.assertEqual(selected_capability.get("capability_id"), ORCHESTRATOR_EXECUTION_CAPABILITY_ID)
            self.assertEqual(receipt_metadata.get("resolved_capability_id"), ORCHESTRATOR_EXECUTION_CAPABILITY_ID)

            events = service.list_delivery_events(mission.mission_id)
            vm_events = [item for item in events if item["event_type"] == "workflow_vm_executed"]
            self.assertEqual(len(vm_events), 1)
            self.assertEqual(vm_events[0]["payload"]["engine"], "execution_bridge")

    def test_once_runner_defaults_to_auto_dispatch_and_auto_execute(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            service = build_orchestrator_service_for_workspace(workspace)
            mission = service.create_mission(
                mission_type="brainstorm_topic",
                title="default auto progression mission",
                nodes=[
                    {
                        "node_id": "generate_angles",
                        "kind": "brainstorm",
                        "title": "Generate implementation angles",
                        "runtime_plan": {
                            "worker_profile": "brainstormer",
                            "workflow_template": {
                                "template_id": "brainstorm.generate_angles",
                                "kind": "local_collaboration",
                                "roles": [
                                    {"role_id": "researcher", "capability_id": "reference_scan"},
                                    {"role_id": "ideator", "capability_id": "brainstorm"},
                                ],
                                "steps": [
                                    {"step_id": "collect", "title": "Collect"},
                                    {"step_id": "expand", "title": "Expand"},
                                ],
                            },
                        },
                    }
                ],
            )

            with mock.patch("butler_main.runtime_os.agent_runtime.cli_runner.cli_provider_available", return_value=True), mock.patch(
                "butler_main.runtime_os.agent_runtime.cli_runner.run_prompt",
                return_value=("default auto progression completed", True),
            ):
                summary = run_orchestrator_service(
                    {
                        "workspace_root": workspace,
                        "orchestrator": {
                            "max_dispatch_per_tick": 1,
                        },
                    },
                    once=True,
                )

            self.assertTrue(summary["ok"])
            self.assertEqual(summary["dispatched_count"], 1)
            self.assertEqual(summary["executed_branch_count"], 1)
            self.assertEqual(summary["completed_branch_count"], 1)

            mission_summary = service.summarize_mission(mission.mission_id)
            self.assertEqual(mission_summary["status"], "completed")

    def test_run_cycle_dispatches_higher_priority_mission_first(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            service = build_orchestrator_service_for_workspace(workspace)
            low = service.create_mission(
                mission_type="talk_ingress",
                title="low priority mission",
                priority=50,
                nodes=[{"node_id": "low", "kind": "talk_ingress", "title": "Low priority"}],
            )
            high = service.create_mission(
                mission_type="campaign",
                title="high priority mission",
                priority=80,
                nodes=[{"node_id": "high", "kind": "campaign_supervisor", "title": "High priority"}],
            )

            summary = run_orchestrator_cycle(
                workspace,
                {
                    "workspace_root": workspace,
                    "orchestrator": {
                        "auto_dispatch": True,
                        "auto_execute": False,
                        "max_dispatch_per_tick": 1,
                    },
                },
                current_pid=123,
            )

            self.assertEqual(summary["dispatched_count"], 1)
            low_summary = service.summarize_mission(low.mission_id)
            high_summary = service.summarize_mission(high.mission_id)
            self.assertEqual(high_summary["nodes"][0]["status"], "running")
            self.assertEqual(low_summary["nodes"][0]["status"], "ready")

    def test_once_runner_campaign_runtime_reuses_prebound_supervisor_session(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            campaign_service = OrchestratorCampaignService()
            created = campaign_service.create_campaign(
                workspace,
                {
                    "top_level_goal": "Complete campaign from runner",
                    "materials": ["docs/05"],
                    "hard_constraints": ["reviewer decides final verdict"],
                    "iteration_budget": {"max_iterations": 1},
                },
            )

            summary = run_orchestrator_service(
                {
                    "workspace_root": workspace,
                    "orchestrator": {
                        "auto_dispatch": True,
                        "auto_execute": True,
                        "max_dispatch_per_tick": 1,
                    },
                },
                once=True,
            )

            self.assertTrue(summary["ok"])
            self.assertEqual(summary["dispatched_count"], 1)
            self.assertEqual(summary["executed_branch_count"], 1)
            self.assertEqual(summary["completed_branch_count"], 1)

            orchestrator = build_orchestrator_service_for_workspace(workspace)
            mission = orchestrator.summarize_mission(created["mission_id"])
            branch = mission["branches"][0]
            self.assertEqual(mission["status"], "completed")
            self.assertEqual(branch["workflow_session"]["session_id"], created["supervisor_session_id"])

            campaign = campaign_service.get_campaign_status(workspace, created["campaign_id"])
            self.assertEqual(campaign["status"], "completed")

            event_types = [
                item["event_type"]
                for item in orchestrator.list_recent_events(mission_id=created["mission_id"], limit=20)
            ]
            self.assertIn("workflow_session_resumed", event_types)

    def test_once_runner_reports_feedback_notifier_summary(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            service = build_orchestrator_service_for_workspace(workspace)
            service.create_mission(
                mission_type="brainstorm_topic",
                title="feedback summary mission",
                nodes=[{"node_id": "scope", "kind": "define_scope", "title": "Define scope"}],
            )
            feedback_notifier = _FakeFeedbackNotifier()

            summary = run_orchestrator_service(
                {
                    "workspace_root": workspace,
                    "orchestrator": {
                        "auto_dispatch": False,
                    },
                },
                once=True,
                feedback_notifier=feedback_notifier,
            )

            self.assertEqual(feedback_notifier.calls, 1)
            self.assertEqual(summary["feedback"]["doc_sync_count"], 1)
            self.assertEqual(summary["feedback"]["push_count"], 2)
            self.assertIn("feedback_docs=1", summary["note"])
            self.assertIn("feedback_pushes=2", summary["note"])

    def test_once_runner_recovers_interrupted_running_branch_before_redispatch(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            service = build_orchestrator_service_for_workspace(workspace)
            mission = service.create_mission(
                mission_type="brainstorm_topic",
                title="recover interrupted branch",
                nodes=[{"node_id": "scope", "kind": "define_scope", "title": "Define scope"}],
            )
            dispatched = service.dispatch_ready_nodes(mission.mission_id, limit=1)
            self.assertEqual(len(dispatched), 1)
            interrupted_branch_id = str(dispatched[0]["branch_id"])

            summary = run_orchestrator_service(
                {
                    "workspace_root": workspace,
                    "orchestrator": {
                        "auto_dispatch": True,
                        "auto_execute": True,
                        "max_dispatch_per_tick": 1,
                    },
                },
                once=True,
                execution_bridge=OrchestratorExecutionBridge(runtime=_CompletedRuntime()),
            )

            self.assertTrue(summary["ok"])
            self.assertEqual(summary["completed_branch_count"], 1)

            mission_summary = service.summarize_mission(mission.mission_id)
            self.assertEqual(mission_summary["status"], "completed")
            branches = mission_summary["branches"]
            self.assertEqual(len(branches), 2)
            original = next(item for item in branches if item["branch_id"] == interrupted_branch_id)
            retried = next(item for item in branches if item["branch_id"] != interrupted_branch_id)
            self.assertEqual(original["status"], "failed")
            self.assertTrue(bool(original["metadata"].get("recovered_after_restart")))
            self.assertEqual(retried["status"], "succeeded")

            events = service.list_delivery_events(mission.mission_id)
            event_types = [item["event_type"] for item in events]
            self.assertIn("branch_recovered_after_restart", event_types)


if __name__ == "__main__":
    unittest.main()
