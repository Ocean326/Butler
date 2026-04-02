from __future__ import annotations

import sys

try:
    from .interfaces.runner import (
        ORCHESTRATOR_LOCK_FILE_NAME,
        ORCHESTRATOR_PID_FILE_NAME,
        ORCHESTRATOR_RUN_STATE_FILE_NAME,
        ORCHESTRATOR_TICK_SECONDS_DEFAULT,
        ORCHESTRATOR_WATCHDOG_STATE_FILE_NAME,
        build_orchestrator_runtime_state_store,
        main,
        run_orchestrator_cycle,
        run_orchestrator_service,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script/import fallback
    from butler_main.orchestrator.interfaces.runner import (
        ORCHESTRATOR_LOCK_FILE_NAME,
        ORCHESTRATOR_PID_FILE_NAME,
        ORCHESTRATOR_RUN_STATE_FILE_NAME,
        ORCHESTRATOR_TICK_SECONDS_DEFAULT,
        ORCHESTRATOR_WATCHDOG_STATE_FILE_NAME,
        build_orchestrator_runtime_state_store,
        main,
        run_orchestrator_cycle,
        run_orchestrator_service,
    )

__all__ = [
    "ORCHESTRATOR_LOCK_FILE_NAME",
    "ORCHESTRATOR_PID_FILE_NAME",
    "ORCHESTRATOR_RUN_STATE_FILE_NAME",
    "ORCHESTRATOR_TICK_SECONDS_DEFAULT",
    "ORCHESTRATOR_WATCHDOG_STATE_FILE_NAME",
    "build_orchestrator_runtime_state_store",
    "main",
    "run_orchestrator_cycle",
    "run_orchestrator_service",
]


if __name__ == "__main__":
    sys.exit(main())
