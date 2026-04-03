from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from butler_main.chat.cli.runner import run_chat_cli


@dataclass(slots=True)
class _LoadedChatRuntime:
    run_agent_fn: Callable[..., str]
    on_reply_sent: Callable[[str, str], None] | None
    on_bot_started: Callable[[], None] | None


class LazyCliRuntime:
    """Lightweight CLI bootstrap that defers heavy chat engine import until needed."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded: _LoadedChatRuntime | None = None

    def _load(self) -> _LoadedChatRuntime:
        loaded = self._loaded
        if loaded is not None:
            return loaded
        with self._lock:
            loaded = self._loaded
            if loaded is not None:
                return loaded
            from butler_main.chat import engine as chat_engine

            loaded = _LoadedChatRuntime(
                run_agent_fn=chat_engine.run_agent,
                on_reply_sent=chat_engine._after_reply_persist_memory_async,
                on_bot_started=chat_engine._memory_provider().start_background_services,
            )
            self._loaded = loaded
            return loaded

    def warmup_async(self) -> None:
        threading.Thread(target=self._load, name="butler-cli-warmup", daemon=True).start()

    def build_run_agent(self) -> Callable[..., str]:
        def _run_agent(prompt: str, **kwargs) -> str:
            return self._load().run_agent_fn(prompt, **kwargs)

        def _describe_runtime_target(prompt: str, invocation_metadata: dict | None = None) -> dict:
            loaded = self._loaded
            if loaded is None:
                try:
                    from butler_main.chat import engine as chat_engine

                    return dict(chat_engine.describe_runtime_target(prompt, invocation_metadata=invocation_metadata) or {})
                except Exception:
                    return {"kind": "run", "cli": "codex", "model": "auto", "prompt": str(prompt or "").strip()}
            describe_runtime = getattr(loaded.run_agent_fn, "describe_runtime_target", None)
            if callable(describe_runtime):
                return dict(describe_runtime(prompt, invocation_metadata=invocation_metadata) or {})
            return {"kind": "run", "cli": "codex", "model": "auto", "prompt": str(prompt or "").strip()}

        _run_agent.describe_runtime_target = _describe_runtime_target  # type: ignore[attr-defined]
        return _run_agent

    def on_bot_started(self) -> None:
        loaded = self._load()
        if callable(loaded.on_bot_started):
            loaded.on_bot_started()

    def on_reply_sent(self, user_prompt: str, assistant_reply: str) -> None:
        loaded = self._load()
        if callable(loaded.on_reply_sent):
            loaded.on_reply_sent(user_prompt, assistant_reply)


def main(argv: list[str] | None = None) -> int:
    runtime = LazyCliRuntime()
    return run_chat_cli(
        default_config_name="butler_bot",
        bot_name="管家bot",
        run_agent_fn=runtime.build_run_agent(),
        on_bot_started=runtime.on_bot_started,
        on_reply_sent=runtime.on_reply_sent,
        argv=argv,
    )


__all__ = ["LazyCliRuntime", "main"]
