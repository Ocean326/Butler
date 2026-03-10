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
                soul_path.parent.mkdir(parents=True, exist_ok=True)
                soul_path.write_text("# Butler SOUL\n可爱一点，轻快一点。", encoding="utf-8")
                profile_path.write_text("# Current User Profile\n当前用户允许少量自然 emoji，并偏好少客服腔。", encoding="utf-8")
                module.CONFIG.clear()
                module.CONFIG.update({"workspace_root": str(root)})

                prompt = module.build_feishu_agent_prompt("帮我设计一个长期记录机制")

                self.assertIn("【灵魂基线】", prompt)
                self.assertIn("有一点可爱和元气", prompt)
                self.assertIn(f"【灵魂真源】@{module.prompt_path_text(module.BUTLER_SOUL_FILE_REL)}", prompt)
                self.assertIn("可爱一点，轻快一点。", prompt)
                self.assertIn("【当前用户画像】", prompt)
                self.assertIn("少量自然 emoji", prompt)
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


if __name__ == "__main__":
    unittest.main()