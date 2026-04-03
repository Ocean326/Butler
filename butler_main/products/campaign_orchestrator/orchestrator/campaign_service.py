from __future__ import annotations

try:
    from .interfaces.campaign_service import OrchestratorCampaignService
except ModuleNotFoundError:  # pragma: no cover - direct script/import fallback
    from butler_main.orchestrator.interfaces.campaign_service import OrchestratorCampaignService

__all__ = ["OrchestratorCampaignService"]
