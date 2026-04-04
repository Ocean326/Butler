from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from butler_main.runtime_os import agent_runtime, process_runtime


AGENT_EXPORTS = set(getattr(agent_runtime, "__all__", ()))
PROCESS_EXPORTS = set(getattr(process_runtime, "__all__", ()))

AGENT_PREFIXES = (
    "agents_os.contracts",
    "agents_os.context",
    "agents_os.execution",
    "agents_os.factory",
    "agents_os.state",
    "agents_os.skills",
    "butler_main.agents_os.contracts",
    "butler_main.agents_os.context",
    "butler_main.agents_os.execution",
    "butler_main.agents_os.factory",
    "butler_main.agents_os.state",
    "butler_main.agents_os.skills",
)

PROCESS_PREFIXES = (
    "agents_os.governance",
    "agents_os.protocol",
    "agents_os.recovery",
    "agents_os.verification",
    "agents_os.workflow",
    "multi_agents_os",
    "butler_main.agents_os.governance",
    "butler_main.agents_os.protocol",
    "butler_main.agents_os.recovery",
    "butler_main.agents_os.verification",
    "butler_main.agents_os.workflow",
    "butler_main.multi_agents_os",
)

LEGACY_IMPORT_RE = re.compile(r"\b(?:butler_main\.)?(?:agents_os|multi_agents_os)\b")
PYTHON_SUFFIXES = {".py"}


@dataclass(slots=True)
class Edit:
    start: int
    end: int
    replacement: str


@dataclass(slots=True)
class FileReport:
    path: str
    rewrite_count: int
    remaining_legacy_hits: int
    changed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "rewrite_count": self.rewrite_count,
            "remaining_legacy_hits": self.remaining_legacy_hits,
            "changed": self.changed,
        }


@dataclass(slots=True)
class ScanSummary:
    mode: str
    files_scanned: int
    changed_files: int
    changed_imports: int
    remaining_files: int
    reports: list[FileReport]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "files_scanned": self.files_scanned,
            "changed_files": self.changed_files,
            "changed_imports": self.changed_imports,
            "remaining_files": self.remaining_files,
            "reports": [report.to_dict() for report in self.reports],
        }


def _arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Draft codemod for agents_os/multi_agents_os -> runtime_os imports."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["butler_main/products/chat", "butler_main/products/campaign_orchestrator/orchestrator", "butler_main/butler_bot_code/tests"],
        help="Files or directories to scan.",
    )
    parser.add_argument("--write", action="store_true", help="Apply safe import rewrites in place.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON summary.")
    parser.add_argument(
        "--fail-on-remaining",
        action="store_true",
        help="Exit with code 1 when legacy imports remain after the scan or rewrite.",
    )
    return parser


def _iter_python_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        path = (REPO_ROOT / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        if path.is_file() and path.suffix in PYTHON_SUFFIXES:
            if path not in seen:
                seen.add(path)
                files.append(path)
            continue
        if not path.exists():
            continue
        for child in path.rglob("*"):
            if child.is_file() and child.suffix in PYTHON_SUFFIXES and child not in seen:
                seen.add(child)
                files.append(child)
    return sorted(files)


def _offsets(source: str) -> list[int]:
    starts = [0]
    for line in source.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    return starts


def _slice(source: str, offsets: list[int], node: ast.AST) -> tuple[int, int]:
    start = offsets[node.lineno - 1] + node.col_offset
    end = offsets[node.end_lineno - 1] + node.end_col_offset
    return start, end


def _is_namespaced(module_name: str) -> bool:
    return module_name.startswith("butler_main.")


def _target_module(*, namespaced: bool, layer: str) -> str:
    prefix = "butler_main.runtime_os" if namespaced else "runtime_os"
    return f"{prefix}.{layer}"


def _classify_symbol(module_name: str, symbol_name: str) -> str | None:
    if module_name in PROCESS_PREFIXES or module_name.startswith("multi_agents_os.") or module_name.startswith("butler_main.multi_agents_os."):
        return "process_runtime"
    if module_name in AGENT_PREFIXES:
        return "agent_runtime"
    if module_name.startswith("agents_os.execution.") or module_name.startswith("butler_main.agents_os.execution."):
        return "agent_runtime"
    if module_name.startswith("agents_os.runtime") or module_name.startswith("butler_main.agents_os.runtime"):
        if symbol_name in AGENT_EXPORTS:
            return "agent_runtime"
        if symbol_name in PROCESS_EXPORTS:
            return "process_runtime"
        return None
    if module_name.startswith("agents_os.") or module_name.startswith("butler_main.agents_os."):
        if symbol_name in AGENT_EXPORTS:
            return "agent_runtime"
        if symbol_name in PROCESS_EXPORTS:
            return "process_runtime"
        return None
    return None


def _render_alias(alias: ast.alias) -> str:
    if alias.asname:
        return f"{alias.name} as {alias.asname}"
    return alias.name


def _rewrite_import_from(node: ast.ImportFrom) -> str | None:
    if node.level != 0 or not node.module:
        return None
    if not LEGACY_IMPORT_RE.search(node.module):
        return None
    if any(alias.name == "*" for alias in node.names):
        return None

    grouped: dict[str, list[str]] = {}
    for alias in node.names:
        layer = _classify_symbol(node.module, alias.name)
        if layer is None:
            return None
        target = _target_module(namespaced=_is_namespaced(node.module), layer=layer)
        grouped.setdefault(target, []).append(_render_alias(alias))

    return "\n".join(
        f"from {module_name} import {', '.join(imports)}"
        for module_name, imports in sorted(grouped.items())
    )


def _rewrite_import(node: ast.Import) -> str | None:
    rendered: list[str] = []
    for alias in node.names:
        module_name = alias.name
        if not LEGACY_IMPORT_RE.search(module_name):
            return None
        leaf = module_name.rsplit(".", 1)[-1]
        layer = _classify_symbol(module_name, leaf)
        if layer is None:
            return None
        target = _target_module(namespaced=_is_namespaced(module_name), layer=layer)
        binding = leaf
        if alias.asname:
            binding = f"{binding} as {alias.asname}"
        rendered.append(f"from {target} import {binding}")
    return "\n".join(rendered)


def _collect_edits(source: str) -> list[Edit]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    offsets = _offsets(source)
    edits: list[Edit] = []
    for node in ast.walk(tree):
        replacement = None
        if isinstance(node, ast.ImportFrom):
            replacement = _rewrite_import_from(node)
        elif isinstance(node, ast.Import):
            replacement = _rewrite_import(node)
        if not replacement:
            continue
        start, end = _slice(source, offsets, node)
        if source[start:end] == replacement:
            continue
        edits.append(Edit(start=start, end=end, replacement=replacement))
    return sorted(edits, key=lambda item: item.start, reverse=True)


def _apply_edits(source: str, edits: list[Edit]) -> str:
    updated = source
    for edit in edits:
        updated = updated[: edit.start] + edit.replacement + updated[edit.end :]
    return updated


def _remaining_legacy_hits(source: str) -> int:
    return len(LEGACY_IMPORT_RE.findall(source))


def _remaining_legacy_imports(source: str) -> int:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _remaining_legacy_hits(source)
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if LEGACY_IMPORT_RE.search(str(alias.name or "").strip()):
                    count += 1
        elif isinstance(node, ast.ImportFrom):
            module_name = str(node.module or "").strip()
            if module_name and LEGACY_IMPORT_RE.search(module_name):
                count += 1
    return count


def _display_path(path: Path) -> str:
    return str(path.resolve())


def scan_paths(paths: list[str], *, write: bool = False) -> ScanSummary:
    files = _iter_python_files(paths)
    reports: list[FileReport] = []
    changed_files = 0
    changed_imports = 0
    remaining_files = 0

    for path in files:
        source = path.read_text(encoding="utf-8")
        edits = _collect_edits(source)
        updated = _apply_edits(source, edits) if edits else source
        remaining_hits = _remaining_legacy_imports(updated)
        if write and edits:
            path.write_text(updated, encoding="utf-8")
        if edits:
            changed_files += 1
            changed_imports += len(edits)
        if remaining_hits:
            remaining_files += 1
        reports.append(
            FileReport(
                path=_display_path(path),
                rewrite_count=len(edits),
                remaining_legacy_hits=remaining_hits,
                changed=bool(edits),
            )
        )

    return ScanSummary(
        mode="write" if write else "dry-run",
        files_scanned=len(files),
        changed_files=changed_files,
        changed_imports=changed_imports,
        remaining_files=remaining_files,
        reports=reports,
    )


def main() -> int:
    args = _arg_parser().parse_args()
    summary = scan_paths(args.paths, write=args.write)

    if args.json:
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    else:
        verb = "rewrote" if args.write else "would rewrite"
        for report in summary.reports:
            if report.changed:
                print(f"{verb} {report.path} ({report.rewrite_count} imports)")
        print(
            "[runtime_os_codemod] "
            f"mode={summary.mode} files_scanned={summary.files_scanned} "
            f"files={summary.changed_files} imports={summary.changed_imports} "
            f"remaining_files={summary.remaining_files}"
        )
    if not args.write and summary.changed_files and not args.json:
        print("[runtime_os_codemod] rerun with --write to apply safe rewrites; remaining hits still need manual cleanup.")
    if args.fail_on_remaining and summary.remaining_files:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
