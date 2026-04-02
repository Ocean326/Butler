from __future__ import annotations

import shlex
from typing import Any, Callable, Mapping


PermissionMatcher = Callable[[str, str], bool]


def _split_shell_segments(command: str) -> list[str]:
    text = str(command or "")
    segments: list[str] = []
    current: list[str] = []
    quote: str = ""
    escape = False
    index = 0
    length = len(text)

    while index < length:
        char = text[index]
        nxt = text[index + 1] if index + 1 < length else ""

        if escape:
            current.append(char)
            escape = False
            index += 1
            continue

        if char == "\\" and quote != "'":
            current.append(char)
            escape = True
            index += 1
            continue

        if quote:
            current.append(char)
            if char == quote:
                quote = ""
            index += 1
            continue

        if char in {"'", '"'}:
            quote = char
            current.append(char)
            index += 1
            continue

        if char == "$" and nxt == "(":
            depth = 1
            inner: list[str] = []
            index += 2
            while index < length and depth > 0:
                inner_char = text[index]
                inner_next = text[index + 1] if index + 1 < length else ""
                if inner_char == "$" and inner_next == "(":
                    depth += 1
                    inner.append("$(")
                    index += 2
                    continue
                if inner_char == "(":
                    depth += 1
                elif inner_char == ")":
                    depth -= 1
                    if depth == 0:
                        index += 1
                        break
                inner.append(inner_char)
                index += 1
            inner_text = "".join(inner).replace("$(", "(")
            segments.extend(_split_shell_segments(inner_text))
            continue

        if char == ";" or (char == "|" and nxt != "|") or (char == "|" and nxt == "|") or (char == "&" and nxt == "&"):
            segment = "".join(current).strip()
            if segment:
                segments.append(segment)
            current = []
            index += 2 if nxt in {"|", "&"} and char in {"|", "&"} else 1
            continue

        current.append(char)
        index += 1

    segment = "".join(current).strip()
    if segment:
        segments.append(segment)
    return segments


def extract_bash_commands(command: str) -> list[str]:
    commands: list[str] = []
    for segment in _split_shell_segments(command):
        try:
            parts = shlex.split(segment, posix=True)
        except Exception:
            parts = segment.split()
        if not parts:
            continue
        command_name = ""
        for token in parts:
            stripped = str(token or "").strip()
            if not stripped:
                continue
            if "=" in stripped and not stripped.startswith(("/", "./", "../")) and stripped.index("=") > 0:
                continue
            command_name = stripped
            break
        if command_name:
            commands.append(command_name)
    return commands if commands else ([str(command or "").split()[0]] if str(command or "").split() else [])


def matches_bash_permission(command_name: str, pattern: str) -> bool:
    expected = str(pattern or "").strip()
    actual = str(command_name or "").strip()
    if not expected or not actual:
        return False
    if expected == actual:
        return True
    if expected.endswith(" *"):
        return actual == expected[:-2]
    return False


def _extract_permission_pattern(permission_key: str, permission: Mapping[str, Any]) -> str:
    key = str(permission_key or "").strip()
    if key.startswith("Bash(") and key.endswith(")"):
        return key[5:-1]
    if key == "bash":
        when = permission.get("when") if isinstance(permission, Mapping) else None
        if isinstance(when, Mapping):
            return str(when.get("command") or "").strip()
    return key


def check_bash_chain_permissions(
    command: str,
    permissions: Mapping[str, Mapping[str, Any]] | None,
    *,
    matcher: PermissionMatcher | None = None,
) -> tuple[bool, str | None, str | None]:
    if not isinstance(permissions, Mapping):
        return False, None, None
    commands = extract_bash_commands(command)
    if not commands:
        return False, None, None
    compare = matcher or matches_bash_permission
    matched_source = "config"

    for command_name in commands:
        allowed = False
        for permission_key, permission_value in permissions.items():
            if not isinstance(permission_value, Mapping):
                continue
            if not permission_value.get("allowed"):
                continue
            pattern = _extract_permission_pattern(permission_key, permission_value)
            if compare(command_name, pattern):
                matched_source = str(permission_value.get("source") or matched_source)
                allowed = True
                break
        if not allowed:
            return False, None, None

    reason = f"safe chain ({len(commands)} commands)" if len(commands) > 1 else "permitted"
    return True, reason, matched_source
