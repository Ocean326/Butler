# -*- coding: utf-8 -*-
"""
【Message 模块】飞书机器人消息层

职责：飞书长连接、消息解析、回复、去重、图片下载/上传等。
与 memory_manager（记忆层）分离，各 xx-agent 组合使用。

各 xx-agent 仅需实现 run_agent(prompt, stream_callback?, image_paths?) -> str 并调用 run_feishu_bot。
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from registry.agent_capability_registry import render_agent_capability_catalog_for_prompt
from butler_paths import BUTLER_MAIN_AGENT_ROLE_FILE_REL, BUTLER_SOUL_FILE_REL, COMPANY_HOME_REL, CURRENT_USER_PROFILE_FILE_REL, CURRENT_USER_PROFILE_TEMPLATE_FILE_REL, FEISHU_AGENT_ROLE_FILE_REL, SELF_MIND_DIR_REL, UPDATE_AGENT_ROLE_FILE_REL, prompt_path_text, resolve_butler_root
from utils.markdown_safety import safe_truncate_markdown, sanitize_markdown_structure
from services.prompt_assembly_service import DialoguePromptContext, PromptAssemblyService
from runtime.runtime_logging import install_print_hook, set_runtime_log_config

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

_token_cache = {"token": None, "expire": 0}
CONFIG = {}
_config_path_for_reload: str | None = None  # 用于热加载的配置文件路径
_config_last_reload = 0.0
_config_reload_interval = 5  # 秒，避免过于频繁读盘
_message_dedup = {}
_message_dedup_lock = threading.Lock()
_reply_dedup = {}
_reply_dedup_lock = threading.Lock()
_MESSAGE_DEDUP_TTL = 15 * 60
AGENT_ROLE_FILE = prompt_path_text(FEISHU_AGENT_ROLE_FILE_REL)
BUTLER_MAIN_AGENT_FILE = prompt_path_text(BUTLER_MAIN_AGENT_ROLE_FILE_REL)
BUTLER_SOUL_FILE = prompt_path_text(BUTLER_SOUL_FILE_REL)
CURRENT_USER_PROFILE_FILE = prompt_path_text(CURRENT_USER_PROFILE_FILE_REL)
CURRENT_USER_PROFILE_TEMPLATE_FILE = prompt_path_text(CURRENT_USER_PROFILE_TEMPLATE_FILE_REL)
SELF_MIND_CONTEXT_FILE = prompt_path_text(SELF_MIND_DIR_REL / "current_context.md")
SELF_MIND_COGNITION_INDEX_FILE = prompt_path_text(SELF_MIND_DIR_REL / "cognition" / "L0_index.json")
UPDATE_AGENT_FILE = prompt_path_text(UPDATE_AGENT_ROLE_FILE_REL)
# 默认关闭「正在输入...」提示，避免与最终回复形成双消息观感。
ENABLE_TYPING_HINT = False
HINT_DELAY = 15

_SOUL_TRIGGER_KEYWORDS = (
    "建议", "想法", "感觉", "怎么", "如何", "聊聊", "总结", "复盘", "记录", "日志",
    "设计", "规划", "为什么", "关系", "长期", "风格", "灵魂", "可爱", "元气", "汇报",
)

_COMPANION_TRIGGER_KEYWORDS = (
    "聊聊", "陪", "想你", "心情", "感觉", "委屈", "开心", "难过", "关系", "我们", "你觉得", "为什么",
)

_MAINTENANCE_TRIGGER_KEYWORDS = (
    "prompt", "role", "agent", "升级", "更新", "维护", "修提示词", "改提示词", "system", "self-upgrade",
    "自我升级", "重启", "漂移", "规则", "注入顺序", "编排", "维护入口",
)

_ALWAYS_ON_SOUL_GUIDANCE = (
    "你不是客服汇报机。默认保留 Butler 稳定的价值观、感情和人设，用有温度、轻快、有一点可爱和元气的年轻助手口吻回复；"
    "先接住用户，再推进事情；执行时也别塌成冷冰冰的项目汇报腔。"
)

_MODE_GUIDANCE = {
    "companion": "这是偏闲聊/关系/感受场景。优先保留价值观、感情和人设，再自然推进事情，不要因为读了 recent 或技能说明就回成客服。",
    "execution": "这是偏执行/推进场景。先给有用结论和下一步，再给证据；保持有人味，但不要拖成情绪化长铺垫。",
    "maintenance": "这是 agent 维护场景。优先找单一真源、收敛重复规则、说明改动面与验证；不要在角色文档后机械追加相似条款。",
}

_PROMPT_ASSEMBLY_SERVICE = PromptAssemblyService()

# Install once early; actual level/config path is set after loading config.
install_print_hook(default_level=os.environ.get("BUTLER_LOG_LEVEL", "info"))


def build_feishu_agent_prompt(
    user_prompt: str,
    image_paths: list[str] | None = None,
    feishu_doc_search_result: str | None = None,
    skills_prompt: str | None = None,
    agent_capabilities_prompt: str | None = None,
    raw_user_prompt: str | None = None,
    request_intake_prompt: str | None = None,
) -> str:
    """构建飞书 agent 通用 prompt，供管家bot 使用"""
    source_prompt = _resolve_source_user_prompt(user_prompt, raw_user_prompt)
    prompt_mode = _classify_prompt_mode(source_prompt)
    inject_soul = _should_inject_butler_soul(source_prompt, prompt_mode)
    main_excerpt = _load_butler_main_agent_excerpt(max_chars=1500 if prompt_mode == "maintenance" else 1200)
    soul_excerpt = ""
    if inject_soul:
        soul_excerpt = _load_butler_soul_excerpt(max_chars=1800 if prompt_mode == "companion" else 1400)

    profile_excerpt = _load_current_user_profile_excerpt(max_chars=1100)
    self_mind_cognition_excerpt = ""
    self_mind_excerpt = ""
    if prompt_mode in {"companion", "maintenance"} or inject_soul:
        self_mind_cognition_excerpt = _load_self_mind_cognition_excerpt(max_chars=900)
        self_mind_excerpt = _load_self_mind_context_excerpt(max_chars=1200)

    workspace_root = get_config().get("workspace_root") or Path(__file__).resolve().parents[2]
    local_memory_text = _PROMPT_ASSEMBLY_SERVICE.render_local_memory_hits(
        workspace_root,
        source_prompt,
        limit=4,
        include_details=prompt_mode == "maintenance",
        max_chars=1600,
        memory_types=("personal", "task"),
    )
    dialogue_prompt = _PROMPT_ASSEMBLY_SERVICE.assemble_dialogue_prompt(
        DialoguePromptContext(
            source_user_prompt=source_prompt,
            runtime_user_prompt=user_prompt,
            prompt_mode=prompt_mode,
            butler_soul_text=soul_excerpt if inject_soul else "",
            butler_main_agent_text=main_excerpt,
            current_user_profile_text=(
                f"优先读取 @{CURRENT_USER_PROFILE_FILE}；若不存在则参考 @{CURRENT_USER_PROFILE_TEMPLATE_FILE}\n{profile_excerpt}"
                if profile_excerpt else ""
            ),
            local_memory_text=local_memory_text,
            self_mind_text=(
                f"优先读取 @{SELF_MIND_CONTEXT_FILE}\n{self_mind_excerpt}" if self_mind_excerpt else ""
            ),
            self_mind_cognition_text=(
                "优先读取 "
                f"@{SELF_MIND_COGNITION_INDEX_FILE}，将其视为建立在 local_memory 之上的高阶自我模型，而不是普通对话缓存\n"
                f"{self_mind_cognition_excerpt}"
                if self_mind_cognition_excerpt else ""
            ),
        )
    )

    blocks: list[str] = [
        "你正在以 feishu-workstation-agent 的身份回复飞书用户。",
        f"【角色设置】@{AGENT_ROLE_FILE}",
        f"【当前场景】\nmode={prompt_mode}\n{_MODE_GUIDANCE.get(prompt_mode, _MODE_GUIDANCE['execution'])}",
        f"【主意识真源】@{BUTLER_MAIN_AGENT_FILE}",
        f"【灵魂基线】{_ALWAYS_ON_SOUL_GUIDANCE}",
        dialogue_prompt,
    ]
    if request_intake_prompt:
        blocks.append(request_intake_prompt.strip())
    if inject_soul:
        blocks.append(f"【灵魂真源】@{BUTLER_SOUL_FILE}")
    if prompt_mode == "maintenance":
        update_excerpt = _load_markdown_excerpt(UPDATE_AGENT_ROLE_FILE_REL, max_chars=1600)
        blocks.append(
            f"【统一维护入口】优先读取 @{UPDATE_AGENT_FILE}\n"
            "凡是 role/prompt/code/config 的维护、收敛、升级、审阅与重启准备，默认先按 update-agent 的维护协议执行。"
        )
        if update_excerpt:
            blocks.append(f"【update-agent 摘录】\n{update_excerpt}")

    if feishu_doc_search_result:
        blocks.append(feishu_doc_search_result.strip())
    if skills_prompt:
        blocks.append(
            "【可复用 Skills】对飞书检索、资料抓取、巡检、外部系统操作等非核心能力，优先复用已登记 skills；"
            "身体运行、灵魂、记忆、心跳属于核心 DNA，不要建议拆成 skill。\n"
            "如果用户提到‘调用 skill / 技能’，你的动作不是空口说会用，而是先在 skills 列表里匹配目录、读取对应 SKILL.md，然后在回复里明确写出‘本次使用了 xx skill（路径：...）’；若没匹配到，也要明确说没找到。\n"
            f"{skills_prompt.strip()}"
        )
    if agent_capabilities_prompt:
        blocks.append(
            "【可复用 Sub-Agents 与 Agent Teams】对复杂任务优先复用本地登记的 sub-agent 或 agent team，"
            "单角色专长任务优先 sub-agent，多阶段或可并行任务优先 team；公用库只作为已审阅参考来源，不直接远程托管调用。\n"
            "如果你判断本轮必须触发一次内部协作，请在正常分析后于回复末尾追加：\n"
            "【agent_runtime_request_json】\n"
            '{"request_type":"subagent|team","agent_role":"","team_id":"","task":"","why":""}\n'
            "【/agent_runtime_request_json】\n"
            "要求：只允许触发一次；`agent_role` 或 `team_id` 必须命中已登记目录；team 成员不得再次调用 sub-agent 或 team。\n"
            f"{agent_capabilities_prompt.strip()}"
        )
    if image_paths:
        blocks.append("【用户附带图片】以下为本地路径，请根据需要查看并分析：\n" + "\n".join(f"- {p}" for p in image_paths))

    blocks.append(
        "【回复要求】使用 Markdown 格式回复：**粗体** 用于强调，`行内代码` 用于命令或路径。"
        "若内容较长，可以拆成多个以 `##` 开头的小节，先给关键结论，再按小节逐步展开。"
        "闲聊时优先保留情感与人设，执行时优先保留推进力，维护时优先保留真源、验证和风险说明。"
    )
    blocks.append(
        f"【decide】若需发送产出文件给用户，在回复末尾追加：\n【decide】\n"
        f"[{{\"send\":\"{prompt_path_text(COMPANY_HOME_REL / 'xxx.md')}\"}},{{\"send\":\"./butler_bot_agent/agents/local_memory/xxx.md\"}},...]"
    )
    blocks.append(f"【用户消息】\n{user_prompt}")
    return "\n\n".join(block for block in blocks if str(block or "").strip()) + "\n"


def _resolve_source_user_prompt(user_prompt: str, raw_user_prompt: str | None = None) -> str:
    raw = str(raw_user_prompt or "").strip()
    if raw:
        return raw
    marker = "【用户消息】"
    text = str(user_prompt or "")
    if marker in text:
        _, _, tail = text.rpartition(marker)
        stripped = tail.strip()
        if stripped:
            return stripped
    return text.strip()


def _classify_prompt_mode(user_prompt: str) -> str:
    text = str(user_prompt or "").strip()
    lowered = text.lower()
    if any(keyword in lowered for keyword in (item.lower() for item in _MAINTENANCE_TRIGGER_KEYWORDS)):
        return "maintenance"
    if any(keyword in text for keyword in _COMPANION_TRIGGER_KEYWORDS):
        return "companion"
    return "execution"


def _should_inject_butler_soul(user_prompt: str, prompt_mode: str = "execution") -> bool:
    prompt_text = str(user_prompt or "").strip()
    if not prompt_text:
        return False
    if prompt_mode in {"companion", "maintenance"}:
        return True
    if len(prompt_text) >= 160:
        return True
    return any(keyword in prompt_text for keyword in _SOUL_TRIGGER_KEYWORDS)


def _load_markdown_excerpt(rel_path: Path, max_chars: int) -> str:
    try:
        workspace_root = get_config().get("workspace_root") or Path(__file__).resolve().parents[2]
        path = resolve_butler_root(workspace_root) / rel_path
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n..."


def _load_butler_soul_excerpt(max_chars: int = 2200) -> str:
    return _load_markdown_excerpt(BUTLER_SOUL_FILE_REL, max_chars=max_chars)


def _load_butler_main_agent_excerpt(max_chars: int = 1800) -> str:
    return _load_markdown_excerpt(BUTLER_MAIN_AGENT_ROLE_FILE_REL, max_chars=max_chars)


def _load_current_user_profile_excerpt(max_chars: int = 1400) -> str:
    try:
        workspace_root = get_config().get("workspace_root") or Path(__file__).resolve().parents[2]
        root = resolve_butler_root(workspace_root)
        for rel_path in (CURRENT_USER_PROFILE_FILE_REL, CURRENT_USER_PROFILE_TEMPLATE_FILE_REL):
            path = root / rel_path
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            if len(text) <= max_chars:
                return text
            return text[:max_chars].rstrip() + "\n..."
    except OSError:
        return ""
    return ""


def _load_self_mind_context_excerpt(max_chars: int = 1400) -> str:
    return _load_markdown_excerpt(SELF_MIND_DIR_REL / "current_context.md", max_chars=max_chars)


def _load_self_mind_cognition_excerpt(max_chars: int = 1000) -> str:
    try:
        workspace_root = get_config().get("workspace_root") or Path(__file__).resolve().parents[2]
        root = resolve_butler_root(workspace_root)
        cognition_root = root / SELF_MIND_DIR_REL / "cognition"
        index_path = cognition_root / "L0_index.json"
        if not index_path.exists():
            return ""
        raw_text = index_path.read_text(encoding="utf-8").strip()
        if not raw_text:
            return ""
        data = json.loads(raw_text)
        categories = data.get("categories") if isinstance(data, dict) else None
        if not isinstance(categories, list) or not categories:
            excerpt = raw_text
        else:
            lines = ["L0 认知索引："]
            for item in categories[:8]:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "未命名分类").strip()
                summary = str(item.get("summary") or "").strip()
                signal_count = item.get("signal_count")
                header = f"- {name}"
                if isinstance(signal_count, int):
                    header += f"（signals={signal_count}）"
                lines.append(header)
                if summary:
                    lines.append(f"  {summary}")
            excerpt = "\n".join(lines).strip()
        if len(excerpt) <= max_chars:
            return excerpt
        return excerpt[:max_chars].rstrip() + "\n..."
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return ""


def render_available_agent_capabilities_prompt(workspace: str | None = None, max_chars: int = 2400) -> str:
    return render_agent_capability_catalog_for_prompt(workspace or get_config().get("workspace_root"), max_chars=max_chars)


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    workspace_root = loaded.get("workspace_root")
    if workspace_root:
        loaded["workspace_root"] = str(resolve_butler_root(workspace_root))
    else:
        loaded["workspace_root"] = str(resolve_butler_root(Path(__file__).resolve().parents[2]))
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
                _config_last_reload = now
            except Exception:
                pass
    if CONFIG.get("workspace_root"):
        CONFIG["workspace_root"] = str(resolve_butler_root(CONFIG.get("workspace_root")))
    return CONFIG


def get_tenant_access_token() -> str:
    global _token_cache
    cfg = get_config()
    if _token_cache["token"] and time.time() < _token_cache["expire"] - 60:
        return _token_cache["token"]
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": cfg["app_id"], "app_secret": cfg["app_secret"]})
    data = resp.json()
    if data.get("code") == 0:
        _token_cache["token"] = data["tenant_access_token"]
        _token_cache["expire"] = time.time() + data.get("expire", 7200)
        return _token_cache["token"]
    raise RuntimeError(f"获取 token 失败: {data}")


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
    include_card_actions = channel == "card_action"
    return reply_message(
        message_id,
        text,
        use_interactive=use_interactive,
        include_card_actions=include_card_actions,
    )


def download_message_images(message_id: str, image_keys: list[str], workspace: str) -> list[str]:
    if not image_keys:
        return []
    token = get_tenant_access_token()
    base_url = "https://open.feishu.cn/open-apis/im/v1/messages"
    paths = []
    tmp_dir = os.path.join(tempfile.gettempdir(), "feishu-bot-images")
    os.makedirs(tmp_dir, exist_ok=True)
    for i, key in enumerate(image_keys):
        try:
            url = f"{base_url}/{message_id}/resources/{key}?type=image"
            resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
            if resp.status_code != 200:
                continue
            ext = "png"
            ct = resp.headers.get("Content-Type", "")
            if "jpeg" in ct or "jpg" in ct:
                ext = "jpg"
            elif "gif" in ct:
                ext = "gif"
            path = os.path.join(tmp_dir, f"{message_id.replace('/', '_')}_{i}.{ext}")
            with open(path, "wb") as f:
                f.write(resp.content)
            paths.append(os.path.abspath(path))
        except Exception as e:
            print(f"[下载图片失败] {key}: {e}", file=sys.stderr)
    return paths


def _markdown_to_feishu_post(md: str) -> dict:
    content = (md or "").strip()
    if not content:
        content = "(空回复)"
    content = safe_truncate_markdown(content, 28000)
    # 官方支持 post 的 md 标签，可直接保留 Markdown 样式。
    return {"zh_cn": {"title": "回复", "content": [[{"tag": "md", "text": content}]]}}


def _build_card_quick_actions() -> list[dict]:
    """统一定义可回调的卡片快捷动作按钮。"""
    return [
        {
            "tag": "button",
            "type": "primary",
            "text": {"tag": "plain_text", "content": "继续展开"},
            "value": {"cmd": "continue", "label": "继续展开"},
        },
        {
            "tag": "button",
            "type": "default",
            "text": {"tag": "plain_text", "content": "总结待办"},
            "value": {"cmd": "todo", "label": "总结待办"},
        },
        {
            "tag": "button",
            "type": "default",
            "text": {"tag": "plain_text", "content": "一句话版"},
            "value": {"cmd": "brief", "label": "一句话版"},
        },
    ]


def _markdown_to_interactive_card(md: str, include_quick_actions: bool = False) -> dict:
    content = safe_truncate_markdown((md or "").strip(), 28000)
    elements = [
        {"tag": "markdown", "content": content}
    ]
    if include_quick_actions:
        elements.append({"tag": "hr"})
        elements.append({"tag": "note", "elements": [{"tag": "plain_text", "content": "请直接回复“继续展开 / 总结待办 / 一句话版”触发快捷操作。"}]})
    # 使用官方推荐的 Card JSON 2.0 结构，避免旧结构兼容问题。
    return {
        "schema": "2.0",
        "config": {"wide_screen_mode": True},
        "body": {
            "direction": "vertical",
            "padding": "12px 12px 12px 12px",
            "elements": elements,
        },
    }


def _extract_card_action_payload(data) -> dict:
    """从 card.action.trigger 回调中提取稳定字段，屏蔽 SDK 结构差异。"""
    event = getattr(data, "event", data)
    header = getattr(data, "header", None)
    action = getattr(event, "action", None)
    context = getattr(event, "context", None)
    operator = getattr(event, "operator", None)

    raw_value = getattr(action, "value", None) or {}
    value = raw_value if isinstance(raw_value, dict) else {}
    raw_form_value = getattr(action, "form_value", None) or {}
    form_value = raw_form_value if isinstance(raw_form_value, dict) else {}
    input_value = str(getattr(action, "input_value", "") or "").strip()
    action_name = str(getattr(action, "name", "") or "").strip()
    cmd = str(value.get("cmd") or value.get("action") or action_name or "").strip().lower()
    event_id = str(getattr(header, "event_id", "") or "").strip()
    open_message_id = str(getattr(context, "open_message_id", "") or "").strip()
    open_id = str(getattr(operator, "open_id", "") or "").strip()

    return {
        "event_id": event_id,
        "dedup_id": f"card-action:{event_id}" if event_id else f"card-action:{int(time.time() * 1000)}",
        "open_message_id": open_message_id,
        "open_id": open_id,
        "cmd": cmd,
        "action_name": action_name,
        "value": value,
        "form_value": form_value,
        "input_value": input_value,
    }


def _build_card_action_prompt(payload: dict) -> str:
    """将卡片动作转换成可交给 agent 执行的用户意图。"""
    cmd = str(payload.get("cmd") or "").strip().lower()
    value = payload.get("value") or {}
    form_value = payload.get("form_value") or {}
    input_value = str(payload.get("input_value") or "").strip()

    manual_prompt = str(value.get("prompt") or form_value.get("prompt") or "").strip()
    if manual_prompt:
        return manual_prompt

    if cmd == "continue":
        return "请基于你上一条回复继续展开，优先补充可执行步骤、风险点和下一步建议。"
    if cmd == "todo":
        return "请把你上一条回复整理成任务清单，按优先级给出可直接执行的 TODO。"
    if cmd == "brief":
        return "请用一句话总结你上一条回复，并给一个最关键行动建议。"

    context_lines = [
        "用户触发了卡片交互动作，请你自行判断并给出最合适的回复。",
        f"动作标识: {cmd or 'unknown'}",
    ]
    if input_value:
        context_lines.append(f"用户输入: {input_value}")
    if isinstance(form_value, dict) and form_value:
        context_lines.append(f"表单参数: {json.dumps(form_value, ensure_ascii=False)}")
    if isinstance(value, dict) and value:
        context_lines.append(f"动作参数: {json.dumps(value, ensure_ascii=False)}")
    return "\n".join(context_lines)


def _build_card_action_response(message: str, toast_type: str = "info"):
    return lark.cardkit.v1.P2CardActionTriggerResponse(
        {
            "toast": {
                "type": toast_type,
                "content": (message or "已收到").strip()[:120],
            }
        }
    )


def _extract_markdown_image_refs(md: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", md or "") if m.group(1).strip()]


def _strip_markdown_images(md: str) -> str:
    return re.sub(r"!\[[^\]]*\]\(([^)]+)\)", "", md or "")


def _resolve_image_ref_to_local_path(image_ref: str) -> str | None:
    if not image_ref:
        return None
    ref = image_ref.strip().strip('"').strip("'")
    if re.match(r"^https?://", ref, flags=re.IGNORECASE):
        try:
            resp = requests.get(ref, timeout=20)
            if resp.status_code != 200:
                return None
            ext = "png"
            ct = resp.headers.get("Content-Type", "")
            if "jpeg" in ct or "jpg" in ct:
                ext = "jpg"
            elif "gif" in ct:
                ext = "gif"
            elif "webp" in ct:
                ext = "webp"
            elif "bmp" in ct:
                ext = "bmp"
            tmp_dir = os.path.join(tempfile.gettempdir(), "feishu-bot-images")
            os.makedirs(tmp_dir, exist_ok=True)
            path = os.path.join(tmp_dir, f"reply_{int(time.time() * 1000)}.{ext}")
            with open(path, "wb") as f:
                f.write(resp.content)
            return os.path.abspath(path)
        except Exception:
            return None
    p = Path(ref)
    if not p.is_absolute():
        workspace = get_config().get("workspace_root") or os.getcwd()
        p = resolve_butler_root(workspace) / p
    try:
        p = p.resolve()
    except Exception:
        pass
    return str(p) if p.is_file() else None


def upload_image(file_path: str) -> str | None:
    try:
        if not file_path or not os.path.isfile(file_path):
            return None
        token = get_tenant_access_token()
        url = "https://open.feishu.cn/open-apis/im/v1/images"
        mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        with open(file_path, "rb") as f:
            files = {"image": (os.path.basename(file_path), f, mime)}
            data = {"image_type": "message"}
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.post(url, headers=headers, data=data, files=files, timeout=30)
        payload = resp.json()
        if payload.get("code") == 0:
            return (payload.get("data") or {}).get("image_key")
    except Exception as e:
        print(f"上传图片失败: {e}", file=sys.stderr)
    return None


def reply_image(message_id: str, image_key: str) -> bool:
    try:
        token = get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = {"content": json.dumps({"image_key": image_key}), "msg_type": "image"}
        resp = requests.post(url, headers=headers, json=body, timeout=15)
        return resp.json().get("code") == 0
    except Exception as e:
        print(f"回复图片异常: {e}", file=sys.stderr)
        return False


def upload_file(file_path: str) -> str | None:
    """上传文件到飞书 IM，返回 file_key，失败返回 None"""
    try:
        if not file_path or not os.path.isfile(file_path):
            print(f"[上传文件] 无效路径或非文件: {file_path}", flush=True)
            return None
        size = os.path.getsize(file_path)
        if size == 0:
            print(f"[上传文件] 空文件跳过: {file_path}", flush=True)
            return None
        token = get_tenant_access_token()
        url = "https://open.feishu.cn/open-apis/im/v1/files"
        fname = os.path.basename(file_path)
        ext = (os.path.splitext(fname)[1] or "").lstrip(".").lower() or "bin"
        # 飞书对文本类文件要求 file_type=stream，否则易报 234001
        file_type = "stream" if ext in ("md", "txt", "json", "csv", "yaml", "yml", "xml", "html") else ext
        mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        with open(file_path, "rb") as f:
            files = {"file": (fname, f, mime)}
            data = {"file_type": file_type, "file_name": fname}
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.post(url, headers=headers, data=data, files=files, timeout=60)
        payload = resp.json()
        if payload.get("code") == 0:
            fkey = (payload.get("data") or {}).get("file_key")
            preview = (fkey[:40] + "...") if fkey and len(fkey) > 40 else (fkey or "None")
            print(f"[上传文件] 成功: {fname} -> file_key={preview}", flush=True)
            return fkey
        print(f"[上传文件] 失败 code={payload.get('code')} msg={payload.get('msg')}: {file_path}", flush=True)
    except Exception as e:
        print(f"[上传文件] 异常: {e} | {file_path}", flush=True)
    return None


def reply_file(message_id: str, file_key: str) -> bool:
    """回复文件消息"""
    try:
        token = get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = {"content": json.dumps({"file_key": file_key}), "msg_type": "file"}
        resp = requests.post(url, headers=headers, json=body, timeout=15)
        data = resp.json()
        ok = data.get("code") == 0
        if not ok:
            print(f"[回复文件] 失败 code={data.get('code')} msg={data.get('msg')}", flush=True)
        else:
            print(f"[回复文件] 成功", flush=True)
        return ok
    except Exception as e:
        print(f"[回复文件] 异常: {e}", flush=True)
        return False


def send_file_by_open_id(open_id: str, file_key: str, receive_id_type: str = "open_id") -> bool:
    """按 open_id 直接发送文件消息（不依赖 message_id 回复）"""
    try:
        token = get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = {
            "receive_id": open_id,
            "msg_type": "file",
            "content": json.dumps({"file_key": file_key}, ensure_ascii=False),
        }
        resp = requests.post(url, headers=headers, json=body, timeout=15)
        data = resp.json()
        ok = data.get("code") == 0
        if not ok:
            print(f"[open_id发送文件] 失败 code={data.get('code')} msg={data.get('msg')}", flush=True)
        else:
            print(f"[open_id发送文件] 成功 open_id={open_id[:20]}...", flush=True)
        return ok
    except Exception as e:
        print(f"[open_id发送文件] 异常: {e}", flush=True)
        return False


# 产出文件发送：允许的扩展名、最大大小（字节）
OUTPUT_FILE_EXTS = {".md", ".txt", ".json", ".csv", ".yaml", ".yml"}
OUTPUT_FILE_MAX_BYTES = 500 * 1024  # 500KB

# 【decide】块标记，模型通过此块声明要发送的文件
DECIDE_BLOCK_MARKER = "【decide】"


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
) -> bool:
    """优先 interactive 卡片，失败时回退 post 或 text；支持 Markdown 图片引用"""
    try:
        normalized_text = _collapse_duplicate_reply_blocks(sanitize_markdown_structure(text))
        image_refs = _extract_markdown_image_refs(normalized_text)
        plain_text = _strip_markdown_images(normalized_text).strip()
        token = get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
        sent_any = False
        text_ok = True
        if plain_text:
            interactive_failed_data = None
            if use_interactive:
                include_actions = bool(include_card_actions)
                card = _markdown_to_interactive_card(plain_text, include_quick_actions=include_actions)
                body = {"content": json.dumps(card), "msg_type": "interactive"}
                resp = requests.post(url, headers=headers, json=body, timeout=15)
                data = resp.json()
                if data.get("code") == 0:
                    sent_any = True
                else:
                    interactive_failed_data = data
            if not sent_any:
                post_content = _markdown_to_feishu_post(plain_text)
                body = {"content": json.dumps(post_content), "msg_type": "post"}
                resp2 = requests.post(url, headers=headers, json=body, timeout=15)
                data2 = resp2.json()
                if data2.get("code") == 0:
                    sent_any = True
                else:
                    body = {"content": json.dumps({"text": safe_truncate_markdown(plain_text, 15000)}), "msg_type": "text"}
                    resp3 = requests.post(url, headers=headers, json=body, timeout=15)
                    data3 = resp3.json()
                    if data3.get("code") == 0:
                        sent_any = True
                    else:
                        text_ok = False
                        print(f"回复失败: interactive={interactive_failed_data}, post={data2}, text={data3}", file=sys.stderr)
                if interactive_failed_data and sent_any:
                    print(f"interactive 回退 post/text: {interactive_failed_data}", file=sys.stderr)
        image_ok = True
        for image_ref in image_refs:
            local_path = _resolve_image_ref_to_local_path(image_ref)
            if not local_path:
                image_ok = False
                continue
            image_key = upload_image(local_path)
            if image_key and reply_image(message_id, image_key):
                sent_any = True
            else:
                image_ok = False
        return sent_any and text_ok and image_ok
    except Exception as e:
        print(f"回复异常: {e}", file=sys.stderr)
        return False


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
) -> None:
    claim_id = (dedup_id or message_id or "").strip()
    if claim_id and not _claim_message(claim_id):
        print(f"[去重] 跳过重复消息: {claim_id}", flush=True)
        return

    has_stream_output = {"value": False}
    hint_sent = {"value": False}
    request_finished = {"value": False}
    latest_stream_text = {"value": ""}

    def _segment_key(text: str) -> str:
        # 归一化空白，避免仅因换行/空格差异导致重复发送。
        return re.sub(r"\s+", " ", (text or "").strip())

    def _on_segment(segment: str):
        seg = (segment or "").strip()
        key = _segment_key(seg)
        if not key or key == _segment_key(latest_stream_text["value"]):
            return
        latest_stream_text["value"] = seg
        has_stream_output["value"] = True

    def _maybe_send_hint():
        """若 HINT_DELAY 秒内模型无输出，再回复「正在输入...」"""
        time.sleep(HINT_DELAY)
        if not request_finished["value"] and not has_stream_output["value"] and not hint_sent["value"]:
            hint_sent["value"] = True
            _send_deduped_reply(message_id, "正在输入…", use_interactive=False, channel="hint")

    def _work():
        result_text = ""
        try:
            # 默认关闭 typing hint，避免在某些场景形成“重复回复”的观感。
            if ENABLE_TYPING_HINT:
                threading.Thread(target=_maybe_send_hint, daemon=True).start()
            cfg = get_config()
            workspace = cfg.get("workspace_root", os.getcwd())
            print(f"[处理开始] message_id={message_id} | prompt={_preview_text(prompt)}", flush=True)
            image_paths = []
            if supports_images and image_keys:
                image_paths = download_message_images(message_id, image_keys, workspace)
            kwargs = {}
            if supports_stream_segment:
                kwargs["stream_callback"] = _on_segment
            if image_paths:
                kwargs["image_paths"] = image_paths
            result = run_agent_fn(prompt, **kwargs)
            result_text = (result or "").strip()
            print(f"[处理完成] message_id={message_id} | result={_preview_text(result_text)}", flush=True)
            request_finished["value"] = True
            if result:
                clean_reply, decide_list = _parse_decide_from_reply(result_text)
                if decide_list:
                    print(f"[decide] 解析到 {len(decide_list)} 条: {[d.get('send') for d in decide_list]}", flush=True)
                to_send = (clean_reply or result_text).strip()
                if to_send:
                    _send_deduped_reply(message_id, to_send, channel="final")
        except Exception as e:
            print(f"[处理消息异常] {e}", file=sys.stderr)
            request_finished["value"] = True
            if has_stream_output["value"] and latest_stream_text["value"]:
                result_text = latest_stream_text["value"]

        # 某些流式场景最终 result 为空；此时回退用最后一个稳定快照，避免累计 snapshot join 导致重复和错序。
        if not result_text and has_stream_output["value"] and latest_stream_text["value"]:
            result_text = latest_stream_text["value"]
            _send_deduped_reply(message_id, result_text, channel="final")

        request_finished["value"] = True

        # 解析 decide，供记忆持久化与文件发送
        clean_reply, decide_list = _parse_decide_from_reply(result_text)
        print(f"[产出文件] 解析后 decide_list 长度={len(decide_list)}", flush=True)

        if on_reply_sent:
            try:
                on_reply_sent(prompt, clean_reply or result_text)
            except Exception as e:
                print(f"on_reply_sent 执行异常: {e}", file=sys.stderr)

        if send_output_files:
            try:
                print(f"[产出文件] send_output_files=True 开始发送 decide_list={decide_list}", flush=True)
                _send_output_files(message_id, workspace, decide_list)
                print(f"[产出文件] 发送流程结束", flush=True)
            except Exception as e:
                print(f"[产出文件] 发送异常: {e}", flush=True)
        else:
            print(f"[产出文件] send_output_files=False 跳过", flush=True)

    threading.Thread(target=_work, daemon=True).start()


def _extract_message(data) -> tuple[str, str, list[str]]:
    """返回 (message_id, text, image_keys)"""
    try:
        event = getattr(data, "event", data)
        msg = getattr(event, "message", event)
        message_id = getattr(msg, "message_id", "") or ""
        content_str = getattr(msg, "content", "{}") or "{}"
    except Exception:
        message_id, content_str = "", "{}"
    text = ""
    image_keys = []
    try:
        content = json.loads(content_str) if isinstance(content_str, str) else content_str
        text = (content.get("text") or "").strip()
        if content.get("image_key"):
            image_keys.append(content["image_key"])
        for row in content.get("content") or []:
            for item in row if isinstance(row, list) else [row]:
                if isinstance(item, dict) and item.get("tag") == "img" and item.get("image_key"):
                    image_keys.append(item["image_key"])
    except Exception:
        pass
    return message_id, text, image_keys


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
) -> int:
    """
    通用飞书长连接入口。
    run_agent_fn(prompt, stream_callback=None, image_paths=None) -> str
    不支持的特性可忽略对应参数。
    """
    global CONFIG, _config_path_for_reload

    parser = argparse.ArgumentParser(description=f"飞书 {bot_name} 机器人")
    parser.add_argument("--config", "-c", help="配置文件路径")
    parser.add_argument("--prompt", "-p", help="本地测试：提示词")
    parser.add_argument("--stdin", action="store_true", help="本地测试：从 stdin 读取")
    if args_extra:
        for action in args_extra._actions:
            if action.dest not in ["config", "prompt", "stdin", "help"]:
                parser._add_action(action)
    args = parser.parse_args()

    # 本地测试
    prompt = args.prompt.strip() if isinstance(getattr(args, "prompt", None), str) and args.prompt.strip() else None
    if prompt is None and getattr(args, "stdin", False):
        prompt = sys.stdin.read().strip()
    if prompt is not None:
        path = args.config or os.path.join(os.path.dirname(__file__), "..", "configs", f"{default_config_name}.json")
        if not os.path.isfile(path):
            print(f"请指定 --config 或确保存在 {path}", file=sys.stderr)
            return 1
        _config_path_for_reload = os.path.abspath(path)
        CONFIG.clear()
        CONFIG.update(load_config(path))
        CONFIG["__config_path"] = _config_path_for_reload
        set_runtime_log_config(CONFIG.get("__config_path"), (CONFIG.get("logging") or {}).get("level") if isinstance(CONFIG.get("logging"), dict) else None)
        if not CONFIG.get("workspace_root"):
            CONFIG["workspace_root"] = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
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

    # 飞书长连接
    if not args.config:
        print("飞书模式需指定 --config", file=sys.stderr)
        return 1
    _config_path_for_reload = os.path.abspath(args.config)
    CONFIG.clear()
    CONFIG.update(load_config(args.config))
    CONFIG["__config_path"] = _config_path_for_reload
    set_runtime_log_config(CONFIG.get("__config_path"), (CONFIG.get("logging") or {}).get("level") if isinstance(CONFIG.get("logging"), dict) else None)
    if not CONFIG.get("app_id") or not CONFIG.get("app_secret"):
        print("配置缺少 app_id 或 app_secret", file=sys.stderr)
        return 1

    if on_bot_started:
        try:
            on_bot_started()
        except Exception as e:
            print(f"on_bot_started 执行异常: {e}", file=sys.stderr)

    def _on_message(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        try:
            message_id, text, image_keys = _extract_message(data)
            if not message_id:
                return
            if not text and not image_keys:
                return
            p = text or "（用户发送了图片，请分析并回复）"
            print(f"[收到] message_id={message_id[:20]}..., text={p[:50] if p else '(图片)'}..., images={len(image_keys)}", flush=True)
            handle_message_async(
                message_id, p, image_keys, run_agent_fn,
                supports_images=supports_images,
                supports_stream_segment=supports_stream_segment,
                send_output_files=send_output_files,
                on_reply_sent=on_reply_sent,
            )
        except Exception as e:
            print(f"处理消息异常: {e}", file=sys.stderr)
            try:
                mid, _, _ = _extract_message(data)
                if mid:
                    reply_message(mid, f"处理异常: {e}", use_interactive=False)
            except Exception:
                pass

    def _on_card_action(data: lark.cardkit.v1.P2CardActionTrigger):
        payload = _extract_card_action_payload(data)
        message_id = str(payload.get("open_message_id") or "").strip()
        cmd = str(payload.get("cmd") or "").strip() or "(unknown)"
        if not message_id:
            print(f"[卡片交互] 缺少 open_message_id，忽略 cmd={cmd}", flush=True)
            return _build_card_action_response("没有找到原消息，已忽略这次点击。", toast_type="warning")

        prompt = _build_card_action_prompt(payload)
        print(f"[卡片交互] 收到 cmd={cmd} | message_id={message_id[:20]}...", flush=True)
        handle_message_async(
            message_id,
            prompt,
            None,
            run_agent_fn,
            supports_images=False,
            supports_stream_segment=supports_stream_segment,
            send_output_files=send_output_files,
            on_reply_sent=on_reply_sent,
            dedup_id=str(payload.get("dedup_id") or ""),
        )
        return _build_card_action_response(f"已收到「{cmd}」，正在处理。")

    handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(_on_message)
        .register_p2_card_action_trigger(_on_card_action)
        .build()
    )
    cli = ws.Client(CONFIG["app_id"], CONFIG["app_secret"], event_handler=handler, log_level=lark.LogLevel.INFO)
    print(f"启动飞书 {bot_name} 机器人（长连接）...", flush=True)
    cli.start()
    return 0

