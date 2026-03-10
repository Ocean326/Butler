# -*- coding: utf-8 -*-
"""
飞书历史聊天记录 skill：获取、分页拉取、导出会话历史消息。

基于飞书开放平台「获取会话历史消息」API：
https://open.feishu.cn/document/server-docs/im-v1/message/list
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

# 飞书 API 常量
FEISHU_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_MESSAGE_LIST_URL = "https://open.feishu.cn/open-apis/im/v1/messages"

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


def _ensure_requests() -> None:
    if requests is None:
        raise RuntimeError("feishu-chat-history skill 需要安装 requests，请执行: pip install requests")


def _resolve_credential(
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    config_provider: Optional[Callable[[], dict]] = None,
) -> tuple[str, str]:
    """从参数 / config_provider / 环境变量解析 app_id、app_secret。"""
    if app_id and app_secret:
        return str(app_id).strip(), str(app_secret).strip()
    if config_provider:
        cfg = config_provider() or {}
        a = str((cfg.get("app_id") or "").strip())
        s = str((cfg.get("app_secret") or "").strip())
        if a and s:
            return a, s
    # 兜底从环境变量读取，便于与 run_feishu_fetch_once 等脚本复用
    env_app_id = os.getenv("FEISHU_APP_ID", "").strip()
    env_app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
    if env_app_id and env_app_secret:
        return env_app_id, env_app_secret
    raise ValueError("需要提供 app_id 与 app_secret，或可返回二者的 config_provider")


def get_tenant_token(
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    config_provider: Optional[Callable[[], dict]] = None,
    timeout: int = 12,
) -> str:
    """
    获取飞书 tenant_access_token。
    可用于本 skill 内部鉴权，也可供其他飞书 API 复用。
    """
    _ensure_requests()
    app_id, app_secret = _resolve_credential(app_id=app_id, app_secret=app_secret, config_provider=config_provider)
    resp = requests.post(
        FEISHU_TOKEN_URL,
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=timeout,
    )
    try:
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"飞书 tenant_access_token 获取失败（响应非 JSON，status={resp.status_code}）: {resp.text}"
        ) from exc
    if data.get("code") != 0:
        raise RuntimeError(
            f"飞书 tenant_access_token 获取失败: code={data.get('code')} msg={data.get('msg')} "
            f"request_id={data.get('request_id')} raw={data}"
        )
    token = data.get("tenant_access_token")
    if not token:
        raise RuntimeError("飞书 tenant_access_token 为空")
    return token


def list_messages(
    container_id: str,
    container_id_type: str = "chat",
    *,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    page_token: Optional[str] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    config_provider: Optional[Callable[[], dict]] = None,
    token: Optional[str] = None,
    timeout: int = 15,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    获取会话历史消息（单页）。
    对应飞书 API：GET /open-apis/im/v1/messages。

    :param container_id: 会话（chat）ID，如 oc_xxxxxxxxxxxx
    :param container_id_type: 固定为 "chat"（单聊+群聊）
    :param start_time: 可选，历史消息起始时间（秒级时间戳）
    :param end_time: 可选，历史消息结束时间（秒级时间戳）
    :param page_token: 可选，分页标记，首次不传
    :param page_size: 分页大小，默认 20，最大 50
    :param app_id / app_secret / config_provider: 鉴权，三选一（或传 token）
    :param token: 若已持有 tenant_access_token，可直接传入，不再请求 token
    :return: 飞书原始响应体，含 items, has_more, page_token 等
    """
    container_id = str(container_id).strip()
    if not container_id:
        raise ValueError("container_id 不能为空")
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        page_size = min(max(1, page_size), MAX_PAGE_SIZE)

    params = {
        "container_id_type": container_id_type or "chat",
        "container_id": container_id,
        "page_size": page_size,
    }
    if start_time is not None:
        params["start_time"] = str(start_time)
    if end_time is not None:
        params["end_time"] = str(end_time)
    if page_token:
        params["page_token"] = page_token

    # dry_run 模式下不实际调用飞书，仅返回将要发送的请求结构，便于本地自检与调试
    if dry_run:
        request_preview = {
            "method": "GET",
            "url": FEISHU_MESSAGE_LIST_URL,
            "headers": {
                "Authorization": "Bearer ***masked***",
                "Content-Type": "application/json",
            },
            "params": params,
        }
        return {
            "dry_run": True,
            "request": request_preview,
            "note": "dry_run 模式，仅构造请求参数，不实际访问飞书。",
        }

    _ensure_requests()
    if token is None:
        token = get_tenant_token(
            app_id=app_id,
            app_secret=app_secret,
            config_provider=config_provider,
            timeout=timeout,
        )

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.get(FEISHU_MESSAGE_LIST_URL, headers=headers, params=params, timeout=timeout)
    try:
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"飞书获取历史消息失败（响应非 JSON，status={resp.status_code}）: {resp.text}"
        ) from exc
    if data.get("code") != 0:
        raise RuntimeError(
            f"飞书获取历史消息失败: code={data.get('code')} msg={data.get('msg')} "
            f"request_id={data.get('request_id')} raw={data}"
        )
    return data.get("data") or {}


def list_all_messages(
    container_id: str,
    container_id_type: str = "chat",
    *,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: Optional[int] = None,
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    config_provider: Optional[Callable[[], dict]] = None,
    timeout: int = 15,
    dry_run: bool = False,
) -> tuple[list[dict], dict[str, Any]]:
    """
    拉取全部历史消息（自动分页），返回合并后的消息列表与摘要。

    :param max_pages: 可选，最多拉取页数，默认不限制直到 has_more=False
    :return: (items 列表, summary 字典)，summary 含 total_count, page_count 等
    """
    # dry_run：只做一次 list_messages dry_run，返回请求预览，不实际访问飞书。
    if dry_run:
        preview = list_messages(
            container_id=container_id,
            container_id_type=container_id_type,
            start_time=start_time,
            end_time=end_time,
            page_size=page_size,
            app_id=app_id,
            app_secret=app_secret,
            config_provider=config_provider,
            timeout=timeout,
            dry_run=True,
        )
        summary = {
            "total_count": 0,
            "page_count": 0,
            "container_id": container_id,
            "container_id_type": container_id_type,
            "start_time": start_time,
            "end_time": end_time,
            "dry_run": True,
            "request_preview": preview,
        }
        return [], summary

    all_items: list[dict] = []
    page_token: Optional[str] = None
    page_count = 0
    token = get_tenant_token(
        app_id=app_id,
        app_secret=app_secret,
        config_provider=config_provider,
        timeout=timeout,
    )

    while True:
        page = list_messages(
            container_id=container_id,
            container_id_type=container_id_type,
            start_time=start_time,
            end_time=end_time,
            page_token=page_token,
            page_size=page_size,
            token=token,
            timeout=timeout,
        )
        items = page.get("items") or []
        all_items.extend(items)
        page_count += 1
        if not page.get("has_more"):
            break
        page_token = page.get("page_token")
        if not page_token:
            break
        if max_pages is not None and page_count >= max_pages:
            break

    summary = {
        "total_count": len(all_items),
        "page_count": page_count,
        "container_id": container_id,
        "container_id_type": container_id_type,
        "start_time": start_time,
        "end_time": end_time,
    }
    return all_items, summary


def download_messages_to_file(
    container_id: str,
    output_path: str,
    container_id_type: str = "chat",
    *,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: Optional[int] = None,
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    config_provider: Optional[Callable[[], dict]] = None,
    timeout: int = 15,
    ensure_ascii: bool = False,
    dry_run: bool = False,
) -> str:
    """
    将指定会话的历史消息拉取并写入 JSON 文件。
    自动创建父目录；文件内容为 {"items": [...], "summary": {...}}。

    :param output_path: 输出文件路径，如 ./工作区/feishu_chat_history/chat_oc_xxx.json
    :return: 写入的绝对路径
    """
    all_items, summary = list_all_messages(
        container_id=container_id,
        container_id_type=container_id_type,
        start_time=start_time,
        end_time=end_time,
        page_size=page_size,
        max_pages=max_pages,
        app_id=app_id,
        app_secret=app_secret,
        config_provider=config_provider,
        timeout=timeout,
        dry_run=dry_run,
    )
    out = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    payload = {"items": all_items, "summary": summary}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=ensure_ascii, indent=2)
    return out
