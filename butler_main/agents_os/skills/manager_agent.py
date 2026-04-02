from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from butler_main.agents_os.contracts import PromptProfile
from butler_main.agents_os.factory import AgentCapabilities, AgentProfile, AgentSpec

from .pathing import resolve_butler_root


SKILL_MANAGER_AGENT_ROOT_REL = Path("butler_main") / "sources" / "skills" / "agent" / "skill_manager_agent"
SKILL_MANAGER_MANIFEST_REL = SKILL_MANAGER_AGENT_ROOT_REL / "agent_manifest.json"


@dataclass(frozen=True, slots=True)
class SkillManagerAgentBundle:
    agent_id: str
    profile_id: str
    display_name: str
    description: str
    runtime_key: str
    entrypoint: str
    default_collection_id: str
    capability_ids: tuple[str, ...] = ()
    supported_workflow_kinds: tuple[str, ...] = ()
    render_mode: str = "dialogue"
    block_order: tuple[str, ...] = ()
    asset_paths: dict[str, str] = field(default_factory=dict)
    assets: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def skill_manager_agent_root(workspace: str | Path | None = None) -> Path:
    return resolve_butler_root(workspace) / SKILL_MANAGER_AGENT_ROOT_REL


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def load_skill_manager_agent_bundle(
    workspace: str | Path | None = None,
    *,
    entrypoint: str = "talk",
) -> SkillManagerAgentBundle:
    root = skill_manager_agent_root(workspace)
    manifest_path = resolve_butler_root(workspace) / SKILL_MANAGER_MANIFEST_REL
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    supported_entrypoints = tuple(str(item).strip().lower() for item in manifest.get("supported_entrypoints") or ())
    normalized_entrypoint = str(entrypoint or manifest.get("default_entrypoint") or "talk").strip().lower() or "talk"
    if normalized_entrypoint not in supported_entrypoints:
        normalized_entrypoint = str(manifest.get("default_entrypoint") or "talk").strip().lower() or "talk"

    asset_paths_raw = dict(manifest.get("assets") or {})
    asset_paths = {key: str(value) for key, value in asset_paths_raw.items() if str(value or "").strip()}
    assets: dict[str, str] = {}
    for key, rel_path in asset_paths.items():
        assets[key] = _read_text(root / rel_path)

    return SkillManagerAgentBundle(
        agent_id=str(manifest.get("agent_id") or "skill_manager_agent").strip() or "skill_manager_agent",
        profile_id=str(manifest.get("profile_id") or "skill.manager").strip() or "skill.manager",
        display_name=str(manifest.get("display_name") or "Skill Manager Agent").strip() or "Skill Manager Agent",
        description=str(manifest.get("description") or "").strip(),
        runtime_key=str(manifest.get("runtime_key") or "default").strip() or "default",
        entrypoint=normalized_entrypoint,
        default_collection_id=str(manifest.get("default_collection_id") or "skill_ops").strip() or "skill_ops",
        capability_ids=tuple(str(item).strip() for item in manifest.get("capability_ids") or () if str(item).strip()),
        supported_workflow_kinds=tuple(
            str(item).strip() for item in manifest.get("supported_workflow_kinds") or () if str(item).strip()
        ),
        render_mode=str(manifest.get("render_mode") or "dialogue").strip() or "dialogue",
        block_order=tuple(str(item).strip() for item in manifest.get("block_order") or () if str(item).strip()),
        asset_paths=asset_paths,
        assets=assets,
        metadata={
            "root_rel": str(SKILL_MANAGER_AGENT_ROOT_REL).replace("\\", "/"),
            "manifest_rel": str(SKILL_MANAGER_MANIFEST_REL).replace("\\", "/"),
            "supported_entrypoints": list(supported_entrypoints),
        },
    )


def render_skill_manager_agent_cold_prompt(
    workspace: str | Path | None = None,
    *,
    entrypoint: str = "talk",
) -> str:
    bundle = load_skill_manager_agent_bundle(workspace, entrypoint=entrypoint)
    sections: list[str] = []
    role_text = str(bundle.assets.get("role") or "").strip()
    bootstrap_text = str(bundle.assets.get("bootstrap") or "").strip()
    entry_key = "talk_prompt" if bundle.entrypoint == "talk" else "orchestrator_prompt"
    entry_text = str(bundle.assets.get(entry_key) or "").strip()
    ops_text = str(bundle.assets.get("ops_skills") or "").strip()
    if role_text:
        sections.append(f"【Skill Manager Role】\n{role_text}")
    if bootstrap_text:
        sections.append(f"【Skill Manager Bootstrap】\n{bootstrap_text}")
    if entry_text:
        sections.append(f"【Skill Manager Entrypoint】\n{entry_text}")
    if ops_text:
        sections.append(f"【Managed Ops Skills】\n{ops_text}")
    return "\n\n".join(section for section in sections if section.strip()).strip()


def build_skill_manager_agent_spec(
    workspace: str | Path | None = None,
    *,
    entrypoint: str = "talk",
    metadata: Mapping[str, Any] | None = None,
) -> AgentSpec:
    bundle = load_skill_manager_agent_bundle(workspace, entrypoint=entrypoint)
    prompt_profile = PromptProfile(
        profile_id=bundle.profile_id,
        display_name=bundle.display_name,
        block_order=list(bundle.block_order),
        render_mode=bundle.render_mode,
        metadata={
            "entrypoint": bundle.entrypoint,
            "default_collection_id": bundle.default_collection_id,
            "asset_root": bundle.metadata.get("root_rel"),
        },
    )
    profile = AgentProfile(
        profile_id=bundle.profile_id,
        prompt_profile=prompt_profile,
        description=bundle.description,
        metadata={
            "entrypoint": bundle.entrypoint,
            "default_collection_id": bundle.default_collection_id,
            "cold_prompt": render_skill_manager_agent_cold_prompt(workspace, entrypoint=entrypoint),
        },
    )
    capabilities = AgentCapabilities(
        memory_mode="default",
        retrieval_enabled=True,
        tool_access=True,
        delivery_target="generic",
        capability_ids=bundle.capability_ids,
        supported_workflow_kinds=bundle.supported_workflow_kinds,
        extras={"default_collection_id": bundle.default_collection_id, "entrypoint": bundle.entrypoint},
    )
    return AgentSpec(
        agent_id=bundle.agent_id,
        profile=profile,
        capabilities=capabilities,
        runtime_key=bundle.runtime_key,
        entrypoints=(bundle.entrypoint,),
        labels=("skills", "manager", bundle.entrypoint),
        metadata={
            "default_collection_id": bundle.default_collection_id,
            "asset_root": bundle.metadata.get("root_rel"),
            **dict(metadata or {}),
        },
    )


__all__ = [
    "SKILL_MANAGER_AGENT_ROOT_REL",
    "SKILL_MANAGER_MANIFEST_REL",
    "SkillManagerAgentBundle",
    "build_skill_manager_agent_spec",
    "load_skill_manager_agent_bundle",
    "render_skill_manager_agent_cold_prompt",
    "skill_manager_agent_root",
]
