from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
for parent in [CURRENT_FILE, *CURRENT_FILE.parents]:
    if (parent / "butler_main").exists():
        import sys

        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

from butler_main.sources.skills.shared.workspace_layout import find_workspace_root, resolve_output_dir, skill_temp_dir


FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>[\s\S]*?)\n---\s*\n?", re.MULTILINE)
REQUIRED_FIELDS = ("name", "description")
ALLOWED_ROOTS = ("./butler_main/sources/skills/",)
INACTIVE_SKILL_STATUSES = {"draft", "incubating", "archived", "disabled", "private"}


def _parse_frontmatter(text: str) -> dict[str, str]:
    matched = FRONTMATTER_RE.match(text or "")
    if not matched:
        return {}
    metadata: dict[str, str] = {}
    for raw_line in matched.group("body").splitlines():
        line = str(raw_line or "").strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip().lower()] = value.strip().strip('"').strip("'")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Butler skill pool and collection registry.")
    parser.add_argument("--workspace", default=".", help="Butler workspace root")
    parser.add_argument("--output-dir", default="", help="Output directory; defaults to butler_main/sources/skills/temp/verify")
    args = parser.parse_args()

    workspace = find_workspace_root(Path(args.workspace).resolve())
    registry_path = workspace / "butler_main" / "sources" / "skills" / "collections" / "registry.json"
    output_dir = resolve_output_dir(workspace, args.output_dir, default_path=skill_temp_dir(workspace, "verify"))

    if not registry_path.exists():
        raise SystemExit(f"registry not found: {registry_path}")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    collections = registry.get("collections") or {}

    issues: list[dict] = []
    name_index: defaultdict[str, list[str]] = defaultdict(list)
    verified_count = 0
    for collection_id, payload in collections.items():
        for raw in payload.get("skills") or []:
            path_text = str(raw.get("path") if isinstance(raw, dict) else raw or "").replace("\\", "/")
            if not any(path_text.startswith(prefix) for prefix in ALLOWED_ROOTS):
                issues.append({"type": "invalid_root", "collection": collection_id, "path": path_text})
                continue
            skill_dir = workspace / path_text.lstrip("./")
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                issues.append({"type": "missing_skill_file", "collection": collection_id, "path": path_text})
                continue
            metadata = _parse_frontmatter(skill_file.read_text(encoding="utf-8", errors="ignore"))
            missing = [field for field in REQUIRED_FIELDS if not str(metadata.get(field) or "").strip()]
            if missing:
                issues.append({"type": "missing_frontmatter_fields", "collection": collection_id, "path": path_text, "fields": missing})
            status = str(metadata.get("status") or "active").strip().lower() or "active"
            if status in INACTIVE_SKILL_STATUSES:
                issues.append({"type": "inactive_skill_exposed", "collection": collection_id, "path": path_text, "status": status})
            name = str(metadata.get("name") or skill_dir.name).strip().lower()
            name_index[name].append(path_text)
            verified_count += 1

    for name, paths in sorted(name_index.items()):
        unique_paths = sorted(set(paths))
        if len(unique_paths) > 1:
            issues.append({"type": "duplicate_skill_name", "name": name, "paths": unique_paths})

    result = {
        "verified_skills": verified_count,
        "collection_count": len(collections),
        "issue_count": len(issues),
        "issues": issues,
    }
    (output_dir / "skill_pool_verify.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Skill Pool Verify Report",
        "",
        f"- collection_count: `{len(collections)}`",
        f"- verified_skills: `{verified_count}`",
        f"- issue_count: `{len(issues)}`",
        "",
    ]
    if issues:
        lines.append("## Issues")
        lines.append("")
        for issue in issues:
            lines.append(f"- `{issue['type']}`: `{json.dumps(issue, ensure_ascii=False)}`")
        lines.append("")
    else:
        lines.append("## Result")
        lines.append("")
        lines.append("- No issues found.")
        lines.append("")
    (output_dir / "skill_pool_verify_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
