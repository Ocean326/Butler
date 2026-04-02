from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .models import CampaignArtifactSummary, CampaignEvent, CampaignInstance, CampaignTurnReceipt


class FileCampaignStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def campaigns_dir(self) -> Path:
        path = self.root / "campaigns"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def campaign_root(self, campaign_id: str) -> Path:
        target = str(campaign_id or "").strip()
        if not target:
            raise ValueError("campaign_id is required")
        path = self.campaigns_dir / target
        path.mkdir(parents=True, exist_ok=True)
        return path

    def instance_path(self, campaign_id: str) -> Path:
        return self.campaign_root(campaign_id) / "instance.json"

    def artifact_index_path(self, campaign_id: str) -> Path:
        return self.campaign_root(campaign_id) / "artifact_index.json"

    def event_log_path(self, campaign_id: str) -> Path:
        return self.campaign_root(campaign_id) / "events.jsonl"

    def artifact_payload_dir(self, campaign_id: str) -> Path:
        path = self.campaign_root(campaign_id) / "artifacts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def turn_log_path(self, campaign_id: str) -> Path:
        return self.campaign_root(campaign_id) / "turns.jsonl"

    def save_instance(self, instance: CampaignInstance) -> CampaignInstance:
        path = self.instance_path(instance.campaign_id)
        path.write_text(json.dumps(instance.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return instance

    def get_instance(self, campaign_id: str) -> CampaignInstance | None:
        path = self.instance_path(campaign_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CampaignInstance.from_dict(payload)

    def list_instances(self) -> list[CampaignInstance]:
        items: list[CampaignInstance] = []
        for path in sorted(self.campaigns_dir.glob("*/instance.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            items.append(CampaignInstance.from_dict(payload))
        return items

    def save_artifact_index(self, campaign_id: str, artifacts: list[CampaignArtifactSummary]) -> list[CampaignArtifactSummary]:
        path = self.artifact_index_path(campaign_id)
        payload = [item.to_dict() for item in artifacts]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return artifacts

    def load_artifact_index(self, campaign_id: str) -> list[CampaignArtifactSummary]:
        path = self.artifact_index_path(campaign_id)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        return [CampaignArtifactSummary.from_dict(item) for item in payload if isinstance(item, Mapping)]

    def write_artifact_payload(
        self,
        campaign_id: str,
        artifact: CampaignArtifactSummary,
        payload: Mapping[str, Any] | None,
    ) -> Path:
        filename = f"{artifact.iteration:02d}_{artifact.phase}_{artifact.kind}_{artifact.artifact_id}.json"
        path = self.artifact_payload_dir(campaign_id) / filename
        path.write_text(json.dumps(dict(payload or {}), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def read_artifact_payload(self, campaign_id: str, ref: str) -> dict[str, Any]:
        target = str(ref or "").strip()
        if not target:
            return {}
        path = Path(target)
        if not path.is_absolute():
            path = self.campaign_root(campaign_id) / target
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    def append_event(self, event: CampaignEvent) -> CampaignEvent:
        path = self.event_log_path(event.campaign_id)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False))
            handle.write("\n")
        return event

    def append_turn_receipt(self, receipt: CampaignTurnReceipt) -> CampaignTurnReceipt:
        path = self.turn_log_path(receipt.campaign_id)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt.to_dict(), ensure_ascii=False))
            handle.write("\n")
        return receipt

    def list_turn_receipts(self, campaign_id: str, *, limit: int = 0) -> list[CampaignTurnReceipt]:
        path = self.turn_log_path(campaign_id)
        if not path.exists():
            return []
        items: list[CampaignTurnReceipt] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except Exception:
                    continue
                if not isinstance(payload, Mapping):
                    continue
                items.append(CampaignTurnReceipt.from_dict(payload))
        if int(limit or 0) > 0:
            return items[-int(limit) :]
        return items

    def list_events(self, campaign_id: str, *, event_type: str = "") -> list[CampaignEvent]:
        path = self.event_log_path(campaign_id)
        if not path.exists():
            return []
        items: list[CampaignEvent] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except Exception:
                    continue
                if not isinstance(payload, Mapping):
                    continue
                item = CampaignEvent.from_dict(payload)
                if event_type and item.event_type != str(event_type).strip():
                    continue
                items.append(item)
        return items

    def ensure_single_active_campaign(self, *, exclude_campaign_id: str = "") -> None:
        excluded = str(exclude_campaign_id or "").strip()
        for instance in self.list_instances():
            if excluded and instance.campaign_id == excluded:
                continue
            if instance.status in {"active", "running", "waiting"}:
                raise ValueError(f"active campaign already exists: {instance.campaign_id}")
