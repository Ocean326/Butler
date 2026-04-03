from __future__ import annotations

import os

from butler_main.agents_os.runtime.writeback import AsyncWritebackRunner


class ChatBackgroundServicesRuntime:
    """Chat-owned bootstrap over injected background-service hooks."""

    def __init__(
        self,
        *,
        manager,
        config_provider,
        task_runner: AsyncWritebackRunner | None = None,
    ) -> None:
        self._manager = manager
        self._config_provider = config_provider
        self._task_runner = task_runner or AsyncWritebackRunner()

    def start_background_services(self) -> None:
        manager = self._manager
        if manager._maintenance_started:
            return
        with manager._maintenance_lock:
            if manager._maintenance_started:
                return
            cfg = self._config_provider() or {}
            workspace = str(cfg.get("workspace_root") or os.getcwd())
            timeout = int(cfg.get("agent_timeout", 300))
            model = cfg.get("agent_model", "auto")

            try:
                manager._recover_pending_recent_entries_on_startup(workspace)
            except Exception as exc:
                print(f"[recent-recover] 启动时修复 pending 记忆失败: {exc}", flush=True)

            manager._write_main_process_state(workspace, state="running")
            manager._register_main_process_exit_hooks(workspace)
            if not manager._main_process_state_started:
                self._task_runner.submit(
                    manager._main_process_state_loop,
                    workspace,
                    name="butler-main-state-writer",
                )
                manager._main_process_state_started = True

            self._task_runner.submit(
                manager._maintenance_loop,
                workspace,
                timeout,
                model,
                name="memory-maintenance-scheduler",
            )
            manager._maintenance_started = True
            print("[记忆维护线程] 已启动（定时 05:00）", flush=True)
            print("[后台服务] chat 当前仅启动 recent/memory 所需后台项", flush=True)


__all__ = ["ChatBackgroundServicesRuntime"]
