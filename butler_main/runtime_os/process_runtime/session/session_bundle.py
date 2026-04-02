try:
    from butler_main.multi_agents_os.session.session_bundle import WorkflowSessionBundle
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from multi_agents_os.session.session_bundle import WorkflowSessionBundle

__all__ = ["WorkflowSessionBundle"]
