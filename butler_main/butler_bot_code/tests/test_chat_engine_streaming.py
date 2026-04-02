import unittest

from butler_main.chat import engine as chat_engine


class ChatEngineStreamingTests(unittest.TestCase):
    def test_final_snapshot_does_not_repeat_visible_text(self):
        emitted = ""

        first = "前置说明\n## 最终结论\n内容"
        visible_delta, emitted = chat_engine._plan_stream_increment(emitted, first)
        self.assertEqual(visible_delta, first)
        self.assertEqual(emitted, first)

        visible_delta, emitted = chat_engine._plan_stream_increment(emitted, first)
        self.assertEqual(visible_delta, "")
        self.assertEqual(emitted, first)

    def test_snapshot_only_emits_new_suffix(self):
        emitted = ""

        first = "## 第一部分\n内容"
        _, emitted = chat_engine._plan_stream_increment(emitted, first)

        extended_snapshot = "## 第一部分\n内容\n## 第二部分\n新增内容"
        visible_delta, emitted = chat_engine._plan_stream_increment(emitted, extended_snapshot)

        self.assertEqual(visible_delta, "\n## 第二部分\n新增内容")
        self.assertEqual(emitted, extended_snapshot)

    def test_extract_ready_markdown_sections_uses_second_heading_as_boundary(self):
        text = "开场说明\n## 第一部分\n第一段\n## 第二部分\n第二段"
        ready_sections, rest = chat_engine._extract_ready_markdown_sections(text)

        self.assertEqual(ready_sections, ["## 第一部分\n第一段"])
        self.assertEqual(rest, "## 第二部分\n第二段")

    def test_extract_ready_markdown_sections_does_not_stream_preamble(self):
        text = "整体说明\n补充说明\n## 第一部分\n第一段\n## 第二部分\n第二段"
        ready_sections, rest = chat_engine._extract_ready_markdown_sections(text)

        self.assertEqual(ready_sections, ["## 第一部分\n第一段"])
        self.assertEqual(rest, "## 第二部分\n第二段")

    def test_collect_unsent_markdown_sections_ignores_repeated_snapshot(self):
        text = "## 第一部分\n第一段\n## 第二部分\n第二段"
        new_sections, sent_count, tail = chat_engine._collect_unsent_markdown_sections(text, 0)

        self.assertEqual(new_sections, ["## 第一部分\n第一段"])
        self.assertEqual(sent_count, 1)
        self.assertEqual(tail, "## 第二部分\n第二段")

        new_sections, sent_count, tail = chat_engine._collect_unsent_markdown_sections(text, sent_count)
        self.assertEqual(new_sections, [])
        self.assertEqual(sent_count, 1)
        self.assertEqual(tail, "## 第二部分\n第二段")

    def test_stream_assembler_marks_unstable_on_large_rollback(self):
        assembler = chat_engine._StreamAssembler()
        first = "第一段说明很长很长很长很长\n## 小节一\n内容 A"
        self.assertEqual(assembler.ingest(first), first)
        self.assertFalse(assembler.unstable_stream)

        rollback_snapshot = "复\n我先帮你设计一套方案\n## 小节一\n内容 A"
        self.assertEqual(assembler.ingest(rollback_snapshot), "")
        self.assertTrue(assembler.unstable_stream)
        self.assertEqual(assembler.final_text(), rollback_snapshot)

    def test_stream_assembler_allows_tail_rewrite_without_unstable(self):
        assembler = chat_engine._StreamAssembler()
        first = "## 结论\n先做 A"
        assembler.ingest(first)
        second = "## 结论\n先做 A，再做 B"
        self.assertEqual(assembler.ingest(second), "，再做 B")
        self.assertFalse(assembler.unstable_stream)
        self.assertEqual(assembler.final_text(), second)


if __name__ == "__main__":
    unittest.main()
