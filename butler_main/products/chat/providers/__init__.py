from __future__ import annotations

import importlib

_EXPORT_MAP = {
    "ButlerChatMemoryProvider": (".butler_memory_provider", "ButlerChatMemoryProvider"),
    "ButlerChatPromptProvider": (".butler_prompt_provider", "ButlerChatPromptProvider"),
    "ButlerChatPromptSupportProvider": (".butler_prompt_support_provider", "ButlerChatPromptSupportProvider"),
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
