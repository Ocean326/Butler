from __future__ import annotations

import os


class SelfMindRuntimeService:
    def __init__(self, manager, *, threading_module, time_module) -> None:
        self._manager = manager
        self._threading = threading_module
        self._time = time_module

    def ensure_loop_started(self) -> None:
        manager = self._manager
        if not manager._self_mind_enabled():
            return
        with manager._self_mind_lock:
            if manager._self_mind_started:
                return
            manager._self_mind_loop_token += 1
            loop_token = manager._self_mind_loop_token
            self._threading.Thread(
                target=self.run_loop,
                args=(loop_token,),
                daemon=True,
                name="butler-self-mind",
            ).start()
            manager._self_mind_started = True
            print("[self-mind] 独立意识循环已启动", flush=True)

    def restart_loop(self) -> tuple[bool, str]:
        manager = self._manager
        if not manager._self_mind_enabled():
            return False, "self_mind 当前未启用。"
        with manager._self_mind_lock:
            manager._self_mind_loop_token += 1
            loop_token = manager._self_mind_loop_token
            self._threading.Thread(
                target=self.run_loop,
                args=(loop_token,),
                daemon=True,
                name="butler-self-mind",
            ).start()
            manager._self_mind_started = True
        return True, "已重启意识循环。"

    def run_loop(self, loop_token: int | None = None) -> None:
        manager = self._manager
        while True:
            try:
                if loop_token is not None and loop_token != manager._self_mind_loop_token:
                    return
                cfg = manager._config_provider() or {}
                workspace = str((cfg or {}).get("workspace_root") or os.getcwd())
                if not manager._self_mind_enabled():
                    self._time.sleep(60)
                    continue
                state = manager._load_self_mind_state(workspace)
                try:
                    last_epoch = float(state.get("last_cycle_epoch") or 0.0)
                except Exception:
                    last_epoch = 0.0
                interval = manager._self_mind_cycle_interval_seconds()
                remaining = interval - max(0.0, self._time.time() - last_epoch) if last_epoch > 0 else 0.0
                if remaining > 0:
                    self._time.sleep(min(remaining, 30.0))
                    continue
                manager._run_self_mind_cycle_once(workspace)
            except Exception as exc:
                print(f"[self-mind] 独立循环失败: {exc}", flush=True)
                self._time.sleep(30)
