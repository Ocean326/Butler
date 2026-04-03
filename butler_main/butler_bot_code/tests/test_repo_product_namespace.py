from __future__ import annotations

import importlib
from pathlib import Path


def test_products_chat_alias_preserves_exports_and_submodules() -> None:
    canonical = importlib.import_module("butler_main.products.chat")
    legacy = importlib.import_module("butler_main.chat")
    canonical_bootstrap = importlib.import_module("butler_main.products.chat.cli.bootstrap")

    assert canonical.ChatApp is legacy.ChatApp
    assert canonical_bootstrap.__file__ is not None
    assert canonical_bootstrap.__file__.endswith("butler_main/chat/cli/bootstrap.py")


def test_butler_flow_move_keeps_legacy_entry_and_canonical_entry() -> None:
    canonical = importlib.import_module("butler_main.products.butler_flow")
    legacy = importlib.import_module("butler_main.butler_flow")
    legacy_cli = importlib.import_module("butler_main.butler_flow.cli")

    assert canonical.FlowApp is legacy.FlowApp
    assert canonical.main is legacy.main
    assert legacy_cli.__file__ is not None
    assert legacy_cli.__file__.endswith("butler_main/products/butler_flow/cli.py")


def test_platform_and_compat_alias_packages_resolve_expected_targets() -> None:
    runtime = importlib.import_module("butler_main.platform.runtime")
    process_runtime = importlib.import_module("butler_main.platform.runtime.process_runtime")
    compat_agents = importlib.import_module("butler_main.compat.agents_os")
    orchestrator = importlib.import_module("butler_main.products.campaign_orchestrator.orchestrator")

    assert hasattr(runtime, "agent_runtime")
    assert process_runtime.__file__ is not None
    assert Path(str(process_runtime.__file__)).as_posix().endswith("butler_main/runtime_os/process_runtime/__init__.py")
    assert compat_agents.__path__[0].endswith("butler_main/agents_os")
    assert orchestrator.OrchestratorService.__name__ == "OrchestratorService"
