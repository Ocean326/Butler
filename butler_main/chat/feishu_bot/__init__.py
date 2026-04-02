from __future__ import annotations

import importlib

_EXPORT_MAP = {
    "FeishuApiClient": (".api", "FeishuApiClient"),
    "FeishuDeliveryAdapter": (".delivery", "FeishuDeliveryAdapter"),
    "FeishuDeliveryPlan": (".delivery", "FeishuDeliveryPlan"),
    "build_card_action_response": (".dispatcher", "build_card_action_response"),
    "build_chat_feishu_event_dispatcher": (".dispatcher", "build_chat_feishu_event_dispatcher"),
    "build_card_action_invocation_metadata": (".interaction", "build_card_action_invocation_metadata"),
    "build_card_action_prompt": (".interaction", "build_card_action_prompt"),
    "build_invocation_metadata_from_message": (".interaction", "build_invocation_metadata_from_message"),
    "extract_card_action_payload": (".interaction", "extract_card_action_payload"),
    "FeishuInputAdapter": (".input", "FeishuInputAdapter"),
    "MessageDeliveryService": (".message_delivery", "MessageDeliveryService"),
    "ChatFeishuPresentationService": (".presentation", "ChatFeishuPresentationService"),
    "FeishuReplyService": (".replying", "FeishuReplyService"),
    "build_card_quick_actions": (".rendering", "build_card_quick_actions"),
    "markdown_to_feishu_post": (".rendering", "markdown_to_feishu_post"),
    "markdown_to_interactive_card": (".rendering", "markdown_to_interactive_card"),
    "run_chat_feishu_bot": (".runner", "run_chat_feishu_bot"),
    "run_chat_feishu_bot_with_loaded_config": (".runner", "run_chat_feishu_bot_with_loaded_config"),
}

__all__ = list(_EXPORT_MAP)


def __getattr__(name: str):
    module_info = _EXPORT_MAP.get(name)
    if module_info is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = module_info
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
