from __future__ import annotations

try:
    from .interfaces.ingress_service import OrchestratorIngressService
except ModuleNotFoundError:  # pragma: no cover - direct script/import fallback
    from butler_main.orchestrator.interfaces.ingress_service import OrchestratorIngressService

__all__ = ["OrchestratorIngressService"]
