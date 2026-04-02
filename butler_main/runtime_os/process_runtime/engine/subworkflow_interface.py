try:
    from butler_main.agents_os.runtime.subworkflow_interface import SubworkflowCapability
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from agents_os.runtime.subworkflow_interface import SubworkflowCapability

__all__ = ["SubworkflowCapability"]
