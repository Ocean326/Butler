from __future__ import annotations

import re
from dataclasses import dataclass, replace

from agents_os.contracts import OutputBundle, TextBlock


@dataclass(frozen=True, slots=True)
class ChannelProfile:
    channel: str
    surface: str
    user_label: str
    dialogue_label: str
    can_receive_images: bool
    can_send_text: bool
    can_send_images: bool
    can_send_files: bool
    can_update_message: bool
    can_stream_updates: bool
    can_use_cards: bool
    allow_decide_send: bool
    prefer_short_paragraphs: bool = True


_GENERIC_PROFILE = ChannelProfile(
    channel="generic",
    surface="chat",
    user_label="聊天界面",
    dialogue_label="通用对话",
    can_receive_images=False,
    can_send_text=True,
    can_send_images=False,
    can_send_files=False,
    can_update_message=False,
    can_stream_updates=False,
    can_use_cards=False,
    allow_decide_send=False,
)

_CHANNEL_PROFILES: dict[str, ChannelProfile] = {
    "cli": ChannelProfile(
        channel="cli",
        surface="terminal",
        user_label="CLI 终端",
        dialogue_label="CLI 对话",
        can_receive_images=False,
        can_send_text=True,
        can_send_images=False,
        can_send_files=False,
        can_update_message=False,
        can_stream_updates=True,
        can_use_cards=False,
        allow_decide_send=False,
    ),
    "feishu": ChannelProfile(
        channel="feishu",
        surface="feishu_chat",
        user_label="飞书聊天",
        dialogue_label="飞书对话",
        can_receive_images=True,
        can_send_text=True,
        can_send_images=True,
        can_send_files=True,
        can_update_message=True,
        can_stream_updates=True,
        can_use_cards=True,
        allow_decide_send=True,
    ),
    "weixin": ChannelProfile(
        channel="weixin",
        surface="weixin_chat",
        user_label="微信聊天",
        dialogue_label="微信对话",
        can_receive_images=False,
        can_send_text=True,
        can_send_images=True,
        can_send_files=True,
        can_update_message=False,
        can_stream_updates=False,
        can_use_cards=False,
        allow_decide_send=True,
    ),
}

_CHANNEL_ALIASES = {
    "command-line": "cli",
    "commandline": "cli",
    "console": "cli",
    "local": "cli",
    "terminal": "cli",
    "wechat": "weixin",
    "weixi": "weixin",
}


def resolve_channel_profile(channel: str | None) -> ChannelProfile:
    normalized = str(channel or "").strip().lower()
    canonical = _CHANNEL_ALIASES.get(normalized, normalized) or "generic"
    profile = _CHANNEL_PROFILES.get(canonical)
    if profile is not None:
        return profile
    return replace(_GENERIC_PROFILE, channel=canonical or _GENERIC_PROFILE.channel)


def render_channel_prompt_block(profile: ChannelProfile) -> str:
    lines = [
        f"- {profile.dialogue_label}",
        f"- 对话形态：{_render_primary_surface(profile)}",
        f"- 直接交付：{_render_direct_delivery(profile)}",
    ]
    extra = _render_channel_extra_hint(profile)
    if extra:
        lines.append(f"- 回复取向：{extra}")
    return "【当前对话】\n" + "\n".join(lines)


def render_channel_reply_requirements(profile: ChannelProfile) -> str:
    if profile.channel == "cli":
        return "直接按 CLI 对话组织结果，优先给结论、步骤、命令和路径；不要假设存在卡片、附件面板或富文本容器。"
    if profile.channel == "weixin":
        return "直接按微信对话组织结果，优先短段落、轻量结论和直接行动建议；纯文本里优先保留清晰结构，可用【标题】、短列表和留白提升可读性；不要使用飞书卡片语气。"
    if profile.channel == "feishu":
        return "直接按飞书对话组织结果；可以自然使用分段、小标题、列表，以及在必要时配合图片、文件和后续补充。"
    return "优先用清楚、可直接消费的文本完成回复。"


def normalize_output_bundle_for_channel(bundle: OutputBundle, profile: ChannelProfile) -> OutputBundle:
    normalized_cards = list(bundle.cards) if profile.can_use_cards else []
    normalized_images = list(bundle.images) if profile.can_send_images else []
    normalized_files = list(bundle.files) if profile.can_send_files and profile.allow_decide_send else []
    normalized_text_blocks = list(bundle.text_blocks)
    metadata = dict(bundle.metadata or {})
    dropped: list[str] = []
    if bundle.cards and not profile.can_use_cards:
        dropped.append("cards")
    if bundle.images and not profile.can_send_images:
        dropped.append("images")
    if bundle.files and not (profile.can_send_files and profile.allow_decide_send):
        dropped.append("files")
    if profile.channel == "weixin":
        normalized_text_blocks = _normalize_weixin_text_blocks(bundle.text_blocks)
        if normalized_text_blocks != list(bundle.text_blocks):
            metadata["text_normalized_for_channel"] = profile.channel
    metadata["channel_profile"] = profile.channel
    if dropped:
        metadata["normalized_away"] = ",".join(dropped)
    return replace(
        bundle,
        text_blocks=normalized_text_blocks,
        cards=normalized_cards,
        images=normalized_images,
        files=normalized_files,
        metadata=metadata,
    )


def _normalize_weixin_text_blocks(blocks: list[TextBlock]) -> list[TextBlock]:
    normalized: list[TextBlock] = []
    for block in blocks:
        text = _normalize_weixin_text(block.text)
        normalized.append(replace(block, text=text, style="plain"))
    return normalized


def _normalize_weixin_text(text: str) -> str:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"```[^\n`]*\n(.*?)```", lambda match: f"\n{match.group(1).strip()}\n", normalized, flags=re.DOTALL)
    normalized = re.sub(r"`([^`\n]+)`", r"\1", normalized)
    normalized = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _replace_markdown_image, normalized)
    normalized = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _replace_markdown_link, normalized)
    normalized = re.sub(r"^\s*>\s?", "", normalized, flags=re.MULTILINE)
    normalized = re.sub(r"^\s*[-*+]\s+", "- ", normalized, flags=re.MULTILINE)
    normalized = re.sub(r"^\s*(\d+)[\.)]\s+", r"\1. ", normalized, flags=re.MULTILINE)
    normalized = re.sub(r"^\s*([-*_])(?:\s*\1){2,}\s*$", "", normalized, flags=re.MULTILINE)
    normalized = re.sub(r"(\*\*|__)(.*?)\1", r"\2", normalized)
    normalized = re.sub(r"(?<!\*)\*(?!\*)([^*\n]+)(?<!\*)\*(?!\*)", r"\1", normalized)
    normalized = re.sub(r"~~(.*?)~~", r"\1", normalized)
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    lines: list[str] = []
    for raw_line in normalized.split("\n"):
        line = str(raw_line or "").strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        heading_match = re.match(r"^\s{0,3}#{1,6}\s*(.+?)\s*$", raw_line)
        if heading_match:
            lines.append(_render_weixin_bracket_title(heading_match.group(1)))
            continue
        label_with_body_match = re.match(r"^([A-Za-z0-9\u4e00-\u9fff _/\-]{1,16})[：:]\s*(.+)$", line)
        if label_with_body_match and "http" not in label_with_body_match.group(1).lower():
            lines.append(f"{_render_weixin_bracket_title(label_with_body_match.group(1))}{label_with_body_match.group(2).strip()}")
            continue
        label_only_match = re.match(r"^([A-Za-z0-9\u4e00-\u9fff _/\-]{1,16})[：:]\s*$", line)
        if label_only_match and "http" not in label_only_match.group(1).lower():
            lines.append(_render_weixin_bracket_title(label_only_match.group(1)))
            continue
        lines.append(line)
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _render_weixin_bracket_title(text: str) -> str:
    title = str(text or "").strip().strip("[]【】")
    return f"【{title}】" if title else ""


def _replace_markdown_link(match: re.Match[str]) -> str:
    label = str(match.group(1) or "").strip()
    url = str(match.group(2) or "").strip()
    if not label:
        return url
    if not url or label == url:
        return label
    return f"{label}: {url}"


def _replace_markdown_image(match: re.Match[str]) -> str:
    alt = str(match.group(1) or "").strip()
    url = str(match.group(2) or "").strip()
    if alt and url:
        return f"{alt}: {url}"
    return alt or url


def _render_primary_surface(profile: ChannelProfile) -> str:
    if profile.channel == "cli":
        return "纯文本终端对话"
    if profile.channel == "feishu":
        return "聊天消息，可扩展到图片、文件和后续补充"
    if profile.channel == "weixin":
        return "聊天消息，文本优先，也可补充图片和文件"
    return "聊天文本"


def _render_direct_delivery(profile: ChannelProfile) -> str:
    parts = ["文本"]
    if profile.can_send_images:
        parts.append("图片")
    if profile.can_send_files:
        parts.append("文件")
    if profile.can_update_message:
        parts.append("更新式回复")
    return "、".join(parts)


def _render_channel_extra_hint(profile: ChannelProfile) -> str:
    if profile.channel == "cli":
        return "把复杂结果收成终端里就能直接执行或理解的形式"
    if profile.channel == "weixin":
        return "更适合短段落、直接表达，以及用【标题】做轻量分段"
    if profile.channel == "feishu":
        return "可以自然利用聊天附件和后续补充能力"
    return ""


__all__ = [
    "ChannelProfile",
    "normalize_output_bundle_for_channel",
    "render_channel_prompt_block",
    "render_channel_reply_requirements",
    "resolve_channel_profile",
]
