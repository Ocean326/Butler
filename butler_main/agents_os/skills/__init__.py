from __future__ import annotations

import importlib

_EXPORT_MAP = {
    "load_skill_collection_registry": (".collection_registry", "load_skill_collection_registry"),
    "resolve_skill_collection_id": (".injection_policy", "resolve_skill_collection_id"),
    "SKILL_MANAGER_AGENT_ROOT_REL": (".manager_agent", "SKILL_MANAGER_AGENT_ROOT_REL"),
    "SkillManagerAgentBundle": (".manager_agent", "SkillManagerAgentBundle"),
    "build_skill_manager_agent_spec": (".manager_agent", "build_skill_manager_agent_spec"),
    "load_skill_manager_agent_bundle": (".manager_agent", "load_skill_manager_agent_bundle"),
    "render_skill_manager_agent_cold_prompt": (".manager_agent", "render_skill_manager_agent_cold_prompt"),
    "skill_manager_agent_root": (".manager_agent", "skill_manager_agent_root"),
    "CODEX_SKILL_COLLECTION": (".models", "CODEX_SKILL_COLLECTION"),
    "CONTENT_SHARE_SKILL_COLLECTION": (".models", "CONTENT_SHARE_SKILL_COLLECTION"),
    "DEFAULT_SKILL_COLLECTION": (".models", "DEFAULT_SKILL_COLLECTION"),
    "AUTOMATION_SAFE_SKILL_COLLECTION": (".models", "AUTOMATION_SAFE_SKILL_COLLECTION"),
    "SkillMetadata": (".models", "SkillMetadata"),
    "SkillExposureContract": (".exposure", "SkillExposureContract"),
    "build_skill_exposure_observation": (".exposure", "build_skill_exposure_observation"),
    "normalize_skill_exposure_payload": (".exposure", "normalize_skill_exposure_payload"),
    "render_skill_exposure_prompt": (".exposure", "render_skill_exposure_prompt"),
    "skill_exposure_provider_override": (".exposure", "skill_exposure_provider_override"),
    "summarize_skill_exposure": (".exposure", "summarize_skill_exposure"),
    "collection_hint_text": (".prompt_policy", "collection_hint_text"),
    "load_runtime_skill_extras": (".prompt_policy", "load_runtime_skill_extras"),
    "load_skill_prompt_policy": (".prompt_policy", "load_skill_prompt_policy"),
    "render_skill_prompt_block": (".prompt_policy", "render_skill_prompt_block"),
    "build_skill_registry_diagnostics": (".runtime_catalog", "build_skill_registry_diagnostics"),
    "expand_skill_family": (".runtime_catalog", "expand_skill_family"),
    "get_skill_collection_detail": (".runtime_catalog", "get_skill_collection_detail"),
    "list_skill_collections": (".runtime_catalog", "list_skill_collections"),
    "load_skill_catalog": (".runtime_catalog", "load_skill_catalog"),
    "read_skill_document": (".runtime_catalog", "read_skill_document"),
    "render_skill_catalog_for_prompt": (".runtime_catalog", "render_skill_catalog_for_prompt"),
    "search_skill_catalog": (".runtime_catalog", "search_skill_catalog"),
    "skill_tool": (".skill_tool", "skill_tool"),
    "UPSTREAM_SKILL_CONVERSION_REGISTRY_REL": (".upstream_registry", "UPSTREAM_SKILL_CONVERSION_REGISTRY_REL"),
    "load_upstream_skill_conversion_registry": (".upstream_registry", "load_upstream_skill_conversion_registry"),
    "resolve_upstream_skill_conversion_entry": (".upstream_registry", "resolve_upstream_skill_conversion_entry"),
    "upstream_skill_conversion_registry_file": (".upstream_registry", "upstream_skill_conversion_registry_file"),
}

__all__ = list(_EXPORT_MAP)


def __getattr__(name: str):
    module_info = _EXPORT_MAP.get(name)
    if module_info is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = module_info
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
