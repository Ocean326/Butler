from __future__ import annotations

try:
    from .interfaces.query_service import OrchestratorQueryService
except ModuleNotFoundError:  # pragma: no cover - direct script/import fallback
    from butler_main.orchestrator.interfaces.query_service import OrchestratorQueryService

__all__ = ["OrchestratorQueryService"]
