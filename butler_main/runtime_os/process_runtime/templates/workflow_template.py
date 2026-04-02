try:
    from butler_main.multi_agents_os.templates.workflow_template import WorkflowTemplate
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from multi_agents_os.templates.workflow_template import WorkflowTemplate

__all__ = ["WorkflowTemplate"]
