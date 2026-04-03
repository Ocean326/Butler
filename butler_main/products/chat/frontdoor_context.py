from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class FrontDoorContext:
    mode: str = ""
    frontdoor_action: str = ""
    urgency: str = ""
    estimated_scale: str = ""
    freshness_need: str = ""
    followup_likelihood: str = ""
    preferred_output: str = ""
    explicit_backend_request: bool = False
    should_discuss_mode_first: bool = False
    direct_execution_ok: bool = False
    external_execution_risk: bool = False
    user_goal: str = ""
    inferred_intent: str = ""
    acceptance_hint: tuple[str, ...] = field(default_factory=tuple)


def resolve_frontdoor_context(
    *,
    intake_decision: Mapping[str, Any] | None = None,
    intake_prompt_block: str | None = None,
) -> FrontDoorContext:
    normalized = _normalize_intake_mapping(intake_decision)
    if intake_prompt_block:
        normalized = {**_parse_frontdesk_prompt_block(intake_prompt_block), **normalized}
    acceptance_hint = normalized.get("acceptance_hint")
    return FrontDoorContext(
        mode=str(normalized.get("mode") or "").strip(),
        frontdoor_action=str(normalized.get("frontdoor_action") or "").strip(),
        urgency=str(normalized.get("urgency") or "").strip(),
        estimated_scale=str(normalized.get("estimated_scale") or "").strip(),
        freshness_need=str(normalized.get("freshness_need") or "").strip(),
        followup_likelihood=str(normalized.get("followup_likelihood") or "").strip(),
        preferred_output=str(normalized.get("preferred_output") or "").strip(),
        explicit_backend_request=_as_bool(normalized.get("explicit_backend_request")),
        should_discuss_mode_first=_as_bool(normalized.get("should_discuss_mode_first")),
        direct_execution_ok=_as_bool(normalized.get("direct_execution_ok")),
        external_execution_risk=_as_bool(normalized.get("external_execution_risk")),
        user_goal=str(normalized.get("user_goal") or "").strip(),
        inferred_intent=str(normalized.get("inferred_intent") or "").strip(),
        acceptance_hint=tuple(_normalize_acceptance_hint(acceptance_hint)),
    )


def _normalize_intake_mapping(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    return {str(key): value for key, value in payload.items()}


def _parse_frontdesk_prompt_block(prompt_block: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for raw_line in str(prompt_block or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("- ") or "=" not in line:
            continue
        key, _, value = line[2:].partition("=")
        normalized_key = str(key or "").strip()
        normalized_value = str(value or "").strip()
        if not normalized_key:
            continue
        if normalized_key == "acceptance_hint":
            result[normalized_key] = _normalize_acceptance_hint(normalized_value)
        else:
            result[normalized_key] = normalized_value
    return result


def _normalize_acceptance_hint(value: Any) -> list[str]:
    if isinstance(value, str):
        parts = [item.strip() for item in value.split("/") if item.strip()]
        return parts[:6]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()][:6]
    return []


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "on"}


__all__ = ["FrontDoorContext", "resolve_frontdoor_context"]
