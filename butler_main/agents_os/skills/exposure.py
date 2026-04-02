from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .collection_registry import load_skill_collection_registry
from .prompt_policy import load_runtime_skill_extras, render_skill_prompt_block
from .runtime_catalog import (
    build_skill_families,
    load_skill_catalog,
    read_skill_document,
    render_skill_catalog_for_prompt,
)


_DEFAULT_INJECTION_MODE = "shortlist"
_SUPPORTED_INJECTION_MODES = {"passive_index", "shortlist", "direct_bind", "tool_api"}
_MAX_DIRECT_BINDINGS = 3
_MAX_DIRECT_BIND_CHARS = 4000


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_text_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        return ()
    deduped: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _normalize_text(item)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        deduped.append(text)
    return tuple(deduped)


def _normalize_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _normalize_text(value).lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _normalize_provider_overrides(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for raw_provider, raw_override in payload.items():
        provider_name = _normalize_text(raw_provider).lower()
        if not provider_name or not isinstance(raw_override, Mapping):
            continue
        item: dict[str, Any] = {}
        for key in ("profile", "model", "speed"):
            value = _normalize_text(raw_override.get(key))
            if value:
                item[key] = value
        for key in ("config_overrides", "extra_args"):
            values = _normalize_text_list(raw_override.get(key))
            if values:
                item[key] = list(values)
        if item:
            normalized[provider_name] = item
    return normalized


@dataclass(frozen=True)
class SkillExposureContract:
    collection_id: str = ""
    family_hints: tuple[str, ...] = ()
    direct_skill_names: tuple[str, ...] = ()
    direct_skill_paths: tuple[str, ...] = ()
    injection_mode: str = _DEFAULT_INJECTION_MODE
    requires_skill_read: bool = False
    provider_skill_source: str = "butler"
    provider_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any] | None,
        *,
        default_collection_id: str = "",
        default_injection_mode: str = _DEFAULT_INJECTION_MODE,
        provider_skill_source: str = "butler",
    ) -> "SkillExposureContract | None":
        normalized = normalize_skill_exposure_payload(
            payload,
            default_collection_id=default_collection_id,
            default_injection_mode=default_injection_mode,
            provider_skill_source=provider_skill_source,
        )
        if not normalized:
            return None
        return cls(
            collection_id=str(normalized.get("collection_id") or "").strip(),
            family_hints=_normalize_text_list(normalized.get("family_hints")),
            direct_skill_names=_normalize_text_list(normalized.get("direct_skill_names")),
            direct_skill_paths=_normalize_text_list(normalized.get("direct_skill_paths")),
            injection_mode=str(normalized.get("injection_mode") or _DEFAULT_INJECTION_MODE).strip(),
            requires_skill_read=bool(normalized.get("requires_skill_read")),
            provider_skill_source=str(normalized.get("provider_skill_source") or "butler").strip() or "butler",
            provider_overrides=_normalize_provider_overrides(normalized.get("provider_overrides")),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "collection_id": self.collection_id,
            "family_hints": list(self.family_hints),
            "direct_skill_names": list(self.direct_skill_names),
            "direct_skill_paths": list(self.direct_skill_paths),
            "injection_mode": self.injection_mode,
            "requires_skill_read": self.requires_skill_read,
            "provider_skill_source": self.provider_skill_source,
        }
        if self.provider_overrides:
            payload["provider_overrides"] = {
                provider: dict(values or {})
                for provider, values in self.provider_overrides.items()
                if provider
            }
        return payload

    def is_empty(self) -> bool:
        return not any(
            (
                self.collection_id,
                self.family_hints,
                self.direct_skill_names,
                self.direct_skill_paths,
                self.provider_overrides,
            )
        )


def normalize_skill_exposure_payload(
    payload: Mapping[str, Any] | None,
    *,
    default_collection_id: str = "",
    default_injection_mode: str = _DEFAULT_INJECTION_MODE,
    provider_skill_source: str = "butler",
) -> dict[str, Any] | None:
    raw = dict(payload or {})
    collection_id = _normalize_text(raw.get("collection_id") or default_collection_id)
    injection_mode = _normalize_text(raw.get("injection_mode") or default_injection_mode).lower() or _DEFAULT_INJECTION_MODE
    if injection_mode not in _SUPPORTED_INJECTION_MODES:
        injection_mode = _DEFAULT_INJECTION_MODE
    family_hints = _normalize_text_list(raw.get("family_hints") or raw.get("hints"))
    direct_skill_names = _normalize_text_list(raw.get("direct_skill_names") or raw.get("skill_names") or raw.get("skills"))
    direct_skill_paths = _normalize_text_list(raw.get("direct_skill_paths") or raw.get("skill_paths"))
    provider_overrides = _normalize_provider_overrides(raw.get("provider_overrides"))
    requires_skill_read = _normalize_bool(
        raw.get("requires_skill_read"),
        default=bool(direct_skill_names or direct_skill_paths or injection_mode == "direct_bind"),
    )
    source = _normalize_text(raw.get("provider_skill_source") or provider_skill_source or "butler") or "butler"
    if not any((collection_id, family_hints, direct_skill_names, direct_skill_paths, provider_overrides)):
        return None
    return {
        "collection_id": collection_id,
        "family_hints": list(family_hints),
        "direct_skill_names": list(direct_skill_names),
        "direct_skill_paths": list(direct_skill_paths),
        "injection_mode": injection_mode,
        "requires_skill_read": requires_skill_read,
        "provider_skill_source": source,
        "provider_overrides": provider_overrides,
    }


def skill_exposure_provider_override(
    exposure: Mapping[str, Any] | None,
    *,
    provider_name: str,
) -> dict[str, Any]:
    normalized = normalize_skill_exposure_payload(exposure)
    if not normalized:
        return {}
    overrides = normalized.get("provider_overrides")
    if not isinstance(overrides, Mapping):
        return {}
    return dict(overrides.get(_normalize_text(provider_name).lower()) or {})


def summarize_skill_exposure(
    exposure: Mapping[str, Any] | None,
    *,
    default_collection_id: str = "",
    default_injection_mode: str = _DEFAULT_INJECTION_MODE,
    provider_skill_source: str = "butler",
) -> dict[str, Any]:
    contract = SkillExposureContract.from_payload(
        exposure,
        default_collection_id=default_collection_id,
        default_injection_mode=default_injection_mode,
        provider_skill_source=provider_skill_source,
    )
    if contract is None:
        return {}
    return {
        "collection_id": contract.collection_id,
        "injection_mode": contract.injection_mode,
        "requires_skill_read": contract.requires_skill_read,
        "provider_skill_source": contract.provider_skill_source,
        "family_hints": list(contract.family_hints),
        "direct_skill_count": len(contract.direct_skill_names) + len(contract.direct_skill_paths),
        "provider_override_keys": sorted(contract.provider_overrides.keys()),
    }


def build_skill_exposure_observation(
    workspace: str,
    *,
    exposure: Mapping[str, Any] | None,
    materialization_mode: str = "prompt_block",
    fallback_reason: str = "",
) -> dict[str, Any]:
    contract = SkillExposureContract.from_payload(exposure)
    if contract is None:
        return {}
    registry = load_skill_collection_registry(workspace)
    collections = registry.get("collections") if isinstance(registry.get("collections"), dict) else {}
    catalog = load_skill_catalog(workspace, collection_id=contract.collection_id or None)
    families = build_skill_families(catalog)
    alias_map: dict[str, tuple[str, str]] = {}
    for family in families:
        alias_map[family.family_id.lower()] = (family.family_id, family.label)
        label = _normalize_text(family.label).lower()
        if label:
            alias_map[label] = (family.family_id, family.label)
    selected_family_ids: list[str] = []
    selected_family_labels: list[str] = []
    for hint in contract.family_hints:
        resolved = alias_map.get(_normalize_text(hint).lower())
        if not resolved:
            continue
        family_id, label = resolved
        if family_id in selected_family_ids:
            continue
        selected_family_ids.append(family_id)
        selected_family_labels.append(label)
    resolved_skill_names: list[str] = []
    for skill_name in contract.direct_skill_names:
        item, _ = read_skill_document(workspace, skill_name=skill_name, collection_id=contract.collection_id or None)
        if item is None or item.name in resolved_skill_names:
            continue
        resolved_skill_names.append(item.name)
    for skill_path in contract.direct_skill_paths:
        item, _ = read_skill_document(workspace, skill_path=skill_path, collection_id=contract.collection_id or None)
        if item is None or item.name in resolved_skill_names:
            continue
        resolved_skill_names.append(item.name)
    return {
        "collection_id": contract.collection_id,
        "collection_known": bool(contract.collection_id and collections.get(contract.collection_id)),
        "collection_family_count": len(families),
        "collection_skill_count": len(catalog),
        "selected_family_ids": selected_family_ids,
        "selected_family_labels": selected_family_labels,
        "selected_skill_names": resolved_skill_names,
        "direct_skill_names": list(contract.direct_skill_names),
        "direct_skill_paths": list(contract.direct_skill_paths),
        "injection_mode": contract.injection_mode,
        "requires_skill_read": contract.requires_skill_read,
        "provider_skill_source": contract.provider_skill_source,
        "provider_override_keys": sorted(contract.provider_overrides.keys()),
        "materialization_mode": _normalize_text(materialization_mode) or "prompt_block",
        "fallback_reason": _normalize_text(fallback_reason),
    }


def render_skill_exposure_prompt(
    workspace: str,
    *,
    exposure: Mapping[str, Any] | None,
    source_prompt: str,
    runtime_name: str = "",
    max_catalog_skills: int = 100,
    max_catalog_chars: int = 2000,
) -> str:
    contract = SkillExposureContract.from_payload(exposure)
    if contract is None or contract.is_empty():
        return ""
    blocks: list[str] = []
    collection_id = contract.collection_id or None
    if collection_id:
        catalog = render_skill_catalog_for_prompt(
            workspace,
            collection_id=collection_id,
            max_skills=max_catalog_skills,
            max_chars=max_catalog_chars,
        )
        if catalog:
            block = render_skill_prompt_block(
                workspace,
                source_prompt=source_prompt,
                skills_prompt=_augment_catalog(catalog, contract),
                collection_id=collection_id,
                strong_reminder=contract.requires_skill_read,
            )
            if block:
                blocks.append(block)
    direct_bind_block = _render_direct_bind_block(workspace, contract=contract, collection_id=collection_id)
    if direct_bind_block:
        blocks.append(direct_bind_block)
    runtime_extras = load_runtime_skill_extras(workspace, runtime_name=runtime_name)
    if runtime_extras:
        blocks.append("【Skill Exposure 运行约束】\n" + "\n".join(f"- {item}" for item in runtime_extras))
    return "\n\n".join(block for block in blocks if _normalize_text(block))


def _augment_catalog(catalog: str, contract: SkillExposureContract) -> str:
    lines = [str(catalog or "").strip()]
    if contract.family_hints:
        lines.append("【本轮优先 family】" + " / ".join(contract.family_hints))
    return "\n".join(line for line in lines if line).strip()


def _render_direct_bind_block(
    workspace: str,
    *,
    contract: SkillExposureContract,
    collection_id: str | None,
) -> str:
    bindings: list[str] = []
    bound_count = 0
    for skill_name in contract.direct_skill_names:
        if bound_count >= _MAX_DIRECT_BINDINGS:
            break
        item, text = read_skill_document(workspace, skill_name=skill_name, collection_id=collection_id)
        rendered = _render_direct_binding(item_name=skill_name, text=text, resolved_name=getattr(item, "name", ""))
        if rendered:
            bindings.append(rendered)
            bound_count += 1
    for skill_path in contract.direct_skill_paths:
        if bound_count >= _MAX_DIRECT_BINDINGS:
            break
        item, text = read_skill_document(workspace, skill_path=skill_path, collection_id=collection_id)
        rendered = _render_direct_binding(item_name=skill_path, text=text, resolved_name=getattr(item, "name", ""))
        if rendered:
            bindings.append(rendered)
            bound_count += 1
    if not bindings:
        return ""
    return (
        "【已直绑 Skill】本轮不要只停在 family shortlist；先阅读以下 leaf skill 的 `SKILL.md` 再执行。\n\n"
        + "\n\n".join(bindings)
    )


def _render_direct_binding(*, item_name: str, text: str, resolved_name: str = "") -> str:
    normalized_text = str(text or "").strip()
    if not normalized_text:
        return ""
    title = _normalize_text(resolved_name or item_name) or "unknown-skill"
    if len(normalized_text) > _MAX_DIRECT_BIND_CHARS:
        normalized_text = normalized_text[: _MAX_DIRECT_BIND_CHARS - 1].rstrip() + "…"
    return f"### {title}\n{normalized_text}"


__all__ = [
    "SkillExposureContract",
    "build_skill_exposure_observation",
    "normalize_skill_exposure_payload",
    "render_skill_exposure_prompt",
    "skill_exposure_provider_override",
    "summarize_skill_exposure",
]
