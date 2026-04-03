from __future__ import annotations

import sys
from pathlib import Path


def _workspace_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "butler_main").exists():
            return parent
    raise SystemExit("workspace root not found")


ROOT = _workspace_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from butler_main.sources.skills.shared.upstream_source_runtime import main


if __name__ == "__main__":
    raise SystemExit(main(source_id="praw-reddit-ingest"))
