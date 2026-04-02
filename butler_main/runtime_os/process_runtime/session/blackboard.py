try:
    from butler_main.multi_agents_os.session.blackboard import BlackboardEntry, WorkflowBlackboard
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from multi_agents_os.session.blackboard import BlackboardEntry, WorkflowBlackboard

__all__ = ["BlackboardEntry", "WorkflowBlackboard"]
