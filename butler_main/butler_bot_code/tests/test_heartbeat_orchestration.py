import json
import tempfile
from pathlib import Path
import sys
import time
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
sys.path.insert(0, str(MODULE_DIR))

from memory_manager import MemoryManager  # noqa: E402
from services.task_ledger_service import TaskLedgerService  # noqa: E402


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

    def test_local_fallback_prefers_task_ledger_over_legacy_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=lambda *_: ("", False),
            )
            ledger = TaskLedgerService(str(workspace))
            payload = ledger.load()
            payload["items"] = [
                {
                    "task_id": "short-1",
                    "task_type": "short",
                    "status": "pending",
                    "title": "先推进账本中的短任务",
                    "detail": "fallback 应优先从 ledger 取任务",
                    "source": "conversation",
                    "priority": "high",
                    "created_at": "2026-03-11 15:00:00",
                    "updated_at": "2026-03-11 15:00:00",
                }
            ]
            ledger.save(payload)

            plan = manager._heartbeat_orchestrator._build_local_fallback_task_plan(
                {"enabled": True},
                manager._build_heartbeat_planning_context({"enabled": True}, str(workspace)),
                str(workspace),
                "planner fallback",
            )

            self.assertEqual(plan["chosen_mode"], "short_task")
            self.assertEqual(plan["selected_task_ids"], ["short-1"])

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
            self.assertIn("少做碎片化微操", prompt)
            self.assertIn("升级不要只停在死知识", prompt)
            self.assertIn("检索公开方案 -> 安全审阅 -> 落 skill/MCP -> 回到原任务重试", prompt)
            self.assertIn("growth_share", prompt)
            self.assertIn('"capability_id":""', prompt)
            self.assertIn('"skill_name":""', prompt)
            self.assertIn('"requires_skill_read":false', prompt)
            self.assertIn("统一维护入口", prompt)
            self.assertIn("agent_role=update-agent", prompt)

    def test_planning_prompt_excludes_self_mind_bridge_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=lambda *_: ("", False),
            )
            manager._save_self_mind_bridge_items(
                str(workspace),
                [
                    {
                        "bridge_id": "bridge-1",
                        "created_at": "2026-03-11 13:30:00",
                        "candidate": "把脑子和身体的桥接规则补清楚",
                        "action_channel": "heartbeat",
                        "action_type": "task",
                        "priority": 80,
                        "heartbeat_reason": "需要 planner 分配身体执行",
                    }
                ],
            )

            prompt = manager._build_heartbeat_planning_prompt(
                {"workspace_root": str(workspace)},
                {"enabled": True},
                str(workspace),
            )

            self.assertNotIn("Self Mind 自我意识态势", prompt)
            self.assertNotIn("Self Mind 提案与脑-体桥接", prompt)
            self.assertNotIn("桥接规则补清楚", prompt)

    def test_apply_plan_does_not_update_self_mind_bridge_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=lambda *_: ("", False),
            )
            manager._save_self_mind_bridge_items(
                str(workspace),
                [
                    {
                        "bridge_id": "bridge-1",
                        "created_at": "2026-03-11 13:30:00",
                        "created_epoch": time.time(),
                        "candidate": "学会给用户发图片惊喜",
                        "action_channel": "heartbeat",
                        "action_type": "visual",
                        "status": "pending",
                    }
                ],
            )

            plan = {
                "chosen_mode": "long_task",
                "execution_mode": "single",
                "reason": "推进一条 self-mind 委托事项",
                "user_message": "本轮先学会图片相关能力。",
                "selected_task_ids": [],
                "deferred_task_ids": [],
                "defer_reason": "",
                "task_groups": [],
                "updates": {"complete_task_ids": [], "defer_task_ids": [], "touch_long_task_ids": []},
            }

            manager._apply_heartbeat_plan(
                str(workspace),
                plan,
                "已完成一次图片能力调研，并形成下一步实现思路。",
                branch_results=[{"branch_id": "b1", "ok": True, "output": "已完成一次图片能力调研"}],
            )

            bridge_path = workspace / "butler_main" / "butle_bot_space" / "self_mind" / "mind_body_bridge.json"
            self.assertFalse(bridge_path.exists())

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

    def test_run_heartbeat_branch_injects_recovery_protocol(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                calls.append(prompt)
                return "已完成", True

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )

            result = manager._run_heartbeat_branch(
                {
                    "branch_id": "recoverable-hit",
                    "agent_role": "heartbeat-executor-agent",
                    "prompt": "role=heartbeat-executor-agent\noutput_dir=./工作区/with_user\n执行任务",
                },
                str(workspace),
                60,
                "auto",
            )

            self.assertTrue(result["ok"])
            self.assertEqual(len(calls), 1)
            self.assertIn("【heartbeat 执行协议】", calls[0])
            self.assertIn("诊断 -> 换路/修正 -> 复试", calls[0])
            self.assertIn("Feishu 230002", calls[0])

    def test_run_heartbeat_branch_returns_runtime_profile_and_process_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                calls.append({"prompt": prompt, "model": model})
                return "已完成验收", True

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace), "runtime_router": {"codex_max_selected_per_window": 5}},
                run_model_fn=fake_model,
            )

            result = manager._run_heartbeat_branch(
                {
                    "branch_id": "acceptance-1",
                    "agent_role": "heartbeat-executor-agent",
                    "process_role": "acceptance",
                    "execution_kind": "acceptance",
                    "runtime_profile": {"cli": "codex", "model": "gpt-5", "why": "explicit acceptance"},
                    "prompt": "请做最终验收并给出通过/不通过结论",
                },
                str(workspace),
                60,
                "auto",
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["process_role"], "acceptance")
            self.assertEqual(result["runtime_profile"]["cli"], "codex")
            self.assertEqual(calls[0]["model"], "gpt-5")
            self.assertIn("【流程角色】", calls[0]["prompt"])
            self.assertIn("runtime_profile", calls[0]["prompt"])

    def test_run_heartbeat_branch_prefers_external_workspace_hint_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []
            hint_path = workspace / "butler_main" / "butler_bot_agent" / "agents" / "heartbeat-executor-workspace-hint.md"
            hint_path.parent.mkdir(parents=True, exist_ok=True)
            hint_path.write_text(
                "【自定义工作区约束】\n默认输出到 {company_root}。\n升级申请写入 {upgrade_request}。",
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
                    "branch_id": "custom-workspace-hint",
                    "agent_role": "heartbeat-executor-agent",
                    "prompt": "role=heartbeat-executor-agent\noutput_dir=./工作区/with_user\n执行任务",
                },
                str(workspace),
                60,
                "auto",
            )

            self.assertTrue(result["ok"])
            self.assertEqual(len(calls), 1)
            self.assertIn("【自定义工作区约束】", calls[0])
            self.assertIn("默认输出到 ./工作区", calls[0])
            self.assertIn("heartbeat_upgrade_request.json", calls[0])

    def test_run_heartbeat_branch_extracts_tell_user_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                return (
                    "执行完成\n\n"
                    "【heartbeat_tell_user_markdown】\n"
                    "## 本分支可同步\n"
                    "- 已完成整理，并确认下一步。\n"
                    "【/heartbeat_tell_user_markdown】",
                    True,
                )

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )

            result = manager._run_heartbeat_branch(
                {
                    "branch_id": "share-hit",
                    "agent_role": "heartbeat-executor-agent",
                    "prompt": "role=heartbeat-executor-agent\noutput_dir=./工作区/with_user\n执行任务",
                },
                str(workspace),
                60,
                "auto",
            )

            self.assertTrue(result["ok"])
            self.assertIn("## 本分支可同步", result["tell_user_markdown"])
            self.assertIn("已完成整理", result["tell_user_markdown"])

    def test_normalize_plan_task_groups_preserves_team_id(self):
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
                                "branch_id": "team-1",
                                "agent_role": "orchestrator-agent",
                                "team_id": "research-implement-review",
                                "execution_kind": "analysis",
                                "prompt": "分析当前复杂任务",
                            }
                        ],
                    }
                ]
            },
            max_parallel=3,
        )

        self.assertEqual(normalized[0]["branches"][0]["team_id"], "research-implement-review")

    def test_run_heartbeat_branch_executes_team_definition(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []
            team_path = workspace / "butler_main" / "butler_bot_agent" / "agents" / "teams" / "research-implement-review.json"
            role_path = workspace / "butler_main" / "butler_bot_agent" / "agents" / "sub-agents" / "discussion-agent.md"
            hint_path = workspace / "butler_main" / "butler_bot_agent" / "agents" / "heartbeat-executor-workspace-hint.md"
            team_path.parent.mkdir(parents=True, exist_ok=True)
            role_path.parent.mkdir(parents=True, exist_ok=True)
            hint_path.parent.mkdir(parents=True, exist_ok=True)
            team_path.write_text(
                '{"team_id":"research-implement-review","name":"Research Implement Review","description":"并行调研后汇总。","execution_mode":"mixed","steps":[{"step_id":"s1","mode":"serial","members":[{"role":"discussion-agent","task":"{task}"}]}]}',
                encoding="utf-8",
            )
            role_path.write_text("---\nname: discussion-agent\ndescription: 负责讨论复杂问题。\n---\n# discussion-agent\nresult/evidence/unresolved/next_step", encoding="utf-8")
            hint_path.write_text("【工作区提示】输出到 ./工作区。", encoding="utf-8")

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                calls.append(prompt)
                return "result\n- 已完成团队子任务\n\nevidence\n- 有角色说明\n\nunresolved\n- 无\n\nnext_step\n- 汇总即可", True

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )

            result = manager._run_heartbeat_branch(
                {
                    "branch_id": "team-hit",
                    "agent_role": "orchestrator-agent",
                    "team_id": "research-implement-review",
                    "prompt": "请分析这个复杂任务",
                },
                str(workspace),
                60,
                "auto",
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["team_id"], "research-implement-review")
            self.assertTrue(calls)

    def test_run_heartbeat_branch_falls_back_when_team_unregistered(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            calls = []
            team_path = workspace / "butler_main" / "butler_bot_agent" / "agents" / "teams" / "research-implement-review.json"
            subagent_path = workspace / "butler_main" / "butler_bot_agent" / "agents" / "sub-agents" / "orchestrator-agent.md"
            team_path.parent.mkdir(parents=True, exist_ok=True)
            subagent_path.parent.mkdir(parents=True, exist_ok=True)
            team_path.write_text(
                '{"team_id":"research-implement-review","name":"Research Implement Review","description":"并行调研后汇总。","execution_mode":"mixed","steps":[]}',
                encoding="utf-8",
            )
            subagent_path.write_text("# orchestrator-agent\n负责普通分支执行。", encoding="utf-8")

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                calls.append(prompt)
                return "已回退到普通 role 执行", True

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )

            result = manager._run_heartbeat_branch(
                {
                    "branch_id": "team-miss",
                    "agent_role": "orchestrator-agent",
                    "team_id": "self_mind_stream",
                    "prompt": "请分析这个复杂任务",
                },
                str(workspace),
                60,
                "auto",
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["team_id"], "self_mind_stream")
            self.assertIn("已回退到普通 role 执行", result["output"])
            self.assertTrue(calls)

    def test_planning_prompt_includes_subagents_and_teams_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=lambda *_: ("", False),
            )
            manager._render_available_subagents_prompt = lambda _workspace: "- discussion-agent @ ./butler_main/butler_bot_agent/agents/sub-agents/discussion-agent.md"
            manager._render_available_teams_prompt = lambda _workspace: "- research-implement-review @ ./butler_main/butler_bot_agent/agents/teams/research-implement-review.json"
            manager._render_public_agent_library_prompt = lambda _workspace: "- autogen-group-chat (event-driven-team)"

            prompt = manager._build_heartbeat_planning_prompt(
                {"workspace_root": str(workspace)},
                {"enabled": True},
                str(workspace),
            )

            self.assertIn("## 可复用 Sub-Agents", prompt)
            self.assertIn("discussion-agent", prompt)
            self.assertIn("## 可复用 Agent Teams", prompt)
            self.assertIn("research-implement-review", prompt)
            self.assertIn("## 公用 Agent/Team 参考库", prompt)
            self.assertIn("autogen-group-chat", prompt)

    def test_summarize_branch_results_prefers_branch_markdown_blocks(self):
        manager = MemoryManager(
            config_provider=lambda: {"workspace_root": "."},
            run_model_fn=lambda *_: ("", False),
        )

        summary = manager._summarize_heartbeat_branch_results(
            {"chosen_mode": "short_task"},
            [
                {
                    "branch_id": "branch-a",
                    "run_mode": "parallel",
                    "ok": True,
                    "tell_user_markdown": "## 分支 A\n- 完成了用户可见整理。",
                    "output": "内部长输出",
                },
                {
                    "branch_id": "branch-b",
                    "run_mode": "serial",
                    "ok": False,
                    "tell_user_markdown": "",
                    "error": "第二分支失败",
                },
            ],
        )

        self.assertIn("## 值得同步", summary)
        self.assertIn("## 分支 A", summary)
        self.assertIn("## 需关注", summary)
        self.assertIn("第二分支失败", summary)

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
            self.assertIn("内容 / 时间 / 有效性", prompt)
            self.assertIn("[Final]", prompt)
            self.assertIn("[Working n/m]", prompt)

    def test_run_branch_uses_update_agent_for_maintenance_execution_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            root = Path(tmp)
            update_agent_path = root / "butler_main" / "butler_bot_agent" / "agents" / "sub-agents" / "update-agent.md"
            hint_path = root / "butler_main" / "butler_bot_agent" / "agents" / "heartbeat-executor-workspace-hint.md"
            update_agent_path.parent.mkdir(parents=True, exist_ok=True)
            hint_path.parent.mkdir(parents=True, exist_ok=True)
            update_agent_path.write_text("你是 update-agent。负责先找单一真源。", encoding="utf-8")
            hint_path.write_text("【工作区约束】只做安全维护。", encoding="utf-8")

            calls = []

            def fake_model(prompt: str, workspace_path: str, timeout: int, model: str):
                calls.append(prompt)
                return "result: 已完成\nevidence: 已验证\nunresolved: 无\nnext_step: 无", True

            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=fake_model,
            )

            result = manager._heartbeat_orchestrator.run_branch(
                {
                    "branch_id": "upgrade-1",
                    "agent_role": "heartbeat-executor-agent",
                    "execution_kind": "maintenance",
                    "capability_type": "agent_maintenance",
                    "prompt": "请收敛重复 prompt 规则并补验证。",
                },
                str(workspace),
                60,
                "auto",
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["agent_role"], "update-agent")
            self.assertTrue(calls)
            self.assertIn("统一维护入口协议", calls[0])
            self.assertIn("update-agent", calls[0])


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

            self.assertEqual(planner_calls["count"], 2)
            self.assertIn(second_plan["chosen_mode"], {"short_task", "status", "long_task"})

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

            self.assertEqual(planner_calls["count"], 2)
            self.assertIn(second_plan["chosen_mode"], {"short_task", "status", "long_task"})

    def test_first_planner_failure_has_no_backoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = MemoryManager(
                config_provider=lambda: {"workspace_root": str(workspace)},
                run_model_fn=lambda *_: ("执行超时", False),
            )

            orchestrator = manager._heartbeat_orchestrator
            manager._heartbeat_planner_failure_count = 1
            self.assertEqual(orchestrator._planner_failure_backoff_seconds({"enabled": True, "every_seconds": 5}), 0)

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

