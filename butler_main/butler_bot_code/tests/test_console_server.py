from __future__ import annotations

from datetime import datetime, timedelta
import io
import json
import sys
import unittest
from pathlib import Path
from wsgiref.util import setup_testing_defaults


BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
for candidate in (str(REPO_ROOT), str(BUTLER_MAIN_DIR), str(MODULE_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from butler_main.butler_bot_code.tests._tmpdir import test_workdir
from butler_main.chat.negotiation import CampaignNegotiationDraft, CampaignNegotiationStore
from butler_main.console import create_console_wsgi_app
from butler_main.orchestrator.interfaces.campaign_service import OrchestratorCampaignService
from butler_main.orchestrator.interfaces.runner import build_orchestrator_runtime_state_store


class ConsoleServerTests(unittest.TestCase):
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

    def _prepare_webapp_root(self, root: Path, *, with_dist: bool) -> Path:
        webapp_root = root / "webapp"
        webapp_root.mkdir(parents=True, exist_ok=True)
        (webapp_root / "index.html").write_text("<h1>legacy-webapp</h1>", encoding="utf-8")
        if with_dist:
            dist_root = webapp_root / "dist"
            dist_root.mkdir(parents=True, exist_ok=True)
            (dist_root / "index.html").write_text("<h1>dist-webapp</h1>", encoding="utf-8")
        return webapp_root

    def _request(
        self,
        app,
        method: str,
        path: str,
        *,
        query: str = "",
        body: dict | None = None,
    ) -> tuple[str, dict[str, str], bytes]:
        raw = json.dumps(body).encode("utf-8") if body is not None else b""
        environ: dict[str, object] = {}
        setup_testing_defaults(environ)
        environ["REQUEST_METHOD"] = method
        environ["PATH_INFO"] = path
        environ["QUERY_STRING"] = query
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
        captured: dict[str, object] = {}

        def start_response(status: str, headers: list[tuple[str, str]]) -> None:
            captured["status"] = status
            captured["headers"] = headers

        chunks = app(environ, start_response)
        payload = b"".join(chunks)
        headers = {key: value for key, value in captured.get("headers", [])}
        return str(captured.get("status") or ""), headers, payload

    def test_wsgi_console_serves_static_assets_and_api_flow(self) -> None:
        with test_workdir("console_server_flow") as root:
            self._prepare_workspace(root)
            store = CampaignNegotiationStore()
            draft = CampaignNegotiationDraft(
                draft_id="draft_console_http",
                session_id="thread_console_http",
                goal="Build the visual console",
                materials=["docs/runtime/Visual_Console_API_Contract_v1.md"],
                hard_constraints=["keep Python first"],
                selected_template_id="campaign.single_repo_delivery",
                frontdoor_mode_id="delivery",
            )
            store.save(workspace=str(root), draft=draft)

            app = create_console_wsgi_app(workspace=str(root))

            status, headers, payload = self._request(app, "GET", "/console/")
            self.assertEqual(status, "200 OK")
            self.assertIn("text/html", headers.get("Content-Type", ""))
            self.assertIn(b"Butler Visual Console", payload)

            status, _, payload = self._request(app, "GET", "/console/api/drafts")
            self.assertEqual(status, "200 OK")
            drafts = json.loads(payload.decode("utf-8"))
            self.assertEqual(drafts[0]["draft_id"], "draft_console_http")

            status, _, payload = self._request(
                app,
                "PATCH",
                "/console/api/drafts/draft_console_http",
                body={
                    "goal": "Updated draft goal",
                    "materials": ["docs/a.md", "docs/b.md"],
                    "skill_selection": {"collection_id": "codex_default", "family_hints": ["ops"]},
                },
            )
            self.assertEqual(status, "200 OK")
            patched = json.loads(payload.decode("utf-8"))
            self.assertEqual(patched["goal"], "Updated draft goal")
            self.assertEqual(patched["skill_selection"]["collection_id"], "codex_default")

            status, _, payload = self._request(app, "GET", "/console/api/drafts/draft_console_http/workflow-authoring")
            self.assertEqual(status, "200 OK")
            draft_workflow = json.loads(payload.decode("utf-8"))
            self.assertEqual(draft_workflow["scope"], "draft")
            self.assertEqual(draft_workflow["template_id"], "campaign.single_repo_delivery")

            status, _, payload = self._request(
                app,
                "PATCH",
                "/console/api/drafts/draft_console_http/workflow-authoring",
                body={
                    "composition_mode": "composition",
                    "composition_plan": {
                        "phase_plan": ["discover", "implement", "evaluate"],
                        "role_plan": ["builder", "reviewer"],
                    },
                    "skeleton_changed": True,
                },
            )
            self.assertEqual(status, "200 OK")
            patched_workflow = json.loads(payload.decode("utf-8"))
            self.assertEqual(patched_workflow["composition_mode"], "composition")
            self.assertTrue(patched_workflow["skeleton_changed"])

            status, _, payload = self._request(
                app,
                "POST",
                "/console/api/drafts/draft_console_http/compile-preview",
                body={
                    "selected_template_id": "campaign.single_repo_delivery",
                    "composition_mode": "composition",
                    "composition_plan": {
                        "phase_plan": ["discover", "implement", "evaluate"],
                        "role_plan": ["builder", "reviewer"],
                    },
                    "skeleton_changed": True,
                },
            )
            self.assertEqual(status, "200 OK")
            compile_preview = json.loads(payload.decode("utf-8"))
            self.assertEqual(compile_preview["compile_result"], "ready")
            self.assertEqual(compile_preview["scope"], "draft")

            status, _, payload = self._request(app, "POST", "/console/api/drafts/draft_console_http/launch")
            self.assertEqual(status, "200 OK")
            launched = json.loads(payload.decode("utf-8"))
            campaign_id = launched["linked_campaign_id"]
            self.assertTrue(campaign_id.startswith("campaign_"))

            status, _, payload = self._request(app, "GET", "/console/api/skills/collections")
            self.assertEqual(status, "200 OK")
            collections = json.loads(payload.decode("utf-8"))
            self.assertEqual(collections[0]["collection_id"], "codex_default")

            status, _, payload = self._request(app, "GET", "/console/api/skills/collections/codex_default")
            self.assertEqual(status, "200 OK")
            collection = json.loads(payload.decode("utf-8"))
            self.assertEqual(collection["collection_id"], "codex_default")

            status, _, payload = self._request(app, "GET", "/console/api/skills/families/ops", query="collection_id=codex_default")
            self.assertEqual(status, "200 OK")
            family = json.loads(payload.decode("utf-8"))
            self.assertEqual(family["family_id"], "ops")

            status, _, payload = self._request(app, "GET", "/console/api/skills/search", query="query=sample&collection_id=codex_default")
            self.assertEqual(status, "200 OK")
            search = json.loads(payload.decode("utf-8"))
            self.assertEqual(search["skills"][0]["name"], "sample-skill")

            status, _, payload = self._request(app, "GET", "/console/api/skills/diagnostics")
            self.assertEqual(status, "200 OK")
            diagnostics = json.loads(payload.decode("utf-8"))
            self.assertEqual(diagnostics["summary"]["collection_count"], 1)

            status, _, payload = self._request(app, "GET", "/console/api/access")
            self.assertEqual(status, "200 OK")
            access = json.loads(payload.decode("utf-8"))
            self.assertEqual(access["listen_host"], "127.0.0.1")
            self.assertEqual(access["port"], 8765)

            status, _, payload = self._request(app, "GET", "/console/api/global/board")
            self.assertEqual(status, "200 OK")
            global_board = json.loads(payload.decode("utf-8"))
            self.assertEqual(global_board["scope"], "global")

            status, _, payload = self._request(app, "GET", f"/console/api/campaigns/{campaign_id}/graph")
            self.assertEqual(status, "200 OK")
            graph = json.loads(payload.decode("utf-8"))
            self.assertGreaterEqual(len(graph["nodes"]), 1)

            status, _, payload = self._request(app, "GET", f"/console/api/campaigns/{campaign_id}/control-plane")
            self.assertEqual(status, "200 OK")
            control_plane = json.loads(payload.decode("utf-8"))
            self.assertEqual(control_plane["campaign_id"], campaign_id)
            self.assertIn("annotate_governance", control_plane["available_actions"])
            self.assertIn("force_recover_from_snapshot", control_plane["available_actions"])

            status, _, payload = self._request(app, "GET", f"/console/api/campaigns/{campaign_id}/transition-options")
            self.assertEqual(status, "200 OK")
            transition_options = json.loads(payload.decode("utf-8"))
            self.assertEqual(transition_options["campaign_id"], campaign_id)
            self.assertTrue(transition_options["options"])

            status, _, payload = self._request(app, "GET", f"/console/api/campaigns/{campaign_id}/recovery-candidates")
            self.assertEqual(status, "200 OK")
            recovery_candidates = json.loads(payload.decode("utf-8"))
            self.assertEqual(recovery_candidates["campaign_id"], campaign_id)
            self.assertTrue(recovery_candidates["candidates"])

            status, _, payload = self._request(app, "GET", f"/console/api/campaigns/{campaign_id}/board")
            self.assertEqual(status, "200 OK")
            board = json.loads(payload.decode("utf-8"))
            self.assertEqual(board["scope"], "campaign")
            self.assertTrue(board["nodes"])
            artifact_id = board["artifacts"][0]["artifact_id"]
            detail_node_id = next(node["detail_node_id"] for node in board["nodes"] if node["detail_available"])

            status, _, payload = self._request(app, "GET", f"/console/api/campaigns/{campaign_id}/prompt-surface")
            self.assertEqual(status, "200 OK")
            prompt_surface = json.loads(payload.decode("utf-8"))
            self.assertEqual(prompt_surface["structured_contract"]["skill_exposure"]["collection_id"], "codex_default")

            status, _, payload = self._request(
                app,
                "PATCH",
                f"/console/api/campaigns/{campaign_id}/prompt-surface",
                body={
                    "risk_level": "high",
                    "autonomy_profile": "guarded",
                    "operator_reason": "tighten campaign guardrails",
                },
            )
            self.assertEqual(status, "200 OK")
            patched_prompt = json.loads(payload.decode("utf-8"))
            self.assertEqual(patched_prompt["structured_contract"]["governance_contract"]["risk_level"], "high")

            status, _, payload = self._request(
                app,
                "GET",
                f"/console/api/campaigns/{campaign_id}/agents/{detail_node_id}/prompt-surface",
            )
            self.assertEqual(status, "200 OK")
            agent_prompt = json.loads(payload.decode("utf-8"))
            self.assertEqual(agent_prompt["node_id"], detail_node_id)

            status, _, payload = self._request(app, "GET", f"/console/api/campaigns/{campaign_id}/workflow-authoring")
            self.assertEqual(status, "200 OK")
            workflow_authoring = json.loads(payload.decode("utf-8"))
            self.assertEqual(workflow_authoring["scope"], "campaign")

            status, _, payload = self._request(
                app,
                "PATCH",
                f"/console/api/campaigns/{campaign_id}/workflow-authoring",
                body={
                    "phase_plan": ["implement", "evaluate"],
                    "role_plan": ["builder", "reviewer"],
                    "operator_reason": "compress the live loop",
                },
            )
            self.assertEqual(status, "200 OK")
            patched_campaign_workflow = json.loads(payload.decode("utf-8"))
            self.assertEqual(patched_campaign_workflow["phase_plan"], ["implement", "evaluate"])

            status, _, payload = self._request(
                app,
                "GET",
                f"/console/api/campaigns/{campaign_id}/artifacts/{artifact_id}/preview",
            )
            self.assertEqual(status, "200 OK")
            preview = json.loads(payload.decode("utf-8"))
            self.assertEqual(preview["scope"], "campaign")
            self.assertTrue(preview["content"])

            status, _, payload = self._request(app, "GET", f"/console/api/campaigns/{campaign_id}/events")
            self.assertEqual(status, "200 OK")
            events = json.loads(payload.decode("utf-8"))
            self.assertTrue(any(item["event_type"] == "campaign_created" for item in events))

            status, headers, payload = self._request(app, "GET", f"/console/api/campaigns/{campaign_id}/events/stream")
            self.assertEqual(status, "200 OK")
            self.assertIn("text/event-stream", headers.get("Content-Type", ""))
            self.assertNotIn("Connection", headers)
            self.assertIn(b"event: message", payload)
            self.assertIn(b"event:", payload)
            self.assertIn(b"data:", payload)

            status, _, payload = self._request(
                app,
                "GET",
                f"/console/api/campaigns/{campaign_id}/agents/{detail_node_id}/detail",
            )
            self.assertEqual(status, "200 OK")
            detail = json.loads(payload.decode("utf-8"))
            self.assertEqual(detail["node_id"], detail_node_id)
            self.assertIn(detail["execution_state"], {"running", "pending", "completed", "idle_unknown"})

            status, _, payload = self._request(app, "GET", f"/console/api/campaigns/{campaign_id}/audit-actions")
            self.assertEqual(status, "200 OK")
            audit_actions = json.loads(payload.decode("utf-8"))
            self.assertTrue(any(item["action_type"] == "prompt_surface_patch" for item in audit_actions))
            self.assertTrue(any(item["action_type"] == "workflow_authoring_patch" for item in audit_actions))
            audit_action_id = audit_actions[0]["action_id"]

            status, _, payload = self._request(
                app,
                "GET",
                f"/console/api/campaigns/{campaign_id}/audit-actions/{audit_action_id}",
            )
            self.assertEqual(status, "200 OK")
            audit_detail = json.loads(payload.decode("utf-8"))
            self.assertEqual(audit_detail["action"]["action_id"], audit_action_id)

            status, _, payload = self._request(
                app,
                "POST",
                f"/console/api/campaigns/{campaign_id}/actions",
                body={"action": "request_approval"},
            )
            self.assertEqual(status, "200 OK")
            action_result = json.loads(payload.decode("utf-8"))
            self.assertTrue(action_result["ok"])
            self.assertEqual(action_result["updated_state"]["governance_summary"]["approval_state"], "requested")

    def test_wsgi_console_blocks_mutations_when_runtime_is_stale(self) -> None:
        with test_workdir("console_server_stale") as root:
            self._prepare_workspace(root)
            store = CampaignNegotiationStore()
            store.save(
                workspace=str(root),
                draft=CampaignNegotiationDraft(
                    draft_id="draft_console_stale",
                    session_id="thread_console_stale",
                    goal="Blocked by stale runtime",
                    selected_template_id="campaign.single_repo_delivery",
                    frontdoor_mode_id="delivery",
                ),
            )
            created = OrchestratorCampaignService().create_campaign(
                str(root),
                {
                    "top_level_goal": "Control should be blocked when stale",
                    "materials": ["docs/05"],
                },
            )

            runtime_state = build_orchestrator_runtime_state_store(str(root))
            runtime_state.write_run_state(run_id="run_console_stale", state="running", phase="tick")
            stale_payload = runtime_state.read_run_state()
            stale_payload["updated_at"] = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            runtime_state.run_state_file().write_text(json.dumps(stale_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            app = create_console_wsgi_app(workspace=str(root), stale_seconds=30)

            status, _, payload = self._request(
                app,
                "PATCH",
                "/console/api/drafts/draft_console_stale",
                body={"goal": "Should not save"},
            )
            self.assertEqual(status, "409 Conflict")
            self.assertIn("stale", payload.decode("utf-8"))

    def test_wsgi_console_prefers_dist_when_present(self) -> None:
        with test_workdir("console_server_dist_preference") as root:
            self._prepare_workspace(root)
            webapp_root = self._prepare_webapp_root(root, with_dist=True)
            app = create_console_wsgi_app(workspace=str(root), webapp_root=webapp_root)

            status, _, payload = self._request(app, "GET", "/console/")
            self.assertEqual(status, "200 OK")
            self.assertIn("dist-webapp", payload.decode("utf-8"))

    def test_wsgi_console_rewrites_root_relative_asset_paths_in_index(self) -> None:
        with test_workdir("console_server_asset_rewrite") as root:
            self._prepare_workspace(root)
            webapp_root = root / "webapp"
            dist_root = webapp_root / "dist"
            dist_root.mkdir(parents=True, exist_ok=True)
            (dist_root / "index.html").write_text(
                '<script src="/assets/app.js"></script><link rel="stylesheet" href="/assets/app.css">',
                encoding="utf-8",
            )
            app = create_console_wsgi_app(workspace=str(root), webapp_root=webapp_root)

            status, _, payload = self._request(app, "GET", "/console/")
            html = payload.decode("utf-8")
            self.assertEqual(status, "200 OK")
            self.assertIn('/console/assets/app.js', html)
            self.assertIn('/console/assets/app.css', html)
            self.assertNotIn('src="/assets/app.js"', html)
            self.assertNotIn('href="/assets/app.css"', html)

    def test_wsgi_console_falls_back_to_legacy_when_dist_missing(self) -> None:
        with test_workdir("console_server_legacy_fallback") as root:
            self._prepare_workspace(root)
            webapp_root = self._prepare_webapp_root(root, with_dist=False)
            app = create_console_wsgi_app(workspace=str(root), webapp_root=webapp_root)

            status, _, payload = self._request(app, "GET", "/console/")
            self.assertEqual(status, "200 OK")
            self.assertIn("legacy-webapp", payload.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
