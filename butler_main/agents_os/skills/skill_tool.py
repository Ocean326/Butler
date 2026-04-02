from __future__ import annotations

from typing import Any

from .runtime_catalog import (
    build_skill_families,
    expand_skill_family,
    load_skill_catalog,
    read_skill_document,
    search_skill_catalog,
)


def skill_tool(
    action: str,
    *,
    workspace: str,
    name: str = "",
    arg: str = "",
    collection: str | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_action = str(action or "").strip().lower()
    collection_id = str(collection or "").strip() or None
    runtime_context = dict(runtime_context or {})
    if normalized_action == "search":
        query = str(name or arg).strip()
        if not query:
            return {
                "ok": False,
                "action": "search",
                "error": "missing_query",
                "collection": collection_id or "all",
            }
        families, skills = search_skill_catalog(workspace, query=query, collection_id=collection_id)
        return {
            "ok": True,
            "action": "search",
            "collection": collection_id or "all",
            "query": query,
            "families": [
                {
                    "family_id": family.family_id,
                    "label": family.label,
                    "summary": family.summary,
                    "category": family.category,
                    "risk_level": family.risk_level,
                    "member_count": len(family.members),
                    "members": [member.name for member in family.members[:5]],
                    "trigger_examples": list(family.trigger_examples[:5]),
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
                    "risk_level": item.risk_level,
                }
                for item in skills
            ],
            "runtime_context": runtime_context,
        }
    if normalized_action == "expand":
        family_query = str(name or arg).strip()
        family = expand_skill_family(workspace, family_id=family_query, collection_id=collection_id)
        if family is None:
            return {
                "ok": False,
                "action": "expand",
                "error": "family_not_found",
                "collection": collection_id or "all",
                "family": family_query,
            }
        return {
            "ok": True,
            "action": "expand",
            "collection": collection_id or "all",
            "family": {
                "family_id": family.family_id,
                "label": family.label,
                "summary": family.summary,
                "category": family.category,
                "risk_level": family.risk_level,
                "trigger_examples": list(family.trigger_examples),
                "member_count": len(family.members),
            },
            "items": [
                {
                    "name": item.name,
                    "description": item.description,
                    "path": item.relative_dir,
                    "skill_file": item.relative_skill_file,
                    "risk_level": item.risk_level,
                    "automation_safe": item.automation_safe,
                    "requires_skill_read": item.requires_skill_read,
                }
                for item in family.members
            ],
            "runtime_context": runtime_context,
        }
    if normalized_action == "list":
        catalog = load_skill_catalog(workspace, collection_id=collection_id)
        items = [
            {
                "name": item.name,
                "description": item.description,
                "category": item.category,
                "family_id": item.family_id,
                "family_label": item.family_label,
                "path": item.relative_dir,
                "skill_file": item.relative_skill_file,
                "status": item.status,
                "risk_level": item.risk_level,
                "automation_safe": item.automation_safe,
                "requires_skill_read": item.requires_skill_read,
            }
            for item in catalog
        ]
        return {
            "ok": True,
            "action": "list",
            "collection": collection_id or "all",
            "families": [
                {
                    "family_id": family.family_id,
                    "label": family.label,
                    "summary": family.summary,
                    "member_count": len(family.members),
                    "members": [member.name for member in family.members[:5]],
                }
                for family in build_skill_families(catalog)
            ],
            "items": items,
            "runtime_context": runtime_context,
        }
    if normalized_action in {"read", "show"}:
        item, text = read_skill_document(
            workspace,
            skill_name=name or arg,
            skill_path=arg if str(arg or "").strip().startswith(".") else "",
            collection_id=collection_id,
        )
        if item is None:
            return {
                "ok": False,
                "action": normalized_action,
                "error": "skill_not_found",
                "collection": collection_id or "all",
                "name": name or arg,
            }
        return {
            "ok": True,
            "action": normalized_action,
            "collection": collection_id or "all",
            "item": {
                "name": item.name,
                "description": item.description,
                "category": item.category,
                "family_id": item.family_id,
                "family_label": item.family_label,
                "path": item.relative_dir,
                "skill_file": item.relative_skill_file,
                "status": item.status,
                "risk_level": item.risk_level,
                "automation_safe": item.automation_safe,
                "requires_skill_read": item.requires_skill_read,
            },
            "content": text,
        }
    if normalized_action == "exec":
        return {
            "ok": False,
            "action": "exec",
            "error": "skill_exec_not_wired",
            "message": "读取 SKILL.md 后，需要由具体 runtime/executor 执行；当前只提供统一 registry/list/read 接口。",
            "collection": collection_id or "all",
            "name": name or arg,
            "runtime_context": runtime_context,
        }
    return {
        "ok": False,
        "action": normalized_action,
        "error": "unsupported_action",
        "supported_actions": ["list", "search", "expand", "read", "show", "exec"],
    }


__all__ = ["skill_tool"]
