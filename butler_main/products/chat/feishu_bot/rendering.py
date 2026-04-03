from __future__ import annotations

from butler_main.agents_os.runtime import safe_truncate_markdown


def _build_card_quick_action_buttons(*, mode: str = "followup", value_extras: dict | None = None) -> list[dict]:
    extras = {
        str(key): value
        for key, value in dict(value_extras or {}).items()
        if str(key or "").strip() and value not in (None, "")
    }
    normalized_mode = str(mode or "followup").strip().lower() or "followup"
    if normalized_mode == "running":
        return [
            {
                "tag": "button",
                "type": "danger",
                "text": {"tag": "plain_text", "content": "终止"},
                "value": {**extras, "cmd": "terminate", "label": "终止"},
            }
        ]
    return [
        {
            "tag": "button",
            "type": "primary",
            "text": {"tag": "plain_text", "content": "继续展开"},
            "value": {**extras, "cmd": "continue", "label": "继续展开"},
        },
        {
            "tag": "button",
            "type": "default",
            "text": {"tag": "plain_text", "content": "总结待办"},
            "value": {**extras, "cmd": "todo", "label": "总结待办"},
        },
        {
            "tag": "button",
            "type": "default",
            "text": {"tag": "plain_text", "content": "一句话版"},
            "value": {**extras, "cmd": "brief", "label": "一句话版"},
        },
    ]


def build_card_quick_actions(*, mode: str = "followup", value_extras: dict | None = None) -> list[dict]:
    return _build_card_quick_action_buttons(mode=mode, value_extras=value_extras)


def _render_quick_action_hint_markdown(*, mode: str = "followup") -> str:
    lines = ["快捷操作："]
    for action in build_card_quick_actions(mode=mode):
        label = str(((action.get("value") or {}).get("label")) or "").strip()
        if label:
            lines.append(f"- `{label}`")
    return "\n".join(lines)


def markdown_to_feishu_post(md: str) -> dict:
    content = (md or "").strip()
    if not content:
        content = "(空回复)"
    content = safe_truncate_markdown(content, 28000)
    return {"zh_cn": {"title": "回复", "content": [[{"tag": "md", "text": content}]]}}


def markdown_to_interactive_card(
    md: str,
    include_quick_actions: bool = False,
    *,
    quick_action_mode: str = "followup",
    action_value_extras: dict | None = None,
) -> dict:
    content = safe_truncate_markdown((md or "").strip(), 28000)
    elements = [{"tag": "markdown", "content": content}]
    if include_quick_actions:
        actions = build_card_quick_actions(mode=quick_action_mode, value_extras=action_value_extras)
        elements.append({"tag": "markdown", "content": _render_quick_action_hint_markdown(mode=quick_action_mode)})
        elements.extend(actions)
    return {
        "schema": "2.0",
        "config": {"wide_screen_mode": True},
        "body": {
            "direction": "vertical",
            "padding": "12px 12px 12px 12px",
            "elements": elements,
        },
    }


__all__ = ["build_card_quick_actions", "markdown_to_feishu_post", "markdown_to_interactive_card"]
