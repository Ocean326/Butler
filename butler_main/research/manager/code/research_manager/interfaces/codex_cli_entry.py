from __future__ import annotations

from ..contracts import ResearchInvocation
from ..manager import ResearchManager


def build_codex_invocation(
    *,
    goal: str = "",
    unit_id: str = "",
    session_id: str = "",
    workspace: str = "",
    payload: dict | None = None,
    metadata: dict | None = None,
) -> ResearchInvocation:
    return ResearchInvocation(
        entrypoint="codex",
        goal=goal,
        unit_id=unit_id,
        session_id=session_id,
        workspace=workspace,
        payload=payload or {},
        metadata=metadata or {},
    )


def invoke_from_codex(manager: ResearchManager, **kwargs: object):
    return manager.invoke(build_codex_invocation(**kwargs))
