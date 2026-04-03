from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

try:
    import requests
except ImportError:  # pragma: no cover - runtime dependency
    requests = None  # type: ignore[assignment]

from butler_main.chat.feishu_bot.api import FeishuApiClient
from butler_main.domains.campaign.status_semantics import build_campaign_semantics
from butler_main.domains.campaign.store import FileCampaignStore

from .event_store import FileLedgerEventStore
from .mission_store import FileMissionStore
from .paths import resolve_butler_root
from .workspace import resolve_orchestrator_root


_HIGH_SIGNAL_MISSION_EVENT_TYPES = {
    "mission_created",
    "workflow_session_created",
    "workflow_session_resumed",
    "branch_dispatched",
    "approval_requested",
    "approval_resolved",
    "judge_verdict",
    "recovery_scheduled",
    "branch_completed",
    "workflow_vm_executed",
}
_HIGH_SIGNAL_CAMPAIGN_EVENT_TYPES = {
    "campaign_created",
    "campaign_turn_committed",
    "campaign_paused",
    "implement_completed",
    "evaluate_completed",
    "working_contract_rewritten",
    "campaign_converged",
    "campaign_stopped",
}


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _mapping_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict") and callable(value.to_dict):
        payload = value.to_dict()
        if isinstance(payload, Mapping):
            return dict(payload)
    return {}


def _read_json_dict(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _write_json_dict(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _stable_hash(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


class FeishuTaskDocService:
    def __init__(
        self,
        *,
        config_getter,
        requests_module=None,
        api_client: FeishuApiClient | None = None,
    ) -> None:
        self._config_getter = config_getter
        self._requests = requests_module if requests_module is not None else requests
        self._api_client = api_client or FeishuApiClient(
            config_getter=config_getter,
            requests_module=self._requests,
        )

    def enabled(self) -> bool:
        if self._requests is None:
            return False
        missing = self._api_client.validate_runtime_config(self._config_getter() or {})
        return not missing

    def create_task_doc(self, *, title: str) -> dict[str, Any] | None:
        if not self.enabled():
            return None
        config = dict(self._config_getter() or {})
        folder_token = str(config.get("task_doc_folder_token") or config.get("task_doc_token") or "").strip()
        ok, data = self._api_client.create_docx_document(title, folder_token=folder_token)
        if not ok:
            return None
        document = _mapping_payload((_mapping_payload(data.get("data"))).get("document"))
        document_id = str(document.get("document_id") or "").strip()
        if not document_id:
            return None
        return {
            "document_id": document_id,
            "url": f"https://feishu.cn/docx/{document_id}",
            "title": str(document.get("title") or title).strip() or str(title or "").strip() or "Task Doc",
            "created_at": _utc_now_iso(),
        }

    def rewrite_task_doc(self, document_id: str, markdown: str) -> bool:
        if not self.enabled():
            return False
        target_document_id = str(document_id or "").strip()
        if not target_document_id:
            return False
        child_count = self._count_root_children(target_document_id)
        if child_count > 0:
            ok, _ = self._api_client.batch_delete_docx_block_children(
                target_document_id,
                start_index=0,
                end_index=child_count,
            )
            if not ok:
                return False
        content = str(markdown or "").strip()
        if not content:
            return True
        ok, converted = self._api_client.convert_docx_markdown(content)
        if not ok:
            return False
        blocks = list((_mapping_payload(converted.get("data"))).get("blocks") or [])
        if not blocks:
            return True
        ok, _ = self._api_client.create_docx_block_children(target_document_id, blocks)
        return bool(ok)

    def _count_root_children(self, document_id: str) -> int:
        total = 0
        page_token = ""
        while True:
            ok, data = self._api_client.get_docx_block_children(document_id, page_token=page_token)
            if not ok:
                return total
            body = _mapping_payload(data.get("data"))
            total += len(body.get("items") or [])
            if not bool(body.get("has_more")):
                return total
            page_token = str(body.get("page_token") or "").strip()
            if not page_token:
                return total


class OrchestratorFeedbackNotifier:
    def __init__(
        self,
        *,
        workspace: str,
        config_snapshot: Mapping[str, Any] | None = None,
        requests_module=None,
    ) -> None:
        self._workspace = str(workspace or "").strip() or "."
        self._config_snapshot = dict(config_snapshot or {})
        self._root = Path(resolve_orchestrator_root(self._workspace))
        self._campaign_store = FileCampaignStore(self._root)
        self._mission_store = FileMissionStore(self._root)
        self._event_store = FileLedgerEventStore(self._root)
        self._state_path = self._root / "feedback_notifier_state.json"
        self._doc_service = FeishuTaskDocService(
            config_getter=self._get_runtime_config,
            requests_module=requests_module,
        )
        self._api_client = FeishuApiClient(
            config_getter=self._get_runtime_config,
            requests_module=requests_module if requests_module is not None else requests,
        )

    def run_cycle(self, *, service) -> dict[str, Any]:
        summary = {
            "campaign_count": 0,
            "doc_sync_count": 0,
            "push_count": 0,
            "error_count": 0,
        }
        for campaign in self._campaign_store.list_instances():
            campaign_payload = campaign.to_dict()
            feedback_contract = self._feedback_contract_for_campaign(campaign_payload)
            if str(feedback_contract.get("platform") or "").strip().lower() != "feishu":
                continue
            campaign_id = str(campaign_payload.get("campaign_id") or "").strip()
            if not campaign_id:
                continue
            summary["campaign_count"] += 1
            try:
                sync_result = self.ensure_feedback_surface_for_campaign(
                    campaign_id=campaign_id,
                    mission_id=str(campaign_payload.get("mission_id") or "").strip(),
                    feedback_contract=feedback_contract,
                    service=service,
                    send_startup_push=False,
                )
                if sync_result:
                    if str(sync_result.get("document_id") or "").strip():
                        summary["doc_sync_count"] += 1
                    summary["push_count"] += int(sync_result.get("push_count") or 0)
            except Exception:
                summary["error_count"] += 1
        return summary

    def _feedback_contract_for_campaign(self, campaign_payload: Mapping[str, Any]) -> dict[str, Any]:
        metadata = _mapping_payload(campaign_payload.get("metadata"))
        contract = _mapping_payload(metadata.get("feedback_contract"))
        if contract:
            return contract
        mission_id = str(campaign_payload.get("mission_id") or "").strip()
        if mission_id:
            mission = self._mission_store.get(mission_id)
            contract = _mapping_payload(_mapping_payload(getattr(mission, "metadata", {})).get("feedback_contract"))
            if contract:
                return contract
        campaign_id = str(campaign_payload.get("campaign_id") or "").strip()
        if not campaign_id:
            return {}
        for mission in self._mission_store.list_missions():
            mission_metadata = _mapping_payload(getattr(mission, "metadata", {}))
            if str(mission_metadata.get("campaign_id") or "").strip() != campaign_id:
                continue
            contract = _mapping_payload(mission_metadata.get("feedback_contract"))
            if contract:
                return contract
        return {}

    def ensure_feedback_surface_for_campaign(
        self,
        *,
        campaign_id: str,
        feedback_contract: Mapping[str, Any] | None,
        mission_id: str = "",
        startup_mode: str = "",
        service=None,
        send_startup_push: bool = False,
    ) -> dict[str, Any] | None:
        contract = _mapping_payload(feedback_contract)
        if str(contract.get("platform") or "").strip().lower() != "feishu":
            return None
        campaign = self._campaign_store.get_instance(str(campaign_id or "").strip())
        mission = self._mission_store.get(str(mission_id or "").strip()) if str(mission_id or "").strip() else None
        if campaign is None:
            return None

        state = self._load_state()
        campaign_state = dict((state.get("campaigns") or {}).get(campaign.campaign_id) or {})
        feedback_doc = _mapping_payload(campaign.metadata.get("feedback_doc"))
        if not feedback_doc and mission is not None:
            feedback_doc = _mapping_payload(mission.metadata.get("feedback_doc"))
        if not feedback_doc:
            feedback_doc = _mapping_payload(campaign_state.get("feedback_doc"))

        snapshot = self._build_campaign_snapshot(
            campaign_id=campaign.campaign_id,
            mission_id=str(getattr(mission, "mission_id", "") or "").strip(),
            service=service,
        )
        markdown = self._render_campaign_markdown(snapshot=snapshot, startup_mode=startup_mode)
        markdown_hash = _stable_hash(markdown)
        push_count = 0

        if not feedback_doc and bool(contract.get("doc_enabled", True)):
            feedback_doc = self._doc_service.create_task_doc(title=self._task_doc_title(snapshot))
            if feedback_doc and self._doc_service.rewrite_task_doc(str(feedback_doc.get("document_id") or "").strip(), markdown):
                campaign_state["last_doc_hash"] = markdown_hash
                campaign_state["last_doc_synced_at"] = _utc_now_iso()
                self._patch_feedback_doc(
                    campaign_id=campaign.campaign_id,
                    mission_id=str(getattr(mission, "mission_id", "") or "").strip(),
                    feedback_doc=feedback_doc,
                )
                if send_startup_push:
                    push_count += int(
                        self._send_push_message(
                            contract=contract,
                            text=self._startup_push_text(snapshot=snapshot, feedback_doc=feedback_doc),
                        )
                    )
            elif feedback_doc:
                self._patch_feedback_doc(
                    campaign_id=campaign.campaign_id,
                    mission_id=str(getattr(mission, "mission_id", "") or "").strip(),
                    feedback_doc=feedback_doc,
                )

        if feedback_doc:
            document_id = str(feedback_doc.get("document_id") or "").strip()
            if document_id and str(campaign_state.get("last_doc_hash") or "").strip() != markdown_hash:
                if self._doc_service.rewrite_task_doc(document_id, markdown):
                    campaign_state["last_doc_hash"] = markdown_hash
                    campaign_state["last_doc_synced_at"] = _utc_now_iso()

        push_events = self._collect_new_push_events(
            snapshot=snapshot,
            campaign_state=campaign_state,
        )
        for event in push_events:
            delivered = self._send_push_message(
                contract=contract,
                text=self._event_push_text(event=event, snapshot=snapshot, feedback_doc=feedback_doc),
            )
            if delivered:
                push_count += 1
                delivered_keys = list(campaign_state.get("delivered_event_keys") or [])
                delivered_keys.append(str(event.get("key") or ""))
                campaign_state["delivered_event_keys"] = delivered_keys[-200:]

        current_status = str(snapshot.get("status") or "").strip()
        previous_status = str(campaign_state.get("last_status") or "").strip()
        if feedback_doc and current_status and current_status != previous_status:
            campaign_state["last_status"] = current_status

        campaign_state["feedback_doc"] = feedback_doc
        campaigns = dict(state.get("campaigns") or {})
        campaigns[campaign.campaign_id] = campaign_state
        state["campaigns"] = campaigns
        _write_json_dict(self._state_path, state)

        if feedback_doc:
            return {**feedback_doc, "push_count": push_count}
        if push_count > 0:
            return {"push_count": push_count}
        return None

    def _get_runtime_config(self) -> dict[str, Any]:
        if self._config_snapshot.get("app_id") and self._config_snapshot.get("app_secret"):
            return dict(self._config_snapshot)
        config_path = str(
            self._config_snapshot.get("__config_path")
            or self._config_snapshot.get("config_path")
            or self._default_config_path()
        ).strip()
        if not config_path:
            return dict(self._config_snapshot)
        path = Path(config_path)
        if not path.exists():
            return dict(self._config_snapshot)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return dict(self._config_snapshot)
        if not isinstance(payload, Mapping):
            return dict(self._config_snapshot)
        return {**dict(payload), **dict(self._config_snapshot)}

    def _default_config_path(self) -> str:
        return str(resolve_butler_root(self._workspace) / "butler_main" / "butler_bot_code" / "configs" / "butler_bot.json")

    def _load_state(self) -> dict[str, Any]:
        if not self._state_path.exists():
            return {"campaigns": {}}
        payload = _read_json_dict(self._state_path)
        if "campaigns" not in payload or not isinstance(payload.get("campaigns"), Mapping):
            payload["campaigns"] = {}
        return payload

    def _patch_feedback_doc(self, *, campaign_id: str, mission_id: str = "", feedback_doc: Mapping[str, Any]) -> None:
        campaign = self._campaign_store.get_instance(campaign_id)
        if campaign is not None:
            campaign.metadata = dict(campaign.metadata or {})
            campaign.metadata["feedback_doc"] = dict(feedback_doc or {})
            campaign.touch()
            self._campaign_store.save_instance(campaign)
        mission = self._mission_store.get(mission_id) if str(mission_id or "").strip() else None
        if mission is not None:
            mission.metadata = dict(mission.metadata or {})
            mission.metadata["feedback_doc"] = dict(feedback_doc or {})
            mission.updated_at = _utc_now_iso()
            self._mission_store.save(mission)

    def _build_campaign_snapshot(self, *, campaign_id: str, mission_id: str = "", service=None) -> dict[str, Any]:
        campaign = self._campaign_store.get_instance(campaign_id)
        mission = self._mission_store.get(mission_id) if str(mission_id or "").strip() else None
        if campaign is None:
            return {}
        artifacts = [
            _mapping_payload(item)
            for item in self._campaign_store.load_artifact_index(campaign_id)
        ]
        campaign_events = [
            _mapping_payload(item)
            for item in self._campaign_store.list_events(campaign_id)
        ]
        mission_events = [
            _mapping_payload(item)
            for item in self._event_store.list_events(mission_id=mission_id)
        ] if mission is not None else []
        mission_summary = _mapping_payload(mission)
        workflow_session = {}
        if service is not None and str(campaign.supervisor_session_id or "").strip():
            try:
                workflow_session = _mapping_payload(service.summarize_workflow_session(campaign.supervisor_session_id))
            except Exception:
                workflow_session = {}
        return {
            **campaign.to_dict(),
            "artifacts": artifacts,
            "campaign_events": campaign_events,
            "mission": mission_summary,
            "workflow_session": workflow_session,
            "mission_events": mission_events,
        }

    def _task_doc_title(self, snapshot: Mapping[str, Any]) -> str:
        title = str(snapshot.get("campaign_title") or snapshot.get("top_level_goal") or "Campaign Task").strip()
        return f"Task - {title[:80]}"

    def _render_campaign_markdown(self, *, snapshot: Mapping[str, Any], startup_mode: str = "") -> str:
        metadata = _mapping_payload(snapshot.get("metadata"))
        task_summary = _mapping_payload(snapshot.get("task_summary")) or _mapping_payload(metadata.get("task_summary"))
        turn_receipt = _mapping_payload(metadata.get("latest_turn_receipt"))
        semantics = self._snapshot_semantics(snapshot)
        runtime_payload = _mapping_payload(metadata.get("campaign_runtime"))
        pending_checks = list(semantics.get("pending_checks") or [])
        resolved_checks = list(semantics.get("resolved_checks") or [])
        waived_checks = list(semantics.get("waived_checks") or [])
        operational_checks = list(semantics.get("operational_checks_pending") or [])
        closure_checks = list(semantics.get("closure_checks_pending") or [])
        not_done_reason = str(semantics.get("not_done_reason") or "").strip()
        closure_reason = str(semantics.get("closure_reason") or "").strip()
        progress_reason = str(semantics.get("progress_reason") or "").strip()
        latest_acceptance_decision = str(semantics.get("latest_acceptance_decision") or "").strip()
        lines: list[str] = []
        title = str(snapshot.get("campaign_title") or snapshot.get("top_level_goal") or "Campaign Task").strip() or "Campaign Task"
        lines.append(f"# {title}")
        lines.append("")
        lines.append("## Status")
        lines.append(f"- campaign_id: {str(snapshot.get('campaign_id') or '').strip()}")
        lines.append(f"- canonical_session_id: {self._canonical_session_id(snapshot) or '-'}")
        lines.append(f"- mission_id: {str(snapshot.get('mission_id') or '').strip()}")
        lines.append(f"- status: {str(snapshot.get('status') or '').strip() or '-'}")
        lines.append(f"- current_phase: {str(snapshot.get('current_phase') or '').strip() or '-'}")
        lines.append(f"- next_phase: {str(snapshot.get('next_phase') or '').strip() or '-'}")
        lines.append(f"- current_iteration: {int(snapshot.get('current_iteration') or 0)}")
        lines.append(f"- runtime_mode: {str(runtime_payload.get('mode') or '').strip() or '-'}")
        lines.append(f"- execution_state: {str(semantics.get('execution_state') or '').strip() or '-'}")
        lines.append(f"- closure_state: {str(semantics.get('closure_state') or '').strip() or '-'}")
        if startup_mode:
            lines.append(f"- startup_mode: {startup_mode}")
        lines.append(f"- updated_at: {str(snapshot.get('updated_at') or '').strip() or _utc_now_iso()}")
        if progress_reason:
            lines.append(f"- progress_reason: {progress_reason}")
        if closure_reason:
            lines.append(f"- closure_reason: {closure_reason}")
        next_action = str(task_summary.get("next_action") or semantics.get("operator_next_action") or "").strip()
        if next_action:
            lines.append(f"- next_action: {next_action}")
        bundle_root = str(metadata.get("bundle_root") or "").strip()
        bundle_manifest = str(metadata.get("bundle_manifest") or "").strip()
        if bundle_root or bundle_manifest:
            lines.append("")
            lines.append("## Output")
            if bundle_root:
                lines.append(f"- bundle_root: {bundle_root}")
            if bundle_manifest:
                lines.append(f"- bundle_manifest: {bundle_manifest}")
            stage_artifact_refs = list(semantics.get("stage_artifact_refs") or [])
            if stage_artifact_refs:
                lines.append(f"- stage_artifact_refs: {', '.join(stage_artifact_refs[:6])}")
        goal = str(snapshot.get("top_level_goal") or "").strip()
        if goal:
            lines.append("")
            lines.append("## Goal")
            lines.append(goal)
        materials = [str(item).strip() for item in snapshot.get("materials") or [] if str(item).strip()]
        if materials:
            lines.append("")
            lines.append("## Materials")
            lines.extend([f"- {item}" for item in materials[:20]])
        constraints = [str(item).strip() for item in snapshot.get("hard_constraints") or [] if str(item).strip()]
        if constraints:
            lines.append("")
            lines.append("## Constraints")
            lines.extend([f"- {item}" for item in constraints[:20]])
        latest_summary = str(
            _mapping_payload(task_summary.get("progress")).get("latest_summary")
            or metadata.get("latest_summary")
            or turn_receipt.get("summary")
            or ""
        ).strip()
        if latest_summary:
            lines.append("")
            lines.append("## Latest Summary")
            lines.append(latest_summary)
        if pending_checks or resolved_checks or waived_checks or latest_acceptance_decision or not_done_reason:
            lines.append("")
            lines.append("## Acceptance")
            lines.append(f"- latest_acceptance_decision: {latest_acceptance_decision or '-'}")
            lines.append(f"- pending_checks: {', '.join(pending_checks) if pending_checks else 'none'}")
            lines.append(f"- operational_checks_pending: {', '.join(operational_checks) if operational_checks else 'none'}")
            lines.append(f"- closure_checks_pending: {', '.join(closure_checks) if closure_checks else 'none'}")
            lines.append(f"- resolved_checks: {', '.join(resolved_checks) if resolved_checks else 'none'}")
            lines.append(f"- waived_checks: {', '.join(waived_checks) if waived_checks else 'none'}")
            if not_done_reason:
                lines.append(f"- not_done_reason: {not_done_reason}")
        lines.append("")
        lines.append("## Recent Events")
        events = self._recent_signal_events(snapshot, limit=12)
        if events:
            for event in events:
                lines.append(
                    f"- [{str(event.get('created_at') or '').strip() or '-'}] "
                    f"{str(event.get('event_type') or '').strip() or 'event'}"
                )
        else:
            lines.append("- no high-signal events yet")
        artifacts = list(snapshot.get("artifacts") or [])
        if artifacts:
            lines.append("")
            lines.append("## Artifacts")
            for artifact in artifacts[-8:]:
                lines.append(
                    f"- [{str(artifact.get('phase') or '').strip() or '-'}] "
                    f"{str(artifact.get('label') or artifact.get('kind') or artifact.get('artifact_id') or '').strip()}"
                )
        latest_verdict = {}
        verdict_history = list(snapshot.get("verdict_history") or [])
        if verdict_history:
            latest_verdict = _mapping_payload(verdict_history[-1])
        if latest_verdict:
            lines.append("")
            lines.append("## Latest Verdict")
            lines.append(f"- decision: {str(latest_verdict.get('decision') or '').strip() or '-'}")
            lines.append(f"- reviewer_role_id: {str(latest_verdict.get('reviewer_role_id') or '').strip() or '-'}")
            summary = str(latest_verdict.get("summary") or "").strip()
            if summary:
                lines.append(f"- summary: {summary}")
        return "\n".join(lines).strip()

    def _recent_signal_events(self, snapshot: Mapping[str, Any], *, limit: int) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for raw in snapshot.get("mission_events") or []:
            event = _mapping_payload(raw)
            if str(event.get("event_type") or "").strip() in _HIGH_SIGNAL_MISSION_EVENT_TYPES:
                event["source"] = "mission"
                events.append(event)
        for raw in snapshot.get("campaign_events") or []:
            event = _mapping_payload(raw)
            if str(event.get("event_type") or "").strip() in _HIGH_SIGNAL_CAMPAIGN_EVENT_TYPES:
                event["source"] = "campaign"
                events.append(event)
        events.sort(key=lambda item: (str(item.get("created_at") or ""), str(item.get("event_id") or "")))
        return events[-max(1, int(limit or 1)) :]

    def _collect_new_push_events(
        self,
        *,
        snapshot: Mapping[str, Any],
        campaign_state: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        delivered = {str(item).strip() for item in campaign_state.get("delivered_event_keys") or [] if str(item).strip()}
        new_events: list[dict[str, Any]] = []
        for event in self._recent_signal_events(snapshot, limit=20):
            source = str(event.get("source") or "event").strip()
            event_id = str(event.get("event_id") or "").strip()
            event_type = str(event.get("event_type") or "").strip()
            created_at = str(event.get("created_at") or "").strip()
            key = f"{source}:{event_id or event_type}:{created_at}"
            if key in delivered:
                continue
            event["key"] = key
            new_events.append(event)
        return new_events

    def _startup_push_text(self, *, snapshot: Mapping[str, Any], feedback_doc: Mapping[str, Any]) -> str:
        title = str(snapshot.get("campaign_title") or snapshot.get("top_level_goal") or "Campaign Task").strip() or "Campaign Task"
        doc_url = str(feedback_doc.get("url") or "").strip()
        metadata = _mapping_payload(snapshot.get("metadata"))
        task_summary = _mapping_payload(snapshot.get("task_summary")) or _mapping_payload(metadata.get("task_summary"))
        progress = _mapping_payload(task_summary.get("progress"))
        closure = _mapping_payload(task_summary.get("closure"))
        semantics = self._snapshot_semantics(snapshot)
        lines = [
            f"[Task Started] {title}",
            f"campaign_id: {str(snapshot.get('campaign_id') or '').strip()}",
            f"canonical_session_id: {self._canonical_session_id(snapshot) or '-'}",
            f"status: {str(snapshot.get('status') or '').strip() or 'active'}",
            f"execution_state: {str(semantics.get('execution_state') or '').strip() or '-'}",
            f"closure_state: {str(semantics.get('closure_state') or '').strip() or '-'}",
        ]
        bundle_root = str(metadata.get("bundle_root") or "").strip()
        if bundle_root:
            lines.append(f"bundle_root: {bundle_root}")
        latest_summary = str(progress.get("latest_summary") or metadata.get("latest_summary") or "").strip()
        if latest_summary:
            lines.append(f"latest_summary: {latest_summary}")
        next_action = str(task_summary.get("next_action") or semantics.get("operator_next_action") or "").strip()
        if next_action:
            lines.append(f"next_action: {next_action}")
        latest_verdict = _mapping_payload(closure.get("latest_verdict")) or _mapping_payload(metadata.get("latest_verdict"))
        latest_decision = str(latest_verdict.get("decision") or semantics.get("latest_acceptance_decision") or "").strip()
        if latest_decision:
            lines.append(f"latest_verdict: {latest_decision}")
        if doc_url:
            lines.append(f"task_doc: {doc_url}")
        return "\n".join(lines)

    def _event_push_text(
        self,
        *,
        event: Mapping[str, Any],
        snapshot: Mapping[str, Any],
        feedback_doc: Mapping[str, Any] | None,
    ) -> str:
        title = str(snapshot.get("campaign_title") or snapshot.get("top_level_goal") or "Campaign Task").strip() or "Campaign Task"
        doc_url = str((feedback_doc or {}).get("url") or "").strip()
        metadata = _mapping_payload(snapshot.get("metadata"))
        task_summary = _mapping_payload(snapshot.get("task_summary")) or _mapping_payload(metadata.get("task_summary"))
        progress = _mapping_payload(task_summary.get("progress"))
        semantics = self._snapshot_semantics(snapshot)
        lines = [
            f"[Task Update] {title}",
            f"event: {str(event.get('event_type') or '').strip() or 'event'}",
            f"at: {str(event.get('created_at') or '').strip() or '-'}",
            f"status: {str(snapshot.get('status') or '').strip() or '-'}",
            f"canonical_session_id: {self._canonical_session_id(snapshot) or '-'}",
            f"execution_state: {str(semantics.get('execution_state') or '').strip() or '-'}",
            f"closure_state: {str(semantics.get('closure_state') or '').strip() or '-'}",
        ]
        progress_reason = str(progress.get("latest_summary") or semantics.get("progress_reason") or "").strip()
        not_done_reason = str(semantics.get("not_done_reason") or "").strip()
        if progress_reason:
            lines.append(f"latest_summary: {progress_reason}")
        next_action = str(task_summary.get("next_action") or semantics.get("operator_next_action") or "").strip()
        if next_action:
            lines.append(f"next_action: {next_action}")
        if not_done_reason:
            lines.append(f"not_done_reason: {not_done_reason}")
        if doc_url:
            lines.append(f"task_doc: {doc_url}")
        return "\n".join(lines)

    def _snapshot_semantics(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        metadata = _mapping_payload(snapshot.get("metadata"))
        task_summary = _mapping_payload(snapshot.get("task_summary")) or _mapping_payload(metadata.get("task_summary"))
        if not task_summary:
            return build_campaign_semantics(snapshot)
        progress = _mapping_payload(task_summary.get("progress"))
        closure = _mapping_payload(task_summary.get("closure"))
        output = _mapping_payload(task_summary.get("output"))
        latest_verdict = _mapping_payload(closure.get("latest_verdict")) or _mapping_payload(metadata.get("latest_verdict"))
        latest_delivery_refs = [
            str(item).strip()
            for item in output.get("latest_delivery_refs") or metadata.get("latest_delivery_refs") or []
            if str(item).strip()
        ]
        pending_checks = [
            str(item).strip()
            for item in metadata.get("pending_correctness_checks") or []
            if str(item).strip()
        ]
        resolved_checks = [
            str(item).strip()
            for item in metadata.get("resolved_correctness_checks") or []
            if str(item).strip()
        ]
        waived_checks = [
            str(item).strip()
            for item in metadata.get("waived_correctness_checks") or []
            if str(item).strip()
        ]
        if str(snapshot.get("status") or "").strip().lower() == "completed":
            execution_state = "terminal"
        elif str(snapshot.get("status") or "").strip().lower() in {"paused", "cancelled"}:
            execution_state = "paused"
        elif str(snapshot.get("status") or "").strip().lower() == "draft":
            execution_state = "ready"
        else:
            execution_state = "running"
        return {
            "execution_state": execution_state,
            "closure_state": str(closure.get("state") or "open").strip(),
            "progress_reason": str(progress.get("latest_summary") or metadata.get("latest_summary") or "").strip(),
            "closure_reason": str(closure.get("final_summary") or "").strip(),
            "not_done_reason": str(progress.get("latest_summary") or "").strip() if execution_state != "terminal" else "",
            "pending_checks": pending_checks,
            "resolved_checks": resolved_checks,
            "waived_checks": waived_checks,
            "operational_checks_pending": [],
            "closure_checks_pending": list(pending_checks),
            "latest_stage_summary": str(progress.get("latest_summary") or "").strip(),
            "stage_artifact_refs": latest_delivery_refs,
            "acceptance_requirements_remaining": list(pending_checks),
            "operator_next_action": str(task_summary.get("next_action") or "").strip(),
            "latest_acceptance_decision": str(latest_verdict.get("decision") or "").strip(),
        }

    def _canonical_session_id(self, snapshot: Mapping[str, Any]) -> str:
        metadata = _mapping_payload(snapshot.get("metadata"))
        control_plane_refs = _mapping_payload(metadata.get("control_plane_refs"))
        return str(
            snapshot.get("canonical_session_id")
            or metadata.get("canonical_session_id")
            or control_plane_refs.get("canonical_session_id")
            or snapshot.get("supervisor_session_id")
            or ""
        ).strip()

    def _send_push_message(self, *, contract: Mapping[str, Any], text: str) -> bool:
        target = str(contract.get("target") or "").strip()
        if not target:
            return False
        receive_id_type = str(contract.get("target_type") or "open_id").strip() or "open_id"
        try:
            ok, _ = self._api_client.send_raw_message(target, receive_id_type, "text", {"text": str(text or "").strip()})
        except Exception:
            return False
        return bool(ok)


__all__ = ["FeishuTaskDocService", "OrchestratorFeedbackNotifier"]
