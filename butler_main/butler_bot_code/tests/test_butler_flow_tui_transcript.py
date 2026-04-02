from __future__ import annotations

import unittest

from rich.padding import Padding
from rich.text import Text

from butler_main.butler_flow.tui.transcript import (
    BODY_STYLE_BY_TONE,
    GROUP_TITLE_STYLE,
    TranscriptFormatter,
    TranscriptGroupKey,
)


class _FakeRichLog:
    def __init__(self) -> None:
        self.items: list[object] = []

    def write(self, content, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        self.items.append(content)
        return self


class TranscriptFormatterTests(unittest.TestCase):
    def test_group_title_text_is_dim_bracket_label(self) -> None:
        formatter = TranscriptFormatter()
        title = formatter.group_title_text(TranscriptGroupKey(lane="workflow", family="raw_execution"))

        self.assertIsInstance(title, Text)
        self.assertEqual(title.plain, "[workflow/raw_execution]")
        self.assertEqual(str(title.style), "dim #565f89")

    def test_group_title_and_body_use_family_colors(self) -> None:
        formatter = TranscriptFormatter()

        decision_title = formatter.group_title_text(TranscriptGroupKey(lane="supervisor", family="decision"))
        approval_title = formatter.group_title_text(TranscriptGroupKey(lane="supervisor", family="approval"))
        artifact_title = formatter.group_title_text(TranscriptGroupKey(lane="workflow", family="artifact"))
        body = formatter.body_text("approved", tone="approval")
        raw_title = formatter.group_title_text(TranscriptGroupKey(lane="workflow", family="raw_execution"))
        raw_meta = formatter.body_text("tool finished", tone="raw_meta")
        raw_output = formatter.body_text("stdout line", tone="raw_output")
        raw_error = formatter.body_text("stderr line", tone="raw_error")

        self.assertEqual(str(decision_title.style), "dim #9ece6a")
        self.assertEqual(str(approval_title.style), "dim #bb9af7")
        self.assertEqual(str(artifact_title.style), "dim #7aa2f7")
        self.assertEqual(str(raw_title.style), "dim #565f89")
        self.assertEqual(str(body.style), BODY_STYLE_BY_TONE["approval"])
        self.assertEqual(str(raw_meta.style), BODY_STYLE_BY_TONE["raw_meta"])
        self.assertEqual(str(raw_output.style), BODY_STYLE_BY_TONE["raw_output"])
        self.assertEqual(str(raw_error.style), BODY_STYLE_BY_TONE["raw_error"])

    def test_repeated_group_title_is_omitted_until_group_changes(self) -> None:
        formatter = TranscriptFormatter()
        transcript = _FakeRichLog()

        formatter.write_group(transcript, lane="workflow", family="raw_execution", body="alpha")
        formatter.write_group(transcript, lane="workflow", family="raw_execution", body="beta")
        formatter.write_group(transcript, lane="workflow", family="artifact", body="artifact.json")
        formatter.write_group(transcript, lane="workflow", family="raw_execution", body="gamma")

        self.assertEqual(len(transcript.items), 9)
        self.assertEqual(transcript.items[0].plain, "[workflow/raw_execution]")
        self.assertIsInstance(transcript.items[1], Padding)
        self.assertEqual(transcript.items[1].renderable.plain, "alpha")
        self.assertIsInstance(transcript.items[2], Padding)
        self.assertEqual(transcript.items[2].renderable.plain, "beta")
        self.assertEqual(transcript.items[3].plain, "")
        self.assertEqual(transcript.items[4].plain, "[workflow/artifact]")
        self.assertEqual(transcript.items[5].renderable.plain, "artifact.json")
        self.assertEqual(transcript.items[6].plain, "")
        self.assertEqual(transcript.items[7].plain, "[workflow/raw_execution]")
        self.assertEqual(transcript.items[8].renderable.plain, "gamma")

    def test_section_resets_active_group_and_indents_body(self) -> None:
        formatter = TranscriptFormatter()
        transcript = _FakeRichLog()

        formatter.write_group(transcript, lane="supervisor", family="decision", body="first")
        formatter.write_section(transcript, title="Supervisor Stream", body="flow_id=flow_alpha\nstatus=running")
        formatter.write_group(transcript, lane="supervisor", family="decision", body="second")

        self.assertEqual(transcript.items[0].plain, "[supervisor/decision]")
        self.assertEqual(transcript.items[1].renderable.plain, "first")
        self.assertEqual(transcript.items[2].plain, "")
        self.assertEqual(transcript.items[3].plain, "Supervisor Stream")
        self.assertEqual(transcript.items[4].renderable.plain, "flow_id=flow_alpha\nstatus=running")
        self.assertEqual(transcript.items[5].plain, "")
        self.assertEqual(transcript.items[6].plain, "[supervisor/decision]")
        self.assertEqual(transcript.items[7].renderable.plain, "second")
