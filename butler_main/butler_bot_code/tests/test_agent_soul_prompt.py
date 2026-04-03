import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.chat import prompting as module

module.set_config_provider(lambda: module.CONFIG)


class ButlerAgentSoulPromptTests(unittest.TestCase):
    def setUp(self) -> None:
        module.set_config_provider(lambda: module.CONFIG)

    def test_build_prompt_includes_soul_guidance_and_excerpt(self):
        original_config = dict(module.CONFIG)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                soul_path = root / module.BUTLER_SOUL_FILE_REL
                profile_path = root / module.CURRENT_USER_PROFILE_FILE_REL
                self_mind_path = root / module.SELF_MIND_DIR_REL / "current_context.md"
                cognition_index_path = root / module.SELF_MIND_DIR_REL / "cognition" / "L0_index.json"
                soul_path.parent.mkdir(parents=True, exist_ok=True)
                self_mind_path.parent.mkdir(parents=True, exist_ok=True)
                cognition_index_path.parent.mkdir(parents=True, exist_ok=True)
                soul_path.write_text("# Butler SOUL\n可爱一点，轻快一点。", encoding="utf-8")
                profile_path.write_text("# Current User Profile\n当前用户允许少量自然 emoji，并偏好少客服腔。", encoding="utf-8")
                self_mind_path.write_text("# 当前上下文\n- 最近主线：在整理长期记录机制。", encoding="utf-8")
                cognition_index_path.write_text(
                    '{"categories":[{"name":"价值观","summary":"优先保留连续主线，不把 self_mind 降成普通缓存。","signal_count":2}]}',
                    encoding="utf-8",
                )
                module.CONFIG.clear()
                module.CONFIG.update({"workspace_root": str(root)})

                prompt = module.build_chat_agent_prompt("帮我设计一个长期记录机制")

                self.assertIn("【基础行为】", prompt)
                self.assertIn("有一点可爱和元气", prompt)
                self.assertIn(f"【灵魂真源】@{module.BUTLER_SOUL_FILE}", prompt)
                self.assertIn("可爱一点，轻快一点。", prompt)
                self.assertIn("【当前用户画像】", prompt)
                self.assertIn("优先读取当前用户画像；若不存在再参考模板", prompt)
                self.assertIn("少量自然 emoji", prompt)
                self.assertNotIn("butler-agent.md", prompt)
                self.assertIn("./butler_main/products/chat/assets/roles/chat-agent.md", prompt)
                self.assertIn("./butler_main/products/chat/assets/dialogues/feishu-dialogue.md", prompt)
                self.assertIn("真源：@./butler_main/products/chat/assets/dialogues/feishu-dialogue.md", prompt)
                self.assertIn("摘要：", prompt)
        finally:
            module.CONFIG.clear()
            module.CONFIG.update(original_config)

    def test_build_prompt_includes_skills_when_provided(self):
        prompt = module.build_feishu_agent_prompt(
            "帮我用 skill 整理飞书历史消息",
            skills_prompt="[feishu]\n- feishu-chat-history @ ./butler_main/platform/skills/pool/chat/feishu_chat_history",
        )

        self.assertIn("【可复用 Skills】", prompt)
        self.assertIn("feishu-chat-history", prompt)
        self.assertIn("capability families", prompt)
        self.assertIn("【本轮提醒】", prompt)

    def test_build_prompt_includes_skills_shortlist_even_without_skill_keyword(self):
        prompt = module.build_feishu_agent_prompt(
            "帮我处理这个链接里的内容",
            skills_prompt="[web]\n- web-note-capture-cn @ ./butler_main/platform/skills/pool/chat/web-note-capture-cn",
        )

        self.assertIn("【可复用 Skills】", prompt)
        self.assertIn("family shortlist", prompt)
        self.assertIn("web-note-capture-cn", prompt)

    def test_build_prompt_treats_images_as_first_class_not_ocr_only(self):
        prompt = module.build_feishu_agent_prompt(
            "帮我看一下这张图里讲了什么",
            image_paths=["C:/tmp/demo.png"],
        )

        self.assertIn("【用户附带图片】", prompt)
        self.assertIn("优先直接理解图片内容", prompt)
        self.assertIn("不要把 OCR 当成唯一前置步骤", prompt)

    def test_build_prompt_uses_raw_user_prompt_for_mode_detection(self):
        original_config = dict(module.CONFIG)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                soul_path = root / module.BUTLER_SOUL_FILE_REL
                soul_path.parent.mkdir(parents=True, exist_ok=True)
                soul_path.write_text("# Butler SOUL\n这里是完整灵魂摘录。", encoding="utf-8")
                module.CONFIG.clear()
                module.CONFIG.update({"workspace_root": str(root)})

                prompt = module.build_feishu_agent_prompt(
                    "【recent_memory】\n这里是一大段 recent，长度已经足够长。\n\n【用户消息】\n修一下这个测试",
                    raw_user_prompt="修一下这个测试",
                )

                self.assertIn("mode=chat", prompt)
                self.assertNotIn("【灵魂真源】", prompt)
        finally:
            module.CONFIG.clear()
            module.CONFIG.update(original_config)

    def test_build_prompt_includes_update_agent_for_maintenance_mode(self):
        original_config = dict(module.CONFIG)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                soul_path = root / module.BUTLER_SOUL_FILE_REL
                soul_path.parent.mkdir(parents=True, exist_ok=True)
                soul_path.write_text("# Butler SOUL\n保留人味。", encoding="utf-8")
                module.CONFIG.clear()
                module.CONFIG.update({"workspace_root": str(root)})

                prompt = module.build_feishu_agent_prompt("请升级 prompt 注入顺序并维护 role", raw_user_prompt="请升级 prompt 注入顺序并维护 role")

                self.assertIn("mode=maintenance", prompt)
                self.assertIn("【统一维护入口】", prompt)
                self.assertIn("chat 维护规则已收敛到 chat 自身协议与代码真源", prompt)
        finally:
            module.CONFIG.clear()
            module.CONFIG.update(original_config)

    def test_build_prompt_prefers_chat_bootstrap_assets_over_legacy_bootstrap(self):
        original_config = dict(module.CONFIG)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                chat_bootstrap = root / "butler_main" / "chat" / "assets" / "bootstrap" / "CHAT.md"
                legacy_bootstrap = root / "butler_main" / "legacy_unused" / "bootstrap" / "CHAT.md"
                chat_bootstrap.parent.mkdir(parents=True, exist_ok=True)
                legacy_bootstrap.parent.mkdir(parents=True, exist_ok=True)
                chat_bootstrap.write_text(
                    "# Chat Bootstrap\n\n## baseline\n优先使用 chat/assets 里的 talk bootstrap。\n",
                    encoding="utf-8",
                )
                legacy_bootstrap.write_text(
                    "# Chat Bootstrap\n\n## baseline\n旧 bootstrap 不应再作为 talk 真源。\n",
                    encoding="utf-8",
                )
                module.CONFIG.clear()
                module.CONFIG.update({"workspace_root": str(root)})

                prompt = module.build_feishu_agent_prompt("帮我继续这个任务", raw_user_prompt="帮我继续这个任务")

                self.assertIn("优先使用 chat/assets 里的 talk bootstrap", prompt)
                self.assertNotIn("旧 bootstrap 不应再作为 talk 真源", prompt)
        finally:
            module.CONFIG.clear()
            module.CONFIG.update(original_config)

    def test_build_prompt_includes_query_based_local_memory_hits(self):
        original_config = dict(module.CONFIG)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                profile_path = root / module.CURRENT_USER_PROFILE_FILE_REL
                profile_path.parent.mkdir(parents=True, exist_ok=True)
                profile_path.write_text(
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
        prompt = module.build_feishu_agent_prompt(
            "帮我并行分析这个复杂任务",
            agent_capabilities_prompt=module.render_available_agent_capabilities_prompt(),
        )

        self.assertIn("【Codex 原生并行协作】", prompt)
        self.assertIn("不要为了并行而并行", prompt)
        self.assertIn("统一汇总结论", prompt)

    def test_build_prompt_uses_share_mode_for_shared_links(self):
        prompt = module.build_feishu_agent_prompt(
            "Ocean:\n一个文件让 Claude Code 战斗力翻倍 http://xhslink.com/o/AirylJSxpim\n复制后打开【小红书】查看笔记！",
            skills_prompt="[web]\n- web-note-capture-cn @ ./butler_main/platform/skills/pool/chat/web-note-capture-cn",
            raw_user_prompt="Ocean:\n一个文件让 Claude Code 战斗力翻倍 http://xhslink.com/o/AirylJSxpim\n复制后打开【小红书】查看笔记！",
        )

        self.assertIn("mode=share", prompt)
        self.assertIn("先直接回应内容本身", prompt)
        self.assertIn("不要先播报你准备怎么处理，也不要把本机命令交给用户代跑", prompt)
        self.assertIn("【可复用 Skills】", prompt)

    def test_build_prompt_includes_active_conversation_rules_section(self):
        original_config = dict(module.CONFIG)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                profile_path = root / module.CURRENT_USER_PROFILE_FILE_REL
                profile_path.parent.mkdir(parents=True, exist_ok=True)
                profile_path.write_text(
                    "# Current User Profile\n\n## 当前对话硬约束\n- 以后技术类链接默认走 web 抓取 skill。\n\n## preferences\n- 少客服腔。\n",
                    encoding="utf-8",
                )
                module.CONFIG.clear()
                module.CONFIG.update({"workspace_root": str(root)})

                prompt = module.build_feishu_agent_prompt("继续按刚才规则处理这个链接", raw_user_prompt="继续按刚才规则处理这个链接")

                self.assertIn("【当前对话硬约束 / 最近确认规则】", prompt)
                self.assertIn("以后技术类链接默认走 web 抓取 skill", prompt)
        finally:
            module.CONFIG.clear()
            module.CONFIG.update(original_config)

    def test_build_prompt_pure_level_one_keeps_rules_but_omits_heavy_memory_blocks(self):
        original_config = dict(module.CONFIG)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                soul_path = root / module.BUTLER_SOUL_FILE_REL
                profile_path = root / module.CURRENT_USER_PROFILE_FILE_REL
                self_mind_path = root / module.SELF_MIND_DIR_REL / "current_context.md"
                cognition_index_path = root / module.SELF_MIND_DIR_REL / "cognition" / "L0_index.json"
                soul_path.parent.mkdir(parents=True, exist_ok=True)
                self_mind_path.parent.mkdir(parents=True, exist_ok=True)
                cognition_index_path.parent.mkdir(parents=True, exist_ok=True)
                soul_path.write_text("# Butler SOUL\n可爱一点，轻快一点。", encoding="utf-8")
                profile_path.write_text(
                    "# Current User Profile\n\n## 当前对话硬约束\n- 以后开会记录放桌面。\n\n## preferences\n- 少客服腔。\n",
                    encoding="utf-8",
                )
                self_mind_path.write_text("# 当前上下文\n- 最近主线：整理长期记录机制。", encoding="utf-8")
                cognition_index_path.write_text('{"categories":[{"name":"价值观","summary":"优先保留连续主线。","signal_count":2}]}', encoding="utf-8")
                module.CONFIG.clear()
                module.CONFIG.update({"workspace_root": str(root)})

                prompt = module.build_feishu_agent_prompt(
                    "继续按刚才规则处理这个链接",
                    raw_user_prompt="继续按刚才规则处理这个链接",
                    prompt_purity={"level": 1},
                )

                self.assertIn("【纯净模式】", prompt)
                self.assertIn("【当前对话硬约束 / 最近确认规则】", prompt)
                self.assertIn("以后开会记录放桌面", prompt)
                self.assertNotIn("【当前用户画像】", prompt)
                self.assertNotIn("【长期记忆命中】", prompt)
                self.assertNotIn("【self_mind 当前上下文】", prompt)
                self.assertNotIn("【灵魂真源】", prompt)
                self.assertNotIn("【Bootstrap/SOUL】", prompt)
        finally:
            module.CONFIG.clear()
            module.CONFIG.update(original_config)

    def test_build_prompt_pure_level_two_omits_role_dialogue_and_skills_blocks(self):
        prompt = module.build_feishu_agent_prompt(
            "帮我直接回复一句测试成功",
            raw_user_prompt="帮我直接回复一句测试成功",
            skills_prompt="[web]\n- web-note-capture-cn @ ./butler_main/platform/skills/pool/chat/web-note-capture-cn",
            prompt_purity={"level": 2},
        )

        self.assertIn("【纯净模式】", prompt)
        self.assertNotIn("【角色设置】@", prompt)
        self.assertNotIn("./butler_main/products/chat/assets/dialogues/feishu-dialogue.md", prompt)
        self.assertNotIn("【可复用 Skills】", prompt)

    def test_build_prompt_uses_compact_codex_prompt_without_path_refs(self):
        prompt = module.build_feishu_agent_prompt(
            "帮我直接回复一句测试成功",
            skills_prompt="[web]\n- web-note-capture-cn @ ./butler_main/platform/skills/pool/chat/web-note-capture-cn",
            skill_collection_id="codex_default",
            agent_capabilities_prompt="【Codex 原生并行协作】并行能力由运行时原生提供。",
            raw_user_prompt="帮我直接回复一句测试成功",
            runtime_cli="codex",
        )

        self.assertIn("【Codex Chat 约束】", prompt)
        self.assertIn("【可复用 Skills】", prompt)
        self.assertIn("web-note-capture-cn", prompt)
        self.assertIn("collection=codex_default", prompt)
        self.assertNotIn("【角色设置】@", prompt)
        self.assertNotIn("【长期记忆命中】", prompt)
        self.assertNotIn("discussion-agent", prompt)

    def test_build_prompt_includes_request_intake_block_for_codex(self):
        prompt = module.build_feishu_agent_prompt(
            "ssh 到服务器后系统梳理至少 100 篇文献并写论文现状。",
            raw_user_prompt="ssh 到服务器后系统梳理至少 100 篇文献并写论文现状。",
            runtime_cli="codex",
            request_intake_prompt="【前台分诊】\n- frontdoor_action=choose_execution_mode\n- should_discuss_mode_first=true",
        )

        self.assertIn("【统一前门合同】", prompt)
        self.assertIn("【前台分诊】", prompt)
        self.assertIn("should_discuss_mode_first=true", prompt)

    def test_build_prompt_prefers_frontdoor_context_over_companion_keywords(self):
        prompt = module.build_feishu_agent_prompt(
            "你觉得这个后台任务要怎么推进",
            raw_user_prompt="你觉得这个后台任务要怎么推进",
            request_intake_prompt="【前台分诊】\n- mode=async_program\n- frontdoor_action=discuss_backend_entry\n- explicit_backend_request=true",
            request_intake_decision={
                "mode": "async_program",
                "frontdoor_action": "discuss_backend_entry",
                "explicit_backend_request": True,
            },
        )

        self.assertIn("【前台分诊】", prompt)
        self.assertIn("explicit_backend_request=true", prompt)
        self.assertIn("【后台入口协作协议】", prompt)

    def test_build_prompt_omits_frontdoor_blocks_when_frontdoor_tasks_disabled(self):
        with patch.dict(os.environ, {"BUTLER_CHAT_FRONTDOOR_TASKS_ENABLED": "0"}):
            prompt = module.build_feishu_agent_prompt(
                "你觉得这个后台任务要怎么推进",
                raw_user_prompt="你觉得这个后台任务要怎么推进",
                request_intake_prompt="【前台分诊】\n- mode=async_program\n- frontdoor_action=discuss_backend_entry\n- explicit_backend_request=true",
                request_intake_decision={
                    "mode": "async_program",
                    "frontdoor_action": "discuss_backend_entry",
                    "explicit_backend_request": True,
                },
            )

        self.assertNotIn("【统一前门合同】", prompt)
        self.assertNotIn("【前台分诊】", prompt)
        self.assertNotIn("【前门协作协议】", prompt)
        self.assertNotIn("【后台入口协作协议】", prompt)
        self.assertNotIn("【任务协作协议】", prompt)

    def test_build_prompt_keeps_recent_injected_user_prompt_for_codex(self):
        prompt = module.build_feishu_agent_prompt(
            "【recent_memory】\n- 最近主线：整理 chat recent 注入\n\n【用户消息】\n继续实现",
            raw_user_prompt="继续实现",
            runtime_cli="codex",
        )

        self.assertIn("【Codex Chat 约束】", prompt)
        self.assertIn("【recent_memory】", prompt)
        self.assertIn("整理 chat recent 注入", prompt)
        self.assertIn("继续实现", prompt)

    def test_build_prompt_only_includes_self_mind_context_when_explicitly_relevant(self):
        original_config = dict(module.CONFIG)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                soul_path = root / module.BUTLER_SOUL_FILE_REL
                profile_path = root / module.CURRENT_USER_PROFILE_FILE_REL
                self_mind_path = root / module.SELF_MIND_DIR_REL / "current_context.md"
                cognition_index_path = root / module.SELF_MIND_DIR_REL / "cognition" / "L0_index.json"
                soul_path.parent.mkdir(parents=True, exist_ok=True)
                self_mind_path.parent.mkdir(parents=True, exist_ok=True)
                cognition_index_path.parent.mkdir(parents=True, exist_ok=True)
                soul_path.write_text("# Butler SOUL\n可爱一点，轻快一点。", encoding="utf-8")
                profile_path.write_text("# Current User Profile\n当前用户允许少量自然 emoji。", encoding="utf-8")
                self_mind_path.write_text("# 当前上下文\n- 最近主线：在整理长期记录机制。", encoding="utf-8")
                cognition_index_path.write_text(
                    '{"categories":[{"name":"价值观","summary":"优先保留连续主线。","signal_count":2}]}',
                    encoding="utf-8",
                )
                module.CONFIG.clear()
                module.CONFIG.update({"workspace_root": str(root)})

                prompt = module.build_feishu_agent_prompt("聊聊 self-mind 最近在想什么", raw_user_prompt="聊聊 self-mind 最近在想什么")

                self.assertIn("【self_mind 认知体系】", prompt)
                self.assertIn("【self_mind 当前上下文】", prompt)
        finally:
            module.CONFIG.clear()
            module.CONFIG.update(original_config)

    def test_build_prompt_switches_channel_block_for_cli(self):
        prompt = module.build_chat_agent_prompt(
            "把结果直接写给我",
            raw_user_prompt="把结果直接写给我",
            channel="cli",
        )

        self.assertIn("【当前对话】", prompt)
        self.assertIn("CLI 对话", prompt)
        self.assertIn("纯文本终端对话", prompt)
        self.assertIn("./butler_main/products/chat/assets/dialogues/cli-dialogue.md", prompt)
        self.assertIn("【交付方式】", prompt)
        self.assertNotIn("【decide】若需发送产出文件给用户", prompt)
        self.assertNotIn("飞书聊天", prompt)

    def test_build_prompt_switches_channel_block_for_weixin(self):
        prompt = module.build_chat_agent_prompt(
            "给我一个简短结论",
            raw_user_prompt="给我一个简短结论",
            channel="weixi",
        )

        self.assertIn("【当前对话】", prompt)
        self.assertIn("微信对话", prompt)
        self.assertIn("聊天消息，文本优先，也可补充图片和文件", prompt)
        self.assertIn("./butler_main/products/chat/assets/dialogues/weixin-dialogue.md", prompt)
        self.assertIn("【decide】若需发送产出文件给用户", prompt)
        self.assertNotIn("飞书聊天", prompt)

    def test_build_prompt_keeps_shared_memory_and_skills_across_dialogue_entries(self):
        original_config = dict(module.CONFIG)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                profile_path = root / module.CURRENT_USER_PROFILE_FILE_REL
                profile_path.parent.mkdir(parents=True, exist_ok=True)
                profile_path.write_text(
                    "# Current User Profile\n\n## preferences\n- 用户偏好少客服腔、直接一点。\n",
                    encoding="utf-8",
                )
                module.CONFIG.clear()
                module.CONFIG.update({"workspace_root": str(root)})

                prompts = {
                    "feishu": module.build_chat_agent_prompt(
                        "继续按我的偏好回复",
                        raw_user_prompt="继续按我的偏好回复",
                        channel="feishu",
                        skills_prompt="[web]\n- web-note-capture-cn @ ./butler_main/platform/skills/web_note_capture_cn",
                    ),
                    "weixin": module.build_chat_agent_prompt(
                        "继续按我的偏好回复",
                        raw_user_prompt="继续按我的偏好回复",
                        channel="weixin",
                        skills_prompt="[web]\n- web-note-capture-cn @ ./butler_main/platform/skills/web_note_capture_cn",
                    ),
                    "cli": module.build_chat_agent_prompt(
                        "继续按我的偏好回复",
                        raw_user_prompt="继续按我的偏好回复",
                        channel="cli",
                        skills_prompt="[web]\n- web-note-capture-cn @ ./butler_main/platform/skills/web_note_capture_cn",
                    ),
                }

                self.assertIn("少客服腔、直接一点", prompts["feishu"])
                self.assertIn("少客服腔、直接一点", prompts["weixin"])
                self.assertIn("少客服腔、直接一点", prompts["cli"])
                self.assertIn("web-note-capture-cn", prompts["feishu"])
                self.assertIn("web-note-capture-cn", prompts["weixin"])
                self.assertIn("web-note-capture-cn", prompts["cli"])
                self.assertIn("./butler_main/products/chat/assets/dialogues/feishu-dialogue.md", prompts["feishu"])
                self.assertIn("./butler_main/products/chat/assets/dialogues/weixin-dialogue.md", prompts["weixin"])
                self.assertIn("./butler_main/products/chat/assets/dialogues/cli-dialogue.md", prompts["cli"])
        finally:
            module.CONFIG.clear()
            module.CONFIG.update(original_config)


if __name__ == "__main__":
    unittest.main()
