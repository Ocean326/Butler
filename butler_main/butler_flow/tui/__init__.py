from __future__ import annotations

from argparse import Namespace
from typing import Any, Callable

from .deps import textual_tui_support


def run_textual_flow_tui(
    *,
    run_prompt_receipt_fn: Callable[..., Any],
    args: Namespace,
    mode: str,
) -> int:
    from .app import ButlerFlowTuiApp

    app = ButlerFlowTuiApp(
        run_prompt_receipt_fn=run_prompt_receipt_fn,
        initial_args=args,
        initial_mode=str(mode or "launcher").strip() or "launcher",
    )
    return int(app.run() or 0)


__all__ = ["run_textual_flow_tui", "textual_tui_support"]
