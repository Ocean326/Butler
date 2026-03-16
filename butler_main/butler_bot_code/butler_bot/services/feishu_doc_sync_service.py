# -*- coding: utf-8 -*-
"""
飞书云文档同步：创建/更新云文档，并把文档链接发到 IM。

用途：
- 对话侧：用户要「发云文档链接」时，创建文档并发链接。
- 心跳侧：每轮 plan 后，将任务摘要同步到配置的「任务云文档」（真源仍为 heartbeat_tasks/*.md）。

实现依据：agents/local_memory/飞书云文档发送与心跳任务云文档_方案.md
"""

from __future__ import annotations

import json
import time
from typing import Any


# 飞书 doc v2 创建文档
def _get_tenant_token(cfg: dict, requests_module) -> str | None:
    app_id = str((cfg or {}).get("app_id") or "").strip()
    app_secret = str((cfg or {}).get("app_secret") or "").strip()
    if not app_id or not app_secret:
        return None
    try:
        r = requests_module.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=12,
        )
        data = r.json()
        if data.get("code") == 0:
            return data.get("tenant_access_token")
    except Exception:
        pass
    return None


def create_doc(
    cfg: dict,
    *,
    folder_token: str | None = None,
    title: str | None = None,
    requests_module,
) -> dict | None:
    """
    创建飞书云文档（doc v2）。
    返回 {"doc_token": str, "url": str, "revision": int} 或 None。
    """
    token = _get_tenant_token(cfg, requests_module)
    if not token:
        return None
    body: dict[str, Any] = {}
    if folder_token:
        body["FolderToken"] = folder_token
    # 若传 title 或初始内容，用 doc v2 文档结构（见飞书开放平台文档数据结构参考）
    if title:
        title_text = (title or "")[:200]
        body["Content"] = json.dumps({
            "title": {"elements": [{"type": "textRun", "textRun": {"text": title_text, "style": {}}}]},
            "body": {"blocks": [{"type": "paragraph", "paragraph": {"elements": [{"type": "textRun", "textRun": {"text": "(由 Butler 同步更新)", "style": {}}}]}}]},
        }, ensure_ascii=False)
    try:
        r = requests_module.post(
            "https://open.feishu.cn/open-apis/doc/v2/create",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
            json=body if body else None,
            timeout=15,
        )
        data = r.json()
        if data.get("code") == 0:
            d = data.get("data") or {}
            return {
                "doc_token": d.get("token") or d.get("doc_token"),
                "url": d.get("url"),
                "revision": int(d.get("revision", 0)),
            }
    except Exception as e:
        print(f"[feishu_doc_sync] create_doc 异常: {e}", flush=True)
    return None


def get_doc_content(
    cfg: dict,
    doc_token: str,
    *,
    requests_module,
) -> dict | None:
    """
    获取文档内容与当前 revision。
    返回 {"revision": int, "content": ...} 或 None。
    """
    token = _get_tenant_token(cfg, requests_module)
    if not token or not doc_token:
        return None
    try:
        r = requests_module.get(
            f"https://open.feishu.cn/open-apis/doc/v2/{doc_token}/content",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        data = r.json()
        if data.get("code") == 0:
            d = data.get("data") or {}
            return {
                "revision": int(d.get("revision", 0)),
                "content": d.get("content"),
            }
    except Exception as e:
        print(f"[feishu_doc_sync] get_doc_content 异常: {e}", flush=True)
    return None


def update_doc_raw_content(
    cfg: dict,
    doc_token: str,
    markdown_or_plain_text: str,
    *,
    requests_module,
) -> bool:
    """
    用飞书 doc v2 batch_update 将文档内容替换为给定文本。
    先获取当前 revision，再发 DeleteContentRange 删全文 + InsertBlocks 插入新段落。
    若 doc 接口不支持或格式复杂，本函数可能失败，届时可退化为「仅创建、不更新」。
    """
    token = _get_tenant_token(cfg, requests_module)
    if not token or not doc_token:
        return False
    info = get_doc_content(cfg, doc_token, requests_module=requests_module)
    if not info:
        # 可能是新文档，revision 常为 0
        revision = 0
    else:
        revision = info["revision"]

    # 飞书 doc v2 batch_update：在文档开头（index=0）插入新段落，实现「本轮摘要」追加
    # 若需全文覆盖，需先 get content 解析 block 的 startIndex/endIndex 再 DeleteContentRange，此处简化为追加
    text = (markdown_or_plain_text or "").strip() or "(无内容)"
    if len(text) > 50000:
        text = text[:50000] + "\n...(已截断)"

    # doc v2 block 结构（与 create 的 body.blocks 一致）
    blocks = [{
        "type": "paragraph",
        "paragraph": {
            "elements": [{"type": "textRun", "textRun": {"text": text, "style": {}}}],
        },
    }]
    requests_list: list[dict] = [{
        "requestType": "insertBlocksRequest",
        "insertBlocksRequest": {
            "location": {"index": 0},
            "blocks": blocks,
        },
    }]
    body = {"Revision": revision, "Requests": requests_list}
    try:
        r = requests_module.post(
            f"https://open.feishu.cn/open-apis/doc/v2/{doc_token}/batch_update",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
            json=body,
            timeout=15,
        )
        data = r.json()
        if data.get("code") == 0:
            return True
        print(f"[feishu_doc_sync] batch_update 失败: {data}", flush=True)
    except Exception as e:
        print(f"[feishu_doc_sync] batch_update 异常: {e}", flush=True)
    return False


def send_doc_link_to_im(
    cfg: dict,
    doc_url: str,
    doc_title: str,
    *,
    receive_id: str,
    receive_id_type: str = "open_id",
    heartbeat_cfg: dict | None = None,
    message_delivery_service,
) -> bool:
    """
    把云文档链接以私聊消息形式发给用户。
    """
    if not doc_url or not receive_id:
        return False
    text = f"【云文档】{doc_title or 'Butler 任务摘要'}\n{doc_url}"
    return message_delivery_service.send_private_message(
        cfg,
        text,
        receive_id=receive_id,
        receive_id_type=receive_id_type,
        fallback_to_startup_target=False,
        heartbeat_cfg=heartbeat_cfg or cfg,
    )


def sync_heartbeat_task_doc(
    cfg: dict,
    heartbeat_cfg: dict,
    plan: dict,
    execution_summary: str,
    *,
    requests_module,
) -> bool:
    """
    心跳每轮 plan 后：将任务摘要同步到配置的「任务云文档」。
    配置项：heartbeat_cfg 中的 task_doc_token（已有文档 token）或 task_doc_folder_token（在目录下创建/更新文档）。
    真源仍为 heartbeat_tasks/*.md，云文档仅为展示出口。
    """
    task_doc_token = str((heartbeat_cfg or {}).get("task_doc_token") or "").strip()
    task_doc_folder_token = str((heartbeat_cfg or {}).get("task_doc_folder_token") or "").strip()
    if not task_doc_token and not task_doc_folder_token:
        return False
    app_id = str((heartbeat_cfg or cfg or {}).get("app_id") or (cfg or {}).get("app_id") or "").strip()
    app_secret = str((heartbeat_cfg or cfg or {}).get("app_secret") or (cfg or {}).get("app_secret") or "").strip()
    if not app_id or not app_secret:
        print("[feishu_doc_sync] 心跳任务云文档：缺少 app_id/app_secret", flush=True)
        return False
    feishu_cfg = {"app_id": app_id, "app_secret": app_secret}

    # 构建摘要文本
    lines = [
        "# Butler 心跳任务摘要",
        "",
        f"更新时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}",
        "",
        "## 本轮规划",
        str(plan.get("reason") or "(无)"),
        "",
        "## 模式与说明",
        str(plan.get("chosen_mode") or "(无)"),
        str(plan.get("user_message") or "").strip() or "(无)",
        "",
        "## 执行摘要",
        (execution_summary or "").strip() or "(无)",
    ]
    summary_text = "\n".join(lines)

    doc_token = task_doc_token
    if not doc_token and task_doc_folder_token:
        # 首次在目录下创建文档（后续可缓存 doc_token 到 state 文件，此处简化为每次创建新文档会重复创建，仅做最小闭环则要求用户配 task_doc_token）
        created = create_doc(
            feishu_cfg,
            folder_token=task_doc_folder_token,
            title="Butler 心跳任务摘要",
            requests_module=requests_module,
        )
        if created:
            doc_token = created.get("doc_token")
            # 可选：把 doc_token 写回配置或 state，下次用同一文档更新
        if not doc_token:
            return False
        # 新文档已有空内容，直接插入
        return update_doc_raw_content(feishu_cfg, doc_token, summary_text, requests_module=requests_module)

    if doc_token:
        return update_doc_raw_content(feishu_cfg, doc_token, summary_text, requests_module=requests_module)
    return False
