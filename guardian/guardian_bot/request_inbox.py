from __future__ import annotations

import json
from pathlib import Path

from guardian_bot.request_models import GuardianRequest


class GuardianRequestInbox:
    def __init__(self, inbox_dir: Path) -> None:
        self.inbox_dir = inbox_dir

    def list_pending_files(self) -> list[Path]:
        if not self.inbox_dir.exists():
            return []
        return sorted(self.inbox_dir.glob("*.json"))

    def load_request(self, path: Path) -> GuardianRequest:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return GuardianRequest.from_dict(payload if isinstance(payload, dict) else {})

    def persist_reviewed_request(self, path: Path, request: GuardianRequest, decision: str) -> Path:
        target_dir = self.inbox_dir / decision
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / path.name
        target_path.write_text(json.dumps(request.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        path.unlink(missing_ok=True)
        return target_path
