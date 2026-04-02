from __future__ import annotations

import sys
import tempfile
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

from butler_main.domains.campaign import (  # noqa: E402
    CampaignCodexResult,
    CampaignDomainService,
    CampaignSupervisorRuntime,
)


class _RecordingCodexProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, *, prompt: str, workspace: str, timeout: int, runtime_request=None) -> CampaignCodexResult:
        self.calls.append(
            {
                "prompt": str(prompt),
                "workspace": str(workspace),
                "timeout": int(timeout),
                "runtime_request": dict(runtime_request or {}),
            }
        )
        return CampaignCodexResult(
            ok=True,
            output_text="codex runtime summary",
            metadata={"cli": "codex", "model": "gpt-5.4"},
        )


class CampaignDomainRuntimeTests(unittest.TestCase):
    def test_default_campaign_runtime_remains_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = CampaignDomainService(tmp)
            created = service.create_campaign(
                {
                    "top_level_goal": "Keep default runtime deterministic",
                    "materials": ["docs/05"],
                    "hard_constraints": ["reviewer independent"],
                },
                mission_id="mission_demo",
                supervisor_session_id="workflow_session_demo",
            )
            resumed = service.resume_campaign(created.campaign_id)

            self.assertEqual(created.metadata["campaign_runtime"]["mode"], "deterministic")
            artifact_kinds = [item.kind for item in service.list_campaign_artifacts(created.campaign_id)]
            self.assertNotIn("codex_discover_report", artifact_kinds)
            self.assertNotIn("codex_implement_report", artifact_kinds)
            self.assertNotIn("codex_iterate_report", artifact_kinds)
            self.assertEqual(resumed.verdict_history[0].metadata["evaluator_kind"], "agent_supervisor")

    def test_campaign_runtime_can_switch_to_codex_via_spec_metadata(self) -> None:
        provider = _RecordingCodexProvider()
        with tempfile.TemporaryDirectory() as tmp:
            service = CampaignDomainService(tmp, codex_provider=provider)
            created = service.create_campaign(
                {
                    "top_level_goal": "Use codex as the thin campaign runtime adapter",
                    "materials": ["docs/05", "docs/11"],
                    "hard_constraints": ["reviewer remains independent"],
                    "workspace_root": tmp,
                    "repo_root": tmp,
                    "metadata": {
                        "campaign_runtime": {
                            "mode": "codex",
                        }
                    },
                },
                mission_id="mission_demo",
                supervisor_session_id="workflow_session_demo",
            )
            resumed = service.resume_campaign(created.campaign_id)

            self.assertEqual(created.metadata["campaign_runtime"]["mode"], "codex")
            self.assertEqual(resumed.verdict_history[0].metadata["evaluator_kind"], "agent_supervisor")
            self.assertEqual(len(provider.calls), 1)
            self.assertEqual(
                provider.calls[0]["runtime_request"]["skill_exposure"]["collection_id"],
                "codex_default",
            )
            self.assertIn("campaign supervisor", str(provider.calls[0]["prompt"]).lower())
            artifact_kinds = [item.kind for item in service.list_campaign_artifacts(created.campaign_id)]
            self.assertIn("campaign_turn_report", artifact_kinds)

    def test_explicit_supervisor_runtime_is_not_overridden_by_codex_mode(self) -> None:
        provider = _RecordingCodexProvider()
        with tempfile.TemporaryDirectory() as tmp:
            service = CampaignDomainService(
                tmp,
                supervisor_runtime=CampaignSupervisorRuntime(),
                codex_provider=provider,
            )
            created = service.create_campaign(
                {
                    "top_level_goal": "Respect explicit supervisor runtime injection",
                    "materials": ["docs/11"],
                    "hard_constraints": ["stable DI priority"],
                    "metadata": {
                        "campaign_runtime": {
                            "mode": "codex",
                        }
                    },
                },
                mission_id="mission_demo",
                supervisor_session_id="workflow_session_demo",
            )
            resumed = service.resume_campaign(created.campaign_id)

            self.assertEqual(created.metadata["campaign_runtime"]["mode"], "codex")
            self.assertEqual(len(provider.calls), 0)
            artifact_kinds = [item.kind for item in service.list_campaign_artifacts(created.campaign_id)]
            self.assertNotIn("codex_discover_report", artifact_kinds)
            self.assertNotIn("codex_implement_report", artifact_kinds)
            self.assertNotIn("codex_iterate_report", artifact_kinds)
            self.assertEqual(resumed.verdict_history[0].metadata["evaluator_kind"], "deterministic_reviewer")

    def test_template_contract_is_normalized_and_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = CampaignDomainService(tmp)
            created = service.create_campaign(
                {
                    "top_level_goal": "Normalize template contract",
                    "materials": ["docs/05"],
                    "metadata": {
                        "template_origin": "campaign.single_repo_delivery",
                        "skeleton_changed": True,
                        "composition_plan": {"base_template_id": "campaign.single_repo_delivery"},
                        "created_from": "campaign_negotiation",
                        "negotiation_session_id": "thread_1",
                    },
                },
                mission_id="mission_demo",
                supervisor_session_id="workflow_session_demo",
            )

            contract = created.metadata.get("template_contract") or {}
            self.assertEqual(contract.get("template_origin"), "campaign.single_repo_delivery")
            self.assertEqual(contract.get("composition_mode"), "composition")
            self.assertTrue(contract.get("skeleton_changed"))
            self.assertEqual(
                contract.get("composition_plan", {}).get("base_template_id"),
                "campaign.single_repo_delivery",
            )
            self.assertEqual(contract.get("created_from"), "campaign_negotiation")
            self.assertEqual(contract.get("negotiation_session_id"), "thread_1")

            spec_payload = created.metadata.get("spec") or {}
            self.assertEqual(spec_payload.get("template_origin"), "campaign.single_repo_delivery")
            self.assertEqual(spec_payload.get("composition_mode"), "composition")
            self.assertTrue(spec_payload.get("skeleton_changed"))

    def test_strict_acceptance_blocks_placeholder_implementation_from_converging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = CampaignDomainService(tmp)
            created = service.create_campaign(
                {
                    "top_level_goal": "Keep placeholder artifacts from closing negotiation-created work",
                    "workspace_root": tmp,
                    "repo_root": tmp,
                    "metadata": {
                        "strict_acceptance_required": True,
                        "pending_correctness_checks": ["clarify_scope"],
                    },
                },
                mission_id="mission_demo",
                supervisor_session_id="workflow_session_demo",
            )

            resumed = service.resume_campaign(created.campaign_id)

            self.assertEqual(resumed.status, "running")
            self.assertEqual(resumed.verdict_history[-1].decision, "continue")
            self.assertIn("pending_correctness_checks", resumed.metadata["latest_acceptance_blockers"])
            self.assertEqual(resumed.metadata["latest_implement_artifact"]["placeholder"], True)
            self.assertEqual(resumed.metadata["latest_implement_artifact"]["deliverable_refs"], [])

    def test_codex_runtime_writes_bundle_deliverable_refs_for_acceptance(self) -> None:
        provider = _RecordingCodexProvider()
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp) / "工作区" / "Butler" / "deliveries" / "background_tasks" / "demo"
            service = CampaignDomainService(tmp, codex_provider=provider)
            created = service.create_campaign(
                {
                    "top_level_goal": "Write codex implementation deliverables into the fixed bundle area",
                    "workspace_root": tmp,
                    "repo_root": tmp,
                    "metadata": {
                        "campaign_runtime": {"mode": "codex"},
                        "strict_acceptance_required": True,
                        "pending_correctness_checks": [],
                        "bundle_root": str(bundle_root),
                        "bundle_manifest": str(bundle_root / "manifest.json"),
                        "reviewer_decision_sequence": ["converge"],
                    },
                },
                mission_id="mission_demo",
                supervisor_session_id="workflow_session_demo",
            )

            resumed = service.resume_campaign(created.campaign_id)

            latest_artifact = dict(resumed.metadata["latest_implement_artifact"])
            self.assertFalse(bool(latest_artifact.get("placeholder")))
            self.assertTrue(latest_artifact["deliverable_refs"])
            deliverable_path = Path(latest_artifact["deliverable_refs"][0])
            self.assertTrue(deliverable_path.exists())
            self.assertIn("implement_iteration_01.md", deliverable_path.name)
            self.assertEqual(resumed.metadata["latest_acceptance_blockers"], [])


if __name__ == "__main__":
    unittest.main()
