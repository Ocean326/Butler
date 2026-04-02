from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


class RuntimeOsRootPackageTests(unittest.TestCase):
    def test_repo_root_supports_runtime_os_imports_without_butler_main_path(self) -> None:
        script = textwrap.dedent(
            """
            from __future__ import annotations

            import inspect
            import json
            import sys
            from pathlib import Path

            root = Path(sys.argv[1]).resolve()
            butler_main_dir = root / "butler_main"
            sys.path[:] = [str(root)] + [
                item
                for item in sys.path
                if Path(item or ".").resolve() not in {root, butler_main_dir}
            ]

            import runtime_os
            from runtime_os import WorkflowFactory as TopWorkflowFactory
            from runtime_os import (
                agent_runtime,
                durability_substrate,
                multi_agent_protocols,
                multi_agent_runtime,
                process_runtime,
            )
            from runtime_os.agent_runtime import RuntimeRequestState, cli_runner
            from runtime_os.durability_substrate import RuntimeSessionCheckpoint
            from runtime_os.multi_agent_protocols import WorkflowTemplate
            from runtime_os.multi_agent_runtime import WorkflowFactory, WorkflowSession
            from butler_main.agents_os.execution import cli_runner as LegacyCliRunner
            from butler_main.agents_os.process_runtime import (
                WorkflowFactory as LegacyWorkflowFactory,
                WorkflowSession as LegacyWorkflowSession,
            )
            from butler_main.agents_os.runtime import RuntimeRequestState as LegacyRuntimeRequestState
            from butler_main.runtime_os import WorkflowFactory as NamespacedWorkflowFactory

            print(
                json.dumps(
                    {
                        "top_level_matches_submodule": TopWorkflowFactory is WorkflowFactory,
                        "workflow_factory_matches_namespaced": WorkflowFactory is NamespacedWorkflowFactory,
                        "workflow_factory_matches_process_runtime": WorkflowFactory is LegacyWorkflowFactory,
                        "workflow_session_matches_process_runtime": WorkflowSession is LegacyWorkflowSession,
                        "workflow_template_matches_process_runtime": WorkflowTemplate is process_runtime.WorkflowTemplate,
                        "runtime_session_checkpoint_matches_process_runtime": RuntimeSessionCheckpoint is process_runtime.RuntimeSessionCheckpoint,
                        "runtime_request_state_matches_legacy": Path(inspect.getfile(RuntimeRequestState)).resolve()
                        == Path(inspect.getfile(LegacyRuntimeRequestState)).resolve(),
                        "cli_runner_matches_legacy": Path(cli_runner.__file__).resolve()
                        == Path(LegacyCliRunner.__file__).resolve(),
                        "submodule_identity": runtime_os.agent_runtime is agent_runtime
                        and runtime_os.multi_agent_protocols is multi_agent_protocols
                        and runtime_os.multi_agent_runtime is multi_agent_runtime
                        and runtime_os.durability_substrate is durability_substrate
                        and runtime_os.process_runtime is process_runtime,
                    }
                )
            )
            """
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        completed = subprocess.run(
            [sys.executable, "-c", script, str(REPO_ROOT)],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

        if completed.returncode != 0:
            self.fail(completed.stderr.strip() or completed.stdout.strip() or "runtime_os root import probe failed")

        payload = json.loads(completed.stdout.strip())
        self.assertTrue(all(payload.values()), payload)


if __name__ == "__main__":
    unittest.main()
