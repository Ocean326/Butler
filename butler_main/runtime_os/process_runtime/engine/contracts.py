try:
    from butler_main.agents_os.runtime.contracts import (
        AcceptanceReceipt,
        EDGE_KINDS,
        PROCESS_ROLES,
        STEP_KINDS,
        normalize_edge_kind,
        normalize_failure_class,
        normalize_process_role,
        normalize_step_kind,
    )
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from agents_os.runtime.contracts import (
        AcceptanceReceipt,
        EDGE_KINDS,
        PROCESS_ROLES,
        STEP_KINDS,
        normalize_edge_kind,
        normalize_failure_class,
        normalize_process_role,
        normalize_step_kind,
    )

__all__ = [
    "AcceptanceReceipt",
    "EDGE_KINDS",
    "PROCESS_ROLES",
    "STEP_KINDS",
    "normalize_edge_kind",
    "normalize_failure_class",
    "normalize_process_role",
    "normalize_step_kind",
]
