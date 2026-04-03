from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from butler_main.butler_flow.desktop_bridge import main
from butler_main.butler_flow.state import (
    flow_artifacts_path,
    flow_dir,
    flow_state_path,
    new_flow_state,
    write_json_atomic,
)


def _config_path(root: Path) -> str:
    path = root / "butler_flow_desktop_bridge_config.json"
    path.write_text(json.dumps({"workspace_root": str(root)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _seed_flow(root: Path, *, flow_id: str) -> None:
    path = flow_dir(root, flow_id)
    state = new_flow_state(
        workflow_id=flow_id,
        workflow_kind="managed_flow",
        workspace_root=str(root),
        goal="ship desktop shell",
        guard_condition="verified",
        max_attempts=8,
        max_phase_attempts=4,
    )
    state["status"] = "running"
    state["current_phase"] = "build"
    state["execution_mode"] = "medium"
    state["session_strategy"] = "role_bound"
    state["active_role_id"] = "implementer"
    write_json_atomic(flow_state_path(path), state)
    write_json_atomic(
        flow_artifacts_path(path),
        {
            "items": [
                {
                    "artifact_ref": "artifact://desktop/workbench",
                    "phase": "build",
                    "attempt_no": 1,
                }
            ]
        },
    )


class ButlerFlowDesktopBridgeTests(unittest.TestCase):
    def test_home_command_emits_workspace_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            _seed_flow(root, flow_id="flow_desktop_bridge")

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = main(["--config", config, "home"])

            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["flows"]["items"][0]["flow_id"], "flow_desktop_bridge")

    def test_flow_command_emits_single_flow_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _config_path(root)
            _seed_flow(root, flow_id="flow_desktop_bridge")

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = main(["--config", config, "flow", "--flow-id", "flow_desktop_bridge"])

            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["flow_id"], "flow_desktop_bridge")
            self.assertEqual(payload["workflow_view"]["artifact_refs"], ["artifact://desktop/workbench"])


if __name__ == "__main__":
    unittest.main()
