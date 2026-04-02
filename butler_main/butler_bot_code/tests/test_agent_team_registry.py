from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
AGENT_TEAM_ROOT = REPO_ROOT / "butler_main" / "sources" / "agent_teams"
REGISTRY_PATH = AGENT_TEAM_ROOT / "collections" / "registry.json"
REQUIRED_MANIFEST_KEYS = (
    "id:",
    "suite:",
    "display_name:",
    "purpose:",
    "use_when:",
    "avoid_when:",
    "inputs:",
    "outputs:",
    "evidence_rules:",
    "permissions_profile:",
    "model_profile:",
    "tool_profile:",
    "vendor_files:",
)
ALLOWED_CODEX_MODELS = {
    "gpt-5.1-codex-mini",
    "gpt-5.2-codex",
    "gpt-5.4",
}
ALLOWED_CLAUDE_MODELS = {"haiku", "sonnet", "opus"}
ALLOWED_SANDBOX = {"read-only", "workspace-write", "danger-full-access"}


def _load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _resolve_repo_path(raw_path: str) -> Path:
    clean = str(raw_path or "").strip()
    if clean.startswith("./"):
        clean = clean[2:]
    return REPO_ROOT / clean


def _iter_role_dirs() -> list[Path]:
    registry = _load_registry()
    role_dirs: list[Path] = []
    for suite in registry["suites"].values():
        for raw_path in suite["roles"]:
            role_dirs.append(_resolve_repo_path(raw_path))
    return role_dirs


def _parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    _, rest = text.split("---\n", 1)
    frontmatter, _, _body = rest.partition("\n---\n")
    data: dict[str, str] = {}
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("- "):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        data[key.strip()] = value.strip()
    return data


class AgentTeamRegistryTests(unittest.TestCase):
    def test_registry_paths_exist(self) -> None:
        registry = _load_registry()
        for raw_path in registry["required_role_files"]:
            self.assertIn(raw_path, {"butler-agent.yaml", "codex.toml", "claude.md"})

        for suite in registry["suites"].values():
            for raw_path in suite["roles"]:
                role_dir = _resolve_repo_path(raw_path)
                self.assertTrue(role_dir.is_dir(), msg=str(role_dir))
                for required in registry["required_role_files"]:
                    self.assertTrue((role_dir / required).is_file(), msg=f"missing {required} in {role_dir}")
            for raw_path in suite["recipes"]:
                recipe_path = _resolve_repo_path(raw_path)
                self.assertTrue(recipe_path.is_file(), msg=str(recipe_path))

    def test_butler_manifests_include_required_contract_fields(self) -> None:
        for role_dir in _iter_role_dirs():
            manifest_text = (role_dir / "butler-agent.yaml").read_text(encoding="utf-8")
            for key in REQUIRED_MANIFEST_KEYS:
                self.assertIn(key, manifest_text, msg=f"missing {key} in {role_dir}")
            self.assertIn("codex: ./codex.toml", manifest_text)
            self.assertIn("claude: ./claude.md", manifest_text)

    def test_codex_templates_use_supported_models_and_sandbox_profiles(self) -> None:
        for role_dir in _iter_role_dirs():
            data = tomllib.loads((role_dir / "codex.toml").read_text(encoding="utf-8"))
            self.assertIn(data.get("model"), ALLOWED_CODEX_MODELS)
            self.assertIn(data.get("sandbox_mode"), ALLOWED_SANDBOX)
            self.assertEqual(data.get("sandbox_mode"), "danger-full-access")
            self.assertTrue(str(data.get("name") or "").strip())
            self.assertTrue(str(data.get("description") or "").strip())
            self.assertTrue(str(data.get("developer_instructions") or "").strip())
            self.assertNotIn("prompt", data)

    def test_claude_templates_define_frontmatter_and_known_model_aliases(self) -> None:
        for role_dir in _iter_role_dirs():
            frontmatter = _parse_frontmatter(role_dir / "claude.md")
            self.assertTrue(frontmatter.get("name"))
            self.assertTrue(frontmatter.get("description"))
            self.assertIn(frontmatter.get("model"), ALLOWED_CLAUDE_MODELS)

    def test_recipe_docs_keep_a_final_verdict_gate(self) -> None:
        registry = _load_registry()
        for suite in registry["suites"].values():
            for raw_path in suite["recipes"]:
                recipe_text = _resolve_repo_path(raw_path).read_text(encoding="utf-8")
                self.assertIn("## Final verdict", recipe_text)
                self.assertIn("## Required evidence", recipe_text)


if __name__ == "__main__":
    unittest.main()
