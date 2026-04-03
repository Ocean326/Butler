from __future__ import annotations

import importlib
import sys
from pathlib import Path

from butler_main.repo_layout import BUTLER_MAIN_REL, HOST_BODY_MODULE_REL, resolve_repo_root

_REPO_ROOT = resolve_repo_root(__file__)
_BUTLER_MAIN_DIR = _REPO_ROOT / BUTLER_MAIN_REL
_BODY_MODULE_DIR = _REPO_ROOT / HOST_BODY_MODULE_REL
_PRODUCT_DIR = (_REPO_ROOT / "butler_main" / "products" / "campaign_orchestrator" / "campaign").resolve()

if str(_BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BUTLER_MAIN_DIR))
if str(_BODY_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_BODY_MODULE_DIR))

__path__ = [str(_PRODUCT_DIR)]

_EXPORT_MAP = {
    "CAMPAIGN_STATUSES": (".models", "CAMPAIGN_STATUSES"),
    "CampaignArtifactRecord": (".phase_runtime", "CampaignArtifactRecord"),
    "CampaignCodexProvider": (".codex_runtime", "CampaignCodexProvider"),
    "CampaignCodexResult": (".codex_runtime", "CampaignCodexResult"),
    "VERDICT_DECISIONS": (".models", "VERDICT_DECISIONS"),
    "CampaignArtifactSummary": (".models", "CampaignArtifactSummary"),
    "CampaignDomainService": (".service", "CampaignDomainService"),
    "CampaignEvent": (".models", "CampaignEvent"),
    "CampaignEventRecord": (".phase_runtime", "CampaignEventRecord"),
    "CampaignInstance": (".models", "CampaignInstance"),
    "CampaignPhase": (".models", "CampaignPhase"),
    "CampaignPhaseOutcome": (".phase_runtime", "CampaignPhaseOutcome"),
    "CampaignPhaseRuntime": (".phase_runtime", "CampaignPhaseRuntime"),
    "CampaignSpec": (".models", "CampaignSpec"),
    "CampaignResumeOutcome": (".supervisor", "CampaignResumeOutcome"),
    "CampaignReviewerRuntime": (".reviewer_runtime", "CampaignReviewerRuntime"),
    "CliRunnerCampaignCodexProvider": (".codex_runtime", "CliRunnerCampaignCodexProvider"),
    "CodexCampaignSupervisorRuntime": (".codex_runtime", "CodexCampaignSupervisorRuntime"),
    "CampaignSupervisorRuntime": (".supervisor", "CampaignSupervisorRuntime"),
    "EvaluationVerdict": (".models", "EvaluationVerdict"),
    "FileCampaignStore": (".store", "FileCampaignStore"),
    "IterationBudget": (".models", "IterationBudget"),
    "WorkingContract": (".models", "WorkingContract"),
    "CampaignModuleDefinition": (".template_registry", "CampaignModuleDefinition"),
    "CampaignTemplateDefinition": (".template_registry", "CampaignTemplateDefinition"),
    "CampaignTemplateRegistry": (".template_registry", "CampaignTemplateRegistry"),
    "CampaignTurnReceipt": (".models", "CampaignTurnReceipt"),
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
