try:
    from butler_main.agents_os.governance.bash_policy import (
        check_bash_chain_permissions,
        extract_bash_commands,
        matches_bash_permission,
    )
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from agents_os.governance.bash_policy import (
        check_bash_chain_permissions,
        extract_bash_commands,
        matches_bash_permission,
    )

__all__ = [
    "check_bash_chain_permissions",
    "extract_bash_commands",
    "matches_bash_permission",
]
