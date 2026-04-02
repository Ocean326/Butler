from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

try:  # pragma: no cover - fallback module layout
    from butler_main.butler_flow import flow_shell as flow_shell  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - fallback module layout
    try:
        from butler_main.butler_flow import shell as flow_shell  # noqa: E402
    except ModuleNotFoundError:
        from butler_main.butler_flow import app as flow_shell  # noqa: E402
from butler_main.butler_flow import cli as flow_cli  # noqa: E402

from butler_main.butler_flow.compiler import build_flow_board, build_role_board, build_turn_task_packet, compile_packet  # noqa: E402
from butler_main.butler_flow.manage_agent import build_manage_chat_prompt, normalize_manage_chat_draft_payload, normalize_manage_chat_result, select_manage_chat_skill  # noqa: E402
from butler_main.runtime_os.process_runtime import ExecutionReceipt  # noqa: E402
from butler_main.butler_flow.state import FileRuntimeStateStore, ensure_flow_sidecars, manage_session_dir  # noqa: E402
from butler_main.butler_flow.role_runtime import current_role_prompt  # noqa: E402
from butler_main.butler_flow import runtime as flow_runtime  # noqa: E402


FlowApp = getattr(flow_shell, "ButlerFlowApp", getattr(flow_shell, "WorkflowShellApp"))
SINGLE_GOAL_KIND = getattr(flow_shell, "SINGLE_GOAL_KIND", "single_goal")
PROJECT_LOOP_KIND = getattr(flow_shell, "PROJECT_LOOP_KIND", "project_loop")
MANAGED_FLOW_KIND = getattr(flow_shell, "MANAGED_FLOW_KIND", "managed_flow")
SINGLE_GOAL_PHASE = getattr(flow_shell, "SINGLE_GOAL_PHASE", "free")
BUTLER_FLOW_VERSION = getattr(flow_shell, "BUTLER_FLOW_VERSION", "1.1.0")
_BUILD_FLOW_ROOT = getattr(
    flow_shell,
    "build_butler_flow_root",
    getattr(flow_shell, "build_flow_root", getattr(flow_shell, "build_workflow_shell_root", None)),
)
_NEW_FLOW_STATE = getattr(flow_shell, "_new_flow_state", getattr(flow_shell, "_new_workflow_state", None))
_WRITE_JSON_ATOMIC = getattr(flow_shell, "_write_json_atomic", None)


def _config_path(root: Path, payload: dict | None = None) -> str:
    path = root / "butler_flow_test_config.json"
    base = {"workspace_root": str(root)}
    if isinstance(payload, dict):
        base.update(payload)
    path.write_text(json.dumps(base, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _receipt(*, status: str = "completed", text: str = "", metadata: dict | None = None, agent_id: str = "") -> ExecutionReceipt:
    return ExecutionReceipt(status=status, summary=text, metadata=dict(metadata or {}), agent_id=agent_id)


class _ReceiptRunner:
    def __init__(self, responses: list):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, prompt, workspace, timeout, cfg, runtime_request, *, stream=False, on_segment=None, on_event=None):
        self.calls.append(
            {
                "prompt": prompt,
                "workspace": workspace,
                "timeout": timeout,
                "cfg": dict(cfg or {}),
                "runtime_request": dict(runtime_request or {}),
                "stream": bool(stream),
            }
        )
        response = self._responses.pop(0)
        if callable(response):
            return response(prompt, workspace, timeout, cfg, runtime_request, stream=stream, on_segment=on_segment, on_event=on_event)
        return response


class ButlerFlowTests(unittest.TestCase):
    def _app(self, runner: _ReceiptRunner, *, input_value: str = "", event_callback=None) -> FlowApp:
        return FlowApp(
            run_prompt_receipt_fn=runner,
            input_fn=lambda prompt: input_value,
            stdout=StringIO(),
            stderr=StringIO(),
            event_callback=event_callback,
        )

    def _flow_dirs(self, root: Path) -> list[Path]:
        if _BUILD_FLOW_ROOT is None:
            raise AssertionError("build_butler_flow_root/build_flow_root must be provided by butler_flow")
        flow_root = _BUILD_FLOW_ROOT(root)
        if not flow_root.exists():
            return []
        return sorted(path for path in flow_root.iterdir() if path.is_dir())

    def _flow_state(self, flow_dir: Path) -> dict:
        return json.loads((flow_dir / "workflow_state.json").read_text(encoding="utf-8"))

    def _read_jsonl(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            text = str(line or "").strip()
            if not text:
                continue
            rows.append(json.loads(text))
        return rows

    def _read_json(self, path: Path) -> dict | list:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_manage_chat_prompt_includes_role_skill_and_asset_notes(self) -> None:
        prompt = build_manage_chat_prompt(
            workspace_root="/tmp/demo",
            manage_target="template:academic_paper_review_v1",
            asset_kind="template",
            instruction="基于这个模板继续整理",
            selected_skill="template_update",
            manager_role_text="ROLE_PROMPT",
            skill_prompt_text="SKILL_PROMPT",
            asset_manager_notes="ASSET_MANAGER_NOTES",
        )
        self.assertIn("ROLE_PROMPT", prompt)
        self.assertIn("SKILL_PROMPT", prompt)
        self.assertIn("ASSET_MANAGER_NOTES", prompt)
        self.assertIn('"manager_stage"', prompt)
        self.assertIn('"confirmation_scope"', prompt)

    def test_manage_chat_skill_defaults_new_flow_request_to_template_first(self) -> None:
        skill = select_manage_chat_skill(
            manage_target="",
            asset_kind="workspace",
            instruction="按需求创建一个新的 pending flow，用于论文写作",
        )
        self.assertEqual(skill, "template_select_or_create")

    def test_manage_chat_result_preserves_confirmation_fields(self) -> None:
        payload = normalize_manage_chat_result(
            {
                "response": "我建议先确认模板，再创建 flow。",
                "manager_stage": "template_confirm",
                "active_skill": "template_select_or_create",
                "confirmation_scope": "template",
                "confirmation_prompt": "如果你认可这个模板方案，我就先创建/更新模板。",
                "action": "manage_flow",
                "action_ready": True,
                "action_manage_target": "template:new",
                "action_instruction": "创建一个研究写作模板，并同步补齐 supervisor 方向说明",
            },
            manage_target="template:academic_paper_review_v1",
        )
        self.assertEqual(payload["action"], "manage_flow")
        self.assertTrue(payload["action_ready"])
        self.assertEqual(payload["manager_stage"], "template_confirm")
        self.assertEqual(payload["active_skill"], "template_select_or_create")
        self.assertEqual(payload["confirmation_scope"], "template")
        self.assertIn("模板方案", payload["confirmation_prompt"])

    def test_manage_chat_draft_normalizes_control_profile(self) -> None:
        draft = normalize_manage_chat_draft_payload(
            {
                "workflow_kind": "managed_flow",
                "control_profile": {
                    "task_archetype": "repo_delivery",
                    "packet_size": "large",
                    "evidence_level": "strict",
                    "gate_cadence": "phase",
                    "repo_binding_policy": "explicit_contract",
                    "repo_contract_paths": ["docs/project-map/00_current_baseline.md"],
                },
            }
        )
        self.assertEqual(draft["control_profile"]["task_archetype"], "repo_delivery")
        self.assertEqual(draft["control_profile"]["packet_size"], "large")
        self.assertEqual(draft["control_profile"]["repo_binding_policy"], "explicit")
        self.assertEqual(draft["control_profile"]["repo_contract_paths"], ["docs/project-map/00_current_baseline.md"])

    def test_manage_chat_draft_maps_inherit_workspace_to_disabled(self) -> None:
        draft = normalize_manage_chat_draft_payload(
            {
                "workflow_kind": "managed_flow",
                "control_profile": {
                    "task_archetype": "repo_delivery",
                    "repo_binding_policy": "inherit_workspace",
                },
            }
        )
        self.assertEqual(draft["control_profile"]["repo_binding_policy"], "disabled")

    def test_manage_chat_requires_existing_pending_action_for_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(
                        text=json.dumps(
                            {
                                "response": "我先整理出模板草稿，等你确认后再创建。",
                                "summary": "template draft ready",
                                "manage_target": "template:new",
                                "manager_stage": "template_confirm",
                                "active_skill": "template_select_or_create",
                                "confirmation_scope": "template",
                                "confirmation_prompt": "如果你认可这版模板草稿，我就创建它。",
                                "action": "manage_flow",
                                "action_ready": True,
                                "action_manage_target": "template:new",
                                "action_instruction": "create template from approved draft",
                                "draft": {
                                    "manage_target": "template:new",
                                    "asset_kind": "template",
                                    "label": "Paper Writer",
                                    "workflow_kind": "managed_flow",
                                    "goal": "write a KDD paper section",
                                    "guard_condition": "section is reviewable",
                                    "phase_plan": [{"phase_id": "plan", "title": "Plan", "objective": "plan", "done_when": "done", "retry_phase_id": "plan", "fallback_phase_id": "plan", "next_phase_id": ""}],
                                    "supervisor_profile": {"archetype": "research_editor"},
                                    "run_brief": "Deliver a reusable writing flow",
                                },
                            },
                            ensure_ascii=False,
                        ),
                        metadata={"external_session": {"provider": "codex", "thread_id": "manager-thread-1", "resume_capable": True}},
                        agent_id="butler_flow.manager_chat",
                    ),
                    _receipt(
                        text=json.dumps(
                            {
                                "response": "收到，按刚才确认的模板执行。",
                                "summary": "confirmed",
                                "manager_stage": "done",
                                "active_skill": "flow_create_or_update",
                            },
                            ensure_ascii=False,
                        ),
                        metadata={"external_session": {"provider": "codex", "thread_id": "manager-thread-1", "resume_capable": True}},
                        agent_id="butler_flow.manager_chat",
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch("butler_main.butler_flow.manage_agent.cli_provider_available", return_value=True):
                app.manage_chat(
                    argparse.Namespace(
                        command="manage-chat",
                        config=config,
                        json=True,
                        manage="",
                        instruction="帮我设计一个论文写作模板",
                        manager_session_id="",
                    )
                )
                first_payload = json.loads(app._stdout.getvalue())
                second_app = self._app(runner)
                second_app.manage_chat(
                    argparse.Namespace(
                        command="manage-chat",
                        config=config,
                        json=True,
                        manage="",
                        instruction="确认",
                        manager_session_id="manager-thread-1",
                    )
                )
                second_payload = json.loads(second_app._stdout.getvalue())

            self.assertFalse(first_payload["action_ready"])
            self.assertIn("template:new", first_payload["draft_summary"])
            self.assertIn("模板草稿", first_payload["pending_action_preview"])
            self.assertTrue(second_payload["action_ready"])
            self.assertEqual(second_payload["action_manage_target"], "template:new")
            self.assertEqual(second_payload["action_draft"]["label"], "Paper Writer")
            self.assertEqual(runner.calls[0]["runtime_request"]["execution_context"], "isolated")
            session_root = manage_session_dir(root, "manager-thread-1")
            self.assertTrue((session_root / "session.json").exists())
            self.assertTrue((session_root / "draft.json").exists())
            self.assertTrue((session_root / "pending_action.json").exists())

    def test_project_loop_defaults_to_medium_role_bound_control_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = self._app(_ReceiptRunner([]))
            args = self._new_args(
                config=config,
                kind=PROJECT_LOOP_KIND,
                launch_mode="flow",
                execution_level="",
                catalog_flow_id="project_loop",
                goal="ship a desktop feature",
                guard_condition="verified",
            )
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                prepared = app.prepare_new_flow(args)
            state = prepared.flow_state
            self.assertEqual(state.get("execution_mode"), "medium")
            self.assertEqual(state.get("session_strategy"), "role_bound")
            self.assertEqual(state.get("control_profile", {}).get("packet_size"), "medium")
            self.assertEqual(state.get("control_profile", {}).get("gate_cadence"), "phase")
            self.assertEqual(state.get("control_profile", {}).get("repo_binding_policy"), "disabled")

    def test_operator_actions_can_tune_control_profile_and_repo_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flow_id = "flow_control_profile"
            flow_dir = root / "butler_main" / "butler_bot_code" / "assets" / "flows" / "instances" / flow_id
            flow_state = _NEW_FLOW_STATE(
                workflow_id=flow_id,
                workflow_kind=PROJECT_LOOP_KIND,
                workspace_root=str(root),
                goal="ship feature",
                guard_condition="verified",
                max_attempts=0,
                max_phase_attempts=6,
            )
            flow_state["status"] = "running"
            ensure_flow_sidecars(flow_dir, flow_state)
            runtime = self._app(_ReceiptRunner([]))._runtime
            receipt = runtime.apply_operator_action(
                cfg={"workspace_root": str(root)},
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                action_type="shrink_packet",
                payload={},
            )
            self.assertEqual(receipt["action_type"], "shrink_packet")
            self.assertEqual(flow_state["control_profile"]["packet_size"], "small")
            self.assertTrue(flow_state["control_profile"]["force_gate_next_turn"])
            runtime.apply_operator_action(
                cfg={"workspace_root": str(root)},
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                action_type="bind_repo_contract",
                payload={"repo_contract_path": "AGENTS.md"},
            )
            self.assertEqual(flow_state["control_profile"]["repo_binding_policy"], "explicit")
            self.assertIn("AGENTS.md", flow_state["control_profile"]["repo_contract_paths"])
            runtime.apply_operator_action(
                cfg={"workspace_root": str(root)},
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                action_type="force_doctor",
                payload={},
            )
            self.assertTrue(flow_state["control_profile"]["force_doctor_next_turn"])

    def _new_args(
        self,
        *,
        config: str,
        kind: str = SINGLE_GOAL_KIND,
        goal: str = "ship it",
        guard_condition: str = "verified",
        launch_mode: str = "single",
        execution_level: str = "simple",
        catalog_flow_id: str = "project_loop",
    ):
        return argparse.Namespace(
            command="new",
            config=config,
            kind=kind,
            launch_mode=launch_mode,
            execution_level=execution_level,
            catalog_flow_id=catalog_flow_id,
            goal=goal,
            guard_condition=guard_condition,
            max_attempts=None,
            max_phase_attempts=None,
            no_stream=True,
        )

    def _run_args(self, *, config: str, kind: str = SINGLE_GOAL_KIND, goal: str = "ship it", guard_condition: str = "verified"):
        return self._new_args(config=config, kind=kind, goal=goal, guard_condition=guard_condition)

    def test_single_goal_first_attempt_extracts_thread_id_and_persists_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(
                        text="implemented",
                        metadata={"external_session": {"provider": "codex", "thread_id": "thread-1", "resume_capable": True}},
                        agent_id="butler_flow.codex_executor",
                    ),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        ),
                        agent_id="butler_flow.cursor_judge",
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._new_args(config=config))
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            self.assertEqual(state["codex_session_id"], "thread-1")
            self.assertEqual(state["current_phase"], SINGLE_GOAL_PHASE)
            self.assertEqual(state["attempt_count"], 1)
            self.assertEqual(state["status"], "completed")
            self.assertTrue((flow_dir / "run_state.json").exists())
            self.assertTrue((flow_dir / "watchdog_state.json").exists())
            self.assertTrue((flow_dir / "drafts" / "attempt_0001.json").exists())
            self.assertTrue((flow_dir / "traces" / f"{state['workflow_id']}.json").exists())
            self.assertTrue((flow_dir / "turns.jsonl").exists())
            self.assertTrue((flow_dir / "actions.jsonl").exists())
            self.assertTrue((flow_dir / "artifacts.json").exists())
            turns = self._read_jsonl(flow_dir / "turns.jsonl")
            self.assertGreaterEqual(len(turns), 2)
            self.assertEqual(turns[0]["turn_id"], state["current_turn_id"])

    def test_cli_main_returns_130_when_launcher_is_interrupted(self) -> None:
        with mock.patch.object(flow_cli, "_stdin_is_interactive", return_value=True), \
             mock.patch.object(flow_cli, "_flow_subcommand_from_argv", return_value=""), \
             mock.patch.object(flow_cli, "textual_tui_support", return_value=(False, "disabled for test")), \
             mock.patch.object(flow_cli, "FlowApp") as mocked_app_cls:
            mocked_app = mocked_app_cls.return_value
            mocked_app.launcher.side_effect = KeyboardInterrupt()
            rc = flow_cli.main([])
        self.assertEqual(rc, 130)
        mocked_app._display.write.assert_called_with("[butler-flow] interrupted", err=True)

    def test_cli_main_routes_tty_new_to_tui_when_supported(self) -> None:
        with mock.patch.object(flow_cli, "_stdout_is_interactive", return_value=True), \
             mock.patch.object(flow_cli, "textual_tui_support", return_value=(True, "")), \
             mock.patch.object(flow_cli, "run_textual_flow_tui", return_value=0) as mocked_tui:
            rc = flow_cli.main(["new", "--goal", "ship cli", "--guard-condition", "done"])
        self.assertEqual(rc, 0)
        mocked_tui.assert_called_once()
        self.assertIn(mocked_tui.call_args.kwargs.get("mode"), {"new", "setup"})

    def test_cli_main_prefers_tui_for_launcher_when_term_is_dumb_but_tty_is_interactive(self) -> None:
        with mock.patch.object(flow_cli, "_stdin_is_interactive", return_value=True), \
             mock.patch.object(flow_cli, "_stdout_is_interactive", return_value=True), \
             mock.patch.object(flow_cli, "textual_tui_support", side_effect=[(False, "TERM=dumb does not support the TUI shell"), (True, "")]), \
             mock.patch.object(flow_cli, "run_textual_flow_tui", return_value=0) as mocked_tui:
            rc = flow_cli.main([])
        self.assertEqual(rc, 0)
        mocked_tui.assert_called_once()
        self.assertEqual(mocked_tui.call_args.kwargs.get("mode"), "launcher")

    def test_cli_main_routes_tty_run_alias_to_new(self) -> None:
        with mock.patch.object(flow_cli, "_stdout_is_interactive", return_value=True), \
             mock.patch.object(flow_cli, "textual_tui_support", return_value=(True, "")), \
             mock.patch.object(flow_cli, "run_textual_flow_tui", return_value=0) as mocked_tui:
            rc = flow_cli.main(["run", "--goal", "ship cli", "--guard-condition", "done"])
        self.assertEqual(rc, 0)
        mocked_tui.assert_called_once()
        self.assertIn(mocked_tui.call_args.kwargs.get("mode"), {"new", "setup"})

    def test_cli_main_plain_new_skips_tui_route(self) -> None:
        with mock.patch.object(flow_cli, "_stdout_is_interactive", return_value=True), \
             mock.patch.object(flow_cli, "textual_tui_support", return_value=(True, "")), \
             mock.patch.object(flow_cli, "run_textual_flow_tui") as mocked_tui, \
             mock.patch.object(flow_cli, "FlowApp") as mocked_app_cls:
            mocked_app_cls.return_value.run_new.return_value = 0
            rc = flow_cli.main(["new", "--goal", "ship cli", "--guard-condition", "done", "--plain"])
        self.assertEqual(rc, 0)
        mocked_tui.assert_not_called()
        mocked_app_cls.return_value.run_new.assert_called_once()

    def test_plain_new_does_not_prompt_when_stdin_is_not_interactive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(
                        text="implemented",
                        metadata={"external_session": {"provider": "codex", "thread_id": "thread-non-tty", "resume_capable": True}},
                        agent_id="butler_flow.codex_executor",
                    ),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        ),
                        agent_id="butler_flow.cursor_judge",
                    ),
                ]
            )
            app = FlowApp(
                run_prompt_receipt_fn=runner,
                input_fn=lambda prompt: (_ for _ in ()).throw(AssertionError(f"unexpected prompt: {prompt}")),
                stdout=StringIO(),
                stderr=StringIO(),
            )
            args = self._new_args(config=config, goal="ship cli", guard_condition="done")
            args.plain = True
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True), \
                 mock.patch.object(flow_shell, "_stdin_is_interactive", return_value=False):
                rc = app.run_new(args)
            self.assertEqual(rc, 0)

    def test_cli_main_exec_new_skips_tui_route(self) -> None:
        with mock.patch.object(flow_cli, "_stdout_is_interactive", return_value=True), \
             mock.patch.object(flow_cli, "textual_tui_support", return_value=(True, "")), \
             mock.patch.object(flow_cli, "run_textual_flow_tui") as mocked_tui, \
             mock.patch.object(flow_cli, "FlowApp") as mocked_app_cls:
            mocked_app_cls.return_value.exec_run.return_value = 0
            rc = flow_cli.main(["exec", "new", "--goal", "ship cli", "--guard-condition", "done"])
        self.assertEqual(rc, 0)
        mocked_tui.assert_not_called()
        mocked_app_cls.return_value.exec_run.assert_called_once()

    def test_cli_main_exec_run_alias_routes_to_exec_new(self) -> None:
        with mock.patch.object(flow_cli, "_stdout_is_interactive", return_value=True), \
             mock.patch.object(flow_cli, "textual_tui_support", return_value=(True, "")), \
             mock.patch.object(flow_cli, "run_textual_flow_tui") as mocked_tui, \
             mock.patch.object(flow_cli, "FlowApp") as mocked_app_cls:
            mocked_app_cls.return_value.exec_run.return_value = 0
            rc = flow_cli.main(["exec", "run", "--goal", "ship cli", "--guard-condition", "done"])
        self.assertEqual(rc, 0)
        mocked_tui.assert_not_called()
        mocked_app_cls.return_value.exec_run.assert_called_once()

    def test_cli_main_exec_resume_skips_tui_route(self) -> None:
        with mock.patch.object(flow_cli, "_stdout_is_interactive", return_value=True), \
             mock.patch.object(flow_cli, "textual_tui_support", return_value=(True, "")), \
             mock.patch.object(flow_cli, "run_textual_flow_tui") as mocked_tui, \
             mock.patch.object(flow_cli, "FlowApp") as mocked_app_cls:
            mocked_app_cls.return_value.exec_resume.return_value = 0
            rc = flow_cli.main(["exec", "resume", "--last"])
        self.assertEqual(rc, 0)
        mocked_tui.assert_not_called()
        mocked_app_cls.return_value.exec_resume.assert_called_once()

    def test_single_goal_retry_then_complete_reuses_codex_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(
                        text="halfway",
                        metadata={"external_session": {"provider": "codex", "thread_id": "thread-2", "resume_capable": True}},
                    ),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "RETRY",
                                "reason": "not yet",
                                "next_codex_prompt": "continue",
                                "completion_summary": "needs more work",
                            },
                            ensure_ascii=False,
                        )
                    ),
                    _receipt(text="finished the rest"),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "reason": "pass",
                                "next_codex_prompt": "",
                                "completion_summary": "all done",
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            codex_calls = [call for call in runner.calls if call["runtime_request"].get("cli") == "codex"]
            self.assertEqual(len(codex_calls), 2)
            self.assertEqual(codex_calls[0]["runtime_request"]["codex_mode"], "exec")
            self.assertEqual(codex_calls[1]["runtime_request"]["codex_mode"], "resume")
            self.assertEqual(codex_calls[1]["runtime_request"]["codex_session_id"], "thread-2")
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            self.assertEqual(state["attempt_count"], 2)
            self.assertEqual(state["last_cursor_decision"]["decision"], "COMPLETE")

    def test_single_goal_resume_failure_reseeds_exec_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(
                        text="halfway",
                        metadata={"external_session": {"provider": "codex", "thread_id": "thread-resume", "resume_capable": True}},
                    ),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "RETRY",
                                "reason": "needs more work",
                                "next_codex_prompt": "continue",
                                "completion_summary": "retry after first attempt",
                            },
                            ensure_ascii=False,
                        )
                    ),
                    _receipt(
                        status="failed",
                        text="resume session not found",
                        metadata={
                            "external_session": {
                                "provider": "codex",
                                "thread_id": "",
                                "resume_capable": True,
                                "resume_failed": True,
                            }
                        },
                    ),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "RETRY",
                                "reason": "resume failed, reseed",
                                "next_codex_prompt": "reseed and continue",
                                "completion_summary": "retry after reseed",
                            },
                            ensure_ascii=False,
                        )
                    ),
                    _receipt(
                        text="finished after reseed",
                        metadata={"external_session": {"provider": "codex", "thread_id": "thread-reseed", "resume_capable": True}},
                    ),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "all done",
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            codex_calls = [call for call in runner.calls if call["runtime_request"].get("cli") == "codex"]
            self.assertEqual(len(codex_calls), 3)
            self.assertEqual(codex_calls[0]["runtime_request"]["codex_mode"], "exec")
            self.assertEqual(codex_calls[1]["runtime_request"]["codex_mode"], "resume")
            self.assertEqual(codex_calls[1]["runtime_request"]["codex_session_id"], "thread-resume")
            self.assertEqual(codex_calls[2]["runtime_request"]["codex_mode"], "exec")
            self.assertEqual(codex_calls[2]["runtime_request"]["codex_session_id"], "")

    def test_single_goal_run_emits_flow_ui_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)

            def _codex_response(prompt, workspace, timeout, cfg, runtime_request, *, stream=False, on_segment=None, on_event=None):
                if callable(on_segment):
                    on_segment("hello")
                    on_segment("hello world")
                if callable(on_event):
                    on_event({"kind": "usage", "text": "tokens=12"})
                return _receipt(
                    text="hello world",
                    metadata={"external_session": {"provider": "codex", "thread_id": "thread-events", "resume_capable": True}},
                    agent_id="butler_flow.codex_executor",
                )

            runner = _ReceiptRunner(
                [
                    _codex_response,
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        ),
                        agent_id="butler_flow.cursor_judge",
                    ),
                ]
            )
            events: list[dict] = []
            app = self._app(runner, event_callback=lambda event: events.append(event.to_dict()))
            args = self._run_args(config=config)
            args.no_stream = False
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(args)
            self.assertEqual(rc, 0)
            kinds = [item["kind"] for item in events]
            self.assertIn("run_started", kinds)
            self.assertIn("supervisor_decided", kinds)
            self.assertIn("codex_segment", kinds)
            self.assertIn("codex_runtime_event", kinds)
            self.assertIn("judge_result", kinds)
            self.assertIn("artifact_registered", kinds)
            self.assertIn("run_completed", kinds)
            flow_dir = self._flow_dirs(root)[0]
            timeline = self._read_jsonl(flow_dir / "events.jsonl")
            self.assertIn("run_started", [row["kind"] for row in timeline])
            self.assertIn("run_completed", [row["kind"] for row in timeline])
            event_index = {str(row.get("kind") or ""): row for row in timeline}
            self.assertEqual(event_index["run_started"]["lane"], "system")
            self.assertEqual(event_index["run_started"]["family"], "run")
            self.assertEqual(event_index["supervisor_decided"]["lane"], "supervisor")
            self.assertEqual(event_index["supervisor_decided"]["family"], "decision")
            self.assertEqual(event_index["codex_segment"]["lane"], "workflow")
            self.assertEqual(event_index["codex_segment"]["family"], "raw_execution")
            self.assertTrue(str(event_index["codex_segment"].get("raw_text") or "").strip())
            self.assertEqual(event_index["judge_result"]["lane"], "supervisor")
            self.assertEqual(event_index["judge_result"]["family"], "decision")
            self.assertEqual(event_index["artifact_registered"]["lane"], "workflow")
            self.assertEqual(event_index["artifact_registered"]["family"], "artifact")
            self.assertEqual(event_index["run_completed"]["lane"], "system")
            self.assertEqual(event_index["run_completed"]["family"], "run")

    def test_llm_supervisor_runtime_uses_dedicated_session_and_writes_structured_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root, {"butler_flow": {"supervisor_runtime": {"enable_llm_supervisor": True}}})
            runner = _ReceiptRunner(
                [
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "execute",
                                "turn_kind": "execute",
                                "reason": "proceed with the active implementer",
                                "confidence": 0.82,
                                "next_action": "run_executor",
                                "instruction": "inspect the repo and complete the bounded task",
                                "active_role_id": "implementer",
                                "session_mode": "cold",
                                "load_profile": "full",
                                "issue_kind": "none",
                                "followup_kind": "none",
                            },
                            ensure_ascii=False,
                        ),
                        metadata={"external_session": {"provider": "codex", "thread_id": "thread-supervisor", "resume_capable": True}},
                        agent_id="butler_flow.supervisor",
                    ),
                    _receipt(
                        text="implemented",
                        metadata={"external_session": {"provider": "codex", "thread_id": "thread-executor", "resume_capable": True}},
                        agent_id="butler_flow.codex_executor",
                    ),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        ),
                        agent_id="butler_flow.cursor_judge",
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            self.assertEqual(state["supervisor_thread_id"], "thread-supervisor")
            self.assertEqual(state["codex_session_id"], "thread-executor")
            runtime_plan = self._read_json(flow_dir / "runtime_plan.json")
            self.assertIn("flow_board", runtime_plan)
            self.assertIn("active_turn_task", runtime_plan)
            packets = self._read_jsonl(flow_dir / "prompt_packets.jsonl")
            self.assertGreaterEqual(len(packets), 3)
            self.assertEqual(packets[0]["target_role"], "supervisor")
            self.assertEqual(packets[0]["session_mode"], "cold")
            self.assertIn("rendered_prompt", packets[0]["packet"])
            self.assertEqual(packets[0]["packet"]["flow_board"]["goal"], "ship it")
            self.assertTrue(any(packet.get("target_role") == "judge" for packet in packets))
            self.assertEqual(runner.calls[0]["runtime_request"]["agent_id"], "butler_flow.supervisor")
            self.assertEqual(runner.calls[1]["runtime_request"]["agent_id"], "butler_flow.codex_executor")
            events = self._read_jsonl(flow_dir / "events.jsonl")
            self.assertTrue(
                any(
                    str(row.get("kind") or "") == "codex_segment"
                    and str(row.get("lane") or "") == "supervisor"
                    and "execute" in str(row.get("raw_text") or row.get("message") or "")
                    for row in events
                )
            )

    def test_compile_packet_includes_source_asset_and_supervisor_knowledge(self) -> None:
        if _NEW_FLOW_STATE is None or _WRITE_JSON_ATOMIC is None or _BUILD_FLOW_ROOT is None:
            raise AssertionError("butler_flow must expose build/new/write helpers for tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flow_dir = _BUILD_FLOW_ROOT(root) / "flow_packet_demo"
            flow_state = _NEW_FLOW_STATE(
                workflow_id="flow_packet_demo",
                workflow_kind=MANAGED_FLOW_KIND,
                workspace_root=str(root),
                goal="ship asset-aware manage center",
                guard_condition="supervisor sees asset context",
                max_attempts=6,
                max_phase_attempts=3,
            )
            flow_state["active_role_id"] = "implementer"
            ensure_flow_sidecars(flow_dir, flow_state)
            bundle_root = flow_dir / "bundle"
            (bundle_root / "derived").mkdir(parents=True, exist_ok=True)
            (bundle_root / "supervisor.md").write_text("Know the flow author's intent and management rules.", encoding="utf-8")
            _WRITE_JSON_ATOMIC(
                bundle_root / "derived" / "supervisor_knowledge.json",
                {
                    "composition_mode": "handwritten+compiled",
                    "knowledge_text": "Compiled checklist: verify lineage, review checklist, and launch defaults.",
                    "updated_at": "2026-04-02 10:00:00",
                },
            )
            _WRITE_JSON_ATOMIC(
                flow_dir / "flow_definition.json",
                {
                    "flow_id": "flow_packet_demo",
                    "workflow_kind": MANAGED_FLOW_KIND,
                    "goal": "ship asset-aware manage center",
                    "guard_condition": "supervisor sees asset context",
                    "phase_plan": list(flow_state.get("phase_plan") or []),
                    "source_asset_key": "template:manage_center_v2",
                    "source_asset_kind": "template",
                    "source_asset_version": "2026.04.02",
                    "review_checklist": ["check static fields", "check supervisor bundle"],
                    "role_guidance": {
                        "suggested_roles": ["planner", "implementer", "reviewer"],
                        "suggested_specialists": ["creator", "product-manager", "user-simulator"],
                        "activation_hints": ["when environment or domain gaps block progress"],
                        "promotion_candidates": ["creator"],
                        "manager_notes": "Use extra specialists only when a real bottleneck appears.",
                    },
                    "doctor_policy": {
                        "enabled": True,
                        "activation_rules": ["repeated_service_fault", "same_resume_failure"],
                        "repair_scope": "runtime_assets_first",
                        "framework_bug_action": "pause",
                        "max_rounds_per_episode": 1,
                    },
                    "control_profile": {
                        "task_archetype": "repo_delivery",
                        "packet_size": "medium",
                        "evidence_level": "standard",
                        "gate_cadence": "phase",
                        "repo_binding_policy": "explicit",
                        "repo_contract_paths": ["docs/project-map/00_current_baseline.md"],
                    },
                    "supervisor_profile": {
                        "archetype": "research_editor",
                        "review_focus": ["evidence quality"],
                    },
                    "run_brief": "Keep the supervisor focused on evidence-backed delivery.",
                    "source_bindings": [{"kind": "doc", "label": "Spec", "ref": "docs/spec.md", "notes": "Primary scope"}],
                    "bundle_manifest": {
                        "bundle_root": "bundle",
                        "supervisor_ref": "bundle/supervisor.md",
                        "sources_ref": "bundle/sources.json",
                        "sources_path": "sources.json",
                        "derived": {"supervisor_compiled": "bundle/derived/supervisor_knowledge.json"},
                    },
                },
            )
            _WRITE_JSON_ATOMIC(
                bundle_root / "sources.json",
                {
                    "asset_kind": "instance",
                    "asset_id": "flow_packet_demo",
                    "items": [{"kind": "doc", "label": "Spec", "ref": "docs/spec.md", "notes": "Primary scope"}],
                },
            )
            app = self._app(_ReceiptRunner([]))
            compiled = app._runtime._compile_packet(
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                target_role="supervisor",
                role_id="supervisor",
                role_turn_no=1,
                attempt_no=1,
                phase_attempt_no=1,
                session_mode="cold",
                load_profile="full",
            )
            self.assertEqual(compiled["flow_board"]["source_asset_key"], "template:manage_center_v2")
            self.assertEqual(compiled["flow_board"]["source_asset_kind"], "template")
            self.assertEqual(compiled["flow_board"]["source_asset_version"], "2026.04.02")
            self.assertIn("check static fields", compiled["flow_board"]["review_checklist"])
            self.assertEqual(compiled["flow_board"]["role_guidance"]["promotion_candidates"], ["creator"])
            self.assertTrue(compiled["flow_board"]["doctor_policy"]["enabled"])
            self.assertEqual(compiled["flow_board"]["control_profile"]["repo_binding_policy"], "disabled")
            self.assertEqual(compiled["asset_context"]["control_profile"]["repo_binding_policy"], "disabled")
            self.assertEqual(compiled["asset_context"]["supervisor_profile"]["archetype"], "research_editor")
            self.assertEqual(compiled["asset_context"]["source_bindings"][0]["label"], "Spec")
            self.assertIn("Know the flow author's intent", compiled["supervisor_knowledge"]["knowledge_text"])
            self.assertIn("Compiled checklist", compiled["supervisor_knowledge"]["knowledge_text"])
            self.assertIn("repo_contract_paths", compiled["supervisor_knowledge"]["knowledge_text"])
            self.assertIn("template:manage_center_v2", compiled["rendered_prompt"])
            self.assertIn("Compiled checklist", compiled["rendered_prompt"])
            self.assertIn("advisory only", compiled["rendered_prompt"])
            self.assertIn("doctor", compiled["rendered_prompt"])
            self.assertIn("creator", compiled["rendered_prompt"])
            self.assertIn("research_editor", compiled["rendered_prompt"])
            self.assertIn("repo_binding_policy", compiled["rendered_prompt"])

    def test_operator_action_force_doctor_sets_control_profile_flag(self) -> None:
        if _NEW_FLOW_STATE is None or _WRITE_JSON_ATOMIC is None or _BUILD_FLOW_ROOT is None:
            raise AssertionError("butler_flow must expose build/new/write helpers for tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flow_id = "flow_force_doctor_demo"
            flow_dir = _BUILD_FLOW_ROOT(root) / flow_id
            flow_state = _NEW_FLOW_STATE(
                workflow_id=flow_id,
                workflow_kind=MANAGED_FLOW_KIND,
                workspace_root=str(root),
                goal="repair current flow",
                guard_condition="doctor can take over",
                max_attempts=0,
                max_phase_attempts=10,
            )
            _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)
            runtime = flow_runtime.FlowRuntime(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                display=flow_shell.FlowDisplay(StringIO(), StringIO()),
            )
            receipt = runtime.apply_operator_action(
                cfg={},
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                action_type="force_doctor",
                payload={},
            )
            self.assertEqual(receipt["action_type"], "force_doctor")
            self.assertTrue(flow_state["control_profile"]["force_doctor_next_turn"])

    def test_operator_action_bind_repo_contract_persists_explicit_binding(self) -> None:
        if _NEW_FLOW_STATE is None or _WRITE_JSON_ATOMIC is None or _BUILD_FLOW_ROOT is None:
            raise AssertionError("butler_flow must expose build/new/write helpers for tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flow_id = "flow_bind_contract_demo"
            flow_dir = _BUILD_FLOW_ROOT(root) / flow_id
            flow_state = _NEW_FLOW_STATE(
                workflow_id=flow_id,
                workflow_kind=MANAGED_FLOW_KIND,
                workspace_root=str(root),
                goal="ship repo change",
                guard_condition="contract stays explicit",
                max_attempts=0,
                max_phase_attempts=10,
            )
            _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)
            runtime = flow_runtime.FlowRuntime(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                display=flow_shell.FlowDisplay(StringIO(), StringIO()),
            )
            receipt = runtime.apply_operator_action(
                cfg={},
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                action_type="bind_repo_contract",
                payload={"repo_contract_path": "docs/project-map/00_current_baseline.md"},
            )
            self.assertEqual(receipt["action_type"], "bind_repo_contract")
            self.assertEqual(flow_state["control_profile"]["repo_binding_policy"], "explicit")
            self.assertEqual(
                flow_state["control_profile"]["repo_contract_paths"],
                ["docs/project-map/00_current_baseline.md"],
            )

    def test_supervisor_control_adjustments_persist_to_flow_state(self) -> None:
        if _NEW_FLOW_STATE is None:
            raise AssertionError("butler_flow must expose _new_flow_state for tests")
        runtime = flow_runtime.FlowRuntime(
            run_prompt_receipt_fn=lambda *args, **kwargs: None,
            display=flow_shell.FlowDisplay(StringIO(), StringIO()),
        )
        flow_state = _NEW_FLOW_STATE(
            workflow_id="flow_supervisor_controls",
            workflow_kind=PROJECT_LOOP_KIND,
            workspace_root="/tmp/demo",
            goal="ship safely",
            guard_condition="done",
            max_attempts=0,
            max_phase_attempts=6,
        )
        flow_state["control_profile"]["repo_binding_policy"] = "explicit"
        flow_state["control_profile"]["repo_contract_paths"] = ["AGENTS.md"]
        decision = runtime._normalize_supervisor_decision(
            {
                "decision": "execute",
                "turn_kind": "execute",
                "reason": "shrink the next packet and temporarily disable repo contract pressure",
                "active_role_id": "implementer",
                "packet_size": "small",
                "evidence_level": "strict",
                "gate_cadence": "strict",
                "repo_binding_policy": "disabled",
            },
            flow_state=flow_state,
            phase="imp",
            attempt_no=2,
        )
        runtime._apply_supervisor_control_profile(flow_state, decision)
        control_profile = dict(flow_state.get("control_profile") or {})
        self.assertEqual(control_profile["packet_size"], "small")
        self.assertEqual(control_profile["evidence_level"], "strict")
        self.assertEqual(control_profile["gate_cadence"], "strict")
        self.assertEqual(control_profile["repo_binding_policy"], "disabled")
        self.assertEqual(control_profile["repo_contract_paths"], ["AGENTS.md"])

    def test_asset_runtime_context_prefers_instance_control_profile_and_strips_stale_control_section(self) -> None:
        if _NEW_FLOW_STATE is None or _WRITE_JSON_ATOMIC is None or _BUILD_FLOW_ROOT is None:
            raise AssertionError("butler_flow must expose build/new/write helpers for tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flow_id = "flow_asset_context_profile"
            flow_dir = _BUILD_FLOW_ROOT(root) / flow_id
            flow_state = _NEW_FLOW_STATE(
                workflow_id=flow_id,
                workflow_kind=PROJECT_LOOP_KIND,
                workspace_root=str(root),
                goal="ship safely",
                guard_condition="done",
                max_attempts=0,
                max_phase_attempts=6,
            )
            flow_state["control_profile"]["packet_size"] = "small"
            flow_state["control_profile"]["repo_binding_policy"] = "disabled"
            ensure_flow_sidecars(flow_dir, flow_state)
            bundle_root = flow_dir / "bundle"
            (bundle_root / "derived").mkdir(parents=True, exist_ok=True)
            _WRITE_JSON_ATOMIC(
                flow_dir / "flow_definition.json",
                {
                    "flow_id": flow_id,
                    "workflow_kind": PROJECT_LOOP_KIND,
                    "bundle_manifest": {
                        "bundle_root": "bundle",
                        "supervisor_ref": "bundle/supervisor.md",
                        "derived": {"supervisor_compiled": "bundle/derived/supervisor_knowledge.json"},
                    },
                    "control_profile": {
                        "task_archetype": "repo_delivery",
                        "packet_size": "large",
                        "evidence_level": "standard",
                        "gate_cadence": "phase",
                        "repo_binding_policy": "explicit",
                        "repo_contract_paths": ["docs/project-map/00_current_baseline.md"],
                    },
                },
            )
            _WRITE_JSON_ATOMIC(
                bundle_root / "derived" / "supervisor_knowledge.json",
                {
                    "composition_mode": "handwritten+compiled",
                    "knowledge_text": (
                        "[supervisor profile]\n- archetype: delivery_manager\n\n"
                        "[control profile]\n- packet_size: large\n- repo_contract_paths: docs/project-map/00_current_baseline.md"
                    ),
                    "updated_at": "2026-04-03 10:00:00",
                },
            )
            runtime = flow_runtime.FlowRuntime(
                run_prompt_receipt_fn=lambda *args, **kwargs: None,
                display=flow_shell.FlowDisplay(StringIO(), StringIO()),
            )
            asset_context, supervisor_knowledge = runtime._asset_runtime_context(flow_dir, flow_state)
            self.assertEqual(asset_context["control_profile"]["packet_size"], "small")
            self.assertEqual(asset_context["control_profile"]["repo_binding_policy"], "disabled")
            self.assertIn("[supervisor profile]", supervisor_knowledge["knowledge_text"])
            self.assertIn('"packet_size": "small"', supervisor_knowledge["knowledge_text"])
            self.assertNotIn("docs/project-map/00_current_baseline.md", supervisor_knowledge["knowledge_text"])

    def test_llm_supervisor_invalid_json_falls_back_to_heuristic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root, {"butler_flow": {"supervisor_runtime": {"enable_llm_supervisor": True}}})
            runner = _ReceiptRunner(
                [
                    _receipt(
                        text="not valid json",
                        metadata={"external_session": {"provider": "codex", "thread_id": "thread-supervisor-bad", "resume_capable": True}},
                        agent_id="butler_flow.supervisor",
                    ),
                    _receipt(
                        text="implemented after fallback",
                        metadata={"external_session": {"provider": "codex", "thread_id": "thread-exec-fallback", "resume_capable": True}},
                        agent_id="butler_flow.codex_executor",
                    ),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        ),
                        agent_id="butler_flow.cursor_judge",
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            self.assertTrue(state["latest_supervisor_decision"].get("fallback_used"))
            trace = self._read_jsonl(flow_dir / "strategy_trace.jsonl")
            self.assertTrue(any(str(row.get("kind") or "") == "supervisor_fallback" for row in trace))
            self.assertEqual(state["supervisor_thread_id"], "thread-supervisor-bad")
            self.assertEqual(state["codex_session_id"], "thread-exec-fallback")

    def test_llm_supervisor_can_spawn_guardrailed_ephemeral_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root, {"butler_flow": {"supervisor_runtime": {"enable_llm_supervisor": True}}})
            runner = _ReceiptRunner(
                [
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "execute",
                                "turn_kind": "execute",
                                "reason": "use a narrow schema specialist for this turn",
                                "confidence": 0.84,
                                "next_action": "run_executor",
                                "instruction": "trace the schema diff and apply the smallest bounded fix",
                                "active_role_id": "schema_specialist",
                                "session_mode": "cold",
                                "load_profile": "compact",
                                "issue_kind": "none",
                                "followup_kind": "none",
                                "mutation": {
                                    "kind": "spawn_ephemeral_role",
                                    "target_role_id": "schema_specialist",
                                    "summary": "spawn a bounded schema specialist",
                                },
                                "ephemeral_role": {
                                    "role_id": "schema_specialist",
                                    "base_role_id": "implementer",
                                    "charter_addendum": "Focus only on schema diff tracing and the smallest bounded repair.",
                                },
                            },
                            ensure_ascii=False,
                        ),
                        metadata={"external_session": {"provider": "codex", "thread_id": "thread-supervisor-ephemeral", "resume_capable": True}},
                        agent_id="butler_flow.supervisor",
                    ),
                    _receipt(
                        text="specialist completed the bounded fix",
                        metadata={"external_session": {"provider": "codex", "thread_id": "thread-ephemeral-executor", "resume_capable": True}},
                        agent_id="butler_flow.codex_executor",
                    ),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        ),
                        agent_id="butler_flow.cursor_judge",
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            role_payload = dict(state["role_sessions"]["schema_specialist"])
            self.assertEqual(role_payload["role_kind"], "ephemeral")
            self.assertEqual(role_payload["base_role_id"], "implementer")
            mutations = self._read_jsonl(flow_dir / "mutations.jsonl")
            self.assertTrue(any(str(row.get("mutation_kind") or "") == "spawn_ephemeral_role" for row in mutations))
            packets = self._read_jsonl(flow_dir / "prompt_packets.jsonl")
            executor_packet = next(packet for packet in packets if packet.get("target_role") == "schema_specialist")
            self.assertEqual(executor_packet["packet"]["role_board"]["role_kind"], "ephemeral")
            self.assertEqual(executor_packet["packet"]["role_board"]["base_role_id"], "implementer")

    def test_exec_run_emits_jsonl_events_and_final_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)

            def _codex_response(prompt, workspace, timeout, cfg, runtime_request, *, stream=False, on_segment=None, on_event=None):
                if callable(on_segment):
                    on_segment("hello")
                    on_segment("hello world")
                if callable(on_event):
                    on_event({"kind": "usage", "text": "tokens=12"})
                return _receipt(
                    text="hello world",
                    metadata={
                        "external_session": {
                            "provider": "codex",
                            "thread_id": "thread-exec",
                            "resume_capable": True,
                        },
                        "provider_returncode": 0,
                    },
                    agent_id="butler_flow.codex_executor",
                )

            runner = _ReceiptRunner(
                [
                    _codex_response,
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        ),
                        agent_id="butler_flow.cursor_judge",
                    ),
                ]
            )
            stdout = StringIO()
            stderr = StringIO()
            app = FlowApp(
                run_prompt_receipt_fn=runner,
                input_fn=lambda prompt: "",
                stdout=stdout,
                stderr=stderr,
            )
            args = self._run_args(config=config)
            args.no_stream = False
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.exec_run(args)
            self.assertEqual(rc, 0)
            rows = [json.loads(line) for line in stdout.getvalue().splitlines() if str(line or "").strip()]
            self.assertGreaterEqual(len(rows), 2)
            self.assertEqual(rows[-1]["kind"], "flow_exec_receipt")
            self.assertEqual(rows[-1]["status"], "completed")
            self.assertEqual(rows[-1]["return_code"], 0)
            self.assertEqual(rows[-1]["codex_session_id"], "thread-exec")
            self.assertEqual(rows[-1]["last_codex_receipt"]["status"], "completed")
            event_kinds = [row["kind"] for row in rows[:-1]]
            self.assertIn("run_started", event_kinds)
            self.assertIn("judge_result", event_kinds)
            self.assertIn("run_completed", event_kinds)

    def test_exec_resume_completed_flow_emits_receipt_without_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            if _NEW_FLOW_STATE is None or _WRITE_JSON_ATOMIC is None:
                raise AssertionError("butler_flow must expose _new_flow_state/_write_json_atomic for tests")
            flow_state = _NEW_FLOW_STATE(
                workflow_id="flow_exec_done",
                workflow_kind=SINGLE_GOAL_KIND,
                workspace_root=str(root),
                goal="ship it",
                guard_condition="verified",
                max_attempts=4,
                max_phase_attempts=2,
                codex_session_id="thread-finished",
            )
            flow_state["status"] = "completed"
            flow_state["last_completion_summary"] = "already done"
            flow_state["last_codex_receipt"] = {"status": "completed", "summary": "done"}
            flow_state["last_cursor_receipt"] = {"status": "completed", "summary": "judge pass"}
            flow_path = _BUILD_FLOW_ROOT(root) / "flow_exec_done"
            _WRITE_JSON_ATOMIC(flow_path / "workflow_state.json", flow_state)

            runner = _ReceiptRunner([])
            stdout = StringIO()
            stderr = StringIO()
            app = FlowApp(
                run_prompt_receipt_fn=runner,
                input_fn=lambda prompt: "",
                stdout=stdout,
                stderr=stderr,
            )
            args = argparse.Namespace(
                command="resume",
                config=config,
                flow_id="flow_exec_done",
                workflow_id="",
                last=False,
                codex_session_id="",
                kind=SINGLE_GOAL_KIND,
                goal="",
                guard_condition="",
                max_attempts=None,
                max_phase_attempts=None,
                no_stream=True,
            )
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.exec_resume(args)
            self.assertEqual(rc, 0)
            self.assertEqual(runner.calls, [])
            rows = [json.loads(line) for line in stdout.getvalue().splitlines() if str(line or "").strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["kind"], "flow_exec_receipt")
            self.assertEqual(rows[0]["status"], "completed")
            self.assertEqual(rows[0]["summary"], "already done")

    def test_build_list_payload_derives_effective_running_status_from_runtime_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            if _NEW_FLOW_STATE is None or _WRITE_JSON_ATOMIC is None:
                raise AssertionError("butler_flow must expose _new_flow_state/_write_json_atomic for tests")
            flow_state = _NEW_FLOW_STATE(
                workflow_id="flow_effective_running",
                workflow_kind=PROJECT_LOOP_KIND,
                workspace_root=str(root),
                goal="ship it",
                guard_condition="verified",
                max_attempts=4,
                max_phase_attempts=2,
            )
            flow_state["status"] = "pending"
            flow_path = _BUILD_FLOW_ROOT(root) / "flow_effective_running"
            _WRITE_JSON_ATOMIC(flow_path / "workflow_state.json", flow_state)
            runtime_store = FileRuntimeStateStore(flow_path)
            runtime_store.write_pid(os.getpid())
            runtime_store.write_watchdog_state(state="foreground", pid=os.getpid(), note="attached")
            runtime_store.write_run_state(
                run_id="flow_effective_running",
                state="running",
                phase="imp",
                pid=os.getpid(),
                note="attempt 1 phase=imp",
            )

            app = self._app(_ReceiptRunner([]))
            list_payload = app.build_flows_payload(argparse.Namespace(command="list", config=config, limit=10, json=False))
            status_payload = app.build_status_payload(
                argparse.Namespace(command="status", config=config, flow_id="flow_effective_running", workflow_id="", last=False, json=False)
            )

            self.assertEqual(list_payload["items"][0]["status"], "pending")
            self.assertEqual(list_payload["items"][0]["effective_status"], "running")
            self.assertEqual(list_payload["items"][0]["effective_phase"], "imp")
            self.assertEqual(status_payload["effective_status"], "running")
            self.assertEqual(status_payload["effective_phase"], "imp")

    def test_single_goal_abort_marks_flow_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(text="cannot complete"),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "ABORT",
                                "reason": "blocked",
                                "next_codex_prompt": "",
                                "completion_summary": "stop",
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 1)
            state = self._flow_state(self._flow_dirs(root)[0])
            self.assertEqual(state["status"], "failed")
            self.assertEqual(state["last_cursor_decision"]["decision"], "ABORT")

    def test_project_loop_auto_advances_plan_imp_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(text="plan ready", metadata={"external_session": {"provider": "codex", "thread_id": "thread-plan", "resume_capable": True}}),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "", "reason": "plan done", "next_codex_prompt": "", "completion_summary": "plan"}, ensure_ascii=False)),
                    _receipt(text="implemented"),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "", "reason": "imp done", "next_codex_prompt": "", "completion_summary": "imp"}, ensure_ascii=False)),
                    _receipt(text="review passed"),
                    _receipt(text=json.dumps({"decision": "COMPLETE", "next_phase": "done", "reason": "review pass", "next_codex_prompt": "", "completion_summary": "done"}, ensure_ascii=False)),
                ]
            )
            app = self._app(runner)
            args = self._run_args(config=config, kind=PROJECT_LOOP_KIND)
            args.max_attempts = 8
            args.max_phase_attempts = 4
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(args)
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            self.assertEqual([row["phase"] for row in state["phase_history"]], ["plan", "imp", "review"])
            self.assertEqual(state["attempt_count"], 3)
            codex_calls = [call for call in runner.calls if call["runtime_request"].get("cli") == "codex"]
            self.assertEqual(codex_calls[0]["runtime_request"]["codex_mode"], "exec")
            self.assertEqual(codex_calls[1]["runtime_request"]["codex_mode"], "exec")
            self.assertEqual(codex_calls[1]["runtime_request"]["codex_session_id"], "")

    def test_execution_mode_defaults_to_simple_and_shared_role_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(
                        text="done",
                        metadata={"external_session": {"provider": "codex", "thread_id": "thread-mode", "resume_capable": True}},
                    ),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            self.assertEqual(state.get("execution_mode"), "simple")
            self.assertEqual(state.get("session_strategy"), "shared")
            self.assertEqual(state.get("execution_context"), "repo_bound")
            role_sessions = state.get("role_sessions")
            self.assertIsInstance(role_sessions, dict)
            self.assertGreaterEqual(len(role_sessions), 1)
            session_ids = []
            for value in role_sessions.values():
                if isinstance(value, str):
                    session_ids.append(value)
                elif isinstance(value, dict):
                    session_ids.append(str(value.get("session_id") or value.get("codex_session_id") or ""))
            self.assertIn(state.get("codex_session_id"), session_ids)

    def test_project_loop_defaults_to_medium_role_bound_and_control_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = _NEW_FLOW_STATE(
                workflow_id="flow_project_default",
                workflow_kind=PROJECT_LOOP_KIND,
                workspace_root=str(root),
                goal="ship safely",
                guard_condition="done",
                max_attempts=0,
                max_phase_attempts=6,
            )
            self.assertEqual(state.get("execution_mode"), "medium")
            self.assertEqual(state.get("session_strategy"), "role_bound")
            self.assertEqual(state.get("control_profile", {}).get("packet_size"), "medium")
            self.assertEqual(state.get("control_profile", {}).get("repo_binding_policy"), "disabled")

    def test_project_flow_defaults_to_medium_role_bound_and_control_profile(self) -> None:
        state = _NEW_FLOW_STATE(
            workflow_id="flow_project_defaults",
            workflow_kind=PROJECT_LOOP_KIND,
            workspace_root="/tmp/demo",
            goal="ship delivery",
            guard_condition="review passes",
            max_attempts=0,
            max_phase_attempts=10,
        )
        self.assertEqual(state.get("execution_mode"), "medium")
        self.assertEqual(state.get("session_strategy"), "role_bound")
        self.assertEqual(state.get("execution_context"), "repo_bound")
        control_profile = dict(state.get("control_profile") or {})
        self.assertEqual(control_profile.get("task_archetype"), "repo_delivery")
        self.assertEqual(control_profile.get("repo_binding_policy"), "disabled")

    def test_medium_creates_role_sidecars_and_handoffs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(
                root,
                {
                    "butler_flow": {
                        "role_runtime": {
                            "execution_mode_default": "medium",
                            "role_pack": "coding_flow",
                        }
                    }
                },
            )
            runner = _ReceiptRunner(
                [
                    _receipt(text="plan ready", metadata={"external_session": {"provider": "codex", "thread_id": "thread-role", "resume_capable": True}}),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "", "reason": "plan done", "next_codex_prompt": "", "completion_summary": "plan"}, ensure_ascii=False)),
                    _receipt(text="implemented"),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "", "reason": "imp done", "next_codex_prompt": "", "completion_summary": "imp"}, ensure_ascii=False)),
                    _receipt(text="review passed"),
                    _receipt(text=json.dumps({"decision": "COMPLETE", "next_phase": "done", "reason": "review pass", "next_codex_prompt": "", "completion_summary": "done"}, ensure_ascii=False)),
                ]
            )
            app = self._app(runner)
            args = self._run_args(config=config, kind=PROJECT_LOOP_KIND)
            args.max_attempts = 6
            args.max_phase_attempts = 3
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(args)
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            role_sessions_path = flow_dir / "role_sessions.json"
            handoffs_path = flow_dir / "handoffs.jsonl"
            self.assertTrue(role_sessions_path.exists())
            self.assertTrue(handoffs_path.exists())
            events_path = flow_dir / "events.jsonl"
            role_payload = self._read_json(role_sessions_path)
            if isinstance(role_payload, dict) and isinstance(role_payload.get("items"), list):
                role_entries = role_payload["items"]
            elif isinstance(role_payload, dict):
                role_entries = [
                    {"role_id": role_id, **(value if isinstance(value, dict) else {"session_id": value})}
                    for role_id, value in role_payload.items()
                ]
            else:
                role_entries = role_payload
            role_ids = {str(entry.get("role_id") or "") for entry in role_entries if isinstance(entry, dict)}
            self.assertTrue({"planner", "implementer", "reviewer"}.issubset(role_ids))
            handoffs = self._read_jsonl(handoffs_path)
            self.assertGreaterEqual(len(handoffs), 2)
            for handoff in handoffs:
                for key in ("handoff_id", "source_role_id", "target_role_id", "status"):
                    self.assertIn(key, handoff)
            events = self._read_jsonl(events_path)
            self.assertTrue(any(str(row.get("kind") or "") == "role_handoff_created" for row in events))
            self.assertTrue(any(str(row.get("kind") or "") == "role_handoff_consumed" for row in events))
            created = next(row for row in events if str(row.get("kind") or "") == "role_handoff_created")
            consumed = next(row for row in events if str(row.get("kind") or "") == "role_handoff_consumed")
            self.assertEqual(created["lane"], "workflow")
            self.assertEqual(created["family"], "handoff")
            self.assertEqual(consumed["lane"], "workflow")
            self.assertEqual(consumed["family"], "handoff")

    def test_medium_artifacts_record_role_visibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(
                root,
                {
                    "butler_flow": {
                        "role_runtime": {
                            "execution_mode_default": "medium",
                            "role_pack": "coding_flow",
                        }
                    }
                },
            )
            runner = _ReceiptRunner(
                [
                    _receipt(text="plan ready", metadata={"external_session": {"provider": "codex", "thread_id": "thread-artifact", "resume_capable": True}}),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "", "reason": "plan done", "next_codex_prompt": "", "completion_summary": "plan"}, ensure_ascii=False)),
                    _receipt(text="implemented"),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "", "reason": "imp done", "next_codex_prompt": "", "completion_summary": "imp"}, ensure_ascii=False)),
                    _receipt(text="review passed"),
                    _receipt(text=json.dumps({"decision": "COMPLETE", "next_phase": "done", "reason": "review pass", "next_codex_prompt": "", "completion_summary": "done"}, ensure_ascii=False)),
                ]
            )
            app = self._app(runner)
            args = self._run_args(config=config, kind=PROJECT_LOOP_KIND)
            args.max_attempts = 6
            args.max_phase_attempts = 3
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(args)
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            artifacts = self._read_json(flow_dir / "artifacts.json")
            items = artifacts.get("items", []) if isinstance(artifacts, dict) else artifacts
            self.assertTrue(items)
            has_visibility = any(
                isinstance(item, dict)
                and "producer_role_id" in item
                and "consumer_role_ids" in item
                for item in items
            )
            self.assertTrue(has_visibility)

    def test_project_loop_review_can_bounce_to_imp_then_plan_then_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(text="plan ready", metadata={"external_session": {"provider": "codex", "thread_id": "thread-loop", "resume_capable": True}}),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "", "reason": "plan", "next_codex_prompt": "", "completion_summary": "plan"}, ensure_ascii=False)),
                    _receipt(text="implemented once"),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "", "reason": "imp", "next_codex_prompt": "", "completion_summary": "imp"}, ensure_ascii=False)),
                    _receipt(text="review found execution gap"),
                    _receipt(text=json.dumps({"decision": "RETRY", "next_phase": "imp", "reason": "fix code", "next_codex_prompt": "fix it", "completion_summary": "back to imp"}, ensure_ascii=False)),
                    _receipt(text="implemented twice"),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "", "reason": "imp again", "next_codex_prompt": "", "completion_summary": "imp2"}, ensure_ascii=False)),
                    _receipt(text="review found plan gap"),
                    _receipt(text=json.dumps({"decision": "RETRY", "next_phase": "plan", "reason": "tighten plan", "next_codex_prompt": "replan", "completion_summary": "back to plan"}, ensure_ascii=False)),
                    _receipt(text="plan tightened"),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "", "reason": "plan2", "next_codex_prompt": "", "completion_summary": "plan2"}, ensure_ascii=False)),
                    _receipt(text="implemented final"),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "", "reason": "imp3", "next_codex_prompt": "", "completion_summary": "imp3"}, ensure_ascii=False)),
                    _receipt(text="review passed"),
                    _receipt(text=json.dumps({"decision": "COMPLETE", "next_phase": "done", "reason": "ship", "next_codex_prompt": "", "completion_summary": "done"}, ensure_ascii=False)),
                ]
            )
            app = self._app(runner)
            args = self._run_args(config=config, kind=PROJECT_LOOP_KIND)
            args.max_attempts = 12
            args.max_phase_attempts = 5
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(args)
            self.assertEqual(rc, 0)
            state = self._flow_state(self._flow_dirs(root)[0])
            self.assertEqual(
                [row["phase"] for row in state["phase_history"]],
                ["plan", "imp", "review", "imp", "review", "plan", "imp", "review"],
            )
            self.assertEqual(state["last_cursor_decision"]["decision"], "COMPLETE")

    def test_single_goal_agent_cli_fault_enters_fix_turn_and_completes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root, {"butler_flow": {"enable_fix_turns": True}})
            runner = _ReceiptRunner(
                [
                    _receipt(text="codex cli invocation failed because the local mcp worker bootstrap was broken"),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "RETRY",
                                "issue_kind": "agent_cli_fault",
                                "followup_kind": "fix",
                                "reason": "repair the local codex cli bootstrap path",
                                "next_codex_prompt": "repair the codex cli bootstrap path and rerun the minimal flow preflight",
                                "completion_summary": "needs local cli repair",
                            },
                            ensure_ascii=False,
                        )
                    ),
                    _receipt(text="edge case fixed and targeted test passed"),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "issue_kind": "none",
                                "followup_kind": "none",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            turns = self._read_jsonl(flow_dir / "turns.jsonl")
            codex_calls = [call for call in runner.calls if call["runtime_request"].get("cli") == "codex"]
            self.assertEqual(self._flow_state(flow_dir)["status"], "completed")
            self.assertTrue(any(str(row.get("turn_kind") or "") == "fix" for row in turns))
            self.assertIn("Turn kind: fix", codex_calls[1]["prompt"])

    def test_single_goal_agent_cli_fault_defaults_to_retry_without_fix_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(text="codex cli invocation failed because the local mcp worker bootstrap was broken"),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "RETRY",
                                "issue_kind": "agent_cli_fault",
                                "followup_kind": "fix",
                                "reason": "repair the local codex cli bootstrap path",
                                "next_codex_prompt": "",
                                "completion_summary": "needs local cli repair",
                            },
                            ensure_ascii=False,
                        )
                    ),
                    _receipt(text="continued without fix turn"),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "issue_kind": "none",
                                "followup_kind": "none",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            turns = self._read_jsonl(flow_dir / "turns.jsonl")
            codex_calls = [call for call in runner.calls if call["runtime_request"].get("cli") == "codex"]
            self.assertEqual(state["phase_history"][0]["decision"]["issue_kind"], "service_fault")
            self.assertEqual(state["phase_history"][0]["decision"]["followup_kind"], "retry")
            self.assertFalse(any(str(row.get("turn_kind") or "") == "fix" for row in turns))
            self.assertIn("Turn kind: execute", codex_calls[1]["prompt"])

    def test_business_bug_retry_stays_execute_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(text="implementation missed one case"),
                    _receipt(text=json.dumps({"decision": "RETRY", "issue_kind": "bug", "followup_kind": "retry", "reason": "fix the business bug and rerun verification", "next_codex_prompt": "fix the business bug and rerun verification", "completion_summary": "needs business bug fix"}, ensure_ascii=False)),
                    _receipt(text="bug fixed"),
                    _receipt(text=json.dumps({"decision": "COMPLETE", "issue_kind": "none", "followup_kind": "none", "reason": "done", "next_codex_prompt": "", "completion_summary": "done"}, ensure_ascii=False)),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            turns = self._read_jsonl(flow_dir / "turns.jsonl")
            codex_calls = [call for call in runner.calls if call["runtime_request"].get("cli") == "codex"]
            self.assertEqual(state["status"], "completed")
            self.assertEqual(state["phase_history"][0]["decision"]["issue_kind"], "bug")
            self.assertEqual(state["phase_history"][0]["decision"]["followup_kind"], "retry")
            self.assertFalse(any(str(row.get("turn_kind") or "") == "fix" for row in turns))
            self.assertIn("Turn kind: execute", codex_calls[1]["prompt"])

    def test_project_loop_review_agent_cli_fault_stays_same_phase_with_fix_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root, {"butler_flow": {"enable_fix_turns": True}})
            runner = _ReceiptRunner(
                [
                    _receipt(text="plan ready"),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "", "issue_kind": "none", "followup_kind": "none", "reason": "plan done", "next_codex_prompt": "", "completion_summary": "plan"}, ensure_ascii=False)),
                    _receipt(text="implementation ready"),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "", "issue_kind": "none", "followup_kind": "none", "reason": "imp done", "next_codex_prompt": "", "completion_summary": "imp"}, ensure_ascii=False)),
                    _receipt(text="review failed because cursor cli parsing broke"),
                    _receipt(text=json.dumps({"decision": "RETRY", "next_phase": "", "issue_kind": "agent_cli_fault", "followup_kind": "fix", "reason": "repair the local cursor cli parsing path", "next_codex_prompt": "repair the local cursor cli parsing path and rerun the review", "completion_summary": "stay on review after local cli repair"}, ensure_ascii=False)),
                    _receipt(text="review rerun succeeded"),
                    _receipt(text=json.dumps({"decision": "COMPLETE", "next_phase": "done", "issue_kind": "none", "followup_kind": "none", "reason": "ship", "next_codex_prompt": "", "completion_summary": "done"}, ensure_ascii=False)),
                ]
            )
            app = self._app(runner)
            args = self._run_args(config=config, kind=PROJECT_LOOP_KIND)
            args.max_attempts = 6
            args.max_phase_attempts = 5
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(args)
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            turns = self._read_jsonl(flow_dir / "turns.jsonl")
            self.assertEqual([row["phase"] for row in state["phase_history"]], ["plan", "imp", "review", "review"])
            self.assertTrue(any(str(row.get("turn_kind") or "") == "fix" for row in turns))

    def test_service_fault_retry_does_not_enter_fix_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(status="failed", text="request timeout while contacting provider"),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "RETRY",
                                "issue_kind": "bug",
                                "followup_kind": "fix",
                                "reason": "timeout while contacting provider",
                                "next_codex_prompt": "",
                                "completion_summary": "retry",
                            },
                            ensure_ascii=False,
                        )
                    ),
                    _receipt(text="resumed and completed"),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "issue_kind": "none",
                                "followup_kind": "none",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            turns = self._read_jsonl(flow_dir / "turns.jsonl")
            self.assertEqual(state["phase_history"][0]["decision"]["issue_kind"], "service_fault")
            self.assertFalse(any(str(row.get("turn_kind") or "") == "fix" for row in turns))

    def test_failed_codex_timeout_overrides_misclassified_agent_cli_fix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(status="failed", text="request timeout while contacting provider"),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "RETRY",
                                "issue_kind": "agent_cli_fault",
                                "followup_kind": "fix",
                                "reason": "execution timed out before the plan was complete",
                                "next_codex_prompt": "continue the plan",
                                "completion_summary": "timed out",
                            },
                            ensure_ascii=False,
                        )
                    ),
                    _receipt(text="resumed and completed"),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "issue_kind": "none",
                                "followup_kind": "none",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            turns = self._read_jsonl(flow_dir / "turns.jsonl")
            self.assertEqual(state["phase_history"][0]["decision"]["issue_kind"], "service_fault")
            self.assertEqual(state["phase_history"][0]["decision"]["followup_kind"], "retry")
            self.assertFalse(any(str(row.get("turn_kind") or "") == "fix" for row in turns))

    def test_auto_fix_limit_pauses_flow_and_requests_operator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root, {"butler_flow": {"enable_fix_turns": True}})
            runner = _ReceiptRunner(
                [
                    _receipt(text="attempt 1 produced a bug"),
                    _receipt(text=json.dumps({"decision": "RETRY", "issue_kind": "agent_cli_fault", "followup_kind": "fix", "reason": "repair codex cli bootstrap one", "next_codex_prompt": "repair codex cli bootstrap one", "completion_summary": "needs fix 1"}, ensure_ascii=False)),
                    _receipt(text="attempt 2 still buggy"),
                    _receipt(text=json.dumps({"decision": "RETRY", "issue_kind": "agent_cli_fault", "followup_kind": "fix", "reason": "repair codex cli bootstrap two", "next_codex_prompt": "repair codex cli bootstrap two", "completion_summary": "needs fix 2"}, ensure_ascii=False)),
                    _receipt(text="attempt 3 still buggy"),
                    _receipt(text=json.dumps({"decision": "RETRY", "issue_kind": "agent_cli_fault", "followup_kind": "fix", "reason": "repair codex cli bootstrap three", "next_codex_prompt": "repair codex cli bootstrap three", "completion_summary": "needs fix 3"}, ensure_ascii=False)),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            events = self._read_jsonl(flow_dir / "events.jsonl")
            self.assertEqual(state["status"], "paused")
            self.assertEqual(state["approval_state"], "operator_required")
            self.assertEqual(state["latest_supervisor_decision"]["decision"], "ask_operator")
            self.assertTrue(any(str(row.get("kind") or "") == "warning" for row in events))
            approval_events = [row for row in events if str(row.get("kind") or "") == "approval_state_changed"]
            self.assertGreaterEqual(len(approval_events), 1)
            self.assertEqual(approval_events[-1]["payload"]["approval_state"], "operator_required")
            self.assertEqual(approval_events[-1]["lane"], "supervisor")
            self.assertEqual(approval_events[-1]["family"], "approval")

    def test_operator_retry_current_phase_keeps_paused_until_real_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = self._app(_ReceiptRunner([]))
            flow_state = _NEW_FLOW_STATE(
                workflow_id="flow_retry_wait",
                workflow_kind=PROJECT_LOOP_KIND,
                workspace_root=str(root),
                goal="retry safely",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            flow_state["status"] = "paused"
            flow_state["approval_state"] = "operator_required"
            flow_dir = _BUILD_FLOW_ROOT(root) / "flow_retry_wait"
            ensure_flow_sidecars(flow_dir, flow_state)
            _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)
            receipt = app._runtime.apply_operator_action(
                cfg=json.loads(Path(config).read_text(encoding="utf-8")),
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                action_type="retry_current_phase",
            )
            self.assertEqual(receipt["action_type"], "retry_current_phase")
            self.assertEqual(flow_state["status"], "paused")
            self.assertEqual(flow_state["approval_state"], "not_required")
            self.assertIn("start a real resume turn", receipt["result_summary"])
            updates = list(flow_state.get("queued_operator_updates") or [])
            self.assertEqual(len(updates), 1)
            self.assertEqual(updates[0]["status"], "queued")
            self.assertTrue(str(updates[0].get("instruction") or "").strip())

    def test_operator_resume_request_keeps_paused_until_runtime_consumes_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = self._app(_ReceiptRunner([]))
            flow_state = _NEW_FLOW_STATE(
                workflow_id="flow_resume_wait",
                workflow_kind=PROJECT_LOOP_KIND,
                workspace_root=str(root),
                goal="resume safely",
                guard_condition="done",
                max_attempts=4,
                max_phase_attempts=2,
            )
            flow_state["status"] = "paused"
            flow_state["approval_state"] = "operator_required"
            flow_dir = _BUILD_FLOW_ROOT(root) / "flow_resume_wait"
            ensure_flow_sidecars(flow_dir, flow_state)
            _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)
            receipt = app._runtime.apply_operator_action(
                cfg=json.loads(Path(config).read_text(encoding="utf-8")),
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                action_type="resume",
            )
            self.assertEqual(receipt["action_type"], "resume")
            self.assertEqual(flow_state["status"], "paused")
            self.assertEqual(flow_state["approval_state"], "not_required")
            self.assertIn("start a real resume turn", receipt["result_summary"])

    def test_operator_control_actions_update_control_profile_via_app_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = self._app(_ReceiptRunner([]))
            flow_state = _NEW_FLOW_STATE(
                workflow_id="flow_control_ops",
                workflow_kind=PROJECT_LOOP_KIND,
                workspace_root=str(root),
                goal="stabilize long flow",
                guard_condition="done",
                max_attempts=0,
                max_phase_attempts=10,
            )
            flow_dir = _BUILD_FLOW_ROOT(root) / "flow_control_ops"
            ensure_flow_sidecars(flow_dir, flow_state)
            _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)

            app._runtime.apply_operator_action(
                cfg=json.loads(Path(config).read_text(encoding="utf-8")),
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                action_type="shrink_packet",
            )
            app._runtime.apply_operator_action(
                cfg=json.loads(Path(config).read_text(encoding="utf-8")),
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                action_type="bind_repo_contract",
                payload={"repo_contract_path": "AGENTS.md"},
            )
            app._runtime.apply_operator_action(
                cfg=json.loads(Path(config).read_text(encoding="utf-8")),
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                action_type="force_doctor",
            )

            control_profile = dict(flow_state.get("control_profile") or {})
            self.assertEqual(control_profile.get("packet_size"), "small")
            self.assertTrue(bool(control_profile.get("force_gate_next_turn")))
            self.assertEqual(control_profile.get("repo_binding_policy"), "explicit")
            self.assertIn("AGENTS.md", list(control_profile.get("repo_contract_paths") or []))
            self.assertTrue(bool(control_profile.get("force_doctor_next_turn")))

    def test_supervisor_and_doctor_runtime_requests_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = self._app(_ReceiptRunner([]))
            flow_state = _NEW_FLOW_STATE(
                workflow_id="flow_runtime_isolation",
                workflow_kind=PROJECT_LOOP_KIND,
                workspace_root=str(root),
                goal="repair repo flow safely",
                guard_condition="done",
                max_attempts=0,
                max_phase_attempts=10,
            )
            flow_dir = _BUILD_FLOW_ROOT(root) / "flow_runtime_isolation"
            ensure_flow_sidecars(flow_dir, flow_state)
            cfg = {"workspace_root": str(root)}

            supervisor_request = app._runtime._build_supervisor_runtime_request(
                cfg,
                flow_id="flow_runtime_isolation",
                flow_state=flow_state,
                flow_dir_path=flow_dir,
            )
            self.assertEqual(supervisor_request["execution_context"], "isolated")
            self.assertIn("supervisor_runtime", supervisor_request["execution_workspace_root"])

            flow_state["active_role_id"] = "doctor"
            doctor_request = app._runtime.build_codex_runtime_request(
                cfg,
                flow_id="flow_runtime_isolation",
                flow_state=flow_state,
                flow_dir_path=flow_dir,
            )
            self.assertEqual(doctor_request["execution_context"], "isolated")
            self.assertIn("doctor_runtime", doctor_request["execution_workspace_root"])

    def test_flow_timeouts_default_to_effectively_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(text="plan ready"),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "issue_kind": "none",
                                "followup_kind": "none",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            self.assertEqual(runner.calls[0]["timeout"], 24 * 60 * 60)
            self.assertEqual(runner.calls[1]["timeout"], 24 * 60 * 60)

    def test_legacy_bug_fix_payload_is_coerced_to_retry_without_fix_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(text="implementation still has a bug"),
                    _receipt(text=json.dumps({"decision": "RETRY", "issue_kind": "bug", "followup_kind": "fix", "reason": "fix the concrete business bug", "next_codex_prompt": "", "completion_summary": "needs bug retry"}, ensure_ascii=False)),
                    _receipt(text="business bug fixed"),
                    _receipt(text=json.dumps({"decision": "COMPLETE", "issue_kind": "none", "followup_kind": "none", "reason": "done", "next_codex_prompt": "", "completion_summary": "done"}, ensure_ascii=False)),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            turns = self._read_jsonl(flow_dir / "turns.jsonl")
            self.assertEqual(state["phase_history"][0]["decision"]["issue_kind"], "bug")
            self.assertEqual(state["phase_history"][0]["decision"]["followup_kind"], "retry")
            self.assertFalse(any(str(row.get("turn_kind") or "") == "fix" for row in turns))

    def test_resume_ignores_failed_phase_retries_when_recomputing_phase_budget(self) -> None:
        if _NEW_FLOW_STATE is None or _WRITE_JSON_ATOMIC is None:
            raise AssertionError("butler_flow must expose _new_flow_state/_write_json_atomic for tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            flow_id = "flow_stale_phase_budget"
            flow_dir = _BUILD_FLOW_ROOT(root) / flow_id
            flow_state = _NEW_FLOW_STATE(
                workflow_id=flow_id,
                workflow_kind=PROJECT_LOOP_KIND,
                workspace_root=str(root),
                goal="recover the launcher",
                guard_condition="review passed",
                max_attempts=8,
                max_phase_attempts=1,
                codex_session_id="thread-existing",
                resume_source="workflow_id",
            )
            flow_state["status"] = "failed"
            flow_state["attempt_count"] = 2
            flow_state["phase_attempt_count"] = 2
            flow_state["phase_history"] = [
                {
                    "at": "2026-03-31 02:41:43",
                    "attempt_no": 1,
                    "phase": "plan",
                    "codex_status": "failed",
                    "cursor_status": "completed",
                    "decision": {"decision": "RETRY", "next_phase": "plan", "reason": "interrupted"},
                },
                {
                    "at": "2026-03-31 02:42:43",
                    "attempt_no": 2,
                    "phase": "plan",
                    "codex_status": "failed",
                    "cursor_status": "completed",
                    "decision": {"decision": "RETRY", "next_phase": "plan", "reason": "interrupted again"},
                },
            ]
            _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)
            runner = _ReceiptRunner(
                [
                    _receipt(text="plan recovered"),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "", "reason": "plan done", "next_codex_prompt": "", "completion_summary": "plan"}, ensure_ascii=False)),
                    _receipt(text="implementation done"),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "", "reason": "imp done", "next_codex_prompt": "", "completion_summary": "imp"}, ensure_ascii=False)),
                    _receipt(text="review passed"),
                    _receipt(text=json.dumps({"decision": "COMPLETE", "next_phase": "done", "reason": "review done", "next_codex_prompt": "", "completion_summary": "done"}, ensure_ascii=False)),
                ]
            )
            app = self._app(runner)
            args = argparse.Namespace(
                command="resume",
                config=config,
                workflow_id=flow_id,
                last=False,
                codex_session_id="",
                kind=PROJECT_LOOP_KIND,
                goal="",
                guard_condition="",
                max_attempts=0,
                max_phase_attempts=0,
                no_stream=True,
            )
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.resume(args)
            self.assertEqual(rc, 0)
            state = self._flow_state(flow_dir)
            self.assertEqual(state["status"], "completed")
            self.assertEqual(state["attempt_count"], 5)
            self.assertEqual(state["phase_attempt_count"], 1)

    def test_resume_flow_id_takes_priority_over_codex_session_id(self) -> None:
        if _NEW_FLOW_STATE is None or _WRITE_JSON_ATOMIC is None:
            raise AssertionError("butler_flow must expose _new_flow_state/_write_json_atomic for tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            flow_id = "flow_existing"
            flow_dir = _BUILD_FLOW_ROOT(root) / flow_id
            flow_state = _NEW_FLOW_STATE(
                workflow_id=flow_id,
                workflow_kind=SINGLE_GOAL_KIND,
                workspace_root=str(root),
                goal="resume local state",
                guard_condition="done",
                max_attempts=6,
                max_phase_attempts=3,
                codex_session_id="thread-local",
                resume_source="workflow_id",
            )
            flow_state["status"] = "running"
            flow_state["role_pack_id"] = "research_flow"
            flow_state["execution_context"] = "isolated"
            _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)
            runner = _ReceiptRunner(
                [
                    _receipt(text="local resume done"),
                    _receipt(text=json.dumps({"decision": "COMPLETE", "reason": "pass", "next_codex_prompt": "", "completion_summary": "done"}, ensure_ascii=False)),
                ]
            )
            app = self._app(runner)
            args = argparse.Namespace(
                command="resume",
                config=config,
                workflow_id=flow_id,
                codex_session_id="thread-external",
                kind=PROJECT_LOOP_KIND,
                goal="ignored",
                guard_condition="ignored",
                max_attempts=0,
                max_phase_attempts=0,
                no_stream=True,
            )
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.resume(args)
            self.assertEqual(rc, 0)
            codex_call = next(call for call in runner.calls if call["runtime_request"].get("cli") == "codex")
            self.assertEqual(codex_call["runtime_request"]["codex_mode"], "resume")
            self.assertEqual(codex_call["runtime_request"]["codex_session_id"], "thread-local")
            self.assertEqual(codex_call["runtime_request"]["execution_context"], "isolated")

    def test_resume_codex_session_id_creates_new_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(text="external resume done"),
                    _receipt(text=json.dumps({"decision": "COMPLETE", "reason": "done", "next_codex_prompt": "", "completion_summary": "done"}, ensure_ascii=False)),
                ]
            )
            app = self._app(runner)
            args = argparse.Namespace(
                command="resume",
                config=config,
                workflow_id="",
                codex_session_id="thread-external",
                kind=SINGLE_GOAL_KIND,
                goal="resume external",
                guard_condition="done",
                max_attempts=0,
                max_phase_attempts=0,
                no_stream=True,
            )
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.resume(args)
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            self.assertEqual(state["resume_source"], "codex_session_id")
            self.assertEqual(state["execution_context"], "repo_bound")
            codex_call = next(call for call in runner.calls if call["runtime_request"].get("cli") == "codex")
            self.assertEqual(codex_call["runtime_request"]["codex_mode"], "resume")
            self.assertEqual(codex_call["runtime_request"]["codex_session_id"], "thread-external")

    def test_butler_flow_codex_calls_guard_oauth_remote_mcp_servers_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(text="implemented"),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            codex_call = next(call for call in runner.calls if call["runtime_request"].get("cli") == "codex")
            self.assertNotIn("profile", codex_call["runtime_request"])
            overrides = codex_call["runtime_request"].get("config_overrides") or []
            self.assertTrue(any("mcp_servers.stripe=" in item for item in overrides))
            self.assertTrue(any("mcp_servers.supabase=" in item for item in overrides))
            self.assertTrue(any("mcp_servers.vercel=" in item for item in overrides))

    def test_butler_flow_can_explicitly_clear_default_remote_mcp_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root, {"butler_flow": {"disable_mcp_servers": []}})
            runner = _ReceiptRunner(
                [
                    _receipt(text="implemented"),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            codex_call = next(call for call in runner.calls if call["runtime_request"].get("cli") == "codex")
            overrides = codex_call["runtime_request"].get("config_overrides") or []
            self.assertEqual(overrides, [])

    def test_butler_flow_can_explicitly_disable_remote_mcp_servers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(
                root,
                {"butler_flow": {"disable_mcp_servers": ["stripe", "supabase", "vercel"]}},
            )
            runner = _ReceiptRunner(
                [
                    _receipt(text="implemented"),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            codex_call = next(call for call in runner.calls if call["runtime_request"].get("cli") == "codex")
            overrides = codex_call["runtime_request"].get("config_overrides") or []
            self.assertTrue(any("mcp_servers.stripe=" in item for item in overrides))
            self.assertTrue(any("mcp_servers.supabase=" in item for item in overrides))
            self.assertTrue(any("mcp_servers.vercel=" in item for item in overrides))

    def test_operator_action_append_instruction_writes_action_receipt(self) -> None:
        if _NEW_FLOW_STATE is None or _WRITE_JSON_ATOMIC is None:
            raise AssertionError("butler_flow must expose _new_flow_state/_write_json_atomic for tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            flow_id = "flow_action_demo"
            flow_dir = _BUILD_FLOW_ROOT(root) / flow_id
            flow_state = _NEW_FLOW_STATE(
                workflow_id=flow_id,
                workflow_kind=SINGLE_GOAL_KIND,
                workspace_root=str(root),
                goal="apply operator action",
                guard_condition="done",
                max_attempts=6,
                max_phase_attempts=3,
            )
            _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)
            app = self._app(_ReceiptRunner([]))
            args = argparse.Namespace(
                command="action",
                config=config,
                flow_id=flow_id,
                workflow_id="",
                last=False,
                type="append_instruction",
                instruction="please retry carefully",
            )
            rc = app.action(args)
            self.assertEqual(rc, 0)
            state = self._flow_state(flow_dir)
            self.assertEqual(state["queued_operator_updates"][0]["instruction"], "please retry carefully")
            self.assertEqual(state["queued_operator_updates"][0]["status"], "queued")
            actions = self._read_jsonl(flow_dir / "actions.jsonl")
            self.assertEqual(actions[-1]["action_type"], "append_instruction")

    def test_operator_control_actions_update_control_profile_with_config_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = self._app(_ReceiptRunner([]))
            flow_state = _NEW_FLOW_STATE(
                workflow_id="flow_control_actions",
                workflow_kind=PROJECT_LOOP_KIND,
                workspace_root=str(root),
                goal="ship bounded progress",
                guard_condition="done",
                max_attempts=0,
                max_phase_attempts=10,
            )
            flow_dir = _BUILD_FLOW_ROOT(root) / "flow_control_actions"
            ensure_flow_sidecars(flow_dir, flow_state)
            _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)

            shrink_receipt = app._runtime.apply_operator_action(
                cfg=json.loads(Path(config).read_text(encoding="utf-8")),
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                action_type="shrink_packet",
            )
            bind_receipt = app._runtime.apply_operator_action(
                cfg=json.loads(Path(config).read_text(encoding="utf-8")),
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                action_type="bind_repo_contract",
                payload={"repo_contract_path": "AGENTS.md"},
            )
            doctor_receipt = app._runtime.apply_operator_action(
                cfg=json.loads(Path(config).read_text(encoding="utf-8")),
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                action_type="force_doctor",
            )

            control_profile = dict(flow_state.get("control_profile") or {})
            self.assertEqual(shrink_receipt["action_type"], "shrink_packet")
            self.assertEqual(bind_receipt["action_type"], "bind_repo_contract")
            self.assertEqual(doctor_receipt["action_type"], "force_doctor")
            self.assertEqual(control_profile["packet_size"], "small")
            self.assertTrue(control_profile["force_gate_next_turn"])
            self.assertTrue(control_profile["force_doctor_next_turn"])
            self.assertEqual(control_profile["repo_binding_policy"], "explicit")
            self.assertEqual(control_profile["repo_contract_paths"], ["AGENTS.md"])

    def test_manager_and_supervisor_use_isolated_codex_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            flow_state = _NEW_FLOW_STATE(
                workflow_id="flow_isolated_roles",
                workflow_kind=PROJECT_LOOP_KIND,
                workspace_root=str(root),
                goal="ship bounded progress",
                guard_condition="done",
                max_attempts=0,
                max_phase_attempts=10,
            )
            app = self._app(_ReceiptRunner([]))
            flow_dir = _BUILD_FLOW_ROOT(root) / "flow_isolated_roles"
            ensure_flow_sidecars(flow_dir, flow_state)
            _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)

            supervisor_request = app._runtime._build_supervisor_runtime_request(
                json.loads(Path(config).read_text(encoding="utf-8")),
                flow_id="flow_isolated_roles",
                flow_state=flow_state,
                flow_dir_path=flow_dir,
            )
            flow_state["active_role_id"] = "doctor"
            doctor_request = app._runtime.build_codex_runtime_request(
                json.loads(Path(config).read_text(encoding="utf-8")),
                flow_id="flow_isolated_roles",
                flow_state=flow_state,
                flow_dir_path=flow_dir,
            )

            self.assertEqual(supervisor_request["execution_context"], "isolated")
            self.assertIn("supervisor_runtime", supervisor_request["execution_workspace_root"])
            self.assertEqual(doctor_request["execution_context"], "isolated")
            self.assertIn("doctor_runtime", doctor_request["execution_workspace_root"])

    def test_operator_control_actions_update_control_profile_with_unbind(self) -> None:
        if _NEW_FLOW_STATE is None or _WRITE_JSON_ATOMIC is None:
            raise AssertionError("butler_flow must expose _new_flow_state/_write_json_atomic for tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flow_id = "flow_control_actions"
            flow_dir = _BUILD_FLOW_ROOT(root) / flow_id
            flow_state = _NEW_FLOW_STATE(
                workflow_id=flow_id,
                workflow_kind=PROJECT_LOOP_KIND,
                workspace_root=str(root),
                goal="ship a bounded change safely",
                guard_condition="done",
                max_attempts=0,
                max_phase_attempts=6,
            )
            ensure_flow_sidecars(flow_dir, flow_state)
            _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)
            app = self._app(_ReceiptRunner([]))

            shrink_receipt = app._runtime.apply_operator_action(
                cfg={},
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                action_type="shrink_packet",
            )
            self.assertEqual(shrink_receipt["action_type"], "shrink_packet")
            self.assertEqual(flow_state["control_profile"]["packet_size"], "small")
            self.assertTrue(flow_state["control_profile"]["force_gate_next_turn"])

            bind_receipt = app._runtime.apply_operator_action(
                cfg={},
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                action_type="bind_repo_contract",
                payload={"repo_contract_path": "AGENTS.md"},
            )
            self.assertEqual(bind_receipt["action_type"], "bind_repo_contract")
            self.assertEqual(flow_state["control_profile"]["repo_binding_policy"], "explicit")
            self.assertIn("AGENTS.md", flow_state["control_profile"]["repo_contract_paths"])

            unbind_receipt = app._runtime.apply_operator_action(
                cfg={},
                flow_dir_path=flow_dir,
                flow_state=flow_state,
                action_type="unbind_repo_contract",
            )
            self.assertEqual(unbind_receipt["action_type"], "unbind_repo_contract")
            self.assertEqual(flow_state["control_profile"]["repo_binding_policy"], "disabled")
            self.assertEqual(flow_state["control_profile"]["repo_contract_paths"], [])

    def test_build_codex_prompt_appends_explicit_repo_contract(self) -> None:
        if _NEW_FLOW_STATE is None:
            raise AssertionError("butler_flow must expose _new_flow_state for tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("Repo contract: keep changes narrow.\n", encoding="utf-8")
            flow_id = "flow_repo_contract_prompt"
            flow_dir = _BUILD_FLOW_ROOT(root) / flow_id
            flow_state = _NEW_FLOW_STATE(
                workflow_id=flow_id,
                workflow_kind=PROJECT_LOOP_KIND,
                workspace_root=str(root),
                goal="ship safely",
                guard_condition="done",
                max_attempts=0,
                max_phase_attempts=6,
            )
            flow_state["control_profile"]["repo_binding_policy"] = "explicit"
            flow_state["control_profile"]["repo_contract_paths"] = ["AGENTS.md"]
            ensure_flow_sidecars(flow_dir, flow_state)
            app = self._app(_ReceiptRunner([]))
            prompt = app._runtime.build_codex_prompt({}, flow_dir, flow_state, attempt_no=1, phase_attempt_no=1)
            self.assertIn("Explicit repo contracts:", prompt)
            self.assertIn("[repo contract: AGENTS.md]", prompt)
            self.assertIn("Repo contract: keep changes narrow.", prompt)

    def test_action_parser_accepts_control_actions(self) -> None:
        parser = flow_cli.build_arg_parser()
        args = parser.parse_args(
            [
                "action",
                "--flow-id",
                "flow_demo",
                "--type",
                "bind_repo_contract",
                "--repo-contract-path",
                "AGENTS.md",
            ]
        )
        self.assertEqual(args.type, "bind_repo_contract")
        self.assertEqual(args.repo_contract_path, "AGENTS.md")

    def test_compile_packet_delta_profile_compacts_flow_payload(self) -> None:
        flow_state = _NEW_FLOW_STATE(
            workflow_id="flow_compact_demo",
            workflow_kind=MANAGED_FLOW_KIND,
            workspace_root="/tmp",
            goal="ship compact packet",
            guard_condition="verified",
            max_attempts=0,
            max_phase_attempts=10,
        )
        flow_state["phase_history"] = [
            {
                "at": f"2026-04-02 10:0{index}:00",
                "attempt_no": index + 1,
                "phase": "imp",
                "decision": {"decision": "RETRY", "reason": f"reason {index}"},
            }
            for index in range(4)
        ]
        flow_state["queued_operator_updates"] = [{"status": "queued", "instruction": "narrow the next work package"}]
        flow_state["bundle_manifest"] = {"bundle_root": "bundle/demo"}
        flow_state["context_governor"] = {"mode": "compact"}
        full_packet = compile_packet(
            target_role="implementer",
            session_mode="warm",
            load_profile="full",
            flow_board=build_flow_board(flow_state),
            role_board=build_role_board(
                flow_state=flow_state,
                role_id="implementer",
                role_kind="stable",
                role_pack_id="coding_flow",
                role_turn_no=1,
                role_session_id="thread-1",
                role_charter="Role: implementer",
            ),
            turn_task_packet=build_turn_task_packet(
                role_id="implementer",
                workflow_kind=MANAGED_FLOW_KIND,
                phase="imp",
                turn_kind="execute",
                attempt_no=5,
                phase_attempt_no=2,
                next_instruction="finish the remaining bounded delta",
            ),
        )
        delta_packet = compile_packet(
            target_role="implementer",
            session_mode="warm",
            load_profile="delta",
            flow_board=build_flow_board(flow_state),
            role_board=build_role_board(
                flow_state=flow_state,
                role_id="implementer",
                role_kind="stable",
                role_pack_id="coding_flow",
                role_turn_no=1,
                role_session_id="thread-1",
                role_charter="Role: implementer",
            ),
            turn_task_packet=build_turn_task_packet(
                role_id="implementer",
                workflow_kind=MANAGED_FLOW_KIND,
                phase="imp",
                turn_kind="execute",
                attempt_no=5,
                phase_attempt_no=2,
                next_instruction="finish the remaining bounded delta",
            ),
        )
        self.assertGreater(len(full_packet["flow_board"]["recent_phase_history"]), len(delta_packet["flow_board"]["recent_phase_history"]))
        self.assertTrue(full_packet["flow_board"]["bundle_manifest"])
        self.assertEqual(delta_packet["flow_board"]["bundle_manifest"], {})
        self.assertLessEqual(len(delta_packet["turn_task_packet"]["next_instruction"]), len(full_packet["turn_task_packet"]["next_instruction"]))

    def test_runtime_budget_with_queued_operator_update_pauses_instead_of_failing(self) -> None:
        if _NEW_FLOW_STATE is None or _WRITE_JSON_ATOMIC is None:
            raise AssertionError("butler_flow must expose _new_flow_state/_write_json_atomic for tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flow_id = "flow_runtime_budget_demo"
            flow_dir = _BUILD_FLOW_ROOT(root) / flow_id
            flow_state = _NEW_FLOW_STATE(
                workflow_id=flow_id,
                workflow_kind=MANAGED_FLOW_KIND,
                workspace_root=str(root),
                goal="respect runtime budget",
                guard_condition="done",
                max_attempts=0,
                max_phase_attempts=10,
            )
            flow_state["runtime_started_at"] = "2026-04-01 00:00:00"
            flow_state["max_runtime_seconds"] = 1
            flow_state["queued_operator_updates"] = [
                {
                    "update_id": "op_update_1",
                    "instruction": "apply my late supplement",
                    "status": "queued",
                    "created_at": "2026-04-02 00:00:00",
                }
            ]
            _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)
            app = self._app(_ReceiptRunner([]))
            rc = app._runtime.run_flow_loop({}, flow_dir, flow_state, stream_enabled=False)
            self.assertEqual(rc, 0)
            state = self._flow_state(flow_dir)
            self.assertEqual(state["status"], "paused")
            self.assertIn("runtime budget reached", state["last_completion_summary"])

    def test_running_flow_honors_external_pause_after_current_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner([])
            app = self._app(runner)

            def inject_pause(*_args, **_kwargs):
                flow_dir = self._flow_dirs(root)[0]
                flow_state = self._flow_state(flow_dir)
                app._runtime.apply_operator_action(
                    cfg={},
                    flow_dir_path=flow_dir,
                    flow_state=flow_state,
                    action_type="pause",
                )
                _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)
                return _receipt(text="attempted once")

            runner._responses.extend(
                [
                    inject_pause,
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "RETRY",
                                "reason": "more work remains",
                                "next_codex_prompt": "continue",
                                "completion_summary": "retry later",
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            self.assertEqual(state["status"], "paused")
            self.assertEqual(state["attempt_count"], 1)
            codex_calls = [call for call in runner.calls if call["runtime_request"].get("cli") == "codex"]
            self.assertEqual(len(codex_calls), 1)

    def test_running_flow_uses_external_append_instruction_on_next_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner([])
            app = self._app(runner)

            def inject_instruction(*_args, **_kwargs):
                flow_dir = self._flow_dirs(root)[0]
                flow_state = self._flow_state(flow_dir)
                app._runtime.apply_operator_action(
                    cfg={},
                    flow_dir_path=flow_dir,
                    flow_state=flow_state,
                    action_type="append_instruction",
                    payload={"instruction": "operator override: focus on failing tests first"},
                )
                _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)
                return _receipt(text="first attempt incomplete")

            runner._responses.extend(
                [
                    inject_instruction,
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "RETRY",
                                "reason": "needs follow-up",
                                "next_codex_prompt": "",
                                "completion_summary": "retry",
                            },
                            ensure_ascii=False,
                        )
                    ),
                    _receipt(text="second attempt complete"),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(self._run_args(config=config))
            self.assertEqual(rc, 0)
            codex_calls = [call for call in runner.calls if call["runtime_request"].get("cli") == "codex"]
            self.assertEqual(len(codex_calls), 2)
            self.assertIn("operator override: focus on failing tests first", codex_calls[1]["prompt"])
            flow_dir = self._flow_dirs(root)[0]
            actions = self._read_jsonl(flow_dir / "actions.jsonl")
            self.assertEqual(actions[-1]["action_type"], "append_instruction")

    def test_legacy_state_file_can_be_loaded_and_migrated_on_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            flow_id = "flow_legacy"
            flow_dir = _BUILD_FLOW_ROOT(root) / flow_id
            flow_dir.mkdir(parents=True, exist_ok=True)
            legacy_state = {
                "workflow_id": flow_id,
                "workflow_kind": SINGLE_GOAL_KIND,
                "workspace_root": str(root),
                "goal": "legacy resume",
                "guard_condition": "done",
                "status": "running",
                "attempt_count": 0,
                "max_attempts": 3,
                "max_phase_attempts": 2,
            }
            (flow_dir / "flow_state.json").write_text(json.dumps(legacy_state, ensure_ascii=False, indent=2), encoding="utf-8")
            runner = _ReceiptRunner(
                [
                    _receipt(text="legacy progressed"),
                    _receipt(text=json.dumps({"decision": "COMPLETE", "reason": "done", "next_codex_prompt": "", "completion_summary": "done"}, ensure_ascii=False)),
                ]
            )
            app = self._app(runner)
            args = argparse.Namespace(
                command="resume",
                config=config,
                flow_id=flow_id,
                workflow_id="",
                last=False,
                codex_session_id="",
                kind=SINGLE_GOAL_KIND,
                goal="",
                guard_condition="",
                max_attempts=0,
                max_phase_attempts=0,
                no_stream=True,
            )
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.resume(args)
            self.assertEqual(rc, 0)
            state = self._flow_state(flow_dir)
            self.assertIn("latest_supervisor_decision", state)
            self.assertIn("latest_judge_decision", state)
            self.assertEqual(state["status"], "completed")

    def test_status_reads_legacy_state_and_migrates_to_workflow_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            flow_id = "flow_legacy_status"
            flow_dir = _BUILD_FLOW_ROOT(root) / flow_id
            flow_dir.mkdir(parents=True, exist_ok=True)
            legacy_state = {
                "workflow_id": flow_id,
                "workflow_kind": SINGLE_GOAL_KIND,
                "workspace_root": str(root),
                "goal": "inspect legacy status",
                "guard_condition": "done",
                "status": "paused",
                "current_phase": SINGLE_GOAL_PHASE,
                "attempt_count": 1,
                "max_attempts": 3,
                "max_phase_attempts": 2,
                "updated_at": "2026-03-31 12:00:00",
            }
            (flow_dir / "flow_state.json").write_text(json.dumps(legacy_state, ensure_ascii=False, indent=2), encoding="utf-8")
            app = self._app(_ReceiptRunner([]))
            args = argparse.Namespace(command="status", config=config, flow_id=flow_id, workflow_id="", last=False, json=False)
            rc = app.status(args)
            self.assertEqual(rc, 0)
            self.assertTrue((flow_dir / "workflow_state.json").exists())
            output = app._stdout.getvalue()
            self.assertIn("workflow_id=flow_legacy_status", output)
            self.assertIn("status=paused", output)

    def test_display_degrades_to_plain_for_non_tty_streams(self) -> None:
        app = self._app(_ReceiptRunner([]))
        self.assertEqual(type(app._display).__name__, "FlowDisplay")

    def test_prepare_new_flow_records_launch_mode_and_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = self._app(_ReceiptRunner([]))
            args = self._new_args(
                config=config,
                kind=SINGLE_GOAL_KIND,
                launch_mode="flow",
                execution_level="medium",
                catalog_flow_id="project_loop",
                goal="ship catalog",
                guard_condition="done",
            )
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                prepared = app.prepare_new_flow(args)
            state = prepared.flow_state
            self.assertEqual(state.get("launch_mode"), "flow")
            self.assertEqual(state.get("catalog_flow_id"), "project_loop")
            self.assertEqual(state.get("workflow_kind"), PROJECT_LOOP_KIND)
            self.assertEqual(state.get("execution_mode"), "medium")
            self.assertEqual(state.get("execution_context"), "repo_bound")

    def test_prepare_new_flow_rejects_high_execution_level(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = self._app(_ReceiptRunner([]))
            args = self._new_args(
                config=config,
                kind=PROJECT_LOOP_KIND,
                launch_mode="flow",
                execution_level="high",
                catalog_flow_id="project_loop",
                goal="ship",
                guard_condition="done",
            )
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                with self.assertRaises(ValueError):
                    app.prepare_new_flow(args)

    def test_prepare_new_flow_free_routes_to_design_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = self._app(_ReceiptRunner([]))
            args = self._new_args(
                config=config,
                kind=MANAGED_FLOW_KIND,
                launch_mode="flow",
                execution_level="simple",
                catalog_flow_id="free",
                goal="design it",
                guard_condition="review passes",
            )
            built = {
                "summary": "draft ready",
                "goal": "designed goal",
                "guard_condition": "designed guard",
                "workflow_kind": MANAGED_FLOW_KIND,
                "phase_plan": [
                    {
                        "phase_id": "discover",
                        "title": "Discover",
                        "objective": "discover",
                        "done_when": "discover done",
                        "retry_phase_id": "discover",
                        "fallback_phase_id": "discover",
                        "next_phase_id": "",
                    }
                ],
            }
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True), \
                 mock.patch.object(app, "_run_free_design_loop", return_value=built) as mocked_design:
                prepared = app.prepare_new_flow(args)
            mocked_design.assert_called_once()
            state = prepared.flow_state
            self.assertEqual(state.get("catalog_flow_id"), "free")
            self.assertEqual(state.get("workflow_kind"), MANAGED_FLOW_KIND)
            self.assertEqual(state.get("goal"), "designed goal")
            self.assertEqual(state.get("guard_condition"), "designed guard")
            self.assertTrue(state.get("phase_plan"))
            self.assertIn("manage_handoff", state)
            self.assertEqual(state["manage_handoff"].get("summary"), "draft ready")
            flow_dir = self._flow_dirs(root)[0]
            events = self._read_jsonl(flow_dir / "events.jsonl")
            self.assertTrue(any(str(row.get("kind") or "") == "manage_handoff_ready" for row in events))
            manage_event = next(row for row in events if str(row.get("kind") or "") == "manage_handoff_ready")
            self.assertEqual(manage_event["lane"], "supervisor")
            self.assertEqual(manage_event["family"], "handoff")

    def test_prepare_new_flow_can_launch_from_template_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            _WRITE_JSON_ATOMIC(
                root / "butler_main" / "butler_bot_code" / "assets" / "flows" / "templates" / "template_demo.json",
                {
                    "flow_id": "template_demo",
                    "label": "Template Demo",
                    "workflow_kind": MANAGED_FLOW_KIND,
                    "default_role_pack": "research_flow",
                    "role_guidance": {
                        "suggested_roles": ["planner", "researcher", "reviewer"],
                        "suggested_specialists": ["creator"],
                        "activation_hints": ["when missing paper formatting or LaTeX capability blocks delivery"],
                    },
                    "phase_plan": [
                        {
                            "phase_id": "scan",
                            "title": "Scan",
                            "objective": "scan sources",
                            "done_when": "sources mapped",
                            "retry_phase_id": "scan",
                            "fallback_phase_id": "scan",
                            "next_phase_id": "synthesize",
                        },
                        {
                            "phase_id": "synthesize",
                            "title": "Synthesize",
                            "objective": "write synthesis",
                            "done_when": "report ready",
                            "retry_phase_id": "synthesize",
                            "fallback_phase_id": "scan",
                            "next_phase_id": "",
                        },
                    ],
                    "updated_at": "2026-03-31 10:00:00",
                },
            )
            app = self._app(_ReceiptRunner([]))
            args = self._new_args(
                config=config,
                kind=MANAGED_FLOW_KIND,
                launch_mode="flow",
                execution_level="medium",
                catalog_flow_id="template:template_demo",
                goal="run the prepared template",
                guard_condition="summary delivered",
            )
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                prepared = app.prepare_new_flow(args)
            state = prepared.flow_state
            self.assertEqual(state.get("catalog_flow_id"), "template:template_demo")
            self.assertEqual(state.get("workflow_kind"), MANAGED_FLOW_KIND)
            self.assertEqual(state.get("current_phase"), "scan")
            self.assertEqual(state.get("phase_plan")[0]["phase_id"], "scan")
            self.assertEqual(state.get("source_asset_key"), "template:template_demo")
            self.assertEqual(state.get("source_asset_kind"), "template")
            self.assertEqual(state.get("bundle_manifest", {}).get("supervisor_ref"), str((self._flow_dirs(root)[0] / "bundle" / "supervisor.md").resolve()))
            self.assertEqual(state.get("bundle_manifest", {}).get("doctor_ref"), str((self._flow_dirs(root)[0] / "bundle" / "doctor.md").resolve()))
            self.assertEqual(state.get("phase_plan")[1]["phase_id"], "synthesize")
            self.assertEqual(state.get("execution_mode"), "medium")
            self.assertEqual(state.get("role_pack_id"), "research_flow")
            self.assertEqual(state.get("execution_context"), "isolated")
            self.assertEqual(state.get("role_guidance", {}).get("suggested_roles"), ["planner", "researcher", "reviewer"])

    def test_exec_receipt_includes_execution_context_and_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = self._app(_ReceiptRunner([]))
            receipt = app._build_exec_receipt(
                flow_path=root / "flow_receipt",
                flow_state={
                    "workflow_id": "flow_receipt",
                    "workflow_kind": SINGLE_GOAL_KIND,
                    "status": "completed",
                    "execution_context": "isolated",
                    "last_codex_receipt": {
                        "metadata": {
                            "execution_workspace_root": str(root / ".isolated" / "flow_receipt"),
                        }
                    },
                },
                return_code=0,
            )
        self.assertEqual(receipt["execution_context"], "isolated")
        self.assertEqual(receipt["execution_workspace_root"], str(root / ".isolated" / "flow_receipt"))

    def test_current_role_prompt_covers_lightweight_specialists(self) -> None:
        creator_prompt = current_role_prompt(role_pack_id="coding_flow", role_id="creator", flow_state={"role_sessions": {}})
        doctor_prompt = current_role_prompt(role_pack_id="coding_flow", role_id="doctor", flow_state={"role_sessions": {}})
        product_prompt = current_role_prompt(role_pack_id="coding_flow", role_id="product-manager", flow_state={"role_sessions": {}})
        user_prompt = current_role_prompt(role_pack_id="coding_flow", role_id="user-simulator", flow_state={"role_sessions": {}})
        self.assertIn("Role: creator", creator_prompt)
        self.assertIn("Role: doctor", doctor_prompt)
        self.assertIn("Role: product-manager", product_prompt)
        self.assertIn("Role: user-simulator", user_prompt)

    def test_run_new_materializes_instance_bundle_with_doctor_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(
                        text="implemented",
                        metadata={"external_session": {"provider": "codex", "thread_id": "thread-bundle", "resume_capable": True}},
                        agent_id="butler_flow.codex_executor",
                    ),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "reason": "done",
                                "next_codex_prompt": "",
                                "completion_summary": "done",
                            },
                            ensure_ascii=False,
                        ),
                        agent_id="butler_flow.cursor_judge",
                    ),
                ]
            )
            app = self._app(runner)
            args = self._new_args(config=config, kind=SINGLE_GOAL_KIND, execution_level="medium")
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app.run_new(args)
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            definition = self._read_json(flow_dir / "flow_definition.json")
            self.assertTrue((flow_dir / "bundle" / "doctor.md").exists())
            self.assertTrue((flow_dir / "bundle" / "skills" / "doctor" / "SKILL.md").exists())
            self.assertEqual(definition["bundle_manifest"]["doctor_ref"], str((flow_dir / "bundle" / "doctor.md").resolve()))
            self.assertEqual(definition["bundle_manifest"]["doctor_skill_ref"], str((flow_dir / "bundle" / "skills" / "doctor" / "SKILL.md").resolve()))

    def test_heuristic_supervisor_spawns_doctor_for_resume_no_rollout_failure(self) -> None:
        if _NEW_FLOW_STATE is None or _WRITE_JSON_ATOMIC is None or _BUILD_FLOW_ROOT is None:
            raise AssertionError("butler_flow must expose build/new/write helpers for tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flow_dir = _BUILD_FLOW_ROOT(root) / "flow_doctor_resume"
            flow_state = _NEW_FLOW_STATE(
                workflow_id="flow_doctor_resume",
                workflow_kind=SINGLE_GOAL_KIND,
                workspace_root=str(root),
                goal="repair the flow and continue",
                guard_condition="blocked task resumes safely",
                max_attempts=2,
                max_phase_attempts=0,
            )
            flow_state["execution_mode"] = "medium"
            flow_state["session_strategy"] = "role_bound"
            flow_state["active_role_id"] = "implementer"
            flow_state["pending_codex_prompt"] = "continue the blocked task"
            flow_state["doctor_policy"] = {
                "enabled": True,
                "activation_rules": ["same_resume_failure", "session_binding_invalid"],
                "repair_scope": "runtime_assets_first",
                "framework_bug_action": "pause",
                "max_rounds_per_episode": 1,
            }
            flow_state["role_sessions"] = {
                "implementer": {
                    "role_id": "implementer",
                    "session_id": "thread-stale",
                    "status": "ready",
                    "updated_at": "2026-04-02 19:29:08",
                }
            }
            flow_state["last_codex_receipt"] = {
                "status": "failed",
                "summary": "Error: thread/resume: thread/resume failed: no rollout found for thread id thread-stale",
                "output_text": "Error: thread/resume: thread/resume failed: no rollout found for thread id thread-stale",
                "metadata": {
                    "runtime_request": {"codex_mode": "resume"},
                    "external_session": {
                        "provider": "codex",
                        "thread_id": "",
                        "requested_session_id": "thread-stale",
                        "resume_capable": False,
                    },
                },
            }
            ensure_flow_sidecars(flow_dir, flow_state)
            _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)
            runner = _ReceiptRunner(
                [
                    _receipt(
                        text="doctor repaired the stale runtime binding and prepared the flow to continue",
                        metadata={"external_session": {"provider": "codex", "thread_id": "thread-doctor", "resume_capable": True}},
                        agent_id="butler_flow.codex_executor",
                    ),
                    _receipt(
                        text=json.dumps(
                            {
                                "decision": "COMPLETE",
                                "reason": "recovery verified",
                                "next_codex_prompt": "",
                                "completion_summary": "recovery done",
                            },
                            ensure_ascii=False,
                        ),
                        agent_id="butler_flow.cursor_judge",
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app._runtime.run_flow_loop({"workspace_root": str(root)}, flow_dir, flow_state, stream_enabled=False)
            self.assertEqual(rc, 0)
            self.assertEqual(runner.calls[0]["runtime_request"]["codex_mode"], "exec")
            self.assertEqual(runner.calls[0]["runtime_request"]["codex_session_id"], "")
            state = self._flow_state(flow_dir)
            self.assertEqual(state["role_sessions"]["implementer"]["status"], "resume_failed")
            self.assertEqual(state["role_sessions"]["doctor"]["session_id"], "thread-doctor")
            turns = self._read_jsonl(flow_dir / "turns.jsonl")
            self.assertTrue(any(row.get("role_id") == "doctor" and row.get("turn_kind") == "recover" for row in turns))

    def test_doctor_framework_bug_output_pauses_flow_for_operator(self) -> None:
        if _NEW_FLOW_STATE is None or _WRITE_JSON_ATOMIC is None or _BUILD_FLOW_ROOT is None:
            raise AssertionError("butler_flow must expose build/new/write helpers for tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flow_dir = _BUILD_FLOW_ROOT(root) / "flow_doctor_pause"
            flow_state = _NEW_FLOW_STATE(
                workflow_id="flow_doctor_pause",
                workflow_kind=SINGLE_GOAL_KIND,
                workspace_root=str(root),
                goal="repair the flow and continue",
                guard_condition="blocked task resumes safely",
                max_attempts=2,
                max_phase_attempts=0,
            )
            flow_state["execution_mode"] = "medium"
            flow_state["session_strategy"] = "role_bound"
            flow_state["active_role_id"] = "implementer"
            flow_state["pending_codex_prompt"] = "continue the blocked task"
            flow_state["doctor_policy"] = {
                "enabled": True,
                "activation_rules": ["same_resume_failure"],
                "repair_scope": "runtime_assets_first",
                "framework_bug_action": "pause",
                "max_rounds_per_episode": 1,
            }
            flow_state["role_sessions"] = {
                "implementer": {
                    "role_id": "implementer",
                    "session_id": "thread-stale",
                    "status": "ready",
                    "updated_at": "2026-04-02 19:29:08",
                }
            }
            flow_state["last_codex_receipt"] = {
                "status": "failed",
                "summary": "Error: thread/resume: thread/resume failed: no rollout found for thread id thread-stale",
                "output_text": "Error: thread/resume: thread/resume failed: no rollout found for thread id thread-stale",
                "metadata": {
                    "runtime_request": {"codex_mode": "resume"},
                    "external_session": {
                        "provider": "codex",
                        "thread_id": "",
                        "requested_session_id": "thread-stale",
                        "resume_capable": False,
                    },
                },
            }
            ensure_flow_sidecars(flow_dir, flow_state)
            _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)
            runner = _ReceiptRunner(
                [
                    _receipt(
                        text="DOCTOR_FRAMEWORK_BUG:\nProblem: runtime keeps requesting stale rollout.\nEvidence: repeated resume/no-rollout failures.\nFix plan: patch the supervisor/runtime session quarantine path.",
                        metadata={"external_session": {"provider": "codex", "thread_id": "thread-doctor", "resume_capable": True}},
                        agent_id="butler_flow.codex_executor",
                    ),
                ]
            )
            app = self._app(runner)
            with mock.patch.object(flow_shell, "cli_provider_available", return_value=True):
                rc = app._runtime.run_flow_loop({"workspace_root": str(root)}, flow_dir, flow_state, stream_enabled=False)
            self.assertEqual(rc, 0)
            self.assertEqual(len(runner.calls), 1)
            state = self._flow_state(flow_dir)
            self.assertEqual(state["status"], "paused")
            self.assertEqual(state["approval_state"], "operator_required")
            self.assertEqual(state["latest_supervisor_decision"]["decision"], "ask_operator")
            self.assertIn("Problem:", state["pending_codex_prompt"])
            self.assertIn("Fix plan:", state["pending_codex_prompt"])

    def test_parser_defaults_new_kind_to_single_goal_and_allows_resume_priority_args(self) -> None:
        parser = flow_shell.build_arg_parser()
        new_args = parser.parse_args(["new", "--goal", "x", "--guard-condition", "y"])
        self.assertEqual(getattr(new_args, "kind", SINGLE_GOAL_KIND), SINGLE_GOAL_KIND)
        managed_args = parser.parse_args(["new", "--kind", MANAGED_FLOW_KIND, "--goal", "x", "--guard-condition", "y"])
        self.assertEqual(getattr(managed_args, "kind", MANAGED_FLOW_KIND), MANAGED_FLOW_KIND)
        resume_args = parser.parse_args(["resume", "--workflow-id", "w1", "--codex-session-id", "thread-1"])
        self.assertEqual(resume_args.workflow_id, "w1")
        self.assertEqual(resume_args.codex_session_id, "thread-1")

    def test_root_help_only_promotes_new_resume_exec(self) -> None:
        parser = flow_shell.build_arg_parser()
        help_text = parser.format_help()
        self.assertIn("new", help_text)
        self.assertIn("resume", help_text)
        self.assertIn("exec", help_text)
        self.assertNotIn("\n  run", help_text)
        self.assertNotIn("\n    run", help_text)
        self.assertNotIn("\n  flows", help_text)

    def test_exec_help_hides_run_compat_alias(self) -> None:
        parser = flow_shell.build_arg_parser()
        stdout = StringIO()
        with mock.patch.object(sys, "stdout", stdout):
            with self.assertRaises(SystemExit) as exc:
                parser.parse_args(["exec", "--help"])
        self.assertEqual(exc.exception.code, 0)
        help_text = stdout.getvalue()
        self.assertIn("{new,resume}", help_text)
        self.assertNotIn("{new,run,resume}", help_text)
        self.assertNotIn("\n    run", help_text)

    def test_cli_version_prints_current_butler_flow_version(self) -> None:
        stream = StringIO()
        with mock.patch.object(sys, "stdout", stream):
            rc = flow_cli.main(["--version"])
        self.assertEqual(rc, 0)
        self.assertIn(BUTLER_FLOW_VERSION, stream.getvalue())

    def test_main_without_subcommand_enters_launcher_on_interactive_tty(self) -> None:
        with mock.patch.object(flow_cli, "_stdin_is_interactive", return_value=True), \
            mock.patch.object(flow_cli, "textual_tui_support", return_value=(False, "disabled for test")), \
            mock.patch.object(flow_cli.FlowApp, "launcher", return_value=0) as mocked_launcher:
            rc = flow_shell.main([])
        self.assertEqual(rc, 0)
        mocked_launcher.assert_called_once()

    def test_status_last_resolves_most_recent_flow(self) -> None:
        if _NEW_FLOW_STATE is None or _WRITE_JSON_ATOMIC is None:
            raise AssertionError("butler_flow must expose _new_flow_state/_write_json_atomic for tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            flow_root = _BUILD_FLOW_ROOT(root)
            older_dir = flow_root / "flow_older"
            newer_dir = flow_root / "flow_newer"
            older_state = _NEW_FLOW_STATE(
                workflow_id="flow_older",
                workflow_kind=SINGLE_GOAL_KIND,
                workspace_root=str(root),
                goal="older",
                guard_condition="done",
                max_attempts=6,
                max_phase_attempts=3,
            )
            newer_state = _NEW_FLOW_STATE(
                workflow_id="flow_newer",
                workflow_kind=PROJECT_LOOP_KIND,
                workspace_root=str(root),
                goal="newer",
                guard_condition="verified",
                max_attempts=6,
                max_phase_attempts=3,
            )
            older_state["updated_at"] = "2026-03-31 09:00:00"
            newer_state["updated_at"] = "2026-03-31 10:00:00"
            _WRITE_JSON_ATOMIC(older_dir / "workflow_state.json", older_state)
            _WRITE_JSON_ATOMIC(newer_dir / "workflow_state.json", newer_state)
            app = self._app(_ReceiptRunner([]))
            args = argparse.Namespace(command="status", config=config, workflow_id="", last=True, json=False)
            rc = app.status(args)
            self.assertEqual(rc, 0)
            output = app._stdout.getvalue()
            self.assertIn("workflow_id=flow_newer", output)
            self.assertIn("kind=project_loop", output)

    def test_list_flows_prints_recent_rows(self) -> None:
        if _NEW_FLOW_STATE is None or _WRITE_JSON_ATOMIC is None:
            raise AssertionError("butler_flow must expose _new_flow_state/_write_json_atomic for tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            flow_root = _BUILD_FLOW_ROOT(root)
            flow_dir = flow_root / "flow_demo"
            flow_state = _NEW_FLOW_STATE(
                workflow_id="flow_demo",
                workflow_kind=SINGLE_GOAL_KIND,
                workspace_root=str(root),
                goal="ship the shell",
                guard_condition="verified",
                max_attempts=6,
                max_phase_attempts=3,
            )
            flow_state["status"] = "running"
            flow_state["attempt_count"] = 2
            flow_state["updated_at"] = "2026-03-31 11:00:00"
            _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)
            app = self._app(_ReceiptRunner([]))
            args = argparse.Namespace(command="list", config=config, limit=5, json=False)
            rc = app.list_flows(args) if hasattr(app, "list_flows") else app.list_workflows(args)
            self.assertEqual(rc, 0)
            output = app._stdout.getvalue()
            self.assertIn("asset_root=", output)
            self.assertIn("builtin:project_loop", output)

    def test_load_config_uses_shared_default_config_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = self._app(_ReceiptRunner([]))
            with mock.patch.object(flow_shell, "resolve_default_config_path", return_value=config) as mocked_resolve:
                cfg, config_path, workspace_root = app._load_config(None)
            mocked_resolve.assert_called_once_with("butler_bot")
            self.assertEqual(config_path, config)
            self.assertEqual(workspace_root, str(root))
            self.assertEqual(cfg["workspace_root"], str(root))

    def test_manage_flow_new_creates_definition_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(
                        text=json.dumps(
                            {
                                "summary": "managed flow prepared",
                                "label": "Managed Flow",
                                "description": "custom instance asset",
                                "goal": "ship managed flow",
                                "guard_condition": "review passes",
                                "workflow_kind": MANAGED_FLOW_KIND,
                                "asset_kind": "instance",
                                "mutation": "create",
                                "risk_level": "normal",
                                "autonomy_profile": "default",
                                "phase_plan": [
                                    {"phase_id": "discover", "title": "Discover", "objective": "discover", "done_when": "discover done", "retry_phase_id": "discover", "fallback_phase_id": "discover", "next_phase_id": "build"},
                                    {"phase_id": "build", "title": "Build", "objective": "build", "done_when": "build done", "retry_phase_id": "build", "fallback_phase_id": "discover", "next_phase_id": ""},
                                ],
                                "operator_guidance": "review then run",
                                "confirmation_prompt": "confirm",
                            },
                            ensure_ascii=False,
                        ),
                        agent_id="butler_flow.manager_agent",
                    )
                ]
            )
            app = self._app(runner)
            with mock.patch("butler_main.butler_flow.manage_agent.cli_provider_available", return_value=True):
                rc = app.manage_flow(
                    argparse.Namespace(
                        command="flows",
                        config=config,
                        limit=5,
                        json=False,
                        manage="new",
                        goal="ship managed flow",
                        guard_condition="review passes",
                        instruction="make it managed",
                    )
                )
            self.assertEqual(rc, 0)
            flow_dir = self._flow_dirs(root)[0]
            state = self._flow_state(flow_dir)
            definition = json.loads((flow_dir / "flow_definition.json").read_text(encoding="utf-8"))
            self.assertEqual(state["workflow_kind"], MANAGED_FLOW_KIND)
            self.assertEqual(state["current_phase"], "discover")
            self.assertEqual(definition["workflow_kind"], MANAGED_FLOW_KIND)
            self.assertEqual(definition["label"], "Managed Flow")
            self.assertEqual(definition["version"], BUTLER_FLOW_VERSION)
            self.assertEqual(definition["phase_plan"][0]["phase_id"], "discover")
            events = self._read_jsonl(flow_dir / "events.jsonl")
            self.assertTrue(any(str(row.get("kind") or "") == "manage_handoff_ready" for row in events))
            manage_event = next(row for row in events if str(row.get("kind") or "") == "manage_handoff_ready")
            self.assertEqual(manage_event["lane"], "supervisor")
            self.assertEqual(manage_event["family"], "handoff")

    def test_manage_flow_can_create_template_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(
                        text=json.dumps(
                            {
                                "summary": "template prepared",
                                "label": "Research Template",
                                "description": "reusable research flow",
                                "goal": "run repeatable research",
                                "guard_condition": "summary delivered",
                                "workflow_kind": MANAGED_FLOW_KIND,
                                "asset_kind": "template",
                                "mutation": "create",
                                "risk_level": "normal",
                                "autonomy_profile": "guarded",
                                "phase_plan": [
                                    {"phase_id": "scan", "title": "Scan", "objective": "scan sources", "done_when": "sources identified", "retry_phase_id": "scan", "fallback_phase_id": "scan", "next_phase_id": "synthesize"},
                                    {"phase_id": "synthesize", "title": "Synthesize", "objective": "write synthesis", "done_when": "report ready", "retry_phase_id": "synthesize", "fallback_phase_id": "scan", "next_phase_id": ""},
                                ],
                                "operator_guidance": "reuse from manage center",
                                "confirmation_prompt": "confirm template",
                            },
                            ensure_ascii=False,
                        ),
                        agent_id="butler_flow.manager_agent",
                    )
                ]
            )
            app = self._app(runner)
            with mock.patch("butler_main.butler_flow.manage_agent.cli_provider_available", return_value=True):
                rc = app.manage_flow(
                    argparse.Namespace(
                        command="manage",
                        config=config,
                        limit=5,
                        json=False,
                        manage="template:new",
                        goal="run repeatable research",
                        guard_condition="summary delivered",
                        instruction="create reusable research template",
                    )
                )
            self.assertEqual(rc, 0)
            payload = app.build_manage_payload(argparse.Namespace(command="list", config=config, limit=20, json=False))
            template_rows = [row for row in list(payload.get("items") or []) if str(row.get("asset_kind") or "") == "template"]
            self.assertEqual(len(template_rows), 1)
            self.assertRegex(template_rows[0]["asset_id"], r"^\d{8}_research_template(?:_\d+)?$")
            self.assertEqual(template_rows[0]["label"], "Research Template")
            self.assertEqual(template_rows[0]["definition"]["phase_plan"][0]["phase_id"], "scan")
            template_bundle = root / "butler_main" / "butler_bot_code" / "assets" / "flows" / "bundles" / "templates" / template_rows[0]["asset_id"]
            self.assertTrue((template_bundle / "manager.md").exists())
            self.assertTrue((template_bundle / "supervisor.md").exists())
            self.assertTrue((template_bundle / "sources.json").exists())
            self.assertTrue((template_bundle / "derived" / "supervisor_knowledge.json").exists())
            self.assertIn("bundle_manifest", template_rows[0]["definition"])

    def test_manage_flow_can_commit_from_structured_draft_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            app = self._app(_ReceiptRunner([]))
            rc = app.manage_flow(
                argparse.Namespace(
                    command="manage",
                    config=config,
                    limit=5,
                    json=True,
                    manage="template:new",
                    goal="",
                    guard_condition="",
                    instruction="commit draft",
                    stage="commit",
                    builtin_mode="",
                    draft_payload={
                        "manage_target": "template:new",
                        "asset_kind": "template",
                        "label": "Desktop Product Delivery",
                        "description": "reusable desktop product flow",
                        "workflow_kind": MANAGED_FLOW_KIND,
                        "goal": "ship a desktop app increment safely",
                        "guard_condition": "handoff is release-ready",
                        "phase_plan": [
                            {"phase_id": "plan", "title": "Plan", "objective": "plan", "done_when": "done", "retry_phase_id": "plan", "fallback_phase_id": "plan", "next_phase_id": "build"},
                            {"phase_id": "build", "title": "Build", "objective": "build", "done_when": "done", "retry_phase_id": "build", "fallback_phase_id": "plan", "next_phase_id": ""},
                        ],
                        "review_checklist": ["check delivery scope", "check release notes"],
                        "supervisor_profile": {
                            "archetype": "delivery_manager",
                            "primary_posture": "steady_delivery",
                            "quality_bar": "reviewable_increment",
                            "risk_bias": "balanced",
                            "review_focus": ["release readiness", "user-visible regression"],
                            "done_policy": {"must_block_on": ["broken build"], "can_defer_with_note": ["minor polish"]},
                            "manager_notes": "Prefer stable weekly delivery.",
                        },
                        "run_brief": "Use this template when the work needs clear delivery cadence.",
                        "source_bindings": [{"kind": "doc", "label": "PRD", "ref": "docs/daily-upgrade/0402/prd.md", "notes": "Desktop product direction"}],
                    },
                )
            )
            self.assertEqual(rc, 0)
            payload = json.loads(app._stdout.getvalue())
            asset_id = payload["asset_id"]
            definition = self._read_json(root / "butler_main" / "butler_bot_code" / "assets" / "flows" / "templates" / f"{asset_id}.json")
            bundle_root = root / "butler_main" / "butler_bot_code" / "assets" / "flows" / "bundles" / "templates" / asset_id
            sources = self._read_json(bundle_root / "sources.json")
            compiled = self._read_json(bundle_root / "derived" / "supervisor_knowledge.json")
            self.assertEqual(definition["supervisor_profile"]["archetype"], "delivery_manager")
            self.assertEqual(definition["run_brief"], "Use this template when the work needs clear delivery cadence.")
            self.assertEqual(sources["items"][0]["label"], "PRD")
            self.assertIn("delivery_manager", compiled["knowledge_text"])
            self.assertIn("release readiness", compiled["knowledge_text"])

    def test_manage_flow_builtin_requires_explicit_mode_and_can_clone_to_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(
                        text=json.dumps(
                            {
                                "summary": "builtin cloned into editable template",
                                "label": "Project Loop Variant",
                                "description": "cloned from builtin",
                                "goal": "ship managed work",
                                "guard_condition": "review passes",
                                "workflow_kind": PROJECT_LOOP_KIND,
                                "asset_kind": "template",
                                "mutation": "create",
                                "risk_level": "normal",
                                "autonomy_profile": "guarded",
                                "phase_plan": [
                                    {"phase_id": "plan", "title": "Plan", "objective": "plan", "done_when": "ready", "retry_phase_id": "plan", "fallback_phase_id": "plan", "next_phase_id": "imp"},
                                    {"phase_id": "imp", "title": "Implement", "objective": "build", "done_when": "done", "retry_phase_id": "imp", "fallback_phase_id": "plan", "next_phase_id": ""},
                                ],
                                "operator_guidance": "review before launch",
                                "confirmation_prompt": "confirm clone",
                            },
                            ensure_ascii=False,
                        ),
                        agent_id="butler_flow.manager_agent",
                    )
                ]
            )
            app = self._app(runner)
            with mock.patch("butler_main.butler_flow.manage_agent.cli_provider_available", return_value=True):
                with self.assertRaises(ValueError):
                    app.manage_flow(
                        argparse.Namespace(
                            command="manage",
                            config=config,
                            limit=5,
                            json=False,
                            manage="builtin:project_loop",
                            goal="ship managed work",
                            guard_condition="review passes",
                            instruction="tighten the built-in phases",
                        )
                    )
                rc = app.manage_flow(
                    argparse.Namespace(
                        command="manage",
                        config=config,
                        limit=5,
                        json=True,
                        manage="builtin:project_loop",
                        goal="ship managed work",
                        guard_condition="review passes",
                        instruction="clone make a team variant",
                    )
                )
            self.assertEqual(rc, 0)
            payload = json.loads(app._stdout.getvalue())
            self.assertEqual(payload["asset_kind"], "template")
            self.assertEqual(payload["builtin_mode"], "clone")
            self.assertEqual(payload["flow_definition"]["lineage"]["cloned_from_asset_key"], "builtin:project_loop")

    def test_build_manage_payload_lists_only_builtin_and_template_assets(self) -> None:
        if _NEW_FLOW_STATE is None or _WRITE_JSON_ATOMIC is None:
            raise AssertionError("butler_flow must expose _new_flow_state/_write_json_atomic for tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            flow_root = _BUILD_FLOW_ROOT(root)
            flow_dir = flow_root / "flow_demo"
            flow_state = _NEW_FLOW_STATE(
                workflow_id="flow_demo",
                workflow_kind=MANAGED_FLOW_KIND,
                workspace_root=str(root),
                goal="ship the shell",
                guard_condition="verified",
                max_attempts=6,
                max_phase_attempts=3,
            )
            flow_state["status"] = "running"
            flow_state["updated_at"] = "2026-03-31 11:00:00"
            _WRITE_JSON_ATOMIC(flow_dir / "workflow_state.json", flow_state)
            _WRITE_JSON_ATOMIC(
                root / "butler_main" / "butler_bot_code" / "assets" / "flows" / "templates" / "template_demo.json",
                {
                    "flow_id": "template_demo",
                    "label": "Template Demo",
                    "workflow_kind": MANAGED_FLOW_KIND,
                    "goal": "template goal",
                    "phase_plan": [{"phase_id": "plan", "title": "Plan", "objective": "plan", "done_when": "done", "retry_phase_id": "plan", "fallback_phase_id": "plan", "next_phase_id": ""}],
                    "updated_at": "2026-03-31 10:00:00",
                },
            )
            app = self._app(_ReceiptRunner([]))
            payload = app.build_manage_payload(argparse.Namespace(command="list", config=config, limit=20, json=False))
            rows = list(payload.get("items") or [])
            asset_kinds = {str(row.get("asset_kind") or "") for row in rows}
            self.assertIn("builtin", asset_kinds)
            self.assertIn("template", asset_kinds)
            self.assertNotIn("instance", asset_kinds)

    def test_managed_flow_uses_custom_phase_plan_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            runner = _ReceiptRunner(
                [
                    _receipt(text="discover done", metadata={"external_session": {"provider": "codex", "thread_id": "managed-thread", "resume_capable": True}}),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "build", "reason": "discover ready", "next_codex_prompt": "", "completion_summary": "discover done"}, ensure_ascii=False)),
                    _receipt(text="build done"),
                    _receipt(text=json.dumps({"decision": "ADVANCE", "next_phase": "review", "reason": "build ready", "next_codex_prompt": "", "completion_summary": "build done"}, ensure_ascii=False)),
                    _receipt(text="review done"),
                    _receipt(text=json.dumps({"decision": "COMPLETE", "next_phase": "done", "reason": "complete", "next_codex_prompt": "", "completion_summary": "managed flow complete"}, ensure_ascii=False)),
                ]
            )
            app = self._app(runner)
            args = argparse.Namespace(
                command="new",
                config=config,
                kind=MANAGED_FLOW_KIND,
                launch_mode="flow",
                execution_level="simple",
                catalog_flow_id="project_loop",
                goal="ship managed flow",
                guard_condition="review passes",
                max_attempts=None,
                max_phase_attempts=None,
                no_stream=True,
            )
            with mock.patch("butler_main.butler_flow.runtime.cli_provider_available", return_value=True):
                prepared = app.prepare_new_flow(args)
                prepared.flow_state["phase_plan"] = [
                    {"phase_id": "discover", "title": "Discover", "objective": "discover", "done_when": "discover done", "retry_phase_id": "discover", "fallback_phase_id": "discover", "next_phase_id": "build"},
                    {"phase_id": "build", "title": "Build", "objective": "build", "done_when": "build done", "retry_phase_id": "build", "fallback_phase_id": "discover", "next_phase_id": "review"},
                    {"phase_id": "review", "title": "Review", "objective": "review", "done_when": "review done", "retry_phase_id": "build", "fallback_phase_id": "build", "next_phase_id": ""},
                ]
                prepared.flow_state["current_phase"] = "discover"
                rc = app.execute_prepared_flow(prepared, stream_enabled=False)
            self.assertEqual(rc, 0)
            state = self._flow_state(prepared.flow_path)
            self.assertEqual(state["status"], "completed")
            self.assertEqual([row["phase"] for row in state["phase_history"]], ["discover", "build", "review"])
            self.assertEqual(state["codex_session_id"], "managed-thread")


if __name__ == "__main__":
    unittest.main()
