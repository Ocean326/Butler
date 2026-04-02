from __future__ import annotations

try:
    from .interfaces.observe import build_parser, main
except ModuleNotFoundError:  # pragma: no cover - direct script/import fallback
    from butler_main.orchestrator.interfaces.observe import build_parser, main

__all__ = ["build_parser", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
