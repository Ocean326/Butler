from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class GuardianLedgerStore:
    def __init__(self, ledger_dir: Path) -> None:
        self.ledger_dir = ledger_dir

    def write_event(self, category: str, event_id: str, payload: dict) -> Path:
        target_dir = self.ledger_dir / category
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{event_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def write_review_event(self, request_id: str, decision: str, notes: list[str], request_payload: dict) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "request_id": request_id,
            "decision": decision,
            "notes": list(notes),
            "request": dict(request_payload or {}),
        }
        return self.write_event("reviews", f"{stamp}_{request_id}", payload)

    def write_execution_event(
        self,
        request_id: str,
        status: str,
        notes: list[str],
        request_payload: dict,
        patch_applied: bool = False,
        tests_passed: bool | None = None,
        rollback_performed: bool = False,
    ) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "request_id": request_id,
            "status": status,
            "notes": list(notes),
            "request": dict(request_payload or {}),
            "patch_applied": patch_applied,
            "tests_passed": tests_passed,
            "rollback_performed": rollback_performed,
        }
        return self.write_event("executions", f"{stamp}_{request_id}", payload)
