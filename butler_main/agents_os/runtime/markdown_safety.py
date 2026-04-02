from __future__ import annotations

import re

_HEADING_NO_SPACE_RE = re.compile(r"(?m)^(#{1,6})([^#\s].*)$")
_HYPHEN_BULLET_NO_SPACE_RE = re.compile(r"(?m)^-(\S)")
_STAR_BULLET_NO_SPACE_RE = re.compile(r"(?m)^\*(?!\*)(?![^\n]{0,80}\*\*)(\S)")
_NUMBERED_NO_SPACE_RE = re.compile(r"(?m)^(\d+)\.(\S)")
_INLINE_HEADING_RE = re.compile(r"(?m)([^\n])\s+(#{1,6}\s)")
_BROKEN_BOLD_LABEL_RE = re.compile(r"(?m)^\*(?P<label>[^\n*]{1,80}?：)\*\*(?P<body>.*)$")
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
    content = _BROKEN_BOLD_LABEL_RE.sub(lambda m: _repair_broken_bold_label_line(m.group("label"), m.group("body")), content)
    content = _HYPHEN_BULLET_NO_SPACE_RE.sub(r"- \1", content)
    content = _STAR_BULLET_NO_SPACE_RE.sub(r"* \1", content)
    content = _NUMBERED_NO_SPACE_RE.sub(r"\1. \2", content)
    content = _collapse_adjacent_duplicate_lines(content)
    content = _drop_tail_repeated_opening(content)
    if looks_like_broken_markdown(content):
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


def _repair_broken_bold_label_line(label: str, body: str) -> str:
    clean_label = re.sub(r"\s+", " ", str(label or "").strip())
    clean_body = str(body or "").strip()
    if clean_body:
        return f"- **{clean_label}** {clean_body}"
    return f"- **{clean_label}**"


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
    tail = content[last_idx:]
    if "\n" not in tail and len(tail) <= len(opening) + 4:
        return content[:last_idx].rstrip()
    return content


__all__ = [
    "looks_like_broken_markdown",
    "normalize_markdown_text",
    "safe_truncate_markdown",
    "sanitize_markdown_structure",
]
