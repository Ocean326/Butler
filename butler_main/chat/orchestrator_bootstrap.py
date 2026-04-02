from __future__ import annotations

from dataclasses import dataclass, field
import sys
from typing import Any


@dataclass(slots=True, frozen=True)
class OrchestratorBootstrapResult:
    ok: bool
    running: bool
    changed: bool = False
    reason: str = ""
    status: dict[str, Any] = field(default_factory=dict)
    command_hint: str = "./tools/butler restart orchestrator"
    fallback_command_hint: str = ".venv/bin/python -m butler_main.butler_bot_code.manager restart orchestrator"


class ChatOrchestratorBootstrapService:
    """Ensure the standalone orchestrator process is online before task ingress proceeds."""

    def ensure_online(self) -> OrchestratorBootstrapResult:
        try:
            from butler_main.butler_bot_code.manager import load_registry, start_service, status_service
        except Exception as exc:
            return OrchestratorBootstrapResult(
                ok=False,
                running=False,
                reason=f"bootstrap_import_failed:{type(exc).__name__}",
            )

        try:
            registry = load_registry()
            spec = registry.get("orchestrator")
            if spec is None:
                return OrchestratorBootstrapResult(
                    ok=False,
                    running=False,
                    reason="orchestrator_not_registered",
                )
            current = status_service(spec)
            if bool(current.get("running")):
                return OrchestratorBootstrapResult(
                    ok=True,
                    running=True,
                    changed=False,
                    reason="already_running",
                    status=dict(current),
                )
            started = start_service(spec, python_executable=sys.executable)
            status = dict(started)
            return OrchestratorBootstrapResult(
                ok=bool(started.get("ok")) and bool(started.get("running")),
                running=bool(started.get("running")),
                changed=bool(started.get("changed")),
                reason="started" if bool(started.get("running")) else "start_failed",
                status=status,
            )
        except Exception as exc:
            return OrchestratorBootstrapResult(
                ok=False,
                running=False,
                reason=f"bootstrap_failed:{type(exc).__name__}",
            )


__all__ = ["ChatOrchestratorBootstrapService", "OrchestratorBootstrapResult"]
