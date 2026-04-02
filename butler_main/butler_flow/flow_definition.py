from __future__ import annotations

from typing import Any

from .constants import MANAGED_FLOW_KIND, PROJECT_LOOP_KIND, SINGLE_GOAL_KIND, SINGLE_GOAL_PHASE


def _text(value: Any) -> str:
    return str(value or "").strip()


def _phase_id(value: Any, *, fallback: str) -> str:
    token = _text(value).lower().replace(" ", "_").replace("-", "_")
    return token or fallback


def default_phase_plan(workflow_kind: str) -> list[dict[str, Any]]:
    kind = _text(workflow_kind) or SINGLE_GOAL_KIND
    if kind in {PROJECT_LOOP_KIND, MANAGED_FLOW_KIND}:
        return [
            {
                "phase_id": "plan",
                "title": "Plan",
                "objective": "Produce or repair the concrete implementation plan, identify files/tests, and leave the repo ready for execution.",
                "done_when": "A concrete implementation plan is ready and the next code/test targets are clear.",
                "retry_phase_id": "plan",
                "fallback_phase_id": "plan",
                "next_phase_id": "imp",
            },
            {
                "phase_id": "imp",
                "title": "Implement",
                "objective": "Implement the plan, update code/tests/docs as needed, and make the repository materially closer to done.",
                "done_when": "The implementation is materially advanced and ready for review or targeted follow-up.",
                "retry_phase_id": "imp",
                "fallback_phase_id": "plan",
                "next_phase_id": "review",
            },
            {
                "phase_id": "review",
                "title": "Review",
                "objective": "Review the latest implementation, run verification, fix real issues you find, then summarize residual risks.",
                "done_when": "Verification is acceptable and the work is ready to conclude.",
                "retry_phase_id": "imp",
                "fallback_phase_id": "imp",
                "next_phase_id": "",
            },
        ]
    return [
        {
            "phase_id": SINGLE_GOAL_PHASE,
            "title": "Execute",
            "objective": "Continue the foreground task until the primary goal and guard condition are satisfied.",
            "done_when": "The goal is satisfied or clearly blocked.",
            "retry_phase_id": SINGLE_GOAL_PHASE,
            "fallback_phase_id": SINGLE_GOAL_PHASE,
            "next_phase_id": "",
        }
    ]


def normalize_phase_plan(
    phase_plan: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    *,
    workflow_kind: str,
) -> list[dict[str, Any]]:
    rows = list(phase_plan or [])
    if not rows:
        return default_phase_plan(workflow_kind)
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        payload = dict(row or {})
        phase_id = _phase_id(payload.get("phase_id") or payload.get("id") or payload.get("name"), fallback=f"phase_{index}")
        normalized.append(
            {
                "phase_id": phase_id,
                "title": _text(payload.get("title") or payload.get("label") or phase_id.replace("_", " ").title()),
                "objective": _text(payload.get("objective") or payload.get("description") or payload.get("prompt") or ""),
                "done_when": _text(payload.get("done_when") or payload.get("success_criteria") or ""),
                "retry_phase_id": _phase_id(payload.get("retry_phase_id") or phase_id, fallback=phase_id),
                "fallback_phase_id": _phase_id(payload.get("fallback_phase_id") or payload.get("retry_phase_id") or phase_id, fallback=phase_id),
                "next_phase_id": _phase_id(payload.get("next_phase_id"), fallback="") if _text(payload.get("next_phase_id")) else "",
            }
        )
    valid_ids = {row["phase_id"] for row in normalized}
    for index, row in enumerate(normalized):
        if not row["objective"]:
            row["objective"] = f"Advance the `{row['phase_id']}` phase toward completion."
        if not row["done_when"]:
            row["done_when"] = f"`{row['phase_id']}` phase objective is satisfied."
        if not row["next_phase_id"] and index + 1 < len(normalized):
            row["next_phase_id"] = normalized[index + 1]["phase_id"]
        if row["retry_phase_id"] not in valid_ids:
            row["retry_phase_id"] = row["phase_id"]
        if row["fallback_phase_id"] not in valid_ids:
            row["fallback_phase_id"] = row["retry_phase_id"]
        if row["next_phase_id"] and row["next_phase_id"] not in valid_ids:
            row["next_phase_id"] = ""
    return normalized


def resolve_phase_plan(flow_state: dict[str, Any]) -> list[dict[str, Any]]:
    workflow_kind = _text(flow_state.get("workflow_kind")) or SINGLE_GOAL_KIND
    raw = flow_state.get("phase_plan")
    return normalize_phase_plan(raw if isinstance(raw, list) else None, workflow_kind=workflow_kind)


def phase_ids(phase_plan: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(_text(row.get("phase_id")) for row in list(phase_plan or []) if _text(row.get("phase_id")))


def first_phase_id(phase_plan: list[dict[str, Any]], *, workflow_kind: str) -> str:
    ids = phase_ids(phase_plan)
    if ids:
        return ids[0]
    return default_phase_plan(workflow_kind)[0]["phase_id"]


def phase_spec(phase_plan: list[dict[str, Any]], phase_id: str) -> dict[str, Any]:
    target = _text(phase_id)
    for row in list(phase_plan or []):
        payload = dict(row or {})
        if _text(payload.get("phase_id")) == target:
            return payload
    return {}


def next_phase_id(phase_plan: list[dict[str, Any]], phase_id: str) -> str:
    payload = phase_spec(phase_plan, phase_id)
    token = _text(payload.get("next_phase_id"))
    if token:
        return token
    ids = list(phase_ids(phase_plan))
    current = _text(phase_id)
    try:
        index = ids.index(current)
    except ValueError:
        return ""
    if index + 1 < len(ids):
        return ids[index + 1]
    return ""


def phase_prompt_context(phase_plan: list[dict[str, Any]], phase_id: str) -> dict[str, Any]:
    payload = phase_spec(phase_plan, phase_id)
    return {
        "phase_id": _text(payload.get("phase_id")) or phase_id,
        "title": _text(payload.get("title")),
        "objective": _text(payload.get("objective")),
        "done_when": _text(payload.get("done_when")),
        "retry_phase_id": _text(payload.get("retry_phase_id")),
        "fallback_phase_id": _text(payload.get("fallback_phase_id")),
        "next_phase_id": _text(payload.get("next_phase_id")),
        "available_next_phases": [phase for phase in phase_ids(phase_plan) if phase != _text(phase_id)],
    }


def coerce_workflow_kind(raw: str) -> str:
    token = _text(raw)
    if token in {SINGLE_GOAL_KIND, PROJECT_LOOP_KIND, MANAGED_FLOW_KIND}:
        return token
    return MANAGED_FLOW_KIND


__all__ = [
    "coerce_workflow_kind",
    "default_phase_plan",
    "first_phase_id",
    "next_phase_id",
    "normalize_phase_plan",
    "phase_ids",
    "phase_prompt_context",
    "phase_spec",
    "resolve_phase_plan",
]
