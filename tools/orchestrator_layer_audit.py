from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_ROOT = REPO_ROOT / "butler_main" / "products" / "campaign_orchestrator" / "orchestrator"
APPLICATION_ROOT = ORCHESTRATOR_ROOT / "application"
INTERFACES_ROOT = ORCHESTRATOR_ROOT / "interfaces"

CONTROL_PLANE_TARGETS = {
    "service": "application/mission_service.py",
}

FOURTH_LAYER_TARGETS = {
    "query_service": "interfaces/query_service.py",
    "ingress_service": "interfaces/ingress_service.py",
    "mission_orchestrator": "interfaces/mission_orchestrator.py",
    "observe": "interfaces/observe.py",
    "runner": "interfaces/runner.py",
}

FORBIDDEN_INTERFACE_IMPORT_PREFIXES = (
    "butler_main.products.campaign_orchestrator.orchestrator.service",
    "butler_main.products.campaign_orchestrator.orchestrator.workflow_vm",
    "butler_main.products.campaign_orchestrator.orchestrator.workflow_ir",
    "butler_main.products.campaign_orchestrator.orchestrator.runtime_bridge.workflow_session_bridge",
    "butler_main.agents_os.process_runtime.session",
    "butler_main.agents_os.process_runtime.factory",
    "butler_main.multi_agents_os",
)
TEMPORARY_ALLOWED_INTERFACE_IMPORTS = {
    "butler_main.products.campaign_orchestrator.orchestrator.interfaces.runner:butler_main.products.campaign_orchestrator.orchestrator.workflow_vm",
}


@dataclass(slots=True)
class ModuleAudit:
    module: str
    root_exists: bool
    root_is_shell: bool
    target_exists: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "root_exists": self.root_exists,
            "root_is_shell": self.root_is_shell,
            "target_exists": self.target_exists,
        }


def _arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit orchestrator physical layering progress.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when expected layer targets are missing.")
    return parser


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
        for forbidden in FORBIDDEN_INTERFACE_IMPORT_PREFIXES
    )


def _collect_forbidden_imports(path: Path) -> list[str]:
    module_name = _module_name_from_path(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported = str(alias.name or "").strip()
                if imported and _matches_forbidden(imported):
                    violations.append(f"{module_name}:{imported}")
        elif isinstance(node, ast.ImportFrom):
            imported = _resolve_import_name(module_name, node)
            if imported and _matches_forbidden(imported):
                violations.append(f"{module_name}:{imported}")
    return violations


def _is_main_guard(node: ast.If) -> bool:
    test = node.test
    if not isinstance(test, ast.Compare):
        return False
    if not isinstance(test.left, ast.Name) or test.left.id != "__name__":
        return False
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    if len(test.comparators) != 1:
        return False
    comparator = test.comparators[0]
    return isinstance(comparator, ast.Constant) and comparator.value == "__main__"


def _file_is_shell(path: Path) -> bool:
    if not path.exists():
        return False
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return False
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Try):
            if all(isinstance(child, (ast.Import, ast.ImportFrom)) for child in node.body) and all(
                all(isinstance(child, (ast.Import, ast.ImportFrom)) for child in handler.body)
                for handler in node.handlers
            ):
                continue
            return False
        if isinstance(node, ast.Assign):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node, ast.If) and _is_main_guard(node):
            continue
        return False
    return True


def _audit_module(root_name: str, target_relative_path: str) -> ModuleAudit:
    root_path = ORCHESTRATOR_ROOT / f"{root_name}.py"
    target_path = ORCHESTRATOR_ROOT / Path(target_relative_path)
    return ModuleAudit(
        module=root_name,
        root_exists=root_path.exists(),
        root_is_shell=_file_is_shell(root_path),
        target_exists=target_path.exists(),
    )


def build_report() -> dict[str, Any]:
    interfaces_audits = [
        _audit_module(name, target)
        for name, target in sorted(FOURTH_LAYER_TARGETS.items())
    ]
    application_audits = [
        _audit_module(name, target)
        for name, target in sorted(CONTROL_PLANE_TARGETS.items())
    ]

    violations: list[str] = []
    if INTERFACES_ROOT.exists():
        for path in sorted(INTERFACES_ROOT.glob("*.py")):
            if path.name == "__init__.py":
                continue
            violations.extend(_collect_forbidden_imports(path))

    violations = [item for item in violations if item not in TEMPORARY_ALLOWED_INTERFACE_IMPORTS]

    return {
        "application_dir_exists": APPLICATION_ROOT.exists(),
        "interfaces_dir_exists": INTERFACES_ROOT.exists(),
        "application_modules": [item.to_dict() for item in application_audits],
        "interface_modules": [item.to_dict() for item in interfaces_audits],
        "forbidden_interface_import_violations": violations,
    }


def main() -> int:
    args = _arg_parser().parse_args()
    report = build_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.strict:
        return 0

    missing_targets = [
        item["module"]
        for item in report["application_modules"] + report["interface_modules"]
        if not item["target_exists"]
    ]
    if missing_targets or report["forbidden_interface_import_violations"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
