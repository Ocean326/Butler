from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from agents_os.contracts import OutputBundle, TextBlock
from butler_main.orchestrator.interfaces.campaign_service import OrchestratorCampaignService
from butler_main.orchestrator.interfaces.query_service import OrchestratorQueryService
from .frontdoor_modes import FrontDoorSlashCommand
from .negotiation import CampaignNegotiationStore


_CAMPAIGN_ID_RE = re.compile(r"\b(campaign_[A-Za-z0-9]+)\b")
_RISK_LEVELS = {"low", "medium", "high", "critical"}


@dataclass(slots=True, frozen=True)
class FrontDoorGovernResult:
    handled: bool
    output_bundle: OutputBundle | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class FrontDoorGovernService:
    def __init__(
        self,
        *,
        store: CampaignNegotiationStore | None = None,
        campaign_service: OrchestratorCampaignService | None = None,
        query_service: OrchestratorQueryService | None = None,
    ) -> None:
        self._store = store or CampaignNegotiationStore()
        self._campaign_service = campaign_service or OrchestratorCampaignService()
        self._query_service = query_service or OrchestratorQueryService(campaign_service=self._campaign_service)

    def handle(
        self,
        *,
        workspace: str,
        session_id: str,
        user_text: str,
        slash_command: FrontDoorSlashCommand | None = None,
    ) -> FrontDoorGovernResult:
        command = slash_command or FrontDoorSlashCommand(mode_id="govern", command_text="/govern", body=user_text)
        target_campaign_id, action, argument = self._parse_command(
            workspace=workspace,
            session_id=session_id,
            body=command.body,
        )
        if not target_campaign_id:
            return self._blocked_result(
                "当前会话没有唯一活动 campaign；请附带 `campaign_id`，例如 `/govern campaign_xxx view`。",
            )
        if action == "view":
            payload = self._query_service.get_campaign_status(workspace, target_campaign_id)
            return self._result_from_payload(target_campaign_id, action, payload)
        patch = self._patch_for_action(action, argument)
        if patch is None:
            return self._blocked_result(
                "只支持 `view` / `set_risk_level` / `set_autonomy_profile` / `request_approval` / `resolve_approval`。",
                target_campaign_id=target_campaign_id,
            )
        self._campaign_service.update_campaign_metadata(
            workspace,
            target_campaign_id,
            {"governance_contract": patch},
        )
        payload = self._query_service.get_campaign_status(workspace, target_campaign_id)
        return self._result_from_payload(target_campaign_id, action, payload)

    def _parse_command(self, *, workspace: str, session_id: str, body: str) -> tuple[str, str, str]:
        text = str(body or "").strip()
        tokens = text.split()
        target_campaign_id = ""
        if tokens:
            matched = _CAMPAIGN_ID_RE.fullmatch(tokens[0])
            if matched is not None:
                target_campaign_id = tokens.pop(0)
        if not target_campaign_id:
            target_campaign_id = self._resolve_campaign_id(workspace=workspace, session_id=session_id, text=text)
        action = "view"
        argument = ""
        if tokens:
            action = str(tokens[0] or "").strip().lower()
            argument = " ".join(tokens[1:]).strip()
        return target_campaign_id, action, argument

    def _resolve_campaign_id(self, *, workspace: str, session_id: str, text: str) -> str:
        matched = _CAMPAIGN_ID_RE.search(text)
        if matched is not None:
            return str(matched.group(1) or "").strip()
        draft = self._store.load(workspace=workspace, session_id=session_id)
        if draft is not None and str(draft.started_campaign_id or "").strip():
            return str(draft.started_campaign_id or "").strip()
        return ""

    @staticmethod
    def _patch_for_action(action: str, argument: str) -> dict[str, Any] | None:
        if action == "set_risk_level":
            risk_level = str(argument or "").strip().lower()
            if risk_level not in _RISK_LEVELS:
                return None
            return {"risk_level": risk_level}
        if action == "set_autonomy_profile":
            autonomy_profile = str(argument or "").strip()
            if not autonomy_profile:
                return None
            return {"autonomy_profile": autonomy_profile}
        if action == "request_approval":
            return {"approval_state": "requested"}
        if action == "resolve_approval":
            state = str(argument or "resolved").strip().lower() or "resolved"
            return {"approval_state": state}
        return None

    @staticmethod
    def _blocked_result(text: str, *, target_campaign_id: str = "") -> FrontDoorGovernResult:
        bundle = OutputBundle(
            summary="campaign governance unresolved",
            text_blocks=[TextBlock(text=text)],
            metadata={
                "frontdoor_action": "govern",
                "frontdoor_target_kind": "campaign",
                "frontdoor_target_id": target_campaign_id,
                "frontdoor_blocked": True,
                "frontdoor_resolution_source": "frontdoor_governance",
                "governance_action": "blocked",
            },
        )
        return FrontDoorGovernResult(
            handled=True,
            output_bundle=bundle,
            metadata=dict(bundle.metadata or {}),
        )

    @staticmethod
    def _result_from_payload(campaign_id: str, action: str, payload: dict[str, Any]) -> FrontDoorGovernResult:
        governance = dict(payload.get("governance_summary") or {})
        risk_level = str(governance.get("risk_level") or "medium").strip() or "medium"
        autonomy_profile = str(governance.get("autonomy_profile") or "").strip() or "-"
        approval_state = str(governance.get("approval_state") or "none").strip() or "none"
        text = "\n".join(
            [
                "campaign governance",
                f"campaign_id: {campaign_id}",
                f"action: {action}",
                f"risk_level: {risk_level}",
                f"autonomy_profile: {autonomy_profile}",
                f"approval_state: {approval_state}",
            ]
        )
        bundle = OutputBundle(
            summary=f"campaign governance: {campaign_id}",
            text_blocks=[TextBlock(text=text)],
            metadata={
                "frontdoor_action": "govern",
                "frontdoor_target_kind": "campaign",
                "frontdoor_target_id": campaign_id,
                "frontdoor_blocked": False,
                "frontdoor_resolution_source": "frontdoor_governance",
                "governance_action": action,
                "governance_summary": governance,
            },
        )
        return FrontDoorGovernResult(
            handled=True,
            output_bundle=bundle,
            metadata=dict(bundle.metadata or {}),
        )


__all__ = ["FrontDoorGovernResult", "FrontDoorGovernService"]
