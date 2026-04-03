from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from butler_main.repo_layout import LEGACY_CHAT_REL, PRODUCT_CHAT_REL

from .assets import (
    CHAT_BOOTSTRAP_CHAT_FILE_REL,
    CHAT_BOOTSTRAP_MEMORY_POLICY_FILE_REL,
    CHAT_BOOTSTRAP_SOUL_FILE_REL,
    CHAT_BOOTSTRAP_TALK_FILE_REL,
    CHAT_BOOTSTRAP_TOOLS_FILE_REL,
    CHAT_BOOTSTRAP_USER_FILE_REL,
)
from .pathing import resolve_butler_root


@dataclass(frozen=True)
class ChatBootstrapBundle:
    soul: str = ""
    talk: str = ""
    user: str = ""
    tools: str = ""
    memory_policy: str = ""


def load_chat_bootstrap(workspace_root: str | Path, *, max_chars: int = 1800) -> ChatBootstrapBundle:
    root = resolve_butler_root(workspace_root)
    return ChatBootstrapBundle(
        soul=_read_first_available(root, [CHAT_BOOTSTRAP_SOUL_FILE_REL], max_chars=max_chars),
        talk=_read_first_available(root, [CHAT_BOOTSTRAP_CHAT_FILE_REL, CHAT_BOOTSTRAP_TALK_FILE_REL], max_chars=max_chars),
        user=_read_first_available(root, [CHAT_BOOTSTRAP_USER_FILE_REL], max_chars=max_chars),
        tools=_read_first_available(root, [CHAT_BOOTSTRAP_TOOLS_FILE_REL], max_chars=max_chars),
        memory_policy=_read_first_available(root, [CHAT_BOOTSTRAP_MEMORY_POLICY_FILE_REL], max_chars=max_chars),
    )


def _read_excerpt(path: Path, *, max_chars: int = 1800) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n..."


def _read_first_available(root: Path, rel_paths: list[Path], *, max_chars: int = 1800) -> str:
    for rel in rel_paths:
        candidates = [rel]
        rel_text = rel.as_posix()
        product_prefix = PRODUCT_CHAT_REL.as_posix()
        legacy_prefix = LEGACY_CHAT_REL.as_posix()
        if rel_text.startswith(product_prefix):
            candidates.append(Path(rel_text.replace(product_prefix, legacy_prefix, 1)))
        elif rel_text.startswith(legacy_prefix):
            candidates.append(Path(rel_text.replace(legacy_prefix, product_prefix, 1)))
        for candidate_rel in candidates:
            text = _read_excerpt(root / candidate_rel, max_chars=max_chars)
            if text:
                return text
    return ""


__all__ = ["ChatBootstrapBundle", "load_chat_bootstrap"]
