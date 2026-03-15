import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

if "requests" not in sys.modules:
    sys.modules["requests"] = types.ModuleType("requests")
if "lark_oapi" not in sys.modules:
    fake_lark = types.ModuleType("lark_oapi")
    fake_lark.ws = types.SimpleNamespace()
    sys.modules["lark_oapi"] = fake_lark

spec = importlib.util.spec_from_file_location("butler_agent", MODULE_DIR / "agent.py")
if spec is None or spec.loader is None:
    raise RuntimeError("failed to load agent module")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class ButlerAgentSoulPromptTests(unittest.TestCase):
    def test_build_prompt_includes_soul_guidance_and_excerpt(self):
        original_config = dict(module.CONFIG)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                soul_path = root / "butler_main" / "butler_bot_agent" / "agents" / "local_memory" / "Butler_SOUL.md"
                profile_path = root / "butler_main" / "butler_bot_agent" / "agents" / "local_memory" / "Current_User_Profile.private.md"
                butler_agent_path = root / "butler_main" / "butler_bot_agent" / "agents" / "butler-agent.md"
                self_mind_path = root / "butler_main" / "butle_bot_space" / "self_mind" / "current_context.md"
                cognition_index_path = root / "butler_main" / "butle_bot_space" / "self_mind" / "cognition" / "L0_index.json"
                soul_path.parent.mkdir(parents=True, exist_ok=True)
                self_mind_path.parent.mkdir(parents=True, exist_ok=True)
                cognition_index_path.parent.mkdir(parents=True, exist_ok=True)
                soul_path.write_text("# Butler SOUL\n可爱一点，轻快一点。", encoding="utf-8")
                profile_path.write_text("# Current User Profile\n当前用户允许少量自然 emoji，并偏好少客服腔。", encoding="utf-8")
                butler_agent_path.write_text("# Butler Main Agent\n先顺着主线想，再决定怎么说。", encoding="utf-8")
                self_mind_path.write_text("# 当前上下文\n- 最近主线：在整理长期记录机制。", encoding="utf-8")
                cognition_index_path.write_text(
                    '{"categories":[{"name":"价值观","summary":"优先保留连续主线，不把 self_mind 降成普通缓存。","signal_count":2}]}',
                    encoding="utf-8",
                )
                module.CONFIG.clear()
                module.CONFIG.update({"workspace_root": str(root)})

                prompt = module.build_feishu_agent_prompt("帮我设计一个长期记录机制")

                self.assertIn("【灵魂基线】", prompt)
                self.assertIn("有一点可爱和元气", prompt)
                self.assertIn(f"【灵魂真源】@{module.prompt_path_text(module.BUTLER_SOUL_FILE_REL)}", prompt)
                self.assertIn("可爱一点，轻快一点。", prompt)
                self.assertIn("【当前用户画像】", prompt)
                self.assertIn("少量自然 emoji", prompt)
                self.assertIn("【主意识真源】", prompt)
                self.assertIn("先顺着主线想，再决定怎么说。", prompt)
                self.assertIn("【self_mind 认知体系】", prompt)
                self.assertIn("优先保留连续主线", prompt)
                self.assertIn("【self_mind 当前上下文】", prompt)
                self.assertIn("最近主线：在整理长期记录机制", prompt)
        finally:
            module.CONFIG.clear()
            module.CONFIG.update(original_config)

    def test_build_prompt_includes_skills_when_provided(self):
        prompt = module.build_feishu_agent_prompt(
            "帮我整理飞书历史消息",
            skills_prompt="[feishu]\n- feishu-chat-history @ ./butler_main/butler_bot_agent/skills/feishu_chat_history",
        )

        self.assertIn("【可复用 Skills】", prompt)
        self.assertIn("feishu-chat-history", prompt)
        self.assertIn("核心 DNA", prompt)

    def test_build_prompt_uses_raw_user_prompt_for_mode_detection(self):
        original_config = dict(module.CONFIG)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                soul_path = root / "butler_main" / "butler_bot_agent" / "agents" / "local_memory" / "Butler_SOUL.md"
                butler_agent_path = root / "butler_main" / "butler_bot_agent" / "agents" / "butler-agent.md"
                soul_path.parent.mkdir(parents=True, exist_ok=True)
                soul_path.write_text("# Butler SOUL\n这里是完整灵魂摘录。", encoding="utf-8")
                butler_agent_path.write_text("# Butler Main Agent\n维持主线判断。", encoding="utf-8")
                module.CONFIG.clear()
                module.CONFIG.update({"workspace_root": str(root)})

                prompt = module.build_feishu_agent_prompt(
                    "【recent_memory】\n这里是一大段 recent，长度已经足够长。\n\n【用户消息】\n修一下这个测试",
                    raw_user_prompt="修一下这个测试",
                )

                self.assertIn("mode=execution", prompt)
                self.assertNotIn("【灵魂真源】", prompt)
        finally:
            module.CONFIG.clear()
            module.CONFIG.update(original_config)

    def test_build_prompt_includes_update_agent_for_maintenance_mode(self):
        original_config = dict(module.CONFIG)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                update_agent_path = root / "butler_main" / "butler_bot_agent" / "agents" / "sub-agents" / "update-agent.md"
                butler_agent_path = root / "butler_main" / "butler_bot_agent" / "agents" / "butler-agent.md"
                soul_path = root / "butler_main" / "butler_bot_agent" / "agents" / "local_memory" / "Butler_SOUL.md"
                update_agent_path.parent.mkdir(parents=True, exist_ok=True)
                soul_path.parent.mkdir(parents=True, exist_ok=True)
                update_agent_path.write_text("# update-agent\n先找单一真源，再收敛重复规则。", encoding="utf-8")
                butler_agent_path.write_text("# Butler Main Agent\n主意识先判断后表达。", encoding="utf-8")
                soul_path.write_text("# Butler SOUL\n保留人味。", encoding="utf-8")
                module.CONFIG.clear()
                module.CONFIG.update({"workspace_root": str(root)})

                prompt = module.build_feishu_agent_prompt("请升级 prompt 注入顺序并维护 role", raw_user_prompt="请升级 prompt 注入顺序并维护 role")

                self.assertIn("mode=maintenance", prompt)
                self.assertIn("【统一维护入口】", prompt)
                self.assertIn("先找单一真源，再收敛重复规则", prompt)
        finally:
            module.CONFIG.clear()
            module.CONFIG.update(original_config)

    def test_build_prompt_includes_query_based_local_memory_hits(self):
        original_config = dict(module.CONFIG)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                local_dir = root / "butler_main" / "butler_bot_agent" / "agents" / "local_memory"
                butler_agent_path = root / "butler_main" / "butler_bot_agent" / "agents" / "butler-agent.md"
                local_dir.mkdir(parents=True, exist_ok=True)
                butler_agent_path.parent.mkdir(parents=True, exist_ok=True)
                butler_agent_path.write_text("# Butler Main Agent\n先判断主线。", encoding="utf-8")
                (local_dir / "Current_User_Profile.private.md").write_text(
                    "# Current User Profile\n\n## 当前结论\n- 用户偏好少客服腔、自然一点。\n",
                    encoding="utf-8",
                )
                module.CONFIG.clear()
                module.CONFIG.update({"workspace_root": str(root)})

                prompt = module.build_feishu_agent_prompt("请按偏好少客服腔地回复我", raw_user_prompt="请按偏好少客服腔地回复我")

                self.assertIn("【长期记忆命中】", prompt)
                self.assertIn("少客服腔", prompt)
        finally:
            module.CONFIG.clear()
            module.CONFIG.update(original_config)

    def test_build_prompt_includes_agent_capability_runtime_protocol(self):
        original_config = dict(module.CONFIG)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                subagent_path = root / "butler_main" / "butler_bot_agent" / "agents" / "sub-agents" / "discussion-agent.md"
                team_path = root / "butler_main" / "butler_bot_agent" / "agents" / "teams" / "research-implement-review.json"
                public_lib_path = root / "butler_main" / "butler_bot_agent" / "agents" / "public-library" / "agent_public_library.json"
                butler_agent_path = root / "butler_main" / "butler_bot_agent" / "agents" / "butler-agent.md"
                subagent_path.parent.mkdir(parents=True, exist_ok=True)
                team_path.parent.mkdir(parents=True, exist_ok=True)
                public_lib_path.parent.mkdir(parents=True, exist_ok=True)
                subagent_path.write_text("---\nname: discussion-agent\ndescription: 负责讨论复杂问题。\n---\n# discussion-agent", encoding="utf-8")
                team_path.write_text(
                    '{"team_id":"research-implement-review","name":"Research Implement Review","description":"并行调研后汇总。","execution_mode":"mixed","steps":[{"step_id":"s1","mode":"serial","members":[{"role":"discussion-agent","task":"{task}"}]}]}',
                    encoding="utf-8",
                )
                public_lib_path.write_text(
                    '{"items":[{"capability_id":"autogen-group-chat","name":"AutoGen Group Chat","category":"event-driven-team","description":"manager-led team","source_url":"https://example.com"}]}',
                    encoding="utf-8",
                )
                butler_agent_path.write_text("# Butler Main Agent\n主意识。", encoding="utf-8")
                module.CONFIG.clear()
                module.CONFIG.update({"workspace_root": str(root)})

                prompt = module.build_feishu_agent_prompt(
                    "帮我并行分析这个复杂任务",
                    agent_capabilities_prompt=module.render_available_agent_capabilities_prompt(str(root)),
                )

                self.assertIn("【可复用 Sub-Agents 与 Agent Teams】", prompt)
                self.assertIn("discussion-agent", prompt)
                self.assertIn("research-implement-review", prompt)
                self.assertIn("autogen-group-chat", prompt)
                self.assertIn("【agent_runtime_request_json】", prompt)
        finally:
            module.CONFIG.clear()
            module.CONFIG.update(original_config)


if __name__ == "__main__":
    unittest.main()