# -*- coding: utf-8 -*-
"""
飞书云文档读取 skill：从飞书云文档获取纯文本、富文本块、基本信息。

基于飞书开放平台 docx/v1 API：
- 获取文档纯文本：GET /docx/v1/documents/:document_id/raw_content
- 获取文档所有块：GET /docx/v1/documents/:document_id/blocks
- 获取文档基本信息：GET /docx/v1/documents/:document_id
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import unquote

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

# ── 飞书 API 常量 ──
FEISHU_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_DOCX_BASE = "https://open.feishu.cn/open-apis/docx/v1/documents"

# 从 URL 中提取 document_id 的正则
# 支持：https://xxx.feishu.cn/docx/AbCdEfGhIjKlMnOpQrStUvWxYz1
#        https://xxx.feishu.cn/wiki/AbCdEfGhIjKlMnOpQrStUvWxYz1
_DOC_URL_RE = re.compile(
    r"(?:https?://)?(?:[^/\s]+\.)?(?:feishu\.cn|larksuite\.com)/(?:docx|wiki|docs)/([A-Za-z0-9_-]{16,})",
    re.IGNORECASE,
)


# ── 凭证解析（复用 feishu_chat_history 同一模式） ──

def _ensure_requests() -> None:
    if requests is None:
        raise RuntimeError("feishu-doc-read skill 需要安装 requests，请执行: pip install requests")


def _find_butler_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "butler_main" / "butler_bot_code").exists():
            return parent
    return current.parents[-1]


def _load_butler_app_credential_from_config() -> Optional[tuple[str, str]]:
    try:
        root = _find_butler_root()
        cfg_path = root / "butler_main" / "butler_bot_code" / "configs" / "butler_bot.json"
        if not cfg_path.is_file():
            return None
        with cfg_path.open("r", encoding="utf-8") as f:
            cfg = json.load(f) or {}
        app_id = str((cfg.get("app_id") or "").strip())
        app_secret = str((cfg.get("app_secret") or "").strip())
        if app_id and app_secret:
            return app_id, app_secret
    except Exception:
        return None
    return None


def _resolve_credential(
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    config_provider: Optional[Callable[[], dict]] = None,
) -> tuple[str, str]:
    if app_id and app_secret:
        return str(app_id).strip(), str(app_secret).strip()
    if config_provider:
        cfg = config_provider() or {}
        a = str((cfg.get("app_id") or "").strip())
        s = str((cfg.get("app_secret") or "").strip())
        if a and s:
            return a, s
    env_app_id = os.getenv("FEISHU_APP_ID", "").strip()
    env_app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
    if env_app_id and env_app_secret:
        return env_app_id, env_app_secret
    cfg_pair = _load_butler_app_credential_from_config()
    if cfg_pair:
        return cfg_pair
    raise ValueError("需要提供 app_id 与 app_secret，或可返回二者的 config_provider")


def get_tenant_token(
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    config_provider: Optional[Callable[[], dict]] = None,
    timeout: int = 12,
) -> str:
    _ensure_requests()
    app_id, app_secret = _resolve_credential(app_id=app_id, app_secret=app_secret, config_provider=config_provider)
    resp = requests.post(
        FEISHU_TOKEN_URL,
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=timeout,
    )
    try:
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(
            f"飞书 tenant_access_token 获取失败（响应非 JSON，status={resp.status_code}）: {resp.text}"
        ) from exc
    if data.get("code") != 0:
        raise RuntimeError(
            f"飞书 tenant_access_token 获取失败: code={data.get('code')} msg={data.get('msg')} "
            f"request_id={data.get('request_id')}"
        )
    token = data.get("tenant_access_token")
    if not token:
        raise RuntimeError("飞书 tenant_access_token 为空")
    return token


# ── URL / ID 解析 ──

def parse_document_id(url_or_id: str) -> str:
    """
    从飞书文档 URL 或纯 document_id 中提取 document_id。
    支持格式：
    - 完整 URL：https://xxx.feishu.cn/docx/QvXLdALtMoJcZrxL34vcsI1ynvT
    - 带密码参数的 URL
    - 纯 ID：QvXLdALtMoJcZrxL34vcsI1ynvT
    """
    text = unquote(str(url_or_id or "").strip())
    if not text:
        raise ValueError("url_or_id 不能为空")
    m = _DOC_URL_RE.search(text)
    if m:
        return m.group(1)
    text = text.split("?")[0].split("#")[0].rstrip("/")
    segments = text.split("/")
    candidate = segments[-1]
    if len(candidate) >= 16 and re.match(r'^[A-Za-z0-9_-]+$', candidate):
        return candidate
    raise ValueError(f"无法从输入中解析 document_id: {url_or_id}")


# ── 核心 API 封装 ──

def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def get_document_meta(
    document_id: str,
    *,
    token: Optional[str] = None,
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    config_provider: Optional[Callable[[], dict]] = None,
    timeout: int = 15,
) -> dict[str, Any]:
    """
    获取文档基本信息（标题、版本号等）。
    API: GET /docx/v1/documents/:document_id
    """
    _ensure_requests()
    if token is None:
        token = get_tenant_token(app_id=app_id, app_secret=app_secret, config_provider=config_provider, timeout=timeout)
    url = f"{FEISHU_DOCX_BASE}/{document_id}"
    resp = requests.get(url, headers=_auth_headers(token), timeout=timeout)
    data = _parse_response(resp, "获取文档基本信息")
    return data.get("document") or data


def get_document_raw_content(
    document_id: str,
    *,
    lang: int = 0,
    token: Optional[str] = None,
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    config_provider: Optional[Callable[[], dict]] = None,
    timeout: int = 15,
) -> str:
    """
    获取文档纯文本内容。
    API: GET /docx/v1/documents/:document_id/raw_content
    :param lang: @用户的语言，0=默认名称 1=英文
    :return: 纯文本字符串
    """
    _ensure_requests()
    if token is None:
        token = get_tenant_token(app_id=app_id, app_secret=app_secret, config_provider=config_provider, timeout=timeout)
    url = f"{FEISHU_DOCX_BASE}/{document_id}/raw_content"
    params = {"lang": lang}
    resp = requests.get(url, headers=_auth_headers(token), params=params, timeout=timeout)
    data = _parse_response(resp, "获取文档纯文本")
    return data.get("content") or ""


def get_document_blocks(
    document_id: str,
    *,
    page_size: int = 500,
    document_revision_id: int = -1,
    token: Optional[str] = None,
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    config_provider: Optional[Callable[[], dict]] = None,
    timeout: int = 15,
) -> list[dict[str, Any]]:
    """
    获取文档所有块（自动分页），返回 block 列表。
    API: GET /docx/v1/documents/:document_id/blocks
    """
    _ensure_requests()
    if token is None:
        token = get_tenant_token(app_id=app_id, app_secret=app_secret, config_provider=config_provider, timeout=timeout)
    url = f"{FEISHU_DOCX_BASE}/{document_id}/blocks"
    all_blocks: list[dict] = []
    page_token: Optional[str] = None

    while True:
        params: dict[str, Any] = {
            "page_size": min(page_size, 500),
            "document_revision_id": document_revision_id,
        }
        if page_token:
            params["page_token"] = page_token
        resp = requests.get(url, headers=_auth_headers(token), params=params, timeout=timeout)
        data = _parse_response(resp, "获取文档块")
        items = data.get("items") or []
        all_blocks.extend(items)
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
        if not page_token:
            break

    return all_blocks


def _parse_response(resp: Any, action: str) -> dict[str, Any]:
    try:
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(
            f"飞书{action}失败（响应非 JSON，status={resp.status_code}）: {resp.text}"
        ) from exc
    if data.get("code") != 0:
        raise RuntimeError(
            f"飞书{action}失败: code={data.get('code')} msg={data.get('msg')} "
            f"request_id={data.get('request_id')} status={resp.status_code} raw={data}"
        )
    return data.get("data") or {}


def _normalize_mode(mode: str) -> str:
    text = str(mode or "").strip().lower()
    alias = {
        "md": "markdown",
        "block": "blocks",
    }
    normalized = alias.get(text, text or "raw")
    if normalized not in {"raw", "markdown", "blocks"}:
        raise ValueError(f"不支持的 mode={mode}，仅支持 raw / markdown / blocks")
    return normalized


# ── Block → Markdown 转换 ──

# block_type → heading level 映射
_HEADING_MAP = {3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 8: 6, 9: 7, 10: 8, 11: 9}

def _extract_text_from_elements(elements: list[dict]) -> str:
    """从 text_run / mention_user / mention_doc / equation 等 elements 中提取文本。"""
    parts: list[str] = []
    for elem in elements:
        if "text_run" in elem:
            tr = elem["text_run"]
            content = tr.get("content") or ""
            style = tr.get("text_element_style") or {}
            if style.get("bold"):
                content = f"**{content}**"
            if style.get("italic"):
                content = f"*{content}*"
            if style.get("strikethrough"):
                content = f"~~{content}~~"
            if style.get("inline_code"):
                content = f"`{content}`"
            link = style.get("link") or {}
            if link.get("url"):
                link_url = unquote(link["url"])
                content = f"[{content}]({link_url})"
            parts.append(content)
        elif "mention_user" in elem:
            parts.append("@user")
        elif "mention_doc" in elem:
            md = elem["mention_doc"]
            title = md.get("title") or "文档"
            doc_url = md.get("url") or ""
            if doc_url:
                doc_url = unquote(doc_url)
                parts.append(f"[@{title}]({doc_url})")
            else:
                parts.append(f"@{title}")
        elif "equation" in elem:
            eq = elem["equation"]
            parts.append(f"$${eq.get('content', '')}$$")
    return "".join(parts)


def blocks_to_markdown(blocks: list[dict]) -> str:
    """
    将飞书文档 block 列表转换为可读 Markdown 文本。
    支持：标题、文本、列表、代码块、引用、待办、分割线、图片占位等。
    """
    lines: list[str] = []

    for block in blocks:
        bt = block.get("block_type")
        if bt == 1:
            page = block.get("page") or {}
            elements = page.get("elements") or []
            if elements:
                title_text = _extract_text_from_elements(elements)
                if title_text.strip():
                    lines.append(f"# {title_text.strip()}")
                    lines.append("")
            continue

        text_key = None
        if bt == 2:
            text_key = "text"
        elif bt in _HEADING_MAP:
            text_key = {3: "heading1", 4: "heading2", 5: "heading3",
                        6: "heading4", 7: "heading5", 8: "heading6",
                        9: "heading7", 10: "heading8", 11: "heading9"}.get(bt)
        elif bt == 12:
            text_key = "bullet"
        elif bt == 13:
            text_key = "ordered"
        elif bt == 14:
            text_key = "code"
        elif bt == 15:
            text_key = "quote"
        elif bt == 17:
            text_key = "todo"

        if text_key and text_key in block:
            text_block = block[text_key]
            elements = text_block.get("elements") or []
            text = _extract_text_from_elements(elements)
            style = text_block.get("style") or {}

            if bt in _HEADING_MAP:
                level = _HEADING_MAP[bt]
                prefix = "#" * min(level, 6)
                lines.append(f"{prefix} {text}")
                lines.append("")
            elif bt == 12:  # bullet
                lines.append(f"- {text}")
            elif bt == 13:  # ordered
                lines.append(f"1. {text}")
            elif bt == 14:  # code
                lang_code = style.get("language", 1)
                lines.append("```")
                lines.append(text)
                lines.append("```")
                lines.append("")
            elif bt == 15:  # quote
                for line in text.split("\n"):
                    lines.append(f"> {line}")
                lines.append("")
            elif bt == 17:  # todo
                done = style.get("done", False)
                mark = "x" if done else " "
                lines.append(f"- [{mark}] {text}")
            else:
                lines.append(text)
                lines.append("")
            continue

        if bt == 22:  # 分割线
            lines.append("---")
            lines.append("")
        elif bt == 27:  # 图片
            lines.append("[图片]")
            lines.append("")
        elif bt == 23:  # 文件
            lines.append("[文件附件]")
            lines.append("")
        elif bt == 18:  # 多维表格
            lines.append("[多维表格]")
            lines.append("")
        elif bt == 31:  # 表格
            lines.append("[表格]")
            lines.append("")

    return "\n".join(lines)


# ── 高层封装 ──

def read_feishu_doc(
    url_or_id: str,
    *,
    mode: str = "raw",
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    config_provider: Optional[Callable[[], dict]] = None,
    timeout: int = 15,
) -> dict[str, Any]:
    """
    一站式读取飞书云文档。

    :param url_or_id: 飞书文档 URL 或 document_id
    :param mode: "raw" 返回纯文本(默认)，"markdown" 返回 block 转 md，"blocks" 返回原始 block JSON
    :return: {
        "document_id": str,
        "title": str,
        "revision_id": int,
        "content": str,          # mode=raw/markdown 时
        "blocks": list[dict],    # mode=blocks 时
    }
    """
    mode = _normalize_mode(mode)
    doc_id = parse_document_id(url_or_id)
    token = get_tenant_token(app_id=app_id, app_secret=app_secret, config_provider=config_provider, timeout=timeout)

    meta = get_document_meta(doc_id, token=token, timeout=timeout)
    title = meta.get("title") or ""
    try:
        revision_id = int(meta.get("revision_id") or meta.get("document", {}).get("revision_id") or -1)
    except (TypeError, ValueError):
        revision_id = -1

    result: dict[str, Any] = {
        "document_id": doc_id,
        "title": title,
        "revision_id": revision_id,
    }

    if mode == "blocks":
        blocks = get_document_blocks(doc_id, token=token, timeout=timeout)
        result["blocks"] = blocks
    elif mode == "markdown":
        blocks = get_document_blocks(doc_id, token=token, timeout=timeout)
        result["content"] = blocks_to_markdown(blocks)
        result["blocks"] = blocks
    else:  # raw
        result["content"] = get_document_raw_content(doc_id, token=token, timeout=timeout)

    return result


def download_doc_to_file(
    url_or_id: str,
    output_path: str,
    *,
    mode: str = "markdown",
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    config_provider: Optional[Callable[[], dict]] = None,
    timeout: int = 15,
) -> str:
    """
    读取飞书云文档并保存到本地文件。

    :param output_path: 输出文件路径（.md / .txt / .json）
    :param mode: "raw" / "markdown" / "blocks"
    :return: 写入的绝对路径
    """
    mode = _normalize_mode(mode)
    doc = read_feishu_doc(
        url_or_id, mode=mode,
        app_id=app_id, app_secret=app_secret,
        config_provider=config_provider, timeout=timeout,
    )
    out = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    if mode == "blocks":
        with open(out, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
    else:
        header = f"# {doc['title']}\n\n" if doc.get("title") else ""
        content = doc.get("content") or ""
        body = content if mode == "markdown" else (header + content)
        with open(out, "w", encoding="utf-8") as f:
            f.write(body)

    return out
