from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "ButlerMissionOrchestrator": (".mission_orchestrator", "ButlerMissionOrchestrator"),
    "MissionIngressResolution": (".mission_orchestrator", "MissionIngressResolution"),
    "ORCHESTRATOR_LOCK_FILE_NAME": (".runner", "ORCHESTRATOR_LOCK_FILE_NAME"),
    "ORCHESTRATOR_PID_FILE_NAME": (".runner", "ORCHESTRATOR_PID_FILE_NAME"),
    "ORCHESTRATOR_RUN_STATE_FILE_NAME": (".runner", "ORCHESTRATOR_RUN_STATE_FILE_NAME"),
    "ORCHESTRATOR_TICK_SECONDS_DEFAULT": (".runner", "ORCHESTRATOR_TICK_SECONDS_DEFAULT"),
    "ORCHESTRATOR_WATCHDOG_STATE_FILE_NAME": (".runner", "ORCHESTRATOR_WATCHDOG_STATE_FILE_NAME"),
    "OrchestratorCampaignService": (".campaign_service", "OrchestratorCampaignService"),
    "OrchestratorIngressService": (".ingress_service", "OrchestratorIngressService"),
    "OrchestratorQueryService": (".query_service", "OrchestratorQueryService"),
    "build_campaign_dashboard_parser": (".campaign_dashboard", "build_parser"),
    "build_campaign_dashboard_payload": (".campaign_dashboard", "build_campaign_dashboard_payload"),
    "build_observe_parser": (".observe", "build_parser"),
    "build_orchestrator_runtime_state_store": (".runner", "build_orchestrator_runtime_state_store"),
    "campaign_dashboard_main": (".campaign_dashboard", "main"),
    "observe_main": (".observe", "main"),
    "render_campaign_dashboard_html": (".campaign_dashboard", "render_campaign_dashboard_html"),
    "run_orchestrator_cycle": (".runner", "run_orchestrator_cycle"),
    "run_orchestrator_service": (".runner", "run_orchestrator_service"),
    "write_campaign_dashboard": (".campaign_dashboard", "write_campaign_dashboard"),
    "write_campaign_dashboard_html": (".campaign_dashboard", "write_campaign_dashboard_html"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    module = import_module(module_name, __name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
