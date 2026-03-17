from __future__ import annotations


class RecentMemoryAdapter:
    def __init__(self, manager) -> None:
        self._manager = manager

    def load_recent_entries(self, workspace: str, pool: str = "talk") -> list[dict]:
        return list(self._manager._load_recent_entries(workspace, pool=pool))

    def save_recent_entries(self, workspace: str, entries: list[dict], pool: str = "talk") -> None:
        self._manager._save_recent_entries(workspace, entries, pool=pool)

    def load_profile_excerpt(self, workspace: str, max_chars: int = 1000) -> str:
        return self._manager._load_current_user_profile_excerpt(workspace, max_chars=max_chars)

    def query_local_memory(self, workspace: str, query_text: str, limit: int = 8, categories: list[str] | None = None) -> list[dict]:
        return self._manager.query_local_memory(
            workspace,
            query_text=query_text,
            limit=limit,
            include_details=False,
            categories=categories or [],
        )
