"""Curated agent-runtime export surface for the runtime_os migration."""

from __future__ import annotations

from importlib import import_module
from importlib.util import find_spec
from typing import Any


_SOURCE_MODULES = (
    ("agents_os.contracts", "butler_main.agents_os.contracts"),
    ("agents_os.context", "butler_main.agents_os.context"),
    ("agents_os.execution", "butler_main.agents_os.execution"),
    ("agents_os.factory", "butler_main.agents_os.factory"),
    ("agents_os.state", "butler_main.agents_os.state"),
    ("agents_os.skills", "butler_main.agents_os.skills"),
    ("agents_os.runtime", "butler_main.agents_os.runtime"),
)

_MODULE_ALIASES = {
    "cli_runner": ("agents_os.execution.cli_runner", "butler_main.agents_os.execution.cli_runner"),
    "codex_cursor_switchover": ("agents_os.execution.codex_cursor_switchover", "butler_main.agents_os.execution.codex_cursor_switchover"),
    "cursor_cli_support": ("agents_os.execution.cursor_cli_support", "butler_main.agents_os.execution.cursor_cli_support"),
    "provider_failover": ("agents_os.execution.provider_failover", "butler_main.agents_os.execution.provider_failover"),
    "runtime_logging": ("agents_os.execution.logging", "butler_main.agents_os.execution.logging"),
    "runtime_policy": ("agents_os.execution.runtime_policy", "butler_main.agents_os.execution.runtime_policy"),
    "butler_flow_prompts": ("butler_flow.prompts", "butler_main.butler_flow.prompts"),
    "butler_flow": ("butler_flow", "butler_main.butler_flow"),
}

_PROCESS_EXPORTS = {
    "AcceptanceReceipt",
    "EDGE_KINDS",
    "ExecutionReceipt",
    "ExecutionRuntime",
    "FileSessionCheckpointStore",
    "FileWorkflowCheckpointStore",
    "PROCESS_ROLES",
    "RuntimeSessionCheckpoint",
    "STEP_KINDS",
    "StepResult",
    "SubworkflowCapability",
    "WorkflowCheckpoint",
    "WorkflowCursor",
    "WorkflowEdgeSpec",
    "WorkflowReceipt",
    "WorkflowRunProjection",
    "WorkflowSpec",
    "WorkflowStepSpec",
    "merge_session_snapshots",
    "normalize_edge_kind",
    "normalize_failure_class",
    "normalize_process_role",
    "normalize_step_kind",
}


def _import_legacy_module(*candidates: str):
    for name in candidates:
        try:
            return import_module(name)
        except ModuleNotFoundError:
            try:
                spec = find_spec(name)
            except ModuleNotFoundError:
                spec = None
            if spec is not None:
                raise
    raise ModuleNotFoundError(f"unable to import any legacy module from {candidates!r}")


def _public_names(module: object) -> list[str]:
    exported = getattr(module, "__all__", None)
    if exported is not None:
        return [name for name in exported if not str(name).startswith("_")]
    return [name for name in dir(module) if not str(name).startswith("_")]


def _build_exports() -> dict[str, tuple[tuple[str, ...], str | None]]:
    exports: dict[str, tuple[tuple[str, ...], str | None]] = {}
    for name, module_candidates in _MODULE_ALIASES.items():
        exports[name] = (module_candidates, None)
    for module_candidates in _SOURCE_MODULES:
        module = _import_legacy_module(*module_candidates)
        for name in _public_names(module):
            if name in _PROCESS_EXPORTS:
                continue
            exports.setdefault(name, (module_candidates, name))
    return exports


_EXPORTS = _build_exports()
__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_candidates, attribute_name = target
    module = _import_legacy_module(*module_candidates)
    value = module if attribute_name is None else getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
