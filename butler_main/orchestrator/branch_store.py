from __future__ import annotations

import json
from pathlib import Path

from .models import Branch


class FileBranchStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def branches_dir(self) -> Path:
        path = self.root / "branches"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def branch_path(self, branch_id: str) -> Path:
        target = str(branch_id or "").strip()
        if not target:
            raise ValueError("branch_id is required")
        return self.branches_dir / f"{target}.json"

    def save(self, branch: Branch) -> Branch:
        path = self.branch_path(branch.branch_id)
        path.write_text(json.dumps(branch.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return branch

    def get(self, branch_id: str) -> Branch | None:
        path = self.branch_path(branch_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return Branch.from_dict(payload)

    def list_branches(self, *, mission_id: str = "", node_id: str = "") -> list[Branch]:
        target_mission_id = str(mission_id or "").strip()
        target_node_id = str(node_id or "").strip()
        branches: list[Branch] = []
        for path in sorted(self.branches_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            branch = Branch.from_dict(payload)
            if target_mission_id and branch.mission_id != target_mission_id:
                continue
            if target_node_id and branch.node_id != target_node_id:
                continue
            branches.append(branch)
        return branches
