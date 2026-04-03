from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Sequence

from textual.suggester import Suggester


_ASSET_KEY_RE = r"(?:template|builtin|instance):[A-Za-z0-9_.-]+"
_MENTION_SUFFIX_RE = re.compile(rf"(^|\s)\$(?P<token>[^\s]*)$")
_MENTION_ANY_RE = re.compile(rf"(^|\s)\$(?P<asset>{_ASSET_KEY_RE})\b")
_BARE_PREFIX_RE = re.compile(rf"^\s*(?P<asset>{_ASSET_KEY_RE})\b")
_INVALID_MENTION_RE = re.compile(r"(?P<prefix>^|\s)\$(?P<token>[^\s]+)")
_DANGLING_DOLLAR_RE = re.compile(r"(^|\s)\$(?=\s|$)")


@dataclass(slots=True)
class ManagePromptRequest:
    raw_text: str
    instruction: str
    manage_target: str
    explicit_target: bool = False


class FlowCommandSuggester(Suggester):
    def __init__(
        self,
        *,
        command_provider: Callable[[], list[str]],
        asset_provider: Callable[[], list[str]],
        asset_index_provider: Callable[[], int],
        case_sensitive: bool = False,
    ) -> None:
        super().__init__(use_cache=False, case_sensitive=True)
        self._command_provider = command_provider
        self._asset_provider = asset_provider
        self._asset_index_provider = asset_index_provider
        self._case_sensitive = bool(case_sensitive)

    def _first_match(self, value: str, options: list[str]) -> str | None:
        if not options:
            return None
        if self._case_sensitive:
            for option in options:
                if option.startswith(value):
                    return option
            return None
        folded = value.casefold()
        for option in options:
            if option.casefold().startswith(folded):
                return option
        return None

    def _asset_candidates(self, token: str) -> list[str]:
        return asset_candidates(asset_keys=self._asset_provider(), token=token, case_sensitive=self._case_sensitive)

    async def get_suggestion(self, value: str) -> str | None:
        if value.startswith("/"):
            return self._first_match(value, list(self._command_provider()))
        token = manage_prompt_token(value)
        if not token and not has_manage_prompt_token(value):
            return None
        candidates = self._asset_candidates(token)
        if not candidates:
            return None
        index = max(0, min(int(self._asset_index_provider()), len(candidates) - 1))
        replaced, _ = replace_manage_prompt_token(value, candidates[index], trailing_space=False)
        return replaced


@dataclass(slots=True)
class ManageMentionPickerState:
    token: str = ""
    candidates: tuple[str, ...] = ()
    selected_index: int = 0
    visible_limit: int = 7

    @property
    def is_open(self) -> bool:
        return bool(self.candidates)

    @property
    def selected_candidate(self) -> str:
        if not self.candidates:
            return ""
        index = max(0, min(self.selected_index, len(self.candidates) - 1))
        return self.candidates[index]

    @property
    def visible_height(self) -> int:
        if not self.is_open:
            return 0
        return min(len(self.candidates), max(1, int(self.visible_limit or 7)))

    def update(self, *, text: str, asset_keys: Sequence[str]) -> None:
        token = manage_prompt_token(text)
        candidates = tuple(asset_candidates(asset_keys=asset_keys, token=token, case_sensitive=False)) if (token or has_manage_prompt_token(text)) else ()
        if token != self.token:
            self.selected_index = 0
        self.token = token
        self.candidates = candidates
        if not self.candidates:
            self.selected_index = 0
            return
        self.selected_index = max(0, min(self.selected_index, len(self.candidates) - 1))

    def move(self, delta: int) -> None:
        if not self.candidates:
            return
        self.selected_index = (self.selected_index + int(delta or 0)) % len(self.candidates)

    def close(self) -> None:
        self.token = ""
        self.candidates = ()
        self.selected_index = 0

    def render_text(self) -> str:
        if not self.candidates:
            return ""
        start = 0
        limit = self.visible_height
        if len(self.candidates) > limit:
            half = limit // 2
            start = max(0, min(self.selected_index - half, len(self.candidates) - limit))
        lines: list[str] = []
        for index, asset_key in enumerate(self.candidates[start : start + limit], start=start):
            marker = "›" if index == self.selected_index else " "
            lines.append(f"{marker} {asset_key}")
        return "\n".join(lines)


def manage_prompt_token(text: str) -> str:
    match = _MENTION_SUFFIX_RE.search(str(text or ""))
    return str(match.group("token") or "") if match else ""


def has_manage_prompt_token(text: str) -> bool:
    return _MENTION_SUFFIX_RE.search(str(text or "")) is not None


def asset_candidates(*, asset_keys: Sequence[str], token: str, case_sensitive: bool = False) -> list[str]:
    options = [str(item or "").strip() for item in list(asset_keys or []) if str(item or "").strip()]
    if not token:
        return options
    if case_sensitive:
        return [option for option in options if option.startswith(token)]
    folded = token.casefold()
    return [option for option in options if option.casefold().startswith(folded)]


def replace_manage_prompt_token(text: str, asset_key: str, *, trailing_space: bool = True) -> tuple[str, bool]:
    raw = str(text or "")
    replacement = f"${str(asset_key or '').strip()}"
    if trailing_space:
        replacement = f"{replacement} "
    match = _MENTION_SUFFIX_RE.search(raw)
    if not match:
        return raw, False
    updated = raw[: match.start()] + f"{match.group(1) or ''}{replacement}"
    return updated, True


def sanitize_manage_prompt(text: str) -> str:
    raw = str(text or "")
    if not raw:
        return ""

    def _replace(match: re.Match[str]) -> str:
        prefix = str(match.group("prefix") or "")
        token = str(match.group("token") or "").strip()
        if re.fullmatch(_ASSET_KEY_RE, token):
            return f"{prefix}${token}"
        return f"{prefix}{token}"

    sanitized = _INVALID_MENTION_RE.sub(_replace, raw)
    sanitized = _DANGLING_DOLLAR_RE.sub(lambda match: str(match.group(1) or ""), sanitized)
    return sanitized.strip()


def split_manage_prompt(text: str) -> tuple[str, str]:
    raw = sanitize_manage_prompt(text)
    if not raw:
        return "", ""
    match = _MENTION_ANY_RE.search(raw)
    if match:
        asset_key = str(match.group("asset") or "").strip()
        instruction = (raw[: match.start()] + raw[match.end() :]).strip()
        return asset_key, instruction
    prefix = _BARE_PREFIX_RE.match(raw)
    if prefix:
        asset_key = str(prefix.group("asset") or "").strip()
        instruction = raw[prefix.end() :].strip()
        return asset_key, instruction
    return "", raw


def parse_manage_prompt(text: str, *, active_asset_key: str = "") -> ManagePromptRequest:
    raw = sanitize_manage_prompt(text)
    asset_key, instruction = split_manage_prompt(raw)
    manage_target = str(asset_key or active_asset_key or "").strip()
    return ManagePromptRequest(
        raw_text=raw,
        instruction=str(instruction or ("" if asset_key else raw)).strip(),
        manage_target=manage_target,
        explicit_target=bool(asset_key),
    )
