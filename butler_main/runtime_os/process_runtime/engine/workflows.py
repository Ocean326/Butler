try:
    from butler_main.agents_os.runtime.workflows import StepResult
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from agents_os.runtime.workflows import StepResult

__all__ = ["StepResult"]
