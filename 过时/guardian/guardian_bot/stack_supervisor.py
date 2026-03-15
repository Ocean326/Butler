from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

from guardian_bot.butler_inspector import inspect_butler_main


class GuardianStackSupervisor:
    def __init__(
        self,
        workspace_root: Path,
        *,
        inspection_interval_seconds: int = 15,
        repair_cooldown_seconds: int = 180,
        heartbeat_stale_seconds: int = 240,
        recovery_timeout_seconds: int = 120,
        heartbeat_soft_failure_limit: int = 1,
    ) -> None:
        self.workspace_root = Path(workspace_root)
        self.inspection_interval_seconds = max(5, int(inspection_interval_seconds or 15))
        self.repair_cooldown_seconds = max(30, int(repair_cooldown_seconds or 180))
        self.heartbeat_stale_seconds = max(60, int(heartbeat_stale_seconds or 240))
        self.recovery_timeout_seconds = max(60, int(recovery_timeout_seconds or 120))
        self.heartbeat_soft_failure_limit = max(1, int(heartbeat_soft_failure_limit or 1))
        self._last_repair_monotonic = 0.0
        self._soft_failure_count = 0

    def _state_path(self) -> Path:
        run_dir = self.workspace_root / "butler_bot_code" / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir / "guardian_stack_supervision.json"

    def _write_state(self, payload: dict) -> None:
        target = self._state_path()
        merged = dict(payload or {})
        merged["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(target)

    def _restart_stack(self) -> tuple[bool, str]:
        manager = self.workspace_root.parent / "guardian" / "manager.ps1"
        if not manager.exists():
            return False, f"guardian manager not found: {manager}"
        try:
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(manager),
                    "restart-stack",
                ],
                cwd=str(manager.parent),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=max(90, self.recovery_timeout_seconds),
            )
        except subprocess.TimeoutExpired:
            return False, "restart-stack timeout"
        except Exception as exc:
            return False, f"restart-stack exception: {exc}"
        text = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
        if completed.returncode != 0:
            return False, text or f"restart-stack exit={completed.returncode}"
        return True, text or "restart-stack done"

    def tick(self, *, trigger: str = "periodic") -> dict:
        inspection = inspect_butler_main(self.workspace_root)
        now = time.monotonic()
        result = {
            "trigger": str(trigger or "periodic"),
            "status": "healthy" if inspection.get("overall", {}).get("healthy") else "degraded",
            "action": "none",
            "detail": str(inspection.get("summary") or ""),
            "inspection": inspection,
        }

        main_ok = bool(inspection.get("main", {}).get("healthy"))
        heartbeat_ok = bool(inspection.get("heartbeat", {}).get("healthy"))
        guardian_ok = bool(inspection.get("guardian_handover", {}).get("healthy"))

        if not heartbeat_ok:
            self._soft_failure_count += 1
        else:
            self._soft_failure_count = 0

        need_repair = (not main_ok) or (not heartbeat_ok and self._soft_failure_count >= self.heartbeat_soft_failure_limit)
        cooldown_remaining = self.repair_cooldown_seconds - (now - self._last_repair_monotonic)
        if need_repair and cooldown_remaining > 0:
            result["status"] = "skipped"
            result["action"] = "cooldown"
            result["detail"] = f"repair cooldown active ({int(cooldown_remaining)}s)"
        elif need_repair:
            ok, detail = self._restart_stack()
            self._last_repair_monotonic = time.monotonic()
            result["status"] = "repaired" if ok else "repair_failed"
            result["action"] = "restart-stack"
            result["detail"] = detail[:1000]
            if ok:
                self._soft_failure_count = 0
        elif not guardian_ok:
            result["status"] = "degraded"
            result["action"] = "observe"
            result["detail"] = str(inspection.get("summary") or "")

        self._write_state(
            {
                "guardian_pid": int(os.getpid()),
                "trigger": result["trigger"],
                "status": result["status"],
                "action": result["action"],
                "detail": result["detail"],
                "soft_failure_count": self._soft_failure_count,
            }
        )
        return result
