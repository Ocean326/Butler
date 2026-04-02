from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
import uuid


TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parents[2]
TMP_ROOT = PROJECT_ROOT / "工作区" / "temp" / "pytest_runtime"
FALLBACK_TMP_ROOT = Path(tempfile.gettempdir()) / "butler_pytest_runtime"

TMP_ROOT.mkdir(parents=True, exist_ok=True)
FALLBACK_TMP_ROOT.mkdir(parents=True, exist_ok=True)

for key in ("TMP", "TEMP", "TMPDIR"):
    os.environ[key] = str(TMP_ROOT)

tempfile.tempdir = str(TMP_ROOT)


def _workspace_mkdtemp(*, prefix: str = "tmp", suffix: str = "", dir: str | None = None) -> str:
    bases = [Path(dir)] if dir else [TMP_ROOT, FALLBACK_TMP_ROOT]
    for base in bases:
        try:
            base.mkdir(parents=True, exist_ok=True)
        except Exception:
            continue
        while True:
            candidate = base / f"{prefix}{uuid.uuid4().hex[:8]}{suffix}"
            try:
                candidate.mkdir(parents=True, exist_ok=False)
                return str(candidate)
            except FileExistsError:
                continue
            except PermissionError:
                break
    raise PermissionError(f"unable to create temp directory under: {[str(item) for item in bases]}")


class _WorkspaceTemporaryDirectory:
    def __init__(self, suffix: str | None = None, prefix: str | None = None, dir: str | None = None, ignore_cleanup_errors: bool = True):
        self.name = _workspace_mkdtemp(
            prefix=prefix or "tmp",
            suffix=suffix or "",
            dir=dir,
        )
        self._ignore_cleanup_errors = ignore_cleanup_errors

    def __enter__(self) -> str:
        return self.name

    def cleanup(self) -> None:
        shutil.rmtree(self.name, ignore_errors=self._ignore_cleanup_errors)

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()


tempfile.mkdtemp = _workspace_mkdtemp
tempfile.TemporaryDirectory = _WorkspaceTemporaryDirectory
