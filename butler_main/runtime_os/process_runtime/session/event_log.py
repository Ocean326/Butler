try:
    from butler_main.multi_agents_os.session.event_log import FileWorkflowEventLog, WorkflowSessionEvent
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from multi_agents_os.session.event_log import FileWorkflowEventLog, WorkflowSessionEvent

__all__ = ["FileWorkflowEventLog", "WorkflowSessionEvent"]
