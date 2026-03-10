import json
import tempfile
from pathlib import Path
import sys
import time
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
sys.path.insert(0, str(MODULE_DIR))

from memory_manager import MemoryManager  # noqa: E402
from task_ledger_service import TaskLedgerService  # noqa: E402


class HeartbeatOrchestrationTests(unittest.TestCase):
    def test_no_tasks_in_explicit_only_mode_still_calls_planner(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                calls.append(prompt)
                return json.dumps(
                    {
                        "chosen_mode": "status",
                        "execution_mode": "defer",
                        "reason": "当前没有更适合推进的事项",
                        "user_message": "本轮已检查显式任务和长期记忆候选，暂不推进新的动作。",
                        "task_groups": [],
                        "updates": {"complete_task_ids": [], "defer_task_ids": [], "touch_long_task_ids": []},
                    },
                    ensure_ascii=False,
                ), True

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )
            manager._render_heartbeat_local_memory_snippet = lambda _workspace: "长期约束：空闲时先从长期记忆恢复低风险事项"

            plan = manager._plan_heartbeat_action(
                {"workspace_root": str(workspace), "agent_timeout": 60},
                {"enabled": True, "every_seconds": 5, "allow_autonomous_explore": False},
                str(workspace),
                60,
                "auto",
            )

            self.assertEqual(len(calls), 1)
            self.assertEqual(plan["chosen_mode"], "long_task")
            self.assertIn("长期记忆候选", calls[0])
            self.assertIn("长期约束", calls[0])
            branch_ids = [branch["branch_id"] for group in plan.get("task_groups", []) for branch in group.get("branches", [])]
            self.assertIn("heartbeat-metabolism", branch_ids)

    def test_force_model_planner_explore_is_blocked_when_autonomous_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                calls.append(prompt)
                return json.dumps(
                    {
                        "chosen_mode": "explore",
                        "execution_mode": "single",
                        "reason": "想做一次主动探索",
                        "user_message": "本轮进入 explore。",
                        "task_groups": [],
                        "updates": {"complete_task_ids": [], "defer_task_ids": [], "touch_long_task_ids": []},
                    },
                    ensure_ascii=False,
                ), True

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )

            plan = manager._plan_heartbeat_action(
                {"workspace_root": str(workspace), "agent_timeout": 60},
                {"enabled": True, "every_seconds": 5, "force_model_planner": True, "allow_autonomous_explore": False},
                str(workspace),
                60,
                "auto",
            )

            self.assertTrue(calls)
            self.assertEqual(plan["chosen_mode"], "status")
            self.assertIn("未开启自主探索模式", plan["user_message"])

    def test_explicit_heartbeat_timeouts_can_match_dialogue_timeout(self):
        manager = MemoryManager(
            config_provider=lambda: {"workspace_root": "."},
            run_model_fn=lambda *_: ("", False),
        )

        heartbeat_cfg = {"planner_timeout": 300, "branch_timeout": 300}
        self.assertEqual(manager._resolve_heartbeat_planner_timeout(heartbeat_cfg, 300), 300)
        self.assertEqual(manager._resolve_heartbeat_branch_timeout(heartbeat_cfg, 300), 300)

    def test_force_model_planner_bypasses_idle_shortcut_when_autonomous_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                calls.append(prompt)
                return json.dumps(
                    {
                        "chosen_mode": "explore",
                        "execution_mode": "single",
                        "reason": "交给规划器决定",
                        "user_message": "规划器已接管本轮判断。",
                        "task_groups": [],
                        "updates": {"complete_task_ids": [], "defer_task_ids": [], "touch_long_task_ids": []},
                    },
                    ensure_ascii=False,
                ), True

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )
            manager._heartbeat_last_planner_started_at = time.time()

            plan = manager._plan_heartbeat_action(
                {"workspace_root": str(workspace), "agent_timeout": 60},
                {"enabled": True, "every_seconds": 5, "force_model_planner": True, "allow_autonomous_explore": True},
                str(workspace),
                60,
                "auto",
            )

            self.assertTrue(calls)
            self.assertEqual(plan["chosen_mode"], "explore")
            self.assertEqual(plan["user_message"], "规划器已接管本轮判断。")

    def test_planning_prompt_keeps_schema_section_with_custom_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=lambda *_: ("", False),
            )

            manager._load_heartbeat_prompt_template = lambda _workspace: (
                "# 自定义模板\n\n当前时间：{now_text}\n\n最近上下文：{recent_text}\n"
            )
            prompt = manager._build_heartbeat_planning_prompt(
                {"workspace_root": str(workspace)},
                {"enabled": True},
                str(workspace),
            )

            self.assertIn("JSON Schema", prompt)
            self.assertIn('"task_groups"', prompt)

    def test_planning_prompt_includes_skills_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=lambda *_: ("", False),
            )
            manager._render_available_skills_prompt = lambda _workspace: (
                "DNA 核心能力保留在主代码：身体运行、灵魂、记忆、心跳。\n"
                "[feishu]\n- feishu-chat-history @ ./butler_main/butler_bot_agent/skills/feishu_chat_history"
            )

            prompt = manager._build_heartbeat_planning_prompt(
                {"workspace_root": str(workspace)},
                {"enabled": True},
                str(workspace),
            )

            self.assertIn("## 可复用 Skills", prompt)
            self.assertIn("feishu-chat-history", prompt)
            self.assertIn("不要把这些基础运转拆成 skill", prompt)
            self.assertIn('"capability_id":""', prompt)
            self.assertIn('"skill_name":""', prompt)
            self.assertIn('"requires_skill_read":false', prompt)

    def test_normalize_plan_task_groups_preserves_skill_metadata(self):
        manager = MemoryManager(
            config_provider=lambda: {"workspace_root": "."},
            run_model_fn=lambda *_: ("", False),
        )

        normalized = manager._normalize_plan_task_groups(
            {
                "task_groups": [
                    {
                        "group_id": "group-1",
                        "branches": [
                            {
                                "branch_id": "b1",
                                "agent_role": "heartbeat-executor-agent",
                                "execution_kind": "task",
                                "capability_id": "skill:feishu_chat_history",
                                "capability_type": "skill",
                                "skill_name": "feishu_chat_history",
                                "skill_dir": "./butler_main/butler_bot_agent/skills/feishu_chat_history",
                                "requires_skill_read": True,
                                "prompt": "role=heartbeat-executor-agent\noutput_dir=./工作区/with_user\n执行任务",
                            }
                        ],
                    }
                ]
            },
            max_parallel=3,
        )

        branch = normalized[0]["branches"][0]
        self.assertEqual(branch["capability_id"], "skill:feishu_chat_history")
        self.assertEqual(branch["capability_type"], "skill")
        self.assertEqual(branch["skill_name"], "feishu_chat_history")
        self.assertEqual(branch["skill_dir"], "./butler_main/butler_bot_agent/skills/feishu_chat_history")
        self.assertTrue(branch["requires_skill_read"])

    def test_run_heartbeat_branch_requires_skill_file_when_declared(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                calls.append(prompt)
                return "不会执行到这里", True

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )

            result = manager._run_heartbeat_branch(
                {
                    "branch_id": "skill-miss",
                    "agent_role": "heartbeat-executor-agent",
                    "skill_name": "missing-skill",
                    "skill_dir": "./butler_main/butler_bot_agent/skills/research/missing-skill",
                    "requires_skill_read": True,
                    "prompt": "role=heartbeat-executor-agent\noutput_dir=./工作区/with_user\n执行任务",
                },
                str(workspace),
                60,
                "auto",
            )

            self.assertFalse(result["ok"])
            self.assertIn("SKILL.md not found", result["error"])
            self.assertFalse(calls)

    def test_run_heartbeat_branch_injects_skill_text_into_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []
            skill_dir = workspace / "butler_main" / "butler_bot_agent" / "skills" / "research" / "demo-skill"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                "# Demo Skill\n\n执行前必须先读取这段 skill 说明。\n",
                encoding="utf-8",
            )

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                calls.append(prompt)
                return "已完成", True

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )

            result = manager._run_heartbeat_branch(
                {
                    "branch_id": "skill-hit",
                    "agent_role": "heartbeat-executor-agent",
                    "skill_name": "demo-skill",
                    "skill_dir": "./butler_main/butler_bot_agent/skills/research/demo-skill",
                    "requires_skill_read": True,
                    "prompt": "role=heartbeat-executor-agent\noutput_dir=./工作区/with_user\n执行任务",
                },
                str(workspace),
                60,
                "auto",
            )

            self.assertTrue(result["ok"])
            self.assertEqual(len(calls), 1)
            self.assertIn("【本分支指定 skill】", calls[0])
            self.assertIn("skill_name=demo-skill", calls[0])
            self.assertIn("skill_path=./butler_main/butler_bot_agent/skills/research/demo-skill/SKILL.md", calls[0])
            self.assertIn("执行前必须先读取这段 skill 说明", calls[0])

    def test_planning_prompt_includes_task_workspace_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=lambda *_: ("", False),
            )
            TaskLedgerService(str(workspace)).ensure_bootstrapped(
                short_tasks=[
                    {
                        "task_id": "task-1",
                        "title": "测 30 条耗时",
                        "detail": "在当前会话里测一次拉取 30 条消息耗时",
                        "status": "pending",
                    }
                ]
            )

            prompt = manager._build_heartbeat_planning_prompt(
                {"workspace_root": str(workspace)},
                {"enabled": True},
                str(workspace),
            )

            self.assertIn("## 任务工作区", prompt)
            self.assertIn("测 30 条耗时", prompt)


    def test_planner_timeout_uses_local_fallback_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            planner_calls = {"count": 0}

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                if "JSON Schema" in prompt:
                    planner_calls["count"] += 1
                    return "执行超时", False
                return "", False

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )
            manager._save_heartbeat_memory(
                str(workspace),
                {
                    "version": 1,
                    "updated_at": "",
                    "tasks": [
                        {
                            "task_id": "task-1",
                            "status": "pending",
                            "title": "整理文档",
                            "detail": "去工作区整理最新文档并更新索引",
                            "created_at": "",
                            "updated_at": "",
                            "priority": "medium",
                            "source": "conversation",
                            "source_memory_id": "",
                            "trigger_hint": "conversation",
                            "due_at": "",
                            "tags": [],
                            "last_result": "",
                        }
                    ],
                    "notes": [],
                },
            )

            plan = manager._plan_heartbeat_action(
                {"workspace_root": str(workspace), "agent_timeout": 60},
                {"enabled": True, "every_seconds": 5},
                str(workspace),
                60,
                "auto",
            )

            self.assertEqual(planner_calls["count"], 1)
            self.assertEqual(plan["chosen_mode"], "short_task")
            self.assertIn("兜底策略", plan["reason"])
            branch_ids = [branch["branch_id"] for group in plan.get("task_groups", []) for branch in group.get("branches", [])]
            self.assertIn("heartbeat-metabolism", branch_ids)

    def test_planner_failure_enters_backoff_and_skips_repeat_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            planner_calls = {"count": 0}

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                if "JSON Schema" in prompt:
                    planner_calls["count"] += 1
                    return "执行超时", False
                return "", False

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )
            manager._save_heartbeat_memory(
                str(workspace),
                {
                    "version": 1,
                    "updated_at": "",
                    "tasks": [
                        {
                            "task_id": "task-1",
                            "status": "pending",
                            "title": "整理文档",
                            "detail": "去工作区整理最新文档并更新索引",
                            "created_at": "",
                            "updated_at": "",
                            "priority": "medium",
                            "source": "conversation",
                            "source_memory_id": "",
                            "trigger_hint": "conversation",
                            "due_at": "",
                            "tags": [],
                            "last_result": "",
                        }
                    ],
                    "notes": [],
                },
            )

            manager._plan_heartbeat_action(
                {"workspace_root": str(workspace), "agent_timeout": 60},
                {"enabled": True, "every_seconds": 5},
                str(workspace),
                60,
                "auto",
            )
            second_plan = manager._plan_heartbeat_action(
                {"workspace_root": str(workspace), "agent_timeout": 60},
                {"enabled": True, "every_seconds": 5},
                str(workspace),
                60,
                "auto",
            )

            self.assertEqual(planner_calls["count"], 1)
            self.assertEqual(second_plan["chosen_mode"], "short_task")

    def test_planner_backoff_survives_manager_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            planner_calls = {"count": 0}

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                if "JSON Schema" in prompt:
                    planner_calls["count"] += 1
                    return "执行超时", False
                return "", False

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )
            manager._save_heartbeat_memory(
                str(workspace),
                {
                    "version": 1,
                    "updated_at": "",
                    "tasks": [
                        {
                            "task_id": "task-1",
                            "status": "pending",
                            "title": "整理文档",
                            "detail": "去工作区整理最新文档并更新索引",
                            "created_at": "",
                            "updated_at": "",
                            "priority": "medium",
                            "source": "conversation",
                            "source_memory_id": "",
                            "trigger_hint": "conversation",
                            "due_at": "",
                            "tags": [],
                            "last_result": "",
                        }
                    ],
                    "notes": [],
                },
            )

            manager._plan_heartbeat_action(
                {"workspace_root": str(workspace), "agent_timeout": 60},
                {"enabled": True, "every_seconds": 5},
                str(workspace),
                60,
                "auto",
            )

            restarted_manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )
            second_plan = restarted_manager._plan_heartbeat_action(
                {"workspace_root": str(workspace), "agent_timeout": 60},
                {"enabled": True, "every_seconds": 5},
                str(workspace),
                60,
                "auto",
            )

            self.assertEqual(planner_calls["count"], 1)
            self.assertEqual(second_plan["chosen_mode"], "short_task")

    def test_status_plan_gets_fixed_metabolism_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                return json.dumps(
                    {
                        "chosen_mode": "status",
                        "execution_mode": "defer",
                        "reason": "本轮暂无更高优先级任务",
                        "user_message": "本轮先观察。",
                        "task_groups": [],
                        "updates": {"complete_task_ids": [], "defer_task_ids": [], "touch_long_task_ids": []},
                    },
                    ensure_ascii=False,
                ), True

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )

            plan = manager._plan_heartbeat_action(
                {"workspace_root": str(workspace), "agent_timeout": 60},
                {"enabled": True, "every_seconds": 5, "fixed_metabolism_branch": True},
                str(workspace),
                60,
                "auto",
            )

            self.assertEqual(plan["chosen_mode"], "long_task")
            branch_ids = [branch["branch_id"] for group in plan.get("task_groups", []) for branch in group.get("branches", [])]
            self.assertIn("heartbeat-metabolism", branch_ids)


if __name__ == "__main__":
    unittest.main()