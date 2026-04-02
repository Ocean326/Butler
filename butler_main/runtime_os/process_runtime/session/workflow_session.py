try:
    from butler_main.multi_agents_os.session.workflow_session import WorkflowSession
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from multi_agents_os.session.workflow_session import WorkflowSession

__all__ = ["WorkflowSession"]
