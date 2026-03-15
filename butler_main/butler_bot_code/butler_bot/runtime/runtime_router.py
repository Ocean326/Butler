from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import shutil

from butler_paths import resolve_butler_root


@dataclass(frozen=True)
class RuntimeRoutingDecision:
    runtime_request: dict
    runtime_profile: dict
    manager_note: str


class RuntimeRouter:
    WINDOW_HOURS = 5

    def route_branch(self, workspace: str, branch: dict, model: str, cfg: dict | None = None) -> RuntimeRoutingDecision:
        config = dict(cfg or {})
        router_cfg = self._router_cfg(config)
        explicit = dict(branch.get("runtime_profile") or {}) if isinstance(branch.get("runtime_profile"), dict) else {}
        runtime_request = self._base_runtime_request(explicit, model)
        manager_note = ""

        if explicit:
            manager_note = "using explicit branch runtime_profile"
        else:
            role = str(branch.get("process_role") or "").strip().lower()
            execution_kind = str(branch.get("execution_kind") or "").strip().lower()
            team_id = str(branch.get("team_id") or "").strip()
            capability_type = str(branch.get("capability_type") or "").strip().lower()
            prefer_codex = bool(router_cfg.get("prefer_codex_specialized_branches", False))
            if role == "acceptance" or execution_kind in {"acceptance", "review"}:
                if prefer_codex:
                    runtime_request.update({"cli": "codex", "model": "gpt-5", "reasoning_effort": "high", "why": "acceptance"})
                    manager_note = "acceptance branch prefers codex/gpt-5"
                else:
                    runtime_request.update({"cli": "cursor", "model": str(model or "auto").strip() or "auto", "reasoning_effort": "medium", "why": "acceptance"})
                    manager_note = "acceptance branch uses cursor by default"
            elif role == "test" or execution_kind in {"test", "evaluate", "maintenance"}:
                if prefer_codex:
                    runtime_request.update({"cli": "codex", "model": "gpt-5", "reasoning_effort": "medium", "why": "verification"})
                    manager_note = "verification branch prefers codex/gpt-5"
                else:
                    runtime_request.update({"cli": "cursor", "model": str(model or "auto").strip() or "auto", "reasoning_effort": "medium", "why": "verification"})
                    manager_note = "verification branch uses cursor by default"
            elif team_id or capability_type in {"team", "analysis"}:
                if prefer_codex:
                    runtime_request.update({"cli": "codex", "model": "gpt-5", "reasoning_effort": "medium", "why": "complex orchestration"})
                    manager_note = "team/analysis branch prefers codex/gpt-5"
                else:
                    runtime_request.update({"cli": "cursor", "model": str(model or "auto").strip() or "auto", "reasoning_effort": "medium", "why": "complex orchestration"})
                    manager_note = "team/analysis branch uses cursor by default"
            else:
                runtime_request.update({"cli": "cursor", "model": str(model or "auto").strip() or "auto", "reasoning_effort": "low", "why": "default executor"})
                manager_note = "default executor branch uses cursor"

        runtime_request["cli"] = self._normalize_cli_name(str(runtime_request.get("cli") or "cursor"))
        if runtime_request["cli"] == "codex" and not self._cli_available("codex", config):
            runtime_request["cli"] = "cursor"
            runtime_request["model"] = str(model or "auto").strip() or "auto"
            runtime_request["why"] = f"{str(runtime_request.get('why') or '').strip()} | codex unavailable fallback".strip(" |")
            manager_note = (manager_note + "; " if manager_note else "") + "codex unavailable fallback to cursor"
        if runtime_request["cli"] == "codex" and not self._codex_allowed(workspace, config):
            runtime_request["cli"] = "cursor"
            runtime_request["model"] = str(model or "auto").strip() or "auto"
            runtime_request["why"] = f"{str(runtime_request.get('why') or '').strip()} | codex quota guard fallback".strip(" |")
            manager_note = (manager_note + "; " if manager_note else "") + "codex quota guard fallback to cursor"
        if runtime_request["cli"] == "codex":
            self._record_codex_selection(workspace)

        runtime_profile = {
            "cli": runtime_request.get("cli") or "cursor",
            "model": runtime_request.get("model") or (str(model or "auto").strip() or "auto"),
            "reasoning_effort": runtime_request.get("reasoning_effort") or "",
            "why": runtime_request.get("why") or "",
        }
        return RuntimeRoutingDecision(runtime_request=runtime_request, runtime_profile=runtime_profile, manager_note=manager_note)

    def _base_runtime_request(self, explicit: dict, model: str) -> dict:
        request = dict(explicit or {})
        request.setdefault("cli", "cursor")
        request.setdefault("model", str(model or "auto").strip() or "auto")
        request.setdefault("reasoning_effort", "")
        request.setdefault("why", "")
        return request

    def _normalize_cli_name(self, cli_name: str) -> str:
        lowered = str(cli_name or "").strip().lower()
        return "codex" if lowered in {"codex", "codex-cli"} else "cursor"

    def _cli_available(self, cli_name: str, cfg: dict) -> bool:
        requested = self._normalize_cli_name(cli_name)
        providers = cfg.get("cli_runtime", {}).get("providers", {}) if isinstance(cfg.get("cli_runtime"), dict) else {}
        provider = dict(providers.get(requested) or {})
        if provider and not provider.get("enabled", True):
            return False
        if requested == "cursor":
            return os.path.isfile(self._resolve_cursor_cli_cmd_path(cfg))
        command = str(provider.get("path") or "codex").strip() or "codex"
        return self._command_exists(command)

    def _resolve_cursor_cli_cmd_path(self, cfg: dict) -> str:
        configured = str(cfg.get("cursor_cli_path") or "").strip()
        if configured and os.path.isfile(configured):
            return configured
        base = os.environ.get("LOCALAPPDATA", "")
        legacy = os.path.join(base, "cursor-agent", "versions", "dist-package", "cursor-agent.cmd")
        if os.path.isfile(legacy):
            return legacy
        versions_dir = os.path.join(base, "cursor-agent", "versions")
        if os.path.isdir(versions_dir):
            try:
                subs = [item for item in os.listdir(versions_dir) if os.path.isdir(os.path.join(versions_dir, item))]
                subs.sort(reverse=True)
                for version in subs:
                    candidate = os.path.join(versions_dir, version, "cursor-agent.cmd")
                    if os.path.isfile(candidate):
                        return candidate
            except OSError:
                pass
        return legacy

    def _command_exists(self, command: str) -> bool:
        candidate = str(command or "").strip()
        if not candidate:
            return False
        if os.path.isfile(candidate):
            return True
        return shutil.which(candidate) is not None

    def _router_cfg(self, cfg: dict) -> dict:
        raw = cfg.get("runtime_router") if isinstance(cfg.get("runtime_router"), dict) else {}
        return dict(raw or {})

    def _codex_usage_path(self, workspace: str) -> Path:
        root = resolve_butler_root(workspace)
        path = root / "butler_main" / "butler_bot_code" / "run" / "runtime_router_codex_usage.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _load_codex_usage(self, workspace: str) -> dict:
        path = self._codex_usage_path(workspace)
        if not path.exists():
            return {"window_hours": self.WINDOW_HOURS, "selected_at": []}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"window_hours": self.WINDOW_HOURS, "selected_at": []}
        if not isinstance(payload, dict):
            return {"window_hours": self.WINDOW_HOURS, "selected_at": []}
        payload["selected_at"] = [str(item).strip() for item in payload.get("selected_at") or [] if str(item).strip()]
        return payload

    def _save_codex_usage(self, workspace: str, payload: dict) -> None:
        path = self._codex_usage_path(workspace)
        normalized = dict(payload or {})
        normalized["window_hours"] = self.WINDOW_HOURS
        normalized["selected_at"] = [str(item).strip() for item in normalized.get("selected_at") or [] if str(item).strip()][-200:]
        path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    def _codex_allowed(self, workspace: str, cfg: dict) -> bool:
        router_cfg = self._router_cfg(cfg)
        limit = int(router_cfg.get("codex_max_selected_per_window") or 0)
        if limit <= 0:
            return True
        payload = self._load_codex_usage(workspace)
        cutoff = datetime.now() - timedelta(hours=self.WINDOW_HOURS)
        kept = []
        for item in payload.get("selected_at") or []:
            try:
                ts = datetime.strptime(str(item), "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if ts >= cutoff:
                kept.append(item)
        payload["selected_at"] = kept
        self._save_codex_usage(workspace, payload)
        return len(kept) < limit

    def _record_codex_selection(self, workspace: str) -> None:
        payload = self._load_codex_usage(workspace)
        payload.setdefault("selected_at", [])
        payload["selected_at"].append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self._save_codex_usage(workspace, payload)
