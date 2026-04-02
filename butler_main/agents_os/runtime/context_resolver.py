from __future__ import annotations

from typing import Any, Mapping


class ContextResolver:
    def resolve(self, invocation: Any, context: Mapping[str, Any]) -> Mapping[str, Any]:
        return context
