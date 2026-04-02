from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from .collection_registry import (
    load_skill_collection_registry,
    normalize_rel_path,
    resolve_collection_skill_dirs,
    source_skills_root,
)
from .models import SkillFamily, SkillMetadata
from .pathing import prompt_path_text, resolve_butler_root
from .prompt_policy import (
    render_skill_catalog_empty_state,
    render_skill_catalog_intro,
    render_skill_overflow_line,
)


FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>[\s\S]*?)\n---\s*\n?", re.MULTILINE)
CATEGORY_PATTERNS = (
    ("feishu", ("feishu", "lark", "chat-history", "chat_history", "doc")),
    ("operations", ("inspection", "daily", "ops", "operation", "maint", "guardian")),
    ("research", ("xiaohongshu", "xhs", "literature", "research", "crawl", "scrape", "ocr", "web")),
)
INACTIVE_SKILL_STATUSES = {"draft", "incubating", "archived", "disabled", "private"}


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
        key = item.lower()
        if not item or key in seen:
            continue
        seen.add(key)
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


def _parse_int_value(raw: str | None, default: int) -> int:
    text = str(raw or "").strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def _normalize_identifier(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").strip().lower()).strip("-")


def _iter_skill_dirs(skills_root: Path) -> list[Path]:
    if not skills_root.exists():
        return []
    skill_dirs: list[Path] = []
    for skill_file in skills_root.rglob("SKILL.md"):
        if "__pycache__" in skill_file.parts:
            continue
        if any(str(part or "").startswith("_tmp") for part in skill_file.parts):
            continue
        if any(part in {".git", ".hg", ".svn", "node_modules", "collections"} for part in skill_file.parts):
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


def _default_skill_dirs(workspace: str | Path | None) -> list[Path]:
    return _iter_skill_dirs(source_skills_root(workspace))


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _normalize_status(metadata: dict[str, str]) -> str:
    return str(metadata.get("status") or metadata.get("skill_status") or "active").strip().lower() or "active"


def _risk_rank(level: str) -> int:
    mapping = {"unknown": 0, "low": 1, "medium": 2, "high": 3}
    return mapping.get(str(level or "").strip().lower(), 0)


def _dedupe_texts(*groups: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    items: list[str] = []
    for group in groups:
        for raw in group:
            text = str(raw or "").strip()
            key = text.lower()
            if not text or key in seen:
                continue
            seen.add(key)
            items.append(text)
    return tuple(items)


def _build_skill_metadata(root: Path, skill_dir: Path) -> SkillMetadata | None:
    skill_file = skill_dir / "SKILL.md"
    try:
        text = skill_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    metadata = _parse_frontmatter(text)
    try:
        relative_dir = prompt_path_text(skill_dir.relative_to(root))
        relative_skill_file = prompt_path_text(skill_file.relative_to(root))
    except Exception:
        relative_dir = str(skill_dir)
        relative_skill_file = str(skill_file)
    name = str(metadata.get("name") or skill_dir.name).strip() or skill_dir.name
    description = str(metadata.get("description") or "").strip()
    category = _infer_category(skill_dir, metadata)
    family_id = _normalize_identifier(str(metadata.get("family_id") or "").strip()) or _normalize_identifier(name)
    family_label = str(metadata.get("family_label") or name).strip() or name
    family_summary = str(metadata.get("family_summary") or description).strip()
    return SkillMetadata(
        name=name,
        description=description,
        category=category,
        relative_dir=relative_dir,
        relative_skill_file=relative_skill_file,
        family_id=family_id,
        family_label=family_label,
        family_summary=family_summary,
        status=_normalize_status(metadata),
        trigger_examples=_parse_list_value(metadata.get("trigger_examples") or metadata.get("triggers")),
        family_trigger_examples=_parse_list_value(metadata.get("family_trigger_examples")),
        allowed_roles=_parse_list_value(metadata.get("allowed_roles") or metadata.get("roles")),
        aliases=_parse_list_value(metadata.get("aliases") or metadata.get("tags")),
        risk_level=str(metadata.get("risk_level") or metadata.get("risk") or "unknown").strip().lower() or "unknown",
        automation_safe=_parse_bool_value(metadata.get("automation_safe"), default=False),
        requires_skill_read=_parse_bool_value(metadata.get("requires_skill_read"), default=True),
        variant_rank=_parse_int_value(metadata.get("variant_rank"), default=100),
    )


def load_skill_catalog(workspace: str | Path | None, *, collection_id: str | None = None) -> list[SkillMetadata]:
    root = resolve_butler_root(workspace)
    normalized_collection = str(collection_id or "").strip()
    if normalized_collection:
        skill_dirs = resolve_collection_skill_dirs(workspace, normalized_collection)
    else:
        skill_dirs = _default_skill_dirs(workspace)
    catalog: list[SkillMetadata] = []
    for skill_dir in skill_dirs:
        item = _build_skill_metadata(root, skill_dir)
        if item is not None:
            if item.status in INACTIVE_SKILL_STATUSES:
                continue
            catalog.append(item)
    if not normalized_collection:
        catalog.sort(key=lambda item: (item.category, item.name.lower()))
    return catalog


def build_skill_families(catalog: list[SkillMetadata]) -> list[SkillFamily]:
    grouped: dict[str, list[SkillMetadata]] = {}
    order: list[str] = []
    for item in catalog:
        family_id = str(item.family_id or "").strip() or _normalize_identifier(item.name) or item.name.lower()
        if family_id not in grouped:
            grouped[family_id] = []
            order.append(family_id)
        grouped[family_id].append(item)
    families: list[SkillFamily] = []
    for family_id in order:
        members = tuple(sorted(grouped.get(family_id, []), key=lambda item: (item.variant_rank, item.name.lower())))
        if not members:
            continue
        first = members[0]
        label = str(first.family_label or first.name).strip() or first.name
        summary = str(first.family_summary or first.description or "查看该 family 下 skill 的 `SKILL.md` 了解用途。").strip()
        triggers = _dedupe_texts(
            tuple(text for member in members for text in member.family_trigger_examples),
            tuple(text for member in members for text in member.trigger_examples),
        )
        risk_level = max((member.risk_level for member in members), key=_risk_rank, default="unknown")
        families.append(
            SkillFamily(
                family_id=family_id,
                label=label,
                summary=summary,
                category=first.category,
                risk_level=risk_level,
                trigger_examples=triggers,
                members=members,
            )
        )
    return families


def expand_skill_family(
    workspace: str | Path | None,
    *,
    family_id: str = "",
    collection_id: str | None = None,
) -> SkillFamily | None:
    normalized = str(family_id or "").strip().lower()
    if not normalized:
        return None
    for family in build_skill_families(load_skill_catalog(workspace, collection_id=collection_id)):
        aliases = {
            family.family_id.lower(),
            family.label.strip().lower(),
            _normalize_identifier(family.label).lower(),
        }
        if normalized in aliases:
            return family
        if any(normalized == member.name.strip().lower() for member in family.members):
            return family
    return None


def _search_score(query: str, *haystacks: str) -> int:
    normalized_query = str(query or "").strip().lower()
    if not normalized_query:
        return 0
    tokens = [token for token in re.split(r"[\s,;|/\\:_\-]+", normalized_query) if token]
    haystack = " ".join(str(item or "").strip().lower() for item in haystacks if str(item or "").strip())
    if not haystack:
        return 0
    score = 0
    if normalized_query in haystack:
        score += 12
    for token in tokens:
        if token in haystack:
            score += 4 if len(token) >= 3 else 2
    return score


def search_skill_catalog(
    workspace: str | Path | None,
    *,
    query: str,
    collection_id: str | None = None,
    family_limit: int = 5,
    skill_limit: int = 5,
) -> tuple[list[SkillFamily], list[SkillMetadata]]:
    catalog = load_skill_catalog(workspace, collection_id=collection_id)
    families = build_skill_families(catalog)
    family_hits = sorted(
        (
            (
                _search_score(
                    query,
                    family.label,
                    family.summary,
                    family.family_id,
                    " ".join(family.trigger_examples),
                    " ".join(member.name for member in family.members),
                ),
                index,
                family,
            )
            for index, family in enumerate(families)
        ),
        key=lambda item: (-item[0], item[1]),
    )
    skill_hits = sorted(
        (
            (
                _search_score(
                    query,
                    item.name,
                    item.description,
                    item.family_label,
                    item.family_summary,
                    item.family_id,
                    " ".join(item.trigger_examples),
                    " ".join(item.aliases),
                ),
                index,
                item,
            )
            for index, item in enumerate(catalog)
        ),
        key=lambda item: (-item[0], item[1]),
    )
    matched_families = [family for score, _, family in family_hits if score > 0][: max(family_limit, 0)]
    matched_skills = [item for score, _, item in skill_hits if score > 0][: max(skill_limit, 0)]
    return matched_families, matched_skills


def read_skill_document(
    workspace: str | Path | None,
    *,
    skill_name: str = "",
    skill_path: str = "",
    collection_id: str | None = None,
) -> tuple[SkillMetadata | None, str]:
    normalized_name = str(skill_name or "").strip().lower()
    normalized_path = str(skill_path or "").strip().replace("\\", "/").lower()
    for item in load_skill_catalog(workspace, collection_id=collection_id):
        if normalized_name and item.name.strip().lower() != normalized_name:
            continue
        if normalized_path and normalized_path not in {
            item.relative_dir.lower(),
            item.relative_skill_file.lower(),
            item.relative_dir.lower().lstrip("./"),
            item.relative_skill_file.lower().lstrip("./"),
        }:
            continue
        try:
            root = resolve_butler_root(workspace)
            text = (root / item.relative_skill_file.lstrip("./")).read_text(encoding="utf-8")
        except OSError:
            return item, ""
        return item, text
    return None, ""


def render_skill_catalog_for_prompt(
    workspace: str | Path | None,
    *,
    collection_id: str | None = None,
    max_skills: int = 16,
    max_chars: int = 1800,
) -> str:
    normalized_collection = str(collection_id or "").strip()
    catalog = load_skill_catalog(workspace, collection_id=normalized_collection or None)
    if not catalog:
        return render_skill_catalog_empty_state(workspace, collection_id=normalized_collection or None)
    lines = render_skill_catalog_intro(workspace, collection_id=normalized_collection or None)
    families = build_skill_families(catalog)
    count = 0
    for family in families:
        if count >= max_skills:
            break
        summary = str(family.summary or "").strip()
        summary = summary.split("。", 1)[0].strip() if "。" in summary else summary
        summary = (summary or "查看该 family 下 skill 的 `SKILL.md` 了解用途。").strip()
        if summary and not summary.endswith(("。", "！", "？", ".", "!", "?")):
            summary += "。"
        members_preview = ", ".join(member.name for member in family.members[:3])
        if len(family.members) > 3:
            members_preview += " 等"
        suffix_parts = [f"成员：{members_preview}"]
        if family.trigger_examples:
            suffix_parts.append(f"触发：{' / '.join(family.trigger_examples[:2])}")
        lines.append(
            f"- {family.label}（family={family.family_id}, {len(family.members)} skills, risk={family.risk_level}）："
            f"{summary[:90]} {'；'.join(part for part in suffix_parts if part)}"
        )
        count += 1
    rendered = "\n".join(line for line in lines if line).strip()
    if len(families) > count:
        candidate = f"{rendered}\n{render_skill_overflow_line(workspace, remaining=len(families) - count)}".strip()
        rendered = candidate if len(candidate) <= max_chars else rendered
    return rendered if len(rendered) <= max_chars else rendered[: max_chars - 1].rstrip() + "…"


def _collection_payload(workspace: str | Path | None, collection_id: str) -> dict[str, object]:
    registry = load_skill_collection_registry(workspace)
    collections = registry.get("collections") if isinstance(registry.get("collections"), dict) else {}
    payload = collections.get(str(collection_id or "").strip()) if isinstance(collections, dict) else None
    return dict(payload) if isinstance(payload, dict) else {}


def _collection_entry_records(
    workspace: str | Path | None,
    *,
    collection_id: str,
) -> list[dict[str, object]]:
    payload = _collection_payload(workspace, collection_id)
    root = resolve_butler_root(workspace)
    entries = payload.get("skills") if isinstance(payload.get("skills"), list) else []
    records: list[dict[str, object]] = []
    for entry in entries:
        raw_path = entry.get("path") if isinstance(entry, dict) else entry
        normalized = normalize_rel_path(raw_path)
        if not normalized:
            continue
        candidate = root / Path(normalized)
        skill_file = candidate if candidate.name.lower() == "skill.md" else candidate / "SKILL.md"
        records.append(
            {
                "path": normalized,
                "skill_file": skill_file,
                "exists": skill_file.exists(),
            }
        )
    return records


def _collection_diagnostics(
    workspace: str | Path | None,
    *,
    collection_id: str,
) -> list[dict[str, str]]:
    root = resolve_butler_root(workspace)
    records = _collection_entry_records(workspace, collection_id=collection_id)
    issues: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for record in records:
        normalized = str(record.get("path") or "").strip()
        if not normalized:
            continue
        if normalized in seen_paths:
            issues.append(
                {
                    "level": "warning",
                    "kind": "duplicate_entry",
                    "collection_id": collection_id,
                    "path": normalized,
                    "message": f"duplicate skill entry in collection {collection_id}",
                }
            )
            continue
        seen_paths.add(normalized)
        skill_file = record.get("skill_file")
        if not isinstance(skill_file, Path) or not bool(record.get("exists")):
            issues.append(
                {
                    "level": "error",
                    "kind": "missing_path",
                    "collection_id": collection_id,
                    "path": normalized,
                    "message": f"skill path missing for collection {collection_id}",
                }
            )
            continue
        item = _build_skill_metadata(root, skill_file.parent)
        if item is None:
            issues.append(
                {
                    "level": "error",
                    "kind": "invalid_skill_document",
                    "collection_id": collection_id,
                    "path": normalized,
                    "message": f"skill document is unreadable for collection {collection_id}",
                }
            )
            continue
        if item.status in INACTIVE_SKILL_STATUSES:
            issues.append(
                {
                    "level": "warning",
                    "kind": "inactive_reference",
                    "collection_id": collection_id,
                    "path": normalized,
                    "skill_name": item.name,
                    "message": f"inactive skill {item.name} is referenced by collection {collection_id}",
                }
            )
    return issues


def list_skill_collections(workspace: str | Path | None) -> list[dict[str, object]]:
    registry = load_skill_collection_registry(workspace)
    collections = registry.get("collections") if isinstance(registry.get("collections"), dict) else {}
    items: list[dict[str, object]] = []
    for collection_id, raw_payload in collections.items():
        payload = dict(raw_payload) if isinstance(raw_payload, dict) else {}
        catalog = load_skill_catalog(workspace, collection_id=collection_id)
        families = build_skill_families(catalog)
        diagnostics = _collection_diagnostics(workspace, collection_id=collection_id)
        items.append(
            {
                "collection_id": str(collection_id or "").strip(),
                "description": str(payload.get("description") or "").strip(),
                "owner": str(payload.get("owner") or "").strip(),
                "status": str(payload.get("status") or "active").strip() or "active",
                "allowed_runtimes": [
                    str(item).strip()
                    for item in payload.get("allowed_runtimes") or []
                    if str(item).strip()
                ],
                "default_injection_mode": str(payload.get("default_injection_mode") or "shortlist").strip() or "shortlist",
                "risk_budget": str(payload.get("risk_budget") or "").strip(),
                "phase_tags": [
                    str(item).strip()
                    for item in payload.get("phase_tags") or []
                    if str(item).strip()
                ],
                "ui_visibility": str(payload.get("ui_visibility") or "visible").strip() or "visible",
                "entry_count": len(_collection_entry_records(workspace, collection_id=collection_id)),
                "skill_count": len(catalog),
                "family_count": len(families),
                "diagnostic_count": len(diagnostics),
            }
        )
    items.sort(key=lambda item: str(item.get("collection_id") or ""))
    return items


def get_skill_collection_detail(
    workspace: str | Path | None,
    *,
    collection_id: str,
) -> dict[str, object] | None:
    normalized = str(collection_id or "").strip()
    if not normalized:
        return None
    payload = _collection_payload(workspace, normalized)
    if not payload:
        return None
    catalog = load_skill_catalog(workspace, collection_id=normalized)
    families = build_skill_families(catalog)
    diagnostics = _collection_diagnostics(workspace, collection_id=normalized)
    return {
        "collection_id": normalized,
        "description": str(payload.get("description") or "").strip(),
        "owner": str(payload.get("owner") or "").strip(),
        "status": str(payload.get("status") or "active").strip() or "active",
        "allowed_runtimes": [
            str(item).strip()
            for item in payload.get("allowed_runtimes") or []
            if str(item).strip()
        ],
        "default_injection_mode": str(payload.get("default_injection_mode") or "shortlist").strip() or "shortlist",
        "risk_budget": str(payload.get("risk_budget") or "").strip(),
        "phase_tags": [
            str(item).strip()
            for item in payload.get("phase_tags") or []
            if str(item).strip()
        ],
        "ui_visibility": str(payload.get("ui_visibility") or "visible").strip() or "visible",
        "families": [
            {
                "family_id": family.family_id,
                "label": family.label,
                "summary": family.summary,
                "category": family.category,
                "risk_level": family.risk_level,
                "trigger_examples": list(family.trigger_examples),
                "member_count": len(family.members),
                "members": [member.name for member in family.members],
            }
            for family in families
        ],
        "skills": [
            {
                "name": item.name,
                "description": item.description,
                "family_id": item.family_id,
                "family_label": item.family_label,
                "category": item.category,
                "path": item.relative_dir,
                "skill_file": item.relative_skill_file,
                "status": item.status,
                "risk_level": item.risk_level,
                "automation_safe": item.automation_safe,
                "requires_skill_read": item.requires_skill_read,
            }
            for item in catalog
        ],
        "diagnostics": diagnostics,
    }


def build_skill_registry_diagnostics(workspace: str | Path | None) -> dict[str, object]:
    collections = list_skill_collections(workspace)
    issues: list[dict[str, str]] = []
    for item in collections:
        collection_id = str(item.get("collection_id") or "").strip()
        issues.extend(_collection_diagnostics(workspace, collection_id=collection_id))
    return {
        "generated_at": _utc_now_iso(),
        "summary": {
            "collection_count": len(collections),
            "issue_count": len(issues),
            "error_count": sum(1 for item in issues if item.get("level") == "error"),
            "warning_count": sum(1 for item in issues if item.get("level") == "warning"),
        },
        "collections": collections,
        "issues": issues,
    }


__all__ = [
    "build_skill_families",
    "build_skill_registry_diagnostics",
    "expand_skill_family",
    "get_skill_collection_detail",
    "list_skill_collections",
    "load_skill_catalog",
    "read_skill_document",
    "render_skill_catalog_for_prompt",
    "search_skill_catalog",
]
