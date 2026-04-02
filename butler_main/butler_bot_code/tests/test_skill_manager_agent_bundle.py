import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.agents_os.skills import (
    build_skill_manager_agent_spec,
    load_skill_manager_agent_bundle,
    render_skill_manager_agent_cold_prompt,
)


class SkillManagerAgentBundleTests(unittest.TestCase):
    def test_load_bundle_for_talk_entrypoint(self) -> None:
        bundle = load_skill_manager_agent_bundle(".", entrypoint="talk")
        self.assertEqual(bundle.agent_id, "skill_manager_agent")
        self.assertEqual(bundle.entrypoint, "talk")
        self.assertEqual(bundle.default_collection_id, "skill_ops")
        self.assertIn("skill.import", bundle.capability_ids)
        self.assertIn("role", bundle.assets)
        self.assertIn("talk_prompt", bundle.assets)
        self.assertIn("skill 池", bundle.assets["bootstrap"])

    def test_build_spec_for_orchestrator_contains_cold_prompt(self) -> None:
        spec = build_skill_manager_agent_spec(".", entrypoint="orchestrator")
        self.assertEqual(spec.agent_id, "skill_manager_agent")
        self.assertEqual(spec.runtime_key, "default")
        self.assertEqual(tuple(spec.entrypoints), ("orchestrator",))
        self.assertIn("skill.collection.governance", spec.capabilities.capability_ids)
        self.assertEqual(spec.metadata["default_collection_id"], "skill_ops")
        cold_prompt = str(spec.profile.metadata.get("cold_prompt") or "")
        self.assertIn("当前入口是 orchestrator", cold_prompt)
        self.assertIn("skill-github-import", cold_prompt)

    def test_render_cold_prompt_contains_role_bootstrap_and_ops_skills(self) -> None:
        prompt = render_skill_manager_agent_cold_prompt(".", entrypoint="talk")
        self.assertIn("【Skill Manager Role】", prompt)
        self.assertIn("【Skill Manager Bootstrap】", prompt)
        self.assertIn("【Managed Ops Skills】", prompt)


if __name__ == "__main__":
    unittest.main()
