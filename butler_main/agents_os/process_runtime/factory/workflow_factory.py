"""Compatibility redirect to the formal process-runtime factory surface."""

if __name__.startswith("butler_main."):
    from butler_main.runtime_os.process_runtime.factory import WorkflowFactory
else:  # pragma: no cover - compatibility for top-level package imports
    from runtime_os.process_runtime.factory import WorkflowFactory

__all__ = ["WorkflowFactory"]
