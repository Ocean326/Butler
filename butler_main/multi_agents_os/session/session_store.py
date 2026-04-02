from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..templates.workflow_template import WorkflowTemplate
from .artifact_registry import ArtifactRegistry
from .blackboard import WorkflowBlackboard
from .collaboration import CollaborationSubstrate
from .session_bundle import WorkflowSessionBundle
from .shared_state import SharedState
from .workflow_session import WorkflowSession


class FileWorkflowSessionStore:
    """Filesystem store for workflow session bundles."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def exists(self, session_id: str) -> bool:
        return self.session_path(session_id).exists()

    def list_session_ids(self) -> list[str]:
        session_ids: list[str] = []
        for path in sorted(self.root_dir.glob("*/session.json")):
            session_id = str(path.parent.name or "").strip()
            if session_id:
                session_ids.append(session_id)
        return session_ids

    def save_bundle(self, bundle: WorkflowSessionBundle) -> WorkflowSessionBundle:
        session_id = str(bundle.session.session_id or "").strip()
        if not session_id:
            raise ValueError("workflow session bundle requires session_id")
        self._write_json(self.template_path(session_id), bundle.template.to_dict())
        self._write_json(self.shared_state_path(session_id), bundle.shared_state.to_dict())
        self._write_json(self.artifact_registry_path(session_id), bundle.artifact_registry.to_dict())
        self._write_json(self.blackboard_path(session_id), bundle.blackboard.to_dict())
        self._write_json(self.collaboration_path(session_id), bundle.collaboration.to_dict())
        self._write_json(self.session_path(session_id), bundle.session.to_dict())
        return bundle

    def load_bundle(self, session_id: str) -> WorkflowSessionBundle | None:
        normalized = str(session_id or "").strip()
        if not normalized or not self.session_path(normalized).exists():
            return None
        template = WorkflowTemplate.from_dict(self._read_json(self.template_path(normalized)))
        session = WorkflowSession.from_dict(self._read_json(self.session_path(normalized)))
        shared_state = SharedState.from_dict(self._read_json(self.shared_state_path(normalized)))
        artifact_registry = ArtifactRegistry.from_dict(self._read_json(self.artifact_registry_path(normalized)))
        blackboard = WorkflowBlackboard.from_dict(self._read_json(self.blackboard_path(normalized)))
        collaboration = CollaborationSubstrate.from_dict(self._read_json(self.collaboration_path(normalized)))
        if not blackboard.session_id:
            blackboard.session_id = session.session_id or normalized
        if not collaboration.session_id:
            collaboration.session_id = session.session_id or normalized
        return WorkflowSessionBundle(
            template=template,
            session=session,
            shared_state=shared_state,
            artifact_registry=artifact_registry,
            blackboard=blackboard,
            collaboration=collaboration,
        )

    def session_root(self, session_id: str) -> Path:
        normalized = str(session_id or "").strip()
        if not normalized:
            raise ValueError("session_id is required")
        return self.root_dir / normalized

    def template_path(self, session_id: str) -> Path:
        return self.session_root(session_id) / "template.json"

    def session_path(self, session_id: str) -> Path:
        return self.session_root(session_id) / "session.json"

    def shared_state_path(self, session_id: str) -> Path:
        return self.session_root(session_id) / "shared_state.json"

    def artifact_registry_path(self, session_id: str) -> Path:
        return self.session_root(session_id) / "artifact_registry.json"

    def blackboard_path(self, session_id: str) -> Path:
        return self.session_root(session_id) / "blackboard.json"

    def collaboration_path(self, session_id: str) -> Path:
        return self.session_root(session_id) / "collaboration.json"

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}
