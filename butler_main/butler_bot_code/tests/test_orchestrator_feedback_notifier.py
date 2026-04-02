from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.butler_bot_code.tests._tmpdir import test_workdir  # noqa: E402
from butler_main.domains.campaign.models import CampaignInstance  # noqa: E402
from butler_main.domains.campaign.store import FileCampaignStore  # noqa: E402
from butler_main.orchestrator.event_store import FileLedgerEventStore  # noqa: E402
from butler_main.orchestrator.feedback_notifier import OrchestratorFeedbackNotifier  # noqa: E402
from butler_main.orchestrator.mission_store import FileMissionStore  # noqa: E402
from butler_main.orchestrator.models import LedgerEvent, Mission  # noqa: E402
from butler_main.orchestrator.workspace import resolve_orchestrator_root  # noqa: E402


class _FakeResponse:
    def __init__(self, payload) -> None:
        self._payload = payload
        self.status_code = 200
        self.headers = {}
        self.content = b""

    def json(self):
        return self._payload


class _FakeRequests:
    def __init__(self) -> None:
        self.posts: list[dict] = []
        self.gets: list[dict] = []
        self.requests: list[dict] = []

    def post(self, url, json=None, data=None, files=None, headers=None, timeout=None):
        self.posts.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if "tenant_access_token/internal" in url:
            return _FakeResponse({"code": 0, "tenant_access_token": "tok_feedback", "expire": 7200})
        if url.endswith("/open-apis/docx/v1/documents"):
            return _FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "document": {
                            "document_id": "doxc_feedback",
                            "title": (json or {}).get("title") or "Task Doc",
                        }
                    },
                }
            )
        if url.endswith("/open-apis/docx/v1/documents/blocks/convert"):
            return _FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "blocks": [
                            {
                                "block_type": 3,
                                "heading1": {
                                    "elements": [
                                        {"text_run": {"content": "Task"}}
                                    ]
                                },
                            }
                        ]
                    },
                }
            )
        if "/children" in url:
            return _FakeResponse({"code": 0, "data": {"children": []}})
        if "/open-apis/im/v1/messages" in url:
            return _FakeResponse({"code": 0, "data": {"message_id": "om_feedback"}})
        return _FakeResponse({"code": 0})

    def get(self, url, headers=None, params=None, timeout=None):
        self.gets.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
        if "/children" in url:
            return _FakeResponse({"code": 0, "data": {"items": [], "has_more": False, "page_token": ""}})
        return _FakeResponse({"code": 0, "data": {}})

    def request(self, method, url, headers=None, json=None, timeout=None):
        self.requests.append(
            {"method": method, "url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return _FakeResponse({"code": 0})


class OrchestratorFeedbackNotifierTests(unittest.TestCase):
    def test_notifier_creates_task_doc_updates_stores_and_pushes_message(self) -> None:
        with test_workdir("orchestrator_feedback_notifier") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            orchestrator_root = Path(resolve_orchestrator_root(str(root)))
            campaign_store = FileCampaignStore(orchestrator_root)
            mission_store = FileMissionStore(orchestrator_root)

            mission = Mission(
                mission_type="campaign",
                title="feedback mission",
                status="ready",
                metadata={
                    "campaign_id": "campaign_feedback",
                    "feedback_contract": {
                        "platform": "feishu",
                        "target": "ou_feedback",
                        "target_type": "open_id",
                        "doc_enabled": True,
                    },
                },
            )
            mission_store.save(mission)
            campaign_store.save_instance(
                CampaignInstance(
                    campaign_id="campaign_feedback",
                    campaign_title="Feedback Campaign",
                    top_level_goal="Ship feedback doc integration",
                    mission_id=mission.mission_id,
                    supervisor_session_id="workflow_session_feedback",
                    status="active",
                    current_phase="discover",
                    next_phase="implement",
                    metadata={
                        "bundle_root": str(root / "工作区" / "Butler" / "deliveries" / "background_tasks" / "feedback"),
                        "bundle_manifest": str(root / "工作区" / "Butler" / "deliveries" / "background_tasks" / "feedback" / "manifest.json"),
                        "campaign_runtime": {"mode": "codex"},
                        "pending_correctness_checks": ["clarify_scope"],
                        "latest_acceptance_decision": "continue",
                        "not_done_reason": "clarify_scope",
                    },
                )
            )

            fake_requests = _FakeRequests()
            notifier = OrchestratorFeedbackNotifier(
                workspace=str(root),
                config_snapshot={"app_id": "cli_feedback", "app_secret": "sec_feedback"},
                requests_module=fake_requests,
            )

            result = notifier.ensure_feedback_surface_for_campaign(
                campaign_id="campaign_feedback",
                mission_id=mission.mission_id,
                feedback_contract=mission.metadata.get("feedback_contract"),
                startup_mode="confirmed",
                send_startup_push=True,
            )

            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result["document_id"], "doxc_feedback")
            self.assertEqual(result["push_count"], 1)

            reloaded_campaign = campaign_store.get_instance("campaign_feedback")
            assert reloaded_campaign is not None
            self.assertEqual(reloaded_campaign.metadata["feedback_doc"]["document_id"], "doxc_feedback")

            reloaded_mission = mission_store.get(mission.mission_id)
            assert reloaded_mission is not None
            self.assertEqual(reloaded_mission.metadata["feedback_doc"]["url"], "https://feishu.cn/docx/doxc_feedback")

            self.assertTrue(any(url["url"].endswith("/open-apis/docx/v1/documents") for url in fake_requests.posts))
            self.assertTrue(any("/open-apis/docx/v1/documents/blocks/convert" in url["url"] for url in fake_requests.posts))
            self.assertTrue(any("/open-apis/im/v1/messages" in url["url"] for url in fake_requests.posts))
            self.assertTrue(
                any(
                    "bundle_root: " in str((url["json"] or {}).get("content") or "")
                    for url in fake_requests.posts
                    if "/open-apis/im/v1/messages" in url["url"]
                )
            )
            self.assertTrue(
                any(
                    "execution_state: " in str((url["json"] or {}).get("content") or "")
                    and "closure_state: " in str((url["json"] or {}).get("content") or "")
                    for url in fake_requests.posts
                    if "/open-apis/im/v1/messages" in url["url"]
                )
            )
            self.assertTrue((orchestrator_root / "feedback_notifier_state.json").exists())

    def test_push_only_feedback_surface_preserves_pushes_without_doc(self) -> None:
        with test_workdir("orchestrator_feedback_push_only") as root:
            (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
            (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)

            orchestrator_root = Path(resolve_orchestrator_root(str(root)))
            campaign_store = FileCampaignStore(orchestrator_root)
            mission_store = FileMissionStore(orchestrator_root)
            event_store = FileLedgerEventStore(orchestrator_root)

            mission = Mission(
                mission_type="campaign",
                title="push only mission",
                status="running",
                metadata={
                    "campaign_id": "campaign_push_only",
                    "feedback_contract": {
                        "platform": "feishu",
                        "target": "ou_push_only",
                        "target_type": "open_id",
                        "doc_enabled": False,
                    },
                },
            )
            mission_store.save(mission)
            campaign_store.save_instance(
                CampaignInstance(
                    campaign_id="campaign_push_only",
                    campaign_title="Push Only Campaign",
                    top_level_goal="Ship push-only feedback",
                    mission_id=mission.mission_id,
                    supervisor_session_id="workflow_session_push_only",
                    status="active",
                    current_phase="implement",
                    next_phase="evaluate",
                )
            )
            event_store.append(
                LedgerEvent(
                    mission_id=mission.mission_id,
                    event_type="branch_completed",
                    payload={"summary": "done"},
                )
            )

            fake_requests = _FakeRequests()
            notifier = OrchestratorFeedbackNotifier(
                workspace=str(root),
                config_snapshot={"app_id": "cli_feedback", "app_secret": "sec_feedback"},
                requests_module=fake_requests,
            )

            surface = notifier.ensure_feedback_surface_for_campaign(
                campaign_id="campaign_push_only",
                mission_id=mission.mission_id,
                feedback_contract=mission.metadata.get("feedback_contract"),
                startup_mode="exploratory",
                send_startup_push=True,
            )
            self.assertEqual(str((surface or {}).get("document_id") or ""), "")
            self.assertGreaterEqual(int((surface or {}).get("push_count") or 0), 1)
            self.assertFalse(any(url["url"].endswith("/open-apis/docx/v1/documents") for url in fake_requests.posts))
            self.assertTrue(any("/open-apis/im/v1/messages" in url["url"] for url in fake_requests.posts))

            event_store.append(
                LedgerEvent(
                    mission_id=mission.mission_id,
                    event_type="judge_verdict",
                    payload={"decision": "continue"},
                )
            )

            class _FakeService:
                def list_missions(self_nonlocal):
                    return [mission_store.get(mission.mission_id)]

            summary = notifier.run_cycle(service=_FakeService())
            self.assertEqual(summary["campaign_count"], 1)
            self.assertEqual(summary["doc_sync_count"], 0)
            self.assertGreaterEqual(summary["push_count"], 1)


if __name__ == "__main__":
    unittest.main()
