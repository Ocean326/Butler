from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable

from butler_main.chat.config_runtime import load_active_config, resolve_default_config_path
from .bridge import build_bridge_url, serve_weixin_bridge
from .client import DEFAULT_LOGIN_TIMEOUT_MS, run_weixin_bridge_client
from .official import (
    DEFAULT_BRIDGE_BASE_URL,
    DEFAULT_CONTROL_URL,
    DEFAULT_LOGIN_COMMAND,
    OfficialQrLink,
    fetch_bridge_qr_link,
    write_bridge_qr_link_markdown,
    write_qr_link_markdown,
)


def run_chat_weixin_bot(
    *,
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
) -> int:
    del bot_name, supports_images, supports_stream_segment, send_output_files
    del local_test_fn, immediate_receipt_text

    parser = argparse.ArgumentParser(parents=[args_extra] if args_extra is not None else [], add_help=args_extra is None)
    parser.add_argument("--config", "-c", default="", help="配置文件路径；默认加载 butler_bot.json")
    parser.add_argument("--serve-bridge", action="store_true", help="启动本地微信 webhook bridge")
    parser.add_argument("--run-bridge-client", action="store_true", help="用本地 bridge 协议直连微信并持续收发消息")
    parser.add_argument("--bridge-host", default="127.0.0.1", help="bridge 监听 host")
    parser.add_argument("--bridge-port", type=int, default=8789, help="bridge 监听端口")
    parser.add_argument("--bridge-path", default="/weixin/webhook", help="bridge 接收路径")
    parser.add_argument("--bridge-public-base-url", default="", help="bridge 对外暴露的基址；生成给手机扫码的地址时使用")
    parser.add_argument("--weixin-state-dir", default="", help="微信 bridge 状态目录；默认取 WEIXIN_STATE_DIR、BUTLER_WEIXIN_STATE_DIR 或兼容的 OPENCLAW_STATE_DIR")
    parser.add_argument("--bridge-session-file", default="", help="bridge 登录会话缓存文件路径")
    parser.add_argument("--bridge-login-timeout-ms", type=int, default=DEFAULT_LOGIN_TIMEOUT_MS, help="bridge 扫码登录等待超时")
    parser.add_argument("--official-print-qr-link", action="store_true", help="打印本地控制台二维码入口")
    parser.add_argument("--official-write-qr-link", default="", help="把二维码入口 markdown 落盘到指定路径")
    parser.add_argument("--official-print-bridge-qr-link", action="store_true", help="打印 bridge 实时连接二维码入口")
    parser.add_argument("--official-write-bridge-qr-link", default="", help="把 bridge 实时连接二维码入口落盘到指定路径")
    parser.add_argument("--official-bridge-base-url", default="", help="bridge API 根地址")
    parser.add_argument("--official-cdn-base-url", default="", help="bridge 的 CDN 根地址，默认跟 bridge API 一致")
    parser.add_argument("--official-control-url", default=DEFAULT_CONTROL_URL, help="本地控制台地址")
    parser.add_argument("--official-login-command", default=DEFAULT_LOGIN_COMMAND, help="微信登录命令")

    args = parser.parse_args()
    config_path = str(args.config or "").strip() or resolve_default_config_path(default_config_name)
    if not os.path.isfile(config_path):
        print(f"[weixin-runner] config not found: {config_path}", flush=True)
        return 1
    load_active_config(config_path)
    print(f"[weixin-runner] loaded config: {config_path}", flush=True)
    if on_bot_started is not None:
        on_bot_started()

    if args.official_print_qr_link:
        qr_link = OfficialQrLink(
            control_url=str(args.official_control_url or DEFAULT_CONTROL_URL),
            login_command=str(args.official_login_command or DEFAULT_LOGIN_COMMAND),
        )
        print(qr_link.render_markdown(), end="", flush=True)

    if str(args.official_write_qr_link or "").strip():
        target = write_qr_link_markdown(
            args.official_write_qr_link,
            control_url=str(args.official_control_url or DEFAULT_CONTROL_URL),
            login_command=str(args.official_login_command or DEFAULT_LOGIN_COMMAND),
        )
        print(f"[weixin-runner] wrote QR link to {target}", flush=True)

    bridge_api_base_url = str(args.official_bridge_base_url or "").strip() or (
        DEFAULT_BRIDGE_BASE_URL
        if not args.bridge_host and not args.bridge_port
        else f"http://{str(args.bridge_host or '127.0.0.1').strip()}:{int(args.bridge_port)}/"
    )
    bridge_cdn_base_url = str(args.official_cdn_base_url or "").strip() or bridge_api_base_url

    if args.official_print_bridge_qr_link:
        qr_link = fetch_bridge_qr_link(
            bridge_api_base_url,
            cdn_base_url=bridge_cdn_base_url,
            login_command=str(args.official_login_command or DEFAULT_LOGIN_COMMAND),
        )
        print(qr_link.render_markdown(), end="", flush=True)

    if str(args.official_write_bridge_qr_link or "").strip():
        target = write_bridge_qr_link_markdown(
            args.official_write_bridge_qr_link,
            bridge_base_url=bridge_api_base_url,
            cdn_base_url=bridge_cdn_base_url,
            login_command=str(args.official_login_command or DEFAULT_LOGIN_COMMAND),
        )
        print(f"[weixin-runner] wrote bridge QR link to {target}", flush=True)

    if args.run_bridge_client:
        return run_weixin_bridge_client(
            run_agent_fn=run_agent_fn,
            bridge_base_url=str(args.official_bridge_base_url or "").strip(),
            cdn_base_url=str(args.official_cdn_base_url or "").strip(),
            state_dir=str(args.weixin_state_dir or "").strip(),
            session_file=str(args.bridge_session_file or "").strip(),
            login_timeout_ms=int(args.bridge_login_timeout_ms or DEFAULT_LOGIN_TIMEOUT_MS),
            on_reply_sent=on_reply_sent,
        )

    if args.serve_bridge:
        return serve_weixin_bridge(
            run_agent_fn=run_agent_fn,
            host=str(args.bridge_host or "127.0.0.1"),
            port=int(args.bridge_port),
            path=str(args.bridge_path or "/weixin/webhook"),
            public_base_url=str(args.bridge_public_base_url or "").strip(),
        )

    print(
        "[weixin-runner] no runtime action requested; use "
        "--serve-bridge, --run-bridge-client, --official-print-qr-link, or --official-write-qr-link",
        flush=True,
    )
    print(
        f"[weixin-runner] suggested bridge URL: {build_bridge_url(host=args.bridge_host, port=args.bridge_port, path=args.bridge_path)}",
        flush=True,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    from butler_main.chat import engine as chat_engine

    previous_argv = sys.argv
    if argv is not None:
        sys.argv = [previous_argv[0], *argv]
    try:
        return run_chat_weixin_bot(
            default_config_name="butler_bot",
            bot_name="管家bot",
            run_agent_fn=chat_engine.run_agent,
        )
    finally:
        sys.argv = previous_argv


__all__ = ["main", "run_chat_weixin_bot"]
