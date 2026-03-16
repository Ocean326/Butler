import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from execution.agent_team_executor import AgentTeamExecutor  # noqa: E402


class AgentTeamExecutorTests(unittest.TestCase):
    def test_parallel_member_exception_is_captured_without_crashing_team(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            subagent_dir = workspace / "butler_main" / "butler_bot_agent" / "agents" / "sub-agents"
            team_dir = workspace / "butler_main" / "butler_bot_agent" / "agents" / "teams"
            hint_path = workspace / "butler_main" / "butler_bot_agent" / "agents" / "heartbeat-executor-workspace-hint.md"
            subagent_dir.mkdir(parents=True, exist_ok=True)
            team_dir.mkdir(parents=True, exist_ok=True)
            hint_path.parent.mkdir(parents=True, exist_ok=True)
            hint_path.write_text("【工作区约束】测试环境。", encoding="utf-8")
            (subagent_dir / "good-agent.md").write_text("# good-agent\n负责输出完成结果。", encoding="utf-8")
            (subagent_dir / "bad-agent.md").write_text("# bad-agent\n负责制造异常。", encoding="utf-8")
            (team_dir / "resilience.json").write_text(
                json.dumps(
                    {
                        "team_id": "resilience",
                        "name": "Resilience Team",
                        "max_parallel": 2,
                        "steps": [
                            {
                                "step_id": "step-1",
                                "mode": "parallel",
                                "members": [
                                    {"role": "good-agent", "task": "{task}"},
                                    {"role": "bad-agent", "task": "{task}"},
                                ],
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            def fake_model(prompt: str, _workspace: str, _timeout: int, _model: str):
                if "role=bad-agent" in prompt:
                    raise RuntimeError("boom")
                return "result\n证据完备", True

            executor = AgentTeamExecutor(fake_model)
            result = executor.execute_team("resilience", "整理测试报告", str(workspace), 60, "auto")

            self.assertTrue(result["ok"])
            self.assertEqual(len(result["member_results"]), 2)
            failed = next(item for item in result["member_results"] if not item["ok"])
            self.assertEqual(failed["agent_role"], "bad-agent")
            self.assertIn("boom", failed["error"])
            self.assertIn("FAILED: boom", result["output"])


if __name__ == "__main__":
    unittest.main()
