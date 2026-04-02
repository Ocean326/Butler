from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from agents_os.runtime import FileInstanceStore
from agents_os.state.run_state_store import FileRuntimeStateStore
from butler_main.chat.memory_runtime.recent_scope_paths import resolve_recent_scope_dir
from butler_main.orchestrator.runtime_paths import resolve_orchestrator_run_file
from butler_main.runtime_os.fs_retention import prune_path_children


def _set_old_mtime(path: Path, *, days_ago: int = 10) -> None:
    old_epoch = time.time() - (days_ago * 24 * 60 * 60)
    os.utime(path, (old_epoch, old_epoch))


class RuntimeRetentionTests(unittest.TestCase):
    def test_prune_path_children_uses_nested_file_mtime_for_directory_age(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_dir = root / "old-run"
            old_dir.mkdir(parents=True, exist_ok=True)
            old_file = old_dir / "events.jsonl"
            old_file.write_text("old", encoding="utf-8")
            _set_old_mtime(old_file)
            _set_old_mtime(old_dir)

            fresh_dir = root / "fresh-run"
            fresh_dir.mkdir(parents=True, exist_ok=True)
            (fresh_dir / "events.jsonl").write_text("fresh", encoding="utf-8")

            removed = prune_path_children(root, retention_days=3, include_dirs=True, include_files=False)

            self.assertEqual([item.name for item in removed], ["old-run"])
            self.assertFalse(old_dir.exists())
            self.assertTrue(fresh_dir.exists())

    def test_recent_scope_resolution_prunes_old_scopes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_scope_dir = root / "butler_main" / "chat" / "data" / "hot" / "recent_memory" / "scopes" / "oldscope"
            old_scope_dir.mkdir(parents=True, exist_ok=True)
            old_memory = old_scope_dir / "recent_memory.json"
            old_memory.write_text("[]", encoding="utf-8")
            _set_old_mtime(old_memory)
            _set_old_mtime(old_scope_dir)

            scope_dir = resolve_recent_scope_dir(str(root), session_scope_id="weixin:user-a")

            self.assertTrue(scope_dir.exists())
            self.assertFalse(old_scope_dir.exists())

    def test_instance_store_prunes_old_instance_dirs_on_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "instances"
            old_instance = root / "instance_old"
            old_instance.mkdir(parents=True, exist_ok=True)
            old_file = old_instance / "instance.json"
            old_file.write_text("{}", encoding="utf-8")
            _set_old_mtime(old_file)
            _set_old_mtime(old_instance)

            fresh_instance = root / "instance_fresh"
            fresh_instance.mkdir(parents=True, exist_ok=True)
            (fresh_instance / "instance.json").write_text("{}", encoding="utf-8")

            FileInstanceStore(root, retention_days=3)

            self.assertFalse(old_instance.exists())
            self.assertTrue(fresh_instance.exists())

    def test_research_scenario_store_prunes_old_instances_and_index_entries(self) -> None:
        from butler_main.research.manager.code.research_manager.services.scenario_instance_store import FileResearchScenarioInstanceStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "scenario_instances"
            old_instance = root / "scenario_instance_old"
            old_instance.mkdir(parents=True, exist_ok=True)
            old_file = old_instance / "instance.json"
            old_file.write_text("{}", encoding="utf-8")
            _set_old_mtime(old_file)
            _set_old_mtime(old_instance)
            root.mkdir(parents=True, exist_ok=True)
            (root / "index.json").write_text(
                json.dumps({"session::paper_manager.project_next_step_planning::s1": "scenario_instance_old"}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            FileResearchScenarioInstanceStore(root, retention_days=3)

            self.assertFalse(old_instance.exists())
            index_payload = json.loads((root / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(index_payload, {})

    def test_runtime_state_store_prunes_old_trace_and_archive_children(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runtime_state"
            archive_file = root / "archive" / "old.json"
            archive_file.parent.mkdir(parents=True, exist_ok=True)
            archive_file.write_text("{}", encoding="utf-8")
            _set_old_mtime(archive_file)

            trace_dir = root / "traces" / "fresh"
            trace_dir.mkdir(parents=True, exist_ok=True)
            (trace_dir / "events.jsonl").write_text("", encoding="utf-8")

            FileRuntimeStateStore(root, retention_days=3)

            self.assertFalse(archive_file.exists())
            self.assertTrue(trace_dir.exists())

    def test_adapter_run_file_resolution_prunes_old_run_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)
            run_dir = root / "butler_main" / "butler_bot_code" / "run" / "agents_os"
            run_dir.mkdir(parents=True, exist_ok=True)
            old_file = run_dir / "old_usage.json"
            old_file.write_text("{}", encoding="utf-8")
            _set_old_mtime(old_file)

            target = resolve_orchestrator_run_file(str(root), "fresh_usage.json")

            self.assertEqual(target, run_dir / "fresh_usage.json")
            self.assertFalse(old_file.exists())
            self.assertTrue(run_dir.exists())


if __name__ == "__main__":
    unittest.main()
