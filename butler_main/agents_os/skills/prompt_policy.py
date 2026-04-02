from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .pathing import SKILL_PROMPT_POLICY_FILE_REL, resolve_butler_root


DEFAULT_PROMPT_POLICY: dict[str, Any] = {
    "version": 1,
    "catalog": {
        "identity_line": "skills 只承载非核心、可复用的外部能力；身体运行、灵魂、记忆与自动化调度仍属于主代码。",
        "selection_line": "先在当前可见 capability families{collection_hint}里匹配最相关族群；命中后再在该 family 内二级检索具体 skill，读取 `SKILL.md` 后执行；未命中就直说。",
        "heading": "当前可见 capability families：",
        "empty_line": "当前可见 skill{collection_hint} 为空；若本轮需要 skill，请明确说明未命中当前 collection，不要假装已调用。",
        "overflow_line": "其余 {remaining} 个 family 已折叠；如需扩展，请在命中的 family 内继续检索具体 skill。",
    },
    "prompt_block": {
        "title": "【可复用 Skills】",
        "preface": "优先先在当前可见 capability families{collection_hint}中匹配最相关族群；命中后再做二级检索并读取 `SKILL.md`，未命中就直说。",
        "strong_reminder": "【本轮提醒】本轮明显涉及 skill / 抓取 / 检索 / OCR / MCP；不要只口头说会用，先锁定 family，再读取对应 `SKILL.md` 后执行。",
        "default_rule": "【默认规则】涉及资料抓取、文档读取、OCR、站点操作或结构化复用时，先看下方 family shortlist；若某个 family 明显命中，先在该 family 内继续检索具体 skill。",
    },
    "runtime_overrides": {
        "orchestrator": {
            "extras": [
                "少做碎片化微操：优先沉淀可复用能力、阶段性结论和稳定工作流，不要把自动化流程浪费在无止境的小修小补上。",
                "升级不要只停在死知识：如果识别到值得长期保留的能力，应尽量把它推进成可执行的 role/prompt/config/skill，而不是只留下一条说明。",
            ]
        }
    },
}


def prompt_policy_file(workspace: str | Path | None) -> Path:
    return resolve_butler_root(workspace) / SKILL_PROMPT_POLICY_FILE_REL


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_skill_prompt_policy(workspace: str | Path | None) -> dict[str, Any]:
    path = prompt_policy_file(workspace)
    if not path.exists():
        return deepcopy(DEFAULT_PROMPT_POLICY)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return deepcopy(DEFAULT_PROMPT_POLICY)
    if not isinstance(payload, dict):
        return deepcopy(DEFAULT_PROMPT_POLICY)
    return _merge_dict(DEFAULT_PROMPT_POLICY, payload)


def collection_hint_text(collection_id: str | None, *, empty_when_missing: bool = False) -> str:
    normalized = str(collection_id or "").strip()
    if normalized:
        return f"（collection={normalized}）"
    return "" if empty_when_missing else "（collection=all）"


def render_skill_catalog_intro(
    workspace: str | Path | None,
    *,
    collection_id: str | None = None,
) -> list[str]:
    policy = load_skill_prompt_policy(workspace)
    catalog_policy = policy.get("catalog") if isinstance(policy.get("catalog"), dict) else {}
    collection_hint = collection_hint_text(collection_id)
    return [
        str(catalog_policy.get("identity_line") or "").strip(),
        str(catalog_policy.get("selection_line") or "").format(collection_hint=collection_hint).strip(),
        str(catalog_policy.get("heading") or "").strip(),
    ]


def render_skill_catalog_empty_state(
    workspace: str | Path | None,
    *,
    collection_id: str | None = None,
) -> str:
    policy = load_skill_prompt_policy(workspace)
    catalog_policy = policy.get("catalog") if isinstance(policy.get("catalog"), dict) else {}
    collection_hint = collection_hint_text(collection_id, empty_when_missing=True)
    lines = [
        str(catalog_policy.get("identity_line") or "").strip(),
        str(catalog_policy.get("empty_line") or "").format(collection_hint=collection_hint).strip(),
    ]
    return "\n".join(line for line in lines if line)


def render_skill_overflow_line(
    workspace: str | Path | None,
    *,
    remaining: int,
) -> str:
    policy = load_skill_prompt_policy(workspace)
    catalog_policy = policy.get("catalog") if isinstance(policy.get("catalog"), dict) else {}
    template = str(
        catalog_policy.get(
            "overflow_line",
            "其余 {remaining} 个 family 已折叠；如需扩展，请在命中的 family 内继续检索具体 skill。",
        )
    )
    return template.format(remaining=remaining).strip()


def render_skill_prompt_block(
    workspace: str | Path | None,
    *,
    source_prompt: str,
    skills_prompt: str,
    collection_id: str | None = None,
    strong_reminder: bool = False,
) -> str:
    policy = load_skill_prompt_policy(workspace)
    prompt_block = policy.get("prompt_block") if isinstance(policy.get("prompt_block"), dict) else {}
    collection_hint = collection_hint_text(collection_id, empty_when_missing=True)
    lines = [
        (
            f"{str(prompt_block.get('title') or '【可复用 Skills】')}"
            f"{str(prompt_block.get('preface') or '').format(collection_hint=collection_hint).strip()}"
        ).strip(),
        str(prompt_block.get("strong_reminder") if strong_reminder else prompt_block.get("default_rule") or "").strip(),
        str(skills_prompt or "").strip(),
    ]
    return "\n".join(line for line in lines if line)


def load_runtime_skill_extras(
    workspace: str | Path | None,
    *,
    runtime_name: str,
) -> tuple[str, ...]:
    policy = load_skill_prompt_policy(workspace)
    runtime_overrides = policy.get("runtime_overrides") if isinstance(policy.get("runtime_overrides"), dict) else {}
    runtime_payload = runtime_overrides.get(str(runtime_name or "").strip()) if isinstance(runtime_overrides, dict) else None
    if not isinstance(runtime_payload, dict):
        return ()
    extras = runtime_payload.get("extras")
    if not isinstance(extras, list):
        return ()
    return tuple(str(item or "").strip() for item in extras if str(item or "").strip())


__all__ = [
    "collection_hint_text",
    "load_runtime_skill_extras",
    "load_skill_prompt_policy",
    "prompt_policy_file",
    "render_skill_catalog_empty_state",
    "render_skill_catalog_intro",
    "render_skill_overflow_line",
    "render_skill_prompt_block",
]
