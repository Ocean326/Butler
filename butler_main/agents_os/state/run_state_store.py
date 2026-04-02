from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import time
from typing import Callable

try:
    from runtime_os.fs_retention import DEFAULT_RETENTION_DAYS, prune_path_children
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from butler_main.runtime_os.fs_retention import DEFAULT_RETENTION_DAYS, prune_path_children

from .models import RuntimeStatusSnapshot


PidProbe = Callable[[int], dict]


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _write_text_atomic(path: Path, text: str, *, keep_backup: bool = False) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_name(f"{target.name}.tmp-{os.getpid()}")
    temp_path.write_text(text, encoding="utf-8")
    if keep_backup and target.exists():
        backup = target.with_name(target.name + ".bak")
        backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    temp_path.replace(target)


class FileRuntimeStateStore:
    def __init__(
        self,
        root_dir: str | Path,
        *,
        pid_file_name: str = "runtime.pid",
        watchdog_state_file_name: str = "watchdog_state.json",
        run_state_file_name: str = "run_state.json",
        lock_file_name: str = "runtime.lock",
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.retention_days = max(1, int(retention_days or DEFAULT_RETENTION_DAYS))
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._pid_file_name = pid_file_name
        self._watchdog_state_file_name = watchdog_state_file_name
        self._run_state_file_name = run_state_file_name
        self._lock_file_name = lock_file_name
        self._prune_retained_dirs()

    def archive_dir(self) -> Path:
        path = self.root_dir / "archive"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def traces_dir(self) -> Path:
        path = self.root_dir / "traces"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def drafts_dir(self) -> Path:
        path = self.root_dir / "drafts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def orphan_dir(self) -> Path:
        path = self.root_dir / "orphans"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _prune_retained_dirs(self) -> None:
        for name in ("archive", "traces", "drafts", "orphans"):
            prune_path_children(
                self.root_dir / name,
                retention_days=self.retention_days,
                include_files=True,
                include_dirs=True,
            )

    def pid_file(self) -> Path:
        return self.root_dir / self._pid_file_name

    def watchdog_state_file(self) -> Path:
        return self.root_dir / self._watchdog_state_file_name

    def run_state_file(self) -> Path:
        return self.root_dir / self._run_state_file_name

    def lock_file(self) -> Path:
        return self.root_dir / self._lock_file_name

    def _write_json(self, path: Path, payload: dict) -> None:
        _write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2), keep_backup=True)

    def _read_json(self, path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def read_pid(self) -> int:
        try:
            return int((self.pid_file().read_text(encoding="utf-8") or "").strip())
        except Exception:
            return 0

    def write_pid(self, pid: int) -> None:
        if int(pid or 0) <= 0:
            return
        _write_text_atomic(self.pid_file(), str(int(pid)), keep_backup=False)

    def clear_pid(self) -> None:
        try:
            self.pid_file().unlink(missing_ok=True)
        except Exception:
            pass

    def _default_pid_probe(self, pid: int) -> dict:
        alive = False
        if pid > 0:
            try:
                os.kill(pid, 0)
                alive = True
            except Exception:
                alive = False
        return {"alive": alive, "matches": alive}

    def probe_pid(self, pid: int, pid_probe: PidProbe | None = None) -> dict:
        probe = pid_probe or self._default_pid_probe
        try:
            payload = probe(int(pid or 0)) or {}
        except Exception:
            payload = {}
        alive = bool(payload.get("alive"))
        matches = bool(payload.get("matches", alive))
        return {"alive": alive, "matches": matches}

    def write_run_state(
        self,
        *,
        run_id: str,
        state: str,
        phase: str,
        pid: int = 0,
        note: str = "",
        error: str = "",
        traceback_text: str = "",
    ) -> dict:
        payload = {
            "updated_at": _now_text(),
            "run_id": str(run_id or "").strip(),
            "state": str(state or "unknown").strip() or "unknown",
            "phase": str(phase or "unknown").strip() or "unknown",
            "pid": int(pid or 0),
            "note": str(note or "").strip()[:500],
            "error": str(error or "").strip()[:1000],
            "traceback": str(traceback_text or "").strip()[:6000],
        }
        self._write_json(self.run_state_file(), payload)
        return payload

    def read_run_state(self) -> dict:
        return self._read_json(self.run_state_file())

    def write_watchdog_state(
        self,
        *,
        state: str,
        pid: int = 0,
        cooldown_until_epoch: float = 0.0,
        restart_inhibit_until_epoch: float = 0.0,
        last_exit_code: int | None = None,
        note: str = "",
    ) -> dict:
        payload = {
            "updated_at": _now_text(),
            "state": str(state or "unknown").strip() or "unknown",
            "pid": int(pid or 0),
            "cooldown_until_epoch": float(cooldown_until_epoch or 0.0),
            "cooldown_until": datetime.fromtimestamp(cooldown_until_epoch).strftime("%Y-%m-%d %H:%M:%S") if cooldown_until_epoch and cooldown_until_epoch > 0 else "",
            "restart_inhibit_until_epoch": float(restart_inhibit_until_epoch or 0.0),
            "restart_inhibit_until": datetime.fromtimestamp(restart_inhibit_until_epoch).strftime("%Y-%m-%d %H:%M:%S") if restart_inhibit_until_epoch and restart_inhibit_until_epoch > 0 else "",
        }
        if last_exit_code is not None:
            payload["last_exit_code"] = int(last_exit_code)
        if note:
            payload["note"] = str(note).strip()[:300]
        self._write_json(self.watchdog_state_file(), payload)
        return payload

    def read_watchdog_state(self) -> dict:
        return self._read_json(self.watchdog_state_file())

    def stale_info(
        self,
        *,
        stale_seconds: int,
        tracked_pid: int = 0,
        now_epoch: float | None = None,
        pid_probe: PidProbe | None = None,
    ) -> tuple[bool, str]:
        payload = self.read_run_state()
        if not payload:
            return False, ""
        if str(payload.get("state") or "").strip().lower() != "running":
            return False, ""
        run_state_pid = int(payload.get("pid") or 0)
        if tracked_pid > 0 and run_state_pid > 0 and tracked_pid != run_state_pid:
            return False, ""
        updated_at = str(payload.get("updated_at") or "").strip()
        if not updated_at:
            return False, ""
        try:
            updated_dt = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return False, ""
        current = time.time() if now_epoch is None else float(now_epoch)
        age_seconds = max(0, int(current - updated_dt.timestamp()))
        pid_status = self.probe_pid(run_state_pid, pid_probe=pid_probe)
        phase = str(payload.get("phase") or "unknown").strip() or "unknown"
        if age_seconds <= stale_seconds and pid_status["alive"]:
            return False, ""
        if not pid_status["alive"]:
            return True, f"run_state stale: pid={run_state_pid} not alive, phase={phase}"
        return True, f"run_state stale: age={age_seconds}s > {stale_seconds}s, phase={phase}"

    def cleanup_before_start(self, *, pid_probe: PidProbe | None = None) -> dict:
        archived: list[str] = []
        owner = self.read_pid()
        if owner > 0 and self.probe_pid(owner, pid_probe=pid_probe)["alive"]:
            return {"skipped": True, "reason": f"pid-alive:{owner}", "archived": archived}
        for path in (self.watchdog_state_file(), self.run_state_file(), self.lock_file()):
            if not path.exists():
                continue
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target = self.archive_dir() / f"{stamp}_{path.name}"
            try:
                path.replace(target)
                archived.append(target.name)
            except Exception:
                pass
        self.clear_pid()
        try:
            self.lock_file().unlink(missing_ok=True)
        except Exception:
            pass
        return {"skipped": False, "archived": archived}

    def acquire_lock(self, *, current_pid: int, pid_probe: PidProbe | None = None) -> tuple[bool, Path]:
        lock_path = self.lock_file()
        for _ in range(3):
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(fd, str(int(current_pid)).encode("utf-8"))
                finally:
                    os.close(fd)
                return True, lock_path
            except FileExistsError:
                owner = 0
                try:
                    owner = int((lock_path.read_text(encoding="utf-8") or "").strip())
                except Exception:
                    owner = 0
                if owner > 0 and self.probe_pid(owner, pid_probe=pid_probe)["alive"]:
                    return False, lock_path
                try:
                    lock_path.unlink(missing_ok=True)
                except Exception:
                    pass
        return False, lock_path

    def release_lock(self) -> None:
        try:
            self.lock_file().unlink(missing_ok=True)
        except Exception:
            pass

    def status_snapshot(
        self,
        *,
        enabled: bool,
        stale_seconds: int,
        tracked_pid: int = 0,
        pid_probe: PidProbe | None = None,
    ) -> RuntimeStatusSnapshot:
        watchdog = self.read_watchdog_state()
        run_state = self.read_run_state()
        pid = int(watchdog.get("pid") or run_state.get("pid") or self.read_pid() or tracked_pid or 0)
        probe = self.probe_pid(pid, pid_probe=pid_probe)
        stale, stale_note = self.stale_info(stale_seconds=stale_seconds, tracked_pid=tracked_pid, pid_probe=pid_probe)
        process_state = "running" if probe["alive"] and probe["matches"] else "stopped"
        if stale:
            process_state = "stale"
        return RuntimeStatusSnapshot(
            config_state="enabled" if enabled else "disabled",
            process_state=process_state,
            watchdog_state=str(watchdog.get("state") or "unknown").strip() or "unknown",
            run_state=str(run_state.get("state") or "unknown").strip() or "unknown",
            progress_state="stalled" if stale else ("progressing" if probe["alive"] else "unknown"),
            pid=pid,
            run_id=str(run_state.get("run_id") or "").strip(),
            phase=str(run_state.get("phase") or "").strip(),
            updated_at=str(run_state.get("updated_at") or watchdog.get("updated_at") or "").strip(),
            note=stale_note or str(watchdog.get("note") or run_state.get("note") or "").strip(),
        )
