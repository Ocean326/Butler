import sys
import json
import unittest
from pathlib import Path
from unittest import mock
from types import SimpleNamespace


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
sys.path.insert(0, str(MODULE_DIR))

import agent  # noqa: E402


class _ImmediateThread:
    def __init__(self, target=None, daemon=None, args=None, kwargs=None):
        self._target = target
        self._args = tuple(args or ())
        self._kwargs = dict(kwargs or {})

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)


class AgentMessageFlowTests(unittest.TestCase):
    def test_extract_message_includes_quote_and_rich_text(self):
        payload = {
            "text": "用PaddleOCR吧",
            "quote": {"text": "把今天那条小红书连同图片 OCR 一起整理"},
            "content": [
                [{"tag": "text", "text": "补充：输出到 BrainStorm"}],
            ],
        }
        data = SimpleNamespace(event=SimpleNamespace(message=SimpleNamespace(message_id="mid-q", content=json.dumps(payload, ensure_ascii=False))))

        message_id, text, image_keys = agent._extract_message(data)

        self.assertEqual(message_id, "mid-q")
        self.assertEqual(image_keys, [])
        self.assertIn("【引用内容】", text)
        self.assertIn("图片 OCR", text)
        self.assertIn("补充：输出到 BrainStorm", text)

    def test_normalize_feishu_text_repairs_markdown_heading_spacing(self):
        text = "###1. 标题\r\n-条目A"
        normalized = agent._normalize_feishu_text(text)
        self.assertIn("### 1. 标题", normalized)
        self.assertIn("- 条目A", normalized)

    def test_collapse_duplicate_reply_blocks_removes_adjacent_duplicates(self):
        text = "第一段 😀\n\n第二段 😼\n\n第二段 😼\n\n第三段"
        collapsed = agent._collapse_duplicate_reply_blocks(text)
        self.assertEqual(collapsed, "第一段 😀\n\n第二段 😼\n\n第三段")

    def test_stream_callback_does_not_send_segment_reply(self):
        sent = []

        def fake_run(prompt, stream_callback=None, image_paths=None):
            if stream_callback:
                stream_callback("第一段")
                stream_callback("第一段\n第二段")
            return "最终完整回复"

        with mock.patch.object(agent, "_claim_message", return_value=True), \
             mock.patch.object(agent.threading, "Thread", _ImmediateThread), \
             mock.patch.object(agent, "get_config", return_value={"workspace_root": "."}), \
             mock.patch.object(agent, "_parse_decide_from_reply", side_effect=lambda text: (text, [])), \
             mock.patch.object(agent, "_send_output_files"), \
             mock.patch.object(agent, "_send_deduped_reply", side_effect=lambda message_id, text, **kwargs: sent.append((kwargs.get("channel"), text)) or True):
            agent.handle_message_async(
                message_id="mid-1",
                prompt="hello",
                image_keys=None,
                run_agent_fn=fake_run,
                supports_images=False,
                supports_stream_segment=True,
            )

        self.assertEqual(sent, [("final", "最终完整回复")])

    def test_immediate_receipt_is_sent_before_final_reply(self):
        sent = []

        def fake_run(prompt, stream_callback=None, image_paths=None):
            return "最终完整回复"

        with mock.patch.object(agent, "_claim_message", return_value=True), \
             mock.patch.object(agent.threading, "Thread", _ImmediateThread), \
             mock.patch.object(agent, "get_config", return_value={"workspace_root": "."}), \
             mock.patch.object(agent, "_parse_decide_from_reply", side_effect=lambda text: (text, [])), \
             mock.patch.object(agent, "_send_output_files"), \
             mock.patch.object(agent, "_send_deduped_reply", side_effect=lambda message_id, text, **kwargs: sent.append((kwargs.get("channel"), text)) or True):
            agent.handle_message_async(
                message_id="mid-receipt",
                prompt="hello",
                image_keys=None,
                run_agent_fn=fake_run,
                supports_images=False,
                supports_stream_segment=False,
                immediate_receipt_text="我在，先接住这句，马上回你。",
            )

        self.assertEqual(
            sent,
            [
                ("receipt", "我在，先接住这句，马上回你。"),
                ("final", "最终完整回复"),
            ],
        )

    def test_empty_result_uses_latest_stream_snapshot_only(self):
        sent = []
        persisted = []

        def fake_run(prompt, stream_callback=None, image_paths=None):
            if stream_callback:
                stream_callback("一")
                stream_callback("一二")
                stream_callback("一二三")
            return ""

        with mock.patch.object(agent, "_claim_message", return_value=True), \
             mock.patch.object(agent.threading, "Thread", _ImmediateThread), \
             mock.patch.object(agent, "get_config", return_value={"workspace_root": "."}), \
             mock.patch.object(agent, "_parse_decide_from_reply", side_effect=lambda text: (text, [])), \
             mock.patch.object(agent, "_send_output_files"), \
             mock.patch.object(agent, "_send_deduped_reply", side_effect=lambda message_id, text, **kwargs: sent.append((kwargs.get("channel"), text)) or True):
            agent.handle_message_async(
                message_id="mid-2",
                prompt="hello",
                image_keys=None,
                run_agent_fn=fake_run,
                supports_images=False,
                supports_stream_segment=True,
                on_reply_sent=lambda user_prompt, assistant_reply: persisted.append(assistant_reply),
            )

        self.assertEqual(sent, [("final", "一二三")])
        self.assertEqual(persisted, ["一二三"])


if __name__ == "__main__":
    unittest.main()
