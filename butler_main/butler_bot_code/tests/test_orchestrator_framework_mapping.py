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

from butler_main.orchestrator import (  # noqa: E402
    FrameworkMappingBundle,
    FrameworkMappingRegistry,
    FrameworkMappingSpec,
    get_builtin_framework_mapping_bundle,
    get_builtin_framework_mapping_spec,
    load_framework_compiler_inputs,
    load_builtin_framework_mapping_registry,
    load_framework_mapping_bundle,
)


class OrchestratorFrameworkMappingTests(unittest.TestCase):
    def test_builtin_framework_mapping_registry_loads_required_specs(self) -> None:
        registry = load_builtin_framework_mapping_registry()

        self.assertIsInstance(registry, FrameworkMappingRegistry)
        self.assertEqual(
            set(registry.list_framework_ids()),
            {
                "superpowers",
                "gstack",
                "openfang",
                "langgraph",
                "openai_agents_sdk",
                "autogen",
                "crewai",
                "metagpt",
                "openhands",
                "temporal",
            },
        )

    def test_framework_mapping_round_trip_preserves_openfang_shape(self) -> None:
        spec = get_builtin_framework_mapping_spec("openfang")

        self.assertIsNotNone(spec)
        assert spec is not None
        cloned = FrameworkMappingSpec.from_dict(spec.to_dict())

        self.assertEqual(cloned.to_dict(), spec.to_dict())
        self.assertEqual(cloned.runtime_binding_hints["host_kind"], "background_runtime")
        self.assertEqual(cloned.compiler_profile_templates[0]["capability_package_ref"], "pkg.cap.autonomous.research")

    def test_openfang_is_not_mapped_to_product_shell(self) -> None:
        bundle = load_framework_mapping_bundle("openfang")

        self.assertIsInstance(bundle, FrameworkMappingBundle)
        self.assertEqual(bundle.entry.source_kind, "agent_os")
        self.assertTrue(any(item["package_kind"] == "capability_package" for item in bundle.mapping.absorbed_packages))
        self.assertTrue(any(item["package_kind"] == "governance_policy_package" for item in bundle.mapping.absorbed_packages))
        self.assertFalse(any(item["package_kind"] == "product_shell" for item in bundle.mapping.absorbed_packages))
        self.assertFalse(any(item["butler_layer"] == "Product Entry / Interface Surface" for item in bundle.mapping.butler_targets))

    def test_mapping_bundle_can_be_loaded_via_package_api(self) -> None:
        bundle = get_builtin_framework_mapping_bundle("gstack")

        self.assertIsNotNone(bundle)
        assert bundle is not None
        self.assertEqual(bundle.mapping.framework_id, "gstack")
        self.assertEqual(bundle.mapping.compiler_profile_templates[0]["workflow_kind"], "software_factory")

    def test_registry_supports_lane_b_queries(self) -> None:
        registry = load_builtin_framework_mapping_registry()

        runtime_specs = registry.find_specs_for_target_kind("runtime_binding")
        governance_specs = registry.find_specs_for_butler_layer("Governance / Observability Plane")

        self.assertTrue(any(item.framework_id == "temporal" for item in runtime_specs))
        self.assertTrue(any(item.framework_id == "openfang" for item in governance_specs))
        self.assertEqual(
            registry.compiler_profile_templates_for("langgraph")[0]["workflow_kind"],
            "graph_governed",
        )

    def test_compiler_inputs_loader_returns_lane_b_ready_payload(self) -> None:
        payload = load_framework_compiler_inputs("openai_agents_sdk")

        self.assertEqual(payload["framework_id"], "openai_agents_sdk")
        self.assertEqual(payload["source_kind"], "agent_sdk")
        self.assertTrue(payload["runtime_binding_hints"]["supports_tracing"])
        self.assertEqual(
            payload["compiler_profile_templates"][0]["template_id"],
            "framework.openai_agents_sdk.handoff_guardrail",
        )


if __name__ == "__main__":
    unittest.main()
