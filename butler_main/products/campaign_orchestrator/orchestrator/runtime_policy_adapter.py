from __future__ import annotations

from datetime import datetime, timedelta
import json

from butler_main.runtime_os.agent_runtime import RuntimePolicyDecision, cli_runner

from .runtime_paths import resolve_orchestrator_run_file


class ButlerRuntimePolicyAdapter:
    WINDOW_HOURS = 5

    def route_branch(self, workspace: str, branch: dict, model: str, cfg: dict | None = None) -> RuntimePolicyDecision:
        config = dict(cfg or {})
        router_cfg = self._router_cfg(config)
        explicit = dict(branch.get("runtime_profile") or {}) if isinstance(branch.get("runtime_profile"), dict) else {}
        manager_note = ""

        if explicit:
            request = self._normalized_request(config, explicit, model)
            manager_note = "using explicit branch runtime_profile"
        else:
            request, manager_note = self._policy_request(branch, model, router_cfg)
            request = self._normalized_request(config, request, model)

        request["cli"] = self._normalize_cli_name(request.get("cli"))
        final_cli = str(request.get("cli") or "cursor").strip()

        if not cli_runner.cli_provider_available(final_cli, config):
            fallback_cli = self._fallback_cli(final_cli, config)
            if fallback_cli:
                request["cli"] = fallback_cli
                request["model"] = cli_runner.normalize_model_name(request.get("model"), fallback_cli)
                request["why"] = self._append_why(request, f"{final_cli} unavailable fallback")
                manager_note = self._append_note(manager_note, f"{final_cli} unavailable fallback to {fallback_cli}")

        if str(request.get("cli") or "").strip() == "codex" and not self._codex_allowed(workspace, config):
            fallback_cli = self._fallback_cli("codex", config) or "cursor"
            request["cli"] = fallback_cli
            request["model"] = cli_runner.normalize_model_name(model, fallback_cli)
            request["why"] = self._append_why(request, "codex quota guard fallback")
            manager_note = self._append_note(manager_note, f"codex quota guard fallback to {fallback_cli}")

        if str(request.get("cli") or "").strip() == "codex":
            self._record_codex_selection(workspace)

        runtime_profile = {
            "cli": str(request.get("cli") or "cursor").strip() or "cursor",
            "model": str(request.get("model") or cli_runner.normalize_model_name(model, request.get("cli")) or "auto").strip() or "auto",
            "reasoning_effort": str(request.get("reasoning_effort") or "").strip(),
            "why": str(request.get("why") or "").strip(),
        }
        return RuntimePolicyDecision(runtime_request=request, runtime_profile=runtime_profile, manager_note=manager_note)

    def _policy_request(self, branch: dict, model: str, router_cfg: dict) -> tuple[dict, str]:
        role = str(branch.get("process_role") or "").strip().lower()
        execution_kind = str(branch.get("execution_kind") or "").strip().lower()
        team_id = str(branch.get("team_id") or "").strip()
        capability_type = str(branch.get("capability_type") or "").strip().lower()
        prefer_codex = bool(router_cfg.get("prefer_codex_specialized_branches", False))
        cursor_model = str(model or "auto").strip() or "auto"

        if role == "acceptance" or execution_kind in {"acceptance", "review"}:
            if prefer_codex:
                return ({"cli": "codex", "model": "gpt-5", "reasoning_effort": "high", "why": "acceptance"}, "acceptance branch prefers codex/gpt-5")
            return ({"cli": "cursor", "model": cursor_model, "reasoning_effort": "medium", "why": "acceptance"}, "acceptance branch uses cursor by default")

        if role == "test" or execution_kind in {"test", "evaluate", "maintenance"}:
            if prefer_codex:
                return ({"cli": "codex", "model": "gpt-5", "reasoning_effort": "medium", "why": "verification"}, "verification branch prefers codex/gpt-5")
            return ({"cli": "cursor", "model": cursor_model, "reasoning_effort": "medium", "why": "verification"}, "verification branch uses cursor by default")

        if team_id or capability_type in {"team", "analysis"}:
            if prefer_codex:
                return ({"cli": "codex", "model": "gpt-5", "reasoning_effort": "medium", "why": "complex orchestration"}, "team/analysis branch prefers codex/gpt-5")
            return ({"cli": "cursor", "model": cursor_model, "reasoning_effort": "medium", "why": "complex orchestration"}, "team/analysis branch uses cursor by default")

        return ({"cli": "cursor", "model": cursor_model, "reasoning_effort": "low", "why": "default executor"}, "default executor branch uses cursor")

    def _normalized_request(self, cfg: dict, request: dict, model: str) -> dict:
        raw = dict(request or {})
        resolved = cli_runner.resolve_runtime_request(cfg, raw, model_override=raw.get("model") or model)
        resolved["reasoning_effort"] = str(raw.get("reasoning_effort") or "").strip()
        resolved["why"] = str(raw.get("why") or "").strip()
        return resolved

    def _normalize_cli_name(self, cli_name: str | None) -> str:
        lowered = str(cli_name or "").strip().lower()
        return cli_runner.CLI_PROVIDER_ALIASES.get(lowered, "cursor")

    def _fallback_cli(self, current_cli: str, cfg: dict) -> str:
        current = self._normalize_cli_name(current_cli)
        for candidate in cli_runner.available_cli_modes(cfg):
            if candidate != current:
                return candidate
        return ""

    def _append_note(self, current: str, suffix: str) -> str:
        current_text = str(current or "").strip()
        extra = str(suffix or "").strip()
        if not extra:
            return current_text
        if not current_text:
            return extra
        return current_text + "; " + extra

    def _append_why(self, request: dict, suffix: str) -> str:
        current = str((request or {}).get("why") or "").strip()
        extra = str(suffix or "").strip()
        if not extra:
            return current
        if not current:
            return extra
        return current + " | " + extra

    def _router_cfg(self, cfg: dict) -> dict:
        raw = cfg.get("runtime_router") if isinstance(cfg.get("runtime_router"), dict) else {}
        return dict(raw or {})

    def _codex_usage_path(self, workspace: str):
        return resolve_orchestrator_run_file(workspace, "agents_os_runtime_policy_codex_usage.json")

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
        kept: list[str] = []
        for item in payload.get("selected_at") or []:
            try:
                timestamp = datetime.strptime(str(item), "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if timestamp >= cutoff:
                kept.append(item)
        payload["selected_at"] = kept
        self._save_codex_usage(workspace, payload)
        return len(kept) < limit

    def _record_codex_selection(self, workspace: str) -> None:
        payload = self._load_codex_usage(workspace)
        payload.setdefault("selected_at", [])
        payload["selected_at"].append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self._save_codex_usage(workspace, payload)
