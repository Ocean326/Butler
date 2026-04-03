from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path


DEFAULT_MAIN_BRANCHES = ("main", "master")
SYSTEM_LAYER_AREAS = {
    "control-plane",
    "process-runtime",
    "frontdoor",
    "butler-flow",
    "agent-runtime",
}
LIGHT_ONLY_AREAS = {
    "agent-protocol",
    "docs-governance",
    "docs-daily",
    "docs",
    "tools",
    "tests",
    "repo-root",
}
AREA_PREFIXES: tuple[tuple[str, str], ...] = (
    ("AGENTS.md", "agent-protocol"),
    ("docs/project-map/", "docs-governance"),
    ("docs/README.md", "docs-governance"),
    ("docs/daily-upgrade/", "docs-daily"),
    ("docs/", "docs"),
    ("tools/", "tools"),
    ("butler_main/products/campaign_orchestrator/", "control-plane"),
    ("butler_main/orchestrator/", "control-plane"),
    ("butler_main/domains/campaign/", "control-plane"),
    ("butler_main/platform/runtime/", "process-runtime"),
    ("butler_main/compat/runtime_os/", "process-runtime"),
    ("butler_main/runtime_os/", "process-runtime"),
    ("runtime_os/", "process-runtime"),
    ("butler_main/products/chat/", "frontdoor"),
    ("butler_main/chat/", "frontdoor"),
    ("butler_main/products/butler_flow/", "butler-flow"),
    ("butler_main/butler_flow/", "butler-flow"),
    ("butler_main/compat/agents_os/", "agent-runtime"),
    ("butler_main/compat/multi_agents_os/", "agent-runtime"),
    ("butler_main/agents_os/", "agent-runtime"),
    ("butler_main/multi_agents_os/", "agent-runtime"),
    ("butler_main/butler_bot_code/tests/", "tests"),
    ("butler_main/platform/host_runtime/", "butler-bot"),
    ("butler_main/butler_bot_code/", "butler-bot"),
    ("butler_main/platform/skills/", "agent-runtime"),
    ("butler_main/incubation/research/", "research"),
    ("butler_main/research/", "research"),
    ("README.md", "repo-root"),
    (".gitignore", "repo-root"),
    ("pytest.ini", "repo-root"),
)
IGNORED_PATH_GLOBS: tuple[str, ...] = (
    "author-year-titlekey",
    "normalized",
    "butler_main/butler_bot_code/assets/flows/manage_audit.jsonl",
    "butler_main/butler_bot_code/assets/flows/instances/**",
)


@dataclass(slots=True)
class CloseAnalysis:
    clean: bool
    repo_root: str
    current_branch: str
    default_branch: str
    remote_name: str
    changed_paths: list[str]
    path_count: int
    matched_layers: list[str]
    matched_features: list[str]
    change_level: str
    doc_mode: str
    doc_targets: list[str]
    requires_worktree: bool
    requires_push: bool
    suggested_commit_type: str
    suggested_branch: str
    suggested_worktree: str
    suggested_summary: str


@dataclass(slots=True)
class ApplyResult:
    repo_root: str
    analysis: dict[str, object]
    actions: list[str]
    branch_before: str
    branch_after: str
    commit_branch: str
    commit_message: str
    commit_created: bool
    commit_sha: str
    pushed: bool
    push_remote: str
    worktree_created: bool
    worktree_path: str


def _run_git(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "core.quotepath=off", *args],
        cwd=str(repo_root),
        check=check,
        text=True,
        capture_output=True,
    )


def _repo_root(explicit_root: str | None = None) -> Path:
    cwd = Path(explicit_root).resolve() if explicit_root else Path.cwd()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(cwd),
        check=True,
        text=True,
        capture_output=True,
    )
    return Path(result.stdout.strip()).resolve()


def _current_branch(repo_root: Path) -> str:
    result = _run_git(repo_root, "branch", "--show-current")
    return result.stdout.strip() or "HEAD"


def _default_branch(repo_root: Path) -> str:
    result = _run_git(repo_root, "for-each-ref", "refs/heads", "--format=%(refname:short)")
    branches = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    for candidate in DEFAULT_MAIN_BRANCHES:
        if candidate in branches:
            return candidate
    current = _current_branch(repo_root)
    return current if current else (branches[0] if branches else "main")


def _remote_name(repo_root: Path) -> str:
    result = _run_git(repo_root, "remote", check=False)
    remotes = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if "origin" in remotes:
        return "origin"
    return remotes[0] if remotes else ""


def _changed_paths(repo_root: Path) -> list[str]:
    changed: set[str] = set()
    for args in (
        ("diff", "--name-only", "--relative"),
        ("diff", "--cached", "--name-only", "--relative"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        result = _run_git(repo_root, *args, check=False)
        for line in result.stdout.splitlines():
            path = line.strip()
            if path:
                changed.add(path)
    return sorted(path for path in changed if not _is_ignored_path(path))


def _is_ignored_path(path: str) -> bool:
    normalized = path.strip().strip('"')
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in IGNORED_PATH_GLOBS)


def _classify_path(path: str) -> str:
    for prefix, area in AREA_PREFIXES:
        if path == prefix or path.startswith(prefix):
            return area
    return "misc"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "mixed-change"


def _humanize_slug(text: str) -> str:
    return re.sub(r"[-_]+", " ", text).strip() or "mixed change"


def _topic_slug(topic: str | None, matched_features: list[str]) -> str:
    if topic:
        return _slugify(topic)
    for area in matched_features:
        if area not in {"docs", "docs-daily", "docs-governance", "tests", "repo-root"}:
            return _slugify(area)
    return "mixed-change"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def analyze_repo(
    repo_root: Path,
    *,
    topic: str | None = None,
    planned: bool = False,
    today: date | None = None,
) -> CloseAnalysis:
    changed_paths = _changed_paths(repo_root)
    current_branch = _current_branch(repo_root)
    default_branch = _default_branch(repo_root)
    remote_name = _remote_name(repo_root)
    if not changed_paths:
        return CloseAnalysis(
            clean=True,
            repo_root=str(repo_root),
            current_branch=current_branch,
            default_branch=default_branch,
            remote_name=remote_name,
            changed_paths=[],
            path_count=0,
            matched_layers=[],
            matched_features=[],
            change_level="clean",
            doc_mode="none",
            doc_targets=[],
            requires_worktree=False,
            requires_push=False,
            suggested_commit_type="chore",
            suggested_branch=f"chore/{_topic_slug(topic, [])}",
            suggested_worktree="",
            suggested_summary="repository already clean",
        )

    matched_features = _dedupe([_classify_path(path) for path in changed_paths])
    matched_layers = sorted(area for area in matched_features if area in SYSTEM_LAYER_AREAS)
    docs_changed = any(
        path == "AGENTS.md"
        or path == "README.md"
        or path.startswith("docs/")
        or path == "tools/README.md"
        for path in changed_paths
    )
    doc_governance_changed = any(area in {"agent-protocol", "docs-governance", "docs-daily"} for area in matched_features)
    tool_changed = "tools" in matched_features
    code_changed = any(
        path.startswith("butler_main/")
        or path.startswith("runtime_os/")
        or path.startswith("tools/")
        for path in changed_paths
    )
    tests_only = all(path.startswith("butler_main/butler_bot_code/tests/") for path in changed_paths)
    only_light_areas = all(area in LIGHT_ONLY_AREAS for area in matched_features)

    if len(matched_layers) >= 2:
        change_level = "system"
    elif planned and (doc_governance_changed or len(matched_layers) >= 1 or tool_changed):
        change_level = "system"
    elif doc_governance_changed and (tool_changed or len(matched_layers) >= 1):
        change_level = "system"
    elif tests_only or (only_light_areas and len(changed_paths) <= 8 and not planned):
        change_level = "light"
    else:
        change_level = "normal"

    doc_mode = "strict" if change_level == "system" else ("minimal" if (docs_changed or code_changed) else "none")
    effective_today = today or date.today()
    mmdd = effective_today.strftime("%m%d")
    doc_targets: list[str] = []
    if doc_mode != "none":
        doc_targets.append(f"docs/daily-upgrade/{mmdd}/00_当日总纲.md")
        if code_changed or tool_changed or planned:
            doc_targets.append(f"docs/daily-upgrade/{mmdd}/专题正文（沿用现有专题或补新专题）")
    if change_level == "system":
        doc_targets.extend(
            [
                "docs/project-map/03_truth_matrix.md",
                "docs/project-map/04_change_packets.md",
                "docs/README.md",
            ]
        )
    doc_targets = _dedupe(doc_targets)

    topic_slug = _topic_slug(topic, matched_features)
    if tests_only:
        commit_type = "test"
    elif only_light_areas and not matched_layers:
        commit_type = "chore"
    else:
        commit_type = "feat"
    branch_prefix = commit_type if commit_type in {"feat", "fix", "refactor", "chore", "test"} else "chore"
    suggested_branch = f"{branch_prefix}/{topic_slug}"
    suggested_summary = _humanize_slug(topic_slug)
    suggested_worktree = ""
    if change_level == "system":
        suggested_worktree = str((repo_root.parent / f"{repo_root.name}-wt" / f"{effective_today.isoformat()}-{topic_slug}").resolve())

    return CloseAnalysis(
        clean=False,
        repo_root=str(repo_root),
        current_branch=current_branch,
        default_branch=default_branch,
        remote_name=remote_name,
        changed_paths=changed_paths,
        path_count=len(changed_paths),
        matched_layers=matched_layers,
        matched_features=matched_features,
        change_level=change_level,
        doc_mode=doc_mode,
        doc_targets=doc_targets,
        requires_worktree=change_level == "system",
        requires_push=bool(remote_name) and change_level != "light",
        suggested_commit_type=commit_type,
        suggested_branch=suggested_branch,
        suggested_worktree=suggested_worktree,
        suggested_summary=suggested_summary,
    )


def _git_has_staged_changes(repo_root: Path) -> bool:
    result = _run_git(repo_root, "diff", "--cached", "--quiet", check=False)
    return result.returncode != 0


def _branch_exists(repo_root: Path, branch_name: str) -> bool:
    result = _run_git(repo_root, "show-ref", "--verify", f"refs/heads/{branch_name}", check=False)
    return result.returncode == 0


def _safe_worktree_path(target: Path) -> Path:
    if not target.exists():
        return target
    parent = target.parent
    stem = target.name
    for index in range(2, 100):
        candidate = parent / f"{stem}-{index}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"unable to allocate worktree path under {parent}")


def apply_closeout(
    repo_root: Path,
    *,
    topic: str | None = None,
    summary: str | None = None,
    commit_type: str | None = None,
    push: bool | None = None,
    planned: bool = False,
) -> ApplyResult:
    analysis = analyze_repo(repo_root, topic=topic, planned=planned)
    if analysis.clean:
        return ApplyResult(
            repo_root=str(repo_root),
            analysis=asdict(analysis),
            actions=["repository already clean"],
            branch_before=analysis.current_branch,
            branch_after=analysis.current_branch,
            commit_branch=analysis.current_branch,
            commit_message="",
            commit_created=False,
            commit_sha="",
            pushed=False,
            push_remote=analysis.remote_name,
            worktree_created=False,
            worktree_path="",
        )

    desired_push = analysis.requires_push if push is None else push
    branch_before = analysis.current_branch
    commit_branch = branch_before
    actions: list[str] = []
    branch_created = False

    if analysis.requires_worktree and branch_before == analysis.default_branch:
        commit_branch = analysis.suggested_branch
        if _branch_exists(repo_root, commit_branch):
            _run_git(repo_root, "switch", commit_branch)
            actions.append(f"switched to existing branch {commit_branch}")
        else:
            _run_git(repo_root, "switch", "-c", commit_branch)
            actions.append(f"created branch {commit_branch}")
        branch_created = True

    effective_commit_type = commit_type or analysis.suggested_commit_type
    effective_summary = (summary or analysis.suggested_summary).strip()
    commit_message = f"{effective_commit_type}: {effective_summary}"

    _run_git(repo_root, "add", "-A", "--", *analysis.changed_paths)
    if not _git_has_staged_changes(repo_root):
        return ApplyResult(
            repo_root=str(repo_root),
            analysis=asdict(analysis),
            actions=actions + ["nothing staged after git add -A"],
            branch_before=branch_before,
            branch_after=_current_branch(repo_root),
            commit_branch=_current_branch(repo_root),
            commit_message=commit_message,
            commit_created=False,
            commit_sha="",
            pushed=False,
            push_remote=analysis.remote_name,
            worktree_created=False,
            worktree_path="",
        )

    _run_git(repo_root, "commit", "-m", commit_message)
    commit_sha = _run_git(repo_root, "rev-parse", "HEAD").stdout.strip()
    actions.append(f"committed {commit_sha}")

    pushed = False
    if desired_push and analysis.remote_name:
        _run_git(repo_root, "push", "-u", analysis.remote_name, commit_branch)
        pushed = True
        actions.append(f"pushed to {analysis.remote_name}/{commit_branch}")
    elif desired_push and not analysis.remote_name:
        actions.append("push skipped: no git remote configured")

    branch_after = _current_branch(repo_root)
    worktree_path = ""
    worktree_created = False
    if analysis.requires_worktree and branch_created and analysis.suggested_worktree:
        target = _safe_worktree_path(Path(analysis.suggested_worktree))
        target.parent.mkdir(parents=True, exist_ok=True)
        _run_git(repo_root, "switch", analysis.default_branch)
        _run_git(repo_root, "worktree", "add", str(target), commit_branch)
        branch_after = _current_branch(repo_root)
        worktree_path = str(target)
        worktree_created = True
        actions.append(f"created worktree {worktree_path}")

    return ApplyResult(
        repo_root=str(repo_root),
        analysis=asdict(analysis),
        actions=actions,
        branch_before=branch_before,
        branch_after=branch_after,
        commit_branch=commit_branch,
        commit_message=commit_message,
        commit_created=True,
        commit_sha=commit_sha,
        pushed=pushed,
        push_remote=analysis.remote_name,
        worktree_created=worktree_created,
        worktree_path=worktree_path,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Butler vibe-close helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="Inspect git changes and suggest closeout actions")
    analyze_parser.add_argument("--topic", default="", help="short topic slug seed")
    analyze_parser.add_argument("--planned", action="store_true", help="mark the task as plan-driven / important")
    analyze_parser.add_argument("--repo-root", default="", help="override repository root")

    apply_parser = subparsers.add_parser("apply", help="Apply the suggested git closeout actions")
    apply_parser.add_argument("--topic", default="", help="short topic slug seed")
    apply_parser.add_argument("--summary", default="", help="commit summary after the prefix")
    apply_parser.add_argument(
        "--commit-type",
        choices=("feat", "fix", "refactor", "chore", "test"),
        default="",
        help="override commit type",
    )
    apply_parser.add_argument("--planned", action="store_true", help="mark the task as plan-driven / important")
    apply_parser.add_argument("--push", dest="push", action="store_true", default=None, help="force push after commit")
    apply_parser.add_argument("--no-push", dest="push", action="store_false", help="disable push after commit")
    apply_parser.add_argument("--repo-root", default="", help="override repository root")

    prompt_parser = subparsers.add_parser("print-prompt", help="Print the standard agent closeout prompt")
    prompt_parser.add_argument("--topic", default="", help="short topic slug seed")
    prompt_parser.add_argument("--planned", action="store_true", help="mark the task as plan-driven / important")
    prompt_parser.add_argument("--repo-root", default="", help="override repository root")
    return parser


def _print_json(payload: dict[str, object]) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.flush()
    return 0


def _print_prompt(repo_root: Path, *, topic: str | None, planned: bool) -> int:
    analysis = analyze_repo(repo_root, topic=topic, planned=planned)
    topic_hint = topic or "<topic-slug>"
    summary_hint = analysis.suggested_summary if not analysis.clean else "<imperative summary>"
    prompt = f"""Butler vibe closeout protocol

1. Run `./tools/vibe-close analyze{' --planned' if planned else ''}{f' --topic {topic_hint}' if topic else ''}` and read the JSON.
2. Update the required docs in `doc_targets`; keep `minimal` vs `strict` doc mode unchanged.
3. Run focused tests for the changed area.
4. Run `./tools/vibe-close apply{' --planned' if planned else ''} --topic {topic_hint} --summary "{summary_hint}"`.
5. In the final handoff, report:
   - `change_level`
   - updated docs
   - tests executed
   - commit SHA / branch / worktree / push result

Current analysis snapshot:
{json.dumps(asdict(analysis), ensure_ascii=False, indent=2)}
"""
    sys.stdout.write(prompt)
    if not prompt.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = _repo_root(getattr(args, "repo_root", "") or None)
    topic = (getattr(args, "topic", "") or "").strip()
    planned = bool(getattr(args, "planned", False))

    if args.command == "analyze":
        return _print_json(asdict(analyze_repo(repo_root, topic=topic or None, planned=planned)))
    if args.command == "apply":
        result = apply_closeout(
            repo_root,
            topic=topic or None,
            summary=(getattr(args, "summary", "") or "").strip() or None,
            commit_type=(getattr(args, "commit_type", "") or "").strip() or None,
            push=getattr(args, "push", None),
            planned=planned,
        )
        return _print_json(asdict(result))
    if args.command == "print-prompt":
        return _print_prompt(repo_root, topic=topic or None, planned=planned)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
