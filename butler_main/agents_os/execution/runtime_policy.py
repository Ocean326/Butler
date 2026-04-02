from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RuntimePolicyDecision:
    runtime_request: dict
    runtime_profile: dict
    manager_note: str


class RuntimePolicy(Protocol):
    def route_branch(self, workspace: str, branch: dict, model: str, cfg: dict | None = None) -> RuntimePolicyDecision: ...
