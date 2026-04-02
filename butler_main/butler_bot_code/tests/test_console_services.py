from __future__ import annotations

import sys
import unittest
from pathlib import Path


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from butler_main.butler_bot_code.tests._tmpdir import test_workdir
from butler_main.chat.negotiation import CampaignNegotiationDraft, CampaignNegotiationStore
from butler_main.console import ConsoleControlService, ConsoleQueryService, ControlActionRequest
from butler_main.orchestrator.interfaces.query_service import OrchestratorQueryService


class ConsoleServicesTests(unittest.TestCase):
    def _prepare_workspace(self, root: Path) -> None:
        (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
        (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)
        (root / "butler_main" / "sources" / "skills" / "pool" / "ops" / "sample-skill").mkdir(parents=True, exist_ok=True)
        (root / "butler_main" / "sources" / "skills" / "collections").mkdir(parents=True, exist_ok=True)
        (root / "butler_main" / "sources" / "skills" / "pool" / "ops" / "sample-skill" / "SKILL.md").write_text(
            "---\nname: sample-skill\nfamily_id: ops\nfamily_label: Ops\nstatus: active\nrisk_level: low\n---\n# sample-skill\n",
            encoding="utf-8",
        )
        (root / "butler_main" / "sources" / "skills" / "collections" / "registry.json").write_text(
            """{
  "version": 1,
  "collections": {
    "codex_default": {
      "description": "Default Codex skill exposure",
      "owner": "butler",
      "default_injection_mode": "shortlist",
      "skills": [
        "./butler_main/sources/skills/pool/ops/sample-skill"
      ]
    }
  }
}""",
            encoding="utf-8",
        )

    def test_graph_snapshot_is_built_from_campaign_query_payload(self) -> None:
        with test_workdir("console_graph_snapshot") as root:
            self._prepare_workspace(root)
            service = ConsoleQueryService()
            store = CampaignNegotiationStore()
            draft = CampaignNegotiationDraft(
                draft_id="draft_console_graph",
                session_id="thread_console_graph",
                goal="Build console graph",
                materials=["docs/console.md"],
                hard_constraints=["keep Python-first"],
                selected_template_id="campaign.single_repo_delivery",
                frontdoor_mode_id="delivery",
            )
            store.save(workspace=str(root), draft=draft)
            launched = service.launch_draft(str(root), draft.draft_id)

            snapshot = service.build_campaign_graph_snapshot(str(root), launched.linked_campaign_id)

            self.assertEqual(snapshot.campaign_id, launched.linked_campaign_id)
            self.assertEqual(snapshot.graph_level, "campaign")
            self.assertTrue(snapshot.workflow_session_id.startswith("workflow_session_"))
            self.assertEqual(len(snapshot.nodes), 4)
            self.assertEqual({node.id for node in snapshot.nodes}, {"ledger", "turn", "delivery", "harness"})
            self.assertTrue(any(node.status == "active" for node in snapshot.nodes))
            self.assertIn("append_feedback", snapshot.available_actions)
            self.assertIn("force_recover_from_snapshot", snapshot.available_actions)
            self.assertTrue(snapshot.inspector_defaults.get("selected_node_id"))

    def test_project_board_projects_current_next_queue_and_preview(self) -> None:
        with test_workdir("console_project_board") as root:
            self._prepare_workspace(root)
            store = CampaignNegotiationStore()
            draft = CampaignNegotiationDraft(
                draft_id="draft_console_board",
                session_id="thread_console_board",
                goal="Board projection",
                materials=["docs/board.md"],
                selected_template_id="campaign.single_repo_delivery",
                frontdoor_mode_id="delivery",
            )
            store.save(workspace=str(root), draft=draft)

            service = ConsoleQueryService(console_host="0.0.0.0", console_port=8765)
            launched = service.launch_draft(str(root), draft.draft_id)

            board = service.build_project_board(str(root), launched.linked_campaign_id)
            self.assertEqual(board.scope, "campaign")
            self.assertEqual(board.scope_id, launched.linked_campaign_id)
            self.assertIsNotNone(board.current_agent)
            self.assertEqual(board.current_agent.step_id, "turn")
            self.assertEqual(board.current_agent.source, "exact")
            self.assertIsNotNone(board.next_agent)
            self.assertEqual(board.next_agent.step_id, "harness")
            self.assertEqual(board.next_agent.source, "inferred")
            self.assertTrue(any(node.status == "running" for node in board.nodes))
            self.assertTrue(any(node.status == "next" for node in board.nodes))
            self.assertTrue(all(node.detail_available for node in board.nodes))
            self.assertGreaterEqual(len(board.artifacts), 1)
            self.assertGreaterEqual(len(board.records), 1)
            self.assertTrue(board.timeline_items)

            ordered = sorted(board.timeline_items, key=lambda item: item.layout_x)
            for left, right in zip(ordered, ordered[1:]):
                self.assertGreaterEqual(right.layout_x, left.layout_x + 142.0)
            self.assertTrue(any(item.detail_available for item in board.timeline_items))

            preview = service.build_artifact_preview(str(root), launched.linked_campaign_id, board.artifacts[0].artifact_id)
            self.assertEqual(preview.scope, "campaign")
            self.assertEqual(preview.preview_kind, "text")
            self.assertTrue(preview.content)

            detail = service.build_agent_detail(str(root), launched.linked_campaign_id, board.current_agent.step_id)
            self.assertEqual(detail.node_id, "turn")
            self.assertEqual(detail.execution_state, "running")
            self.assertTrue(detail.planned_input.get("goal"))
            self.assertIn(detail.execution_state, {"running", "pending", "completed", "idle_unknown"})

    def test_global_board_and_access_diagnostics_surface_idle_state(self) -> None:
        with test_workdir("console_global_board_idle") as root:
            self._prepare_workspace(root)
            service = ConsoleQueryService(console_host="0.0.0.0", console_port=8765)

            board = service.build_global_scheduler_board(str(root), limit=5)
            access = service.get_access_diagnostics(str(root))

            self.assertEqual(board.scope, "global")
            self.assertIn("idle", board.idle_reason.lower())
            self.assertTrue(access.local_urls)
            self.assertEqual(access.listen_host, "0.0.0.0")
            self.assertEqual(access.port, 8765)

    def test_draft_listing_patch_and_launch_flow_are_console_ready(self) -> None:
        with test_workdir("console_draft_flow") as root:
            self._prepare_workspace(root)
            store = CampaignNegotiationStore()
            draft = CampaignNegotiationDraft(
                draft_id="draft_console_patch",
                session_id="thread_console_patch",
                goal="Initial draft goal",
                materials=["docs/a.md"],
                hard_constraints=["keep scope narrow"],
                acceptance_criteria=["write a report"],
                selected_template_id="campaign.research_then_implement",
                frontdoor_mode_id="research",
            )
            store.save(workspace=str(root), draft=draft)

            service = ConsoleQueryService()
            drafts = service.list_drafts(str(root), limit=10)
            self.assertEqual(drafts[0].draft_id, "draft_console_patch")

            patched = service.patch_draft(
                str(root),
                "draft_console_patch",
                {
                    "goal": "Updated draft goal",
                    "materials": ["docs/a.md", "docs/b.md"],
                    "selected_template_id": "campaign.single_repo_delivery",
                    "frontdoor_mode_id": "delivery",
                    "skill_selection": {"collection_id": "codex_default", "family_hints": ["ops"]},
                },
            )
            self.assertEqual(patched.goal, "Updated draft goal")
            self.assertEqual(patched.selected_template_id, "campaign.single_repo_delivery")
            self.assertEqual(patched.mode_id, "delivery")
            self.assertEqual(patched.skill_selection["collection_id"], "codex_default")

            launched = service.launch_draft(str(root), "draft_console_patch")
            self.assertTrue(launched.linked_campaign_id.startswith("campaign_"))
            self.assertEqual(launched.metadata.get("status"), "started")
            status = service.get_campaign_detail(str(root), launched.linked_campaign_id)
            self.assertEqual(status["skill_exposure_observation"]["collection_id"], "codex_default")

    def test_console_skill_registry_queries_surface_collections_and_diagnostics(self) -> None:
        with test_workdir("console_skill_registry") as root:
            self._prepare_workspace(root)
            service = ConsoleQueryService()

            collections = service.list_skill_collections(str(root))
            detail = service.get_skill_collection_detail(str(root), "codex_default")
            family = service.get_skill_family_detail(str(root), family_id="ops", collection_id="codex_default")
            diagnostics = service.get_skill_diagnostics(str(root))

            self.assertEqual(collections[0]["collection_id"], "codex_default")
            self.assertEqual(detail["collection_id"], "codex_default")
            self.assertEqual(family["family_id"], "ops")
            self.assertEqual(diagnostics["summary"]["collection_count"], 1)

    def test_operator_control_plane_and_authoring_surfaces_are_queryable(self) -> None:
        with test_workdir("console_operator_surfaces") as root:
            self._prepare_workspace(root)
            store = CampaignNegotiationStore()
            draft = CampaignNegotiationDraft(
                draft_id="draft_console_operator",
                session_id="thread_console_operator",
                goal="Upgrade the operator console",
                materials=["docs/runtime/Visual_Console_API_Contract_v1.md"],
                selected_template_id="campaign.single_repo_delivery",
                frontdoor_mode_id="delivery",
                skill_selection={"collection_id": "codex_default", "family_hints": ["ops"]},
            )
            store.save(workspace=str(root), draft=draft)

            query = ConsoleQueryService()
            draft_authoring = query.get_draft_workflow_authoring(str(root), draft.draft_id)
            draft_compile = query.get_draft_compile_preview(str(root), draft.draft_id)

            self.assertEqual(draft_authoring["scope"], "draft")
            self.assertEqual(draft_authoring["template_id"], "campaign.single_repo_delivery")
            self.assertEqual(draft_compile["compile_result"], "ready")
            self.assertEqual(draft_compile["scope_id"], draft.draft_id)

            launched = query.launch_draft(str(root), draft.draft_id)
            campaign_id = launched.linked_campaign_id

            control_plane = query.get_campaign_control_plane(str(root), campaign_id)
            self.assertEqual(control_plane["campaign_id"], campaign_id)
            self.assertIn("annotate_governance", control_plane["available_actions"])
            self.assertIn("force_recover_from_snapshot", control_plane["available_actions"])
            self.assertTrue(control_plane["transition_options"])
            self.assertTrue(control_plane["recovery_candidates"])
            self.assertTrue(control_plane["canonical_session_id"])

            prompt_surface = query.get_prompt_surface(str(root), campaign_id)
            self.assertEqual(prompt_surface["structured_contract"]["skill_exposure"]["collection_id"], "codex_default")

            patched_prompt = query.patch_prompt_surface(
                str(root),
                campaign_id,
                node_id="implement",
                patch={
                    "risk_level": "high",
                    "autonomy_profile": "guarded",
                    "node_overlay": {"notes": ["keep implementation bounded"]},
                    "operator_reason": "tighten operator guardrails",
                },
            )
            self.assertEqual(patched_prompt["structured_contract"]["governance_contract"]["risk_level"], "high")
            self.assertEqual(patched_prompt["structured_contract"]["node_overlay"]["notes"], ["keep implementation bounded"])

            workflow_authoring = query.patch_campaign_workflow_authoring(
                str(root),
                campaign_id,
                patch={
                    "phase_plan": ["implement", "evaluate"],
                    "role_plan": ["builder", "reviewer"],
                    "transition_rules": [{"from": "implement", "to": "evaluate", "when": "deliverable_ready"}],
                    "recovery_entries": [{"resume_from": "implement", "policy": "checkpoint"}],
                    "operator_reason": "compress the loop",
                },
            )
            self.assertEqual(workflow_authoring["phase_plan"], ["implement", "evaluate"])
            self.assertEqual(workflow_authoring["role_plan"], ["builder", "reviewer"])
            self.assertEqual(workflow_authoring["transition_rules"][0]["when"], "deliverable_ready")
            self.assertEqual(workflow_authoring["recovery_entries"][0]["policy"], "checkpoint")

            preserved_workflow = query.patch_campaign_workflow_authoring(
                str(root),
                campaign_id,
                patch={
                    "role_plan": ["builder", "reviewer", "auditor"],
                    "operator_reason": "extend role coverage",
                },
            )
            self.assertEqual(preserved_workflow["role_plan"], ["builder", "reviewer", "auditor"])
            self.assertEqual(preserved_workflow["transition_rules"][0]["when"], "deliverable_ready")
            self.assertEqual(preserved_workflow["recovery_entries"][0]["policy"], "checkpoint")

            control = ConsoleControlService()
            transition = control.apply(
                str(root),
                ControlActionRequest(
                    action="force_recover_from_snapshot",
                    target_id=campaign_id,
                    operator_reason="reload the canonical session",
                ),
            )
            self.assertTrue(transition.ok)
            self.assertIn("latest_turn_receipt", transition.updated_state)

            audits = query.list_audit_actions(str(root), campaign_id)
            action_types = {item["action_type"] for item in audits}
            self.assertIn("prompt_surface_patch", action_types)
            self.assertIn("workflow_authoring_patch", action_types)
            self.assertIn("force_recover_from_snapshot", action_types)

            detail = query.get_audit_action_detail(str(root), campaign_id, audits[0]["action_id"])
            self.assertEqual(detail["action"]["action_id"], audits[0]["action_id"])
            self.assertEqual(detail["action"]["campaign_id"], campaign_id)

    def test_control_service_updates_governance_and_feedback(self) -> None:
        with test_workdir("console_control") as root:
            self._prepare_workspace(root)
            store = CampaignNegotiationStore()
            draft = CampaignNegotiationDraft(
                draft_id="draft_console_control",
                session_id="thread_console_control",
                goal="Control path",
                materials=["docs/control.md"],
                selected_template_id="campaign.single_repo_delivery",
                frontdoor_mode_id="delivery",
            )
            store.save(workspace=str(root), draft=draft)
            query = ConsoleQueryService()
            launched = query.launch_draft(str(root), draft.draft_id)

            control = ConsoleControlService()
            approval = control.apply(
                str(root),
                ControlActionRequest(action="request_approval", target_id=launched.linked_campaign_id),
            )
            self.assertTrue(approval.ok)
            self.assertEqual(approval.updated_state["governance_summary"]["approval_state"], "requested")

            feedback = control.apply(
                str(root),
                ControlActionRequest(
                    action="append_feedback",
                    target_id=launched.linked_campaign_id,
                    payload={"feedback": "Please tighten the acceptance criteria."},
                ),
            )
            self.assertTrue(feedback.ok)
            self.assertGreaterEqual(int(feedback.updated_state["user_feedback"].get("count") or 0), 1)
            status = OrchestratorQueryService().get_campaign_status(str(root), launched.linked_campaign_id)
            self.assertGreaterEqual(int(status.get("user_feedback", {}).get("count") or 0), 1)
            audits = query.list_audit_actions(str(root), launched.linked_campaign_id)
            self.assertTrue(any(item["action_type"] == "request_approval" for item in audits))
            self.assertTrue(any(item["action_type"] == "append_feedback" for item in audits))


if __name__ == "__main__":
    unittest.main()
