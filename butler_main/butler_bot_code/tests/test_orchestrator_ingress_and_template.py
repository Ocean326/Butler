from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.orchestrator import build_orchestrator_service_for_workspace  # noqa: E402
from butler_main.orchestrator.interfaces.ingress_service import OrchestratorIngressService  # noqa: E402
from butler_main.orchestrator.interfaces.query_service import OrchestratorQueryService  # noqa: E402
from butler_main.orchestrator.observe import main as observe_main  # noqa: E402
from butler_main.orchestrator.runtime_paths import resolve_orchestrator_run_file  # noqa: E402
from butler_main.orchestrator.templates import build_agent_harness_brainstorm_inputs  # noqa: E402


class OrchestratorIngressAndTemplateTests(unittest.TestCase):
    @staticmethod
    def _contract_payload(window: dict) -> dict:
        contract = window.get("contract") or window.get("contracts")
        if not isinstance(contract, dict):
            raise AssertionError("observation window must expose a contract payload")
        return contract

    @staticmethod
    def _stable_evidence_keys(contract: dict) -> list[str]:
        payload = contract.get("stable_evidence_keys") or contract.get("evidence_keys") or []
        return [str(item).strip() for item in payload if str(item).strip()]

    @staticmethod
    def _port_ids(contract: dict) -> list[str]:
        raw_ports = contract.get("ports") or []
        port_ids: list[str] = []
        for item in raw_ports:
            if isinstance(item, dict):
                port_id = str(item.get("port_id") or item.get("id") or "").strip()
            else:
                port_id = str(item).strip()
            if port_id:
                port_ids.append(port_id)
        return port_ids

    def _workspace(self) -> tempfile.TemporaryDirectory[str]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
        (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)
        return tmp

    def test_brainstorm_template_creates_route_a_style_mission(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            ingress = OrchestratorIngressService()
            query = OrchestratorQueryService()

            response = ingress.create_mission(
                workspace,
                {
                    "template_id": "brainstorm_topic",
                    "template_inputs": build_agent_harness_brainstorm_inputs(
                        current_date="2026-03-21",
                        reference_items=[
                            {"title": "OpenAI Agents SDK", "url": "https://openai.github.io/openai-agents-python/", "note": "lightweight agents SDK"},
                            {"title": "LangGraph", "url": "https://docs.langchain.com/oss/python/langgraph/overview", "note": "durable stateful orchestration"},
                        ],
                    ),
                },
            )
            summary = query.get_mission_status(workspace, response["mission_id"])

            self.assertTrue(response["ok"])
            self.assertEqual(response["ingress_kind"], "orchestrator_mission")
            self.assertEqual(summary["mission_type"], "brainstorm_topic")
            self.assertEqual(summary["nodes"][0]["node_id"], "scope")
            self.assertEqual(summary["nodes"][0]["status"], "ready")

    def test_trial_mission_can_run_through_minimal_node_cycle(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            ingress = OrchestratorIngressService()
            response = ingress.create_mission(
                workspace,
                {
                    "template_id": "brainstorm_topic",
                    "template_inputs": build_agent_harness_brainstorm_inputs(
                        current_date="2026-03-21",
                        reference_items=[
                            {"title": "OpenAI Agents SDK", "url": "https://openai.github.io/openai-agents-python/", "note": "lightweight agents SDK"},
                            {"title": "Google ADK", "url": "https://google.github.io/adk-docs/", "note": "multi-language ADK"},
                        ],
                    ),
                },
            )
            mission_id = response["mission_id"]
            service = build_orchestrator_service_for_workspace(workspace)

            expected_order = ["scope", "scan_references", "generate_angles", "synthesize", "archive"]
            seen: list[str] = []
            for _ in expected_order:
                dispatched = service.dispatch_ready_nodes(mission_id, limit=1)
                self.assertEqual(len(dispatched), 1)
                branch = dispatched[0]
                seen.append(str(branch["node_id"]))
                service.record_branch_result(
                    mission_id,
                    branch["branch_id"],
                    ok=True,
                    result_ref=f"artifact:{branch['node_id']}",
                    result_payload={"summary": f"completed {branch['node_id']}"},
                )
                service.tick(mission_id)

            summary = service.summarize_mission(mission_id)
            self.assertEqual(seen, expected_order)
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(len(summary["branches"]), len(expected_order))


    def test_query_service_exposes_observation_windows(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            query = OrchestratorQueryService()
            service = build_orchestrator_service_for_workspace(workspace)
            mission = service.create_mission(
                mission_type="workflow",
                title="Observation mission",
                nodes=[
                    {
                        "node_id": "generate_angles",
                        "kind": "brainstorm",
                        "title": "Generate angles",
                        "runtime_plan": {
                            "worker_profile": "codex-debug",
                            "workflow_template": {
                                "template_id": "brainstorm.generate_angles",
                                "kind": "local_collaboration",
                                "roles": [{"role_id": "ideator", "capability_id": "brainstorm"}],
                                "steps": [{"step_id": "collect", "title": "Collect"}],
                            },
                        },
                    }
                ],
            )
            branch = service.dispatch_ready_nodes(mission.mission_id, limit=1)[0]
            branch_id = str(branch["branch_id"])
            session_id = str(branch["input_payload"].get("workflow_session_id") or "")
            self.assertTrue(session_id)

            overview = query.list_missions(workspace, limit=10)
            self.assertEqual(overview[0]["mission_id"], mission.mission_id)
            self.assertEqual(overview[0]["workflow_session_count"], 1)
            self.assertIn("mission_view", overview[0])
            self.assertEqual(overview[0]["mission_view"]["mission_id"], mission.mission_id)
            self.assertEqual(overview[0]["mission_view"]["workflow_session_count"], 1)

            branch_status = query.get_branch_status(workspace, branch_id)
            self.assertEqual(branch_status["branch_id"], branch_id)
            self.assertEqual(branch_status["workflow_session"]["session_id"], session_id)
            self.assertEqual(branch_status["runtime_debug"]["worker_profile"], "codex-debug")
            self.assertIn("branch_view", branch_status)
            self.assertEqual(branch_status["branch_view"]["branch_id"], branch_id)
            self.assertEqual(branch_status["branch_view"]["workflow_session_id"], session_id)

            session_status = query.get_workflow_session_status(workspace, session_id)
            self.assertEqual(session_status["template"]["template_id"], "brainstorm.generate_angles")
            self.assertEqual(session_status["shared_state"]["state"]["branch_id"], branch_id)
            self.assertIn("session_view", session_status)
            self.assertEqual(session_status["session_view"]["workflow_session_id"], session_id)
            self.assertEqual(session_status["session_view"]["active_step"], session_status["active_step"])

            recent_events = query.list_recent_events(workspace, mission_id=mission.mission_id, limit=5)
            self.assertTrue(any(item["event_type"] == "workflow_session_created" for item in recent_events))

            window = query.get_startup_observation_window(workspace, mission_limit=5, branch_limit=5, event_limit=5)
            self.assertIn("runtime", window)
            self.assertEqual(window["missions"][0]["mission_id"], mission.mission_id)
            self.assertEqual(window["active_branches"][0]["branch_id"], branch_id)
            self.assertIn("codex_debug", window)
            self.assertEqual(window["closure_signals"]["runtime_namespace"], "runtime_os")
            self.assertGreaterEqual(window["closure_signals"]["workflow_session_count"], 1)
            self.assertGreaterEqual(window["closure_signals"]["session_aware_branch_count"], 1)
            self.assertIn("workflow_ir_compiled", window["closure_signals"]["observed_event_types"])
            self.assertEqual(window["closure_signals"]["execution_boundary_samples"][0]["runtime_namespace"], "runtime_os")
            self.assertIn("mission_views", window)
            self.assertEqual(window["mission_views"][0]["mission_id"], mission.mission_id)
            self.assertIn("active_branch_views", window)
            self.assertEqual(window["active_branch_views"][0]["workflow_session_id"], session_id)
            contract = self._contract_payload(window)
            self.assertEqual(contract["port_namespace"], "domain_product_plane.v1")
            self.assertEqual(
                self._port_ids(contract),
                ["frontdoor", "mission_facade", "observation", "domain_pack"],
            )
            stable_evidence_keys = self._stable_evidence_keys(contract)
            self.assertIn("workflow_ir_compiled", stable_evidence_keys)
            self.assertIn("workflow_vm_executed", stable_evidence_keys)
            self.assertIn("workflow_session_count", stable_evidence_keys)

    def test_observe_cli_and_codex_window(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            usage_path = resolve_orchestrator_run_file(workspace, "agents_os_runtime_policy_codex_usage.json")
            usage_path.write_text(json.dumps({"window_hours": 5, "selected_at": ["2026-03-22 09:00:00", "2026-03-22 09:30:00"]}, ensure_ascii=False), encoding="utf-8")

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = observe_main(["codex", "--workspace", workspace, "--limit", "5"])
            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["selected_count"], 2)
            self.assertEqual(payload["selected_at"][-1], "2026-03-22 09:30:00")

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = observe_main(["window", "--workspace", workspace])
            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertIn("runtime", payload)
            self.assertIn("missions", payload)

if __name__ == "__main__":
    unittest.main()
