try:
    from butler_main.multi_agents_os.factory.workflow_factory import WorkflowFactory
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from multi_agents_os.factory.workflow_factory import WorkflowFactory

__all__ = ["WorkflowFactory"]
