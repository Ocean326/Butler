try:
    from butler_main.multi_agents_os.session.shared_state import SharedState
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from multi_agents_os.session.shared_state import SharedState

__all__ = ["SharedState"]
