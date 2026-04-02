from __future__ import annotations


DEFAULT_CORE_HOST = "127.0.0.1"
DEFAULT_CORE_PORT = 18789
DEFAULT_CORE_CHANNELS = ("cli", "feishu", "weixin")
DEFAULT_WEIXIN_OFFICIAL_BRIDGE_BASE_URL = "https://ilinkai.weixin.qq.com"
DEFAULT_WEIXIN_OFFICIAL_CDN_BASE_URL = "https://novac2c.cdn.weixin.qq.com/c2c"


__all__ = [
    "DEFAULT_CORE_CHANNELS",
    "DEFAULT_CORE_HOST",
    "DEFAULT_CORE_PORT",
    "DEFAULT_WEIXIN_OFFICIAL_BRIDGE_BASE_URL",
    "DEFAULT_WEIXIN_OFFICIAL_CDN_BASE_URL",
]
