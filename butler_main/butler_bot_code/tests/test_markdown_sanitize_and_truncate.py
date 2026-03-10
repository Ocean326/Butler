import sys
import unittest
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
sys.path.insert(0, str(MODULE_DIR))

import markdown_safety  # noqa: E402


class MarkdownSafetyTests(unittest.TestCase):
    def test_sanitize_fixes_heading_and_list_spacing(self):
        raw = "###1.标题\r\n-项目A\r\n1.步骤\r\n正文"
        sanitized = markdown_safety.sanitize_markdown_structure(raw)
        self.assertIn("### 1.标题", sanitized)
        self.assertIn("- 项目A", sanitized)
        self.assertIn("1. 步骤", sanitized)

    def test_safe_truncate_closes_fence_block(self):
        raw = "## 示例\n```python\nprint('x')\nprint('y')\n"
        truncated = markdown_safety.safe_truncate_markdown(raw, 28)
        self.assertIn("...[内容已截断]", truncated)
        self.assertEqual(truncated.count("```") % 2, 0)

    def test_safe_truncate_prefers_boundary(self):
        raw = "## 第一部分\n内容一\n\n## 第二部分\n内容二\n\n## 第三部分\n内容三"
        truncated = markdown_safety.safe_truncate_markdown(raw, 30)
        self.assertTrue(truncated.startswith("## 第一部分"))
        self.assertIn("...[内容已截断]", truncated)

    def test_sanitize_inserts_newline_before_inline_heading(self):
        raw = "开场说明。 ### 先对齐一句话版本\n正文"
        sanitized = markdown_safety.sanitize_markdown_structure(raw)
        self.assertIn("开场说明。\n### 先对齐一句话版本", sanitized)

    def test_sanitize_drops_tail_repeated_opening_line(self):
        raw = "嗯，这句我记住了，而且挺打在点上的。\n\n主体内容\n\n嗯，这句我记住了，而且挺打在点上的。"
        sanitized = markdown_safety.sanitize_markdown_structure(raw)
        self.assertEqual(sanitized.count("嗯，这句我记住了，而且挺打在点上的。"), 1)


if __name__ == "__main__":
    unittest.main()
