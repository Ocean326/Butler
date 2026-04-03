from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_text_tuple(values: tuple[Any, ...] | list[Any] | None) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    seen: set[str] = set()
    normalized: list[str] = []
    for item in values:
        text = _normalize_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return tuple(normalized)


@dataclass(slots=True, frozen=True)
class CampaignTemplateDefinition:
    template_id: str
    display_name: str
    summary: str
    keywords: tuple[str, ...] = ()
    default_phase_ids: tuple[str, ...] = ()
    default_role_ids: tuple[str, ...] = ()
    governance_profile: str = "reviewed_delivery"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "template_id", _normalize_text(self.template_id))
        object.__setattr__(self, "display_name", _normalize_text(self.display_name))
        object.__setattr__(self, "summary", _normalize_text(self.summary))
        object.__setattr__(self, "keywords", _normalize_text_tuple(self.keywords))
        object.__setattr__(self, "default_phase_ids", _normalize_text_tuple(self.default_phase_ids))
        object.__setattr__(self, "default_role_ids", _normalize_text_tuple(self.default_role_ids))
        object.__setattr__(self, "governance_profile", _normalize_text(self.governance_profile) or "reviewed_delivery")
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class CampaignModuleDefinition:
    module_id: str
    module_kind: str
    display_name: str
    summary: str
    values: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "module_id", _normalize_text(self.module_id))
        object.__setattr__(self, "module_kind", _normalize_text(self.module_kind))
        object.__setattr__(self, "display_name", _normalize_text(self.display_name))
        object.__setattr__(self, "summary", _normalize_text(self.summary))
        object.__setattr__(self, "values", _normalize_text_tuple(self.values))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CampaignTemplateRegistry:
    """Official template and module catalog for campaign negotiation/runtime."""

    def __init__(
        self,
        *,
        templates: list[CampaignTemplateDefinition] | None = None,
        modules: list[CampaignModuleDefinition] | None = None,
    ) -> None:
        self._templates = {
            item.template_id: item
            for item in (templates or _default_templates())
        }
        self._modules = {
            item.module_id: item
            for item in (modules or _default_modules())
        }

    def list_templates(self) -> list[CampaignTemplateDefinition]:
        return list(self._templates.values())

    def list_modules(self, *, module_kind: str = "") -> list[CampaignModuleDefinition]:
        kind = _normalize_text(module_kind).lower()
        items = list(self._modules.values())
        if not kind:
            return items
        return [item for item in items if item.module_kind.lower() == kind]

    def get_template(self, template_id: str) -> CampaignTemplateDefinition | None:
        return self._templates.get(_normalize_text(template_id))

    def recommend(self, text: str) -> tuple[CampaignTemplateDefinition, float, str]:
        normalized = _normalize_text(text).lower()
        best = next(iter(self._templates.values()))
        best_score = 0.0
        best_reason = "default_template"
        for template in self._templates.values():
            score = 0.0
            if template.template_id.lower() in normalized:
                score += 0.4
            for keyword in template.keywords:
                if keyword.lower() in normalized:
                    score += 0.2
            if score > best_score:
                best = template
                best_score = score
                best_reason = f"matched:{template.template_id}"
        return best, min(0.95, max(0.55, best_score + 0.4)), best_reason

    def build_default_composition(self, template_id: str) -> dict[str, Any]:
        template = self.get_template(template_id)
        if template is None:
            return {
                "base_template_id": "",
                "phase_plan": [],
                "role_plan": [],
                "governance_plan": {},
                "diff_summary": [],
                "skeleton_changed": False,
            }
        return {
            "base_template_id": template.template_id,
            "phase_plan": list(template.default_phase_ids),
            "role_plan": list(template.default_role_ids),
            "governance_plan": {
                "profile": template.governance_profile,
            },
            "diff_summary": [],
            "skeleton_changed": False,
        }


def _default_templates() -> list[CampaignTemplateDefinition]:
    return [
        CampaignTemplateDefinition(
            template_id="campaign.single_repo_delivery",
            display_name="Single Repo Delivery",
            summary="Single repo, multi-phase delivery loop with independent reviewer.",
            keywords=("交付", "上线", "发布", "补丁", "实现", "修复"),
            default_phase_ids=("discover", "implement", "evaluate", "iterate"),
            default_role_ids=("campaign_supervisor", "campaign_reviewer"),
            governance_profile="reviewed_delivery",
        ),
        CampaignTemplateDefinition(
            template_id="campaign.research_then_implement",
            display_name="Research Then Implement",
            summary="Research first, then implement with explicit reviewer gates.",
            keywords=("调研", "研究", "资料", "方案", "论文", "调研后实现"),
            default_phase_ids=("discover", "implement", "evaluate", "iterate"),
            default_role_ids=("campaign_supervisor", "campaign_reviewer"),
            governance_profile="research_to_delivery",
        ),
        CampaignTemplateDefinition(
            template_id="campaign.guarded_autonomy",
            display_name="Guarded Autonomy",
            summary="Autonomous loop with approval and review guardrails.",
            keywords=("自治", "监督", "审批", "评审", "守门", "防护"),
            default_phase_ids=("discover", "implement", "evaluate", "iterate"),
            default_role_ids=("campaign_supervisor", "campaign_reviewer"),
            governance_profile="guarded_autonomy",
        ),
    ]


def _default_modules() -> list[CampaignModuleDefinition]:
    return [
        CampaignModuleDefinition(
            module_id="phase.discover",
            module_kind="phase",
            display_name="Discover",
            summary="Scope goals, material inventory, and initial working contract.",
            values=("discover",),
        ),
        CampaignModuleDefinition(
            module_id="phase.implement",
            module_kind="phase",
            display_name="Implement",
            summary="Execute the current contract against the workspace.",
            values=("implement",),
        ),
        CampaignModuleDefinition(
            module_id="phase.evaluate",
            module_kind="phase",
            display_name="Evaluate",
            summary="Independent reviewer emits verdict and evidence.",
            values=("evaluate",),
        ),
        CampaignModuleDefinition(
            module_id="phase.iterate",
            module_kind="phase",
            display_name="Iterate",
            summary="Rewrite contract or converge the campaign.",
            values=("iterate",),
        ),
        CampaignModuleDefinition(
            module_id="role.campaign_supervisor",
            module_kind="role",
            display_name="Campaign Supervisor",
            summary="Owns execution planning and campaign continuity.",
            values=("campaign_supervisor",),
        ),
        CampaignModuleDefinition(
            module_id="role.campaign_reviewer",
            module_kind="role",
            display_name="Campaign Reviewer",
            summary="Provides independent deterministic review.",
            values=("campaign_reviewer",),
        ),
        CampaignModuleDefinition(
            module_id="governance.reviewed_delivery",
            module_kind="governance",
            display_name="Reviewed Delivery",
            summary="Standard supervisor + reviewer delivery loop.",
            values=("reviewed_delivery",),
        ),
        CampaignModuleDefinition(
            module_id="governance.research_to_delivery",
            module_kind="governance",
            display_name="Research To Delivery",
            summary="Bias toward material discovery before code changes.",
            values=("research_to_delivery",),
        ),
        CampaignModuleDefinition(
            module_id="governance.guarded_autonomy",
            module_kind="governance",
            display_name="Guarded Autonomy",
            summary="Higher autonomy with explicit approval guardrails.",
            values=("guarded_autonomy",),
        ),
    ]


__all__ = [
    "CampaignModuleDefinition",
    "CampaignTemplateDefinition",
    "CampaignTemplateRegistry",
]
