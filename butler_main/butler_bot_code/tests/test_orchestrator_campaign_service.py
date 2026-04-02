from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MODULE_DIR = Path(__file__).resolve().parents[1] / "butler_bot"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
BUTLER_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(BUTLER_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BUTLER_MAIN_DIR))

from butler_main.orchestrator import (  # noqa: E402
    CampaignService,
    OrchestratorCampaignService,
    build_orchestrator_service_for_workspace,
)
from butler_main.orchestrator.background_task_bundle import ensure_campaign_bundle_files  # noqa: E402
from butler_main.orchestrator.interfaces import OrchestratorCampaignService as InterfaceCampaignService  # noqa: E402
from butler_main.orchestrator.interfaces import campaign_service as campaign_service_module  # noqa: E402


class _RecordingCampaignService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def create_campaign(self, spec):
        self.calls.append(("create_campaign", spec))
        return {"campaign_id": "campaign_1", "status": "discovering"}

    def get_campaign_status(self, campaign_id: str):
        self.calls.append(("get_campaign_status", campaign_id))
        return {"campaign_id": campaign_id, "status": "active"}

    def summarize_campaign_task(self, campaign_id: str):
        self.calls.append(("summarize_campaign_task", campaign_id))
        return {"progress": {"status": "running"}}

    def list_campaign_artifacts(self, campaign_id: str):
        self.calls.append(("list_campaign_artifacts", campaign_id))
        return [{"campaign_id": campaign_id, "artifact_ref": "artifact://discover/report"}]

    def resume_campaign(self, campaign_id: str):
        self.calls.append(("resume_campaign", campaign_id))
        return {"campaign_id": campaign_id, "status": "iterating"}

    def run_campaign_turn(self, campaign_id: str, *, reason: str = ""):
        self.calls.append(("run_campaign_turn", campaign_id, reason))
        return {"campaign_id": campaign_id, "status": "running"}

    def stop_campaign(self, campaign_id: str):
        self.calls.append(("stop_campaign", campaign_id))
        return {"campaign_id": campaign_id, "status": "stopped"}


class _FakeWorkflowFactory:
    instances: list["_FakeWorkflowFactory"] = []

    def __init__(self, root_dir) -> None:
        self.root_dir = Path(root_dir)
        self.created_sessions: list[dict[str, object]] = []
        self.updated_steps: list[tuple[str, str, str]] = []
        self.patched_states: list[tuple[str, dict[str, object]]] = []
        type(self).instances.append(self)

    def create_session(self, **kwargs):
        self.created_sessions.append(dict(kwargs))
        return types.SimpleNamespace(session_id="workflow_session_fake")

    def update_active_step(self, session_id: str, active_step: str, *, status: str = ""):
        self.updated_steps.append((session_id, active_step, status))
        return types.SimpleNamespace(session_id=session_id, active_step=active_step, status=status)

    def patch_shared_state(self, session_id: str, payload):
        self.patched_states.append((session_id, dict(payload or {})))
        return types.SimpleNamespace(session_id=session_id, state=dict(payload or {}))


class _FakeCampaignSpec:
    def __init__(self, **payload) -> None:
        self.payload = dict(payload)

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))


class _FakeCampaignStore:
    instances: list["_FakeCampaignStore"] = []

    def __init__(self, root) -> None:
        self.root = Path(root)
        type(self).instances.append(self)


class _FakeCampaignDomainService:
    instances: list["_FakeCampaignDomainService"] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = dict(kwargs)
        self.created_specs: list[object] = []
        type(self).instances.append(self)

    def create_campaign(self, spec, **kwargs):
        self.created_specs.append(spec)
        return {
            "campaign_id": "campaign_demo",
            "mission_id": str(kwargs.get("mission_id") or ""),
            "supervisor_session_id": str(kwargs.get("supervisor_session_id") or ""),
            "status": "active",
            "current_phase": "discover",
            "next_phase": "implement",
            "current_iteration": 0,
            "working_contract": {"version": 1},
            "verdict_history": [],
            "store_root": str(self.kwargs["store"].root),
            "workflow_factory_root": str(self.kwargs["workflow_factory"].root_dir),
        }

    def get_campaign_status(self, campaign_id: str):
        return {"campaign_id": campaign_id, "status": "discovering"}

    def summarize_campaign_task(self, campaign_id: str):
        return {"progress": {"status": "draft"}}

    def list_campaign_artifacts(self, campaign_id: str):
        return [{"campaign_id": campaign_id, "artifact_ref": "artifact://campaign/discover"}]

    def resume_campaign(self, campaign_id: str):
        return {"campaign_id": campaign_id, "status": "iterating"}

    def run_campaign_turn(self, campaign_id: str, *, reason: str = ""):
        return {"campaign_id": campaign_id, "status": "running", "reason": reason}

    def stop_campaign(self, campaign_id: str):
        return {"campaign_id": campaign_id, "status": "stopped"}


class _FakeOrchestratorService:
    def create_mission(self, **kwargs):
        return types.SimpleNamespace(mission_id="mission_fake", payload=dict(kwargs))


class _ObservingCampaignDomainService(_FakeCampaignDomainService):
    instances: list["_ObservingCampaignDomainService"] = []

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.observed_mission_status = ""
        self.observed_node_status = ""
        type(self).instances.append(self)

    def create_campaign(self, spec, **kwargs):
        orchestrator_service = self.kwargs.get("orchestrator_service")
        mission_id = str(kwargs.get("mission_id") or "").strip()
        if orchestrator_service is not None and mission_id:
            mission = orchestrator_service.get_mission(mission_id)
            node = mission.node_by_id("campaign_supervisor") if mission is not None else None
            self.observed_mission_status = str(getattr(mission, "status", "") or "").strip()
            self.observed_node_status = str(getattr(node, "status", "") or "").strip()
        return super().create_campaign(spec, **kwargs)


class OrchestratorCampaignServiceTests(unittest.TestCase):
    def _workspace(self) -> tempfile.TemporaryDirectory[str]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "butler_main" / "chat").mkdir(parents=True, exist_ok=True)
        (root / "butler_main" / "butler_bot_code").mkdir(parents=True, exist_ok=True)
        return tmp

    def test_compat_exports_point_to_same_campaign_service(self) -> None:
        self.assertIs(CampaignService, OrchestratorCampaignService)
        self.assertIs(InterfaceCampaignService, OrchestratorCampaignService)

    def test_service_factory_delegates_all_campaign_operations(self) -> None:
        recording = _RecordingCampaignService()
        service = OrchestratorCampaignService(service_factory=lambda workspace: recording)

        created = service.create_campaign("C:/workspace", {"goal": "ship campaign"})
        status = service.get_campaign_status("C:/workspace", "campaign_1")
        task = service.summarize_campaign_task("C:/workspace", "campaign_1")
        artifacts = service.list_campaign_artifacts("C:/workspace", "campaign_1")
        resumed = service.resume_campaign("C:/workspace", "campaign_1")
        turned = service.run_campaign_turn("C:/workspace", "campaign_1", reason="tick")
        stopped = service.stop_campaign("C:/workspace", "campaign_1")

        self.assertEqual(created["campaign_id"], "campaign_1")
        self.assertEqual(status["status"], "active")
        self.assertEqual(task["progress"]["status"], "running")
        self.assertEqual(artifacts[0]["artifact_ref"], "artifact://discover/report")
        self.assertEqual(resumed["status"], "iterating")
        self.assertEqual(turned["status"], "running")
        self.assertEqual(stopped["status"], "stopped")
        self.assertEqual(recording.calls[0], ("create_campaign", {"goal": "ship campaign"}))
        self.assertIn(("get_campaign_status", "campaign_1"), recording.calls)
        self.assertIn(("summarize_campaign_task", "campaign_1"), recording.calls)
        self.assertIn(("list_campaign_artifacts", "campaign_1"), recording.calls)
        self.assertIn(("resume_campaign", "campaign_1"), recording.calls)
        self.assertIn(("run_campaign_turn", "campaign_1", "tick"), recording.calls)
        self.assertIn(("stop_campaign", "campaign_1"), recording.calls)

    def test_default_builder_uses_orchestrator_run_root_and_domain_exports(self) -> None:
        fake_module = types.SimpleNamespace(
            CampaignSpec=_FakeCampaignSpec,
            CampaignDomainService=_FakeCampaignDomainService,
            FileCampaignStore=_FakeCampaignStore,
        )
        sentinel_orchestrator_service = _FakeOrchestratorService()
        _FakeCampaignStore.instances.clear()
        _FakeCampaignDomainService.instances.clear()
        _FakeWorkflowFactory.instances.clear()

        with tempfile.TemporaryDirectory() as tmp:
            orchestrator_root = Path(tmp) / "run" / "orchestrator"
            with (
                patch.object(campaign_service_module, "import_module", return_value=fake_module),
                patch.object(campaign_service_module, "resolve_orchestrator_root", return_value=str(orchestrator_root)),
                patch.object(
                    campaign_service_module,
                    "build_orchestrator_service_for_workspace",
                    return_value=sentinel_orchestrator_service,
                ),
                patch.object(campaign_service_module, "WorkflowFactory", _FakeWorkflowFactory),
            ):
                service = OrchestratorCampaignService()
                created = service.create_campaign("C:/workspace", {"goal": "ship", "materials": ["docs"]})
                status = service.get_campaign_status("C:/workspace", "campaign_demo")
                task = service.summarize_campaign_task("C:/workspace", "campaign_demo")
                artifacts = service.list_campaign_artifacts("C:/workspace", "campaign_demo")
                resumed = service.resume_campaign("C:/workspace", "campaign_demo")
                turned = service.run_campaign_turn("C:/workspace", "campaign_demo", reason="tick")
                stopped = service.stop_campaign("C:/workspace", "campaign_demo")

        self.assertEqual(created["campaign_id"], "campaign_demo")
        self.assertEqual(status["status"], "discovering")
        self.assertEqual(task["progress"]["status"], "draft")
        self.assertEqual(artifacts[0]["artifact_ref"], "artifact://campaign/discover")
        self.assertEqual(resumed["status"], "iterating")
        self.assertEqual(turned["status"], "running")
        self.assertEqual(stopped["status"], "stopped")
        self.assertEqual(_FakeCampaignStore.instances[0].root, orchestrator_root)
        self.assertEqual(_FakeWorkflowFactory.instances[0].root_dir, orchestrator_root / "workflow_sessions")
        self.assertEqual(created["mission_id"], "")
        self.assertEqual(created["supervisor_session_id"], "")
        self.assertEqual(created["canonical_session_id"], "")
        self.assertFalse(any(instance.created_sessions for instance in _FakeWorkflowFactory.instances))
        self.assertFalse(any(instance.patched_states for instance in _FakeWorkflowFactory.instances))
        self.assertIs(
            _FakeCampaignDomainService.instances[0].kwargs["orchestrator_service"],
            sentinel_orchestrator_service,
        )
        self.assertIsInstance(_FakeCampaignDomainService.instances[0].created_specs[0], _FakeCampaignSpec)

    def test_template_contract_is_normalized_into_spec_payload(self) -> None:
        fake_module = types.SimpleNamespace(
            CampaignSpec=_FakeCampaignSpec,
            CampaignDomainService=_FakeCampaignDomainService,
            FileCampaignStore=_FakeCampaignStore,
        )
        sentinel_orchestrator_service = _FakeOrchestratorService()
        _FakeCampaignStore.instances.clear()
        _FakeCampaignDomainService.instances.clear()
        _FakeWorkflowFactory.instances.clear()

        with tempfile.TemporaryDirectory() as tmp:
            orchestrator_root = Path(tmp) / "run" / "orchestrator"
            with (
                patch.object(campaign_service_module, "import_module", return_value=fake_module),
                patch.object(campaign_service_module, "resolve_orchestrator_root", return_value=str(orchestrator_root)),
                patch.object(
                    campaign_service_module,
                    "build_orchestrator_service_for_workspace",
                    return_value=sentinel_orchestrator_service,
                ),
                patch.object(campaign_service_module, "WorkflowFactory", _FakeWorkflowFactory),
            ):
                service = OrchestratorCampaignService()
                service.create_campaign(
                    "C:/workspace",
                    {
                        "goal": "ship with template contract",
                        "metadata": {
                            "template_origin": "campaign.single_repo_delivery",
                            "skeleton_changed": True,
                            "composition_plan": {"base_template_id": "campaign.single_repo_delivery"},
                            "created_from": "campaign_negotiation",
                            "negotiation_session_id": "thread_1",
                        },
                    },
                )

        created_spec = _FakeCampaignDomainService.instances[0].created_specs[0].payload
        self.assertEqual(created_spec["template_origin"], "campaign.single_repo_delivery")
        self.assertEqual(created_spec["composition_mode"], "composition")
        self.assertTrue(created_spec["skeleton_changed"])
        self.assertEqual(
            created_spec["composition_plan"]["base_template_id"],
            "campaign.single_repo_delivery",
        )
        self.assertEqual(created_spec["created_from"], "campaign_negotiation")
        self.assertEqual(created_spec["negotiation_session_id"], "thread_1")
        self.assertIn("template_contract", created_spec["metadata"])
        self.assertEqual(created_spec["metadata"]["template_contract"]["composition_mode"], "composition")

    def test_feedback_surface_bootstrap_merges_feedback_doc_into_payload(self) -> None:
        fake_module = types.SimpleNamespace(
            CampaignSpec=_FakeCampaignSpec,
            CampaignDomainService=_FakeCampaignDomainService,
            FileCampaignStore=_FakeCampaignStore,
        )
        sentinel_orchestrator_service = _FakeOrchestratorService()
        _FakeCampaignStore.instances.clear()
        _FakeCampaignDomainService.instances.clear()
        _FakeWorkflowFactory.instances.clear()

        with tempfile.TemporaryDirectory() as tmp:
            orchestrator_root = Path(tmp) / "run" / "orchestrator"
            with (
                patch.object(campaign_service_module, "import_module", return_value=fake_module),
                patch.object(campaign_service_module, "resolve_orchestrator_root", return_value=str(orchestrator_root)),
                patch.object(
                    campaign_service_module,
                    "build_orchestrator_service_for_workspace",
                    return_value=sentinel_orchestrator_service,
                ),
                patch.object(campaign_service_module, "WorkflowFactory", _FakeWorkflowFactory),
                patch.object(
                    campaign_service_module,
                    "_bootstrap_feedback_surface",
                    return_value={
                        "document_id": "doxc_feedback",
                        "url": "https://feishu.cn/docx/doxc_feedback",
                        "title": "Task - ship",
                    },
                ),
            ):
                service = OrchestratorCampaignService()
                created = service.create_campaign(
                    "C:/workspace",
                    {
                        "goal": "ship with feedback",
                        "metadata": {
                            "feedback_contract": {
                                "platform": "feishu",
                                "target": "ou_feedback",
                                "target_type": "open_id",
                                "doc_enabled": True,
                            }
                        },
                    },
                )

        self.assertEqual(created["feedback_doc"]["document_id"], "doxc_feedback")
        self.assertEqual(created["metadata"]["feedback_doc"]["url"], "https://feishu.cn/docx/doxc_feedback")

    def test_feedback_contract_preserves_explicit_push_only_mode(self) -> None:
        fake_module = types.SimpleNamespace(
            CampaignSpec=_FakeCampaignSpec,
            CampaignDomainService=_FakeCampaignDomainService,
            FileCampaignStore=_FakeCampaignStore,
        )

        class _RecordingOrchestratorService:
            def __init__(self) -> None:
                self.last_create_payload = None

            def create_mission(self, **kwargs):
                self.last_create_payload = dict(kwargs)
                return types.SimpleNamespace(mission_id="mission_fake", payload=dict(kwargs))

        sentinel_orchestrator_service = _RecordingOrchestratorService()
        _FakeCampaignStore.instances.clear()
        _FakeCampaignDomainService.instances.clear()
        _FakeWorkflowFactory.instances.clear()

        with tempfile.TemporaryDirectory() as tmp:
            orchestrator_root = Path(tmp) / "run" / "orchestrator"
            with (
                patch.object(campaign_service_module, "import_module", return_value=fake_module),
                patch.object(campaign_service_module, "resolve_orchestrator_root", return_value=str(orchestrator_root)),
                patch.object(
                    campaign_service_module,
                    "build_orchestrator_service_for_workspace",
                    return_value=sentinel_orchestrator_service,
                ),
                patch.object(campaign_service_module, "WorkflowFactory", _FakeWorkflowFactory),
                patch.object(
                    campaign_service_module,
                    "_bootstrap_feedback_surface",
                    return_value=None,
                ),
            ):
                service = OrchestratorCampaignService()
                created = service.create_campaign(
                    "C:/workspace",
                    {
                        "goal": "ship with push-only feedback",
                        "metadata": {
                            "feedback_contract": {
                                "platform": "feishu",
                                "target": "ou_feedback",
                                "target_type": "open_id",
                                "doc_enabled": False,
                                "progress_surface": "push_only",
                            }
                        },
                    },
                )

        created_spec = _FakeCampaignDomainService.instances[0].created_specs[0].payload
        self.assertFalse(bool(created_spec["metadata"]["feedback_contract"]["doc_enabled"]))
        self.assertEqual(created_spec["metadata"]["feedback_contract"]["progress_surface"], "push_only")
        self.assertIsNone(sentinel_orchestrator_service.last_create_payload)

    def test_negotiation_created_campaign_gets_fixed_bundle_and_codex_runtime_defaults(self) -> None:
        fake_module = types.SimpleNamespace(
            CampaignSpec=_FakeCampaignSpec,
            CampaignDomainService=_FakeCampaignDomainService,
            FileCampaignStore=_FakeCampaignStore,
        )
        sentinel_orchestrator_service = _FakeOrchestratorService()
        _FakeCampaignStore.instances.clear()
        _FakeCampaignDomainService.instances.clear()
        _FakeWorkflowFactory.instances.clear()

        with tempfile.TemporaryDirectory() as tmp:
            orchestrator_root = Path(tmp) / "run" / "orchestrator"
            with (
                patch.object(campaign_service_module, "import_module", return_value=fake_module),
                patch.object(campaign_service_module, "resolve_orchestrator_root", return_value=str(orchestrator_root)),
                patch.object(
                    campaign_service_module,
                    "build_orchestrator_service_for_workspace",
                    return_value=sentinel_orchestrator_service,
                ),
                patch.object(campaign_service_module, "WorkflowFactory", _FakeWorkflowFactory),
            ):
                service = OrchestratorCampaignService()
                service.create_campaign(
                    tmp,
                    {
                        "goal": "ship negotiation-created research task",
                        "metadata": {
                            "created_from": "campaign_negotiation",
                            "planning_contract": {"mode_id": "research"},
                            "template_origin": "campaign.research_then_implement",
                        },
                    },
                )

        created_spec = _FakeCampaignDomainService.instances[0].created_specs[0].payload
        metadata = dict(created_spec["metadata"])
        self.assertEqual(metadata["campaign_runtime"]["mode"], "codex")
        self.assertEqual(metadata["skill_exposure"]["collection_id"], "codex_default")
        self.assertEqual(metadata["skill_exposure"]["injection_mode"], "shortlist")
        self.assertEqual(metadata["skill_exposure"]["provider_skill_source"], "butler")
        self.assertTrue(bool(metadata["strict_acceptance_required"]))
        self.assertIn("工作区/Butler/deliveries/background_tasks/", metadata["bundle_root"])
        self.assertTrue(metadata["bundle_manifest"].endswith("manifest.json"))
        self.assertTrue(metadata["planning_contract"]["spec_ref"].endswith("briefs/spec.md"))
        self.assertTrue(metadata["planning_contract"]["plan_ref"].endswith("briefs/plan.md"))
        self.assertTrue(metadata["planning_contract"]["progress_ref"].endswith("progress.md"))

    def test_bundle_helper_skips_cwd_writes_when_bundle_root_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            previous_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                patch = ensure_campaign_bundle_files(
                    workspace=tmp,
                    payload={
                        "campaign_id": "campaign_demo",
                        "status": "discovering",
                        "metadata": {},
                    },
                )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(patch, {})
            self.assertFalse((Path(tmp) / "manifest.json").exists())
            self.assertFalse((Path(tmp) / "progress.md").exists())
            self.assertFalse((Path(tmp) / "artifacts").exists())
            self.assertFalse((Path(tmp) / "briefs").exists())
            self.assertFalse((Path(tmp) / "deliveries").exists())

    def test_real_campaign_flow_creates_agent_turn_session(self) -> None:
        with self._workspace() as tmp:
            workspace = tmp
            service = OrchestratorCampaignService()

            created = service.create_campaign(
                workspace,
                {
                    "top_level_goal": "Ship the first Campaign MVP skeleton",
                    "materials": ["docs/05", "docs/09"],
                    "hard_constraints": ["do not mutate top-level goal"],
                    "iteration_budget": {"max_iterations": 2, "max_minutes": 30, "max_file_changes": 4},
                },
            )
            self.assertEqual(created["status"], "draft")
            self.assertTrue(str(created["campaign_id"]).startswith("campaign_"))
            self.assertTrue(str(created["supervisor_session_id"]).startswith("workflow_session_"))
            self.assertEqual(created["mission_id"], "")
            self.assertEqual(created["canonical_session_id"], created["supervisor_session_id"])
            self.assertEqual(created["current_phase"], "discover")
            self.assertEqual(created["next_phase"], "discover")
            self.assertIn("background_tasks", str(created["metadata"]["bundle_root"]))
            self.assertTrue(Path(created["metadata"]["bundle_manifest"]).exists())

            orchestrator = build_orchestrator_service_for_workspace(workspace)
            session = orchestrator.summarize_workflow_session(created["supervisor_session_id"])
            self.assertEqual(session["template"]["template_id"], "campaign.agent_turn.v1")
            self.assertEqual(session["shared_state"]["state"]["campaign_id"], created["campaign_id"])
            self.assertEqual(session["shared_state"]["state"]["campaign_status"], "draft")
            self.assertEqual(session["active_step"], "turn")

            artifacts = service.list_campaign_artifacts(workspace, created["campaign_id"])
            self.assertEqual(len(artifacts), 0)

            resumed = service.resume_campaign(workspace, created["campaign_id"])
            self.assertEqual(resumed["status"], "running")
            self.assertEqual(resumed["current_iteration"], 1)
            self.assertEqual(resumed["next_phase"], "iterate")
            self.assertEqual(len(resumed["verdict_history"]), 1)
            self.assertGreaterEqual(len(resumed["contract_history"]), 1)
            self.assertEqual(resumed["top_level_goal"], created["top_level_goal"])
            self.assertEqual(resumed["hard_constraints"], created["hard_constraints"])
            self.assertEqual(resumed["verdict_history"][0]["reviewer_role_id"], "campaign_supervisor")
            self.assertEqual(resumed["verdict_history"][0]["decision"], "continue")
            self.assertEqual(
                resumed["metadata"]["campaign_engine"],
                "agent_turn",
            )
            self.assertEqual(
                resumed["task_summary"]["progress"]["artifact_count"],
                1,
            )

            resumed_session = orchestrator.summarize_workflow_session(created["supervisor_session_id"])
            self.assertEqual(resumed_session["active_step"], "turn")
            self.assertEqual(resumed_session["shared_state"]["state"]["turn_count"], 1)
            self.assertEqual(
                resumed_session["shared_state"]["state"]["campaign_status"],
                "running",
            )

            stopped = service.stop_campaign(workspace, created["campaign_id"])
            self.assertEqual(stopped["status"], "paused")
            stopped_session = orchestrator.summarize_workflow_session(created["supervisor_session_id"])
            self.assertEqual(stopped_session["status"], "paused")
            self.assertEqual(stopped_session["active_step"], "")

    def test_campaign_creation_no_longer_bootstraps_mission_shell(self) -> None:
        fake_module = types.SimpleNamespace(
            CampaignSpec=_FakeCampaignSpec,
            CampaignDomainService=_ObservingCampaignDomainService,
            FileCampaignStore=_FakeCampaignStore,
        )
        _FakeCampaignStore.instances.clear()
        _FakeCampaignDomainService.instances.clear()
        _ObservingCampaignDomainService.instances.clear()

        with self._workspace() as tmp:
            with patch.object(campaign_service_module, "import_module", return_value=fake_module):
                service = OrchestratorCampaignService()
                created = service.create_campaign(
                    tmp,
                    {
                        "top_level_goal": "Start campaign only after instance exists",
                        "materials": ["docs/05"],
                    },
                )

            observed = _ObservingCampaignDomainService.instances[0]
            self.assertEqual(observed.observed_mission_status, "")
            self.assertEqual(observed.observed_node_status, "")
            self.assertEqual(created["mission_id"], "")
            self.assertEqual(created["supervisor_session_id"], "")

    def test_campaign_converges_at_budget_boundary(self) -> None:
        with self._workspace() as tmp:
            service = OrchestratorCampaignService()
            created = service.create_campaign(
                tmp,
                {
                    "top_level_goal": "Reach converge on second resume",
                    "materials": ["docs/09"],
                    "hard_constraints": ["reviewer decides final verdict"],
                    "iteration_budget": {"max_iterations": 2},
                },
            )

            first = service.resume_campaign(tmp, created["campaign_id"])
            second = service.resume_campaign(tmp, created["campaign_id"])

            self.assertEqual(first["verdict_history"][0]["decision"], "continue")
            self.assertEqual(second["status"], "completed")
            self.assertEqual(second["verdict_history"][-1]["decision"], "converge")
            self.assertEqual(second["next_phase"], "iterate")
            self.assertEqual(second["top_level_goal"], created["top_level_goal"])
            self.assertEqual(second["hard_constraints"], created["hard_constraints"])


if __name__ == "__main__":
    unittest.main()
