from __future__ import annotations

import re

_HEADING_NO_SPACE_RE = re.compile(r"(?m)^(#{1,6})([^#\s].*)$")
_BULLET_NO_SPACE_RE = re.compile(r"(?m)^([*-])(\S)")
_NUMBERED_NO_SPACE_RE = re.compile(r"(?m)^(\d+)\.(\S)")
_INLINE_HEADING_RE = re.compile(r"(?m)([^\n])\s+(#{1,6}\s)")
_TAIL_DUP_OPENING_MIN_LEN = 12


def normalize_markdown_text(text: str) -> str:
    normalized = str(text or "").replace("\ufeff", "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    return normalized.strip()


def looks_like_broken_markdown(text: str) -> bool:
    content = normalize_markdown_text(text)
    if not content:
        return False
    if _HEADING_NO_SPACE_RE.search(content):
        return True
    prefix = content[:600]
    if len(prefix) >= 120 and prefix[:80] in prefix[80:]:
        return True
    return False


def sanitize_markdown_structure(text: str) -> str:
    content = normalize_markdown_text(text)
    if not content:
        return ""
    content = _INLINE_HEADING_RE.sub(r"\1\n\2", content)
    content = _HEADING_NO_SPACE_RE.sub(r"\1 \2", content)
    content = _BULLET_NO_SPACE_RE.sub(r"\1 \2", content)
    content = _NUMBERED_NO_SPACE_RE.sub(r"\1. \2", content)
    content = _collapse_adjacent_duplicate_lines(content)
    content = _drop_tail_repeated_opening(content)
    if looks_like_broken_markdown(content):
        # 轻度“去噪”：异常场景下合并连续 3+ 空行为双空行，避免渲染碎裂。
        content = re.sub(r"\n{3,}", "\n\n", content)
    return content


def safe_truncate_markdown(text: str, limit: int, suffix: str = "\n\n...[内容已截断]") -> str:
    content = str(text or "")
    if limit <= 0:
        return ""
    if len(content) <= limit:
        return content

    suffix_text = suffix if len(suffix) < limit else suffix[: max(0, limit // 4)]
    budget = max(1, limit - len(suffix_text))
    window = content[:budget]
    floor = int(budget * 0.7)

    candidates = [
        window.rfind("\n## "),
        window.rfind("\n### "),
        window.rfind("\n\n"),
        window.rfind("\n- "),
        window.rfind("\n1. "),
        window.rfind("\n"),
        window.rfind("。"),
    ]
    cut = max(pos for pos in candidates if pos >= floor) if any(pos >= floor for pos in candidates) else budget
    trimmed = window[:cut].rstrip()

    if trimmed.count("```") % 2 == 1:
        trimmed += "\n```"
    if trimmed.count("`") % 2 == 1 and not trimmed.endswith("`"):
        trimmed += "`"
    return trimmed + suffix_text


def _collapse_adjacent_duplicate_lines(content: str) -> str:
    lines = content.split("\n")
    result: list[str] = []
    previous_key = ""
    for line in lines:
        key = re.sub(r"\s+", " ", line.strip())
        if key and key == previous_key:
            continue
        result.append(line)
        previous_key = key
    return "\n".join(result).strip()


def _drop_tail_repeated_opening(content: str) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return content
    opening = lines[0]
    if len(opening) < _TAIL_DUP_OPENING_MIN_LEN:
        return content
    first_idx = content.find(opening)
    last_idx = content.rfind(opening)
    if first_idx != 0 or last_idx <= first_idx:
        return content
    if last_idx < int(len(content) * 0.6):
        return content
    # 仅处理尾部独立重复开头语，避免误删正文中的正常引用。
    tail = content[last_idx:]
    if "\n" not in tail and len(tail) <= len(opening) + 4:
        return content[:last_idx].rstrip()
    return content
