# -*- coding: utf-8 -*-
"""
【Message 模块】飞书机器人消息层

职责：飞书长连接、消息解析、回复、去重、图片下载/上传等。
与 memory_manager（记忆层）分离，各 xx-agent 组合使用。

各 xx-agent 仅需实现 run_agent(prompt, stream_callback?, image_paths?) -> str 并调用 run_feishu_bot。
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import re
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

from agents_os.contracts import OutputBundle
from butler_main.agents_os.runtime import sanitize_markdown_structure
from butler_main.chat.feishu_bot.api import FeishuApiClient
from butler_main.chat.feishu_bot.dispatcher import (
    build_card_action_response as _dispatcher_build_card_action_response,
    build_chat_feishu_event_dispatcher,
)
from butler_main.chat.feishu_bot.interaction import (
    build_card_action_prompt as _interaction_build_card_action_prompt,
    build_invocation_metadata_from_message as _interaction_build_invocation_metadata_from_message,
    build_message_receive_payload as _interaction_build_message_receive_payload,
    extract_card_action_payload as _interaction_extract_card_action_payload,
    extract_message_image_keys as _interaction_extract_message_image_keys,
    extract_message_text as _interaction_extract_message_text,
)
from butler_main.chat.feishu_bot.message_delivery import MessageDeliveryService
from butler_main.chat.feishu_bot.replying import FeishuReplyService
from butler_main.chat.feishu_bot.rendering import (
    markdown_to_feishu_post as _render_markdown_to_feishu_post,
    markdown_to_interactive_card as _render_markdown_to_interactive_card,
)
from butler_main.chat.pathing import COMPANY_HOME_REL, resolve_butler_root
from butler_main.repo_layout import HOST_RUNTIME_REL, LEGACY_CHAT_REL, PRODUCT_CHAT_REL, resolve_repo_path
from butler_main.runtime_os.agent_runtime import install_print_hook, set_runtime_log_config

# 确保日志 / 控制台输出 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
if not sys.stdout.isatty():
    try:
        sys.stdout.buffer.write(b"\xef\xbb\xbf")
        sys.stdout.flush()
    except Exception:
        pass

try:
    import requests
    import lark_oapi as lark
    from lark_oapi import ws
except ImportError:
    print("请先安装: pip install lark-oapi requests -U")
    sys.exit(1)

_MESSAGE_DELIVERY_SERVICE = MessageDeliveryService(requests_module=requests)
CONFIG = {}
_config_path_for_reload: str | None = None  # 用于热加载的配置文件路径
_config_last_reload = 0.0
_config_reload_interval = 5  # 秒，避免过于频繁读盘
_message_dedup = {}
_message_dedup_lock = threading.Lock()
_reply_dedup = {}
_reply_dedup_lock = threading.Lock()
_recent_feishu_sessions = {}
_recent_feishu_sessions_lock = threading.Lock()
_MESSAGE_DEDUP_TTL = 15 * 60
_RECENT_FEISHU_SESSION_MAX_ITEMS = 8
_RECENT_FEISHU_BACKFILL_MESSAGE_LIMIT = 20
ENABLE_TYPING_HINT = False
HINT_DELAY = 15
PROCESSING_RECEIPT_DELAY_SECONDS = 4.0
STREAM_PLACEHOLDER_TEXT = "正在思考…"
# Install once early; actual level/config path is set after loading config.
install_print_hook(default_level=os.environ.get("BUTLER_LOG_LEVEL", "info"))


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    workspace_root = loaded.get("workspace_root")
    if workspace_root:
        loaded["workspace_root"] = str(resolve_butler_root(workspace_root))
    else:
        loaded["workspace_root"] = str(resolve_butler_root(__file__))
    return loaded


def get_config() -> dict:
    """返回当前配置；若已设置配置文件路径则按间隔从磁盘重载（热加载）。"""
    global CONFIG, _config_path_for_reload, _config_last_reload
    path = _config_path_for_reload or (CONFIG.get("__config_path") if isinstance(CONFIG.get("__config_path"), str) else None)
    if path and os.path.isfile(path):
        now = time.time()
        if (now - _config_last_reload) >= _config_reload_interval:
            try:
                loaded = load_config(path)
                CONFIG.clear()
                CONFIG.update(loaded)
                CONFIG["__config_path"] = os.path.abspath(path)
                _sync_feishu_runtime_state(CONFIG)
                _config_last_reload = now
            except Exception:
                pass
    if CONFIG.get("workspace_root"):
        CONFIG["workspace_root"] = str(resolve_butler_root(CONFIG.get("workspace_root")))
    return CONFIG


_API_CLIENT = FeishuApiClient(config_getter=get_config, requests_module=requests)
_REPLY_SERVICE = FeishuReplyService(
    api_client=_API_CLIENT,
    config_getter=get_config,
    markdown_to_interactive_card=_render_markdown_to_interactive_card,
    markdown_to_feishu_post=_render_markdown_to_feishu_post,
)


def _candidate_config_paths(default_config_name: str) -> list[str]:
    config_name = f"{default_config_name}.json"
    transport_file = Path(__file__).resolve()
    root = resolve_butler_root(transport_file)
    for candidate in (transport_file.parent, *transport_file.parents):
        if (candidate / "butler_main").is_dir():
            root = resolve_butler_root(candidate)
            break
        if (candidate / "chat" / "configs").is_dir() or (candidate / "butler_bot_code" / "configs").is_dir():
            root = candidate
            break
    if not (root / "butler_main").is_dir():
        return [
            str((root / "chat" / "configs" / config_name).resolve()),
            str((root / "butler_bot_code" / "configs" / config_name).resolve()),
        ]
    chat_root = resolve_repo_path(
        root,
        canonical_rel=PRODUCT_CHAT_REL,
        compat_rel=LEGACY_CHAT_REL,
        require_existing=True,
    )
    return [
        str((chat_root / "configs" / config_name).resolve()),
        str((root / HOST_RUNTIME_REL / "configs" / config_name).resolve()),
    ]


def _resolve_default_config_path(default_config_name: str) -> str:
    candidates = _candidate_config_paths(default_config_name)
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0]


def _sync_feishu_runtime_state(config: dict | None = None) -> None:
    _API_CLIENT.sync_runtime_config(config or get_config())


def _normalize_feishu_session_scope_id(raw_scope_id: str) -> str:
    scope_id = str(raw_scope_id or "").strip()
    if not scope_id:
        return ""
    if scope_id.lower().startswith("feishu:"):
        return scope_id
    return f"feishu:{scope_id}"


def _register_recent_feishu_session(metadata: dict | None) -> None:
    normalized = dict(metadata or {})
    chat_id = str(normalized.get("feishu.chat_id") or normalized.get("open_chat_id") or "").strip()
    raw_scope_id = str(
        normalized.get("session_scope_id")
        or normalized.get("feishu.raw_session_ref")
        or normalized.get("session_id")
        or chat_id
        or ""
    ).strip()
    session_scope_id = _normalize_feishu_session_scope_id(raw_scope_id)
    if not chat_id or not session_scope_id:
        return
    record = {
        "session_scope_id": session_scope_id,
        "chat_id": chat_id,
        "message_id": str(normalized.get("feishu.message_id") or normalized.get("message_id") or "").strip(),
        "actor_id": str(normalized.get("actor_id") or normalized.get("feishu.receive_id") or "").strip(),
        "updated_at": time.time(),
    }
    with _recent_feishu_sessions_lock:
        _recent_feishu_sessions[session_scope_id] = record
        ordered = sorted(
            _recent_feishu_sessions.values(),
            key=lambda item: float(item.get("updated_at") or 0.0),
        )
        while len(ordered) > _RECENT_FEISHU_SESSION_MAX_ITEMS:
            dropped = ordered.pop(0)
            _recent_feishu_sessions.pop(str(dropped.get("session_scope_id") or "").strip(), None)


def _list_recent_feishu_sessions() -> list[dict]:
    with _recent_feishu_sessions_lock:
        sessions = [dict(item) for item in _recent_feishu_sessions.values() if isinstance(item, dict)]
    sessions.sort(key=lambda item: float(item.get("updated_at") or 0.0), reverse=True)
    return sessions


def _run_feishu_preflight(*, auth_probe: bool = False) -> tuple[bool, str]:
    result = _API_CLIENT.run_preflight(auth_probe=auth_probe)
    ok = bool(result.get("ok"))
    missing = list(result.get("missing") or [])
    workspace_root = str(result.get("workspace_root") or "").strip() or "."
    app_id_preview = str(result.get("app_id_preview") or "").strip() or "-"
    if ok:
        token_preview = str(result.get("token_preview") or "").strip()
        detail = f"workspace_root={workspace_root} app_id={app_id_preview}"
        if token_preview:
            detail += f" token={token_preview}"
        return True, detail
    error = str(result.get("error") or "").strip()
    if missing:
        error = error or f"missing config keys: {', '.join(missing)}"
    return False, error or "unknown feishu preflight error"


def get_tenant_access_token() -> str:
    return _API_CLIENT.get_tenant_access_token()


def _claim_message(message_id: str) -> bool:
    now = time.time()
    with _message_dedup_lock:
        expired = [k for k, ts in _message_dedup.items() if now - ts > _MESSAGE_DEDUP_TTL]
        for k in expired:
            _message_dedup.pop(k, None)
        if message_id in _message_dedup:
            return False
        _message_dedup[message_id] = now
        return True


def _normalize_reply_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _preview_text(text: str, limit: int = 120) -> str:
    normalized = _normalize_reply_text(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "..."


def _normalize_feishu_text(text: str) -> str:
    return sanitize_markdown_structure(text)


def _collapse_duplicate_reply_blocks(text: str) -> str:
    normalized = _normalize_feishu_text(text)
    if not normalized:
        return ""

    blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
    if len(blocks) <= 1:
        return normalized

    deduped: list[str] = []
    previous_key = ""
    for block in blocks:
        current_key = _normalize_reply_text(block)
        if current_key and current_key == previous_key:
            continue
        deduped.append(block)
        previous_key = current_key
    return "\n\n".join(deduped).strip()


def _extract_incremental_stream_entry(previous_snapshot: str, current_snapshot: str) -> str:
    previous = _collapse_duplicate_reply_blocks(previous_snapshot).strip()
    current = _collapse_duplicate_reply_blocks(current_snapshot).strip()
    if not current:
        return ""
    if not previous:
        return current
    previous_lines = [line.rstrip() for line in previous.splitlines()]
    current_lines = [line.rstrip() for line in current.splitlines()]
    if current.startswith(previous) and len(current_lines) > len(previous_lines):
        delta = current[len(previous):].strip()
        return delta or current
    common_prefix = 0
    while common_prefix < min(len(previous_lines), len(current_lines)) and previous_lines[common_prefix] == current_lines[common_prefix]:
        common_prefix += 1
    if common_prefix > 0:
        delta = "\n".join(current_lines[common_prefix:]).strip()
        if delta:
            return delta
    return current


def _append_stream_process_entry(entries: list[str], text: str) -> list[str]:
    normalized_text = _collapse_duplicate_reply_blocks(text).strip()
    if not normalized_text:
        return list(entries)
    updated_entries = list(entries)
    if updated_entries and _normalize_reply_text(updated_entries[-1]) == _normalize_reply_text(normalized_text):
        return updated_entries
    updated_entries.append(normalized_text)
    return updated_entries


def _render_stream_process_text(entries: list[str]) -> str:
    if not entries:
        return STREAM_PLACEHOLDER_TEXT
    sections = ["## 过程"]
    for entry in entries:
        sections.append(entry.strip())
    return "\n\n".join(section for section in sections if str(section or "").strip()).strip()


def _extract_section_title(text: str) -> str:
    first_line = ((text or "").strip().splitlines() or [""])[0].strip()
    if first_line.startswith("##"):
        return re.sub(r"\s+", " ", first_line.lstrip("#").strip()).lower()
    return ""


def _claim_reply(message_id: str, text: str, channel: str) -> bool:
    now = time.time()
    normalized = _normalize_reply_text(text)
    if not normalized:
        return False
    dedup_key = f"{message_id}|{channel}|{normalized}"
    with _reply_dedup_lock:
        expired = [k for k, ts in _reply_dedup.items() if now - ts > _MESSAGE_DEDUP_TTL]
        for k in expired:
            _reply_dedup.pop(k, None)
        if dedup_key in _reply_dedup:
            return False
        _reply_dedup[dedup_key] = now
        return True


def _send_deduped_reply(message_id: str, text: str, use_interactive: bool = True, channel: str = "text") -> bool:
    if not _claim_reply(message_id, text, channel):
        preview = _preview_text(text, 80)
        print(f"[发送去重] 跳过重复{channel}: {message_id} | {preview}", flush=True)
        return False
    preview = _preview_text(text, 80)
    print(f"[发送] {channel}: {message_id} | {preview}", flush=True)
    # 最终回复默认挂快捷动作，避免卡片交互只存在于一条未实际走到的分支。
    include_card_actions = channel in {"card_action"}
    return reply_message(
        message_id,
        text,
        use_interactive=use_interactive,
        include_card_actions=include_card_actions,
    )


def download_message_images(message_id: str, image_keys: list[str], workspace: str) -> list[str]:
    del workspace
    return _API_CLIENT.download_message_images(message_id, image_keys)


def _markdown_to_feishu_post(md: str) -> dict:
    return _render_markdown_to_feishu_post(md)


def _markdown_to_interactive_card(md: str, include_quick_actions: bool = False) -> dict:
    return _render_markdown_to_interactive_card(md, include_quick_actions=include_quick_actions)


def _extract_card_action_payload(data) -> dict:
    return _interaction_extract_card_action_payload(data)


def _build_card_action_prompt(payload: dict) -> str:
    return _interaction_build_card_action_prompt(payload)


def _build_card_action_response(message: str, toast_type: str = "info"):
    return _dispatcher_build_card_action_response(message, toast_type=toast_type)


def _extract_markdown_image_refs(md: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", md or "") if m.group(1).strip()]


def _strip_markdown_images(md: str) -> str:
    return re.sub(r"!\[[^\]]*\]\(([^)]+)\)", "", md or "")


def _resolve_image_ref_to_local_path(image_ref: str) -> str | None:
    return _REPLY_SERVICE.resolve_image_ref_to_local_path(image_ref)


def upload_image(file_path: str) -> str | None:
    return _API_CLIENT.upload_image(file_path)


def reply_image(message_id: str, image_key: str) -> bool:
    return _API_CLIENT.reply_image(message_id, image_key)


def upload_file(file_path: str) -> str | None:
    return _API_CLIENT.upload_file(file_path)


def reply_file(message_id: str, file_key: str) -> bool:
    return _API_CLIENT.reply_file(message_id, file_key)


def send_file_by_open_id(open_id: str, file_key: str, receive_id_type: str = "open_id") -> bool:
    return _API_CLIENT.send_file_by_open_id(open_id, file_key, receive_id_type)


def _send_private_text_message(receive_id: str, text: str, receive_id_type: str = "open_id") -> bool:
    cfg = get_config() or {}
    return _MESSAGE_DELIVERY_SERVICE.send_private_message(
        cfg,
        text,
        receive_id=str(receive_id or "").strip(),
        receive_id_type=str(receive_id_type or "open_id").strip() or "open_id",
    )


def send_image_by_open_id(open_id: str, image_key: str, receive_id_type: str = "open_id") -> bool:
    return _API_CLIENT.send_image_by_open_id(open_id, image_key, receive_id_type)


# 产出文件发送：允许的扩展名、最大大小（字节）
OUTPUT_FILE_EXTS = {".md", ".txt", ".json", ".csv", ".yaml", ".yml"}
OUTPUT_FILE_MAX_BYTES = 500 * 1024  # 500KB

# 【decide】块标记，模型通过此块声明要发送的文件
DECIDE_BLOCK_MARKER = "【decide】"
CARD_CONTROL_COMMANDS = {"terminate", "stop", "cancel", "abort"}


def _parse_decide_from_reply(text: str) -> tuple[str, list[dict]]:
    """
    从模型回复中解析 【decide】 块，返回 (去除 decide 后的正文, decide 列表)。
    decide 格式: [{"send": "path/to/file"}, ...]
    """
    if not text:
        return text, []
    if DECIDE_BLOCK_MARKER not in text:
        return text, []
    idx = text.find(DECIDE_BLOCK_MARKER)
    body = text[:idx].rstrip()
    rest = text[idx + len(DECIDE_BLOCK_MARKER):].lstrip()
    decide_list = []
    try:
        json_str = re.sub(r"^```\w*\s*", "", rest.strip())
        json_str = re.sub(r"\s*```\s*$", "", json_str).strip()
        decoded = json.loads(json_str)
        if isinstance(decoded, list):
            for item in decoded:
                if isinstance(item, dict) and item.get("send"):
                    decide_list.append({"send": str(item["send"]).strip()})
            print(f"[decide解析] 成功解析 {len(decide_list)} 条: {[d.get('send') for d in decide_list]}", flush=True)
        else:
            print(f"[decide解析] decoded 非列表 type={type(decoded)}", flush=True)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"[decide解析] JSON 解析失败: {e} | rest_preview={rest[:200]}", flush=True)
    return body, decide_list


def _get_turn_raw_reply(run_agent_fn: Callable[..., str]) -> str:
    getter = getattr(run_agent_fn, "get_turn_raw_reply", None)
    if not callable(getter):
        return ""
    try:
        return str(getter() or "").strip()
    except Exception as exc:
        print(f"[decide解析] get_turn_raw_reply failed: {exc}", flush=True)
        return ""


def _get_turn_output_bundle(run_agent_fn: Callable[..., str]) -> OutputBundle | None:
    getter = getattr(run_agent_fn, "get_turn_output_bundle", None)
    if not callable(getter):
        return None
    try:
        bundle = getter()
    except Exception as exc:
        print(f"[decide解析] get_turn_output_bundle failed: {exc}", flush=True)
        return None
    return bundle if isinstance(bundle, OutputBundle) else None


def _decide_list_from_output_bundle(bundle: OutputBundle | None) -> list[dict]:
    if not isinstance(bundle, OutputBundle):
        return []
    decide_list: list[dict] = []
    seen_paths: set[str] = set()
    for asset in list(bundle.files or []):
        path_text = str(getattr(asset, "path", "") or "").strip()
        if not path_text or path_text in seen_paths:
            continue
        seen_paths.add(path_text)
        decide_list.append({"send": path_text})
    return decide_list


def _resolve_decide_payload(
    run_agent_fn: Callable[..., str],
    visible_reply_text: str,
) -> tuple[str, list[dict]]:
    raw_reply_text = _get_turn_raw_reply(run_agent_fn)
    clean_reply, decide_list = _parse_decide_from_reply(raw_reply_text or visible_reply_text)
    if decide_list:
        return clean_reply, decide_list
    fallback = _decide_list_from_output_bundle(_get_turn_output_bundle(run_agent_fn))
    if fallback:
        print(f"[decide解析] 回退到 output_bundle 文件: {[item.get('send') for item in fallback]}", flush=True)
        return clean_reply or str(visible_reply_text or "").strip(), fallback
    return clean_reply, decide_list


def collect_output_files(workspace: str) -> list[str]:
    """扫描公司目录（工作区）中最近修改的、可发送的产出文件"""
    base = str(resolve_butler_root(workspace) / COMPANY_HOME_REL)
    print(f"[产出文件扫描] workspace={workspace} | base={base}", flush=True)
    if not os.path.isdir(base):
        print(f"[产出文件扫描] 目录不存在，跳过: {base}", flush=True)
        return []
    now = time.time()
    candidates = []
    skip_size = 0
    skip_time = 0
    for root, _, files in os.walk(base):
        for f in files:
            path = os.path.join(root, f)
            try:
                ext = os.path.splitext(f)[1].lower()
                if ext not in OUTPUT_FILE_EXTS:
                    continue
                size = os.path.getsize(path)
                if size > OUTPUT_FILE_MAX_BYTES:
                    skip_size += 1
                    continue
                mtime = os.path.getmtime(path)
                age = now - mtime
                if age > OUTPUT_FILE_RECENT_SEC:
                    skip_time += 1
                    continue
                candidates.append((mtime, path))
            except OSError as e:
                print(f"[产出文件扫描] 跳过(异常): {path} err={e}", flush=True)
                continue
    candidates.sort(key=lambda x: -x[0])
    result = [p for _, p in candidates[:5]]
    print(f"[产出文件扫描] 命中 {len(result)} 个 | 跳过超大小={skip_size} 超时={skip_time} | 文件={[os.path.basename(p) for p in result]}", flush=True)
    return result


def reply_message(
    message_id: str,
    text: str,
    use_interactive: bool = True,
    include_card_actions: bool | None = None,
    card_action_mode: str = "followup",
) -> bool:
    return _REPLY_SERVICE.reply_message(
        message_id,
        text,
        use_interactive=use_interactive,
        include_card_actions=include_card_actions,
        card_action_mode=card_action_mode,
    )


def _create_stream_reply_placeholder(
    message_id: str,
    text: str = STREAM_PLACEHOLDER_TEXT,
    *,
    card_action_value_extras: dict | None = None,
) -> str:
    placeholder_id = _REPLY_SERVICE.create_interactive_reply(
        message_id,
        text,
        include_card_actions=True,
        card_action_mode="running",
        card_action_value_extras=card_action_value_extras,
    )
    if placeholder_id:
        print(f"[stream-reply] created placeholder reply={placeholder_id}", flush=True)
    return placeholder_id


def _update_stream_reply_message(
    message_id: str,
    text: str,
    *,
    include_card_actions: bool = False,
    card_action_mode: str = "followup",
    card_action_value_extras: dict | None = None,
) -> bool:
    ok = _REPLY_SERVICE.update_interactive_message(
        message_id,
        text,
        include_card_actions=include_card_actions,
        card_action_mode=card_action_mode,
        card_action_value_extras=card_action_value_extras,
    )
    if ok:
        print(
            f"[stream-reply] updated message_id={message_id} final={include_card_actions} preview={_preview_text(text)}",
            flush=True,
        )
    return ok


def _send_output_files(message_id: str, workspace: str, decide_list: list[dict] | None = None) -> None:
    """
    根据模型输出的 decide 列表发送文件。
    优先使用 file_send_open_id 直接发送；未配置时回退到 reply 回复原消息。
    """
    cfg = get_config() or {}
    open_id = str(cfg.get("file_send_open_id") or cfg.get("startup_notify_open_id") or "").strip()
    use_open_id = bool(open_id)
    receive_id_type = str(cfg.get("file_send_receive_id_type") or cfg.get("startup_notify_receive_id_type") or "open_id").strip() or "open_id"

    print(f"[发送产出文件] 开始 use_open_id={use_open_id} open_id={open_id[:20] if open_id else ''}... decide={decide_list}", flush=True)
    if not decide_list:
        print(f"[发送产出文件] 无 decide 指令，跳过", flush=True)
        return
    paths = []
    for d in decide_list:
        p = (d.get("send") or "").strip()
        if p:
            full = str((resolve_butler_root(workspace) / p).resolve()) if not os.path.isabs(p) else p
            print(f"[发送产出文件] 检查路径: {p} -> full={full} exists={os.path.isfile(full)}", flush=True)
            if os.path.isfile(full):
                size = os.path.getsize(full)
                if size <= OUTPUT_FILE_MAX_BYTES:
                    paths.append(full)
                else:
                    print(f"[发送产出文件] 跳过(超大小): {p} size={size} max={OUTPUT_FILE_MAX_BYTES}", flush=True)
            else:
                print(f"[发送产出文件] 文件不存在: {p}", flush=True)
    if not paths:
        print(f"[发送产出文件] 无有效文件可发送", flush=True)
        return
    for path in paths:
        try:
            print(f"[发送产出文件] 上传中: {path}", flush=True)
            fkey = upload_file(path)
            if not fkey:
                print(f"[发送产出文件] 上传失败(无file_key): {path}", flush=True)
                continue
            print(f"[发送产出文件] 上传成功 file_key={fkey[:40] + '...' if len(fkey) > 40 else fkey}", flush=True)
            if use_open_id:
                ok = send_file_by_open_id(open_id, fkey, receive_id_type)
            else:
                ok = reply_file(message_id, fkey)
            if ok:
                print(f"[发送产出文件] 已发送: {path}", flush=True)
            else:
                print(f"[发送产出文件] 发送失败: {path}", flush=True)
        except Exception as e:
            print(f"[发送产出文件失败] {path}: {e}", flush=True)


def _resolve_processing_receipt_text(
    prompt: str,
    run_agent_fn: Callable[..., str],
    immediate_receipt_text: str | None,
    invocation_metadata: dict | None,
) -> str:
    template = str(immediate_receipt_text or "").strip()
    if not template:
        return ""
    runtime_descriptor = {}
    describe_runtime = getattr(run_agent_fn, "describe_runtime_target", None)
    if callable(describe_runtime):
        try:
            runtime_descriptor = dict(describe_runtime(prompt, invocation_metadata=invocation_metadata) or {})
        except TypeError:
            runtime_descriptor = dict(describe_runtime(prompt) or {})
        except Exception as exc:
            print(f"[receipt] describe_runtime_target failed: {exc}", flush=True)
            runtime_descriptor = {}
    cli_name = str(runtime_descriptor.get("cli") or "cursor").strip() or "cursor"
    model_name = str(runtime_descriptor.get("model") or "auto").strip() or "auto"
    try:
        return template.format(cli=cli_name, model=model_name).strip()
    except Exception:
        return template


def _processing_receipt_delay_seconds() -> float:
    return float(PROCESSING_RECEIPT_DELAY_SECONDS)


def _handle_card_control_action(payload: dict, run_agent_fn: Callable[..., str]) -> dict:
    cmd = str(payload.get("cmd") or "").strip().lower()
    if cmd not in CARD_CONTROL_COMMANDS:
        return {"handled": False}
    cancel_fn = getattr(run_agent_fn, "cancel_active_execution", None)
    if not callable(cancel_fn):
        return {"handled": True, "message": "当前运行时还不支持终止。", "toast_type": "warning"}
    action_value = dict(payload.get("value") or {}) if isinstance(payload.get("value"), dict) else {}
    request_id = str(action_value.get("request_id") or "").strip()
    session_id = str(action_value.get("session_id") or payload.get("open_chat_id") or "").strip()
    actor_id = str(payload.get("open_id") or payload.get("user_id") or "").strip()
    message_id = str(action_value.get("source_message_id") or payload.get("open_message_id") or "").strip()
    try:
        result = cancel_fn(
            request_id=request_id,
            session_id=session_id,
            actor_id=actor_id,
            message_id=message_id,
            payload=dict(payload),
        )
    except TypeError:
        result = cancel_fn(request_id=request_id, session_id=session_id, actor_id=actor_id, message_id=message_id)
    payload_dict = dict(result or {}) if isinstance(result, dict) else {}
    cancelled_count = int(payload_dict.get("cancelled_count") or payload_dict.get("matched_count") or 0)
    if cancelled_count > 0:
        return {"handled": True, "message": f"已请求终止当前执行（{cancelled_count}）", "toast_type": "success"}
    if payload_dict.get("supported") is False:
        return {"handled": True, "message": "当前运行时还不支持终止。", "toast_type": "warning"}
    return {"handled": True, "message": "当前没有可终止的执行。", "toast_type": "info"}


def handle_message_async(
    message_id: str,
    prompt: str,
    image_keys: list[str] | None,
    run_agent_fn: Callable[..., str],
    supports_images: bool = True,
    supports_stream_segment: bool = True,
    on_reply_sent: Callable[[str, str], None] | None = None,
    send_output_files: bool = True,
    dedup_id: str | None = None,
    immediate_receipt_text: str | None = None,
    invocation_metadata: dict | None = None,
    deliver_output_bundle_fn: Callable[..., bool] | None = None,
) -> None:
    claim_id = (dedup_id or message_id or "").strip()
    if claim_id and not _claim_message(claim_id):
        print(f"[去重] 跳过重复消息: {claim_id}", flush=True)
        return

    has_stream_output = {"value": False}
    hint_sent = {"value": False}
    receipt_sent = {"value": False}
    request_finished = {"value": False}
    latest_stream_text = {"value": ""}
    stream_process_entries = {"value": []}
    stream_reply_message_id = {"value": ""}
    workspace_ref = {"value": os.getcwd()}
    request_id = f"chat-run-{uuid.uuid4().hex[:12]}"
    effective_invocation_metadata = dict(invocation_metadata or {})
    effective_invocation_metadata.setdefault("message_id", str(message_id or "").strip())
    effective_invocation_metadata["request_id"] = request_id
    _register_recent_feishu_session(effective_invocation_metadata)
    action_value_extras = {
        "request_id": request_id,
        "source_message_id": str(message_id or "").strip(),
    }
    session_ref = str(effective_invocation_metadata.get("session_id") or "").strip()
    if session_ref:
        action_value_extras["session_id"] = session_ref

    receipt_text = _resolve_processing_receipt_text(prompt, run_agent_fn, immediate_receipt_text, effective_invocation_metadata)

    def _ensure_stream_reply_placeholder(text: str = "") -> str:
        if not supports_stream_segment:
            return ""
        if stream_reply_message_id["value"]:
            return stream_reply_message_id["value"]
        placeholder_text = str(text or "").strip() or STREAM_PLACEHOLDER_TEXT
        stream_reply_message_id["value"] = _create_stream_reply_placeholder(
            message_id,
            placeholder_text,
            card_action_value_extras=action_value_extras,
        )
        return stream_reply_message_id["value"]

    def _segment_key(text: str) -> str:
        # 归一化空白，避免仅因换行/空格差异导致重复发送。
        return re.sub(r"\s+", " ", (text or "").strip())

    def _on_segment(segment: str):
        seg = (segment or "").strip()
        key = _segment_key(seg)
        if not key or key == _segment_key(latest_stream_text["value"]):
            return
        previous_snapshot = latest_stream_text["value"]
        latest_stream_text["value"] = seg
        has_stream_output["value"] = True
        stream_process_entries["value"] = _append_stream_process_entry(
            stream_process_entries["value"],
            _extract_incremental_stream_entry(previous_snapshot, seg),
        )
        process_text = _render_stream_process_text(stream_process_entries["value"])
        if not stream_reply_message_id["value"]:
            _ensure_stream_reply_placeholder(process_text)
        if stream_reply_message_id["value"]:
            _update_stream_reply_message(
                stream_reply_message_id["value"],
                process_text,
                include_card_actions=True,
                card_action_mode="running",
                card_action_value_extras=action_value_extras,
            )

    def _maybe_send_hint():
        """若 HINT_DELAY 秒内模型无输出，再回复「正在输入...」"""
        time.sleep(HINT_DELAY)
        if not request_finished["value"] and not has_stream_output["value"] and not hint_sent["value"]:
            hint_sent["value"] = True
            _send_deduped_reply(message_id, "正在输入…", use_interactive=False, channel="hint")

    def _maybe_send_processing_receipt():
        delay_seconds = max(0.0, _processing_receipt_delay_seconds())
        if delay_seconds:
            time.sleep(delay_seconds)
        if receipt_sent["value"] or not receipt_text:
            return
        if request_finished["value"] or has_stream_output["value"] or stream_reply_message_id["value"]:
            return
        receipt_sent["value"] = True
        _send_deduped_reply(message_id, receipt_text, use_interactive=False, channel="receipt")

    def _deliver_output_bundle(*, send_text: bool) -> bool:
        if not callable(deliver_output_bundle_fn):
            return False
        if send_text:
            return bool(deliver_output_bundle_fn(message_id, run_agent_fn, workspace_ref["value"]))
        return bool(deliver_output_bundle_fn(message_id, run_agent_fn, workspace_ref["value"], send_text=False))

    def _work():
        result_text = ""
        workspace = os.getcwd()
        used_chat_delivery = False
        try:
            # 默认关闭 typing hint，避免在某些场景形成“重复回复”的观感。
            if ENABLE_TYPING_HINT:
                threading.Thread(target=_maybe_send_hint, daemon=True).start()
            cfg = get_config()
            workspace = cfg.get("workspace_root", os.getcwd())
            workspace_ref["value"] = workspace
            print(f"[处理开始] message_id={message_id} | prompt={_preview_text(prompt)}", flush=True)
            image_paths = []
            if supports_images and image_keys:
                image_paths = download_message_images(message_id, image_keys, workspace)
            kwargs = {}
            if supports_stream_segment:
                kwargs["stream_callback"] = _on_segment
            if image_paths:
                kwargs["image_paths"] = image_paths
            if effective_invocation_metadata:
                try:
                    sig = inspect.signature(run_agent_fn)
                    if "invocation_metadata" in sig.parameters:
                        kwargs["invocation_metadata"] = effective_invocation_metadata
                except Exception:
                    pass
            result = run_agent_fn(prompt, **kwargs)
            result_text = (result or "").strip()
            print(f"[处理完成] message_id={message_id} | result={_preview_text(result_text)}", flush=True)
            request_finished["value"] = True
            if result_text:
                clean_reply, decide_list = _resolve_decide_payload(run_agent_fn, result_text)
                if decide_list:
                    print(f"[decide] 解析到 {len(decide_list)} 条: {[d.get('send') for d in decide_list]}", flush=True)
                if stream_reply_message_id["value"]:
                    print("[stream-reply] final text will close existing interactive card", flush=True)
                    if callable(deliver_output_bundle_fn):
                        try:
                            used_chat_delivery = _deliver_output_bundle(send_text=False)
                        except Exception as exc:
                            print(f"[delivery-callback] failed: {exc}", flush=True)
                            used_chat_delivery = False
                elif callable(deliver_output_bundle_fn):
                    try:
                        used_chat_delivery = _deliver_output_bundle(send_text=True)
                    except Exception as exc:
                        print(f"[delivery-callback] failed: {exc}", flush=True)
                        used_chat_delivery = False
                if used_chat_delivery:
                    print("[chat-delivery] 新发送链已接管本轮输出", flush=True)
                else:
                    to_send = (clean_reply or result_text).strip()
                    if to_send:
                        if stream_reply_message_id["value"]:
                            if not _update_stream_reply_message(stream_reply_message_id["value"], to_send, include_card_actions=False):
                                _send_deduped_reply(message_id, to_send, channel="final")
                        else:
                            _send_deduped_reply(message_id, to_send, channel="final")
        except Exception as e:
            print(f"[处理消息异常] {e}", file=sys.stderr)
            request_finished["value"] = True
            if has_stream_output["value"] and latest_stream_text["value"]:
                result_text = latest_stream_text["value"]

        # 某些流式场景最终 result 为空；此时回退用最后一个稳定快照，避免累计 snapshot join 导致重复和错序。
        if not result_text and has_stream_output["value"] and latest_stream_text["value"]:
            result_text = latest_stream_text["value"]
            if stream_reply_message_id["value"]:
                if not _update_stream_reply_message(stream_reply_message_id["value"], result_text, include_card_actions=False):
                    _send_deduped_reply(message_id, result_text, channel="final")
            else:
                _send_deduped_reply(message_id, result_text, channel="final")

        request_finished["value"] = True

        # 解析 decide，供记忆持久化与文件发送
        clean_reply, decide_list = _resolve_decide_payload(run_agent_fn, result_text)
        print(f"[产出文件] 解析后 decide_list 长度={len(decide_list)}", flush=True)

        if on_reply_sent:
            try:
                on_reply_sent(prompt, clean_reply or result_text)
            except Exception as e:
                print(f"on_reply_sent 执行异常: {e}", file=sys.stderr)

        if used_chat_delivery:
            print("[产出文件] chat delivery 已接管，跳过旧文件发送链", flush=True)
        elif send_output_files:
            try:
                print(f"[产出文件] send_output_files=True 开始发送 decide_list={decide_list}", flush=True)
                _send_output_files(message_id, workspace, decide_list)
                print(f"[产出文件] 发送流程结束", flush=True)
            except Exception as e:
                print(f"[产出文件] 发送异常: {e}", flush=True)
        else:
            print(f"[产出文件] send_output_files=False 跳过", flush=True)

    if supports_stream_segment:
        _ensure_stream_reply_placeholder()
    threading.Thread(target=_work, daemon=True).start()
    if receipt_text:
        threading.Thread(target=_maybe_send_processing_receipt, daemon=True).start()


def _extract_message(data) -> tuple[str, str, list[str]]:
    """返回 (message_id, text, image_keys)"""
    payload = _interaction_build_message_receive_payload(data)
    message = payload.get("event", {}).get("message", {})
    message_id = str(message.get("message_id") or "")
    raw_content = message.get("content", "{}")
    text = _interaction_extract_message_text(raw_content)
    image_keys = _interaction_extract_message_image_keys(raw_content)
    return message_id, text, image_keys


def _build_invocation_metadata_from_message(data) -> dict:
    return _interaction_build_invocation_metadata_from_message(data)


def _normalize_feishu_history_timestamp(raw_value) -> tuple[int, str]:
    text = str(raw_value or "").strip()
    if not text:
        return 0, ""
    try:
        value = int(float(text))
    except Exception:
        value = 0
    if value > 0:
        seconds = value / 1000.0 if value > 10**11 else float(value)
        return int(seconds), time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(seconds))
    if len(text) >= 19 and text[4:5] == "-" and text[7:8] == "-":
        return 0, text[:19]
    return 0, text[:19]


def _extract_feishu_history_message_text(message: dict) -> str:
    body = dict(message.get("body") or {}) if isinstance(message.get("body"), dict) else {}
    raw_content = body.get("content")
    if raw_content in (None, ""):
        raw_content = message.get("content")
    text = _interaction_extract_message_text(raw_content)
    if text:
        return text
    image_keys = _interaction_extract_message_image_keys(raw_content)
    if image_keys:
        return "[图片]" if len(image_keys) == 1 else f"[图片 x{len(image_keys)}]"
    msg_type = str(message.get("msg_type") or message.get("message_type") or body.get("msg_type") or "").strip().lower()
    fallback_map = {
        "image": "[图片]",
        "file": "[文件]",
        "audio": "[语音]",
        "media": "[媒体]",
        "sticker": "[表情]",
        "interactive": "[卡片消息]",
        "post": "[富文本消息]",
    }
    return fallback_map.get(msg_type, f"[{msg_type}]" if msg_type else "")


def _normalize_feishu_history_message(message: dict, *, input_order: int) -> dict | None:
    if not isinstance(message, dict):
        return None
    sender = dict(message.get("sender") or {}) if isinstance(message.get("sender"), dict) else {}
    sender_type = str(message.get("sender_type") or sender.get("sender_type") or "").strip().lower()
    msg_type = str(message.get("msg_type") or message.get("message_type") or "").strip().lower()
    role = "assistant" if sender_type in {"bot", "app"} or msg_type == "interactive" else "user"
    sort_value, timestamp_text = _normalize_feishu_history_timestamp(
        message.get("create_time") or message.get("update_time") or message.get("timestamp")
    )
    message_id = str(message.get("message_id") or "").strip()
    text = _extract_feishu_history_message_text(message).strip()
    if not message_id and not text:
        return None
    return {
        "message_id": message_id,
        "role": role,
        "text": text,
        "timestamp": timestamp_text,
        "sort_value": sort_value,
        "input_order": int(input_order),
    }


def _build_feishu_backfill_turns(messages: list[dict], *, session_scope_id: str, chat_id: str) -> list[dict]:
    normalized_messages: list[dict] = []
    for index, item in enumerate(messages or []):
        normalized = _normalize_feishu_history_message(item, input_order=index)
        if normalized is not None:
            normalized_messages.append(normalized)
    normalized_messages.sort(key=lambda item: (int(item.get("sort_value") or 0), int(item.get("input_order") or 0)))
    turns: list[dict] = []
    pending_user_texts: list[str] = []
    pending_user_ids: list[str] = []
    pending_user_timestamp = ""
    for item in normalized_messages:
        role = str(item.get("role") or "user").strip().lower()
        text = str(item.get("text") or "").strip()
        message_id = str(item.get("message_id") or "").strip()
        timestamp_text = str(item.get("timestamp") or "").strip()
        if role == "assistant":
            if not text or not message_id:
                continue
            user_prompt = "\n\n".join(part for part in pending_user_texts if part).strip()
            source_ids = [*pending_user_ids, message_id]
            turns.append(
                {
                    "memory_id": f"feishu-backfill:{message_id}",
                    "timestamp": timestamp_text or pending_user_timestamp,
                    "user_prompt": user_prompt,
                    "assistant_reply_visible": text,
                    "assistant_reply_raw": text,
                    "status": "completed",
                    "source_kind": "feishu_backfill",
                    "source_chat_id": str(chat_id or "").strip(),
                    "source_message_ids": [item for item in source_ids if item],
                    "session_scope_id": session_scope_id,
                }
            )
            pending_user_texts = []
            pending_user_ids = []
            pending_user_timestamp = ""
            continue
        if not text:
            continue
        pending_user_texts.append(text)
        if message_id:
            pending_user_ids.append(message_id)
        if not pending_user_timestamp and timestamp_text:
            pending_user_timestamp = timestamp_text
    return turns


def _backfill_recent_feishu_history_before_restart(run_agent_fn: Callable[..., str]) -> None:
    backfill_fn = getattr(run_agent_fn, "backfill_recent_feishu_messages", None)
    if not callable(backfill_fn):
        return
    sessions = _list_recent_feishu_sessions()
    if not sessions:
        return
    for session in sessions:
        chat_id = str(session.get("chat_id") or "").strip()
        session_scope_id = str(session.get("session_scope_id") or "").strip()
        if not chat_id or not session_scope_id:
            continue
        try:
            ok, payload = _API_CLIENT.list_messages(
                container_id=chat_id,
                container_id_type="chat",
                page_size=_RECENT_FEISHU_BACKFILL_MESSAGE_LIMIT,
                sort_type="ByCreateTimeDesc",
            )
        except Exception as exc:
            print(f"[feishu-backfill] list_messages failed chat_id={chat_id[:24]} err={exc}", flush=True)
            continue
        if not ok:
            print(f"[feishu-backfill] list_messages returned non-ok chat_id={chat_id[:24]}", flush=True)
            continue
        items = ((payload.get("data") or {}).get("items") or [])
        turns = _build_feishu_backfill_turns(
            list(items),
            session_scope_id=session_scope_id,
            chat_id=chat_id,
        )
        if not turns:
            print(f"[feishu-backfill] no completed turns recovered for {session_scope_id}", flush=True)
            continue
        try:
            written = int(
                backfill_fn(
                    turns,
                    session_scope_id=session_scope_id,
                    chat_id=chat_id,
                )
                or 0
            )
        except Exception as exc:
            print(f"[feishu-backfill] write failed scope={session_scope_id} err={exc}", flush=True)
            continue
        print(
            f"[feishu-backfill] scope={session_scope_id} chat_id={chat_id[:24]} fetched={len(items)} turns={len(turns)} written={written}",
            flush=True,
        )


def _run_feishu_loop(
    *,
    bot_name: str,
    run_agent_fn: Callable[..., str],
    supports_images: bool,
    supports_stream_segment: bool,
    send_output_files: bool,
    on_bot_started: Callable[[], None] | None,
    on_reply_sent: Callable[[str, str], None] | None,
    immediate_receipt_text: str | None = None,
    deliver_output_bundle_fn: Callable[..., bool] | None = None,
) -> int:
    _sync_feishu_runtime_state(CONFIG)
    ok, detail = _run_feishu_preflight(auth_probe=False)
    if not ok:
        print(f"飞书 preflight 失败: {detail}", file=sys.stderr)
        return 1
    print(f"[feishu-preflight] ok | {detail}", flush=True)

    if on_bot_started:
        try:
            on_bot_started()
        except Exception as e:
            print(f"on_bot_started 执行异常: {e}", file=sys.stderr)

    restart_cfg = CONFIG.get("feishu_long_connection") or {}
    auto_restart = bool(restart_cfg.get("auto_restart_on_disconnect", True))
    max_restart_attempts = max(0, int(restart_cfg.get("max_restart_attempts", 0) or 0))
    restart_backoff_seconds = max(1, int(restart_cfg.get("restart_backoff_seconds", 5) or 5))
    restart_backoff_max_seconds = max(restart_backoff_seconds, int(restart_cfg.get("restart_backoff_max_seconds", 60) or 60))
    handler = build_chat_feishu_event_dispatcher(
        run_agent_fn=run_agent_fn,
        supports_images=supports_images,
        supports_stream_segment=supports_stream_segment,
        send_output_files=send_output_files,
        on_reply_sent=on_reply_sent,
        immediate_receipt_text=immediate_receipt_text,
        deliver_output_bundle_fn=deliver_output_bundle_fn,
        handle_card_control_fn=lambda payload: _handle_card_control_action(payload, run_agent_fn),
        handle_message_async_fn=handle_message_async,
        reply_message_fn=reply_message,
    )
    restart_attempt = 0
    while True:
        cli = ws.Client(CONFIG["app_id"], CONFIG["app_secret"], event_handler=handler, log_level=lark.LogLevel.INFO)
        print(f"启动飞书 {bot_name} 机器人（长连接）...", flush=True)
        try:
            cli.start()
            if not auto_restart:
                return 0
            restart_attempt += 1
            if max_restart_attempts > 0 and restart_attempt > max_restart_attempts:
                print(f"[feishu-loop] 长连接异常结束，已达到最大重启次数 {max_restart_attempts}，停止自动重连", file=sys.stderr, flush=True)
                return 1
            _backfill_recent_feishu_history_before_restart(run_agent_fn)
            delay_seconds = min(restart_backoff_max_seconds, restart_backoff_seconds * (2 ** max(0, restart_attempt - 1)))
            print(f"[feishu-loop] 长连接意外结束，{delay_seconds}s 后重连（attempt={restart_attempt}）", file=sys.stderr, flush=True)
            time.sleep(delay_seconds)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            if not auto_restart:
                print(f"飞书长连接异常退出: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
                return 1
            restart_attempt += 1
            if max_restart_attempts > 0 and restart_attempt > max_restart_attempts:
                print(
                    f"[feishu-loop] 长连接异常退出 {type(exc).__name__}: {exc}；已达到最大重启次数 {max_restart_attempts}",
                    file=sys.stderr,
                    flush=True,
                )
                return 1
            _backfill_recent_feishu_history_before_restart(run_agent_fn)
            delay_seconds = min(restart_backoff_max_seconds, restart_backoff_seconds * (2 ** max(0, restart_attempt - 1)))
            print(
                f"[feishu-loop] 长连接异常退出 {type(exc).__name__}: {exc}；{delay_seconds}s 后重连（attempt={restart_attempt}）",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(delay_seconds)


def run_feishu_bot_with_loaded_config(
    config: dict,
    *,
    bot_name: str,
    run_agent_fn: Callable[..., str],
    supports_images: bool = True,
    supports_stream_segment: bool = True,
    send_output_files: bool = True,
    on_bot_started: Callable[[], None] | None = None,
    on_reply_sent: Callable[[str, str], None] | None = None,
    immediate_receipt_text: str | None = None,
    deliver_output_bundle_fn: Callable[..., bool] | None = None,
) -> int:
    global CONFIG, _config_path_for_reload
    normalized = dict(config or {})
    _config_path_for_reload = os.path.abspath(str(normalized.get("__config_path") or "")) if str(normalized.get("__config_path") or "").strip() else None
    CONFIG.clear()
    CONFIG.update(normalized)
    if not CONFIG.get("workspace_root"):
        CONFIG["workspace_root"] = str(resolve_butler_root(__file__))
    _sync_feishu_runtime_state(CONFIG)
    set_runtime_log_config(CONFIG.get("__config_path"), (CONFIG.get("logging") or {}).get("level") if isinstance(CONFIG.get("logging"), dict) else None)
    return _run_feishu_loop(
        bot_name=bot_name,
        run_agent_fn=run_agent_fn,
        supports_images=supports_images,
        supports_stream_segment=supports_stream_segment,
        send_output_files=send_output_files,
        on_bot_started=on_bot_started,
        on_reply_sent=on_reply_sent,
        immediate_receipt_text=immediate_receipt_text,
        deliver_output_bundle_fn=deliver_output_bundle_fn,
    )


def run_feishu_bot(
    config_path: str,
    default_config_name: str,
    bot_name: str,
    run_agent_fn: Callable[..., str],
    supports_images: bool = True,
    supports_stream_segment: bool = True,
    send_output_files: bool = True,
    args_extra: argparse.ArgumentParser | None = None,
    local_test_fn: Callable[[str, argparse.Namespace], str] | Callable[[str], str] | None = None,
    on_bot_started: Callable[[], None] | None = None,
    on_reply_sent: Callable[[str, str], None] | None = None,
    immediate_receipt_text: str | None = None,
    deliver_output_bundle_fn: Callable[..., bool] | None = None,
) -> int:
    """
    通用飞书长连接入口。
    run_agent_fn(prompt, stream_callback=None, image_paths=None) -> str
    不支持的特性可忽略对应参数。
    """
    global CONFIG, _config_path_for_reload

    parser = argparse.ArgumentParser(description=f"Butler chat service ({bot_name}; Feishu by default)")
    parser.add_argument("--config", "-c", help="配置文件路径")
    parser.add_argument("--prompt", "-p", help="本地测试：提示词")
    parser.add_argument("--stdin", action="store_true", help="本地测试：从 stdin 读取")
    parser.add_argument("--preflight", action="store_true", help="仅校验飞书配置与运行前状态，不启动长连接")
    if args_extra:
        for action in args_extra._actions:
            if action.dest not in ["config", "prompt", "stdin", "help"]:
                parser._add_action(action)
    args = parser.parse_args()

    if getattr(args, "preflight", False):
        path = args.config or _resolve_default_config_path(default_config_name)
        if not os.path.isfile(path):
            print(f"请指定 --config 或确保存在 {path}", file=sys.stderr)
            return 1
        _config_path_for_reload = os.path.abspath(path)
        CONFIG.clear()
        CONFIG.update(load_config(path))
        CONFIG["__config_path"] = _config_path_for_reload
        _sync_feishu_runtime_state(CONFIG)
        ok, detail = _run_feishu_preflight(auth_probe=True)
        if ok:
            print(f"[feishu-preflight] ok | {detail}", flush=True)
            return 0
        print(f"[feishu-preflight] failed | {detail}", file=sys.stderr)
        return 1

    # 本地测试
    prompt = args.prompt.strip() if isinstance(getattr(args, "prompt", None), str) and args.prompt.strip() else None
    if prompt is None and getattr(args, "stdin", False):
        prompt = sys.stdin.read().strip()
    if prompt is not None:
        path = args.config or _resolve_default_config_path(default_config_name)
        if not os.path.isfile(path):
            print(f"请指定 --config 或确保存在 {path}", file=sys.stderr)
            return 1
        _config_path_for_reload = os.path.abspath(path)
        CONFIG.clear()
        CONFIG.update(load_config(path))
        CONFIG["__config_path"] = _config_path_for_reload
        _sync_feishu_runtime_state(CONFIG)
        set_runtime_log_config(CONFIG.get("__config_path"), (CONFIG.get("logging") or {}).get("level") if isinstance(CONFIG.get("logging"), dict) else None)
        if not CONFIG.get("workspace_root"):
            CONFIG["workspace_root"] = str(resolve_butler_root(__file__))
        if local_test_fn:
            import inspect
            sig = inspect.signature(local_test_fn)
            if len(sig.parameters) >= 2:
                result = local_test_fn(prompt, args)
            else:
                result = local_test_fn(prompt)
        else:
            result = run_agent_fn(prompt)
        print("\n--- 回复 ---\n", result, flush=True)
        if on_reply_sent and (result or "").strip():
            try:
                on_reply_sent(prompt, result)
                print("[记忆] 本地测试模式已触发短期记忆更新", flush=True)
            except Exception as e:
                print(f"[记忆] on_reply_sent 执行异常: {e}", file=sys.stderr)
        return 0

    # ── 交互式 REPL 模式 ──
    # 等价于飞书输入的本机命令行入口：
    #   1. 完整加载配置（与飞书模式相同）
    #   2. 调用 on_bot_started() 启动后台服务（recent recover、定时维护等），补齐 --prompt 单次模式的缺失
    #   3. 进入 REPL 循环：每轮输入走 run_agent() 全链路（记忆注入 → prompt 组装 → CLI runtime → 回复）
    #   4. 回复后触发 on_reply_sent() 做记忆持久化，与飞书回复后的行为一致
    # 用法：.venv\Scripts\python.exe -m butler_main.chat --interactive [-c config.json] [--stream]
    if getattr(args, "interactive", False):
        path = args.config or _resolve_default_config_path(default_config_name)
        if not os.path.isfile(path):
            print(f"请指定 --config 或确保存在 {path}", file=sys.stderr)
            return 1
        _config_path_for_reload = os.path.abspath(path)
        CONFIG.clear()
        CONFIG.update(load_config(path))
        CONFIG["__config_path"] = _config_path_for_reload
        _sync_feishu_runtime_state(CONFIG)
        set_runtime_log_config(
            CONFIG.get("__config_path"),
            (CONFIG.get("logging") or {}).get("level")
            if isinstance(CONFIG.get("logging"), dict) else None,
        )
        if not CONFIG.get("workspace_root"):
            CONFIG["workspace_root"] = str(resolve_butler_root(__file__))

        # 与飞书模式一致：启动后台服务（recent recover、定时维护等）
        if on_bot_started:
            try:
                on_bot_started()
            except Exception as e:
                print(f"on_bot_started 执行异常: {e}", file=sys.stderr)

        print(f"\n{'=' * 54}")
        print(f"  {bot_name} · 交互式命令行模式")
        print(f"  输入消息后回车发送 | exit / quit 退出 | Ctrl+C 退出")
        print(f"{'=' * 54}\n", flush=True)

        try:
            while True:
                try:
                    user_input = input("你> ").strip()
                except EOFError:
                    # stdin 关闭（管道结束等），优雅退出
                    break
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
                    break

                # 调用与飞书消息处理相同的 run_agent 链路
                if local_test_fn:
                    import inspect
                    sig = inspect.signature(local_test_fn)
                    if len(sig.parameters) >= 2:
                        result = local_test_fn(user_input, args)
                    else:
                        result = local_test_fn(user_input)
                else:
                    result = run_agent_fn(user_input)

                print(f"\n{result}\n", flush=True)

                # 回复后持久化记忆，与飞书 on_reply_sent 行为一致
                if on_reply_sent and (result or "").strip():
                    try:
                        on_reply_sent(user_input, result)
                    except Exception as e:
                        print(f"[记忆] on_reply_sent 异常: {e}", file=sys.stderr)
        except KeyboardInterrupt:
            print("\n\n[交互模式] 已退出。")
        return 0

    # 飞书长连接
    if not args.config:
        print("飞书模式需指定 --config", file=sys.stderr)
        return 1
    _config_path_for_reload = os.path.abspath(args.config)
    CONFIG.clear()
    CONFIG.update(load_config(args.config))
    CONFIG["__config_path"] = _config_path_for_reload
    _sync_feishu_runtime_state(CONFIG)
    set_runtime_log_config(CONFIG.get("__config_path"), (CONFIG.get("logging") or {}).get("level") if isinstance(CONFIG.get("logging"), dict) else None)
    return _run_feishu_loop(
        bot_name=bot_name,
        run_agent_fn=run_agent_fn,
        supports_images=supports_images,
        supports_stream_segment=supports_stream_segment,
        send_output_files=send_output_files,
        on_bot_started=on_bot_started,
        on_reply_sent=on_reply_sent,
        immediate_receipt_text=immediate_receipt_text,
        deliver_output_bundle_fn=deliver_output_bundle_fn,
    )






