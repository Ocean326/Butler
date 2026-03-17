from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from butler_paths import (
    BOOTSTRAP_EXECUTOR_FILE_REL,
    BOOTSTRAP_HEARTBEAT_FILE_REL,
    BOOTSTRAP_MEMORY_POLICY_FILE_REL,
    BOOTSTRAP_SELF_MIND_FILE_REL,
    BOOTSTRAP_SOUL_FILE_REL,
    BOOTSTRAP_TALK_FILE_REL,
    BOOTSTRAP_TOOLS_FILE_REL,
    BOOTSTRAP_USER_FILE_REL,
    resolve_butler_root,
)


@dataclass(frozen=True)
class BootstrapBundle:
    session_type: str
    soul: str = ""
    talk: str = ""
    heartbeat: str = ""
    executor: str = ""
    self_mind: str = ""
    user: str = ""
    tools: str = ""
    memory_policy: str = ""

    def render(self) -> str:
        blocks: list[str] = []
        if self.soul:
            blocks.append("【Bootstrap:SOUL】\n" + self.soul)
        if self.talk:
            blocks.append("【Bootstrap:TALK】\n" + self.talk)
        if self.heartbeat:
            blocks.append("【Bootstrap:HEARTBEAT】\n" + self.heartbeat)
        if self.executor:
            blocks.append("【Bootstrap:EXECUTOR】\n" + self.executor)
        if self.self_mind:
            blocks.append("【Bootstrap:SELF_MIND】\n" + self.self_mind)
        if self.user:
            blocks.append("【Bootstrap:USER】\n" + self.user)
        if self.tools:
            blocks.append("【Bootstrap:TOOLS】\n" + self.tools)
        if self.memory_policy:
            blocks.append("【Bootstrap:MEMORY_POLICY】\n" + self.memory_policy)
        return "\n\n".join(blocks).strip()


class BootstrapLoaderService:
    def load_for_session(self, session_type: str, workspace_root: str | Path, *, max_chars: int = 1800) -> BootstrapBundle:
        kind = str(session_type or "").strip().lower()
        root = resolve_butler_root(workspace_root)
        read = lambda rel: self._read_excerpt(root / rel, max_chars=max_chars)

        if kind == "talk":
            return BootstrapBundle(
                session_type=kind,
                soul=read(BOOTSTRAP_SOUL_FILE_REL),
                talk=read(BOOTSTRAP_TALK_FILE_REL),
                user=read(BOOTSTRAP_USER_FILE_REL),
                tools=read(BOOTSTRAP_TOOLS_FILE_REL),
                memory_policy=read(BOOTSTRAP_MEMORY_POLICY_FILE_REL),
            )
        if kind == "heartbeat_planner":
            return BootstrapBundle(
                session_type=kind,
                heartbeat=read(BOOTSTRAP_HEARTBEAT_FILE_REL),
                tools=read(BOOTSTRAP_TOOLS_FILE_REL),
                memory_policy=read(BOOTSTRAP_MEMORY_POLICY_FILE_REL),
            )
        if kind == "heartbeat_executor":
            return BootstrapBundle(
                session_type=kind,
                executor=read(BOOTSTRAP_EXECUTOR_FILE_REL),
                tools=read(BOOTSTRAP_TOOLS_FILE_REL),
                memory_policy=read(BOOTSTRAP_MEMORY_POLICY_FILE_REL),
            )
        if kind in {"self_mind_cycle", "self_mind_chat"}:
            return BootstrapBundle(
                session_type=kind,
                soul=read(BOOTSTRAP_SOUL_FILE_REL),
                self_mind=read(BOOTSTRAP_SELF_MIND_FILE_REL),
                user=read(BOOTSTRAP_USER_FILE_REL),
                memory_policy=read(BOOTSTRAP_MEMORY_POLICY_FILE_REL),
            )
        return BootstrapBundle(session_type=kind)

    def _read_excerpt(self, path: Path, *, max_chars: int = 1800) -> str:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "\n..."
