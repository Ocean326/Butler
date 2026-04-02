"""Compatibility redirect to the formal process-runtime engine surface."""

try:
    from butler_main.runtime_os.process_runtime.engine import ExecutionRuntime
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from runtime_os.process_runtime.engine import ExecutionRuntime

__all__ = ["ExecutionRuntime"]
