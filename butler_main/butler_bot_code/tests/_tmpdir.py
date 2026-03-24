from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
from uuid import uuid4


_ROOT = Path(__file__).resolve().parents[3] / "工作区" / "temp" / "pytest_runtime" / "unittest"


@contextmanager
def test_workdir(prefix: str):
    _ROOT.mkdir(parents=True, exist_ok=True)
    path = _ROOT / f"{prefix}_{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


test_workdir.__test__ = False
