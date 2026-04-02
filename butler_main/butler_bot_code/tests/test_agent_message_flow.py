import sys
import json
import threading
import unittest
from pathlib import Path
from unittest import mock
from types import SimpleNamespace

BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BUTLER_MAIN_DIR))

from agents_os.contracts import FileAsset, OutputBundle, TextBlock
from butler_main.chat.feishu_bot import transport


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

        message_id, text, image_keys = transport._extract_message(data)

        self.assertEqual(message_id, "mid-q")
        self.assertEqual(image_keys, [])
        self.assertIn("【引用内容】", text)
        self.assertIn("图片 OCR", text)
        self.assertIn("补充：输出到 BrainStorm", text)

    def test_normalize_feishu_text_repairs_markdown_heading_spacing(self):
        text = "###1. 标题\r\n-条目A"
        normalized = transport._normalize_feishu_text(text)
        self.assertIn("### 1. 标题", normalized)
        self.assertIn("- 条目A", normalized)

    def test_collapse_duplicate_reply_blocks_removes_adjacent_duplicates(self):
        text = "第一段 😀\n\n第二段 😼\n\n第二段 😼\n\n第三段"
        collapsed = transport._collapse_duplicate_reply_blocks(text)
        self.assertEqual(collapsed, "第一段 😀\n\n第二段 😼\n\n第三段")

    def test_stream_callback_updates_existing_reply_then_finalizes(self):
        updates = []
        placeholders = []

        def fake_run(prompt, stream_callback=None, image_paths=None):
            if stream_callback:
                stream_callback("第一段")
                stream_callback("第一段\n第二段")
            return "最终完整回复"

        with mock.patch.object(transport, "_claim_message", return_value=True), \
             mock.patch.object(transport.threading, "Thread", _ImmediateThread), \
             mock.patch.object(transport, "get_config", return_value={"workspace_root": "."}), \
             mock.patch.object(
                 transport,
                 "_create_stream_reply_placeholder",
                 side_effect=lambda message_id, text, **kwargs: placeholders.append((message_id, text, kwargs)) or "om_reply_1",
             ), \
             mock.patch.object(transport, "_parse_decide_from_reply", side_effect=lambda text: (text, [])), \
             mock.patch.object(transport, "_send_output_files"), \
             mock.patch.object(transport, "_update_stream_reply_message", side_effect=lambda message_id, text, **kwargs: updates.append((message_id, text, kwargs.get("include_card_actions"))) or True), \
             mock.patch.object(transport, "_send_deduped_reply") as send_reply:
            transport.handle_message_async(
                message_id="mid-1",
                prompt="hello",
                image_keys=None,
                run_agent_fn=fake_run,
                supports_images=False,
                supports_stream_segment=True,
            )

        self.assertEqual(len(placeholders), 1)
        self.assertEqual(placeholders[0][0], "mid-1")
        self.assertEqual(placeholders[0][1], transport.STREAM_PLACEHOLDER_TEXT)
        self.assertIn("request_id", placeholders[0][2]["card_action_value_extras"])
        self.assertEqual(
            updates,
            [
                ("om_reply_1", "## 过程\n\n第一段", True),
                ("om_reply_1", "## 过程\n\n第一段\n\n第二段", True),
                ("om_reply_1", "最终完整回复", False),
            ],
        )
        send_reply.assert_not_called()

    def test_stream_placeholder_uses_first_real_segment_instead_of_thinking_text(self):
        placeholders = []

        def fake_run(prompt, stream_callback=None, image_paths=None):
            if stream_callback:
                stream_callback("首段输出")
            return "最终完整回复"

        with mock.patch.object(transport, "_claim_message", return_value=True), \
             mock.patch.object(transport.threading, "Thread", _ImmediateThread), \
             mock.patch.object(transport, "get_config", return_value={"workspace_root": "."}), \
             mock.patch.object(
                 transport,
                 "_create_stream_reply_placeholder",
                 side_effect=lambda message_id, text, **kwargs: placeholders.append((message_id, text, kwargs)) or "om_reply_3",
             ), \
             mock.patch.object(transport, "_parse_decide_from_reply", side_effect=lambda text: (text, [])), \
             mock.patch.object(transport, "_send_output_files"), \
             mock.patch.object(transport, "_update_stream_reply_message", return_value=True), \
             mock.patch.object(transport, "_send_deduped_reply"):
            transport.handle_message_async(
                message_id="mid-3",
                prompt="hello",
                image_keys=None,
                run_agent_fn=fake_run,
                supports_images=False,
                supports_stream_segment=True,
            )

        self.assertEqual(len(placeholders), 1)
        self.assertEqual(placeholders[0][0], "mid-3")
        self.assertEqual(placeholders[0][1], transport.STREAM_PLACEHOLDER_TEXT)

    def test_processing_receipt_is_delayed_and_includes_runtime_label(self):
        sent = []
        receipt_sent = threading.Event()
        final_sent = threading.Event()
        release_run = threading.Event()

        def fake_run(prompt, stream_callback=None, image_paths=None):
            self.assertEqual(prompt, "hello")
            release_run.wait(timeout=1)
            return "最终完整回复"

        fake_run.describe_runtime_target = lambda prompt, invocation_metadata=None: {"cli": "codex", "model": "gpt-5.4"}

        def fake_send(message_id, text, **kwargs):
            sent.append((kwargs.get("channel"), text))
            if kwargs.get("channel") == "receipt":
                receipt_sent.set()
            if kwargs.get("channel") == "final":
                final_sent.set()
            return True

        with mock.patch.object(transport, "_claim_message", return_value=True), \
             mock.patch.object(transport, "get_config", return_value={"workspace_root": "."}), \
             mock.patch.object(transport, "_processing_receipt_delay_seconds", return_value=0.01), \
             mock.patch.object(transport, "_parse_decide_from_reply", side_effect=lambda text: (text, [])), \
             mock.patch.object(transport, "_send_output_files"), \
             mock.patch.object(transport, "_send_deduped_reply", side_effect=fake_send):
            transport.handle_message_async(
                message_id="mid-receipt",
                prompt="hello",
                image_keys=None,
                run_agent_fn=fake_run,
                supports_images=False,
                supports_stream_segment=False,
                immediate_receipt_text="处理中，{cli} {model} 模型调用中…",
            )
            self.assertTrue(receipt_sent.wait(timeout=0.5))
            release_run.set()
            self.assertTrue(final_sent.wait(timeout=0.5))
            self.assertEqual(
                sent,
                [
                    ("receipt", "处理中，codex gpt-5.4 模型调用中…"),
                    ("final", "最终完整回复"),
                ],
            )

    def test_empty_result_uses_latest_stream_snapshot_only(self):
        updates = []
        persisted = []

        def fake_run(prompt, stream_callback=None, image_paths=None):
            if stream_callback:
                stream_callback("一")
                stream_callback("一二")
                stream_callback("一二三")
            return ""

        with mock.patch.object(transport, "_claim_message", return_value=True), \
             mock.patch.object(transport.threading, "Thread", _ImmediateThread), \
             mock.patch.object(transport, "get_config", return_value={"workspace_root": "."}), \
             mock.patch.object(transport, "_create_stream_reply_placeholder", return_value="om_reply_2"), \
             mock.patch.object(transport, "_parse_decide_from_reply", side_effect=lambda text: (text, [])), \
             mock.patch.object(transport, "_send_output_files"), \
             mock.patch.object(transport, "_update_stream_reply_message", side_effect=lambda message_id, text, **kwargs: updates.append((message_id, text, kwargs.get("include_card_actions"))) or True), \
             mock.patch.object(transport, "_send_deduped_reply") as send_reply:
            transport.handle_message_async(
                message_id="mid-2",
                prompt="hello",
                image_keys=None,
                run_agent_fn=fake_run,
                supports_images=False,
                supports_stream_segment=True,
                on_reply_sent=lambda user_prompt, assistant_reply: persisted.append(assistant_reply),
            )

        self.assertEqual(
            updates,
            [
                ("om_reply_2", "## 过程\n\n一", True),
                ("om_reply_2", "## 过程\n\n一\n\n一二", True),
                ("om_reply_2", "## 过程\n\n一\n\n一二\n\n一二三", True),
                ("om_reply_2", "一二三", False),
            ],
        )
        self.assertEqual(persisted, ["一二三"])
        send_reply.assert_not_called()

    def test_stream_process_entries_append_only_incremental_delta_for_snapshot_growth(self):
        self.assertEqual(transport._extract_incremental_stream_entry("第一段", "第一段\n第二段"), "第二段")
        self.assertEqual(transport._extract_incremental_stream_entry("一二", "一二三"), "一二三")

    def test_final_reply_does_not_enable_card_actions(self):
        with mock.patch.object(transport, "_claim_reply", return_value=True), \
             mock.patch.object(transport, "reply_message", return_value=True) as reply_message:
            ok = transport._send_deduped_reply("mid-final", "最终回复", channel="final")

        self.assertTrue(ok)
        reply_message.assert_called_once_with(
            "mid-final",
            "最终回复",
            use_interactive=True,
            include_card_actions=False,
        )

    def test_delivery_callback_success_skips_legacy_reply_and_output_files(self):
        delivered = []

        def fake_run(prompt, stream_callback=None, image_paths=None):
            return "最终完整回复"

        def fake_delivery(message_id, run_agent_fn, workspace):
            delivered.append((message_id, workspace, run_agent_fn is fake_run))
            return True

        with mock.patch.object(transport, "_claim_message", return_value=True), \
             mock.patch.object(transport.threading, "Thread", _ImmediateThread), \
             mock.patch.object(transport, "get_config", return_value={"workspace_root": "."}), \
             mock.patch.object(transport, "_parse_decide_from_reply", side_effect=lambda text: (text, [])), \
             mock.patch.object(transport, "_send_output_files") as send_output_files, \
             mock.patch.object(transport, "_send_deduped_reply") as send_deduped_reply:
            transport.handle_message_async(
                message_id="mid-chat",
                prompt="hello",
                image_keys=None,
                run_agent_fn=fake_run,
                supports_images=False,
                supports_stream_segment=False,
                deliver_output_bundle_fn=fake_delivery,
            )

        self.assertEqual(delivered, [("mid-chat", ".", True)])
        send_deduped_reply.assert_not_called()
        send_output_files.assert_not_called()

    def test_streaming_delivery_callback_sends_only_media_and_skips_legacy_file_chain(self):
        delivered = []

        def fake_run(prompt, stream_callback=None, image_paths=None):
            if stream_callback:
                stream_callback("第一段")
            return "最终完整回复"

        def fake_delivery(message_id, run_agent_fn, workspace, *, send_text=True):
            delivered.append((message_id, workspace, run_agent_fn is fake_run, send_text))
            return True

        with mock.patch.object(transport, "_claim_message", return_value=True), \
             mock.patch.object(transport.threading, "Thread", _ImmediateThread), \
             mock.patch.object(transport, "get_config", return_value={"workspace_root": "."}), \
             mock.patch.object(transport, "_create_stream_reply_placeholder", return_value="om_reply_stream_media"), \
             mock.patch.object(transport, "_parse_decide_from_reply", side_effect=lambda text: (text, [])), \
             mock.patch.object(transport, "_send_output_files") as send_output_files, \
             mock.patch.object(transport, "_update_stream_reply_message", return_value=True), \
             mock.patch.object(transport, "_send_deduped_reply") as send_deduped_reply:
            transport.handle_message_async(
                message_id="mid-stream-media",
                prompt="hello",
                image_keys=None,
                run_agent_fn=fake_run,
                supports_images=False,
                supports_stream_segment=True,
                deliver_output_bundle_fn=fake_delivery,
            )

        self.assertEqual(delivered, [("mid-stream-media", ".", True, False)])
        send_deduped_reply.assert_not_called()
        send_output_files.assert_not_called()

    def test_legacy_file_fallback_reads_decide_from_turn_raw_reply(self):
        sent_decide_lists = []

        def fake_run(prompt, stream_callback=None, image_paths=None):
            return "正文回复"

        fake_run.get_turn_raw_reply = lambda: '正文回复\n【decide】\n[{"send":"./工作区/report.md"}]'

        with mock.patch.object(transport, "_claim_message", return_value=True), \
             mock.patch.object(transport.threading, "Thread", _ImmediateThread), \
             mock.patch.object(transport, "get_config", return_value={"workspace_root": "."}), \
             mock.patch.object(transport, "_send_deduped_reply"), \
             mock.patch.object(
                 transport,
                 "_send_output_files",
                 side_effect=lambda message_id, workspace, decide_list=None: sent_decide_lists.append(list(decide_list or [])),
             ):
            transport.handle_message_async(
                message_id="mid-file-raw",
                prompt="hello",
                image_keys=None,
                run_agent_fn=fake_run,
                supports_images=False,
                supports_stream_segment=False,
            )

        self.assertEqual(sent_decide_lists, [[{"send": "./工作区/report.md"}]])

    def test_legacy_file_fallback_uses_output_bundle_when_visible_reply_has_no_decide(self):
        sent_decide_lists = []

        def fake_run(prompt, stream_callback=None, image_paths=None):
            return "正文回复"

        fake_run.get_turn_output_bundle = lambda: OutputBundle(
            text_blocks=[TextBlock(text="正文回复")],
            files=[FileAsset(path="./工作区/report.md")],
        )

        with mock.patch.object(transport, "_claim_message", return_value=True), \
             mock.patch.object(transport.threading, "Thread", _ImmediateThread), \
             mock.patch.object(transport, "get_config", return_value={"workspace_root": "."}), \
             mock.patch.object(transport, "_send_deduped_reply"), \
             mock.patch.object(
                 transport,
                 "_send_output_files",
                 side_effect=lambda message_id, workspace, decide_list=None: sent_decide_lists.append(list(decide_list or [])),
             ):
            transport.handle_message_async(
                message_id="mid-file-bundle",
                prompt="hello",
                image_keys=None,
                run_agent_fn=fake_run,
                supports_images=False,
                supports_stream_segment=False,
            )

        self.assertEqual(sent_decide_lists, [[{"send": "./工作区/report.md"}]])


    def test_handle_card_control_action_requests_runtime_cancel(self):
        observed = {}

        class _FakeRun:
            @staticmethod
            def cancel_active_execution(**kwargs):
                observed.update(kwargs)
                return {"cancelled_count": 1}

        result = transport._handle_card_control_action(
            {
                "cmd": "terminate",
                "value": {"request_id": "chat-run-123", "session_id": "thread_1", "source_message_id": "mid-source-1"},
                "open_chat_id": "chat_1",
                "open_id": "ou_1",
                "open_message_id": "om_card_1",
            },
            _FakeRun,
        )

        self.assertTrue(result["handled"])
        self.assertEqual(result["toast_type"], "success")
        self.assertEqual(observed["request_id"], "chat-run-123")
        self.assertEqual(observed["session_id"], "thread_1")
        self.assertEqual(observed["actor_id"], "ou_1")
        self.assertEqual(observed["message_id"], "mid-source-1")


if __name__ == "__main__":
    unittest.main()
