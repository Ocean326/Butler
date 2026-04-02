if __name__.startswith("butler_main."):
    from butler_main.runtime_os.process_runtime.session import FileWorkflowEventLog, WorkflowSessionEvent
else:  # pragma: no cover - compatibility for top-level package imports
    from runtime_os.process_runtime.session import FileWorkflowEventLog, WorkflowSessionEvent

__all__ = ["FileWorkflowEventLog", "WorkflowSessionEvent"]
