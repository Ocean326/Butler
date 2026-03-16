from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from butler_paths import SKILLS_HOME_REL, prompt_path_text, resolve_butler_root


FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>[\s\S]*?)\n---\s*\n?", re.MULTILINE)
CATEGORY_PATTERNS = (
    ("feishu", ("feishu", "lark", "chat-history", "chat_history", "doc")),
    ("operations", ("inspection", "daily", "ops", "operation", "maint", "guardian")),
    ("research", ("xiaohongshu", "xhs", "literature", "research", "crawl", "scrape")),
)


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    category: str
    relative_dir: str
    relative_skill_file: str
    trigger_examples: tuple[str, ...] = ()
    allowed_roles: tuple[str, ...] = ()
    risk_level: str = "unknown"
    heartbeat_safe: bool = False
    requires_skill_read: bool = True


def _skills_root(workspace: str | Path | None) -> Path:
    return resolve_butler_root(workspace) / SKILLS_HOME_REL


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


def _parse_list_value(raw: str | None) -> tuple[str, ...]:
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


def _parse_bool_value(raw: str | None, default: bool) -> bool:
    text = str(raw or "").strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _iter_skill_dirs(skills_root: Path) -> list[Path]:
    if not skills_root.exists():
        return []
    skill_dirs: list[Path] = []
    for skill_file in skills_root.rglob("SKILL.md"):
        if "__pycache__" in skill_file.parts:
            continue
        if any(str(part or "").startswith("_tmp") for part in skill_file.parts):
            continue
        if any(part in {".git", ".hg", ".svn", "node_modules"} for part in skill_file.parts):
            continue
        skill_dirs.append(skill_file.parent)
    return sorted(skill_dirs)


def _infer_category(skill_dir: Path, metadata: dict[str, str]) -> str:
    declared = str(metadata.get("category") or "").strip().lower()
    if declared:
        return declared
    haystack = " ".join(part.lower() for part in skill_dir.parts)
    for category, keywords in CATEGORY_PATTERNS:
        if any(keyword in haystack for keyword in keywords):
            return category
    return "general"


def load_skill_catalog(workspace: str | Path | None) -> list[SkillMetadata]:
    skills_root = _skills_root(workspace)
    root = resolve_butler_root(workspace)
    catalog: list[SkillMetadata] = []
    for skill_dir in _iter_skill_dirs(skills_root):
        skill_file = skill_dir / "SKILL.md"
        try:
            text = skill_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        metadata = _parse_frontmatter(text)
        relative_dir = prompt_path_text(skill_dir.relative_to(root))
        relative_skill_file = prompt_path_text(skill_file.relative_to(root))
        name = str(metadata.get("name") or skill_dir.name).strip() or skill_dir.name
        description = str(metadata.get("description") or "").strip()
        category = _infer_category(skill_dir, metadata)
        catalog.append(
            SkillMetadata(
                name=name,
                description=description,
                category=category,
                relative_dir=relative_dir,
                relative_skill_file=relative_skill_file,
                trigger_examples=_parse_list_value(metadata.get("trigger_examples") or metadata.get("triggers")),
                allowed_roles=_parse_list_value(metadata.get("allowed_roles") or metadata.get("roles")),
                risk_level=str(metadata.get("risk_level") or metadata.get("risk") or "unknown").strip().lower() or "unknown",
                heartbeat_safe=_parse_bool_value(metadata.get("heartbeat_safe"), default=False),
                requires_skill_read=_parse_bool_value(metadata.get("requires_skill_read"), default=True),
            )
        )
    catalog.sort(key=lambda item: (item.category, item.name.lower()))
    return catalog


def render_skill_catalog_for_prompt(
    workspace: str | Path | None,
    *,
    max_skills: int = 16,
    max_chars: int = 1800,
) -> str:
    catalog = load_skill_catalog(workspace)
    if not catalog:
        return (
            "DNA 核心能力保留在主代码：身体运行、灵魂、记忆、心跳。\n"
            "当前未发现可复用 skills；若用户要求调用 skill，应明确告知当前 `./butler_main/butler_bot_agent/skills/` 下未找到命中项，而不是假装已调用。\n"
            "若新增非核心复用能力，请写入 ./butler_main/butler_bot_agent/skills/分类目录/技能名/。"
        )

    lines = [
        "DNA 核心能力保留在主代码：身体运行、灵魂、记忆、心跳；不要把这些拆成 skills。",
        "调用 skill 的标准动作：先在 `./butler_main/butler_bot_agent/skills/` 里匹配最相关目录 -> 读取其中 `SKILL.md` -> 按文档执行 -> 在回复里明确说出本次使用的 skill 名和路径。",
        "如果用户说“调用 skill/技能”但没点名，你要先在已登记 skills 里匹配最相关项；如果没找到，就直说未命中，并给出你扫描过的目录或候选。",
        "非核心、可复用、可配置的外部能力优先走 skills。当前已登记：",
    ]
    current_category = ""
    count = 0
    for item in catalog:
        if count >= max_skills:
            break
        if item.category != current_category:
            current_category = item.category
            lines.append(f"[{current_category}]")
        desc = item.description[:160] if item.description else ""
        extras: list[str] = []
        if item.trigger_examples:
            extras.append("triggers=" + "/".join(item.trigger_examples[:3]))
        if item.allowed_roles:
            extras.append("roles=" + "/".join(item.allowed_roles[:2]))
        if item.heartbeat_safe:
            extras.append("heartbeat-safe")
        if not item.requires_skill_read:
            extras.append("read-optional")
        if item.risk_level != "unknown":
            extras.append(f"risk={item.risk_level}")
        suffix_parts = []
        if desc:
            suffix_parts.append(desc)
        if extras:
            suffix_parts.append("; ".join(extras))
        suffix = f" - {' | '.join(suffix_parts)}" if suffix_parts else ""
        lines.append(f"- {item.name} @ {item.relative_dir}{suffix}")
        count += 1

    if len(catalog) > count:
        lines.append(f"- 其余 {len(catalog) - count} 个 skill 已省略；如需扩展请继续扫描 skills 目录。")

    lines.append("新增 skill 时优先放到分类子目录，保留 SKILL.md 作为入口说明；调用 skill 不是神秘函数名，而是按该目录下的 SKILL.md 执行。")
    rendered = "\n".join(lines).strip()
    if len(rendered) <= max_chars:
        return rendered
    return rendered[: max_chars - 1].rstrip() + "…"
