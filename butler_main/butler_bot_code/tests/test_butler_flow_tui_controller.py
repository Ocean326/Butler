from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.butler_flow.state import (  # noqa: E402
    FileRuntimeStateStore,
    flow_actions_path,
    flow_artifacts_path,
    flow_dir,
    flow_events_path,
    recovery_cursor_path,
    receipts_path,
    flow_state_path,
    flow_turns_path,
    handoffs_path,
    new_flow_state,
    write_json_atomic,
)
from butler_main.butler_flow.tui.controller import FlowTuiController  # noqa: E402


def _config_path(root: Path) -> str:
    path = root / "butler_flow_tui_config.json"
    path.write_text(json.dumps({"workspace_root": str(root)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _controller() -> FlowTuiController:
    return FlowTuiController(
        run_prompt_receipt_fn=lambda *args, **kwargs: None,
        event_callback=lambda event: None,
    )


def _write_flow_state(root: Path, *, flow_id: str, status: str, kind: str = "project_loop") -> Path:
    path = flow_dir(root, flow_id)
    state = new_flow_state(
        workflow_id=flow_id,
        workflow_kind=kind,
        workspace_root=str(root),
        goal="ship v1.1",
        guard_condition="verified",
        max_attempts=8,
        max_phase_attempts=4,
    )
    state["status"] = status
    write_json_atomic(flow_state_path(path), state)
    return path


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


class ButlerFlowTuiControllerTests(unittest.TestCase):
    def test_parse_command_resolves_registry_aliases(self) -> None:
        controller = _controller()

        parsed = controller.parse_command("/new ship multi flow console")
        self.assertEqual(parsed.name, "new")
        self.assertEqual(parsed.args, ["ship", "multi", "flow", "console"])

        parsed = controller.parse_command("/resume-run")
        self.assertEqual(parsed.name, "resume-flow")

        parsed = controller.parse_command("/retry-phase")
        self.assertEqual(parsed.name, "retry")

        parsed = controller.parse_command("/history")
        self.assertEqual(parsed.name, "history")

        parsed = controller.parse_command("/focus flow_123")
        self.assertEqual(parsed.name, "focus")
        self.assertEqual(parsed.args, ["flow_123"])

        parsed = controller.parse_command("/flows")
        self.assertEqual(parsed.name, "flows")

        with self.assertRaises(ValueError):
            controller.parse_command("/run ship")

    def test_command_suggestions_hide_legacy_navigation_aliases(self) -> None:
        controller = _controller()

        suggestions = controller.command_suggestions()

        self.assertIn("/new", suggestions)
        self.assertIn("/manage", suggestions)
        self.assertIn("/resume-flow", suggestions)
        self.assertIn("/resume-run", suggestions)
        self.assertNotIn("/history", suggestions)
        self.assertNotIn("/flows", suggestions)
        self.assertNotIn("/run <goal>", suggestions)

    def test_help_text_hides_legacy_navigation_aliases(self) -> None:
        controller = _controller()

        help_text = controller.help_text(config=None, flow_id="")

        self.assertIn("/manage [asset|instruction]", help_text)
        self.assertNotIn("/history", help_text)
        self.assertNotIn("/flows", help_text)

    def test_manage_chat_returns_decoded_payload(self) -> None:
        controller = _controller()

        class _StubApp:
            def __init__(self) -> None:
                self._stdout = io.StringIO()

            def manage_chat(self, args) -> None:
                del args
                self._stdout.write(json.dumps({"response": "ok", "manager_session_id": "thread-1"}))

        with mock.patch.object(controller, "_new_plain_app", return_value=_StubApp()):
            payload = controller.manage_chat(config=None, instruction="介绍一下")

        self.assertEqual(payload["response"], "ok")
        self.assertEqual(payload["manager_session_id"], "thread-1")

    def test_manage_flow_passes_structured_draft_payload(self) -> None:
        controller = _controller()

        class _StubApp:
            def __init__(self) -> None:
                self._stdout = io.StringIO()
                self.received_args = None

            def manage_flow(self, args) -> None:
                self.received_args = args
                self._stdout.write(json.dumps({"asset_key": "template:demo"}))

        stub = _StubApp()
        with mock.patch.object(controller, "_new_plain_app", return_value=stub):
            payload = controller.manage_flow(
                config=None,
                manage_target="template:new",
                instruction="commit",
                draft_payload={"goal": "ship demo"},
            )

        self.assertEqual(payload["asset_key"], "template:demo")
        self.assertEqual(stub.received_args.draft_payload["goal"], "ship demo")

    def test_running_flow_enables_only_running_operator_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            path = _write_flow_state(root, flow_id="flow_running", status="running")
            runtime_store = FileRuntimeStateStore(path)
            runtime_store.write_pid(os.getpid())
            runtime_store.write_watchdog_state(state="foreground", pid=os.getpid(), note="attached")
            runtime_store.write_run_state(
                run_id="flow_running",
                state="running",
                phase="imp",
                pid=os.getpid(),
                note="attempt 1 phase=imp",
            )

            available = {
                name: controller.command_availability(config=config, flow_id="flow_running", command_name=name).enabled
                for name in ("pause", "append", "resume-flow", "retry", "abort")
            }

            self.assertEqual(
                available,
                {
                    "pause": True,
                    "append": True,
                    "resume-flow": False,
                    "retry": False,
                    "abort": True,
                },
            )

    def test_paused_flow_enables_resume_append_retry_abort(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            _write_flow_state(root, flow_id="flow_paused", status="paused")

            available = {
                name: controller.command_availability(config=config, flow_id="flow_paused", command_name=name).enabled
                for name in ("pause", "append", "resume-flow", "retry", "abort")
            }

            self.assertEqual(
                available,
                {
                    "pause": False,
                    "append": True,
                    "resume-flow": True,
                    "retry": True,
                    "abort": True,
                },
            )

    def test_completed_flow_disables_operator_commands_but_keeps_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            _write_flow_state(root, flow_id="flow_done", status="completed")

            operator_names = [spec.name for spec in controller.available_operator_commands(config=config, flow_id="flow_done")]
            inspect_state = controller.command_availability(config=config, flow_id="flow_done", command_name="inspect")

            self.assertEqual(operator_names, [])
            self.assertTrue(inspect_state.enabled)

    def test_action_bar_reflects_focus_status_and_enabled_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            _write_flow_state(root, flow_id="flow_paused", status="paused")

            bar = controller.action_bar_text(config=config, flow_id="flow_paused")

            self.assertIn("focus=flow_paused", bar)
            self.assertIn("status=paused", bar)
            self.assertIn("actions=/append /resume-flow /retry /abort", bar)
            self.assertNotIn("/pause", bar)

    def test_pending_flow_uses_runtime_snapshot_as_effective_running_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            path = _write_flow_state(root, flow_id="flow_pending", status="pending")
            runtime_store = FileRuntimeStateStore(path)
            runtime_store.write_pid(os.getpid())
            runtime_store.write_watchdog_state(state="foreground", pid=os.getpid(), note="attached")
            runtime_store.write_run_state(
                run_id="flow_pending",
                state="running",
                phase="imp",
                pid=os.getpid(),
                note="attempt 1 phase=imp",
            )

            availability = controller.command_availability(config=config, flow_id="flow_pending", command_name="pause")
            context = controller.flow_context(config=config, flow_id="flow_pending")

            self.assertTrue(availability.enabled)
            self.assertEqual(context.status, "running")
            self.assertEqual(context.phase, "imp")

    def test_dead_runtime_snapshot_does_not_stay_false_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            path = _write_flow_state(root, flow_id="flow_stale", status="running")
            runtime_store = FileRuntimeStateStore(path)
            runtime_store.write_watchdog_state(state="foreground", pid=0, note="stale foreground")
            runtime_store.write_run_state(
                run_id="flow_stale",
                state="running",
                phase="imp",
                pid=0,
                note="stale run state",
            )

            context = controller.flow_context(config=config, flow_id="flow_stale")

            self.assertNotEqual(context.status, "running")
            self.assertEqual(context.status, "stale")

    def test_timeline_payload_reads_events_jsonl_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            path = _write_flow_state(root, flow_id="flow_events", status="running")
            _append_jsonl(
                flow_events_path(path),
                [
                    {
                        "event_id": "evt-1",
                        "kind": "run_started",
                        "flow_id": "flow_events",
                        "phase": "plan",
                        "attempt_no": 1,
                        "created_at": "2026-03-31 10:00:00",
                        "message": "flow run started",
                        "payload": {"turn_id": "turn-1"},
                    }
                ],
            )

            timeline = controller.timeline_payload(config=config, flow_id="flow_events")

            self.assertEqual(len(timeline), 1)
            self.assertEqual(timeline[0]["event_id"], "evt-1")
            self.assertEqual(timeline[0]["kind"], "run_started")

    def test_timeline_payload_synthesizes_and_backfills_legacy_flow_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            path = _write_flow_state(root, flow_id="flow_legacy", status="completed")
            _append_jsonl(
                flow_turns_path(path),
                [
                    {
                        "turn_id": "turn-1",
                        "flow_id": "flow_legacy",
                        "phase": "plan",
                        "attempt_no": 1,
                        "supervisor_decision": {"reason": "continue mainline flow execution"},
                        "decision": "COMPLETE",
                        "reason": "done",
                        "started_at": "2026-03-31 10:00:00",
                        "completed_at": "2026-03-31 10:01:00",
                    }
                ],
            )
            _append_jsonl(
                flow_actions_path(path),
                [
                    {
                        "action_id": "action-1",
                        "flow_id": "flow_legacy",
                        "action_type": "append_instruction",
                        "result_summary": "instruction appended for next supervisor turn",
                        "after_state": {"current_phase": "plan"},
                        "created_at": "2026-03-31 10:00:30",
                    }
                ],
            )
            flow_artifacts_path(path).write_text(
                json.dumps(
                    {
                        "flow_id": "flow_legacy",
                        "items": [
                            {
                                "artifact_ref": "artifact:1:plan",
                                "phase": "plan",
                                "attempt_no": 1,
                                "created_at": "2026-03-31 10:01:00",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            timeline = controller.timeline_payload(config=config, flow_id="flow_legacy")
            persisted = [json.loads(line) for line in flow_events_path(path).read_text(encoding="utf-8").splitlines() if line.strip()]

            self.assertGreaterEqual(len(timeline), 4)
            self.assertEqual(timeline[0]["kind"], "run_started")
            self.assertIn("judge_result", [row["kind"] for row in timeline])
            self.assertIn("artifact_registered", [row["kind"] for row in timeline])
            self.assertIn("run_completed", [row["kind"] for row in timeline])
            self.assertEqual(len(persisted), len(timeline))

    def test_timeline_payload_includes_supervisor_input_output_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            path = _write_flow_state(root, flow_id="flow_supervisor_io", status="running")
            _append_jsonl(
                flow_turns_path(path),
                [
                    {
                        "turn_id": "turn-1",
                        "flow_id": "flow_supervisor_io",
                        "phase": "plan",
                        "attempt_no": 1,
                        "supervisor_decision": {
                            "decision": "execute",
                            "next_action": "run_executor",
                            "turn_kind": "execute",
                            "active_role_id": "planner",
                            "session_mode": "warm",
                            "load_profile": "compact",
                            "instruction": "focus on the remaining blockers",
                        },
                        "decision": "ADVANCE",
                        "reason": "go",
                        "started_at": "2026-03-31 10:00:00",
                        "completed_at": "2026-03-31 10:01:00",
                    }
                ],
            )

            timeline = controller.timeline_payload(config=config, flow_id="flow_supervisor_io")

            kinds = {str(row.get("kind") or "") for row in timeline}
            self.assertIn("supervisor_input", kinds)
            self.assertIn("supervisor_output", kinds)
            input_event = next(row for row in timeline if str(row.get("kind") or "") == "supervisor_input")
            output_event = next(row for row in timeline if str(row.get("kind") or "") == "supervisor_output")
            self.assertEqual(input_event.get("lane"), "supervisor")
            self.assertEqual(input_event.get("family"), "input")
            self.assertEqual(output_event.get("lane"), "supervisor")
            self.assertEqual(output_event.get("family"), "output")
            self.assertEqual(dict(input_event.get("payload") or {}).get("decision", {}).get("active_role_id"), "planner")
            self.assertEqual(dict(output_event.get("payload") or {}).get("decision", {}).get("active_role_id"), "planner")

    def test_single_flow_payload_includes_summary_and_phase_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            path = _write_flow_state(root, flow_id="flow_summary", status="running")
            runtime_store = FileRuntimeStateStore(path)
            runtime_store.write_pid(os.getpid())
            runtime_store.write_watchdog_state(state="foreground", pid=os.getpid(), note="attached")
            runtime_store.write_run_state(
                run_id="flow_summary",
                state="running",
                phase="review",
                pid=os.getpid(),
                note="attempt 2 phase=review",
            )
            state = json.loads(flow_state_path(path).read_text(encoding="utf-8"))
            state["current_phase"] = "review"
            state["active_role_id"] = "planner"
            state["codex_session_id"] = "thread-summary"
            state["phase_history"] = [
                {
                    "at": "2026-03-31 10:00:00",
                    "attempt_no": 1,
                    "phase": "plan",
                    "decision": {"decision": "ADVANCE", "reason": "plan done", "completion_summary": "plan done"},
                },
                {
                    "at": "2026-03-31 10:05:00",
                    "attempt_no": 2,
                    "phase": "imp",
                    "decision": {"decision": "ADVANCE", "reason": "imp done", "completion_summary": "imp done"},
                },
            ]
            write_json_atomic(flow_state_path(path), state)
            _append_jsonl(
                receipts_path(path),
                [
                    {
                        "receipt_id": "receipt-2",
                        "receipt_kind": "turn_acceptance",
                        "flow_id": "flow_summary",
                        "task_contract_id": "task_contract_flow_summary",
                        "status": "accepted",
                        "phase": "imp",
                        "attempt_no": 2,
                        "active_role_id": "planner",
                        "summary": "imp done",
                        "created_at": "2026-03-31 10:05:00",
                    }
                ],
            )
            write_json_atomic(
                recovery_cursor_path(path),
                {
                    "flow_id": "flow_summary",
                    "task_contract_id": "task_contract_flow_summary",
                    "latest_accepted_receipt_id": "receipt-2",
                    "latest_artifact_ref": "",
                    "current_phase": "review",
                    "active_role_id": "planner",
                    "codex_session_id": "thread-summary",
                    "recovery_state": "resume_existing_session",
                    "updated_at": "2026-03-31 10:05:01",
                },
            )

            payload = controller.single_flow_payload(config=config, flow_id="flow_summary")

            self.assertEqual(payload["surface_meta"]["projection_kind"], "run_console")
            self.assertEqual(payload["summary"]["effective_status"], "running")
            self.assertEqual(payload["summary"]["effective_phase"], "review")
            self.assertEqual(payload["summary"]["task_contract_id"], "task_contract_flow_summary")
            self.assertEqual(payload["summary"]["latest_receipt_summary"]["receipt_kind"], "turn_acceptance")
            self.assertEqual(payload["summary"]["recovery_state"], "resume_existing_session")
            self.assertEqual(dict(payload.get("task_contract_summary") or {}).get("goal"), "ship v1.1")
            self.assertEqual(payload["flow_console"]["summary"], payload["summary"])
            self.assertEqual(payload["mission_console"]["task_contract_id"], "task_contract_flow_summary")
            self.assertEqual(payload["mission_console"]["derived_responsibility_graph"]["graph_kind"], "derived_responsibility_graph")
            self.assertEqual(payload["governance_summary"]["ledger_owner"], "receipts.jsonl")
            self.assertEqual(payload["recovery_cursor"]["latest_accepted_receipt_id"], "receipt-2")
            self.assertEqual(payload["recovery_cursor"]["recovery_state"], "resume_existing_session")
            self.assertEqual(len(payload["step_history"]), 2)
            self.assertEqual(payload["step_history"][0]["phase"], "plan")
            self.assertEqual(payload["step_history"][1]["decision"], "ADVANCE")

    def test_single_flow_payload_summary_enriches_operator_and_role_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            path = _write_flow_state(root, flow_id="flow_enriched", status="running")
            state = json.loads(flow_state_path(path).read_text(encoding="utf-8"))
            state["approval_state"] = "operator_required"
            state["execution_mode"] = "medium"
            state["session_strategy"] = "role_bound"
            state["active_role_id"] = "planner"
            state["latest_judge_decision"] = {"decision": "RETRY"}
            state["last_operator_action"] = {"action_type": "pause"}
            write_json_atomic(flow_state_path(path), state)
            _append_jsonl(
                handoffs_path(path),
                [
                    {
                        "handoff_id": "handoff-1",
                        "flow_id": "flow_enriched",
                        "from_role_id": "planner",
                        "to_role_id": "implementer",
                        "status": "pending",
                        "summary": "plan complete",
                        "created_at": "2026-03-31 10:00:00",
                    }
                ],
            )

            payload = controller.single_flow_payload(config=config, flow_id="flow_enriched")

            self.assertEqual(payload["summary"]["approval_state"], "operator_required")
            self.assertEqual(payload["summary"]["execution_mode"], "medium")
            self.assertEqual(payload["summary"]["session_strategy"], "role_bound")
            self.assertEqual(payload["summary"]["active_role_id"], "planner")
            self.assertEqual(payload["summary"]["latest_handoff_summary"]["handoff_id"], "handoff-1")

    def test_single_flow_payload_splits_surface_events_by_view(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            path = _write_flow_state(root, flow_id="flow_split", status="running")
            _append_jsonl(
                flow_events_path(path),
                [
                    {
                        "event_id": "evt-system",
                        "kind": "run_started",
                        "lane": "system",
                        "family": "run",
                        "flow_id": "flow_split",
                        "phase": "plan",
                        "attempt_no": 1,
                        "created_at": "2026-04-03 10:00:00",
                        "message": "flow started",
                    },
                    {
                        "event_id": "evt-supervisor",
                        "kind": "supervisor_output",
                        "lane": "supervisor",
                        "family": "output",
                        "flow_id": "flow_split",
                        "phase": "plan",
                        "attempt_no": 1,
                        "created_at": "2026-04-03 10:00:01",
                        "message": "supervisor summary",
                    },
                    {
                        "event_id": "evt-workflow",
                        "kind": "artifact_registered",
                        "lane": "workflow",
                        "family": "artifact",
                        "flow_id": "flow_split",
                        "phase": "imp",
                        "attempt_no": 1,
                        "created_at": "2026-04-03 10:00:02",
                        "message": "artifact:1:imp",
                    },
                ],
            )

            payload = controller.single_flow_payload(config=config, flow_id="flow_split")
            supervisor_events = list(dict(payload.get("supervisor_view") or {}).get("events") or [])
            workflow_events = list(dict(payload.get("workflow_view") or {}).get("events") or [])

            self.assertEqual([row["event_id"] for row in supervisor_events], ["evt-supervisor"])
            self.assertEqual([row["event_id"] for row in workflow_events], ["evt-workflow"])
            self.assertEqual(payload["navigator_summary"], payload["summary"])

    def test_workspace_payload_enriches_flow_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            path = _write_flow_state(root, flow_id="flow_workspace", status="running")
            state = json.loads(flow_state_path(path).read_text(encoding="utf-8"))
            state["approval_state"] = "operator_required"
            state["execution_mode"] = "medium"
            state["session_strategy"] = "role_bound"
            state["active_role_id"] = "planner"
            state["latest_judge_decision"] = {"decision": "RETRY"}
            state["last_operator_action"] = {"action_type": "pause"}
            write_json_atomic(flow_state_path(path), state)
            _append_jsonl(
                handoffs_path(path),
                [
                    {
                        "handoff_id": "handoff-2",
                        "flow_id": "flow_workspace",
                        "from_role_id": "planner",
                        "to_role_id": "implementer",
                        "status": "pending",
                        "summary": "handoff ready",
                        "created_at": "2026-03-31 10:00:00",
                    }
                ],
            )

            payload = controller.workspace_payload(config=config)
            rows = list(dict(payload.get("flows") or {}).get("items") or [])
            row = next((item for item in rows if str(item.get("flow_id") or "") == "flow_workspace"), {})

            self.assertEqual(dict(payload.get("surface_meta") or {}).get("projection_kind"), "mission_index")
            self.assertEqual(row.get("approval_state"), "operator_required")
            self.assertEqual(row.get("execution_mode"), "medium")
            self.assertEqual(row.get("session_strategy"), "role_bound")
            self.assertEqual(row.get("active_role_id"), "planner")
            self.assertEqual(row.get("goal"), "ship v1.1")
            self.assertEqual(dict(row.get("task_contract_summary") or {}).get("task_contract_id"), "task_contract_flow_workspace")
            self.assertEqual(
                dict(dict(row.get("task_contract_summary") or {}).get("acceptance_summary") or {}).get("guard_condition"),
                "verified",
            )
            self.assertEqual(dict(row.get("latest_handoff_summary") or {}).get("handoff_id"), "handoff-2")
            self.assertEqual(dict(row.get("latest_judge_decision") or {}).get("decision"), "RETRY")
            self.assertEqual(dict(row.get("latest_operator_action") or {}).get("action_type"), "pause")

    def test_manage_center_payload_surfaces_contract_studio_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            template_path = (
                root
                / "butler_main"
                / "butler_bot_code"
                / "assets"
                / "flows"
                / "templates"
                / "contract_studio_demo.json"
            )
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text(
                json.dumps(
                    {
                        "flow_id": "contract_studio_demo",
                        "label": "Contract Studio Demo",
                        "workflow_kind": "managed_flow",
                        "goal": "shape contract inputs",
                        "guard_condition": "reviewed",
                        "control_profile": {"packet_size": "small"},
                        "review_checklist": ["review contract"],
                        "role_guidance": {"manager_notes": "edit the contract before launch"},
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            payload = controller.manage_center_payload(config=config)

            self.assertEqual(payload["surface_meta"]["projection_kind"], "contract_studio")
            self.assertEqual(payload["contract_studio"]["goal"], "shape contract inputs")
            self.assertEqual(payload["role_guidance"]["manager_notes"], "edit the contract before launch")
            self.assertEqual(payload["review_checklist"], ["review contract"])

    def test_operator_rail_payload_exposes_approval_and_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            path = _write_flow_state(root, flow_id="flow_rail", status="paused")
            state = json.loads(flow_state_path(path).read_text(encoding="utf-8"))
            state["approval_state"] = "operator_required"
            state["pending_codex_prompt"] = "review and continue"
            state["latest_supervisor_decision"] = {"decision": "ask_operator"}
            state["latest_judge_decision"] = {"decision": "RETRY"}
            state["last_operator_action"] = {"action_type": "pause"}
            write_json_atomic(flow_state_path(path), state)

            rail = controller.operator_rail_payload(config=config, flow_id="flow_rail")

            self.assertEqual(rail["approval_state"], "operator_required")
            self.assertEqual(rail["pending_codex_prompt"], "review and continue")
            self.assertEqual(dict(rail["latest_judge_decision"]).get("decision"), "RETRY")
            self.assertEqual(dict(rail["latest_operator_action"]).get("action_type"), "pause")
            self.assertEqual(dict(rail["latest_supervisor_decision"]).get("decision"), "ask_operator")

    def test_role_strip_payload_includes_roles_and_handoffs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            path = _write_flow_state(root, flow_id="flow_roles", status="running")
            state = json.loads(flow_state_path(path).read_text(encoding="utf-8"))
            state["execution_mode"] = "medium"
            state["session_strategy"] = "role_bound"
            state["active_role_id"] = "planner"
            state["role_sessions"] = {
                "planner": {"role_id": "planner", "session_id": "sess-1"},
                "reviewer": {"role_id": "reviewer", "session_id": "sess-2"},
            }
            state["latest_role_handoffs"] = {"reviewer": "handoff-3"}
            write_json_atomic(flow_state_path(path), state)
            _append_jsonl(
                handoffs_path(path),
                [
                    {
                        "handoff_id": "handoff-3",
                        "flow_id": "flow_roles",
                        "from_role_id": "planner",
                        "to_role_id": "reviewer",
                        "status": "pending",
                        "summary": "ready for review",
                        "created_at": "2026-03-31 10:02:00",
                    }
                ],
            )

            payload = controller.role_strip_payload(config=config, flow_id="flow_roles")

            self.assertEqual(payload["active_role_id"], "planner")
            self.assertEqual(payload["execution_mode"], "medium")
            self.assertEqual(payload["session_strategy"], "role_bound")
            self.assertEqual(dict(payload.get("latest_handoff_summary") or {}).get("handoff_id"), "handoff-3")
            self.assertEqual(len(list(payload.get("roles") or [])), 2)
            chips = {str(item.get("role_id") or ""): str(item.get("state") or "") for item in list(payload.get("role_chips") or [])}
            self.assertEqual(chips.get("planner"), "active")
            self.assertEqual(chips.get("reviewer"), "receiving_handoff")

    def test_latest_handoff_summary_prefers_pending_over_newer_consumed_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            path = _write_flow_state(root, flow_id="flow_pending_first", status="running")
            state = json.loads(flow_state_path(path).read_text(encoding="utf-8"))
            state["active_role_id"] = "planner"
            state["role_sessions"] = {
                "planner": {"role_id": "planner", "session_id": "sess-1"},
                "reviewer": {"role_id": "reviewer", "session_id": "sess-2"},
            }
            write_json_atomic(flow_state_path(path), state)
            _append_jsonl(
                handoffs_path(path),
                [
                    {
                        "handoff_id": "handoff-pending",
                        "flow_id": "flow_pending_first",
                        "from_role_id": "planner",
                        "to_role_id": "reviewer",
                        "status": "pending",
                        "summary": "waiting for reviewer",
                        "created_at": "2026-03-31 10:01:00",
                    },
                    {
                        "handoff_id": "handoff-old",
                        "flow_id": "flow_pending_first",
                        "from_role_id": "researcher",
                        "to_role_id": "planner",
                        "status": "consumed",
                        "summary": "consumed later",
                        "created_at": "2026-03-31 10:00:00",
                        "consumed_at": "2026-03-31 10:05:00",
                    },
                ],
            )

            payload = controller.role_strip_payload(config=config, flow_id="flow_pending_first")

            self.assertEqual(dict(payload.get("latest_handoff_summary") or {}).get("handoff_id"), "handoff-pending")

    def test_detail_payload_exposes_structured_multi_agent_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            path = _write_flow_state(root, flow_id="flow_detail_roles", status="running")
            state = json.loads(flow_state_path(path).read_text(encoding="utf-8"))
            state["active_role_id"] = "planner"
            state["role_sessions"] = {
                "planner": {"role_id": "planner", "session_id": "sess-1"},
                "reviewer": {"role_id": "reviewer", "session_id": "sess-2"},
            }
            write_json_atomic(flow_state_path(path), state)
            _append_jsonl(
                handoffs_path(path),
                [
                    {
                        "handoff_id": "handoff-roles",
                        "flow_id": "flow_detail_roles",
                        "from_role_id": "planner",
                        "to_role_id": "reviewer",
                        "status": "pending",
                        "summary": "ready for review",
                        "created_at": "2026-03-31 10:02:00",
                        "source_phase": "build",
                        "target_phase": "review",
                    }
                ],
            )

            payload = controller.detail_payload(config=config, flow_id="flow_detail_roles")

            multi_agent = dict(payload.get("multi_agent") or {})
            self.assertEqual(multi_agent.get("active_role_id"), "planner")
            self.assertEqual(len(list(multi_agent.get("role_chips") or [])), 2)
            self.assertEqual(len(list(multi_agent.get("pending_handoffs") or [])), 1)
            self.assertEqual(dict(multi_agent.get("latest_handoff_summary") or {}).get("handoff_id"), "handoff-roles")

    def test_timeline_payload_unifies_handoffs_and_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            controller = _controller()
            path = _write_flow_state(root, flow_id="flow_timeline", status="running")
            _append_jsonl(
                flow_actions_path(path),
                [
                    {
                        "action_id": "action-1",
                        "flow_id": "flow_timeline",
                        "action_type": "append_instruction",
                        "result_summary": "instruction appended",
                        "after_state": {"current_phase": "plan"},
                        "created_at": "2026-03-31 10:00:10",
                    }
                ],
            )
            _append_jsonl(
                flow_turns_path(path),
                [
                    {
                        "turn_id": "turn-1",
                        "flow_id": "flow_timeline",
                        "phase": "plan",
                        "attempt_no": 1,
                        "decision": "COMPLETE",
                        "reason": "done",
                        "started_at": "2026-03-31 10:00:00",
                        "completed_at": "2026-03-31 10:00:20",
                    }
                ],
            )
            _append_jsonl(
                handoffs_path(path),
                [
                    {
                        "handoff_id": "handoff-4",
                        "flow_id": "flow_timeline",
                        "from_role_id": "planner",
                        "to_role_id": "implementer",
                        "status": "pending",
                        "summary": "handoff created",
                        "created_at": "2026-03-31 10:00:05",
                    },
                    {
                        "handoff_id": "handoff-4",
                        "flow_id": "flow_timeline",
                        "from_role_id": "planner",
                        "to_role_id": "implementer",
                        "status": "consumed",
                        "summary": "handoff consumed",
                        "created_at": "2026-03-31 10:00:05",
                        "consumed_at": "2026-03-31 10:00:30",
                    },
                ],
            )

            timeline = controller.timeline_payload(config=config, flow_id="flow_timeline")
            kinds = {str(row.get("kind") or "") for row in timeline}

            self.assertIn("operator_action_applied", kinds)
            self.assertIn("judge_result", kinds)
            self.assertIn("role_handoff_created", kinds)
            self.assertIn("role_handoff_consumed", kinds)

    def test_manage_flow_returns_json_payload(self) -> None:
        controller = _controller()
        expected = {"flow_id": "flow_managed", "workflow_kind": "managed_flow"}
        with mock.patch.object(FlowTuiController, "_new_plain_app") as mocked_app_factory:
            mocked_app = mocked_app_factory.return_value
            mocked_app.manage_flow.side_effect = lambda args: mocked_app._stdout.write(json.dumps(expected, ensure_ascii=False))
            mocked_app._stdout = io.StringIO()
            payload = controller.manage_flow(config="demo.json", manage_target="new", instruction="shape it")
        self.assertEqual(payload["flow_id"], "flow_managed")
        self.assertEqual(payload["workflow_kind"], "managed_flow")


if __name__ == "__main__":
    unittest.main()
