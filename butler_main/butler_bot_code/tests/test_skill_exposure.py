from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
for candidate in (REPO_ROOT, BUTLER_MAIN_DIR):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)

from butler_main.agents_os.skills import (
    build_skill_exposure_observation,
    normalize_skill_exposure_payload,
    render_skill_exposure_prompt,
)


class SkillExposureTests(unittest.TestCase):
    def test_normalize_skill_exposure_applies_defaults_and_provider_overrides(self) -> None:
        payload = normalize_skill_exposure_payload(
            {
                "family_hints": ["research", "research", "ocr"],
                "direct_skill_names": ["paper-search", "paper-search", "pdf-read"],
                "provider_overrides": {
                    "codex": {
                        "config_overrides": ["model_reasoning_effort='high'"],
                        "extra_args": ["--skip-something"],
                    }
                },
            },
            default_collection_id="codex_default",
            provider_skill_source="butler",
        )

        self.assertEqual(payload["collection_id"], "codex_default")
        self.assertEqual(payload["injection_mode"], "shortlist")
        self.assertEqual(payload["family_hints"], ["research", "ocr"])
        self.assertEqual(payload["direct_skill_names"], ["paper-search", "pdf-read"])
        self.assertTrue(payload["requires_skill_read"])
        self.assertEqual(
            payload["provider_overrides"]["codex"]["config_overrides"],
            ["model_reasoning_effort='high'"],
        )

    def test_render_skill_exposure_prompt_renders_shortlist_and_direct_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "butler_main" / "platform" / "skills" / "collections" / "registry.json"
            alpha = root / "butler_main" / "platform" / "skills" / "pool" / "research" / "paper-search"
            beta = root / "butler_main" / "platform" / "skills" / "pool" / "general" / "pdf-read"
            registry.parent.mkdir(parents=True, exist_ok=True)
            alpha.mkdir(parents=True, exist_ok=True)
            beta.mkdir(parents=True, exist_ok=True)
            (alpha / "SKILL.md").write_text(
                "---\nname: paper-search\ndescription: 搜索论文并输出摘要\nfamily_id: research\nfamily_label: Research\n---\n# paper-search\n先搜索论文。",
                encoding="utf-8",
            )
            (beta / "SKILL.md").write_text(
                "---\nname: pdf-read\ndescription: 读取 PDF 并抽取重点\nfamily_id: docs\nfamily_label: Docs\n---\n# pdf-read\n先读取 PDF。",
                encoding="utf-8",
            )
            registry.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "collections": {
                            "codex_default": {
                                "skills": [
                                    "./butler_main/platform/skills/pool/research/paper-search",
                                    "./butler_main/platform/skills/pool/general/pdf-read",
                                ]
                            }
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            prompt = render_skill_exposure_prompt(
                str(root),
                exposure={
                    "collection_id": "codex_default",
                    "family_hints": ["research"],
                    "direct_skill_names": ["pdf-read"],
                    "requires_skill_read": True,
                },
                source_prompt="帮我看论文并读 PDF",
                runtime_name="orchestrator",
            )

            self.assertIn("【可复用 Skills】", prompt)
            self.assertIn("collection=codex_default", prompt)
            self.assertIn("【本轮优先 family】research", prompt)
            self.assertIn("【已直绑 Skill】", prompt)
            self.assertIn("### pdf-read", prompt)
            self.assertIn("先读取 PDF", prompt)
            self.assertIn("【Skill Exposure 运行约束】", prompt)

    def test_build_skill_exposure_observation_surfaces_selected_families_and_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "butler_main" / "platform" / "skills" / "collections" / "registry.json"
            alpha = root / "butler_main" / "platform" / "skills" / "pool" / "research" / "paper-search"
            beta = root / "butler_main" / "platform" / "skills" / "pool" / "general" / "pdf-read"
            registry.parent.mkdir(parents=True, exist_ok=True)
            alpha.mkdir(parents=True, exist_ok=True)
            beta.mkdir(parents=True, exist_ok=True)
            (alpha / "SKILL.md").write_text(
                "---\nname: paper-search\nfamily_id: research\nfamily_label: Research\n---\n# paper-search",
                encoding="utf-8",
            )
            (beta / "SKILL.md").write_text(
                "---\nname: pdf-read\nfamily_id: docs\nfamily_label: Docs\n---\n# pdf-read",
                encoding="utf-8",
            )
            registry.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "collections": {
                            "codex_default": {
                                "skills": [
                                    "./butler_main/platform/skills/pool/research/paper-search",
                                    "./butler_main/platform/skills/pool/general/pdf-read",
                                ]
                            }
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            observation = build_skill_exposure_observation(
                str(root),
                exposure={
                    "collection_id": "codex_default",
                    "family_hints": ["research"],
                    "direct_skill_names": ["pdf-read"],
                },
            )

            self.assertTrue(observation["collection_known"])
            self.assertEqual(observation["selected_family_ids"], ["research"])
            self.assertEqual(observation["selected_skill_names"], ["pdf-read"])
            self.assertEqual(observation["materialization_mode"], "prompt_block")


if __name__ == "__main__":
    unittest.main()
