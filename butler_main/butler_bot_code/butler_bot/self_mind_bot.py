# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import os
import sys
from typing import Callable

from agent import load_config, run_feishu_bot_with_loaded_config
from memory_manager import MemoryManager
from runtime import cli_runtime as cli_runtime_service
from utils.markdown_safety import safe_truncate_markdown, sanitize_markdown_structure


SELF_MIND_CONFIG: dict = {}


def _config() -> dict:
    return dict(SELF_MIND_CONFIG)


def _run_model(prompt: str, workspace: str, timeout: int, model: str) -> tuple[str, bool]:
    cfg = _config()
    memory_cfg = ((cfg or {}).get("memory") or {}).get("self_mind") or {}
    runtime_request = {
        "cli": str(memory_cfg.get("chat_cli") or memory_cfg.get("cycle_cli") or "cursor").strip() or "cursor",
        "model": str(model or memory_cfg.get("chat_model") or memory_cfg.get("cycle_model") or cfg.get("agent_model") or "auto").strip() or "auto",
    }
    return cli_runtime_service.run_prompt(prompt, workspace, timeout, cfg, runtime_request, stream=False)


MEMORY = MemoryManager(config_provider=_config, run_model_fn=_run_model)


def run_agent(
    user_prompt: str,
    stream_callback: Callable[[str], None] | None = None,
    image_paths: list[str] | None = None,
) -> str:
    del image_paths
    cfg = _config()
    workspace = str(cfg.get("workspace_root") or os.getcwd())
    timeout = int(cfg.get("agent_timeout", 300))
    self_mind_cfg = ((cfg or {}).get("memory") or {}).get("self_mind") or {}
    model = str(self_mind_cfg.get("chat_model") or self_mind_cfg.get("cycle_model") or cfg.get("agent_model") or "auto").strip() or "auto"
    prompt_text = str(user_prompt or "").strip()
    if not prompt_text:
        return "我在。"

    MEMORY._append_self_mind_listener_turn(workspace, prompt_text, "", source="listener_inbound")
    prompt = MEMORY._build_self_mind_chat_prompt(workspace, prompt_text)
    out, ok = _run_model(prompt, workspace, timeout, model)
    reply = sanitize_markdown_structure(out if ok and out else (out or "这轮我有点卡住了，但我还在。"))
    reply = safe_truncate_markdown(reply, int(cfg.get("max_reply_len", 12000)))
    MEMORY._append_self_mind_listener_turn(workspace, prompt_text, reply, source="listener_reply")
    MEMORY._append_self_mind_log(
        workspace,
        "self_mind_listener_reply",
        {
            "message_preview": reply[:220],
            "self_mind_note": prompt_text[:220],
            "share_type": "listener_chat",
        },
    )
    MEMORY._refresh_self_mind_context(
        workspace,
        {"status": "chatting", "share_type": "listener_chat", "candidate": reply[:220]},
        last_event="self_mind_listener_chat",
        rendered_text=reply,
    )
    if stream_callback:
        stream_callback(reply)
    return reply


def main() -> int:
    parser = argparse.ArgumentParser(description="self_mind 独立飞书机器人")
    parser.add_argument("--config", "-c", required=True, help="主配置文件路径")
    args = parser.parse_args()

    loaded = load_config(args.config)
    loaded["__config_path"] = os.path.abspath(args.config)
    settings = ((loaded or {}).get("memory") or {}).get("self_mind") or {}
    app_id = str(settings.get("listener_app_id") or settings.get("talk_app_id") or "").strip()
    app_secret = str(settings.get("listener_app_secret") or settings.get("talk_app_secret") or "").strip()
    if not app_id or not app_secret:
        print("self_mind listener 缺少 app_id/app_secret", file=sys.stderr)
        return 1

    SELF_MIND_CONFIG.clear()
    SELF_MIND_CONFIG.update(loaded)
    SELF_MIND_CONFIG["app_id"] = app_id
    SELF_MIND_CONFIG["app_secret"] = app_secret
    return run_feishu_bot_with_loaded_config(
        SELF_MIND_CONFIG,
        bot_name="self_mind",
        run_agent_fn=run_agent,
        supports_images=False,
        supports_stream_segment=False,
        send_output_files=False,
        immediate_receipt_text="我在，先接住这句，马上回你。",
    )


if __name__ == "__main__":
    raise SystemExit(main())
