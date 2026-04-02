from __future__ import annotations

import json
from pathlib import Path

from .models import Mission


class FileMissionStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def missions_dir(self) -> Path:
        path = self.root / "missions"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def mission_path(self, mission_id: str) -> Path:
        target = str(mission_id or "").strip()
        if not target:
            raise ValueError("mission_id is required")
        return self.missions_dir / f"{target}.json"

    def save(self, mission: Mission) -> Mission:
        path = self.mission_path(mission.mission_id)
        path.write_text(json.dumps(mission.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return mission

    def get(self, mission_id: str) -> Mission | None:
        path = self.mission_path(mission_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return Mission.from_dict(payload)

    def list_missions(self) -> list[Mission]:
        missions: list[Mission] = []
        for path in sorted(self.missions_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            missions.append(Mission.from_dict(payload))
        return missions
