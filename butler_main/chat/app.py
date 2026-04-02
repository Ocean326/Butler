from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Any, Callable

from butler_main.agents_os.runtime.provider_interfaces import MemoryRuntimeProvider, PromptRuntimeProvider


def run_chat_cli(**kwargs) -> int:
    from butler_main.chat.cli import run_chat_cli as _runner

    return _runner(**kwargs)


def run_chat_feishu_bot(**kwargs) -> int:
    from butler_main.chat.feishu_bot import run_chat_feishu_bot as _runner

    return _runner(**kwargs)


def run_chat_weixin_bot(**kwargs) -> int:
    from butler_main.chat.weixi import run_chat_weixin_bot as _runner

    return _runner(**kwargs)


@dataclass(slots=True)
class ChatApp:
    run_agent_fn: Callable[..., str]
    prompt_provider: PromptRuntimeProvider
    memory_provider: MemoryRuntimeProvider
    bot_name: str = "管家bot"
    default_config_name: str = "butler_bot"
    supports_images: bool = True
    supports_stream_segment: bool = True
    send_output_files: bool = True
    immediate_receipt_text: str | None = None
    channel: str = "feishu"
    metadata: dict[str, Any] = field(default_factory=dict)

    def on_bot_started(self) -> None:
        self.memory_provider.start_background_services()

    def on_reply_sent(self, user_prompt: str, assistant_reply: str) -> None:
        callback = self.metadata.get("on_reply_sent_callback")
        if callable(callback):
            callback(user_prompt, assistant_reply)
            return
        self.memory_provider.persist_reply_async(user_prompt, assistant_reply)

    def local_test(self, prompt: str, args: argparse.Namespace) -> str:
        if getattr(args, "stream", False):
            return self.run_agent_fn(prompt, stream_output=True)
        return self.run_agent_fn(prompt)

    def build_arg_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser()
        parser.add_argument("--no-stream", action="store_true", help="本地测试：一次性输出（默认）")
        parser.add_argument("--stream", action="store_true", help="本地测试：流式输出文字到终端")
        parser.add_argument(
            "--interactive",
            "-i",
            action="store_true",
            help="交互式 REPL 模式：持续对话，等价于飞书输入（含后台服务）",
        )
        return parser

    def run(self) -> int:
        runner = self._resolve_channel_runner()
        return runner(
            default_config_name=self.default_config_name,
            bot_name=self.bot_name,
            run_agent_fn=self.run_agent_fn,
            supports_images=self.supports_images,
            supports_stream_segment=self.supports_stream_segment,
            send_output_files=self.send_output_files,
            args_extra=self.build_arg_parser(),
            local_test_fn=self.local_test,
            on_bot_started=self.on_bot_started,
            on_reply_sent=self.on_reply_sent,
            immediate_receipt_text=self.immediate_receipt_text,
        )

    def _resolve_channel_runner(self) -> Callable[..., int]:
        normalized = str(self.channel or "feishu").strip().lower() or "feishu"
        if normalized in {"cli", "terminal", "console", "commandline", "command-line"}:
            return run_chat_cli
        if normalized in {"weixi", "weixin", "wechat"}:
            return run_chat_weixin_bot
        return run_chat_feishu_bot


@dataclass(slots=True, frozen=True)
class ChatAppBootstrap:
    app: ChatApp
    body_module_name: str
    prompt_provider_name: str
    memory_provider_name: str


def create_default_chat_app() -> ChatAppBootstrap:
    from butler_main.chat import engine as chat_engine

    prompt_provider = chat_engine.PROMPT_PROVIDER
    memory_provider = chat_engine.MEMORY_PROVIDER
    app = ChatApp(
        run_agent_fn=chat_engine.run_agent,
        prompt_provider=prompt_provider,
        memory_provider=memory_provider,
        immediate_receipt_text="处理中，{cli} {model} 模型调用中…",
        metadata={"on_reply_sent_callback": chat_engine._after_reply_persist_memory_async},
    )
    return ChatAppBootstrap(
        app=app,
        body_module_name=chat_engine.__name__,
        prompt_provider_name=type(prompt_provider).__name__,
        memory_provider_name=type(memory_provider).__name__,
    )


def create_default_weixi_chat_app() -> ChatAppBootstrap:
    bootstrap = create_default_chat_app()
    bootstrap.app.channel = "weixi"
    bootstrap.app.metadata["channel_layer"] = "weixi"
    return bootstrap


def create_default_cli_chat_app() -> ChatAppBootstrap:
    bootstrap = create_default_chat_app()
    bootstrap.app.channel = "cli"
    bootstrap.app.metadata["channel_layer"] = "cli"
    return bootstrap


def main() -> int:
    return create_default_chat_app().app.run()


__all__ = [
    "ChatApp",
    "ChatAppBootstrap",
    "create_default_chat_app",
    "create_default_cli_chat_app",
    "create_default_weixi_chat_app",
    "main",
]
