from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


USER_AGENT = "Butler-SkillGitHubImport/0.1"
API_ROOT = "https://api.github.com/repos"


def _request_json(url: str) -> list[dict] | dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download_file(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def _sanitize_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(name or "").strip())
    cleaned = cleaned.strip("-_")
    return cleaned or "imported-skill"


def _download_tree(repo: str, path: str, ref: str, dest_dir: Path, *, base_path: str) -> list[str]:
    normalized_path = path.strip("/").replace("\\", "/")
    encoded_path = urllib.parse.quote(normalized_path)
    url = f"{API_ROOT}/{repo}/contents/{encoded_path}?ref={urllib.parse.quote(ref)}"
    payload = _request_json(url)
    if not isinstance(payload, list):
        raise RuntimeError(f"目标路径不是目录或不存在: {repo}:{path}@{ref}")
    downloaded: list[str] = []
    for item in payload:
        item_type = str(item.get("type") or "")
        rel_path = str(item.get("path") or "")
        relative_child = rel_path[len(base_path):].lstrip("/\\") if rel_path.startswith(base_path) else Path(rel_path).name
        target = dest_dir / relative_child
        if item_type == "dir":
            downloaded.extend(_download_tree(repo, rel_path, ref, dest_dir, base_path=base_path))
            continue
        if item_type != "file":
            continue
        download_url = str(item.get("download_url") or "").strip()
        if not download_url:
            continue
        _download_file(download_url, target)
        downloaded.append(relative_child.replace("\\", "/"))
    return downloaded


def main() -> int:
    parser = argparse.ArgumentParser(description="Download a GitHub skill directory into Butler sources/skills/pool.")
    parser.add_argument("--repo", required=True, help="GitHub repo in owner/repo form")
    parser.add_argument("--path", required=True, help="Path to the skill directory inside the repo")
    parser.add_argument("--ref", default="main", help="Git ref, default main")
    parser.add_argument("--dest-root", default="butler_main/sources/skills/pool/imported", help="Import root")
    parser.add_argument("--name", default="", help="Optional imported directory name")
    parser.add_argument("--replace", action="store_true", help="Replace target if it already exists")
    args = parser.parse_args()

    repo = str(args.repo or "").strip()
    path = str(args.path or "").strip().strip("/").replace("\\", "/")
    if "/" not in repo or not path:
        raise SystemExit("`--repo` must be owner/repo and `--path` must be a repo directory path")

    workspace = Path.cwd()
    dest_root = (workspace / args.dest_root).resolve()
    skill_name = _sanitize_name(args.name or Path(path).name)
    target_dir = dest_root / skill_name

    if target_dir.exists():
        if not args.replace:
            raise SystemExit(f"target already exists: {target_dir}")
        shutil.rmtree(target_dir)

    downloaded = _download_tree(repo, path, str(args.ref or "main"), target_dir, base_path=path)
    skill_file = target_dir / "SKILL.md"
    if not skill_file.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
        raise SystemExit(f"downloaded directory does not contain SKILL.md: {repo}:{path}@{args.ref}")

    metadata = {
        "repo": repo,
        "path": path,
        "ref": str(args.ref or "main"),
        "imported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_dir": str(target_dir.relative_to(workspace)).replace("\\", "/"),
        "file_count": len(downloaded),
        "files": downloaded,
    }
    (target_dir / "UPSTREAM_IMPORT.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    report = [
        "# GitHub Skill Import Report",
        "",
        f"- repo: `{repo}`",
        f"- path: `{path}`",
        f"- ref: `{args.ref}`",
        f"- target: `{metadata['target_dir']}`",
        f"- file_count: `{len(downloaded)}`",
        "",
        "## Next Steps",
        "",
        "1. 审阅 `SKILL.md` 与脚本副作用。",
        "2. 如需对 chat/codex 暴露，再更新 `butler_main/sources/skills/collections/registry.json`。",
        "3. 对脚本型 skill 再跑一次验证或沙箱试跑。",
        "",
    ]
    (target_dir / "IMPORT_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
