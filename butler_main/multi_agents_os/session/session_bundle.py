from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from ..templates.workflow_template import WorkflowTemplate
from .artifact_registry import ArtifactRegistry
from .blackboard import WorkflowBlackboard
from .collaboration import CollaborationSubstrate
from .shared_state import SharedState
from .workflow_session import WorkflowSession


@dataclass(slots=True)
class WorkflowSessionBundle:
    """Serializable bundle for one local workflow session."""

    template: WorkflowTemplate
    session: WorkflowSession
    shared_state: SharedState
    artifact_registry: ArtifactRegistry
    blackboard: WorkflowBlackboard
    collaboration: CollaborationSubstrate

    def to_dict(self) -> dict[str, Any]:
        return {
            "template": self.template.to_dict(),
            "session": self.session.to_dict(),
            "shared_state": self.shared_state.to_dict(),
            "artifact_registry": self.artifact_registry.to_dict(),
            "blackboard": self.blackboard.to_dict(),
            "collaboration": self.collaboration.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "WorkflowSessionBundle | None":
        if not isinstance(payload, Mapping):
            return None
        template = WorkflowTemplate.from_dict(payload.get("template") if isinstance(payload.get("template"), Mapping) else {})
        session = WorkflowSession.from_dict(payload.get("session") if isinstance(payload.get("session"), Mapping) else {})
        shared_state = SharedState.from_dict(payload.get("shared_state") if isinstance(payload.get("shared_state"), Mapping) else {})
        artifact_registry = ArtifactRegistry.from_dict(payload.get("artifact_registry") if isinstance(payload.get("artifact_registry"), Mapping) else {})
        blackboard = WorkflowBlackboard.from_dict(payload.get("blackboard") if isinstance(payload.get("blackboard"), Mapping) else {})
        collaboration = CollaborationSubstrate.from_dict(payload.get("collaboration") if isinstance(payload.get("collaboration"), Mapping) else {})
        if not blackboard.session_id:
            blackboard.session_id = session.session_id
        if not collaboration.session_id:
            collaboration.session_id = session.session_id
        return cls(
            template=template,
            session=session,
            shared_state=shared_state,
            artifact_registry=artifact_registry,
            blackboard=blackboard,
            collaboration=collaboration,
        )
