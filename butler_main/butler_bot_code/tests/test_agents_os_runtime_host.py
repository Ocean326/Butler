from __future__ import annotations

import sys
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from agents_os.governance import check_bash_chain_permissions, extract_bash_commands
from agents_os.runtime import FileInstanceStore, RunInput, RuntimeHost, RuntimeKernel, WorkerResult, FunctionWorker, merge_session_snapshots
from butler_main.butler_bot_code.tests._tmpdir import test_workdir


class AgentsOsRuntimeHostTests(unittest.TestCase):
    def test_instance_store_creates_minimal_runtime_layout(self) -> None:
        with test_workdir("agents_os_runtime_host_layout") as tmp_dir:
            store = FileInstanceStore(tmp_dir / "instances")
            instance = store.create(data={"agent_id": "maintenance.executor.main", "owner_domain": "maintenance"})
            instance_root = store.instance_root(instance.instance_id)

            self.assertTrue((instance_root / "instance.json").exists())
            self.assertTrue((instance_root / "profile.json").exists())
            self.assertTrue((instance_root / "status.json").exists())
            self.assertTrue((instance_root / "session" / "session.json").exists())
            self.assertTrue((instance_root / "session" / "checkpoints").exists())
            self.assertTrue((instance_root / "workflow" / "workflow.json").exists())
            self.assertTrue((instance_root / "workflow" / "checkpoints").exists())
            self.assertTrue((instance_root / "traces" / "events.jsonl").exists())
            self.assertTrue((instance_root / "artifacts" / "drafts").exists())
            self.assertTrue((instance_root / "inbox").exists())
            self.assertTrue((instance_root / "outbox").exists())

            loaded = store.load(instance.instance_id)
            self.assertEqual(loaded.agent_id, "maintenance.executor.main")
            self.assertEqual(loaded.owner_domain, "maintenance")

    def test_runtime_host_submit_and_resume_round_trip(self) -> None:
        with test_workdir("agents_os_runtime_host_roundtrip") as tmp_dir:
            kernel = RuntimeKernel()
            call_counter = {"value": 0}

            def handler(request):
                call_counter["value"] += 1
                return WorkerResult(
                    output={"call_count": call_counter["value"], "payload": request.payload},
                    context_updates={"call_count": call_counter["value"]},
                )

            kernel.register_worker(FunctionWorker("echo", handler))
            host = RuntimeHost(kernel, instance_store=FileInstanceStore(tmp_dir / "instances"))
            instance = host.create_instance({"agent_id": "demo.agent", "agent_kind": "executor"})

            result = host.submit_run(
                instance.instance_id,
                RunInput(
                    worker="echo",
                    payload={"text": "hello"},
                    metadata={"goal": "demo goal", "workflow_id": "demo_workflow", "current_step_id": "dispatch"},
                ),
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.output["call_count"], 1)

            stored = host.load_instance(instance.instance_id)
            self.assertEqual(stored.status, "idle")
            self.assertEqual(stored.current_goal, "demo goal")
            self.assertEqual(stored.conversation_cursor, "1")
            self.assertEqual(stored.active_workflow_id, "demo_workflow")
            self.assertEqual(stored.current_step_id, "dispatch")
            self.assertTrue(stored.last_checkpoint_id)
            self.assertTrue(stored.last_workflow_checkpoint_id)
            self.assertEqual(kernel.context_store.load(stored.session_id)["call_count"], 1)

            resumed = host.resume_instance(instance.instance_id)
            self.assertEqual(resumed.status, "completed")
            self.assertEqual(resumed.output["call_count"], 2)

            updated = host.load_instance(instance.instance_id)
            self.assertEqual(updated.conversation_cursor, "2")
            self.assertNotEqual(updated.last_checkpoint_id, "")

    def test_merge_session_snapshots_prefers_newer_cursor_then_timestamp(self) -> None:
        merged, persisted_won = merge_session_snapshots(
            {"conversation_cursor": "1", "updated_at": "2026-03-20T10:00:00"},
            {"conversation_cursor": "2", "updated_at": "2026-03-20T09:59:59"},
        )
        self.assertTrue(persisted_won)
        self.assertEqual(merged["conversation_cursor"], "2")

        merged, persisted_won = merge_session_snapshots(
            {"conversation_cursor": "2", "updated_at": "2026-03-20T10:00:00"},
            {"conversation_cursor": "2", "updated_at": "2026-03-20T10:00:01"},
        )
        self.assertTrue(persisted_won)
        self.assertEqual(merged["updated_at"], "2026-03-20T10:00:01")

    def test_bash_chain_permissions_cover_all_segments(self) -> None:
        commands = extract_bash_commands("git status && python -m pytest; echo done")
        self.assertEqual(commands, ["git", "python", "echo"])

        permissions = {
            "Bash(git *)": {"allowed": True, "source": "skill"},
            "bash": {"allowed": True, "source": "config", "when": {"command": "python *"}},
            "Bash(echo done)": {"allowed": True, "source": "config"},
        }
        allowed, reason, source = check_bash_chain_permissions("git status && python -m pytest", permissions)
        self.assertTrue(allowed)
        self.assertEqual(reason, "safe chain (2 commands)")
        self.assertEqual(source, "config")

        denied, _, _ = check_bash_chain_permissions("git status && rm -rf tmp", permissions)
        self.assertFalse(denied)


if __name__ == "__main__":
    unittest.main()
