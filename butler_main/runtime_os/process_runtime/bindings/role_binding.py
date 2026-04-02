try:
    from butler_main.multi_agents_os.bindings.role_binding import RoleBinding
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from multi_agents_os.bindings.role_binding import RoleBinding

__all__ = ["RoleBinding"]
