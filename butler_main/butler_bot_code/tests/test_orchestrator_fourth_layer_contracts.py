from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
ORCHESTRATOR_ROOT = REPO_ROOT / "butler_main" / "orchestrator"
from butler_main.orchestrator.fourth_layer_contracts import (  # noqa: E402
    FOURTH_LAYER_FORBIDDEN_DIRECT_IMPORTS,
    FOURTH_LAYER_PORT_NAMESPACE,
    FOURTH_LAYER_PORTS,
    FOURTH_LAYER_STABLE_EVIDENCE_KEYS,
    build_fourth_layer_contract_manifest,
    build_stable_evidence,
)
FOURTH_LAYER_ENTRYPOINTS = (
    ORCHESTRATOR_ROOT / "query_service.py",
    ORCHESTRATOR_ROOT / "ingress_service.py",
    ORCHESTRATOR_ROOT / "mission_orchestrator.py",
    ORCHESTRATOR_ROOT / "observe.py",
    ORCHESTRATOR_ROOT / "runner.py",
)
TEMPORARY_ALLOWED_IMPORTS = {
    ("butler_main.orchestrator.runner", "butler_main.orchestrator.workflow_vm"),
    ("butler_main.orchestrator.interfaces.runner", "butler_main.orchestrator.workflow_vm"),
}


def _module_name_from_path(path: Path) -> str:
    relative = path.relative_to(REPO_ROOT).with_suffix("")
    return ".".join(relative.parts)


def _resolve_import_name(module_name: str, node: ast.ImportFrom) -> str:
    imported = str(node.module or "").strip()
    if node.level <= 0:
        return imported
    parts = module_name.split(".")
    base_parts = parts[:-node.level]
    if imported:
        return ".".join([*base_parts, imported])
    return ".".join(base_parts)


def _matches_forbidden(import_name: str) -> bool:
    return any(
        import_name == forbidden or import_name.startswith(f"{forbidden}.")
        for forbidden in FOURTH_LAYER_FORBIDDEN_DIRECT_IMPORTS
    )


def _collect_forbidden_imports(path: Path) -> list[tuple[str, str]]:
    module_name = _module_name_from_path(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported = str(alias.name or "").strip()
                if imported and _matches_forbidden(imported):
                    violations.append((module_name, imported))
        elif isinstance(node, ast.ImportFrom):
            imported = _resolve_import_name(module_name, node)
            if imported and _matches_forbidden(imported):
                violations.append((module_name, imported))
    return violations


class FourthLayerContractTests(unittest.TestCase):
    def test_contract_manifest_is_stable(self) -> None:
        manifest = build_fourth_layer_contract_manifest()
        self.assertEqual(manifest["port_namespace"], FOURTH_LAYER_PORT_NAMESPACE)
        self.assertEqual(manifest["ports"], list(FOURTH_LAYER_PORTS))
        self.assertEqual(manifest["stable_evidence_keys"], list(FOURTH_LAYER_STABLE_EVIDENCE_KEYS))
        self.assertEqual(manifest["forbidden_direct_imports"], list(FOURTH_LAYER_FORBIDDEN_DIRECT_IMPORTS))

    def test_fourth_layer_entrypoints_do_not_grow_new_forbidden_imports(self) -> None:
        violations: list[tuple[str, str]] = []
        for path in FOURTH_LAYER_ENTRYPOINTS:
            if path.exists():
                violations.extend(_collect_forbidden_imports(path))

        interfaces_dir = ORCHESTRATOR_ROOT / "interfaces"
        if interfaces_dir.exists():
            for path in interfaces_dir.glob("*.py"):
                if path.name == "__init__.py":
                    continue
                violations.extend(_collect_forbidden_imports(path))

        unexpected = [
            item
            for item in violations
            if item not in TEMPORARY_ALLOWED_IMPORTS
        ]
        self.assertEqual(unexpected, [])
        self.assertLessEqual(len(violations), len(TEMPORARY_ALLOWED_IMPORTS))

    def test_stable_evidence_falls_back_to_recent_execution_refs_when_idle(self) -> None:
        payload = build_stable_evidence(
            closure_signals={
                "workflow_ir_compiled_visible": True,
                "workflow_vm_executed_visible": True,
                "workflow_session_count": 1,
            },
            missions=[
                {
                    "mission_id": "mission_idle",
                    "title": "idle mission",
                    "status": "completed",
                    "workflow_session_count": 1,
                }
            ],
            active_branches=[],
            recent_events=[
                {
                    "event_type": "branch_completed",
                    "branch_id": "branch_idle",
                    "payload": {
                        "result_payload": {
                            "workflow_ir": {
                                "workflow_id": "workflow_idle",
                                "workflow_session_id": "workflow_session_idle",
                            }
                        }
                    },
                }
            ],
        )

        self.assertEqual(payload["mission_id"], "mission_idle")
        self.assertEqual(payload["branch_id"], "branch_idle")
        self.assertEqual(payload["workflow_id"], "workflow_idle")
        self.assertEqual(payload["workflow_session_id"], "workflow_session_idle")
        self.assertEqual(payload["workflow_session_count"], 1)
        self.assertTrue(payload["workflow_ir_compiled"])
        self.assertTrue(payload["workflow_vm_executed"])


if __name__ == "__main__":
    unittest.main()
