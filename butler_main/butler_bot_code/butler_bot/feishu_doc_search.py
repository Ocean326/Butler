# -*- coding: utf-8 -*-
"""
飞书文档检索模块

调用飞书云文档搜索 API，检索企业内的文档、电子表格、多维表格等。
需在飞书开放平台申请「搜索云文档」或「docs:doc:read」等权限。
"""

from __future__ import annotations

from typing import Callable

try:
    import requests
except ImportError:
    requests = None

# 飞书文档搜索 API（suite docs-api）
FEISHU_DOCS_SEARCH_URL = "https://open.feishu.cn/open-apis/suite/docs-api/search/object"

# 备用：部分环境可能使用不同路径
FEISHU_DOCS_SEARCH_URL_ALT = "https://open.feishu.cn/suite/docs-api/search/object"


def search_feishu_docs(
    search_key: str,
    get_token_fn: Callable[[], str],
    count: int = 10,
    offset: int = 0,
    docs_types: list[str] | None = None,
) -> dict:
    """
    搜索飞书云文档。

    Args:
        search_key: 搜索关键字
        get_token_fn: 获取 tenant_access_token 的函数
        count: 返回数量，0-50
        offset: 偏移量
        docs_types: 文档类型过滤，如 ["doc", "sheet", "bitable"]

    Returns:
        {"ok": bool, "docs": [...], "total": int, "error": str}
    """
    if not requests:
        return {"ok": False, "docs": [], "total": 0, "error": "缺少 requests 库"}
    if not search_key or not search_key.strip():
        return {"ok": False, "docs": [], "total": 0, "error": "搜索关键字为空"}

    payload = {
        "search_key": search_key.strip(),
        "count": min(max(0, count), 50),
        "offset": max(0, offset),
    }
    if docs_types:
        payload["docs_types"] = docs_types

    try:
        token = get_token_fn()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            FEISHU_DOCS_SEARCH_URL,
            headers=headers,
            json=payload,
            timeout=15,
        )
        data = resp.json()

        if data.get("code") != 0:
            err_msg = data.get("msg", "未知错误")
            # 若主 URL 失败，尝试备用（部分环境）
            if "suite" in str(data) or resp.status_code >= 400:
                try:
                    resp2 = requests.post(
                        FEISHU_DOCS_SEARCH_URL_ALT,
                        headers=headers,
                        json=payload,
                        timeout=15,
                    )
                    data2 = resp2.json()
                    if data2.get("code") == 0:
                        return _parse_docs_response(data2)
                except Exception:
                    pass
            return {"ok": False, "docs": [], "total": 0, "error": err_msg}

        return _parse_docs_response(data)
    except Exception as e:
        return {"ok": False, "docs": [], "total": 0, "error": str(e)}


def _parse_docs_response(data: dict) -> dict:
    """解析飞书文档搜索响应"""
    body = data.get("data") or {}
    entities = body.get("docs_entities") or []
    docs = []
    for e in entities:
        docs.append({
            "docs_token": e.get("docs_token", ""),
            "docs_type": e.get("docs_type", ""),
            "title": e.get("title", ""),
            "owner_id": e.get("owner_id", ""),
            "url": _build_doc_url(e.get("docs_token"), e.get("docs_type")),
        })
    return {
        "ok": True,
        "docs": docs,
        "total": body.get("total", len(docs)),
        "has_more": body.get("has_more", False),
    }


def _build_doc_url(docs_token: str, docs_type: str) -> str:
    """构建飞书文档打开链接"""
    if not docs_token:
        return ""
    # 飞书文档链接格式
    type_map = {
        "doc": "docx",
        "sheet": "sheets",
        "bitable": "base",
        "slide": "pptx",
        "mindnote": "mindnote",
        "file": "file",
    }
    suffix = type_map.get(docs_type, "docx")
    return f"https://open.feishu.cn/{suffix}/{docs_token}"


def format_docs_for_prompt(result: dict) -> str:
    """将检索结果格式化为可注入 prompt 的文本"""
    if not result.get("ok") or not result.get("docs"):
        if result.get("error"):
            return f"【飞书文档检索】检索失败: {result['error']}"
        return "【飞书文档检索】未找到相关文档。"
    lines = ["【飞书文档检索结果】"]
    for i, d in enumerate(result["docs"][:15], 1):
        lines.append(f"{i}. {d.get('title', '(无标题)')} ({d.get('docs_type', '')})")
        lines.append(f"   链接: {d.get('url', '')}")
    if result.get("total", 0) > 15:
        lines.append(f"... 共 {result['total']} 条结果，仅展示前 15 条")
    return "\n".join(lines)
