from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GuardianScope:
    files: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    runtime_objects: list[str] = field(default_factory=list)


@dataclass
class GuardianRequest:
    request_id: str
    source: str
    request_type: str
    title: str
    reason: str
    risk_level: str
    review_status: str = "pending"
    scope: GuardianScope = field(default_factory=GuardianScope)
    planned_actions: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)
    rollback: list[str] = field(default_factory=list)
    review_notes: list[str] = field(default_factory=list)
    execution_notes: list[str] = field(default_factory=list)
    requested_tests: list[str] = field(default_factory=list)
    requires_code_change: bool = False
    requires_restart: bool = False
    patch_plan: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GuardianRequest":
        scope_payload = payload.get("scope") if isinstance(payload.get("scope"), dict) else {}
        scope = GuardianScope(
            files=[str(x) for x in (scope_payload.get("files") or [])],
            modules=[str(x) for x in (scope_payload.get("modules") or [])],
            runtime_objects=[str(x) for x in (scope_payload.get("runtime_objects") or [])],
        )
        return cls(
            request_id=str(payload.get("request_id") or "").strip(),
            source=str(payload.get("source") or "").strip(),
            request_type=str(payload.get("request_type") or "").strip(),
            title=str(payload.get("title") or "").strip(),
            reason=str(payload.get("reason") or "").strip(),
            risk_level=str(payload.get("risk_level") or "").strip(),
            review_status=str(payload.get("review_status") or "pending").strip() or "pending",
            scope=scope,
            planned_actions=[str(x) for x in (payload.get("planned_actions") or [])],
            verification=[str(x) for x in (payload.get("verification") or [])],
            rollback=[str(x) for x in (payload.get("rollback") or [])],
            review_notes=[str(x) for x in (payload.get("review_notes") or [])],
            execution_notes=[str(x) for x in (payload.get("execution_notes") or [])],
            requested_tests=[str(x) for x in (payload.get("requested_tests") or [])],
            requires_code_change=bool(payload.get("requires_code_change")),
            requires_restart=bool(payload.get("requires_restart")),
            patch_plan=payload.get("patch_plan") if isinstance(payload.get("patch_plan"), dict) else payload.get("patch_plan"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "source": self.source,
            "request_type": self.request_type,
            "title": self.title,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "review_status": self.review_status,
            "scope": {
                "files": list(self.scope.files),
                "modules": list(self.scope.modules),
                "runtime_objects": list(self.scope.runtime_objects),
            },
            "planned_actions": list(self.planned_actions),
            "verification": list(self.verification),
            "rollback": list(self.rollback),
            "review_notes": list(self.review_notes),
            "execution_notes": list(self.execution_notes),
            "requested_tests": list(self.requested_tests),
            "requires_code_change": self.requires_code_change,
            "requires_restart": self.requires_restart,
            "patch_plan": self.patch_plan,
        }


@dataclass
class GuardianReviewResult:
    decision: str
    notes: list[str] = field(default_factory=list)
