from __future__ import annotations

try:
    from butler_main.runtime_os.process_runtime.engine.receipts import (
        ExecutionReceipt,
        RUNTIME_VERDICT_STATUSES,
        RuntimeVerdict,
        TERMINAL_RUNTIME_VERDICT_STATUSES,
        WorkflowReceipt,
        normalize_runtime_verdict_status,
    )
except ModuleNotFoundError:  # pragma: no cover - compatibility for top-level package imports
    from runtime_os.process_runtime.engine.receipts import (
        ExecutionReceipt,
        RUNTIME_VERDICT_STATUSES,
        RuntimeVerdict,
        TERMINAL_RUNTIME_VERDICT_STATUSES,
        WorkflowReceipt,
        normalize_runtime_verdict_status,
    )

__all__ = [
    "ExecutionReceipt",
    "RUNTIME_VERDICT_STATUSES",
    "RuntimeVerdict",
    "TERMINAL_RUNTIME_VERDICT_STATUSES",
    "WorkflowReceipt",
    "normalize_runtime_verdict_status",
]
