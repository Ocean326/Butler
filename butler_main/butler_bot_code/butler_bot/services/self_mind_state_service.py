from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from butler_paths import SELF_MIND_DIR_REL, resolve_butler_root


class SelfMindStateService:
    def __init__(
        self,
        manager,
        *,
        raw_file_name: str,
        review_file_name: str,
        behavior_mirror_file_name: str,
        state_file_name: str,
        bridge_file_name: str,
        cognition_index_file_name: str,
        cognition_l1_dir_name: str,
        cognition_l2_dir_name: str,
        perception_file_name: str,
        tell_user_receive_id_key: str,
        tell_user_receive_id_type_key: str,
    ) -> None:
        self._manager = manager
        self._raw_file_name = raw_file_name
        self._review_file_name = review_file_name
        self._behavior_mirror_file_name = behavior_mirror_file_name
        self._state_file_name = state_file_name
        self._bridge_file_name = bridge_file_name
        self._cognition_index_file_name = cognition_index_file_name
        self._cognition_l1_dir_name = cognition_l1_dir_name
        self._cognition_l2_dir_name = cognition_l2_dir_name
        self._perception_file_name = perception_file_name
        self._tell_user_receive_id_key = tell_user_receive_id_key
        self._tell_user_receive_id_type_key = tell_user_receive_id_type_key

    def self_mind_dir(self, workspace: str) -> Path:
        return resolve_butler_root(workspace or os.getcwd()) / SELF_MIND_DIR_REL

    def context_path(self, workspace: str) -> Path:
        return self.self_mind_dir(workspace) / "current_context.md"

    def log_dir(self, workspace: str) -> Path:
        return self.self_mind_dir(workspace) / "logs"

    def raw_path(self, workspace: str) -> Path:
        return self.self_mind_dir(workspace) / self._raw_file_name

    def review_path(self, workspace: str) -> Path:
        return self.self_mind_dir(workspace) / self._review_file_name

    def behavior_mirror_path(self, workspace: str) -> Path:
        return self.self_mind_dir(workspace) / self._behavior_mirror_file_name

    def state_path(self, workspace: str) -> Path:
        return self.self_mind_dir(workspace) / self._state_file_name

    def log_path(self, workspace: str) -> Path:
        return self.log_dir(workspace) / f"mental_stream_{datetime.now().strftime('%Y%m%d')}.jsonl"

    def daily_dir(self, workspace: str) -> Path:
        return self.self_mind_dir(workspace) / "daily"

    def daily_summary_path(self, workspace: str) -> Path:
        return self.daily_dir(workspace) / f"{datetime.now().strftime('%Y%m%d')}.md"

    def cognition_dir(self, workspace: str) -> Path:
        return self.self_mind_dir(workspace) / "cognition"

    def cognition_index_path(self, workspace: str) -> Path:
        return self.cognition_dir(workspace) / self._cognition_index_file_name

    def cognition_l1_dir(self, workspace: str) -> Path:
        return self.cognition_dir(workspace) / self._cognition_l1_dir_name

    def cognition_l2_dir(self, workspace: str) -> Path:
        return self.cognition_dir(workspace) / self._cognition_l2_dir_name

    def perception_path(self, workspace: str) -> Path:
        return self.self_mind_dir(workspace) / self._perception_file_name

    def domain_dir(self, workspace: str, domain: str) -> Path:
        return self.self_mind_dir(workspace) / domain

    def load_context_excerpt(self, workspace: str, max_chars: int | None = None) -> str:
        manager = self._manager
        effective_max = manager._self_mind_context_max_chars() if max_chars is None else max_chars
        return manager._load_markdown_excerpt(self.context_path(workspace), max_chars=effective_max)

    def load_state(self, workspace: str) -> dict:
        return self._manager._load_json_store(self.state_path(workspace), lambda: {"version": 1})

    def save_state(self, workspace: str, payload: dict) -> None:
        self._manager._save_json_store(self.state_path(workspace), {"version": 1, **dict(payload or {})})

    def talk_target(self, cfg: dict) -> tuple[str, str]:
        settings = self._manager._self_mind_settings()
        target_id = str(settings.get("talk_receive_id") or "").strip()
        target_type = str(settings.get("talk_receive_id_type") or "open_id").strip() or "open_id"
        if target_id:
            return target_id, target_type
        target_id = str((cfg or {}).get(self._tell_user_receive_id_key) or "").strip()
        target_type = str((cfg or {}).get(self._tell_user_receive_id_type_key) or "open_id").strip() or "open_id"
        return target_id, target_type

    def talk_delivery_override(self) -> dict | None:
        settings = self._manager._self_mind_settings()
        app_id = str(settings.get("talk_app_id") or "").strip()
        app_secret = str(settings.get("talk_app_secret") or "").strip()
        if not app_id or not app_secret:
            return None
        return {"app_id": app_id, "app_secret": app_secret}

    def listener_delivery_override(self) -> dict | None:
        settings = self._manager._self_mind_settings()
        app_id = str(settings.get("listener_app_id") or settings.get("talk_app_id") or "").strip()
        app_secret = str(settings.get("listener_app_secret") or settings.get("talk_app_secret") or "").strip()
        if not app_id or not app_secret:
            return None
        return {"app_id": app_id, "app_secret": app_secret}

    def listener_enabled(self) -> bool:
        settings = self._manager._self_mind_settings()
        raw = settings.get("listener_enabled")
        if raw is None:
            return self.listener_delivery_override() is not None
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        return bool(raw)
