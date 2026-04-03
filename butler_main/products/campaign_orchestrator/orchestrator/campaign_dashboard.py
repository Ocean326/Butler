from __future__ import annotations

try:
    from .interfaces.campaign_dashboard import (
        CampaignDashboardService,
        build_campaign_dashboard_payload,
        build_parser,
        main,
        render_campaign_dashboard_html,
        write_campaign_dashboard,
        write_campaign_dashboard_html,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script/import fallback
    from butler_main.orchestrator.interfaces.campaign_dashboard import (  # type: ignore
        CampaignDashboardService,
        build_campaign_dashboard_payload,
        build_parser,
        main,
        render_campaign_dashboard_html,
        write_campaign_dashboard,
        write_campaign_dashboard_html,
    )

__all__ = [
    "CampaignDashboardService",
    "build_campaign_dashboard_payload",
    "build_parser",
    "main",
    "render_campaign_dashboard_html",
    "write_campaign_dashboard",
    "write_campaign_dashboard_html",
]


if __name__ == "__main__":
    raise SystemExit(main())
