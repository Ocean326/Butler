from __future__ import annotations

import importlib

_EXPORT_MAP = {
    "WeixinInputAdapter": (".input", "WeixinInputAdapter"),
    "WeixinDeliveryAdapter": (".delivery", "WeixinDeliveryAdapter"),
    "WeixinDeliveryPlan": (".delivery", "WeixinDeliveryPlan"),
    "WeixinMessageOperation": (".delivery", "WeixinMessageOperation"),
    "build_bridge_url": (".bridge", "build_bridge_url"),
    "poll_weixin_bridge_once": (".client", "poll_weixin_bridge_once"),
    "process_weixin_webhook_event": (".bridge", "process_weixin_webhook_event"),
    "resolve_weixin_bridge_config": (".client", "resolve_weixin_bridge_config"),
    "run_weixin_bridge_client": (".client", "run_weixin_bridge_client"),
    "serve_weixin_bridge": (".bridge", "serve_weixin_bridge"),
    "run_chat_weixin_bot": (".runner", "run_chat_weixin_bot"),
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
