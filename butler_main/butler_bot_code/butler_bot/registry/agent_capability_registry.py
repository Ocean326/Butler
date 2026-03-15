from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from butler_paths import (
    PUBLIC_AGENT_LIBRARY_FILE_REL,
    SUBAGENT_HOME_REL,
    TEAM_HOME_REL,
    prompt_path_text,
    resolve_butler_root,
)


FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>[\s\S]*?)\n---\s*\n?", re.MULTILINE)


@dataclass(frozen=True)
class SubagentMetadata:
    role_name: str
    description: str
    relative_file: str
    tags: tuple[str, ...] = ()
    allowed_entry_roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class TeamMetadata:
    team_id: str
    name: str
    description: str
    relative_file: str
    mode: str
    entry_roles: tuple[str, ...] = ()
    member_roles: tuple[str, ...] = ()
    public_library_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class PublicCapabilityMetadata:
    capability_id: str
    name: str
    category: str
    description: str
    source_url: str
    fit_note: str = ""


def _parse_frontmatter(text: str) -> dict[str, str]:
    matched = FRONTMATTER_RE.match(text or "")
    if not matched:
        return {}
    metadata: dict[str, str] = {}
    for raw_line in matched.group("body").splitlines():
        line = str(raw_line or "").strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip().lower()] = value.strip().strip('"').strip("'")
    return metadata


def _parse_list_value(raw: str | list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if isinstance(raw, (list, tuple)):
        items = [str(item or "").strip() for item in raw]
    else:
        text = str(raw or "").strip()
        if not text:
            return ()
        normalized = text.replace("；", ",").replace("、", ",").replace("|", ",")
        items = [item.strip().strip('"').strip("'") for item in normalized.split(",")]
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return tuple(deduped)


def _truncate(text: str, limit: int) -> str:
    compact = str(text or "").strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _first_heading_or_text(text: str) -> str:
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            return line.lstrip("#").strip()
        return line
    return ""


def load_subagent_catalog(workspace: str | Path | None) -> list[SubagentMetadata]:
    root = resolve_butler_root(workspace)
    subagent_root = root / SUBAGENT_HOME_REL
    if not subagent_root.exists():
        return []
    catalog: list[SubagentMetadata] = []
    for path in sorted(subagent_root.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        metadata = _parse_frontmatter(text)
        role_name = str(metadata.get("name") or path.stem).strip() or path.stem
        description = str(metadata.get("description") or "").strip() or _first_heading_or_text(text)
        tags = _parse_list_value(metadata.get("tags"))
        allowed = _parse_list_value(metadata.get("allowed_entry_roles") or metadata.get("entry_roles"))
        catalog.append(
            SubagentMetadata(
                role_name=role_name,
                description=description,
                relative_file=prompt_path_text(path.relative_to(root)),
                tags=tags,
                allowed_entry_roles=allowed,
            )
        )
    return catalog


def load_team_catalog(workspace: str | Path | None) -> list[TeamMetadata]:
    root = resolve_butler_root(workspace)
    team_root = root / TEAM_HOME_REL
    if not team_root.exists():
        return []
    catalog: list[TeamMetadata] = []
    for path in sorted(team_root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        team_id = str(payload.get("team_id") or path.stem).strip() or path.stem
        name = str(payload.get("name") or team_id).strip() or team_id
        description = str(payload.get("description") or "").strip()
        mode = str(payload.get("execution_mode") or "mixed").strip() or "mixed"
        entry_roles = _parse_list_value(payload.get("entry_roles"))
        public_refs = _parse_list_value(payload.get("public_library_refs"))
        member_roles: list[str] = []
        for step in payload.get("steps") or []:
            if not isinstance(step, dict):
                continue
            for member in step.get("members") or []:
                if not isinstance(member, dict):
                    continue
                role_name = str(member.get("role") or "").strip()
                if role_name and role_name not in member_roles:
                    member_roles.append(role_name)
        catalog.append(
            TeamMetadata(
                team_id=team_id,
                name=name,
                description=description,
                relative_file=prompt_path_text(path.relative_to(root)),
                mode=mode,
                entry_roles=entry_roles,
                member_roles=tuple(member_roles),
                public_library_refs=public_refs,
            )
        )
    return catalog


def load_team_definition(workspace: str | Path | None, team_id: str) -> dict | None:
    target = str(team_id or "").strip()
    if not target:
        return None
    root = resolve_butler_root(workspace)
    team_root = root / TEAM_HOME_REL
    path = team_root / f"{target}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    for candidate in sorted(team_root.glob("*.json")):
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(payload.get("team_id") or "").strip() == target:
            return payload
    return None


def load_public_capability_catalog(workspace: str | Path | None) -> list[PublicCapabilityMetadata]:
    root = resolve_butler_root(workspace)
    path = root / PUBLIC_AGENT_LIBRARY_FILE_REL
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = payload.get("items") if isinstance(payload, dict) else []
    catalog: list[PublicCapabilityMetadata] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        capability_id = str(item.get("capability_id") or "").strip()
        name = str(item.get("name") or capability_id).strip() or capability_id
        if not capability_id:
            continue
        catalog.append(
            PublicCapabilityMetadata(
                capability_id=capability_id,
                name=name,
                category=str(item.get("category") or "reference").strip() or "reference",
                description=str(item.get("description") or "").strip(),
                source_url=str(item.get("source_url") or "").strip(),
                fit_note=str(item.get("fit_note") or "").strip(),
            )
        )
    return catalog


def render_subagent_catalog_for_prompt(workspace: str | Path | None, *, max_chars: int = 1200) -> str:
    catalog = load_subagent_catalog(workspace)
    if not catalog:
        return "当前未登记可调用 sub-agent。"
    lines = [
        "单角色专长任务优先匹配已登记 sub-agent；真正调用前先确认角色名命中登记表。",
        "sub-agent 只负责本轮局部任务，不得再递归调用 sub-agent 或 agent team。",
    ]
    for item in catalog[:10]:
        extras: list[str] = []
        if item.tags:
            extras.append("tags=" + "/".join(item.tags[:3]))
        if item.allowed_entry_roles:
            extras.append("entry=" + "/".join(item.allowed_entry_roles[:3]))
        suffix = " | ".join(extras)
        desc = _truncate(item.description, 96)
        line = f"- {item.role_name} @ {item.relative_file}"
        if desc:
            line += f" - {desc}"
        if suffix:
            line += f" | {suffix}"
        lines.append(line)
    rendered = "\n".join(lines).strip()
    return _truncate(rendered, max_chars)


def render_team_catalog_for_prompt(workspace: str | Path | None, *, max_chars: int = 1200) -> str:
    catalog = load_team_catalog(workspace)
    if not catalog:
        return "当前未登记可调用 agent team。"
    lines = [
        "复杂、多阶段、可并行任务优先匹配已登记 agent team；team 由主入口统一调度。",
        "team 成员可以并行执行，但 team 成员不得再次调用 sub-agent 或 team。",
    ]
    for item in catalog[:8]:
        extras: list[str] = [f"mode={item.mode}"]
        if item.member_roles:
            extras.append("roles=" + "/".join(item.member_roles[:4]))
        if item.public_library_refs:
            extras.append("refs=" + "/".join(item.public_library_refs[:3]))
        line = f"- {item.team_id} @ {item.relative_file} - {_truncate(item.description, 96)} | {' | '.join(extras)}"
        lines.append(line)
    rendered = "\n".join(lines).strip()
    return _truncate(rendered, max_chars)


def render_public_capability_catalog_for_prompt(workspace: str | Path | None, *, max_chars: int = 1000) -> str:
    catalog = load_public_capability_catalog(workspace)
    if not catalog:
        return "当前未登记公用 agent/team 参考库。"
    lines = [
        "公用库只作为已审阅参考来源；默认先本地登记、再执行，不直接远程托管调用。",
    ]
    for item in catalog[:6]:
        note = f" | {item.fit_note}" if item.fit_note else ""
        lines.append(f"- {item.capability_id} ({item.category}) - {_truncate(item.description, 88)}{note}")
    rendered = "\n".join(lines).strip()
    return _truncate(rendered, max_chars)


def render_agent_capability_catalog_for_prompt(workspace: str | Path | None, *, max_chars: int = 2600) -> str:
    parts = [
        "【Sub-Agents】\n" + render_subagent_catalog_for_prompt(workspace, max_chars=1000),
        "【Agent Teams】\n" + render_team_catalog_for_prompt(workspace, max_chars=1000),
        "【Public Library】\n" + render_public_capability_catalog_for_prompt(workspace, max_chars=700),
    ]
    rendered = "\n\n".join(part for part in parts if str(part or "").strip())
    return _truncate(rendered, max_chars)
